(function(root,factory){
 if(typeof module==='object'&&module.exports)module.exports=factory();
 else(root.CR=root.CR||{}).search=factory();
})(globalThis,function(){
 'use strict';
 const normalize=value=>String(value??'').toLowerCase().replace(/\s+/g,' ').trim();
 const poolNames={pending:'На ревью',problem:'Проблемы',done:'Проверено'};
 const stateNames={unseen:'□ не смотрелось',ok:'✓ ок',bad:'✕ не ок'};
 function index(row,record={},profile={}){
  const values=[];
  const add=value=>{if(typeof value==='string'||typeof value==='number')values.push(normalize(value));};
  // Raw values include optional and unknown CSV columns. Normalized values
  // also cover what is shown in the card without requiring details to open.
  for(const field of row.raw||[])add(field.value);
  for(const value of Object.values(row))add(value);
  add(profile.label);add(record.reviewComment);add(record.updatedAt);add(poolNames[record.pool]);
  if(record.needsRecheck)add('Изменилось после ревью — требуется повторная проверка');
  function checks(items,states){
   for(const item of items||[]){add(item.label);const state=states?.[item.id]||'unseen';add(stateNames[state]);add(state);}
  }
  checks(profile.items,record.checks);
  const previous=record.previousReview;
  if(previous){
   for(const value of Object.values(previous.basis||{}))add(value);
   add(previous.reviewComment);add(previous.updatedAt);add(poolNames[previous.pool]);
   checks(previous.checklistSnapshot,previous.checks);
  }
  return [...new Set(values.filter(Boolean))].join('\n');
 }
 const matches=(text,query)=>{const needle=normalize(query);return !needle||text.includes(needle);};
 return {normalize,index,matches};
});
