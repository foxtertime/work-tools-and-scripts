(function(root,factory){
 if(typeof module==='object'&&module.exports)module.exports=factory(require('../checklists.json'));
 else(root.CR=root.CR||{}).checklists=factory(root.CR.checklistDefinitions);
})(globalThis,function(definitions){
 'use strict';
 const norm=v=>String(v??'').trim().replace(/\s+/g,' ').toLowerCase();
 function createCatalog(data){
  if(data?.schemaVersion!==1||!Array.isArray(data.profiles)||!data.profiles.length)throw Error('Некорректный справочник чеклистов.');
  const profileIds=new Set(),measures=new Map();
  const profiles=data.profiles.map(raw=>{
   if(!raw||typeof raw.id!=='string'||!/^[-a-z0-9]+$/.test(raw.id)||profileIds.has(raw.id)||['unknown','unspecified'].includes(raw.id)||!Number.isInteger(raw.version)||raw.version<1||typeof raw.label!=='string'||!raw.label.trim()||!Array.isArray(raw.measures)||!raw.measures.length||!Array.isArray(raw.items)||!raw.items.length)throw Error('Некорректный профиль чеклиста.');
   profileIds.add(raw.id);const ids=new Set();
   const items=raw.items.map(i=>{
    if(!i||typeof i.id!=='string'||!/^[-a-z0-9]+$/.test(i.id)||ids.has(i.id)||typeof i.label!=='string'||!i.label.trim()||typeof i.description!=='string'||!i.description.trim())throw Error('Некорректный или повторяющийся ID пункта чеклиста.');
    ids.add(i.id);return {id:i.id,label:i.label,description:i.description};
   });
   return {id:raw.id,version:raw.version,label:raw.label,measures:[...raw.measures],items,warning:''};
  });
  for(const p of profiles)for(const value of p.measures){
   if(typeof value!=='string'||!norm(value))throw Error('Пустая мера в справочнике.');
   const key=norm(value);if(measures.has(key)&&measures.get(key)!==p)throw Error('Одна мера соответствует разным чеклистам: '+value);
   measures.set(key,p);
  }
  const fallback=profiles.find(p=>p.id==='other')?.items||[{id:'comment',label:'Комментарий добавлен',description:'В задаче оставлен комментарий.'},{id:'task-closure',label:'Задача закрыта корректно',description:'Проверена корректность закрытия задачи.'}];
  for(const id of ['unknown','unspecified'])profiles.push({id,label:id==='unknown'?'Общий чеклист':'Мера не указана',version:2,measures:[],items:fallback.map(i=>({...i})),warning:id==='unknown'?'Нет специального чеклиста для этой меры.':'Принятая мера не указана.'});
  return {profiles,byId:id=>profiles.find(p=>p.id===id)||null,forMeasure:value=>{const key=norm(value);return measures.get(key)||profiles.find(p=>p.id===(!key||['-','—'].includes(key)?'unspecified':'unknown'));}};
 }
 return {...createCatalog(definitions),createCatalog};
});
