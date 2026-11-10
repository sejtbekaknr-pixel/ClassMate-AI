"""Mocked Chromium static UI smoke (does not reach localhost, which sandbox blocks)."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'index.html').read_text()
mock='''<script>
window.fetch=async function(url,opts){
 let k=String(url).split('/api/')[1]||'';
 let result={};
 if(k==='status')result={setup_required:false};
 else if(k==='me')result={user:{id:2,role:'teacher',name:'Сынақ жетекші',must_change:0},csrf:'testcsrf'};
 else if(k==='classes')result=[{id:1,name:'7-А'}];
 else if(k==='students')result=[{id:1,full_name:'Демо оқушы',class_id:1,class_name:'7-А'}];
 else if(k==='overview'||k==='report')result={students:1,attendance:[],absences:[],plans:0,draft_messages:0,generated:'2026-11-10'};
 else if(k==='criteria')result={modules:[['F01','Басты бет','dashboard']],acceptance:[['AC-01','Рөлдік қолжетімділік','local_tests','Сынақ керек']]};
 else if(k==='norms')result=[{code:'18',title_kk:'Сынып жетекшілігі',title_ru:'Классное руководство',url:'https://adilet.zan.kz/'}];
 else if(k==='integrations')result=[];
 else if(k==='plans'||k==='activities'||k==='assignments'||k==='ai/history'||k==='messages'||k==='social_profiles'||k==='lessons/logs'||k==='audit'||k==='users')result=[];
 return {ok:true,json:async()=>result};
}
</script>'''
html=html.replace('<script>',mock+'<script>',1)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1366,'height':768})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('about:blank');page.set_content(html)
 page.wait_for_timeout(900)
 if not page.locator('#app').is_visible():raise RuntimeError('APP HIDDEN '+str(errors)+page.locator('body').inner_text()[:300])
 page.evaluate('nav();show("criteria")')
 page.wait_for_timeout(250)
 print('CRIT:',page.locator('#content').inner_text()[:800], 'ERRORS:',errors);assert 'AC-01' in page.locator('#content').inner_text()
 page.evaluate('show("laws")')
 page.wait_for_timeout(250)
 assert '18' in page.locator('#content').inner_text()
 page.evaluate('show("settings")')
 page.wait_for_timeout(250)
 assert page.locator('button',has_text='Русский').count()>0
 page.locator('button',has_text='Русский').first.click();page.wait_for_timeout(350)
 assert 'Настройки' in page.locator('#head').inner_text(),page.locator('#head').inner_text()
 page.locator('button',has_text='Қазақша').first.click();page.wait_for_timeout(250)
 page.screenshot(path=str(ROOT/'screenshot_desktop.png'),full_page=True)
 print('Desktop UI PASS, errors:',errors)
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(250)
 page.screenshot(path=str(ROOT/'screenshot_mobile.png'),full_page=True)
 print('Mobile UI PASS')
 browser.close()
