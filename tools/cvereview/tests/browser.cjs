/* Development-only: PLAYWRIGHT_MODULE=/path/to/playwright node tests/browser.cjs */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {fixture}=require('./helpers.cjs');const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const html=path.resolve(__dirname,'../cvereview.html');
const input=(name,text)=>({name,mimeType:name.endsWith('.csv')?'text/csv':'application/json',buffer:Buffer.from(text)});
const initial=fixture([{'Advisory (RHSA)':'https://access.redhat.com/errata/RHSA-2026:99999','Комментарий':'<img src=x onerror="globalThis.injected=1">'}, {'Task ID':'101','Компонент':'kernel','Принятая мера':'Обоснована неприменимость'},{'Task ID':'102','Статус':'Готов','Принятая мера':'Импорт новой версии'},{'Task ID':'103','Разработчик':'SecOps','Статус':'Готов'},{'Task ID':'104','Статус':'В работе'}]);
(async()=>{
 assert.ok(fs.existsSync(html),'Standalone cvereview.html must exist');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{}),args:['--no-sandbox']});
 try{
  const context=await browser.newContext({acceptDownloads:true,viewport:{width:1440,height:1100}});const page=await context.newPage(),errors=[],network=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url());});
  await page.goto(pathToFileURL(html).href);assert.equal(await page.locator('.list-card').count(),0);assert.equal(await page.locator('#save-state').isDisabled(),true);
  await page.locator('#csv-file').setInputFiles(input('vulnsheet.csv',initial));await page.waitForSelector('.list-card');
  const card=()=>page.locator('.list-card[data-task="100"]');
  assert.equal(await page.locator('.list-card').count(),3);assert.ok((await page.locator('#csv-diagnostics').innerText()).includes('5'));assert.equal(await page.evaluate(()=>globalThis.injected),undefined);assert.equal(await card().locator('.dev-note img').count(),0);
  assert.equal(await card().getByRole('link',{name:'RHSA',exact:true}).count(),1);assert.equal(await card().locator('[data-action="done"]').isDisabled(),true);assert.ok((await page.locator('.list-card[data-task="101"] .review-checklist').innerText()).includes('AI подтверждает неприменимость'));
  for(const el of await card().locator('input[value="ok"]').all())await el.check();assert.equal(await card().locator('[data-action="done"]').isEnabled(),true);
  await card().locator('input[data-item="branch"][value="bad"]').check();assert.equal(await card().locator('[data-action="done"]').isEnabled(),true);await card().locator('input[data-item="branch"][value="unseen"]').check();assert.equal(await card().locator('[data-action="done"]').isDisabled(),true);await card().locator('input[data-item="branch"][value="ok"]').check();
  await card().locator('[data-action="problem"]').click();await page.locator('#problem-comment').fill('   ');await page.locator('#problem-form button[type="submit"]').click();assert.equal(await page.locator('#problem-dialog').evaluate(e=>e.open),true);
  await page.locator('#problem-comment').fill('Проверить spec.');await page.locator('#problem-form button[type="submit"]').click();assert.equal(await page.locator('.list-card').count(),2);await page.locator('[data-action="pool"][data-pool="problem"]').click();assert.ok((await card().innerText()).includes('Проверить spec.'));
  await card().locator('[data-action="pending"]').click();await page.locator('[data-action="pool"][data-pool="pending"]').click();await card().locator('[data-action="done"]').click();assert.equal(await card().count(),0);await page.locator('[data-action="undo"]').click();assert.equal(await card().locator('input:checked[value="ok"]').count(),8);
  const downloadEvent=page.waitForEvent('download');await page.locator('#save-state').click();const download=await downloadEvent,stream=await download.createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);const stateText=Buffer.concat(chunks).toString(),exported=JSON.parse(stateText);assert.equal(exported.app,'cvereview');assert.equal(exported.records.find(r=>r.identity.task==='100').checks.branch,'ok');
  await page.locator('#csv-file').setInputFiles(input('bad.csv','not a CSV'));await page.waitForFunction(()=>document.getElementById('message').textContent.includes('шапк'));assert.equal(await page.locator('.list-card').count(),3);
  const invalid=structuredClone(exported);invalid.schemaVersion=99;await page.locator('#state-file').setInputFiles(input('bad.json',JSON.stringify(invalid)));await page.waitForFunction(()=>document.getElementById('message').textContent.includes('схем'));assert.equal(await card().locator('input:checked[value="ok"]').count(),8);
  await page.reload();await page.waitForSelector('.list-card');assert.equal(await card().locator('input:checked[value="ok"]').count(),8);
  await page.locator('#csv-file').setInputFiles(input('updated.csv',initial.replace('openssl-3.0.7-1.sl9','openssl-3.0.7-2.sl9')));await page.waitForFunction(()=>document.querySelector('.recheck-notice'));assert.equal(await card().locator('input:checked[value="unseen"]').count(),8);assert.ok((await card().innerText()).includes('Изменилось после ревью'));
  await page.locator('#state-file').setInputFiles(input('review.json',stateText));await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Загружено'));assert.equal(await card().locator('input:checked[value="unseen"]').count(),8);
  await page.locator('#search').fill('kernel');assert.equal(await page.locator('.list-card').count(),1);await page.locator('#search').fill('');
  for(const width of [1440,1000,901,900,650,390,360]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'overflow at '+width);}
  await page.setViewportSize({width:1440,height:1100});
  const many=fixture(Array.from({length:65},(_,i)=>({'Task ID':String(200+i)})));await page.locator('#csv-file').setInputFiles(input('many.csv',many));await page.waitForFunction(()=>document.querySelectorAll('.list-card').length===50);await page.locator('[data-action="next-page"]').click();assert.equal(await page.locator('.list-card').count(),15);
  const denied=await browser.newContext();await denied.addInitScript(()=>{Storage.prototype.setItem=function(){throw new Error('denied');};});const p=await denied.newPage();await p.goto(pathToFileURL(html).href);await p.locator('#csv-file').setInputFiles(input('x.csv',initial));await p.waitForSelector('.list-card');assert.ok((await p.locator('#storage-status').innerText()).includes('недоступ'));assert.equal(await p.locator('#save-state').isEnabled(),true);await denied.close();
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);console.log('PASS browser: CSV/JSON, state, profiles, tri-state/undo, stale review, injection, cache failure, pagination, mobile, offline');
  await require('./review-regressions.cjs')(browser);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
