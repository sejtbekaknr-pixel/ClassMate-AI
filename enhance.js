/* ClassMate AI v3 additional functional UI; no external dependencies. */
const CRIT_NAV=['criteria','🧪','Қабылдау критерийлері'];
NAV.push(CRIT_NAV);
for (let r of ['teacher','deputy','director','admin']) { if(!FOR[r].includes('criteria')) FOR[r].push('criteria'); }
const RULABEL={dashboard:'Главная',students:'Мой класс',plans:'План воспитательной работы',lesson:'Классный час',attendance:'Посещаемость и успеваемость',social:'Социальный паспорт',parents:'Родители',safety:'Безопасность',mood:'Психологический климат',events:'Мероприятия',reports:'Документы и отчёты',assistant:'AI помощник',analytics:'Аналитика',laws:'Нормативная база',settings:'Настройки и безопасность',meetings:'Родительские собрания',assignments:'Задания',imports:'Импорт данных',medical:'Медицинская помощь',criteria:'Приёмочные критерии'};
const TR={
 'Басты бет':'Главная','Менің сыныбым':'Мой класс','Тәрбие жоспары':'Воспитательный план','Сынып сағаты':'Классный час',
 'Қатысу және үлгерім':'Посещаемость и успеваемость','Әлеуметтік паспорт':'Социальный паспорт','Ата-аналармен жұмыс':'Работа с родителями',
 'Қауіпсіздік':'Безопасность','Психологиялық ахуал':'Психологический климат','Іс-шаралар':'Мероприятия','Құжаттар және есептер':'Документы и отчёты',
 'ClassMate көмекшісі':'AI помощник ClassMate','Аналитика':'Аналитика','Нормативтік база':'Нормативная база','Баптаулар':'Настройки',
 'Ата-ана жиналысы':'Родительские собрания','Тапсырмалар':'Задания','Деректер импорты':'Импорт данных','Медициналық көмек':'Медицинская помощь',
 'Қабылдау критерийлері':'Критерии приёмки','Жеке кабинетке кіру':'Вход в личный кабинет',
 'Логин':'Логин','Құпиясөз':'Пароль','Кіру':'Войти','Шығу':'Выход','Алғашқы баптау':'Первичная настройка',
 'Әкімшінің аты':'Имя администратора','Әкімшінің логині (латын әрпі)':'Логин администратора (латиница)',
 'Жеке құпиясөз (кемі 12 таңба, әріп пен сан)':'Личный пароль (12+ символов, буквы и цифры)',
 'Әкімші аккаунтын құру':'Создать администратора','Жеке пароль орнату':'Установить личный пароль',
 'Сақтау және кіру':'Сохранить и войти','Жаңа жеке пароль (кемі 12 таңба, әріп пен сан)':'Новый пароль (12+ символов)',
 'Бүгін':'Сегодня','Оқушылар базасы':'База учеников','Сынып':'Класс','Аты-жөні':'ФИО','Ата-ана':'Родитель',
 'Күні':'Дата','Мәртебе':'Статус','Сақтау':'Сохранить','Есепті жүктеу':'Скачать отчёт',
 'Тақырып':'Тема','Жауап':'Ответ','Қолдау':'Поддержка','Сұраныс':'Запрос','Қаралды':'Рассмотрено',
 'Мұғалім':'Учитель','Жоба дайындау':'Подготовить проект','Оқушы':'Ученик','Мәтін':'Текст',
 'Мұғалім бекітеді':'Утверждает учитель','Оқушы саны':'Количество учеников','Қатысу':'Посещаемость',
 'Бекіту':'Утвердить','Құжатты сақтау':'Сохранить документ','Бөлім':'Раздел','Санат':'Категория',
 'Әр пайдаланушының өз логині және жеке паролі болады':'У каждого пользователя свой логин и пароль',
 'Сынып жетекшісіне арналған жұмыс кеңістігі':'Рабочее пространство классного руководителя',
 'Құпиясөзді өзгерту':'Сменить пароль','Оқушылар':'Ученики','Тіл':'Язык'
};
let UI_LANG='kk';try{UI_LANG=localStorage.getItem('classmate_lang')||'kk'}catch(e){}
const ORIGINAL=new WeakMap();
function translate(root=document.body){
 const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 while(walk.nextNode()){
  const node=walk.currentNode;
  if(!node.parentElement||['PRE','CODE','TEXTAREA','SCRIPT','STYLE'].includes(node.parentElement.tagName))continue;
  if(!ORIGINAL.has(node))ORIGINAL.set(node,node.nodeValue);
  const val=ORIGINAL.get(node), trim=val.trim();
  if(TR[trim])node.nodeValue=UI_LANG==='ru'?val.replace(trim,TR[trim]):val;
 }
 document.documentElement.lang=UI_LANG==='ru'?'ru':'kk';
 document.querySelectorAll('input[placeholder],textarea[placeholder]').forEach(el=>{
  if(!el.dataset.kazplaceholder)el.dataset.kazplaceholder=el.placeholder;
  el.placeholder=UI_LANG==='ru'?(TR[el.dataset.kazplaceholder]||el.dataset.kazplaceholder):el.dataset.kazplaceholder;
 });
}
function setLanguage(lang){UI_LANG=lang==='ru'?'ru':'kk';try{localStorage.setItem('classmate_lang',UI_LANG)}catch(e){}nav();show(PAGE);translate();}
const v2render=render;
render=async function(id){
 if(id==='criteria'){await renderCriteria();}else{await v2render(id);}
 if(ME?.role==='teacher' || ME?.role==='deputy' || ME?.role==='director'|| ME?.role==='admin'){
  if(id==='plans'||id==='lesson')await extendPlans(id);
  if(id==='students'&&ME.role==='teacher')extendStudents();
  if(id==='imports'&&ME.role==='teacher')extendImport();
  if(id==='reports'&&ME.role==='teacher')extendReports();
  if(id==='assistant' && ME.role==='teacher')await extendAI();
 }
 if(id==='lesson')await extendLesson(id);
 if(id==='parents')await extendParents();
 if(id==='medical'||id==='mood'||id==='safety')await extendSupport(id);
 if(id==='laws')await extendLaws();
 if(id==='settings')await extendSettings();
 if(id==='dashboard' && (ME.role==='teacher'||ME.role==='subject'))extendSearch();
 translate($('content'));
};
const v2nav=nav;
nav=function(){v2nav(); if(UI_LANG==='ru')document.querySelectorAll('nav button').forEach(btn=>{let key=btn.id.replace('nav_','');btn.textContent=NAV.find(a=>a[0]===key)?.[1]+'  '+(RULABEL[key]||btn.textContent);});}
const v2show=show;
show=async function(id){PAGE=id;$('head').innerText=UI_LANG==='ru'?(RULABEL[id]||'ClassMate AI'):(NAV.find(n=>n[0]===id)||[])[2]||'ClassMate AI';document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.id==='nav_'+id));try{await render(id)}catch(e){set(panel('Қате',esc(e.message)))}translate();}

function appendHTML(html){$('content').insertAdjacentHTML('beforeend',html);}
async function renderCriteria(){
 const d=await api('criteria');
 const icons={implemented:'✅',partial:'◐',local_tests:'🧪',unverified:'⚠️',external:'🔒'};
 set(panel('Техникалық тапсырманың 15 модулі',table(['Код','Модуль','Сайттағы бөлім'],d.modules.map(m=>[m[0],m[1],(NAV.find(n=>n[0]===m[2])||[])[2]||m[2]])))+
 panel('12 қабылдау критерийі — нақты жағдай',`<p class="notice">Бұлар автоматты түрде «100%» деп белгіленбейді. Қол қою, қауіпсіздік аудиті, пилот және сыртқы интеграциялар бөлек қабылданады.</p>`+
 table(['Код','Қабылдау талабы','Мәртебе','Ескертпе'],d.acceptance.map(a=>[a[0],a[1],icons[a[2]]+' '+a[2],a[3]])))+
 panel('Бағалау құжаттамасы','<p><a href="/api/health" target="_blank">Жүйе денсаулығын тексеру</a> · Архивтегі ACCEPTANCE.md және tests/ файлдарында қабылдау матрицасы мен сынақтар бар.</p>'));
}
async function extendPlans(id){
 const plans=await api('plans');
 appendHTML(panel('Жоспарларды келісу және бекіту',`<p class="hint">Сынып жетекшісі жобаны тексеруге жібереді, тәрбие ісі жөніндегі орынбасар бекітеді.</p>`+
 table(['Тақырып','Мәртебе','Кезең'],plans.map(p=>[p.topic,p.status||'draft',(ME.role==='teacher' && (p.status||'draft')!=='approved'?`Жоба ID ${p.id}`:`Жоба ID ${p.id}`)]))+
 (plans.length?`<label>Жоспар</label><select id="approvalPlan">${plans.map(p=>`<option value="${p.id}">${esc(p.topic)} · ${esc(p.status||'draft')}</option>`).join('')}</select><label>Түсіндірме</label><input id="planComment" placeholder="Қажет болса түсініктеме"><div class="toolbar">${ME.role==='teacher'?'<button class="primary" onclick="decidePlan(\'submit\')">Келісуге жіберу</button>':''}${ME.role==='deputy'?'<button class="primary" onclick="decidePlan(\'approve\')">Бекіту</button> <button class="secondary" onclick="decidePlan(\'return\')">Түзетуге қайтару</button>':''}</div>`:'<p>Жоспар әлі жоқ</p>')));
}
async function decidePlan(decision){try{await api('plans/decision',{id:+$('approvalPlan').value,decision,comment:$('planComment').value});toast('Жоспар мәртебесі өзгерді');show(PAGE)}catch(e){error(e)}}
function extendStudents(){
 appendHTML(panel('Оқушы карточкасын жаңарту және архивтеу',`<p class="hint">Өзгерістер пайдаланушы және күн бойынша сақталады.</p><label>Оқушы</label>${pickStudent().replace('id="sid"','id="editSid"')}<label>Жаңа аты-жөні</label><input id="editName" placeholder="Жаңартылған аты-жөні"><div class="toolbar"><button class="secondary" onclick="updateStudent()">Өзгерісті сақтау</button><button class="secondary danger" onclick="archiveStudent()">Архивке жіберу</button></div>`)+
 panel('Рұқсат пен келісімдерді тіркеу',`<label>Оқушы</label>${pickStudent().replace('id="sid"','id="consentSid"')}<div class="fields"><div><label>Келісім түрі</label><select id="consentKind"><option value="event">Іс-шараға қатысу</option><option value="photo">Фото материал</option><option value="communications">Байланыс арнасы</option><option value="data_processing">Деректі өңдеу</option></select></div><div><label>Мәртебе</label><select id="consentGrant"><option value="1">Бар</option><option value="0">Жоқ / кері алынған</option></select></div></div><label>Келісімнің негізі</label><input id="consentEvidence" placeholder="Келісілген уақыт, құжат тіркеу нөмірі (тек демонстрациялық)"><button class="secondary" onclick="saveConsent()">Мәртебені сақтау</button>`));
}
async function updateStudent(){try{await api('students/update',{id:+$('editSid').value,full_name:$('editName').value});toast('Өзгеріс сақталды');STUDENTS=await api('students');show('students')}catch(e){error(e)}}
async function archiveStudent(){if(!confirm('Оқушы карточкасын архивке жібересіз бе?'))return;try{await api('students/archive',{id:+$('editSid').value});toast('Архивке жіберілді');STUDENTS=await api('students');show('students')}catch(e){error(e)}}
async function saveConsent(){try{await api('consents/save',{student_id:+$('consentSid').value,kind:$('consentKind').value,granted:$('consentGrant').value==='1',evidence:$('consentEvidence').value});toast('Келісім сақталды')}catch(e){error(e)}}
function extendImport(){
 appendHTML(panel('Мұғалім тексеретін CSV импорт',`<p class="hint">CSV бағандары: full_name,guardian_name. Бір импортта 250 оқушыға дейін. Жазбалар тек бекіткеннен кейін базаға қосылады.</p><label>Сынып</label>${pickClass().replace('id="cid"','id="csvClass"')}<label>CSV файлы</label><input id="csvFile" type="file" accept=".csv,text/csv"><button class="primary" onclick="previewStudentsCSV()">Алдын ала тексеру</button><div id="csvPreview"></div>`));
}
async function previewStudentsCSV(){let f=$('csvFile').files[0];if(!f)return toast('CSV таңдаңыз');try{let r=await api('import/preview',{name:f.name,csv:await f.text(),class_id:+$('csvClass').value});$('csvPreview').innerHTML='<div class="notice">'+r.rows+' жазба тексеруге дайын. Басқа сыныпқа рұқсат етілмейді.</div>'+table(['Оқушы','Ата-ана'],r.preview.map(x=>[x.full_name,x.guardian_name]))+`<button class="primary" onclick="commitStudentCSV(${r.id})">Тексердім — базаға енгізу</button>`}catch(e){error(e)}}
async function commitStudentCSV(id){if(!confirm('Осы CSV жазбаларын базаға енгізесіз бе?'))return;try{let r=await api('import/commit',{id});toast(r.count+' оқушы енгізілді');STUDENTS=await api('students');show('students')}catch(e){error(e)}}
function extendReports(){
 appendHTML(panel('Нормативтік құжат нысандары — жоба экспорты',`<p class="notice">Көрме нұсқасында автоматты жасалған құжат — жоба. Мектеп бекіткен ресми бланкіге мұғалім сәйкестендіреді.</p><label>Құжат</label><select id="docKind"><option value="plan">Тәрбие жұмысының жоспары</option><option value="analysis">Тәрбие жұмысының талдауы</option><option value="social">Әлеуметтік паспорт (құпия)</option><option value="minutes">Ата-аналар жиналысының хаттамасы</option><option value="lesson">Сынып сағаты журналы</option><option value="summary">Жинақталған есеп</option></select><div class="toolbar"><button class="primary" onclick="docExport('docx')">Word DOCX</button><button class="secondary" onclick="docExport('pdf')">PDF</button><button class="secondary" onclick="docExport('html')">Басып шығару / PDF сақтау</button></div>`));
}
function docExport(fmt){let k=$('docKind').value;window.open('/api/document?kind='+encodeURIComponent(k)+'&format='+encodeURIComponent(fmt),'_blank')}
async function extendAI(){let a=await api('ai/history');appendHTML(panel('ЖИ жобасын педагогтің бекітуі',`<p class="hint">AI мәтіні автоматты түрде ата-анаға жіберілмейді және ресми шешім болып саналмайды.</p>${a.length?a.slice(0,10).map(x=>`<details class="card"><summary>${esc(x.kind)} · ${esc(x.created_at)} · ${esc(x.status)}</summary><label>Редакциялау</label><textarea id="aiEdit_${x.id}">${esc(x.result)}</textarea><button class="primary" onclick="approveAI(${x.id})">Мәтінді тексеріп бекіту</button></details>`).join(''):'<p>ЖИ жобалары әлі жоқ</p>'}`));}
async function approveAI(id){try{await api('assistant/decision',{id,result:$('aiEdit_'+id).value});toast('AI жобасы тексеріліп бекітілді');show('assistant')}catch(e){error(e)}}
async function extendLesson(id){
 if(ME.role==='teacher')appendHTML(panel('Сынып сағатының өтуін тіркеу (F04)',`<label>Сынып</label>${pickClass().replace('id="cid"','id="lessonClass"')}<div class="fields"><div><label>Күні</label><input type="date" id="lessonDate" value="${new Date().toISOString().slice(0,10)}"></div><div><label>Тақырып</label><input id="lessonTopic" placeholder="Сынып сағатының тақырыбы"></div></div><label>Мақсаты</label><input id="lessonGoal"><label>Материал</label><input id="lessonMaterials"><label>Қатысу туралы ескертпе</label><input id="lessonAttendance"><label>Оқушы рефлексиясы</label><textarea id="lessonReflection"></textarea><button class="primary" onclick="saveLesson()">Журналға тіркеу</button>`));
 if(['teacher','director','deputy'].includes(ME.role)){
  let logs=await api('lessons/logs');appendHTML(panel('Өткен сынып сағаттары',table(['Күн','Сынып','Тақырып','Рефлексия'],logs.map(x=>[x.day,x.class_name,x.topic,x.reflection]))));
 }
}
async function saveLesson(){try{await api('lessons/log',{class_id:+$('lessonClass').value,day:$('lessonDate').value,topic:$('lessonTopic').value,objectives:$('lessonGoal').value,materials:$('lessonMaterials').value,attendance_note:$('lessonAttendance').value,reflection:$('lessonReflection').value});toast('Журналға сақталды');show('lesson')}catch(e){error(e)}}
async function extendParents(){
 if(ME.role==='teacher')appendHTML(panel('Жіберілген хабарламаларды бекіту туралы',`<p class="notice">«Бекіту» батырмасы ішкі кабинетте көрсетуге ғана рұқсат береді; нақты SMS/WhatsApp жіберілмейді. Ата-ана өз баласына қатысты ақпаратты ғана көреді.</p>`));
 if(ME.role==='parent'){
   let msgs=await api('messages');
   if(msgs.length)appendHTML(panel('Хабарламаны оқылған деп белгілеу',msgs.map(m=>`<p><span class="muted">${esc(m.created_at)}</span> <button class="secondary" onclick="markRead(${m.id})">Оқылды</button></p>`).join('')))
 }
}
async function markRead(id){try{await api('messages/read',{id});toast('Хабарлама оқылды деп белгіленді')}catch(e){error(e)}}
async function extendSupport(id){
 const types=id==='medical'?['medical','Медицина қызметкеріне сұрау']:id==='mood'?['psych_private','Психологке құпия сұрау']:['safety','Қауіпсіздік туралы хабарлама'];
 const allowed=['student','parent','teacher'].includes(ME.role);
 if(allowed){let choose=(ME.role==='teacher'?`<label>Оқушы</label>${pickStudent().replace('id="sid"','id="supportStudent"')}`:'');
  appendHTML(panel('Маманға тікелей ішкі өтініш (F08/F09)',`<p class="notice">Медициналық не психологиялық диагноз қойылмайды. Шұғыл жағдайда платформаға ғана сенбей, бірден жауапты ересекке немесе жедел көмекке хабарласу қажет.</p>${choose}<label>Хабарлама</label><textarea id="supportDetails" placeholder="Көмек түрін қысқаша жазыңыз"></textarea><button class="primary" onclick="requestSupport('${types[0]}')">${types[1]}</button>`));
 }
 try{let a=await api('support/requests');if(a.length)appendHTML(panel('Көмек өтініштерінің мәртебесі',a.map(x=>`<p class="hint">#${x.id} · ${esc(x.category)} · ${esc(x.status)} ${['nurse','psychologist','social','teacher'].includes(ME.role)?`<button class="secondary" onclick="resolveSupport(${x.id})">Қаралды деп белгілеу</button>`:''}</p>`).join('')))}catch(e){}
}
async function requestSupport(category){try{let r=await api('support/request',{category,student_id:ME.role==='teacher'?+$('supportStudent').value:undefined,details:$('supportDetails').value});toast(r.notice);show(PAGE)}catch(e){error(e)}}
async function resolveSupport(id){try{await api('support/decision',{id,status:'reviewed'});toast('Өтініш қаралды');show(PAGE)}catch(e){error(e)}}
async function extendLaws(){
 try{let data=await api('norms');appendHTML(panel('Құжаттар тізілімі және ресми дереккөздер',`<p class="hint">Сілтемелер — қолмен енгізілген анықтамалық жазбалар. Өзгерістерді заңгер/мектеп маманы ресми «Әділеттен» тексеруі тиіс.</p><div class="tablewrap"><table><thead><tr><th>Нөмір</th><th>Құжат</th><th>Редакция күні</th><th>Дереккөз</th></tr></thead><tbody>${data.map(x=>`<tr><td>${esc(x.code)}</td><td>${esc(UI_LANG==='ru'?x.title_ru:x.title_kk)}</td><td>${esc(x.revision_date||'Тексеру қажет')}</td><td>${x.url?.startsWith('https://adilet.zan.kz/')?`<a href="${esc(x.url)}" target="_blank" rel="noopener">Әділет</a>`:'—'}</td></tr>`).join('')}</tbody></table></div>`));}catch(e){error(e)}
}
async function extendSettings(){
 appendHTML(panel('Жүйеден шығу',`<button class="secondary" onclick="logout()">Шығу / Выход</button>`));
 appendHTML(panel('Интерфейс тілі / Язык интерфейса',`<div class="toolbar"><button class="secondary" onclick="setLanguage('kk')">Қазақша</button><button class="secondary" onclick="setLanguage('ru')">Русский</button></div><p class="hint">Тілді ауыстырғанда база өзгермейді. Қалған кәсіби мәтіндердің толық аудармасы пилотта тексеріледі.</p>`));
 appendHTML(panel('Ақау туралы хабарлау және қабылдау тесті',`<label>Ақауды сипаттау</label><textarea id="bugText" placeholder="Қай бөлім, қандай батырма, не дұрыс істемеді..."></textarea><button class="secondary" onclick="submitBug()">Ақауды тіркеу</button>`));
 if(ME.role==='admin'){
 let status=await api('integrations');appendHTML(panel('Күнделікті резервтік көшірме (демонстрация)',`<p class="hint">SQLite көшірмесін жасайды. Аутоматты қалпына келтіру үшін әкімшіде бөлек CLI команда бар.</p><button class="primary" onclick="location.href='/api/backup'">База көшірмесін жүктеу</button>`)+panel('Интеграциялар',table(['Жүйе','Мәртебе','Ескертпе'],status.map(x=>[x.name,x.status,x.description]))));
 }
}
async function submitBug(){try{await api('bug-report',{description:$('bugText').value});toast('Ақау тіркелді');$('bugText').value=''}catch(e){error(e)}}
function extendSearch(){appendHTML(panel('Оқушыны аты бойынша іздеу',`<div class="toolbar"><input id="searchInput" style="max-width:350px" placeholder="Оқушы аты (кемі екі әріп)"><button class="secondary" onclick="searchStudent()">Іздеу</button></div><div id="searchResult"></div>`));}
async function searchStudent(){try{let q=$('searchInput').value;let r=await api('search?q='+encodeURIComponent(q));$('searchResult').innerHTML=table(['Оқушы','Сынып'],r.map(x=>[x.full_name,(CLASSES.find(c=>c.id===x.class_id)||{}).name||x.class_id]))}catch(e){error(e)}}

// Do not auto-send to external services. Browser-side label for all AI drafts.
const OLDcompose=composeAI;
composeAI=async function(){await OLDcompose();};
// Translation can be toggled at any time without editing stored data.
setTimeout(()=>translate(),0);
