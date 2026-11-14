(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory(require('./csv.js'),require('./checklists.js'),require('./links.js'));else(root.CR=root.CR||{}).model=factory(root.CR.csv,root.CR.checklists,root.CR.links);})(globalThis,function(csv,checklists,links){
 'use strict';
 const STATES=['unseen','ok','bad'],POOLS=['pending','problem','done'];
 const BASIS=['dev','status','start','end','measure','p','d','sl','rh','fixdate','rstate','severity','cvss','rhsa','comment','ai_nvr','ai_verdict','ai_confidence','ai_remediation','ai_run'];
 const clone=v=>JSON.parse(JSON.stringify(v)),now=()=>new Date().toISOString();
 const profile=row=>checklists.forMeasure(row.measure);
 function date(v){const s=String(v??'').trim(),m=/^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s.*)?$/.exec(s),iso=m?`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`:s.slice(0,10);const d=new Date(iso+'T00:00:00Z');return /^\d{4}-\d{2}-\d{2}$/.test(iso)&&Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===iso?iso:s;}
 function basis(row){return Object.fromEntries(BASIS.map(key=>{let v=String(row[key]??'').trim();if(['start','end','fixdate','ai_run'].includes(key))v=date(v);if(['dev','status','measure','severity','rstate'].includes(key))v=csv.norm(v);return [key,v];}));}
 const sameBasis=(a,b)=>BASIS.every(k=>a?.[k]===b?.[k]);
 const complete=(r,p)=>p.items.every(i=>r.checks[i.id]==='ok'||r.checks[i.id]==='bad');
 function fresh(row){const p=profile(row);return {key:csv.keyOf(row),identity:csv.identity(row),basisVersion:1,basis:basis(row),checklistId:p.id,checklistVersion:p.version,checklistSnapshot:p.items.map(({id,label})=>({id,label})),checks:Object.fromEntries(p.items.map(i=>[i.id,'unseen'])),pool:'pending',reviewComment:'',updatedAt:now(),needsRecheck:false,previousReview:null};}
 function reconcile(row,old){
  const next=fresh(row);if(!old)return next;
  if(old.basisVersion===1&&sameBasis(next.basis,old.basis)&&next.checklistId===old.checklistId&&next.checklistVersion===old.checklistVersion)return {...clone(old),key:next.key};
  const untouched=old.needsRecheck&&Object.values(old.checks).every(v=>v==='unseen')&&!old.reviewComment;
  const previous=untouched&&old.previousReview?clone(old.previousReview):snapshot(old);
  return {...next,needsRecheck:true,previousReview:previous};
 }
 function snapshot(record){const {previousReview,key,...previous}=record;return clone(previous);}
 function create(table,previous=null){
  const records=new Map((previous?.records||[]).map(r=>[r.key,clone(r)]));
  for(const row of table.rows.filter(csv.eligible))records.set(csv.keyOf(row),reconcile(row,records.get(csv.keyOf(row))));
  return {table,records:[...records.values()],settings:{taskTemplate:links.DEFAULT_TASK,repoTemplate:'',release:'',...previous?.settings},dirty:Boolean(previous?.dirty||previous),updatedAt:now()};
 }
 function change(session,key,fn){const record=session.records.find(r=>r.key===key);if(!record)throw Error('Задача не найдена.');const next=fn(clone(record));return {...session,records:session.records.map(r=>r.key===key?{...next,updatedAt:now()}:r),dirty:true,updatedAt:now()};}
 function setCheck(session,key,item,value){return change(session,key,r=>{const row=session.table.rows.find(row=>csv.keyOf(row)===key),p=row&&profile(row);if(r.pool==='done')throw Error('Сначала верните задачу на ревью.');if(!p||!p.items.some(i=>i.id===item)||!STATES.includes(value))throw Error('Неверный пункт или состояние проверки.');r.checks[item]=value;return r;});}
 function decide(session,key,pool,comment){
  if(!POOLS.includes(pool))throw Error('Неизвестный пул.');
  return change(session,key,r=>{const row=session.table.rows.find(row=>csv.keyOf(row)===key);if(!row||!csv.eligible(row))throw Error('Задача не входит в активный пул.');if(pool==='done'&&!complete(r,profile(row)))throw Error('Отметьте каждый пункт чеклиста.');if(comment!==undefined){if(typeof comment!=='string')throw Error('Комментарий должен быть текстом.');r.reviewComment=comment.trim();}if(pool==='problem'&&!r.reviewComment.trim())throw Error('Опишите проблему в комментарии.');r.pool=pool;if(pool==='done')r.needsRecheck=false;return r;});
 }
 const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
 const fail=message=>{throw Error('Некорректное состояние JSON: '+message);};
 function validateRecord(raw,historical=false){
  if(!object(raw)||!object(raw.identity))fail('нет идентичности задачи.');
  const identity={};for(const k of ['task','cve','component']){if(typeof raw.identity[k]!=='string'||!raw.identity[k].trim())fail('пустой идентификатор.');identity[k]=raw.identity[k].trim();}identity.cve=identity.cve.toUpperCase();
  if(!Number.isInteger(raw.basisVersion)||raw.basisVersion<1||!object(raw.basis)||!BASIS.every(k=>typeof raw.basis[k]==='string'))fail('неверный контекст строки.');
  if(typeof raw.checklistId!=='string'||!Number.isInteger(raw.checklistVersion)||raw.checklistVersion<1)fail('неверный профиль чеклиста.');
  if(!Array.isArray(raw.checklistSnapshot)||!raw.checklistSnapshot.length||!raw.checklistSnapshot.every(i=>object(i)&&typeof i.id==='string'&&i.id&&typeof i.label==='string'))fail('нет снимка чеклиста.');
  const ids=raw.checklistSnapshot.map(i=>i.id);if(new Set(ids).size!==ids.length||!object(raw.checks)||Object.keys(raw.checks).length!==ids.length||!ids.every(id=>Object.hasOwn(raw.checks,id)&&STATES.includes(raw.checks[id])))fail('неверные пункты проверок.');
  const p=checklists.byId(raw.checklistId);if(p&&p.version===raw.checklistVersion&&(p.items.length!==ids.length||!p.items.every(i=>ids.includes(i.id))))fail('пункты не соответствуют профилю.');
  if(!POOLS.includes(raw.pool)||typeof raw.reviewComment!=='string'||typeof raw.updatedAt!=='string'||!Number.isFinite(Date.parse(raw.updatedAt))||typeof raw.needsRecheck!=='boolean')fail('неверный результат ревью.');
  if(raw.pool==='done'&&!ids.every(i=>raw.checks[i]!=='unseen'))fail('ревью завершено с непроверенными пунктами.');
  if(raw.pool==='problem'&&!raw.reviewComment.trim())fail('проблема без комментария.');
  const result={key:JSON.stringify([identity.task,identity.cve,identity.component]),identity,basisVersion:raw.basisVersion,basis:Object.fromEntries(BASIS.map(k=>[k,raw.basis[k]])),checklistId:raw.checklistId,checklistVersion:raw.checklistVersion,checklistSnapshot:raw.checklistSnapshot.map(i=>({id:i.id,label:i.label})),checks:Object.fromEntries(ids.map(i=>[i,raw.checks[i]])),pool:raw.pool,reviewComment:raw.reviewComment,updatedAt:raw.updatedAt,needsRecheck:raw.needsRecheck,previousReview:null};
  if(!historical&&raw.previousReview){result.previousReview=snapshot(validateRecord(raw.previousReview,true));if(JSON.stringify(result.previousReview.identity)!==JSON.stringify(identity))fail('история относится к другой задаче.');}
  return result;
 }
 function settingsFrom(raw){if(!object(raw))fail('нет настроек.');const result={};for(const name of ['taskTemplate','repoTemplate','release']){if(typeof raw[name]!=='string')fail('неверные настройки.');result[name]=raw[name];}if(result.taskTemplate)links.validateTemplate(result.taskTemplate);if(result.repoTemplate)links.validateTemplate(result.repoTemplate);return result;}
 function importJSON(session,text){
  let data;try{data=JSON.parse(text);}catch{fail('файл не разбирается.');}
  if(!object(data)||data.app!=='cvereview'||data.schemaVersion!==1)fail('неподдерживаемая схема или другой тип файла.');
  if(typeof data.sourceName!=='string'||typeof data.savedAt!=='string'||!Number.isFinite(Date.parse(data.savedAt))||!Array.isArray(data.records))fail('нет метаданных/записей.');
  const settings=settingsFrom(data.settings),incoming=data.records.map(r=>validateRecord(r)),seen=new Set();for(const r of incoming){if(seen.has(r.key))fail('дубликат идентичности.');seen.add(r.key);}
  const merged=new Map(session.records.map(r=>[r.key,r]));for(const r of incoming)merged.set(r.key,r);
  const next=create(session.table,{...session,settings,records:[...merged.values()]}),active=new Set(session.table.rows.filter(csv.eligible).map(csv.keyOf));
  return {session:{...next,dirty:true},summary:{loaded:incoming.length,matched:incoming.filter(r=>active.has(r.key)).length,archived:incoming.filter(r=>!active.has(r.key)).length,recheck:next.records.filter(r=>active.has(r.key)&&r.needsRecheck).length}};
 }
 function exportJSON(session){return JSON.stringify({app:'cvereview',schemaVersion:1,savedAt:now(),sourceName:session.table.sourceName,settings:session.settings,records:session.records.map(({key,...r})=>r)},null,2);}
 return {create,setCheck,decide,importJSON,exportJSON,profile,complete,basis,date,BASIS};
});
