const {test}=require('node:test');const assert=require('node:assert/strict');let l;try{l=require('../assets/js/links.js');}catch{l={};}
test('task URLs and encoded template parts are preserved; GitLab needs setup',()=>{const r={task:'https://tracker.test/t/1',component:'a/b & c',cve:'CVE-2026-1000',rhsa:'',link:''};let links=l.forRow(r,{});assert.equal(links.find(i=>i.id==='task').url,r.task);assert.equal(links.find(i=>i.id==='repo').url,null);links=l.forRow(r,{repoTemplate:'https://git.test/rpms/{component}'});assert.equal(links.find(i=>i.id==='repo').url,'https://git.test/rpms/a%2Fb%20%26%20c');});
test('CVE fallback and RHSA only for a valid supplied URL',()=>{const r={task:'100',component:'openssl',cve:'CVE-2026-1000',link:'',rhsa:'https://access.redhat.com/errata/RHSA-2026:99999'};assert.equal(l.forRow(r,{}).find(i=>i.id==='rhsa').url,r.rhsa);assert.equal(l.forRow(r,{}).find(i=>i.id==='cve').url,'https://access.redhat.com/security/cve/CVE-2026-1000');for(const v of ['', '-', '—','javascript:alert(1)'])assert.ok(!l.forRow({...r,rhsa:v},{}).some(i=>i.id==='rhsa'));});
test('unsafe protocols, relative URLs and malformed templates cannot become links',()=>{for(const v of ['javascript:alert(1)','data:text/html,x','file:///tmp/x','//example.com','https://','https://ok.test/\nfoo'])assert.equal(l.safeURL(v),null);assert.throws(()=>l.validateTemplate('javascript:{task}'));assert.throws(()=>l.validateTemplate('https://a.test/{typo}'));assert.equal(l.validateTemplate('https://a.test/{task}'),'https://a.test/{task}');});
test('numeric task IDs need an explicit tracker setting and clearing it disables the link',()=>{
 const row={task:'100',component:'openssl',cve:'CVE-2026-1000',rhsa:'',link:''};
 assert.equal(l.forRow(row,{}).find(i=>i.id==='task').url,null);
 assert.equal(l.forRow(row,{taskTemplate:'https://tracker.test/tasks/{task}'}).find(i=>i.id==='task').url,'https://tracker.test/tasks/100');
 const cleared=l.forRow(row,{taskTemplate:''}).find(i=>i.id==='task');assert.equal(cleared.url,null);assert.ok(cleared.reason.includes('тасктрекера'));
});
test('RHSA link shows the full advisory ID from plain and encoded URL paths',()=>{
 const row={task:'100',component:'openssl',cve:'CVE-2026-1000',link:''};
 for(const [url,label] of [
  ['https://access.redhat.com/errata/RHSA-2026:99999','RHSA-2026:99999'],
  ['https://access.redhat.com/errata/rhsa-2025%3A01234?view=full#details','RHSA-2025:01234'],
  ['https://access.redhat.com/errata/unknown','RHSA'],
  ['https://access.redhat.com/errata/%invalid','RHSA']
 ]){
  const link=l.forRow({...row,rhsa:url}).find(i=>i.id==='rhsa');
  assert.equal(link.label,label);assert.equal(link.url,url);
 }
});
