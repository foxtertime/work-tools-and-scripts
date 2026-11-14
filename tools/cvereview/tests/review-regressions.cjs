const assert=require('node:assert/strict'),path=require('node:path');const {pathToFileURL}=require('node:url');const {fixture}=require('./helpers.cjs');
const C=require('../assets/js/csv.js'),M=require('../assets/js/model.js');
const url=pathToFileURL(path.resolve(__dirname,'../cvereview.html')).href;
const input=(name,text)=>({name,mimeType:name.endsWith('.csv')?'text/csv':'application/json',buffer:Buffer.from(text)});
async function run(browser,only='all'){
 if(only==='all'||only==='import'){
  const p=await browser.newPage();try{await p.goto(url);await p.locator('#csv-file').setInputFiles(input('race.csv',fixture()));await p.waitForSelector('.list-card');
   const data=JSON.parse(M.exportJSON(M.create(C.parse(fixture(),'race.csv'))));data.records=[];
   await p.evaluate(()=>{const original=File.prototype.text;File.prototype.text=async function(){const result=await original.call(this);if(this.name==='slow.json'){globalThis.readStarted=true;await new Promise(resolve=>{globalThis.finishRead=resolve;});}return result;};});
   await p.locator('#state-file').setInputFiles(input('slow.json',JSON.stringify(data)));await p.waitForFunction(()=>globalThis.readStarted);
   await p.locator('input[data-item="source"][value="ok"]').check();await p.evaluate(()=>globalThis.finishRead());await p.waitForFunction(()=>document.getElementById('message').textContent.includes('Загружено решений'));
   assert.equal(await p.locator('input[data-item="source"][value="ok"]').isChecked(),true,'JSON import must preserve edits made during file reading for unmentioned tasks');
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
