"""ClassMate AI v3: local-first pilot, extending the tested v2 engine.
IMPORTANT: This is NOT a certified public internet service or a substitute for official school systems.
"""
import json, re, csv, io, os, time, datetime, urllib.parse, secrets, sqlite3, pathlib, threading, zipfile
from http.server import ThreadingHTTPServer
from http import cookies
import core
import doc_exports

ROOT = pathlib.Path(__file__).resolve().parent
BACKUPS = ROOT / 'backups'
BACKUPS.mkdir(exist_ok=True)

NORMS = [
 ('18','Сынып жетекшілігі туралы ереже','Положение о классном руководстве','2016-01-12','https://adilet.zan.kz/kaz/docs/V1600013067'),
 ('130','Педагогтер жүргізетін міндетті құжаттар','Обязательные документы педагогов','2020-04-06','https://adilet.zan.kz/kaz/docs/V2000020317'),
 ('506','Буллингтің профилактикасы қағидалары','Правила профилактики буллинга','2022-12-21','https://adilet.zan.kz/kaz/docs/V2200031180'),
 ('319-III','Білім туралы заң','Закон об образовании','2007-07-27','https://adilet.zan.kz/kaz/docs/Z070000319_'),
 ('293-VI','Педагог мәртебесі туралы заң','Закон о статусе педагога','2019-12-27','https://adilet.zan.kz/kaz/docs/Z1900000293'),
]

F_MODULES = [
 ('F01','Басты бет','dashboard'),('F02','Менің сыныбым','students'),('F03','Тәрбие жоспары','plans'),
 ('F04','Сынып сағаты','lesson'),('F05','Қатысу және үлгерім','attendance'),('F06','Әлеуметтік паспорт','social'),
 ('F07','Ата-аналармен жұмыс','parents'),('F08','Қауіпсіздік','safety'),('F09','Психологиялық ахуал','mood'),
 ('F10','Іс-шаралар','events'),('F11','Құжаттар және есептер','reports'),('F12','ClassMate AI көмекшісі','assistant'),
 ('F13','Аналитика','analytics'),('F14','Нормативтік база','laws'),('F15','Баптаулар және қауіпсіздік','settings')]

# Honest acceptance tracking: available != externally certified.
CRITERIA = [
 ('AC-01','Рөлдер мен оқушы деңгейінде қолжетімділіктің барлық сынақтары','local_tests','Толық сыртқы сынақ қажет'),
 ('AC-02','15 негізгі модульдің қызметтері','partial','Модульдер іске қосылады; кей кеңейтілген қызметтер жоқ'),
 ('AC-03','№130 құжаттарының бекітілген нысанда DOCX/PDF экспорты','partial','Жергілікті экспорт үлгілері; мектеп бекіткен ресми шаблондар қажет'),
 ('AC-04','Қазақша және орысша интерфейс','partial','Негізгі мәзір мен интерфейс аударылады; толық тілдік аудит қажет'),
 ('AC-05','AI жобасы таңбаланып, педагог растауынсыз жіберілмейді','implemented','Ішкі бекіту қолданылады; сервистік қауіпсіздік аудиті қажет'),
 ('AC-06','Сыни және жоғары деңгейлі қауіпсіздік ақауы қалмауы','unverified','Тәуелсіз пен-тест және DPIA қажет'),
 ('AC-07','95% негізгі бет 3 секунд ішінде','unverified','Келісілген жүктемемен сынақ өткізу қажет'),
 ('AC-08','Backup қалпына келтіру сынағы','local_tests','Local backup және restore тексеріледі; RPO/RTO өндірісте тексерілмеген'),
 ('AC-09','Қазақша әріптер, кестелер, беттер','partial','DOCX/XLSX және PDF-ті бірнеше құрылғыда визуалды тексеру қажет'),
 ('AC-10','Пайдаланушы, әкімші және API құжаттамасы','implemented','README, ADMIN, API, ACCEPTANCE'),
 ('AC-11','Тапсырыс берушілермен UAT','external','Мектеп және Индира апаймен қабылдау сынағы қажет'),
 ('AC-12','Ақауларды бекіту/жабу','external','Ақау журналы және қол қойылған қабылдау қажет'),
]


def init_extra():
    core.init()
    with core.conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS lesson_logs(id INTEGER PRIMARY KEY,class_id INTEGER,day TEXT,topic TEXT,objectives TEXT,
            materials TEXT,attendance_note TEXT,reflection TEXT,status TEXT DEFAULT 'draft',created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS policy_refs(id INTEGER PRIMARY KEY,code TEXT UNIQUE,title_kk TEXT,title_ru TEXT,
            issued_date TEXT,revision_date TEXT,url TEXT,verified INTEGER DEFAULT 0,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS consent_records(id INTEGER PRIMARY KEY,student_id INTEGER,kind TEXT,granted INTEGER,
            evidence TEXT,updated_by INTEGER,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(student_id,kind));
        CREATE TABLE IF NOT EXISTS approval_history(id INTEGER PRIMARY KEY,kind TEXT,object_id INTEGER,decision TEXT,
            comment TEXT,actor_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS message_reads(message_id INTEGER,user_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(message_id,user_id));
        CREATE TABLE IF NOT EXISTS student_change_history(id INTEGER PRIMARY KEY,student_id INTEGER,action TEXT,field TEXT,
            previous TEXT,new_value TEXT,actor_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS backup_events(id INTEGER PRIMARY KEY,kind TEXT,archive_file TEXT,created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS integration_status(name TEXT PRIMARY KEY,status TEXT,last_sync TEXT,description TEXT);
        CREATE TABLE IF NOT EXISTS support_cases(id INTEGER PRIMARY KEY,student_id INTEGER,category TEXT,details TEXT,
            assigned_role TEXT,status TEXT DEFAULT 'new',class_id INTEGER,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            handled_by INTEGER,handled_at TEXT);
        CREATE TABLE IF NOT EXISTS lesson_materials(id INTEGER PRIMARY KEY,class_id INTEGER,kind TEXT,title TEXT,body TEXT,
            source TEXT,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS ix_students_class_name ON students(class_id,full_name)')
        c.execute('CREATE INDEX IF NOT EXISTS ix_attendance_student_day ON attendance(student_id,day)')
        c.execute('CREATE INDEX IF NOT EXISTS ix_messages_student_state ON messages(student_id,state)')
        for code,title,ru,day,url in NORMS:
            c.execute('INSERT OR IGNORE INTO policy_refs(code,title_kk,title_ru,issued_date,url) VALUES(?,?,?,?,?)',(code,title,ru,day,url))
        for n,desc in [('Kundelik','Тек ресми API мен құқық берілгеннен кейін'),('ҰБДҚ','Тек уәкілетті интерфейс болғанда'),('SMS/Email','Хабарлама провайдері мен келісім қажет'),('Ollama','Компьютердегі жергілікті Qwen3:4B')]:
            c.execute('INSERT OR IGNORE INTO integration_status(name,status,description) VALUES(?,?,?)',(n,'unconnected' if n!='Ollama' else 'local_optional',desc))
        for table,col,typ in [
            ('students','archived','INTEGER DEFAULT 0'),('students','updated_at','TEXT DEFAULT NULL'),
            ('attendance','source','TEXT DEFAULT \'Қолмен енгізу\''),('attendance','last_sync','TEXT DEFAULT NULL'),
            ('plans','status','TEXT DEFAULT \'draft\''),('plans','version','INTEGER DEFAULT 1'),
            ('plans','approved_by','INTEGER'),('plans','approved_at','TEXT'),
            ('meetings','approved_by','INTEGER'),('meetings','approved_at','TEXT'),
            ('ai_activity','approved_by','INTEGER'),('ai_activity','approved_at','TEXT'),
        ]:
            try:c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
            except sqlite3.OperationalError:pass


def clean(v,lim=1500):return str(v or '').strip()[:lim]

def scan_student(c,u,sid):
    if not sid:return False
    if u['role'] in ('parent','student'):return int(u['student_id'] or -1)==sid
    if u['role'] in ('teacher','subject'):
        return core.allowed_student(c,u,sid)
    if u['role']=='social':return True # restricted only to social passport/support functions
    if u['role'] in ('nurse','psychologist'):return False # route-specific assignment required
    return u['role'] in ('director','deputy') # admin is infrastructure role, not medical/social content

def class_ids(c,u):
    if u['role'] in ('teacher','subject'):
        return [x[0] for x in c.execute('SELECT id FROM classes WHERE teacher_id=? OR id IN (SELECT class_id FROM user_classes WHERE user_id=?)',(u['id'],u['id']))]
    if u['role'] in ('parent','student'):
        return [x[0] for x in c.execute('SELECT class_id FROM students WHERE id=?',(u['student_id'],))]
    if u['role'] in ('director','deputy'):return [x[0] for x in c.execute('SELECT id FROM classes')]
    return []


def safe_body(c,u,payload):
    # AI should never receive raw student names/contact fields or protected reports automatically.
    prompt=clean(payload.get('prompt'),650)
    if any(token in prompt.lower() for token in ('жсн','иин','диагноз','мекенжай','адрес','телефон нөмірі')):
        raise ValueError('Оқушының құпия дерегін ЖИ сұрауына қоспаңыз')
    return prompt

class Handler(core.Handler):
    def body(self):
        if not hasattr(self,'_cached_body'):
            self._cached_body=super().body()
        return self._cached_body
    def actor(self,csrf=False):
        u=self.user()
        if not u:raise PermissionError('Жеке кабинетке кіріңіз')
        if u['must_change']:raise PermissionError('Алдымен жеке пароліңізді өзгертіңіз')
        if csrf:
            ck=cookies.SimpleCookie();ck.load(self.headers.get('Cookie',''))
            tok=ck.get('session'); rec=core.TOKENS.get(tok.value) if tok else None
            if not rec or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),rec[2]):
                raise PermissionError('CSRF қорғау тексерісі өтпеді')
            origin=self.headers.get('Origin','')
            if origin and urllib.parse.urlparse(origin).netloc!=self.headers.get('Host',''):
                raise PermissionError('Бөгде сайт сұранысы қабылданбайды')
        return u
    def do_GET(self):
        p=urllib.parse.urlparse(self.path).path
        if p=='/api/health':return self.send({'status':'ok','name':'ClassMate AI v3','mode':'local-pilot'})
        if p=='/api/document':
            try:
                u=self.actor();params=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                fmt=params.get('format',['docx'])[0];kind=params.get('kind',['summary'])[0]
                if fmt not in ('docx','pdf','html'):return self.fail('Формат жоқ')
                with core.conn() as c:
                    title,lines=doc_exports.contents(c,u,kind,class_ids(c,u))
                    core.audit(c,u,'Құжат экспортталды',kind+'/'+fmt)
                raw={'docx':lambda:doc_exports.make_docx(title,lines),'pdf':lambda:doc_exports.make_pdf(title,lines),'html':lambda:doc_exports.make_html(title,lines)}[fmt]()
                typ={'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','pdf':'application/pdf','html':'text/html; charset=utf-8'}[fmt]
                return self.send(raw,type=typ,headers={'Content-Disposition':f'attachment; filename=ClassMate_{kind}.{fmt}' if fmt!='html' else 'inline'})
            except (PermissionError,ValueError) as e:return self.fail(str(e),403)
            except Exception as e:return self.fail(str(e),501)
        # All below are protected. Do not reuse permissive v2 listing endpoints.
        if p in ('/api/norms','/api/lessons/logs','/api/consents','/api/approvals','/api/backup',
                 '/api/integrations','/api/criteria','/api/search','/api/support/requests','/api/lessons/materials',
                 '/api/records','/api/messages','/api/cases','/api/plans','/api/activities','/api/meetings','/api/social_profiles',
                 '/api/analytics','/api/report','/api/overview','/api/dashboard','/api/students','/api/attendance','/api/assignments'):
            try:
                u=self.actor()
                with core.conn() as c:
                    if p in ('/api/social_profiles','/api/support/requests','/api/consents','/api/students','/api/cases'):
                        core.audit(c,u,'Жеке деректерді қарау',p)
                    role=u['role'];mine=class_ids(c,u)
                    if p=='/api/criteria':return self.send({'modules':F_MODULES,'acceptance':CRITERIA})
                    if p=='/api/norms':return self.send(core.rows(c,'SELECT * FROM policy_refs ORDER BY id'))
                    if p=='/api/integrations':return self.send(core.rows(c,'SELECT * FROM integration_status ORDER BY name'))
                    if p=='/api/backup':
                        if role!='admin':return self.fail('Тек әкімші',403)
                        target=BACKUPS / ('classmate_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.sqlite3')
                        with sqlite3.connect(target) as out:c.backup(out)
                        c.execute('INSERT INTO backup_events(kind,archive_file,created_by) VALUES(?,?,?)',('create',target.name,u['id']))
                        core.audit(c,u,'Резервтік көшірме',target.name)
                        return self.send(target.read_bytes(),type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="ClassMate_backup.sqlite3"'})
                    if p=='/api/search':
                        if role not in ('teacher','subject','director','deputy'):return self.fail('Рұқсат жоқ',403)
                        q=clean(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('q',[''])[0],80)
                        if len(q)<2:return self.send([])
                        filt='%'+q+'%'
                        if role in ('teacher','subject'):
                            if not mine:return self.send([])
                            sql='SELECT id,full_name,class_id FROM students WHERE class_id IN ('+','.join('?'*len(mine))+') AND full_name LIKE ? ORDER BY id LIMIT 60';params=(*mine,filt)
                        else:sql='SELECT id,full_name,class_id FROM students WHERE full_name LIKE ? ORDER BY id LIMIT 60';params=(filt,)
                        return self.send(core.rows(c,sql,params))
                    if p=='/api/lessons/logs':
                        if role not in ('teacher','deputy','director'):return self.fail('Рұқсат жоқ',403)
                        where='' if role!='teacher' else ' WHERE l.class_id IN ('+(','.join('?'*len(mine)) if mine else 'NULL')+')'
                        return self.send(core.rows(c,'SELECT l.*,cl.name class_name FROM lesson_logs l JOIN classes cl ON cl.id=l.class_id'+where+' ORDER BY l.day DESC LIMIT 100',mine if role=='teacher' else ()))
                    if p=='/api/lessons/materials':
                        if role not in ('teacher','subject','parent','student'):return self.fail('Рұқсат жоқ',403)
                        if not mine:return self.send([])
                        sql='SELECT id,class_id,title,kind,body,source,created_at FROM lesson_materials WHERE class_id IN ('+','.join('?'*len(mine))+') ORDER BY id DESC LIMIT 100'
                        return self.send(core.rows(c,sql,mine))
                    if p=='/api/consents':
                        if role not in ('teacher','social','parent','student'):return self.fail('Рұқсат жоқ',403)
                        if role in ('parent','student'):return self.send(core.rows(c,'SELECT student_id,kind,granted,updated_at FROM consent_records WHERE student_id=?',(u['student_id'],)))
                        if role=='social':return self.fail('Тек жеке қолдау жағдайында рұқсат беріледі',403)
                        return self.send(core.rows(c,'SELECT * FROM consent_records WHERE student_id IN (SELECT s.id FROM students s JOIN classes cl ON s.class_id=cl.id WHERE cl.teacher_id=? OR cl.id IN (SELECT class_id FROM user_classes WHERE user_id=?))',(u['id'],u['id'])))
                    if p=='/api/approvals':
                        if role not in ('teacher','deputy','director'):return self.fail('Рұқсат жоқ',403)
                        return self.send(core.rows(c,'SELECT * FROM approval_history ORDER BY id DESC LIMIT 100'))
                    if p=='/api/support/requests':
                        if role in ('parent','student'):return self.send(core.rows(c,'SELECT id,category,status,created_at FROM support_cases WHERE student_id=? ORDER BY id DESC',(u['student_id'],)))
                        if role not in ('teacher','nurse','psychologist','social'):return self.fail('Рұқсат жоқ',403)
                        kind={'nurse':'medical','psychologist':'psych_private','social':'social'}.get(role)
                        if role=='teacher':
                            if not mine:return self.send([])
                            sql='SELECT id,student_id,category,details,status,created_at FROM support_cases WHERE category NOT IN (\'psych_private\',\'medical\') AND class_id IN ('+','.join('?'*len(mine))+') ORDER BY id DESC LIMIT 100'
                            return self.send(core.rows(c,sql,mine))
                        return self.send(core.rows(c,'SELECT id,student_id,category,details,status,created_at FROM support_cases WHERE category=? ORDER BY id DESC LIMIT 100',(kind,)))
                    # Limit access to class-specific information before falling through.
                    if p in ('/api/students','/api/attendance','/api/messages','/api/plans','/api/meetings','/api/activities','/api/assignments','/api/records','/api/social_profiles','/api/overview','/api/report','/api/dashboard','/api/analytics'):
                        if role=='admin' and p=='/api/students':return self.send(core.rows(c,'SELECT id,full_name,class_id FROM students WHERE archived=0 ORDER BY id LIMIT 500'))
                        if role=='admin' and p!='/api/overview':return self.fail('Техникалық әкімшіге оқу мазмұны ашылмайды',403)
                        if p=='/api/cases':
                            if role in ('parent','student'):
                                return self.send(core.rows(c,'SELECT id,category,status,created_at FROM cases WHERE student_id=? AND category IN (\'medical\',\'absence_followup\')',(u['student_id'],)))
                            if role=='teacher':
                                if not mine:return self.send([])
                                return self.send(core.rows(c,'SELECT ca.id,ca.student_id,ca.category,ca.details,ca.status,ca.created_at FROM cases ca JOIN students s ON s.id=ca.student_id WHERE ca.category NOT IN (\'medical\',\'psych_private\') AND s.class_id IN ('+','.join('?'*len(mine))+') ORDER BY ca.id DESC',mine))
                            if role in ('nurse','psychologist','social'):
                                kind={'nurse':'medical','psychologist':'psych_private','social':'social'}[role]
                                return self.send(core.rows(c,'SELECT id,student_id,category,details,status,created_at FROM cases WHERE category=?',(kind,)))
                            return self.fail('Құпия өтініштерге рұқсат жоқ',403)
                        if p=='/api/records':
                            if role!='teacher':return self.fail('Рұқсат жоқ',403)
                            return self.send(core.rows(c,'SELECT id,kind,title,content,created_at FROM records WHERE created_by=? ORDER BY id DESC LIMIT 100',(u['id'],)))
                        if p=='/api/students' and role=='teacher':
                            if not mine:return self.send([])
                            return self.send(core.rows(c,'SELECT s.id,s.full_name,s.class_id,cl.name class_name,s.guardian_name FROM students s JOIN classes cl ON cl.id=s.class_id WHERE s.archived=0 AND s.class_id IN ('+','.join('?'*len(mine))+') ORDER BY s.id',mine))
                        if p=='/api/social_profiles':
                            if role=='teacher':
                                if not mine:return self.send([])
                                return self.send(core.rows(c,'SELECT sp.*,s.full_name FROM social_passports sp JOIN students s ON s.id=sp.student_id WHERE s.class_id IN ('+','.join('?'*len(mine))+') ORDER BY sp.id DESC',mine))
                            if role!='social':return self.fail('Құпия модуль',403)
                        if p=='/api/messages' and role=='teacher':
                            if not mine:return self.send([])
                            return self.send(core.rows(c,'SELECT m.*,s.full_name,(SELECT COUNT(*) FROM message_reads mr WHERE mr.message_id=m.id) AS read_count FROM messages m JOIN students s ON s.id=m.student_id WHERE s.class_id IN ('+','.join('?'*len(mine))+') ORDER BY m.id DESC LIMIT 200',mine))
                        if p=='/api/messages' and role in ('director','deputy','admin'):return self.fail('Жеке хат алмасу құпия',403)
                        if p=='/api/plans' and role=='teacher':
                            if not mine:return self.send([])
                            return self.send(core.rows(c,'SELECT p.*,cl.name class_name FROM plans p JOIN classes cl ON cl.id=p.class_id WHERE p.class_id IN ('+','.join('?'*len(mine))+') ORDER BY p.id DESC LIMIT 100',mine))
                        if p in ('/api/activities','/api/assignments','/api/meetings') and role in ('teacher','subject','parent','student'):
                            if not mine:return self.send([])
                            table={'/api/activities':'activities','/api/assignments':'assignments','/api/meetings':'meetings'}[p]
                            if p=='/api/meetings' and role not in ('teacher',):return self.fail('Жиналыс хаттамасы шектелген',403)
                            sql='SELECT * FROM '+table+' WHERE class_id IN ('+','.join('?'*len(mine))+') ORDER BY id DESC LIMIT 150'
                            return self.send(core.rows(c,sql,mine))
                        if p in ('/api/overview','/api/report','/api/dashboard','/api/analytics') and role=='teacher':
                            # Avoid exposing all classes through global aggregate.
                            if not mine:return self.send({'students':0,'attendance':[],'absences':[],'draft_messages':0,'plans':0,'generated':core.nowday()})
                            where=','.join('?'*len(mine))
                            count=c.execute(f'SELECT COUNT(*) FROM students WHERE archived=0 AND class_id IN ({where})',mine).fetchone()[0]
                            att=core.rows(c,f'SELECT status,COUNT(*) n FROM attendance WHERE student_id IN (SELECT id FROM students WHERE class_id IN ({where})) GROUP BY status',mine)
                            plans=c.execute(f'SELECT COUNT(*) FROM plans WHERE class_id IN ({where})',mine).fetchone()[0]
                            drafts=c.execute(f'SELECT COUNT(*) FROM messages WHERE state="draft" AND student_id IN (SELECT id FROM students WHERE class_id IN ({where}))',mine).fetchone()[0]
                            absences=core.rows(c,f'SELECT s.full_name,a.subject,a.day FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.status="absent" AND s.class_id IN ({where}) ORDER BY a.id DESC LIMIT 30',mine)
                            data={'students':count,'attendance':att,'plans':plans,'draft_messages':drafts,'absences':absences,'generated':datetime.datetime.now().isoformat(timespec='minutes')}
                            if p=='/api/analytics':data['grades']=core.rows(c,f'SELECT subject,ROUND(AVG(100.0*score/max_score),1) average FROM grades WHERE max_score>0 AND student_id IN (SELECT id FROM students WHERE class_id IN ({where})) GROUP BY subject',mine)
                            return self.send(data)
                    # base handles other routes with existing permission logic
                return super().do_GET()
            except PermissionError as e:return self.fail(str(e),403)
            except Exception as e:return self.fail('Қызмет қатесі: '+str(e)[:80],500)
        return super().do_GET()
    def do_POST(self):
        path=urllib.parse.urlparse(self.path).path
        custom={'/api/norms/save','/api/lessons/log','/api/lessons/material','/api/consents/save',
                '/api/plans/decision','/api/meetings/decision','/api/assistant/decision',
                '/api/support/request','/api/support/decision','/api/students/archive',
                '/api/students/update','/api/import/preview','/api/import/commit','/api/bug-report','/api/messages/read'}
        if path not in custom:
            if path=='/api/ingest':return self.fail('Импорт алдымен тексеріліп, мұғаліммен бекітілуі қажет. Деректер импорты бөлімін қолданыңыз.',403)
            # Protect sensitive mutations whose v2 handlers had only coarse role checks.
            if path in ('/api/social_profiles','/api/messages/approve','/api/activities/status','/api/cases/resolve'):
                try:
                    u=self.actor(csrf=True);raw=self.body() or {};id=int(raw.get('id') or raw.get('student_id') or 0)
                    with core.conn() as c:
                        if path=='/api/social_profiles' and (u['role']!='teacher' or not scan_student(c,u,id)):
                            return self.fail('Әлеуметтік паспортқа рұқсат жоқ',403)
                        if path=='/api/messages/approve':
                            r=c.execute('SELECT student_id FROM messages WHERE id=?',(id,)).fetchone()
                            if not r or not scan_student(c,u,r['student_id']):return self.fail('Басқа сыныптың хабарламасы',403)
                        if path=='/api/activities/status':
                            r=c.execute('SELECT class_id FROM activities WHERE id=?',(id,)).fetchone()
                            if not r or (u['role']=='teacher' and r['class_id'] not in class_ids(c,u)):return self.fail('Басқа сынып',403)
                        if path=='/api/cases/resolve':
                            r=c.execute('SELECT student_id,category FROM cases WHERE id=?',(id,)).fetchone()
                            if r and u['role']=='teacher' and not scan_student(c,u,r['student_id']):return self.fail('Рұқсат жоқ',403)
                except PermissionError as e:return self.fail(str(e),403)
            return super().do_POST()
        try:
            u=self.actor(csrf=True)
            d=self.body()
            if not isinstance(d,dict):return self.fail('JSON объектісі қажет')
            role=u['role']
            with core.LOCK,core.conn() as c:
                def only(*r):
                    if role not in r:raise PermissionError('Рөлге рұқсат жоқ')
                def sid_ok(sid):return scan_student(c,u,sid)
                if path=='/api/messages/read':
                    only('parent');mid=int(d.get('id') or 0)
                    r=c.execute('SELECT student_id,state FROM messages WHERE id=?',(mid,)).fetchone()
                    if not r or r['student_id']!=u['student_id'] or r['state']!='approved':return self.fail('Хабарлама табылмады',403)
                    c.execute('INSERT OR IGNORE INTO message_reads(message_id,user_id) VALUES(?,?)',(mid,u['id']))
                    core.audit(c,u,'Хабарлама оқылды',mid);return self.send({'ok':True})
                if path=='/api/norms/save':
                    only('admin');code=clean(d.get('code'),40);kk=clean(d.get('title_kk'),250);ru=clean(d.get('title_ru'),250);url=clean(d.get('url'),500)
                    if not code or not kk or (url and not url.startswith('https://adilet.zan.kz/')):return self.fail('Нөмір, атау және ресми URL қажет')
                    c.execute('INSERT INTO policy_refs(code,title_kk,title_ru,revision_date,url) VALUES(?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET title_kk=excluded.title_kk,title_ru=excluded.title_ru,revision_date=excluded.revision_date,url=excluded.url,updated_at=CURRENT_TIMESTAMP',(code,kk,ru,clean(d.get('revision_date'),20),url));core.audit(c,u,'Нормативтік карточка жаңартылды',code);return self.send({'ok':True})
                if path=='/api/lessons/log':
                    only('teacher');cl=int(d.get('class_id') or 0)
                    if cl not in class_ids(c,u):return self.fail('Сыныпқа рұқсат жоқ',403)
                    topic=clean(d.get('topic'),200)
                    if not topic:return self.fail('Тақырып қажет')
                    fields=(cl,clean(d.get('day'),10) or core.nowday(),topic,clean(d.get('objectives'),1200),clean(d.get('materials'),1200),clean(d.get('attendance_note'),600),clean(d.get('reflection'),1200),u['id'])
                    c.execute('INSERT INTO lesson_logs(class_id,day,topic,objectives,materials,attendance_note,reflection,created_by) VALUES(?,?,?,?,?,?,?,?)',fields)
                    core.audit(c,u,'Сынып сағатының журналы',topic);return self.send({'ok':True})
                if path=='/api/lessons/material':
                    only('teacher','subject');cl=int(d.get('class_id') or 0)
                    if cl not in class_ids(c,u):return self.fail('Сыныпқа рұқсат жоқ',403)
                    c.execute('INSERT INTO lesson_materials(class_id,kind,title,body,source,created_by) VALUES(?,?,?,?,?,?)',(cl,clean(d.get('kind'),30),clean(d.get('title'),200),clean(d.get('body'),4000),clean(d.get('source'),100),u['id']))
                    core.audit(c,u,'Сынып материалы',cl);return self.send({'ok':True})
                if path=='/api/consents/save':
                    only('teacher');sid=int(d.get('student_id') or 0)
                    if not sid_ok(sid):return self.fail('Басқа сыныпқа рұқсат жоқ',403)
                    kind=clean(d.get('kind'),40)
                    if kind not in ('event','photo','communications','data_processing'):return self.fail('Келісім түрі дұрыс емес')
                    if not clean(d.get('evidence'),200):return self.fail('Келісім негізі қажет')
                    c.execute('INSERT INTO consent_records(student_id,kind,granted,evidence,updated_by) VALUES(?,?,?,?,?) ON CONFLICT(student_id,kind) DO UPDATE SET granted=excluded.granted,evidence=excluded.evidence,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP',(sid,kind,int(bool(d.get('granted'))),clean(d.get('evidence'),500),u['id']))
                    core.audit(c,u,'Келісім мәртебесі',f'{sid}/{kind}');return self.send({'ok':True})
                if path=='/api/plans/decision':
                    only('teacher','deputy');id=int(d.get('id') or 0);state=clean(d.get('decision'),40)
                    r=c.execute('SELECT * FROM plans WHERE id=?',(id,)).fetchone()
                    if not r or (role=='teacher' and r['class_id'] not in class_ids(c,u)):return self.fail('Жоспар табылмады',404)
                    if state=='submit' and role=='teacher' and r['status'] in ('draft','returned'):
                        c.execute('UPDATE plans SET status="review",version=version+1 WHERE id=?',(id,))
                    elif state=='approve' and role=='deputy' and r['status']=='review':
                        c.execute('UPDATE plans SET status="approved",approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE id=?',(u['id'],id))
                    elif state=='return' and role=='deputy' and r['status']=='review':c.execute('UPDATE plans SET status="returned" WHERE id=?',(id,))
                    else:return self.fail('Бекіту кезеңі дұрыс емес',409)
                    c.execute('INSERT INTO approval_history(kind,object_id,decision,comment,actor_id) VALUES(?,?,?,?,?)',('plan',id,state,clean(d.get('comment'),600),u['id']))
                    core.audit(c,u,'Жоспар келісілді',f'{id}/{state}');return self.send({'ok':True})
                if path=='/api/meetings/decision':
                    only('teacher','deputy');id=int(d.get('id') or 0);r=c.execute('SELECT * FROM meetings WHERE id=?',(id,)).fetchone()
                    if not r or (role=='teacher' and r['class_id'] not in class_ids(c,u)):return self.fail('Жиналыс табылмады',404)
                    state=clean(d.get('decision'),30)
                    if state=='submit' and role=='teacher':c.execute('UPDATE meetings SET status="review" WHERE id=?',(id,))
                    elif state=='approve' and role=='deputy' and r['status']=='review':c.execute('UPDATE meetings SET status="approved",approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE id=?',(u['id'],id))
                    else:return self.fail('Бекіту кезеңі дұрыс емес',409)
                    c.execute('INSERT INTO approval_history(kind,object_id,decision,comment,actor_id) VALUES(?,?,?,?,?)',('meeting',id,state,clean(d.get('comment'),600),u['id']))
                    core.audit(c,u,'Жиналыс келісілді',id);return self.send({'ok':True})
                if path=='/api/assistant/decision':
                    only('teacher','deputy');id=int(d.get('id') or 0)
                    r=c.execute('SELECT * FROM ai_activity WHERE id=?',(id,)).fetchone()
                    if not r or r['actor_id']!=u['id']:return self.fail('ЖИ жобасы табылмады',404)
                    content=clean(d.get('result'),15000) or r['result']
                    if not content:return self.fail('Мәтін бос')
                    c.execute('UPDATE ai_activity SET result=?,status="approved",approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE id=?',(content,u['id'],id))
                    core.audit(c,u,'ЖИ жобасын педагог бекітті',id);return self.send({'ok':True})
                if path=='/api/support/request':
                    only('teacher','student','parent');category=clean(d.get('category'),30)
                    if category not in ('medical','psych_private','social','safety'):return self.fail('Санат дұрыс емес')
                    sid=int(u['student_id'] or 0) if role in ('student','parent') else int(d.get('student_id') or 0)
                    r=c.execute('SELECT class_id FROM students WHERE id=?',(sid,)).fetchone()
                    if not r or not sid_ok(sid):return self.fail('Оқушыға рұқсат жоқ',403)
                    # Sensitive detail remains in restricted support_cases, not sent to AI.
                    txt=clean(d.get('details'),1200)
                    if not txt:return self.fail('Өтініш мәтіні керек')
                    assignment={'medical':'nurse','psych_private':'psychologist','social':'social','safety':'teacher'}[category]
                    c.execute('INSERT INTO support_cases(student_id,class_id,category,details,assigned_role,created_by) VALUES(?,?,?,?,?,?)',(sid,r['class_id'],category,txt,assignment,u['id']))
                    core.audit(c,u,'Құпия қолдау өтініші',category);return self.send({'ok':True,'notice':'Тек ішкі кабинетке жіберілді; шұғыл жағдайда дереу ересек адамға/жедел қызметке хабарласу керек.'})
                if path=='/api/support/decision':
                    only('nurse','psychologist','social','teacher');id=int(d.get('id') or 0)
                    r=c.execute('SELECT * FROM support_cases WHERE id=?',(id,)).fetchone()
                    if not r or (r['assigned_role']!=role) or (role=='teacher' and r['class_id'] not in class_ids(c,u)):return self.fail('Өтінішке рұқсат жоқ',403)
                    state=clean(d.get('status'),20)
                    if state not in ('reviewed','in_progress','closed'):return self.fail('Күйі дұрыс емес')
                    c.execute('UPDATE support_cases SET status=?,handled_by=?,handled_at=CURRENT_TIMESTAMP WHERE id=?',(state,u['id'],id))
                    core.audit(c,u,'Қолдау өтініші өңделді',id);return self.send({'ok':True})
                if path=='/api/students/archive':
                    only('teacher');sid=int(d.get('id') or 0)
                    if not sid_ok(sid):return self.fail('Рұқсат жоқ',403)
                    c.execute('UPDATE students SET archived=1,updated_at=CURRENT_TIMESTAMP WHERE id=?',(sid,))
                    c.execute('INSERT INTO student_change_history(student_id,action,actor_id) VALUES(?,?,?)',(sid,'archive',u['id']))
                    core.audit(c,u,'Оқушы архивтелді',sid);return self.send({'ok':True})
                if path=='/api/students/update':
                    only('teacher');sid=int(d.get('id') or 0)
                    if not sid_ok(sid):return self.fail('Рұқсат жоқ',403)
                    for k in ('full_name','guardian_name','guardian_contact'):
                        if k in d:
                            prev=c.execute(f'SELECT {k} FROM students WHERE id=?',(sid,)).fetchone()[0]
                            new=clean(d.get(k),170)
                            if not new and k=='full_name':return self.fail('Оқушы аты бос')
                            c.execute(f'UPDATE students SET {k}=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(new,sid))
                            c.execute('INSERT INTO student_change_history(student_id,action,field,previous,new_value,actor_id) VALUES(?,?,?,?,?,?)',(sid,'update',k,prev,new,u['id']))
                    core.audit(c,u,'Оқушы карточкасы өзгерді',sid);return self.send({'ok':True})
                if path=='/api/import/preview':
                    only('teacher');text=clean(d.get('csv'),80000)
                    rows=list(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
                    if not rows:return self.fail('CSV тақырыбы мен жазбалар қажет')
                    if len(rows)>250:return self.fail('Бір импортта 250 оқушыдан артық болмауы тиіс')
                    preview=[]
                    for r in rows:
                        name=clean(r.get('full_name') or r.get('аты-жөні'),170)
                        if not name:continue
                        preview.append({'full_name':name,'guardian_name':clean(r.get('guardian_name'),120),'class_id':int(d.get('class_id') or 0)})
                    if not preview:return self.fail('full_name деген баған болуы керек')
                    if preview[0]['class_id'] not in class_ids(c,u):return self.fail('Сыныпқа рұқсат жоқ',403)
                    job=c.execute('INSERT INTO import_jobs(name,kind,rows_count,status,details,created_by) VALUES(?,?,?,?,?,?)',(clean(d.get('name'),90),'student_csv',len(preview),'review',json.dumps(preview,ensure_ascii=False),u['id'])).lastrowid
                    core.audit(c,u,'CSV алдын ала қаралды',job)
                    return self.send({'ok':True,'id':job,'rows':len(preview),'preview':preview[:12],'note':'Тек тексеріп бекіткеннен кейін базаға қосылады.'})
                if path=='/api/import/commit':
                    only('teacher');id=int(d.get('id') or 0)
                    r=c.execute('SELECT * FROM import_jobs WHERE id=? AND created_by=? AND status="review" AND kind="student_csv"',(id,u['id'])).fetchone()
                    if not r:return self.fail('Тексерілген CSV табылмады',404)
                    items=json.loads(r['details']);count=0
                    for item in items:
                        if item['class_id'] not in class_ids(c,u):raise PermissionError('Сыныпқа рұқсат жоқ')
                        c.execute('INSERT INTO students(full_name,class_id,guardian_name) VALUES(?,?,?)',(item['full_name'],item['class_id'],item['guardian_name']))
                        count+=1
                    c.execute('UPDATE import_jobs SET status="approved" WHERE id=?',(id,))
                    core.audit(c,u,'CSV бекітілді және қосылды',count);return self.send({'ok':True,'count':count})
                if path=='/api/bug-report':
                    only('teacher','subject','parent','student','deputy','director','admin');description=clean(d.get('description'),1500)
                    if not description:return self.fail('Ақау сипаттамасы қажет')
                    c.execute('INSERT INTO records(kind,title,content,created_by) VALUES(?,?,?,?)',('Ақау журналы','Ақау туралы хабарлама',description,u['id']))
                    core.audit(c,u,'Ақау туралы хабарланды');return self.send({'ok':True})
        except (PermissionError,ValueError) as e:return self.fail(str(e),403)
        except Exception as e:return self.fail('Әрекет орындалмады: '+str(e)[:120],500)
        return self.fail('API жолы табылмады',404)


def run():
    init_extra()
    port=int(os.environ.get('CLASSMATE_PORT','8772'))
    # loopback only by design. Internet exposure requires secure cloud infrastructure & audit.
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'ClassMate AI v3: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()

if __name__=='__main__':run()
