const assert=require('node:assert/strict'),path=require('node:path');const {pathToFileURL}=require('node:url');const {fixture}=require('./helpers.cjs');
const C=require('../assets/js/csv.js'),M=require('../assets/js/model.js');
const url=pathToFileURL(path.resolve(__dirname,'../cvereview.html')).href;
const input=(name,text)=>({name,mimeType:name.endsWith('.csv')?'text/csv':'application/json',buffer:Buffer.from(text)});
async function selectFilter(p,id,choices=[]){
 const root=p.locator('#'+id);if(!Array.isArray(choices))choices=choices===''?[]:[choices];
 if(!await root.evaluate(el=>el.open))await root.locator('summary').click();
 await root.locator('[data-action="clear-filter"]').click();
 for(const choice of choices){const label=typeof choice==='object'?choice.label:({'готов':'Готов','ожидает ревью':'Ожидает ревью'}[choice]||choice);await root.getByRole('checkbox',{name:label,exact:true}).check();}
 await root.locator('summary').click();
}
async function run(browser,only='all'){
 if(only==='all'||only==='sorting'){
  const p=await browser.newPage();try{
   const rows=[
    {'Task ID':'10','Разработчик':'Борис','Принятая мера':'Обновление версии','Статус':'Готов','Компонент':'zlib','CVE ID':'CVE-2026-10000','End date':'03.11.2026','Task date':'01.11.2026','RHEL severity':'Important'},
    {'Task ID':'2','Разработчик':'Анна','Принятая мера':'Бэкпорт патча','Статус':'Ожидает ревью','Компонент':'openssl','CVE ID':'CVE-2026-9999','End date':'01.11.2026','Task date':'03.11.2026','RHEL severity':'Critical'},
    {'Task ID':'100','Разработчик':'Вера','Принятая мера':'Собственный патч','Статус':'Готов','Компонент':'kernel','CVE ID':'CVE-2026-10001','End date':'02.11.2026','Task date':'02.11.2026','RHEL severity':'Low'}
   ];
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('sort.csv',fixture(rows)));await p.waitForSelector('.list-card');
   assert.equal(await p.locator('#sort-direction').count(),1,'Sort direction control must be available');
   const tasks=()=>p.locator('.list-card').evaluateAll(els=>els.map(el=>el.dataset.task));
   assert.deepEqual(await tasks(),['2','10','100']);
   const cases=[['end',['2','100','10'],['10','100','2']],['taskdate',['10','100','2'],['2','100','10']],['dev',['2','10','100'],['100','10','2']],['measure',['2','10','100'],['100','10','2']],['component',['100','2','10'],['10','2','100']],['task',['2','10','100'],['100','10','2']],['cve',['2','10','100'],['100','10','2']],['status',['10','100','2'],['2','10','100']],['severity',['2','10','100'],['100','10','2']]];
   for(const [key,first,reverse] of cases){await p.locator('#order').selectOption(key);assert.deepEqual(await tasks(),first,key);await p.locator('#sort-direction').click();assert.deepEqual(await tasks(),reverse,key+' reversed');}
   await p.locator('.list-card[data-task="2"] input[data-item="branch"][value="ok"]').check();await selectFilter(p,'dev',['Анна','Борис']);
   await p.locator('#order').selectOption('component');assert.deepEqual(await tasks(),['2','10']);await p.locator('#sort-direction').click();assert.deepEqual(await tasks(),['10','2']);
   await p.locator('#search').fill('CVE-2026-9999');assert.deepEqual(await tasks(),['2']);assert.equal(await p.locator('.list-card input[data-item="branch"][value="ok"]').isChecked(),true);assert.equal(await p.locator('#order').inputValue(),'component');
   await p.locator('#csv-file').setInputFiles(input('many.csv',fixture(Array.from({length:56},(_,i)=>({'Task ID':String(200+i)})))));await p.waitForFunction(()=>document.querySelectorAll('.list-card').length===50);
   await p.locator('[data-action="next-page"]').click();assert.equal(await p.locator('.list-card').count(),6);await p.locator('#order').selectOption('end');assert.equal(await p.locator('.list-card').count(),50);assert.equal(await p.locator('[data-action="prev-page"]').isDisabled(),true);
   console.log('PASS regression: sort fields/directions, combined filters, pagination and review preservation');
  }finally{await p.close();}
 }
 if(only==='all'||only==='multi'){
  const p=await browser.newPage();try{
   const custom='Особая мера с длинным названием для проверки ширины выпадающего списка';
   const rows=[
    {'Разработчик':'Анна','Статус':'Ожидает ревью','Принятая мера':'Бэкпорт патча'},
    {'Разработчик':'Борис','Статус':'Готов','Принятая мера':'Обновление версии'},
    {'Разработчик':'Вера','Статус':'Ожидает ревью','Принятая мера':'Бэкпорт патча'},
    {'Разработчик':'Анна','Статус':'Готов','Принятая мера':'Обновление версии'},
    {'Разработчик':'Борис','Статус':'Ожидает ревью','Принятая мера':custom},
    {'Разработчик':'Вера','Статус':'Готов','Принятая мера':''}
   ].map((r,i)=>({...r,'Task ID':String(100+i)}));
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('multi.csv',fixture(rows)));await p.waitForSelector('.list-card');
   assert.equal(await p.locator('#dev input[type="checkbox"]').count(),3,'Filters must offer checkbox choices');
   const tasks=async()=>(await p.locator('.list-card').evaluateAll(els=>els.map(el=>el.dataset.task))).sort();
   await selectFilter(p,'dev',['Анна','Борис']);assert.deepEqual(await tasks(),['100','101','103','104']);
   await selectFilter(p,'developer-status',['Ожидает ревью','Готов']);
   await selectFilter(p,'measure',['Бэкпорт патча','Обновление версии']);assert.deepEqual(await tasks(),['100','101','103']);
   const status=p.locator('#developer-status');await status.locator('summary').click();await status.getByRole('checkbox',{name:'Готов',exact:true}).uncheck();assert.deepEqual(await tasks(),['100']);
   assert.equal(await status.evaluate(el=>el.open),true,'Menu stays open while choosing values');assert.equal(await status.getByRole('checkbox',{name:'Готов',exact:true}).evaluate(el=>el===document.activeElement),true);
   await status.getByRole('checkbox',{name:'Готов',exact:true}).check();await p.keyboard.press('Escape');assert.equal(await status.evaluate(el=>el.open),false);
   await p.locator('.list-card[data-task="100"] input[data-item="branch"][value="ok"]').check();
   await p.locator('#search').fill('Иванов');assert.equal(await p.locator('.list-card').count(),0);await p.locator('#search').fill('');assert.deepEqual(await tasks(),['100','101','103']);
   await selectFilter(p,'dev',['Анна']);assert.deepEqual(await tasks(),['100','103']);await selectFilter(p,'dev',[]);assert.deepEqual(await tasks(),['100','101','102','103']);
   await selectFilter(p,'measure',['Мера не указана',custom]);assert.deepEqual(await tasks(),['104','105']);await selectFilter(p,'measure',[]);assert.equal(await p.locator('.list-card[data-task="100"] input[data-item="branch"][value="ok"]').isChecked(),true);
   for(const width of [1440,1000,901,850,801,800,360]){await p.setViewportSize({width,height:1000});await p.locator('#measure summary').click();const box=await p.locator('#measure .filter-options').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width,'Open menu must fit width '+width);await p.locator('.section-line').click();assert.equal(await p.locator('#measure').evaluate(el=>el.open),false);}
   await p.locator('#csv-file').setInputFiles(input('reset.csv',fixture()));await p.waitForSelector('.list-card');assert.equal(await p.locator('.multi-filter input:checked').count(),0);assert.equal(await p.locator('.list-card').count(),1);
   await p.locator('#csv-file').setInputFiles(input('people.csv',fixture(Array.from({length:45},(_,i)=>({'Task ID':String(200+i),'Разработчик':'Разработчик '+String(i).padStart(2,'0')})))));await p.waitForSelector('.list-card');
   await p.locator('#dev summary').click();await p.locator('#dev').getByRole('checkbox',{name:'Разработчик 44',exact:true}).check();assert.ok(await p.locator('#dev .filter-choices').evaluate(el=>el.scrollTop>0),'Choosing from a long list must preserve menu scroll position');
   console.log('PASS regression: multiselect OR within each filter, AND across filters, keyboard/mobile and review preservation');
  }finally{await p.close();}
 }
 if(only==='all'||only==='measure'){
  const p=await browser.newPage();try{
   const rows=Array.from({length:56},(_,i)=>({'Task ID':String(100+i),'Принятая мера':i<52?(i===0?'Бэкпорт патча':' БЭКПОРТ   ПАТЧА '):i===53?'Особая мера':i===54?'':'Обновление версии','Статус':i===55?'Готов':'Ожидает ревью','Разработчик':i===55?'Петров П.П.':'Иванов И.И.'}));
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('measures.csv',fixture(rows)));await p.waitForSelector('.list-card');
   assert.equal(await p.locator('#measure.multi-filter').count(),1,'Measure filter must be available');
   assert.equal(await p.locator('#severity').count(),0);
   assert.equal(await p.locator('#measure input[type=checkbox]').count(),4,'Case and whitespace variants must share one option');
   await p.locator('[data-action="next-page"]').click();assert.equal(await p.locator('.list-card').count(),6);
   await selectFilter(p,'measure',{label:'Обновление версии'});assert.equal(await p.locator('.list-card').count(),2);assert.equal(await p.locator('.pagination').count(),0);
   await selectFilter(p,'developer-status','готов');await selectFilter(p,'dev','Петров П.П.');await p.locator('#search').fill('CVE-2026-1000');assert.equal(await p.locator('.list-card').count(),1);
   const card=p.locator('.list-card[data-task="155"]');await card.locator('input[data-item="branch"][value="ok"]').check();
   await card.locator('[data-action="problem"]').click();await p.locator('#problem-comment').fill('Проверить версию');await p.locator('#problem-form button[type="submit"]').click();
   await p.locator('[data-action="pool"][data-pool="problem"]').click();assert.equal(await card.count(),1);
   await selectFilter(p,'measure',{label:'Бэкпорт патча'});assert.equal(await p.locator('.list-card').count(),0);
   await selectFilter(p,'measure','');assert.equal(await card.locator('input[data-item="branch"][value="ok"]').isChecked(),true);
   await selectFilter(p,'developer-status','');await selectFilter(p,'dev','');await p.locator('#search').fill('');await p.locator('[data-action="pool"][data-pool="pending"]').click();
   for(const [label,task] of [['Особая мера','153'],['Мера не указана','154']]){await selectFilter(p,'measure',{label});assert.equal(await p.locator('.list-card').count(),1);assert.equal(await p.locator('.list-card').getAttribute('data-task'),task);}
   await selectFilter(p,'measure',{label:'Бэкпорт патча'});assert.equal(await p.locator('.section-line h2 span').innerText(),'52');
   await p.locator('#csv-file').setInputFiles(input('new.csv',fixture()));await p.waitForSelector('.list-card');assert.equal(await p.locator('#measure input:checked').count(),0);assert.equal(await p.locator('.list-card').count(),1);
   console.log('PASS regression: measures replace severity, combine with filters, preserve marks and handle custom/empty values');
  }finally{await p.close();}
 }
 if(only==='all'||only==='copy'){
  const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']}),p=await context.newPage();try{
   const {headers}=require('./helpers.cjs'),extra='  Строка & <текст>\n"кавычки"\t  ';
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('copy.csv',fixture([{'Комментарий':'Комментарий без названия поля',Extra:extra}],';',[...headers,'Extra'])));await p.waitForSelector('.list-card');
   const card=p.locator('.list-card');
   const saved=await p.evaluate(()=>localStorage.getItem('cvereview:workspace:v1'));
   await card.locator('.builds code').first().click();
   await p.waitForFunction(()=>!document.getElementById('toast').hidden,{},{timeout:2000});
   assert.equal(await p.evaluate(()=>navigator.clipboard.readText()),'openssl-3.0.7-1.sl9');
   for(const [selector,value] of [['.package','openssl'],['.cve','CVE-2026-1000'],['.task-id','100'],['.facts dd','Иванов И.И.'],['.dev-note p','Комментарий без названия поля']]){
    await card.locator(selector).first().click();await p.waitForFunction(async text=>await navigator.clipboard.readText()===text,value);
   }
   await card.locator('.raw summary').click();const raw=card.locator('.raw dl>div').filter({has:p.locator('dt',{hasText:/^Extra$/})}).locator('dd');
   await raw.click();await p.waitForFunction(async text=>await navigator.clipboard.readText()===text,extra);
   // Exercise the file-page fallback against the real browser clipboard.
   await p.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined}));
   await card.locator('.builds code').first().focus();await p.keyboard.press('Enter');await p.evaluate(()=>delete navigator.clipboard);
   await p.waitForFunction(async()=>await navigator.clipboard.readText()==='openssl-3.0.7-1.sl9');
   assert.equal(await p.evaluate(()=>localStorage.getItem('cvereview:workspace:v1')),saved,'Copying must not change review state');
   await card.locator('input[data-item="branch"][value="ok"]').check();
   assert.notEqual(await p.evaluate(()=>localStorage.getItem('cvereview:workspace:v1')),saved);assert.equal(await p.evaluate(()=>navigator.clipboard.readText()),'openssl-3.0.7-1.sl9');
   await p.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied');}}});document.execCommand=()=>false;});
   await card.locator('.package').click();await p.waitForFunction(()=>document.getElementById('message').textContent.includes('Не удалось скопировать'));
   console.log('PASS regression: click/keyboard copy exact field values and clipboard fallback');
  }finally{await context.close();}
 }
 if(only==='all'||only==='status'){
  const p=await browser.newPage();try{
   const rows=Array.from({length:56},(_,i)=>({'Task ID':String(100+i),'Статус':i<54?'  ГОТОВ  ':' Ожидает   ревью ','Разработчик':i===0?'Петров П.П.':'Иванов И.И.','Принятая мера':i===1?'Обновление версии':'Бэкпорт патча','Комментарий':i===0?'Unique filtered target':'Патч применён.'}));
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('status.csv',fixture(rows)));await p.waitForSelector('.list-card');
   assert.equal(await p.locator('#developer-status').count(),1,'Developer status filter must be available');
   assert.equal(await p.locator('#developer-status input:checked').count(),0);
   await p.locator('[data-action="next-page"]').click();assert.equal(await p.locator('.list-card').count(),6);
   await selectFilter(p,'developer-status','ожидает ревью');assert.equal(await p.locator('.list-card').count(),2);assert.equal(await p.locator('.pagination').count(),0);
   await p.locator('.list-card[data-task="154"] input[data-item="branch"][value="ok"]').check();
   await selectFilter(p,'developer-status','готов');assert.equal(await p.locator('.list-card').count(),50);
   await selectFilter(p,'dev','Петров П.П.');assert.equal(await p.locator('.list-card').count(),1);
   await selectFilter(p,'measure',{label:'Обновление версии'});assert.equal(await p.locator('.list-card').count(),0);
   await selectFilter(p,'measure','');await p.locator('#search').fill('Unique filtered target');assert.equal(await p.locator('.list-card').count(),1);
   await selectFilter(p,'developer-status','ожидает ревью');assert.equal(await p.locator('.list-card').count(),0);
   await p.locator('#search').fill('');await selectFilter(p,'dev','');assert.equal(await p.locator('.list-card').count(),2);
   const card=p.locator('.list-card[data-task="154"]');assert.equal(await card.locator('input[data-item="branch"][value="ok"]').isChecked(),true);
   await card.locator('[data-action="problem"]').click();await p.locator('#problem-comment').fill('Уточнить патч');await p.locator('#problem-form button[type="submit"]').click();
   await p.locator('[data-action="pool"][data-pool="problem"]').click();assert.equal(await p.locator('.list-card').count(),1);
   await selectFilter(p,'developer-status','готов');assert.equal(await p.locator('.list-card').count(),0);
   await selectFilter(p,'developer-status','');assert.equal(await card.locator('input[data-item="branch"][value="ok"]').isChecked(),true);
   await selectFilter(p,'developer-status','готов');await p.locator('#csv-file').setInputFiles(input('new.csv',fixture()));await p.waitForSelector('.list-card');assert.equal(await p.locator('#developer-status input:checked').count(),0);assert.equal(await p.locator('.list-card').count(),1);
   console.log('PASS regression: developer status combines with filters, resets pagination and preserves review');
  }finally{await p.close();}
 }
 if(only==='all'||only==='search'){
  const p=await browser.newPage();try{
   const {headers}=require('./helpers.cjs');
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('search.csv',fixture([{'SL NVR (latest build)':'special-build-abc','ai_remediation':'special-ai-result',Extra:'Custom search token'},{'Task ID':'101'}],';',[...headers,'Extra'])));await p.waitForSelector('.list-card');
   for(const q of ['special-build-abc','SPECIAL-AI-RESULT','custom search token']){await p.locator('#search').fill(q);assert.equal(await p.locator('.list-card').count(),1);assert.equal(await p.locator('.list-card').first().getAttribute('data-task'),'100');}
   await p.locator('#search').fill('');await p.locator('.list-card[data-task="100"] input[data-item="branch"][value="bad"]').check();
   await p.locator('#search').fill('✕');assert.equal(await p.locator('.list-card').count(),1);
   // This click intentionally removes its own card from the filtered DOM;
   // check() would wait for that now-detached input to remain checked.
   await p.locator('.list-card[data-task="100"] input[data-item="branch"][value="ok"]').click();assert.equal(await p.locator('.list-card').count(),0);
   assert.equal(await p.locator('#search').inputValue(),'✕');
   await p.locator('#search').fill('special-build-abc');assert.equal(await p.locator('.list-card input[data-item="branch"][value="ok"]').isChecked(),true);
   console.log('PASS regression: all-field search updates after checker edits');
  }finally{await p.close();}
 }
 if(only==='all'||only==='tracker'){
  const p=await browser.newPage();try{
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('tracker.csv',fixture()));await p.waitForSelector('.list-card');
   await p.locator('[data-action="settings"]').click();assert.equal(await p.locator('#task-template').inputValue(),'');
   await p.locator('#task-template').fill('https://tracker.test/tasks/{task}');await p.locator('#settings-form button[type="submit"]').click();
   assert.equal(await p.getByRole('link',{name:'Тикет 100',exact:true}).getAttribute('href'),'https://tracker.test/tasks/100');
   await p.locator('[data-action="settings"]').click();await p.locator('#task-template').fill('');await p.locator('#settings-form button[type="submit"]').click();
   assert.equal(await p.getByRole('button',{name:'Тикет 100',exact:true}).isDisabled(),true);
   await p.reload();await p.waitForSelector('.list-card');assert.equal(await p.getByRole('button',{name:'Тикет 100',exact:true}).isDisabled(),true);
   console.log('PASS regression: tracker is configured explicitly and can be cleared');
  }finally{await p.close();}
 }
 if(only==='all'||only==='catalog'){
  const p=await browser.newPage();try{
   const s=M.create(C.parse(fixture(),'legacy.csv'));for(const i of require('../assets/js/checklists.js').forMeasure('Патч из апстрима').items)s.records[0].checks[i.id]='ok';s.records[0].pool='done';
   const data=JSON.parse(M.exportJSON(s)),r=data.records[0];r.checklistVersion=1;r.checklistSnapshot=[{id:'source',label:'Источник патча'},{id:'cve-coverage',label:'Патч закрывает CVE'},{id:'build-inclusion',label:'Применён в сборке'},{id:'regression',label:'Регрессии проверены'}];r.checks=Object.fromEntries(r.checklistSnapshot.map(i=>[i.id,'ok']));
   await p.goto(url);await p.evaluate(cache=>localStorage.setItem('cvereview:workspace:v1',JSON.stringify(cache)),{version:1,csv:fixture(),sourceName:'legacy.csv',encoding:'UTF-8',state:JSON.stringify(data),dirty:false});await p.reload();await p.waitForSelector('.list-card');
   assert.equal(await p.locator('input:checked[value="unseen"]').count(),8);assert.ok((await p.locator('#json-status').innerText()).includes('несохранённые'));await p.locator('.history summary').click();assert.ok((await p.locator('.history').innerText()).includes('Источник патча'));
   console.log('PASS regression: legacy cached checklist migrates without losing old review');
  }finally{await p.close();}
 }
 if(only==='all'||only==='import'){
  const p=await browser.newPage();try{await p.goto(url);await p.locator('#csv-file').setInputFiles(input('race.csv',fixture()));await p.waitForSelector('.list-card');
   const data=JSON.parse(M.exportJSON(M.create(C.parse(fixture(),'race.csv'))));data.records=[];
   await p.evaluate(()=>{const original=File.prototype.text;File.prototype.text=async function(){const result=await original.call(this);if(this.name==='slow.json'){globalThis.readStarted=true;await new Promise(resolve=>{globalThis.finishRead=resolve;});}return result;};});
   await p.locator('#state-file').setInputFiles(input('slow.json',JSON.stringify(data)));await p.waitForFunction(()=>globalThis.readStarted);
   await p.locator('input[data-item="branch"][value="ok"]').check();await p.evaluate(()=>globalThis.finishRead());await p.waitForFunction(()=>document.getElementById('message').textContent.includes('Загружено решений'));
   assert.equal(await p.locator('input[data-item="branch"][value="ok"]').isChecked(),true,'JSON import must preserve edits made during file reading for unmentioned tasks');
   console.log('PASS regression: async import preserves concurrent edits');
  }finally{await p.close();}
 }
 if(only==='all'||only==='performance'){
  const p=await browser.newPage();try{await p.goto(url);await p.locator('#csv-file').setInputFiles(input('large.csv',fixture(Array.from({length:5000},(_,i)=>({'Task ID':String(20000+i)})))));await p.waitForFunction(()=>document.getElementById('csv-diagnostics').textContent.includes('5000'));
   const elapsed=await p.evaluate(()=>{const field=document.getElementById('search');field.value='CVE';const start=performance.now();field.dispatchEvent(new Event('input',{bubbles:true}));return performance.now()-start;});
   assert.ok(elapsed<2000,`Search must stay responsive on 5000 rows; synchronous processing took ${elapsed.toFixed(0)}ms`);assert.equal(await p.locator('.list-card').count(),50);console.log('PASS regression: 5000-row search',Math.round(elapsed)+'ms');
  }finally{await p.close();}
 }
 if(only==='all'||only==='date'){
  const p=await browser.newPage();try{await p.goto(url);await p.locator('#csv-file').setInputFiles(input('dates.csv',fixture([{'End date':'2026-02-30'},{'Task ID':'101','End date':'2026-03-01'}])));await p.waitForSelector('.list-card');await p.locator('#order').selectOption('end');assert.equal(await p.locator('.list-card').first().getAttribute('data-task'),'101','Impossible ISO date must sort after valid dates');console.log('PASS regression: invalid calendar date sorts last');}finally{await p.close();}
 }
}
module.exports=run;
if(require.main===module){const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');(async()=>{const b=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{}),args:['--no-sandbox']});try{await run(b,process.argv[2]);}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});}
