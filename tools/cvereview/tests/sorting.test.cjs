const {test}=require('node:test'),assert=require('node:assert/strict');
let sorting;try{sorting=require('../assets/js/sorting.js');}catch{sorting={};}
const item=(task,fields={})=>({row:{task:String(task),cve:'CVE-2026-1000',component:'openssl',...fields},record:{pool:'pending'}});
const ids=items=>items.map(i=>i.row.task);
test('submission and creation dates sort chronologically in either direction across supported formats',()=>{
 for(const key of ['end','taskdate']){
  const rows=[item(1,{[key]:'03.11.2026'}),item(2,{[key]:'2026-02-28T12:30:00Z'}),item(3,{[key]:'1.12.2025'})];
  assert.deepEqual(ids(sorting.sortItems(rows,key,'asc')),['3','2','1']);
  assert.deepEqual(ids(sorting.sortItems(rows,key,'desc')),['1','2','3']);
 }
});
test('blank and impossible dates stay last for both directions, including leap-year rules',()=>{
 const rows=[item(1,{end:''}),item(2,{end:'2026-02-30'}),item(3,{end:'2024-02-29'}),item(4,{end:'29.02.2026'}),item(5,{end:'2026-03-01'})];
 assert.deepEqual(ids(sorting.sortItems(rows,'end','asc')),['3','5','1','2','4']);
 assert.deepEqual(ids(sorting.sortItems(rows,'end','desc')),['5','3','1','2','4']);
});
test('developer, measure, component and status use natural Russian text order and keep missing values last',()=>{
 for(const key of ['dev','measure','component','status']){
  const rows=[item(100,{[key]:'Борис'}),item(10,{[key]:'  Анна  '}),item(2,{[key]:'анна'}),item(4,{[key]:''})];
  assert.deepEqual(ids(sorting.sortItems(rows,key,'asc')),['2','10','100','4']);
  assert.deepEqual(ids(sorting.sortItems(rows,key,'desc')),['100','2','10','4']);
 }
});
test('task IDs and CVEs compare embedded numbers rather than individual digits',()=>{
 const rows=[item(10,{cve:'CVE-2026-10000'}),item(2,{cve:'CVE-2026-9999'}),item(100,{cve:'CVE-2026-10001'})];
 for(const key of ['task','cve']){
  assert.deepEqual(ids(sorting.sortItems(rows,key,'asc')),['2','10','100']);
  assert.deepEqual(ids(sorting.sortItems(rows,key,'desc')),['100','10','2']);
 }
});
test('severity uses risk levels then CVSS, with unrecognized severity last in either direction',()=>{
 const rows=[item(1,{severity:'Critical',cvss:'9,8'}),item(2,{severity:'Low',cvss:'3'}),item(3,{severity:' critical ',cvss:'10'}),item(4,{severity:'Unknown',cvss:'10'}),item(5,{severity:'Important',cvss:'8'})];
 assert.deepEqual(ids(sorting.sortItems(rows,'severity','desc')),['3','1','5','2','4']);
 assert.deepEqual(ids(sorting.sortItems(rows,'severity','asc')),['2','5','1','3','4']);
});
test('missing or invalid CVSS does not act as zero, while actual zero remains a valid score',()=>{
 const rows=[item(1,{severity:'Low',cvss:''}),item(2,{severity:'Low',cvss:'0'}),item(3,{severity:'Low',cvss:'2'}),item(4,{severity:'Low',cvss:'-1'}),item(5,{severity:'Low',cvss:'11'})];
 assert.deepEqual(ids(sorting.sortItems(rows,'severity','asc')),['2','3','1','4','5']);
 assert.deepEqual(ids(sorting.sortItems(rows,'severity','desc')),['3','2','1','4','5']);
});
test('equal values have deterministic task/CVE/component tie breaks without mutating records or input order',()=>{
 const rows=[item(10,{dev:'Анна'}),item(2,{dev:'Анна',cve:'CVE-2026-10000'}),item(2,{dev:'Анна',cve:'CVE-2026-9999'})],before=JSON.stringify(rows);
 const sorted=sorting.sortItems(rows,'dev','desc');assert.deepEqual(sorted.map(i=>i.row.cve),['CVE-2026-9999','CVE-2026-10000','CVE-2026-1000']);
 assert.deepEqual(sorting.sortItems([...rows].reverse(),'dev','desc'),sorted);assert.equal(JSON.stringify(rows),before);assert.equal(sorted[0],rows[2]);
});
