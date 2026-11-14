const {test}=require('node:test');const assert=require('node:assert/strict');
const {fixture,headers}=require('./helpers.cjs');
let csv;try{csv=require('../assets/js/csv.js');}catch{csv={};}
test('quoted separators, escaped quotes, multiline and a pre-header preserve raw cells',()=>{
 const t=csv.parse('Группа;Релиз\r\n'+fixture([{'Комментарий':'a; "цитата"\r\nстрока <script>x</script>'}]),'a.csv');
 assert.equal(t.rows[0].comment,'a; "цитата"\r\nстрока <script>x</script>');assert.equal(t.rows[0].record,3);assert.equal(t.headers.length,27);assert.equal(t.rows[0].cvss,'8.1');
});
test('comma, tab, BOM, reordered headers and empty trailing columns',()=>{for(const sep of [',','\t',';']){const t=csv.parse('\ufeff'+fixture([{}],sep,[...headers].reverse())+'\r\n');assert.equal(t.delimiter,sep);assert.equal(t.rows[0].task,'100');assert.equal(t.rows[0].rh,'');}});
test('strict UTF8 fallback decodes cp1251 and rejects binary or malformed CSV',()=>{
 assert.equal(csv.decode(new Uint8Array([0xcf,0xf0,0xe8,0xe2,0xe5,0xf2])).text,'Привет');
 assert.equal(csv.read(new TextEncoder().encode(fixture()),'x.csv').sourceName,'x.csv');
 for(const s of ['x;y','CVE ID;Task ID\n"unfinished','\0abc'])assert.throws(()=>csv.parse(s));
 assert.throws(()=>csv.decode(new Uint8Array([255,254,0,0])));
});
test('eligibility includes both developer statuses but excludes SecOps and other statuses',()=>{
 const t=csv.parse(fixture([{}, {'Task ID':'101','Статус':' ГОТОВ '},{'Task ID':'102','Разработчик':' sEcOps ','Статус':'Готов'},{'Task ID':'103','Статус':'В работе'},{'Task ID':'104','Разработчик':'-'}]));
 assert.deepEqual(t.rows.filter(csv.eligible).map(r=>r.task),['100','101']);
});
test('tuple identity survives ordering and prevents collisions across CVEs and components',()=>{
 const t=csv.parse(fixture([{}, {'CVE ID':'cve-2026-1001'},{'Компонент':'libssl'}]));
 assert.equal(csv.keyOf(t.rows[0]),'["100","CVE-2026-1000","openssl"]');assert.equal(new Set(t.rows.map(csv.keyOf)).size,3);
});
test('identical duplicates deduplicate, conflicting duplicates reject, missing identity skips',()=>{
 assert.equal(csv.parse(fixture([{},{}])).rows.length,1);
 assert.throws(()=>csv.parse(fixture([{}, {'Комментарий':'Другие данные'}])),/дубликат|конфликт/i);
 assert.equal(csv.parse(fixture([{'Task ID':'-'}])).rows.length,0);
});
test('required column errors and extra columns produce actionable results',()=>{
 assert.throws(()=>csv.parse(fixture([{}],';',headers.filter(h=>h!=='Разработчик'))),/Разработчик/);
 const t=csv.parse(fixture([{'Extra':'abc'}],';',[...headers,'Extra']));assert.equal(t.rows[0].raw.at(-1).value,'abc');
});
