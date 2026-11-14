const assert=require('node:assert/strict'),path=require('node:path');const {pathToFileURL}=require('node:url');const {fixture}=require('./helpers.cjs');
const C=require('../assets/js/csv.js'),M=require('../assets/js/model.js');
const url=pathToFileURL(path.resolve(__dirname,'../cvereview.html')).href;
const input=(name,text)=>({name,mimeType:name.endsWith('.csv')?'text/csv':'application/json',buffer:Buffer.from(text)});
async function run(browser,only='all'){
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
   const rows=Array.from({length:56},(_,i)=>({'Task ID':String(100+i),'Статус':i<54?'  ГОТОВ  ':' Ожидает   ревью ','Разработчик':i===0?'Петров П.П.':'Иванов И.И.','RHEL severity':i===1?'Low':'Important','Комментарий':i===0?'Unique filtered target':'Патч применён.'}));
   await p.goto(url);await p.locator('#csv-file').setInputFiles(input('status.csv',fixture(rows)));await p.waitForSelector('.list-card');
   assert.equal(await p.locator('#developer-status').count(),1,'Developer status filter must be available');
   assert.equal(await p.locator('#developer-status').inputValue(),'');
   await p.locator('[data-action="next-page"]').click();assert.equal(await p.locator('.list-card').count(),6);
   await p.locator('#developer-status').selectOption('ожидает ревью');assert.equal(await p.locator('.list-card').count(),2);assert.equal(await p.locator('.pagination').count(),0);
   await p.locator('.list-card[data-task="154"] input[data-item="branch"][value="ok"]').check();
   await p.locator('#developer-status').selectOption('готов');assert.equal(await p.locator('.list-card').count(),50);
   await p.locator('#dev').selectOption('Петров П.П.');assert.equal(await p.locator('.list-card').count(),1);
   await p.locator('#severity').selectOption('Low');assert.equal(await p.locator('.list-card').count(),0);
   await p.locator('#severity').selectOption('');await p.locator('#search').fill('Unique filtered target');assert.equal(await p.locator('.list-card').count(),1);
   await p.locator('#developer-status').selectOption('ожидает ревью');assert.equal(await p.locator('.list-card').count(),0);
   await p.locator('#search').fill('');await p.locator('#dev').selectOption('');assert.equal(await p.locator('.list-card').count(),2);
   const card=p.locator('.list-card[data-task="154"]');assert.equal(await card.locator('input[data-item="branch"][value="ok"]').isChecked(),true);
   await card.locator('[data-action="problem"]').click();await p.locator('#problem-comment').fill('Уточнить патч');await p.locator('#problem-form button[type="submit"]').click();
   await p.locator('[data-action="pool"][data-pool="problem"]').click();assert.equal(await p.locator('.list-card').count(),1);
   await p.locator('#developer-status').selectOption('готов');assert.equal(await p.locator('.list-card').count(),0);
   await p.locator('#developer-status').selectOption('');assert.equal(await card.locator('input[data-item="branch"][value="ok"]').isChecked(),true);
   await p.locator('#developer-status').selectOption('готов');await p.locator('#csv-file').setInputFiles(input('new.csv',fixture()));await p.waitForSelector('.list-card');assert.equal(await p.locator('#developer-status').inputValue(),'');assert.equal(await p.locator('.list-card').count(),1);
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
  const p=await browser.newPage();try{await p.goto(url);await p.locator('#csv-file').setInputFiles(input('dates.csv',fixture([{'End date':'2026-02-30'},{'Task ID':'101','End date':'2026-03-01'}])));await p.waitForSelector('.list-card');await p.locator('#order').selectOption('oldest');assert.equal(await p.locator('.list-card').first().getAttribute('data-task'),'101','Impossible ISO date must sort after valid dates');console.log('PASS regression: invalid calendar date sorts last');}finally{await p.close();}
 }
}
module.exports=run;
if(require.main===module){const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');(async()=>{const b=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{}),args:['--no-sandbox']});try{await run(b,process.argv[2]);}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});}
