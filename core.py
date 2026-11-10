"""ClassMate AI — local educational prototype (Python standard library + SQLite)."""
import json, sqlite3, os, csv, io, re, secrets, hashlib, hmac, datetime, threading, zipfile, html, urllib.request, urllib.error, time, copy, base64
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http import cookies
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('CLASSMATE_DB_PATH', str(ROOT/'classmate.db')))
TOKENS={}
FAILED={}
LOCK=threading.RLock()
ROLES=('teacher','subject','parent','student','nurse','psychologist','social','admin','director','deputy')
ROLE_NAMES={'teacher':'Сынып жетекшісі','subject':'Пән мұғалімі','parent':'Ата-ана','student':'Оқушы','nurse':'Медицина қызметкері','psychologist':'Психолог','social':'Әлеуметтік педагог','admin':'Әкімші','director':'Директор','deputy':'Тәрбие ісі жөніндегі орынбасар'}

def conn():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def pwd_hash(s,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+'$'+hashlib.pbkdf2_hmac('sha256',s.encode(),salt.encode(),160000).hex()
def check_pwd(s,h):
 salt=h.split('$')[0];return hmac.compare_digest(pwd_hash(s,salt),h)

def init():
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,name TEXT NOT NULL,student_id INTEGER);
CREATE TABLE IF NOT EXISTS classes(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,teacher_id INTEGER);
CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY,full_name TEXT NOT NULL,class_id INTEGER NOT NULL,guardian_name TEXT DEFAULT '',guardian_contact TEXT DEFAULT '',notes TEXT DEFAULT '',FOREIGN KEY(class_id) REFERENCES classes(id));
CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY,name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS enrollments(id INTEGER PRIMARY KEY,student_id INTEGER,subject_id INTEGER,UNIQUE(student_id,subject_id));
CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY,student_id INTEGER NOT NULL,subject TEXT NOT NULL,day TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(student_id,subject,day));
CREATE TABLE IF NOT EXISTS grades(id INTEGER PRIMARY KEY,student_id INTEGER,subject TEXT,score INTEGER,max_score INTEGER,day TEXT DEFAULT CURRENT_DATE,created_by INTEGER);
CREATE TABLE IF NOT EXISTS homework(id INTEGER PRIMARY KEY,student_id INTEGER,subject TEXT,title TEXT,status TEXT,day TEXT DEFAULT CURRENT_DATE);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,student_id INTEGER,channel TEXT NOT NULL,recipient TEXT NOT NULL,body TEXT NOT NULL,state TEXT DEFAULT 'draft',created_at TEXT DEFAULT CURRENT_TIMESTAMP,approved_by INTEGER);
CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,student_id INTEGER,category TEXT NOT NULL,details TEXT NOT NULL,status TEXT DEFAULT 'new',private INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY,class_id INTEGER,topic TEXT,scenario TEXT,approved INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor_id INTEGER,action TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY,class_id INTEGER,kind TEXT NOT NULL,topic TEXT NOT NULL,day TEXT,status TEXT DEFAULT 'planned',description TEXT DEFAULT '',created_by INTEGER);
CREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY,class_id INTEGER,day TEXT,agenda TEXT NOT NULL,minutes TEXT DEFAULT '',status TEXT DEFAULT 'draft',created_by INTEGER);
CREATE TABLE IF NOT EXISTS social_passports(id INTEGER PRIMARY KEY,student_id INTEGER UNIQUE,category TEXT DEFAULT '',support TEXT DEFAULT '',updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS surveys(id INTEGER PRIMARY KEY,class_id INTEGER,question TEXT,answer TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY,class_id INTEGER,subject TEXT,title TEXT,deadline TEXT,status TEXT DEFAULT 'active',created_by INTEGER);
CREATE TABLE IF NOT EXISTS permissions(id INTEGER PRIMARY KEY,student_id INTEGER,kind TEXT,granted INTEGER DEFAULT 0,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(student_id,kind));
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,student_id INTEGER,kind TEXT,body TEXT,status TEXT DEFAULT 'new',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS import_jobs(id INTEGER PRIMARY KEY,name TEXT,kind TEXT,rows_count INTEGER DEFAULT 0,status TEXT DEFAULT 'review',details TEXT,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS saved_reports(id INTEGER PRIMARY KEY,kind TEXT,title TEXT,payload TEXT,approved INTEGER DEFAULT 0,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ai_activity(id INTEGER PRIMARY KEY,actor_id INTEGER,kind TEXT,prompt TEXT,result TEXT,status TEXT DEFAULT 'draft',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS school_settings(id INTEGER PRIMARY KEY CHECK(id=1),school_name TEXT DEFAULT 'Демонстрациялық мектеп',academic_year TEXT DEFAULT '2026–2027');''')
  # No hard-coded passwords or demo users. Admin account is created on first local launch.
  try: c.execute('ALTER TABLE users ADD COLUMN must_change INTEGER DEFAULT 0')
  except sqlite3.OperationalError: pass
  try: c.execute('ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1')
  except sqlite3.OperationalError: pass
  c.execute('CREATE TABLE IF NOT EXISTS user_classes(user_id INTEGER NOT NULL,class_id INTEGER NOT NULL,PRIMARY KEY(user_id,class_id))')
  c.execute("INSERT OR IGNORE INTO school_settings(id) VALUES(1)")

def audit(c,u,action,details=''):
 c.execute('INSERT INTO audit(actor_id,action,details) VALUES(?,?,?)',(u['id'],action,str(details)[:500]))
def rows(c,sql,params=()):return [dict(r) for r in c.execute(sql,params)]
def nowday():return datetime.date.today().isoformat()
def scenario(cls,topic):
 return f'''Тақырыбы: {topic}\nСынып: {cls}\nҰзақтығы: 40 минут\nМақсаты: оқушылардың тақырып бойынша түсінігін кеңейту және пікір алмасуға жағдай жасау.\n1. Ұйымдастыру (3 мин): сәлемдесу және қауіпсіз орта ережесін еске салу.\n2. Қызығушылық ояту (5 мин): «{topic}» туралы ашық сұрақтар.\n3. Негізгі бөлім (15 мин): шағын жағдаяттарды жұпта талдау, дәлел келтіру.\n4. Топтық тапсырма (10 мин): тақырыпқа қатысты 3 нақты ұсынысты постерге жазу.\n5. Кері байланыс (5 мин): «Бүгін білдім / әлі білгім келеді».\n6. Қорытынды (2 мин): келісілген ортақ әрекетті анықтау.\nБағалау: өзіндік рефлексия және қатысу белсенділігі; балаға жария рейтинг қойылмайды.\nЕскерту: бұл ережеге сай екені тексерілуі тиіс үлгі. Мұғалім өңдеп, бекітеді.'''

# Qwen3 is already installed by the user in local Ollama. No paid API or pip package.
OLLAMA_URL=os.environ.get('CLASSMATE_OLLAMA_URL','http://127.0.0.1:11434/api/chat')
OLLAMA_MODEL=os.environ.get('CLASSMATE_OLLAMA_MODEL','qwen3:4b')

def ollama_compose(kind, prompt, class_name):
    kind = kind if kind in ('class_hour','parent_message','meeting','report') else 'class_hour'
    tasks = {
        'class_hour': (f'Тәрбие сағаты: {class_name}. Тақырып: {prompt}. '
                       '40 минуттық нақты сценарий жаз: мақсаты; кіріспе (5 мин); '
                       'негізгі түсіндіру (10 мин); үш тәжірибелік тапсырма (әрқайсысы 5 минут); '
                       'рефлексия (5 мин); қорытынды (5 мин). Барлығы 40 минут. '
                       'Тапсырмалардың орындалу қадамдарын көрсет.'),
        'parent_message': ('Ата-анаға құрметті, бейтарап хабарлама ЖОБАСЫН жаз. '
                           'Мұғалім оны тексеріп бекіткен соң ғана жіберуге болады. Жағдай: '+prompt),
        'meeting': ('Ата-аналар жиналысына күн тәртібі мен хаттама ЖОБАСЫН жаз. '
                    'Шешімдер мен қатысу фактілерін ойдан қоспа. Тақырып: '+prompt),
        'report': ('Сынып жетекшісіне ресми емес есеп ЖОБАСЫН дайында. '
                   'Нақты дерек берілмесе, сан мен факт ойдан шығарма, бос орын немесе үлгі деп көрсет. Сұраныс: '+prompt),
    }
    payload={
        'model':OLLAMA_MODEL,
        'stream':False,
        'think':False,
        'keep_alive':'20s',
        'options':{'temperature':0.2,'repeat_penalty':1.18,'num_ctx':1536,'num_predict':540},
        'messages':[
            {'role':'system','content':(
                'Сен ClassMate AI жүйесіндегі педагогке арналған мәтін көмекшісісің. '
                'Тек сауатты қазақ тілінде жаз. Ағылшынша түсіндірме, ойлау процесі немесе өзіңнің жоспарың туралы пікір жазба. '
                'Тікелей қолдануға болатын нақты мәтін бер. Шұбалаңқы сөз қайталама. '
                'Оқушыға диагноз, жаза немесе қорытынды баға қойма. '
                'Деректерді ойдан шығарма. Барлық нәтиже педагог тексеретін жоба болып табылады.')},
            {'role':'user','content':'/no_think\n'+tasks[kind]}
        ]
    }
    req=urllib.request.Request(OLLAMA_URL,data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result=json.load(resp)
    except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
        raise RuntimeError('Ollama жауап бермеді. Ол компьютерде қосылып тұрғанын тексеріңіз.') from exc
    answer=str(result.get('message',{}).get('content','')).strip()
    # Ignore reasoning if any older model/version embeds it in content.
    answer=re.sub(r'<think>.*?</think>','',answer,flags=re.S|re.I).strip()
    if '<think>' in answer.lower():
        answer=answer.split('</think>')[-1].strip() if '</think>' in answer.lower() else ''
    if not answer:
        raise RuntimeError('ЖИ дайын мәтін қайтармады. Кейін қайта көріңіз.')
    return answer[:13000]

def classify(text):
 t=text.lower()
 if any(x in t for x in ['жиналыс','хаттама','ата-ана жиналысы']):return 'Ата-аналармен жұмыс'
 if any(x in t for x in ['сынып сағат','тәрбие сағат','тәрбие жоспары']):return 'Тәрбие жоспары'
 if any(x in t for x in ['буллинг','қауіпсіздік','тәртіп']):return 'Қауіпсіздік және профилактика'
 if any(x in t for x in ['келмеді','қатысу','кешігу']):return 'Қатысу және үлгерім'
 if any(x in t for x in ['медицин','дәрігер','мазасы']):return 'Медициналық көмек'
 if any(x in t for x in ['әлеуметтік','отбасы','қамқоршы']):return 'Әлеуметтік паспорт'
 return 'Құжаттар және есептер'

def report(c):
 sts=c.execute('SELECT COUNT(*) FROM students').fetchone()[0]
 att=rows(c,'SELECT status,COUNT(*) n FROM attendance GROUP BY status')
 miss=rows(c,"SELECT s.full_name,a.subject,a.day FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.status='absent' ORDER BY a.id DESC LIMIT 20")
 pending=c.execute("SELECT COUNT(*) FROM messages WHERE state='draft'").fetchone()[0]
 plan=c.execute('SELECT COUNT(*) FROM plans').fetchone()[0]
 return {'students':sts,'attendance':att,'absences':miss,'draft_messages':pending,'plans':plan,'generated':datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

def extract_uploaded(name,encoded):
 raw=base64.b64decode(encoded,validate=True)
 if len(raw)>1800000:raise ValueError('Файл тым үлкен (1.8 МБ)')
 ext=Path(name).suffix.lower()
 if ext in ('.txt','.md','.csv'):
  try:return raw.decode('utf-8-sig')
  except UnicodeDecodeError:return raw.decode('cp1251',errors='replace')
 if ext=='.docx':
  from docx import Document
  doc=Document(io.BytesIO(raw));parts=[p.text for p in doc.paragraphs]
  for t in doc.tables:
   for r in t.rows:parts.append(' | '.join(c.text for c in r.cells))
  return '\n'.join(parts)[:100000]
 if ext=='.xlsx':
  from openpyxl import load_workbook
  book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
  parts=[]
  for sheet in book.worksheets[:3]:
   parts.append('Парақ: '+sheet.title)
   for row in sheet.iter_rows(max_row=1200,values_only=True):parts.append(' | '.join(str(v or '') for v in row[:25]))
  book.close();return '\n'.join(parts)[:100000]
 raise ValueError('Тек TXT, CSV, DOCX, XLSX файлдары')

def generate_export(d,fmt,kind):
 title={'summary':'Сынып жетекшісінің жинақталған есебі','attendance':'Сабаққа қатысу есебі','planning':'Тәрбие жұмысының талдауы'}.get(kind,'Сынып жетекшісінің есебі')
 lines=[('Жасалған уақыты',d['generated']),('Оқушы саны',str(d['students'])),('Тәрбие сағаты жоспарлары',str(d['plans'])),('Хабарлама жобалары',str(d['draft_messages']))]
 table=[('Мәртебе','Саны')]+[(x['status'],str(x['n'])) for x in d['attendance']]
 if fmt=='docx':
  from docx import Document
  from docx.shared import Pt
  doc=Document();doc.add_heading(title,0)
  for a,b in lines:doc.add_paragraph(f'{a}: {b}')
  t=doc.add_table(rows=0,cols=2);t.style='Table Grid'
  for a,b in table:
   cells=t.add_row().cells;cells[0].text=a;cells[1].text=b
  doc.add_paragraph('Жоба. Ақпаратты сынып жетекшісі тексеріп, бекітеді.')
  for p in doc.paragraphs:
   for r in p.runs:r.font.name='Times New Roman';r.font.size=Pt(12)
  b=io.BytesIO();doc.save(b);return b.getvalue()
 if fmt=='xlsx':
  from openpyxl import Workbook
  from openpyxl.styles import Font
  wb=Workbook();ws=wb.active;ws.title='Есеп';ws.append([title])
  for row in lines:ws.append(list(row))
  ws.append([])
  for row in table:ws.append(list(row))
  ws.column_dimensions['A'].width=36;ws.column_dimensions['B'].width=24;ws['A1'].font=Font(bold=True,size=15)
  b=io.BytesIO();wb.save(b);return b.getvalue()
 from reportlab.pdfgen import canvas
 from reportlab.lib.pagesizes import A4
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
 if not os.path.exists(font):font='/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'
 pdfmetrics.registerFont(TTFont('KazakhFont',font))
 b=io.BytesIO();c=canvas.Canvas(b,pagesize=A4);c.setFont('KazakhFont',14);c.drawString(45,790,title);y=755;c.setFont('KazakhFont',10)
 for a,v in lines+table:
  c.drawString(45,y,f'{a}: {v}');y-=24
 c.drawString(45,y-25,'Жоба. Педагогтің тексеруі қажет.');c.save();return b.getvalue()

def valid_password(p):
 return isinstance(p,str) and 12<=len(p)<=128 and any(x.isalpha() for x in p) and any(x.isdigit() for x in p)

def allowed_student(c,u,sid):
 if u['role'] in ('parent','student'):return u['student_id']==sid
 if u['role'] in ('teacher','subject'):
  return bool(c.execute("SELECT 1 FROM students s JOIN classes cl ON cl.id=s.class_id WHERE s.id=? AND (cl.teacher_id=? OR EXISTS(SELECT 1 FROM user_classes uc WHERE uc.class_id=cl.id AND uc.user_id=?))",(sid,u['id'],u['id'])).fetchone())
 return u['role'] in ('admin','director','deputy','social','nurse','psychologist')

def allowed_class(c,u,cl):
 if u['role'] in ('teacher','subject'):
  return bool(c.execute('SELECT 1 FROM classes WHERE id=? AND (teacher_id=? OR EXISTS(SELECT 1 FROM user_classes WHERE class_id=? AND user_id=?))',(cl,u['id'],cl,u['id'])).fetchone())
 return u['role'] in ('admin','director','deputy')

class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):pass
 def send(self,data,status=200,type='application/json; charset=utf-8',headers=None):
  raw=(json.dumps(data,ensure_ascii=False).encode() if type.startswith('application/json') else data)
  self.send_response(status);self.send_header('Content-Type',type);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(raw)
 def user(self):
  cookie=cookies.SimpleCookie();
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:return None
  token=cookie.get('session');record=TOKENS.get(token.value) if token else None
  if record and record[1]<time.time():TOKENS.pop(token.value,None);record=None
  id=record[0] if record else None
  if not id:return None
  with conn() as c:
   r=c.execute('SELECT id,role,name,username,student_id,must_change,active FROM users WHERE id=?',(id,)).fetchone()
  return dict(r) if r and r['active'] else None
 def body(self):
  if int(self.headers.get('Content-Length','0'))>4000000:return None
  try:return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
  except Exception:return None
 def fail(self,msg,status=400):self.send({'error':msg},status)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/':return self.send((ROOT/'index.html').read_bytes(),type='text/html; charset=utf-8')
  u=self.user()
  if path=='/api/status':
   with conn() as c:needed=not bool(c.execute('SELECT 1 FROM users').fetchone())
   return self.send({'setup_required':needed,'version':'2.0-local'})
  if path=='/api/me':
   cookie=cookies.SimpleCookie();cookie.load(self.headers.get('Cookie',''))
   tok=cookie.get('session');session=TOKENS.get(tok.value) if tok else None
   return self.send({'user':u,'csrf':session[2] if session and u else None})
  if not u:return self.fail('Алдымен жүйеге кіріңіз',401)
  if u['must_change']:return self.fail('Алдымен уақытша құпиясөзді өзгертіңіз',403)
  with conn() as c:
   if path=='/api/users':
    if u['role']!='admin':return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,'SELECT id,username,role,name,student_id,must_change,active FROM users ORDER BY id'))
   if path=='/api/ai/status':
    if u['role'] not in ('teacher','deputy'):return self.fail('Рұқсат жоқ',403)
    try:
     url=OLLAMA_URL.replace('/api/chat','/api/tags')
     with urllib.request.urlopen(url,timeout=3) as response:models=json.load(response).get('models',[])
     found=any(v.get('name','').split(':')[0]==OLLAMA_MODEL.split(':')[0] and v.get('name','').split(':')[-1]==OLLAMA_MODEL.split(':')[-1] for v in models)
     return self.send({'connected':True,'model':OLLAMA_MODEL,'installed':found})
    except Exception:return self.send({'connected':False,'model':OLLAMA_MODEL,'installed':False})
   if path=='/api/overview':
    base=report(c) if u['role'] in ('teacher','director','deputy','admin') else {'students':0,'plans':0,'draft_messages':0,'attendance':[]}
    if u['role'] in ('teacher','director','deputy','admin'):
     base['activities']=rows(c,"SELECT * FROM activities ORDER BY day DESC LIMIT 20")
     base['pending_cases']=c.execute("SELECT COUNT(*) FROM cases WHERE status='new' AND category!='psych_private'").fetchone()[0]
     base['meetings']=c.execute('SELECT COUNT(*) FROM meetings').fetchone()[0]
     base['tasks']=rows(c,"SELECT id,topic,day,status FROM activities WHERE status!='completed' ORDER BY day LIMIT 8")
    else:base['activities']=[];base['pending_cases']=0;base['meetings']=0;base['tasks']=[]
    return self.send(base)
   if path=='/api/catalog':
    return self.send({'classes':rows(c,'SELECT id,name FROM classes'),'subjects':rows(c,'SELECT id,name FROM subjects')})
   if path=='/api/dashboard':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    data=report(c);data['cases']=rows(c,"SELECT category,status,COUNT(*) n FROM cases GROUP BY category,status") if u['role'] in ('teacher','director','deputy','admin','nurse','psychologist','social') else []
    return self.send(data)
   if path=='/api/classes':
    if u['role'] in ('teacher','subject'):
     return self.send(rows(c,'SELECT id,name FROM classes WHERE teacher_id=? OR id IN(SELECT class_id FROM user_classes WHERE user_id=?)',(u['id'],u['id'])))
    if u['role'] in ('parent','student'):
     return self.send(rows(c,'SELECT id,name FROM classes WHERE id=(SELECT class_id FROM students WHERE id=?)',(u['student_id'],)))
    if u['role'] in ('nurse','psychologist'):return self.send([])
    return self.send(rows(c,'SELECT id,name FROM classes'))
   if path=='/api/students':
    if u['role'] in ('parent','student'):
     return self.send(rows(c,'SELECT id,full_name,class_id FROM students WHERE id=?',(u['student_id'],)))
    if u['role'] in ('nurse','psychologist'):return self.fail('Оқушылар тізімі бұл рөл үшін ашық емес',403)
    if u['role'] in ('teacher','subject'):
     return self.send(rows(c,'SELECT s.id,s.full_name,s.class_id,cl.name class_name,s.guardian_name FROM students s JOIN classes cl ON cl.id=s.class_id WHERE cl.teacher_id=? OR s.class_id IN(SELECT class_id FROM user_classes WHERE user_id=?) ORDER BY s.id',(u['id'],u['id'])))
    if u['role']=='social':return self.fail('Бұл тізім үшін рұқсат жоқ',403)
    return self.send(rows(c,'SELECT s.*,cl.name class_name FROM students s JOIN classes cl ON cl.id=s.class_id ORDER BY s.id'))
   if path=='/api/attendance':
    sql='SELECT a.*,s.full_name FROM attendance a JOIN students s ON s.id=a.student_id'
    if u['role'] in ('parent','student'):return self.send(rows(c,sql+' WHERE student_id=? ORDER BY a.id DESC LIMIT 100',(u['student_id'],)))
    if u['role'] in ('teacher','subject'):
     return self.send(rows(c,sql+' JOIN classes cl ON cl.id=s.class_id WHERE cl.teacher_id=? OR s.class_id IN(SELECT class_id FROM user_classes WHERE user_id=?) ORDER BY a.id DESC LIMIT 100',(u['id'],u['id'])))
    if u['role'] in ('director','deputy','admin'):return self.send(rows(c,sql+' ORDER BY a.id DESC LIMIT 100'))
    return self.fail('Рұқсат жоқ',403)
   if path=='/api/messages':
    if u['role'] in ('teacher','admin','director','deputy'):return self.send(rows(c,'SELECT m.*,s.full_name FROM messages m LEFT JOIN students s ON s.id=m.student_id ORDER BY m.id DESC LIMIT 100'))
    if u['role'] in ('parent','student'):return self.send(rows(c,"SELECT m.id,m.body,m.state,m.created_at FROM messages m WHERE m.student_id=? AND m.state='approved' ORDER BY m.id DESC",(u['student_id'],)))
    return self.fail('Рұқсат жоқ',403)
   if path=='/api/cases':
    role=u['role']
    if role in ('parent','student'):return self.send(rows(c,"SELECT id,category,details,status,created_at FROM cases WHERE student_id=? AND category='medical'",(u['student_id'],)))
    allowed={'teacher':"category!='psych_private'",'nurse':"category='medical'",'psychologist':"category='psych_private'",'social':"category='social'",'admin':"1=0",'director':"1=0"}
    if role not in allowed:return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,f'SELECT id,student_id,category,details,status,created_at FROM cases WHERE {allowed[role]} ORDER BY id DESC LIMIT 100'))
   if path=='/api/plans':return self.send(rows(c,'SELECT p.*,cl.name class_name FROM plans p LEFT JOIN classes cl ON cl.id=p.class_id ORDER BY p.id DESC LIMIT 80')) if u['role'] in ('teacher','director','deputy','admin') else self.fail('Рұқсат жоқ',403)
   if path=='/api/records':return self.send(rows(c,'SELECT id,kind,title,content,created_at FROM records ORDER BY id DESC LIMIT 100')) if u['role'] in ('teacher','director','admin') else self.fail('Рұқсат жоқ',403)
   if path=='/api/audit':return self.send(rows(c,'SELECT a.created_at,u.name actor,a.action,a.details FROM audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 80')) if u['role']=='admin' else self.fail('Рұқсат жоқ',403)
   if path=='/api/activities':
    if u['role'] not in ('teacher','director','deputy','admin','parent','student'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,"SELECT a.*,cl.name class_name FROM activities a LEFT JOIN classes cl ON cl.id=a.class_id ORDER BY a.day DESC LIMIT 150"))
   if path=='/api/meetings':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,"SELECT m.*,cl.name class_name FROM meetings m LEFT JOIN classes cl ON cl.id=m.class_id ORDER BY m.id DESC LIMIT 100"))
   if path=='/api/social_profiles':
    if u['role'] not in ('teacher','social'):return self.fail('Құпия деректерге қолжетімділік жоқ',403)
    return self.send(rows(c,'SELECT sp.*,s.full_name FROM social_passports sp JOIN students s ON s.id=sp.student_id ORDER BY sp.id DESC'))
   if path=='/api/assignments':
    if u['role'] not in ('teacher','subject','parent','student','director','deputy'):return self.fail('Рұқсат жоқ',403)
    if u['role'] in ('parent','student'):
     return self.send(rows(c,'SELECT a.* FROM assignments a JOIN students s ON s.class_id=a.class_id WHERE s.id=? ORDER BY a.id DESC',(u['student_id'],)))
    return self.send(rows(c,'SELECT * FROM assignments ORDER BY id DESC LIMIT 150'))
   if path=='/api/surveys':
    if u['role'] in ('teacher','psychologist'):
     return self.send(rows(c,'SELECT class_id,answer,COUNT(*) AS count FROM surveys GROUP BY class_id,answer'))
    return self.fail('Рұқсат жоқ',403)
   if path=='/api/notifications':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,'SELECT * FROM notifications ORDER BY id DESC LIMIT 100'))
   if path=='/api/import_jobs':
    if u['role'] not in ('teacher','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,'SELECT id,name,kind,rows_count,status,created_at FROM import_jobs ORDER BY id DESC LIMIT 80'))
   if path=='/api/reports/saved':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,'SELECT id,title,kind,approved,created_at FROM saved_reports ORDER BY id DESC LIMIT 100'))
   if path=='/api/ai/history':
    if u['role'] not in ('teacher','director','deputy'):return self.fail('Рұқсат жоқ',403)
    return self.send(rows(c,'SELECT id,kind,prompt,result,status,created_at FROM ai_activity WHERE actor_id=? ORDER BY id DESC LIMIT 40',(u['id'],)))
   if path=='/api/analytics':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send({'attendance':rows(c,'SELECT substr(day,1,7) month,status,COUNT(*) count FROM attendance GROUP BY month,status ORDER BY month DESC'),'grades':rows(c,'SELECT subject,ROUND(AVG(100.0*score/max_score),1) average FROM grades WHERE max_score>0 GROUP BY subject'),'activities':rows(c,'SELECT kind,status,COUNT(*) count FROM activities GROUP BY kind,status'),'assignments':rows(c,'SELECT subject,status,COUNT(*) count FROM assignments GROUP BY subject,status')})
   if path=='/api/export':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    qs=parse_qs(urlparse(self.path).query);fmt=qs.get('format',['docx'])[0];kind=qs.get('kind',['summary'])[0]
    if fmt not in ('docx','pdf','xlsx'):return self.fail('Формат жоқ')
    d=report(c);name='ClassMate_AI_report_'+nowday()+'.'+fmt
    try:
     content=generate_export(d,fmt,kind)
     audit(c,u,'Есеп экспортталды',fmt)
    except ImportError:return self.fail('Экспорт кітапханалары орнатылмаған',501)
    return self.send(content,type={'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','pdf':'application/pdf','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[fmt],headers={'Content-Disposition':f'attachment; filename="{name}"'})
   if path=='/api/report':
    if u['role'] not in ('teacher','director','deputy','admin'):return self.fail('Рұқсат жоқ',403)
    return self.send(report(c))
  self.fail('Бет табылмады',404)
 def do_POST(self):
  path=urlparse(self.path).path;d=self.body()
  if not isinstance(d,dict):return self.fail('JSON деректері дұрыс емес')
  if path=='/api/setup':
   # First admin can only be created from the computer running this server.
   if self.client_address[0] not in ('127.0.0.1','::1'):return self.fail('Алғашқы баптауды сервер компьютерінде жасаңыз',403)
   username=str(d.get('username','')).strip().lower();name=str(d.get('name','')).strip();pw=d.get('password','')
   if not re.fullmatch(r'[a-z0-9._-]{3,32}',username) or not name or not valid_password(pw):return self.fail('Логин 3–32 таңба, пароль кемі 12 таңба (әріп пен сан) болуы керек')
   with LOCK,conn() as c:
    if c.execute('SELECT 1 FROM users').fetchone():return self.fail('Әкімші тіркеліп қойған',403)
    c.execute('INSERT INTO users(username,password,role,name,must_change,active) VALUES(?,?,?,?,0,1)',(username,pwd_hash(pw),'admin',name))
   return self.send({'ok':True})
  # The browser includes an anti-CSRF token for all authenticated POST actions.
  if path not in ('/api/login',):
   u0=self.user()
   if not u0:return self.fail('Алдымен жүйеге кіріңіз',401)
   ck=cookies.SimpleCookie();ck.load(self.headers.get('Cookie',''))
   tok=ck.get('session');rec=TOKENS.get(tok.value) if tok else None
   if not rec or not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),rec[2]):return self.fail('Қауіпсіздік токені жоқ',403)
   if u0['must_change'] and path not in ('/api/change-password','/api/logout'):return self.fail('Алдымен құпиясөзді өзгертіңіз',403)
  if path=='/api/login':
   with conn() as c:r=c.execute('SELECT * FROM users WHERE username=?',(str(d.get('username','')),)).fetchone()
   username=str(d.get('username',''))
   attempts=FAILED.get(username,[])
   attempts=[x for x in attempts if x>time.time()-300]
   if len(attempts)>=5:return self.fail('5 қате әрекеттен кейін 5 минутқа уақытша шектеу қойылды',429)
   if not r or not r['active'] or not check_pwd(str(d.get('password','')),r['password']):FAILED[username]=attempts+[time.time()];return self.fail('Логин немесе құпиясөз қате',401)
   FAILED.pop(username,None)
   token=secrets.token_urlsafe(32);TOKENS[token]=(r['id'],time.time()+8*3600,secrets.token_urlsafe(24))
   return self.send({'ok':True,'role':r['role'],'must_change':bool(r['must_change'])},headers={'Set-Cookie':f'session={token}; HttpOnly; SameSite=Strict; Path=/'+('; Secure' if os.environ.get('CLASSMATE_HTTPS')=='1' else '')})
  u=self.user()
  if not u:return self.fail('Алдымен жүйеге кіріңіз',401)
  role=u['role']
  if path=='/api/logout':
   ck=cookies.SimpleCookie();ck.load(self.headers.get('Cookie',''))
   if ck.get('session'):TOKENS.pop(ck['session'].value,None)
   return self.send({'ok':True},headers={'Set-Cookie':'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/change-password':
   old=str(d.get('old_password',''));new=d.get('new_password','')
   if not valid_password(new):return self.fail('Жаңа пароль 12–128 таңба, әріп пен сан болуы қажет')
   with LOCK,conn() as c:
    r=c.execute('SELECT password FROM users WHERE id=?',(u['id'],)).fetchone()
    if not r or not check_pwd(old,r['password']):return self.fail('Қазіргі пароль дұрыс емес',403)
    if old==new:return self.fail('Жаңа пароль ескісінен өзгеше болуы қажет')
    c.execute('UPDATE users SET password=?,must_change=0 WHERE id=?',(pwd_hash(new),u['id']))
    audit(c,u,'Құпиясөз өзгертілді')
    for t,v in list(TOKENS.items()):
     if v[0]==u['id'] and t!=cookies.SimpleCookie(self.headers.get('Cookie','')).get('session',cookies.Morsel()).value:TOKENS.pop(t,None)
   return self.send({'ok':True})
  if path=='/api/users':
   if u['role']!='admin':return self.fail('Тек әкімші жаңа аккаунт жасайды',403)
   username=str(d.get('username','')).strip().lower();name=str(d.get('name','')).strip()[:120];role=str(d.get('role',''))
   if not re.fullmatch(r'[a-z0-9._-]{3,32}',username) or not name or role not in ROLES:return self.fail('Логин, аты және рөлі қажет')
   if role=='admin':return self.fail('Қосымша әкімші аккаунты бұл демода құрылмайды',403)
   sid=int(d.get('student_id') or 0)
   with LOCK,conn() as c:
    if role in ('parent','student') and not c.execute('SELECT 1 FROM students WHERE id=?',(sid,)).fetchone():return self.fail('Ата-ана немесе оқушы аккаунтын нақты оқушыға байланыстырыңыз')
    temporary=secrets.token_urlsafe(14)+'7a'
    try:
     cur=c.execute('INSERT INTO users(username,password,role,name,student_id,must_change,active) VALUES(?,?,?,?,?,1,1)',(username,pwd_hash(temporary),role,name,sid if sid else None))
    except sqlite3.IntegrityError:return self.fail('Бұл логин бұрыннан бар',409)
    for class_id in d.get('class_ids',[]) if isinstance(d.get('class_ids'),list) else []:
     try: cl=int(class_id)
     except (ValueError,TypeError):continue
     if c.execute('SELECT 1 FROM classes WHERE id=?',(cl,)).fetchone():c.execute('INSERT OR IGNORE INTO user_classes(user_id,class_id) VALUES(?,?)',(cur.lastrowid,cl))
    audit(c,u,'Жеке аккаунт жасалды',f'{username}/{role}')
   return self.send({'ok':True,'temporary_password':temporary,'note':'Уақытша пароль тек осы жауапта көрсетіледі. Бірінші кіргенде өзгертілуі міндетті.'})
  if path=='/api/users/reset':
   if u['role']!='admin':return self.fail('Тек әкімші',403)
   uid=int(d.get('id') or 0)
   with LOCK,conn() as c:
    r=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    if not r or r['role']=='admin':return self.fail('Пайдаланушы табылмады')
    temporary=secrets.token_urlsafe(14)+'7a'
    c.execute('UPDATE users SET password=?,must_change=1 WHERE id=?',(pwd_hash(temporary),uid))
    for tok,session in list(TOKENS.items()):
     if session[0]==uid:TOKENS.pop(tok,None)
    audit(c,u,'Уақытша пароль қайта берілді',uid)
   return self.send({'ok':True,'temporary_password':temporary})
  if path=='/api/users/toggle':
   if u['role']!='admin':return self.fail('Тек әкімші',403)
   uid=int(d.get('id') or 0)
   with LOCK,conn() as c:
    r=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    if not r or r['role']=='admin':return self.fail('Бұл аккаунтты өзгертуге болмайды')
    c.execute('UPDATE users SET active=? WHERE id=?',(0 if r['active'] else 1,uid))
    for tok,session in list(TOKENS.items()):
     if session[0]==uid:TOKENS.pop(tok,None)
    audit(c,u,'Аккаунт күйі өзгертілді',uid)
   return self.send({'ok':True})
  if path=='/api/assistant/compose':
   if role not in ('teacher','deputy'):return self.fail('Бұл әрекетке рұқсат жоқ',403)
   kind=str(d.get('kind','class_hour'))
   prompt=str(d.get('prompt','')).strip()[:650]
   cls=str(d.get('class_name','7-А')).strip()[:50]
   if not prompt:return self.fail('Тақырып немесе сұраныс енгізіңіз')
   if any(w in prompt.lower() for w in ('жсн','иин','диагноз','үй мекенжайы','телефон нөмірі')):return self.fail('Оқушының құпия деректерін ЖИ-ға жіберуге болмайды',403)
   try: result=ollama_compose(kind,prompt,cls)
   except RuntimeError as exc:return self.fail(str(exc),503)
   except Exception:return self.fail('Ollama байланысында ақау болды. Ollama қосылғанын тексеріңіз.',503)
   with LOCK,conn() as c:
    c.execute('INSERT INTO ai_activity(actor_id,kind,prompt,result) VALUES(?,?,?,?)',(u['id'],kind,prompt,result))
    audit(c,u,'Жергілікті ЖИ жоба жасады',kind)
   return self.send({'ok':True,'result':result,'engine':'Ollama · Qwen3:4B (жергілікті, тегін)','label':'ЖИ дайындаған ЖОБА · мұғалім тексереді'})
  def need(*roles):
   if role not in roles:raise PermissionError('Бұл әрекетке рұқсатыңыз жоқ')
  try:
   with LOCK,conn() as c:
    if path=='/api/importfile':
     need('teacher');name=str(d.get('name',''))[:120]
     try:content=extract_uploaded(name,str(d.get('data','')))
     except Exception as e:return self.fail('Файлды оқу қатесі: '+str(e)[:130])
     kind=classify(name+' '+content[:3000]);count=len(content.splitlines())
     cur=c.execute('INSERT INTO import_jobs(name,kind,rows_count,status,details,created_by) VALUES(?,?,?,?,?,?)',(name,kind,count,'review',content[:90000],u['id']))
     audit(c,u,'Импорт тексеруге ұсынылды',name)
     return self.send({'ok':True,'id':cur.lastrowid,'kind':kind,'rows':count,'preview':content[:1500],'note':'Мұғалім алдын ала тексеріп бекітпейінше негізгі дерекқорға енгізілмейді.'})
    if path=='/api/importfile/approve':
     need('teacher');jid=int(d.get('id') or 0)
     r=c.execute('SELECT * FROM import_jobs WHERE id=? AND status=? AND created_by=?',(jid,'review',u['id'])).fetchone()
     if not r:return self.fail('Бекітілетін импорт жоқ')
     c.execute('INSERT INTO records(kind,title,content,created_by) VALUES(?,?,?,?)',(r['kind'],r['name'],r['details'],u['id']))
     c.execute('UPDATE import_jobs SET status=? WHERE id=?',('approved',jid));audit(c,u,'Файл бекітіліп тіркелді',r['name'])
     return self.send({'ok':True,'kind':r['kind'],'note':'Файл қажетті санатта құжат ретінде тіркелді. Құрылымдалған оқушы карталарын импорттау үшін CSV оқушылар импорты пайдаланылады.'})
    if path=='/api/messages/reply':
     need('parent');body=str(d.get('body','')).strip()[:1200];sid=u['student_id']
     if not sid or not body:return self.fail('Хабарлама мәтіні қажет')
     c.execute('INSERT INTO messages(student_id,channel,recipient,body,state) VALUES(?,?,?,?,?)',(sid,'parent_reply','Сынып жетекшісі',body,'approved'));audit(c,u,'Ата-ананың жауабы',sid)
     return self.send({'ok':True,'note':'Жауап ішкі кабинетте тіркелді. Нақты телефонға жіберілмейді.'})
    if path=='/api/classes':
     need('teacher','admin');name=str(d.get('name','')).strip()[:60]
     if not name:return self.fail('Сыныптың атауы қажет')
     c.execute('INSERT INTO classes(name,teacher_id) VALUES(?,?)',(name,u['id'] if role=='teacher' else None));audit(c,u,'Сынып құрылды',name);return self.send({'ok':True})
    if path=='/api/activities':
     need('teacher','deputy');cl=int(d.get('class_id') or 0);kind=str(d.get('kind','event'))[:50];topic=str(d.get('topic','')).strip()[:200];day=str(d.get('day') or nowday());desc=str(d.get('description',''))[:4000]
     if not topic or not allowed_class(c,u,cl):return self.fail('Сынып пен тақырып қажет')
     if kind not in ('event','plan','class_hour','safety'):return self.fail('Түрі дұрыс емес')
     c.execute('INSERT INTO activities(class_id,kind,topic,day,description,created_by) VALUES(?,?,?,?,?,?)',(cl,kind,topic,day,desc,u['id']));audit(c,u,'Іс-шара жоспарланды',topic);return self.send({'ok':True})
    if path=='/api/activities/status':
     need('teacher','deputy');ident=int(d.get('id') or 0);state=str(d.get('status',''))
     if state not in ('planned','in_progress','completed'):return self.fail('Мәртебесі дұрыс емес')
     c.execute('UPDATE activities SET status=? WHERE id=?',(state,ident));audit(c,u,'Іс-шара жаңартылды',ident);return self.send({'ok':True})
    if path=='/api/meetings':
     need('teacher');cl=int(d.get('class_id') or 0);agenda=str(d.get('agenda','')).strip()[:4000];day=str(d.get('day') or nowday());minutes=str(d.get('minutes',''))[:5000]
     if not agenda or not allowed_class(c,u,cl):return self.fail('Күн тәртібі мен сынып қажет')
     c.execute('INSERT INTO meetings(class_id,day,agenda,minutes,created_by) VALUES(?,?,?,?,?)',(cl,day,agenda,minutes,u['id']));audit(c,u,'Жиналыс жобасы',cl);return self.send({'ok':True})
    if path=='/api/social_profiles':
     need('teacher','social');sid=int(d.get('student_id') or 0);category=str(d.get('category','')).strip()[:180];support=str(d.get('support','')).strip()[:1000]
     if not c.execute('SELECT id FROM students WHERE id=?',(sid,)).fetchone():return self.fail('Оқушы жоқ')
     c.execute("INSERT INTO social_passports(student_id,category,support) VALUES(?,?,?) ON CONFLICT(student_id) DO UPDATE SET category=excluded.category,support=excluded.support,updated_at=CURRENT_TIMESTAMP",(sid,category,support));audit(c,u,'Әлеуметтік паспорт жаңартылды',sid);return self.send({'ok':True})
    if path=='/api/assignments':
     need('subject','teacher');cl=int(d.get('class_id') or 0);title=str(d.get('title','')).strip()[:200];subject=str(d.get('subject','')).strip()[:120];deadline=str(d.get('deadline') or nowday())
     if not title or not subject or not allowed_class(c,u,cl):return self.fail('Сынып, пән, тапсырма қажет')
     c.execute('INSERT INTO assignments(class_id,subject,title,deadline,created_by) VALUES(?,?,?,?,?)',(cl,subject,title,deadline,u['id']));audit(c,u,'Тапсырма тіркелді',title);return self.send({'ok':True})
    if path=='/api/surveys':
     need('student');answer=str(d.get('answer',''))
     if answer not in ('good','neutral','need_help'):return self.fail('Таңдау қате')
     cls=c.execute('SELECT class_id FROM students WHERE id=?',(u['student_id'],)).fetchone()
     if not cls:return self.fail('Сынып табылмады')
     c.execute('INSERT INTO surveys(class_id,question,answer) VALUES(?,?,?)',(cls['class_id'],'Бүгінгі жағдай',answer));audit(c,u,'Анонимді жалпы сауалнама жіберілді','Жеке жауап аудитке жазылмайды');return self.send({'ok':True,'note':'Сынып бойынша жинақталған статистикаға қосылды.'})
    if path=='/api/grades':
     need('subject','teacher');sid=int(d.get('student_id') or 0);subject=str(d.get('subject','')).strip()[:100];score=int(d.get('score') or 0);maxscore=int(d.get('max_score') or 0)
     if not subject or maxscore<=0 or score<0 or score>maxscore or not allowed_student(c,u,sid):return self.fail('Деректер дұрыс емес')
     c.execute('INSERT INTO grades(student_id,subject,score,max_score,created_by) VALUES(?,?,?,?,?)',(sid,subject,score,maxscore,u['id']));audit(c,u,'Диагностика тіркелді',f'{sid}/{subject}');return self.send({'ok':True})
    if path=='/api/reports/save':
     need('teacher');title=str(d.get('title','')).strip()[:180];kind=str(d.get('kind','summary'))[:80]
     if not title:return self.fail('Есеп тақырыбы қажет')
     payload=json.dumps(report(c),ensure_ascii=False)
     c.execute('INSERT INTO saved_reports(kind,title,payload,created_by) VALUES(?,?,?,?)',(kind,title,payload,u['id']));audit(c,u,'Есеп жобасы сақталды',title);return self.send({'ok':True})
    if path=='/api/students':
     need('teacher','admin')
     name=str(d.get('full_name','')).strip();cl=int(d.get('class_id') or 0)
     if not name or not allowed_class(c,u,cl):return self.fail('Сыныпты таңдаңыз немесе өз сыныбыңызды құрыңыз')
     cur=c.execute('INSERT INTO students(full_name,class_id,guardian_name,guardian_contact) VALUES(?,?,?,?)',(name,cl,str(d.get('guardian_name',''))[:90],str(d.get('guardian_contact',''))[:100]));audit(c,u,'Оқушы қосылды',name)
     return self.send({'ok':True,'id':cur.lastrowid})
    if path=='/api/attendance':
     need('subject','teacher')
     sid=int(d.get('student_id') or 0);subject=str(d.get('subject','')).strip()[:100];status=str(d.get('status',''))
     day=str(d.get('day') or nowday())
     if status not in ('present','absent','late') or not subject or not allowed_student(c,u,sid):return self.fail('Деректер дұрыс емес')
     c.execute('INSERT INTO attendance(student_id,subject,day,status,created_by) VALUES(?,?,?,?,?) ON CONFLICT(student_id,subject,day) DO UPDATE SET status=excluded.status,created_by=excluded.created_by',(sid,subject,day,status,u['id']))
     if status=='absent':
      student=c.execute('SELECT full_name,guardian_name FROM students WHERE id=?',(sid,)).fetchone()
      dup=c.execute("SELECT id FROM messages WHERE student_id=? AND channel='absence' AND state='draft' AND substr(created_at,1,10)=?",(sid,nowday())).fetchone()
      if not dup:
       msg=f"Сәлеметсіз бе! {student['full_name']} бүгін ({day}) {subject} сабағына қатыспады деп белгіленді. Себебін нақтылауға көмектесесіз бе? Сынып жетекшісіне жауап беруіңізді сұраймыз."
       c.execute('INSERT INTO messages(student_id,channel,recipient,body) VALUES(?,?,?,?)',(sid,'absence','Ата-ана',msg))
       c.execute('INSERT INTO cases(student_id,category,details) VALUES(?,?,?)',(sid,'absence_followup',f'{day}: {subject}. Ата-ананың жауабы күтілуде.'))
     audit(c,u,'Қатысу жаңартылды',f'{sid}/{status}/{subject}');return self.send({'ok':True,'draft_created':status=='absent'})
    if path=='/api/messages/approve':
     need('teacher');mid=int(d.get('id') or 0)
     cur=c.execute("UPDATE messages SET state='approved',approved_by=? WHERE id=? AND state='draft'",(u['id'],mid))
     if not cur.rowcount:return self.fail('Жоба табылмады немесе бекітілген')
     audit(c,u,'Хабарлама бекітілді',mid);return self.send({'ok':True,'note':'Ішкі кабинетте ғана көрінеді. SMS/WhatsApp жіберілмейді.'})
    if path=='/api/messages':
     need('teacher','subject');sid=int(d.get('student_id') or 0)
     if not allowed_student(c,u,sid):return self.fail('Оқушыға рұқсат жоқ',403)
     body=str(d.get('body','')).strip()[:1200]
     if not body:return self.fail('Хабарлама мәтінін жазыңыз')
     c.execute('INSERT INTO messages(student_id,channel,recipient,body) VALUES(?,?,?,?)',(sid,'general','Ата-ана',body));audit(c,u,'Хабарлама жобасы',sid)
     return self.send({'ok':True})
    if path=='/api/cases':
     category=str(d.get('category',''))
     if category=='medical':need('teacher','student','parent','nurse')
     elif category=='psych_private':need('student','parent','psychologist')
     else:need('teacher','social')
     sid=(u['student_id'] if role in ('student','parent') else int(d.get('student_id') or 0));details=str(d.get('details','')).strip()[:1000]
     if not sid or not details:return self.fail('Оқушы мен өтініш мәтіні қажет')
     if not allowed_student(c,u,sid):return self.fail('Оқушы табылмады')
     c.execute('INSERT INTO cases(student_id,category,details,private) VALUES(?,?,?,?)',(sid,category,details,1 if category=='psych_private' else 0));audit(c,u,'Көмек сұрауы',category)
     return self.send({'ok':True,'note':'Тек жергілікті базаға жазылды, нақты медицина қызметкеріне қоңырау жіберілген жоқ.'})
    if path=='/api/plans':
     need('teacher');topic=str(d.get('topic','')).strip()[:160];cl=int(d.get('class_id') or 0)
     if not topic or not allowed_class(c,u,cl):return self.fail('Сынып пен тақырыпты енгізіңіз')
     cname=c.execute('SELECT name FROM classes WHERE id=?',(cl,)).fetchone()['name'];s=scenario(cname,topic)
     c.execute('INSERT INTO plans(class_id,topic,scenario) VALUES(?,?,?)',(cl,topic,s));audit(c,u,'Сценарий үлгісі құрылды',topic)
     return self.send({'ok':True,'scenario':s,'disclaimer':'Бұл офлайн шаблон. Нақты LLM/AI API қосылмаған.'})
    if path=='/api/ingest':
     need('teacher');name=str(d.get('name','Жүктелген мәтін'))[:130];content=str(d.get('content',''))[:30000]
     if not content:return self.fail('Мәтін немесе CSV дерегі қажет')
     imported=0;kind=classify(name+' '+content[:2000])
     if name.lower().endswith('.csv'):
      reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
      cols=reader.fieldnames or []
      if any(x in cols for x in ('full_name','аты-жөні')):
       cl=c.execute('SELECT id FROM classes ORDER BY id LIMIT 1').fetchone()
       if cl:
        for line in reader:
         nm=(line.get('full_name') or line.get('аты-жөні') or '').strip()
         if nm and imported<300:
          c.execute('INSERT INTO students(full_name,class_id,guardian_name,guardian_contact) VALUES(?,?,?,?)',(nm,cl[0],line.get('guardian_name',''),line.get('guardian_contact','')));imported+=1
        kind='Оқушылар тізімі'
     c.execute('INSERT INTO records(kind,title,content,created_by) VALUES(?,?,?,?)',(kind,name,content,u['id']))
     audit(c,u,'Файл жіктелді',f'{name} -> {kind}; imported={imported}')
     return self.send({'ok':True,'kind':kind,'students_imported':imported,'note':'Ережеге негізделген жіктеу: мұғалім нәтижені тексеруі керек.'})
    if path=='/api/records':
     need('teacher');title=str(d.get('title','')).strip()[:160];content=str(d.get('content','')).strip()[:12000]
     if not title or not content:return self.fail('Тақырып және мәтін енгізіңіз')
     kind=classify(title+' '+content)
     c.execute('INSERT INTO records(kind,title,content,created_by) VALUES(?,?,?,?)',(kind,title,content,u['id']));audit(c,u,'Жазба сұрыпталды',kind)
     return self.send({'ok':True,'kind':kind})
    if path=='/api/cases/resolve':
     need('teacher','nurse','psychologist','social');cid=int(d.get('id') or 0)
     r=c.execute('SELECT category FROM cases WHERE id=?',(cid,)).fetchone()
     if not r:return self.fail('Өтініш табылмады')
     if (r['category']=='medical' and role not in ('nurse','teacher')) or (r['category']=='psych_private' and role!='psychologist') or (r['category']=='social' and role not in ('social','teacher')):return self.fail('Рұқсат жоқ',403)
     c.execute("UPDATE cases SET status='reviewed' WHERE id=?",(cid,));audit(c,u,'Өтініш қаралды',cid);return self.send({'ok':True})
   return self.fail('Әрекет табылмады',404)
  except PermissionError as e:return self.fail(str(e),403)
  except (ValueError,sqlite3.IntegrityError) as e:return self.fail('Қате мәлімет немесе қайталанған жазба: '+str(e)[:100])

def run():
 init();port=int(os.environ.get('CLASSMATE_PORT','8770'));srv=ThreadingHTTPServer(('127.0.0.1',port),Handler);print(f'ClassMate AI v2: http://127.0.0.1:{port}',flush=True);srv.serve_forever()
if __name__=='__main__':run()
