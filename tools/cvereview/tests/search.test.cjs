const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../assets/js/csv.js'),P=require('../assets/js/checklists.js'),M=require('../assets/js/model.js'),{fixture,headers}=require('./helpers.cjs');
let search;try{search=require('../assets/js/search.js');}catch{search={};}
const row=changes=>C.parse(fixture([changes])).rows[0];
test('search covers every CSV value, including custom columns and multiline fields',()=>{
 const changes=Object.fromEntries(headers.map((h,i)=>[h,'unique-field-'+i]));
 changes['Разработчик']='Иванов И.И.';changes['Статус']='Готов';changes['CVE ID']='CVE-2026-1000';
 const r=C.parse(fixture([{...changes,Extra:'Extra marker\nwith spaces'}],';',[...headers,'Extra'])).rows[0],index=search.index(r,{},P.forMeasure(r.measure));
 for(let i=0;i<headers.length;i++)if(!['Разработчик','Статус','CVE ID'].includes(headers[i]))assert.equal(search.matches(index,'UNIQUE-FIELD-'+i),true,headers[i]);
 assert.equal(search.matches(index,'extra marker with   spaces'),true);assert.equal(search.matches(index,'несуществующая строка'),false);
});
test('source values stay searchable without requiring expanded details',()=>{
 const r=row({'SL NVR (latest build)':'openssl-3.2.7-44.sl9','RHEL NVR (if fixed)':'openssl-3.2.7-45.el9','Advisory (RHSA)':'https://access.redhat.com/errata/RHSA-2026:55555','ai_remediation':'Unique AI remediation','Task state':'Tracker-CLOSED','End date':'15.11.2026'}),index=search.index(r,{},P.forMeasure(r.measure));
 for(const value of ['3.2.7-44.sl9','45.el9','55555','AI REMEDIATION','tracker-closed','15.11.2026'])assert.equal(search.matches(index,value),true,value);
});
test('review comment, canonical profile, checker labels and marked states are searchable',()=>{
 const r=row({}),s=M.create(C.parse(fixture())).records[0],p=P.forMeasure(r.measure);
 s.reviewComment='Заменить spec-файл';s.checks.branch='bad';
 const index=search.index(r,s,p);
 for(const q of ['заменить SPEC-файл','Бэкпорт патча','Ветка выбрана верно','✕','bad'])assert.equal(search.matches(index,q),true,q);
 s.checks.branch='ok';assert.equal(search.matches(search.index(r,s,p),'✕'),false);
});
test('previous review values and deleted checker labels remain discoverable',()=>{
 const r=row({}),s=M.create(C.parse(fixture())).records[0];s.previousReview={pool:'problem',basis:{sl:'old-build-123'},reviewComment:'Старое замечание',checklistSnapshot:[{id:'deleted-proof',label:'Удалённая проверка'}],checks:{'deleted-proof':'bad'},updatedAt:'2026-11-15T00:00:00Z'};
 const index=search.index(r,s,P.forMeasure(r.measure));for(const q of ['old-build-123','старое замечание','удалённая проверка'])assert.equal(search.matches(index,q),true);
});
test('empty query matches and column headers do not cause every row to match',()=>{
 const r=row({}),index=search.index(r,{},P.forMeasure(r.measure));assert.equal(search.matches(index,'  '),true);assert.equal(search.matches(index,'SL NVR (latest build)'),false);
});
