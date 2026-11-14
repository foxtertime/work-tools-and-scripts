const {test}=require('node:test');const assert=require('node:assert/strict');const c=require('../assets/js/checklists.js');
test('user measure names and legacy aliases select the intended variable-length lists',()=>{
 const cases=[['Бэкпорт патча','upstream-patch',8],['Обновление версии','version-import',9],['Тэгирование билда','build-tag',5],['Ребилд','dependency-rebuild',6],['Собственный патч','custom-patch',8],['Восстановление патча','patch-restore',2],['Неприменимо','not-applicable',3],['Устранено ранее','already-fixed',4],['Неприменимо ранее','previously-not-applicable',4],['Устранение не планируется','wont-fix',2],['Другое','other',2]];
 for(const [name,id,count] of cases){const p=c.forMeasure(name);assert.equal(p.id,id);assert.equal(p.items.length,count);assert.equal(new Set(p.items.map(i=>i.id)).size,count);assert.ok(p.items.every(i=>i.label&&i.description));}
 assert.equal(c.forMeasure(' ПАТЧ  из\nапстрима ').id,'upstream-patch');assert.equal(c.forMeasure('Патч из прошлой ветки').id,'upstream-patch');assert.equal(c.forMeasure('Импорт новой версии').id,'version-import');
});
test('unknown and unspecified measures remain explicit instead of guessing',()=>{assert.equal(c.forMeasure('Пропатчено').id,'unknown');assert.ok(c.forMeasure('Пропатчено').warning);assert.equal(c.forMeasure('-').id,'unspecified');assert.ok(c.forMeasure('').warning);assert.equal(c.byId('no-such-profile'),null);});
test('non-applicability only asks for AI evidence, comment and task closure',()=>{assert.deepEqual(c.forMeasure('Неприменимо').items.map(i=>i.id),['ai-verdict','comment','task-closure']);});
test('editable catalog rejects ambiguous aliases and duplicate item IDs',()=>{
 const profile={id:'test',version:1,label:'Test',measures:['Test'],items:[{id:'one',label:'One',description:'Inspect one'}]};
 assert.throws(()=>c.createCatalog({schemaVersion:1,profiles:[{...profile,items:[...profile.items,...profile.items]}]}));
 assert.throws(()=>c.createCatalog({schemaVersion:1,profiles:[profile,{...profile,id:'second',label:'Other',measures:['test']}]}));
});
