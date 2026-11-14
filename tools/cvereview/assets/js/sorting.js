(function(root,factory){
 if(typeof module==='object'&&module.exports)module.exports=factory(require('./model.js'));
 else(root.CR=root.CR||{}).sorting=factory(root.CR.model);
})(globalThis,function(model){
 'use strict';
 const fields=[
  {key:'severity',label:'По критичности',type:'severity',defaultDirection:'desc'},
  {key:'end',label:'По дате сдачи',type:'date',defaultDirection:'asc'},
  {key:'taskdate',label:'По дате создания',type:'date',defaultDirection:'asc'},
  {key:'dev',label:'По разработчику',type:'text',defaultDirection:'asc'},
  {key:'measure',label:'По принятой мере',type:'text',defaultDirection:'asc'},
  {key:'component',label:'По компоненту',type:'text',defaultDirection:'asc'},
  {key:'task',label:'По номеру задачи',type:'number',defaultDirection:'asc'},
  {key:'cve',label:'По CVE',type:'number',defaultDirection:'asc'},
  {key:'status',label:'По статусу',type:'text',defaultDirection:'asc'}
 ];
 const field=key=>fields.find(f=>f.key===key)||fields[0];
 const collator=new Intl.Collator('ru',{numeric:true,sensitivity:'base'});
 const ranks=new Map([['critical',4],['important',3],['moderate',2],['low',1]]);
 const text=value=>{const v=String(value??'').trim().replace(/\s+/g,' ');return !v||['-','—'].includes(v)?null:v;};
 function date(value){
  const v=model.date(value),d=new Date(v+'T00:00:00Z');
  return /^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===v?v:null;
 }
 function score(value){const v=text(value),n=Number(v?.replace(',','.'));return v!==null&&Number.isFinite(n)&&n>=0&&n<=10?n:null;}
 function compare(a,b,direction){
  if(a===null||b===null)return a===b?0:a===null?1:-1;
  return (typeof a==='number'?a-b:collator.compare(a,b))*(direction==='desc'?-1:1);
 }
 function tie(a,b){
  for(const key of ['task','cve','component']){const result=collator.compare(String(a[key]??''),String(b[key]??''));if(result)return result;}
  const left=JSON.stringify([a.task,a.cve,a.component]),right=JSON.stringify([b.task,b.cve,b.component]);return left<right?-1:left>right?1:0;
 }
 function sortItems(items,key='severity',direction){
  const f=field(key),dir=['asc','desc'].includes(direction)?direction:f.defaultDirection;
  const prepared=items.map(item=>{
   const row=item.row;let value=text(row[f.key]);
   if(f.type==='date')value=date(row[f.key]);
   if(f.type==='severity')value=ranks.get(String(row.severity??'').trim().toLowerCase())??null;
   return {item,value,cvss:f.type==='severity'?score(row.cvss):null};
  });
  prepared.sort((a,b)=>compare(a.value,b.value,dir)||(f.type==='severity'?compare(a.cvss,b.cvss,dir):0)||tie(a.item.row,b.item.row));
  return prepared.map(i=>i.item);
 }
 function directionLabel(key,direction){const type=field(key).type,desc=direction==='desc';return type==='date'?(desc?'Новые → старые':'Старые → новые'):type==='severity'?(desc?'Высокая → низкая':'Низкая → высокая'):type==='number'?(desc?'По убыванию':'По возрастанию'):(desc?'Я → А':'А → Я');}
 return {fields,field,sortItems,directionLabel};
});
