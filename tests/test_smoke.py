"""Functional smoke tests with isolated temporary copy and synthetic student data.
Run: py tests/test_smoke.py. Tests do not contact the Internet or install packages.
"""
import os,sys,json,time,subprocess,tempfile,pathlib,shutil,http.client,http.server,threading
ROOT=pathlib.Path(__file__).resolve().parents[1]
TESTPORT=18772
class Mock(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  b=json.dumps({'models':[{'name':'qwen3:4b'}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  self.rfile.read(int(self.headers.get('Content-Length','0')))
  b=json.dumps({'message':{'content':'Сынып сағатының қазақша мәтіні. Мақсаты және тапсырмалары берілген.'}}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass

class Client:
 def __init__(self):self.cookie='';self.csrf='';self.calls=[]
 def request(self,method,path,data=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',TESTPORT,timeout=15)
  h={'Cookie':self.cookie}
  if data is not None:h.update({'Content-Type':'application/json','X-CSRF-Token':self.csrf})
  if headers:h.update(headers)
  body=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
  c.request(method,path,body,h);r=c.getresponse();raw=r.read();status=r.status
  if r.getheader('Set-Cookie'):self.cookie=r.getheader('Set-Cookie').split(';')[0]
  try:res=json.loads(raw)
  except:res=raw
  c.close();self.calls.append((method,path,status));return status,res
 def login(self,name,pw):
  code,result=self.request('POST','/api/login',{'username':name,'password':pw});assert code==200,(code,result)
  code,result=self.request('GET','/api/me');assert code==200;self.csrf=result['csrf'];return result
 def act(self,path,payload):return self.request('POST',path,payload)
 def get(self,path):return self.request('GET',path)

passed=[]
def test(name,cond):
 assert cond,name
 passed.append(name)

if __name__=='__main__':
 work=pathlib.Path(tempfile.mkdtemp(prefix='classmate-v3-'))
 for f in ['server.py','core.py','doc_exports.py','index.html']:
  shutil.copy2(ROOT/f,work/f)
 mock=http.server.ThreadingHTTPServer(('127.0.0.1',18773),Mock)
 threading.Thread(target=mock.serve_forever,daemon=True).start()
 env=os.environ.copy();env['CLASSMATE_PORT']=str(TESTPORT);env['CLASSMATE_OLLAMA_URL']='http://127.0.0.1:18773/api/chat'
 p=subprocess.Popen([sys.executable,'server.py'],cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 try:
  for _ in range(50):
   try:
    c=Client();code,data=c.get('/api/health')
    if code==200:break
   except Exception:time.sleep(.12)
  else:raise RuntimeError('server did not start: '+p.stdout.read())
  a=Client();test('Бірінші кіруде setup керек',a.get('/api/status')[1]['setup_required'])
  code,_=a.get('/api/students');test('Аноним оқушыны көрмейді',code in (401,403))
  code,r=a.act('/api/setup',{'username':'root_admin','name':'Техникалық әкімші','password':'StrongPass2026##'});test('Ортақ парольсіз әкімші құру',code==200)
  a.login('root_admin','StrongPass2026##')
  code,r=a.act('/api/users',{'username':'teacher1','name':'Сынып жетекші 1','role':'teacher'});test('Жеке мұғалім аккаунты',code==200);tpass=r['temporary_password']
  t=Client();me=t.login('teacher1',tpass);test('Уақытша пароль өзгертуді сұрайды',bool(me['user']['must_change']))
  code,_=t.act('/api/classes',{'name':'7 А'});test('Уақытша парольмен жазуға болмайды',code==403)
  code,_=t.act('/api/change-password',{'old_password':tpass,'new_password':'TeacherPass2026##'});test('Құпиясөзді ауыстыру',code==200)
  t.login('teacher1','TeacherPass2026##')
  code,_=t.act('/api/classes',{'name':'7 А'});test('Сынып құру',code==200)
  code,cdata=t.get('/api/classes');cl=cdata[0]['id']
  code,r=t.act('/api/students',{'full_name':'Айша Оқушы','class_id':cl,'guardian_name':'Ата-ана'});test('Оқушы қосу',code==200);sid=r['id']
  code,r=t.act('/api/students/update',{'id':sid,'full_name':'Айша Оқушы-1'});test('Өзгерістер тарихы',code==200)
  code,r=t.act('/api/attendance',{'student_id':sid,'day':'2026-11-10','subject':'Информатика','status':'absent'});test('Келмегеннен хабарлама жобасы',code==200 and r['draft_created'])
  code,msgs=t.get('/api/messages');test('Хабарлама тексеруді күтеді',code==200 and msgs[0]['state']=='draft');mid=msgs[0]['id']
  code,r=t.act('/api/messages/approve',{'id':mid});test('Мұғалім хабарламаны бекітеді',code==200)
  code,r=t.act('/api/lessons/log',{'class_id':cl,'day':'2026-11-10','topic':'Киберқауіпсіздік','objectives':'Қауіпсіздік','reflection':'Үйренді'});test('Сынып сағаты журналы',code==200)
  code,r=t.act('/api/plans',{'class_id':cl,'topic':'Киберқауіпсіздік'});test('Тәрбие жоспары',code==200)
  code,r=t.get('/api/plans');pid=r[0]['id']
  code,r=t.act('/api/plans/decision',{'id':pid,'decision':'submit','comment':''});test('Жоспарды келісуге жіберу',code==200)
  code,r=t.act('/api/consents/save',{'student_id':sid,'kind':'photo','granted':False,'evidence':'Құпия дерек енгізілмеген'});test('Келісімдерді басқару',code==200)
  code,r=t.act('/api/import/preview',{'name':'test.csv','class_id':cl,'csv':'full_name,guardian_name\nАрман Үлгі,Ата-ана 2'});test('Импорт алдын ала тексеру',code==200 and r['rows']==1);job=r['id']
  code,r=t.act('/api/import/commit',{'id':job});test('Импорт мұғалім бекіткен соң',code==200 and r['count']==1)
  code,r=t.act('/api/assistant/compose',{'kind':'class_hour','prompt':'Қауіпсіздік','class_name':'7 А'});test('Ollama жергілікті API байланысы',code==200 and r['label'].startswith('ЖИ'));aid=t.get('/api/ai/history')[1][0]['id']
  code,r=t.act('/api/assistant/decision',{'id':aid,'result':'Сауатты дайын сценарий'});test('ЖИ нәтижесін бекіту',code==200)
  code,r=t.get('/api/document?kind=plan&format=docx');test('DOCX жоба экспорты',code==200 and isinstance(r,bytes) and r[:2]==b'PK')
  code,r=t.get('/api/document?kind=analysis&format=html');test('HTML/PDF басып шығару',code==200 and isinstance(r,bytes) and b'html' in r[:50])
  code,r=t.get('/api/document?kind=plan&format=pdf');test('PDF жоба экспорты (кітапхана орнатылса)',(code==200 and isinstance(r,bytes) and r[:4]==b'%PDF') or (code==501 and isinstance(r,dict) and 'PDF' in r.get('error','')))
  code,r=t.get('/api/criteria');test('12 критерийдің ашық мәртебесі',code==200 and len(r['acceptance'])==12)
  code,r=t.get('/api/norms');test('Ресми нормативтік карточкалар',code==200 and len(r)>=3)
  code,r=t.act('/api/support/request',{'student_id':sid,'category':'medical','details':'Медициналық қызметкерге хабарлау'});test('Құпия медициналық сұрау',code==200)
  code,r=t.get('/api/support/requests');test('Медицина өтініші сынып жетекшіге толық ашылмайды',code==200 and not r)
  code,r=a.act('/api/users',{'username':'parent1','name':'Ата-ана 1','role':'parent','student_id':sid});test('Ата-ананы жеке оқушыға байланыстыру',code==200);pp=r['temporary_password']
  parent=Client();parent.login('parent1',pp);parent.act('/api/change-password',{'old_password':pp,'new_password':'ParentPass2026##'});parent.login('parent1','ParentPass2026##')
  code,visible=parent.get('/api/messages');test('Ата-ана тек өз бекітілген хабарламасын көреді',code==200 and visible)
  code,r=parent.act('/api/messages/read',{'id':visible[0]['id']});test('Ата-ананың оқылды белгісі',code==200)
  code,newmsgs=t.get('/api/messages');test('Оқылғаны мұғалімге көрінеді',code==200 and newmsgs[0]['read_count']>=1)
  code,visible=parent.get('/api/social_profiles');test('Әлеуметтік паспорт ата-анаға жабық',code==403)
  code,visible=parent.get('/api/assistant/compose');test('ЖИ endpoint рөлмен жабық',code in (403,404))
  code,visible=parent.get('/api/students');test('Ата-ана өз оқушысын ғана көреді',code==200 and len(visible)==1 and visible[0]['id']==sid)
  code,r=a.act('/api/users',{'username':'deputy1','name':'Орынбасар','role':'deputy'});test('Орынбасар аккаунты',code==200);dp=r['temporary_password']
  dep=Client();dep.login('deputy1',dp);dep.act('/api/change-password',{'old_password':dp,'new_password':'DeputyPass2026##'});dep.login('deputy1','DeputyPass2026##')
  code,r=dep.act('/api/plans/decision',{'id':pid,'decision':'approve'});test('Жоспарды орынбасар бекітеді',code==200)
  code,b=a.get('/api/backup');test('Резервтік көшірме SQLite файлы',code==200 and isinstance(b,bytes) and b.startswith(b'SQLite format 3'))
  code,r=parent.get('/api/backup');test('База көшірмесін ата-ана ала алмайды',code==403)
  code,r=t.get('/api/search?q=%D0%90%D0%B9%D1%88%D0%B0');test('Оқушы іздеу',code==200 and len(r)>=1)
  test('Негізгі 15 модуль коды',len(t.get('/api/criteria')[1]['modules'])==15)
  code,r=t.act('/api/bug-report',{'description':'Тек демонстрациялық тест'});test('Ақау журналы',code==200)
  print('PASS',len(passed))
  for x in passed:print('  ✓',x)
 except Exception as e:
  print('FAIL',len(passed),e)
  print('SERVER OUTPUT:')
  p.terminate()
  try:print(p.communicate(timeout=4)[0][-5000:])
  except:pass
  raise
 finally:
  mock.shutdown();p.terminate()
  try:p.wait(timeout=3)
  except: p.kill()
  shutil.rmtree(work,ignore_errors=True)
