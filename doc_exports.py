"""Dependency-free DOCX/HTML export and optional ReportLab PDF. Data always scoped by caller."""
import io,zipfile,datetime,html,os
from xml.sax.saxutils import escape

def contents(conn,u,kind,allowed):
    if u['role'] not in ('teacher','director','deputy','social'):raise PermissionError('Есеп экспортына рұқсат жоқ')
    if kind=='social' and u['role'] not in ('teacher','social'):raise PermissionError('Әлеуметтік паспорт құпия')
    if u['role']=='teacher' and not allowed:return ('Құжат жобасы', [('Мәлімет','Өз сыныбыңыз жоқ')])
    label={
        'plan':'Сыныптың тәрбие жұмысы жоспары',
        'analysis':'Тәрбие жұмысының талдауы',
        'social':'Сыныптың әлеуметтік паспорты',
        'minutes':'Ата-аналар жиналысының хаттамасы',
        'lesson':'Сынып сағаты журналы',
        'summary':'Сынып жетекшісінің жиынтық есебі',
    }.get(kind)
    if not label:raise ValueError('Құжат түрі табылмады')
    today=datetime.date.today().isoformat()
    out=[('Құжат мәртебесі','ЖОБА — педагог пен мектептің бекітуі қажет'),('Құрылған күні',today),('Дерек көзі','ClassMate AI жергілікті мәліметтер қоры'),('Нұсқасы','v3.0 / экспорт 1')]
    pred=(' WHERE class_id IN ('+','.join('?'*len(allowed))+')') if u['role']=='teacher' else ''
    params=allowed if u['role']=='teacher' else ()
    if kind in ('plan','analysis'):
        q='SELECT topic,day,status,kind FROM activities'+pred+' ORDER BY day'
        acts=conn.execute(q,params).fetchall()
        out.extend([('Іс-шара',f'{a[1]} | {a[0]} | {a[2]}') for a in acts] or [('Жоспар','Жазба жоқ')])
        if kind=='analysis':
            out.append(('Жоспар орындалуы',str(sum(a[2]=='completed' for a in acts))+' / '+str(len(acts))))
    elif kind=='minutes':
        q='SELECT day,agenda,minutes,status FROM meetings'+pred+' ORDER BY day DESC'
        vals=conn.execute(q,params).fetchall()
        for x in vals:out.extend([('Күні',x[0]),('Күн тәртібі',x[1]),('Хаттама жобасы',x[2]),('Мәртебе',x[3])])
        if not vals:out.append(('Хаттама','Әлі енгізілмеген'))
    elif kind=='lesson':
        q='SELECT day,topic,reflection,status FROM lesson_logs'+pred+' ORDER BY day DESC'
        vals=conn.execute(q,params).fetchall()
        out.extend([('Сынып сағаты',f'{x[0]} | {x[1]} | {x[2]} | {x[3]}') for x in vals] or [('Журнал','Жазба жоқ')])
    elif kind=='social':
        if u['role']=='teacher':
            rows=conn.execute('SELECT s.full_name,sp.category,sp.support FROM social_passports sp JOIN students s ON s.id=sp.student_id WHERE s.class_id IN ('+','.join('?'*len(allowed))+')',allowed).fetchall()
        else:rows=conn.execute('SELECT s.full_name,sp.category,sp.support FROM social_passports sp JOIN students s ON s.id=sp.student_id').fetchall()
        out.extend([('Қолдау жазбасы',f'{x[0]} | {x[1]} | {x[2]}') for x in rows] or [('Әлеуметтік паспорт','Жазба жоқ')])
    else:
        if u['role']=='teacher':
            count=conn.execute('SELECT COUNT(*) FROM students WHERE archived=0 AND class_id IN ('+','.join('?'*len(allowed))+')',allowed).fetchone()[0]
            att=conn.execute('SELECT status,COUNT(*) FROM attendance WHERE student_id IN (SELECT id FROM students WHERE class_id IN ('+','.join('?'*len(allowed))+')) GROUP BY status',allowed).fetchall()
        else:
            count=conn.execute('SELECT COUNT(*) FROM students WHERE archived=0').fetchone()[0]
            att=conn.execute('SELECT status,COUNT(*) FROM attendance GROUP BY status').fetchall()
        out.append(('Оқушы саны',str(count)))
        out.extend([('Қатысу көрсеткіші',f'{r[0]}: {r[1]}') for r in att])
    out.append(('Ескертпе','Ресми құжат нысаны емес. Мектеп бекіткен үлгіге тексеріп сәйкестендіру қажет.'))
    return label,out

def make_docx(title,lines):
    text=lambda s:escape(str(s or ''))
    paragraphs=[]
    def p(t,bold=False):
        q='<w:b/>' if bold else ''
        return '<w:p><w:r><w:rPr>'+q+'</w:rPr><w:t xml:space="preserve">'+text(t)+'</w:t></w:r></w:p>'
    paragraphs.append(p(title,True))
    for name,value in lines:
        paragraphs.append(p(str(name)+': '+str(value)))
    body=''.join(paragraphs)+'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1200" w:bottom="1200" w:left="1200" w:right="1200"/></w:sectPr>'
    doc='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+body+'</w:body></w:document>'
    types='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rel='<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',types)
        z.writestr('_rels/.rels',rel)
        z.writestr('word/document.xml',doc)
    return b.getvalue()

def make_html(title,lines):
    h=lambda x:html.escape(str(x or ''))
    rows=''.join('<tr><th>'+h(n)+'</th><td>'+h(v)+'</td></tr>' for n,v in lines)
    return ('<!doctype html><html lang="kk"><meta charset="utf-8"><title>'+h(title)+'</title><style>body{font:15px Arial,sans-serif;margin:40px;line-height:1.55}h1{font-size:22px}th,td{padding:10px;text-align:left;border:1px solid #aaa;vertical-align:top}table{border-collapse:collapse;width:100%}th{width:25%}@media print{button{display:none}}</style><h1>'+h(title)+'</h1><table>'+rows+'</table><p><b>Жоба.</b> Педагог тексеріп бекітеді.</p><button onclick="window.print()">PDF ретінде сақтау / Басып шығару</button></html>').encode('utf-8')

def make_pdf(title,lines):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        raise RuntimeError('PDF модулі жоқ. Браузерден «Басып шығару → PDF ретінде сақтау» қолданыңыз.')
    font=next((x for x in [r'C:\Windows\Fonts\arial.ttf',r'C:\Windows\Fonts\times.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if os.path.exists(x)),None)
    if not font:raise RuntimeError('Кирилл қарпі табылмады. HTML басып шығару мүмкіндігін қолданыңыз.')
    pdfmetrics.registerFont(TTFont('ClassmateFont',font))
    b=io.BytesIO();cv=canvas.Canvas(b,pagesize=A4);width,height=A4;x=42;y=height-60
    cv.setFont('ClassmateFont',14);cv.drawString(x,y,title[:80]);y-=37;cv.setFont('ClassmateFont',10)
    for name,value in lines:
        txt=f'{name}: {value}'.replace('\r',' ').replace('\n',' ')
        while txt:
            segment=txt[:95];txt=txt[95:]
            if y<65:cv.showPage();y=height-50;cv.setFont('ClassmateFont',10)
            cv.drawString(x,y,segment);y-=20
        y-=7
    cv.save();return b.getvalue()
