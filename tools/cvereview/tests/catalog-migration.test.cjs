const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../assets/js/csv.js'),P=require('../assets/js/checklists.js'),M=require('../assets/js/model.js'),{fixture}=require('./helpers.cjs');
const key='["100","CVE-2026-1000","openssl"]',record=s=>s.records.find(r=>r.key===key);
const table=()=>C.parse(fixture(),'review.csv');
function done(){let s=M.create(table());for(const item of P.forMeasure('Патч из апстрима').items)s=M.setCheck(s,key,item.id,'ok');return M.decide(s,key,'done');}
function modelWith(items,version=P.forMeasure('Патч из апстрима').version){
 const base=P.forMeasure('Патч из апстрима');
 const config={schemaVersion:1,profiles:[{...structuredClone(base),measures:['Патч из апстрима'],items,version}]};
 const catalog=P.createCatalog(config),context={module:{exports:{}},require:name=>name==='./checklists.js'?catalog:require('../assets/js/'+name.slice(2))};
 vm.runInNewContext(fs.readFileSync(require.resolve('../assets/js/model.js'),'utf8'),context);return context.module.exports;
}
test('label edits and reorder preserve marks by ID, including after JSON import',()=>{
 const old=done(),items=P.forMeasure('Патч из апстрима').items.map(i=>({...i,label:'Новая формулировка: '+i.label})).reverse(),m=modelWith(items);
 const next=m.importJSON(m.create(table()),M.exportJSON(old)).session;
 assert.equal(record(next).pool,'done');assert.ok(Object.values(record(next).checks).every(v=>v==='ok'));
 assert.equal(record(next).checklistSnapshot[0].label,items[0].label);
});
test('an added check starts unseen and reopens done; existing marks and old snapshot survive',()=>{
 const old=done(),items=[...P.forMeasure('Патч из апстрима').items,{id:'new-proof',label:'Новая проверка',description:'Проверить новое подтверждение'}],m=modelWith(items);
 const next=m.importJSON(m.create(table()),M.exportJSON(old)).session,r=record(next);
 assert.equal(r.pool,'pending');assert.equal(r.checks['new-proof'],'unseen');assert.equal(r.checks.branch,'ok');assert.equal(r.needsRecheck,true);
 assert.equal(r.previousReview.pool,'done');assert.equal(r.previousReview.checklistSnapshot.length,items.length-1);
 assert.throws(()=>m.decide(next,key,'done'));
});
test('deleting a check keeps completed remaining checks and records the removed result in history',()=>{
 const old=done(),items=P.forMeasure('Патч из апстрима').items.filter(i=>i.id!=='branch'),m=modelWith(items,P.forMeasure('Патч из апстрима').version+1);
 const next=m.importJSON(m.create(table()),M.exportJSON(old)).session,r=record(next);
 assert.equal(r.pool,'done');assert.equal(Object.hasOwn(r.checks,'branch'),false);assert.equal(r.previousReview.checks.branch,'ok');assert.equal(r.needsRecheck,false);
});
test('new semantic ID never inherits a removed check result by position or caption',()=>{
 const old=done(),items=P.forMeasure('Патч из апстрима').items.map((i,n)=>n?i:{...i,id:'branch-v2'}),m=modelWith(items);
 const r=record(m.importJSON(m.create(table()),M.exportJSON(old)).session);assert.equal(r.checks['branch-v2'],'unseen');assert.equal(Object.hasOwn(r.checks,'branch'),false);assert.equal(r.previousReview.checks.branch,'ok');
});
test('another CSV update does not overwrite meaningful history with blank newly added checks',()=>{
 const old=done(),items=[...P.forMeasure('Патч из апстрима').items,{id:'new-proof',label:'Новая проверка',description:'Проверить'}],m=modelWith(items);
 const first=m.importJSON(m.create(table()),M.exportJSON(old)).session,next=m.create(table(),first);
 assert.equal(record(next).checks['new-proof'],'unseen');assert.equal(record(next).previousReview.pool,'done');assert.equal(record(next).checks.branch,'ok');
});
test('legacy four-item JSON remains readable and becomes history for the new backport list',()=>{
 const data=JSON.parse(M.exportJSON(done())),r=data.records[0];
 r.checklistVersion=1;r.checklistSnapshot=[{id:'source',label:'Источник патча'},{id:'cve-coverage',label:'Патч закрывает CVE'},{id:'build-inclusion',label:'Применён в сборке'},{id:'regression',label:'Регрессии проверены'}];
 r.checks=Object.fromEntries(r.checklistSnapshot.map(i=>[i.id,'ok']));
 const next=M.importJSON(M.create(table()),JSON.stringify(data)).session;
 assert.equal(record(next).pool,'pending');assert.equal(Object.keys(record(next).checks).length,8);assert.ok(Object.values(record(next).checks).every(v=>v==='unseen'));assert.equal(record(next).previousReview.checks.source,'ok');
 assert.equal(M.importJSON(M.create(table()),M.exportJSON(next)).session.records[0].previousReview.checks.source,'ok');
});
test('self-consistent incomplete snapshot cannot bypass newly required checks',()=>{
 const data=JSON.parse(M.exportJSON(done())),r=data.records[0];r.checklistSnapshot=r.checklistSnapshot.filter(i=>i.id!=='branch');delete r.checks.branch;
 const next=M.importJSON(M.create(table()),JSON.stringify(data)).session;assert.equal(record(next).checks.branch,'unseen');assert.equal(record(next).pool,'pending');assert.throws(()=>M.decide(next,key,'done'));
});
test('add, mark bad, then remove keeps the removed result in exported history',()=>{
 const original=done(),items=P.forMeasure('Патч из апстрима').items;
 const expanded=modelWith([...items,{id:'new-proof',label:'Новая проверка',description:'Проверить новое подтверждение'}]);
 let s=expanded.importJSON(expanded.create(table()),M.exportJSON(original)).session;
 s=expanded.setCheck(s,key,'new-proof','bad');
 const reduced=modelWith(items),next=reduced.importJSON(reduced.create(table()),expanded.exportJSON(s)).session;
 assert.equal(Object.hasOwn(record(next).checks,'new-proof'),false);
 assert.equal(record(next).previousReview.checks['new-proof'],'bad');
 assert.equal(record(next).previousReview.checklistSnapshot.at(-1).label,'Новая проверка');
 const restored=reduced.importJSON(reduced.create(table()),reduced.exportJSON(next)).session;
 assert.equal(record(restored).previousReview.checks['new-proof'],'bad');
});
