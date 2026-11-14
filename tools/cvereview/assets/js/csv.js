(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else(root.CR=root.CR||{}).csv=factory();})(globalThis,function(){
 'use strict';
 const FIELDS={dev:'Разработчик',status:'Статус',start:'Start date',end:'End date',measure:'Принятая мера',task:'Task ID',cve:'CVE ID',taskstate:'Task state',taskdate:'Task date',executor:'Исполнитель',component:'Компонент',p:'P',d:'D',sl:'SL NVR (latest build)',rh:'RHEL NVR (if fixed)',fixdate:'Fix date',rstate:'RHEL state',severity:'RHEL severity',cvss:'RHEL CVSS',rhsa:'Advisory (RHSA)',link:'CVE link',ai_nvr:'ai_nvr',ai_verdict:'ai_verdict',ai_confidence:'ai_confidence',ai_remediation:'ai_remediation',ai_run:'ai_run',comment:'Комментарий'};
 const REQUIRED=['task','cve','component','dev','status'];
 const norm=v=>String(v??'').trim().replace(/\s+/g,' ').toLowerCase();
 const value=v=>['-','—'].includes(String(v??'').trim())?'':String(v??'').trim();
 const identity=r=>({task:r.task.trim(),cve:r.cve.trim().toUpperCase(),component:r.component.trim()});
 const keyOf=r=>{const i=identity(r);return JSON.stringify([i.task,i.cve,i.component]);};
 const eligible=r=>Boolean(r.dev)&&norm(r.dev)!=='secops'&&['ожидает ревью','готов'].includes(norm(r.status));
 function decode(bytes){
  if(bytes.includes(0)||bytes[0]===255&&bytes[1]===254||bytes[0]===254&&bytes[1]===255)throw Error('Нужен CSV в UTF-8 или Windows-1251, не XLSX/UTF-16.');
  try{return {text:new TextDecoder('utf-8',{fatal:true}).decode(bytes),encoding:'UTF-8'};}
  catch{return {text:new TextDecoder('windows-1251',{fatal:true}).decode(bytes),encoding:'Windows-1251'};}
 }
 function records(text,sep){
  const out=[];let row=[],cell='',quoted=false,closed=false;
  for(let i=0;i<text.length;i++){
   const ch=text[i];
   if(quoted){if(ch==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=ch;continue;}
   if(ch===sep){row.push(cell);cell='';closed=false;continue;}
   if(ch==='\n'||ch==='\r'){row.push(cell);out.push(row);row=[];cell='';closed=false;if(ch==='\r'&&text[i+1]==='\n')i++;continue;}
   if(closed){if(ch===' '||ch==='\t'&&sep!=='\t')continue;throw Error('Некорректные символы после закрывающей кавычки.');}
   if(ch==='"'){if(cell!=='')throw Error('Кавычка внутри поля без экранирования.');quoted=true;}else cell+=ch;
  }
  if(quoted)throw Error('Незакрытая кавычка в CSV.');
  if(cell!==''||row.length||closed){row.push(cell);out.push(row);}
  return out;
 }
 function parse(text,sourceName=''){
  if(typeof text!=='string'||text.includes('\0'))throw Error('Файл не является текстовым CSV.');
  text=text.replace(/^\ufeff/,'');let best=null,lastError=null;
  for(const delimiter of [';',',','\t']){try{const parsed=records(text,delimiter);const at=parsed.findIndex(r=>r.some(c=>norm(c)==='cve id'));if(at>=0&&(!best||parsed[at].length>best.headers.length))best={parsed,at,delimiter,headers:parsed[at]};}catch(e){lastError=e;}}
  if(!best)throw Error(lastError?.message||'Не найдена шапка с колонкой CVE ID.');
  const {headers,parsed,at,delimiter}=best,index=new Map(),duplicates=[];
  headers.forEach((h,i)=>{const name=norm(h);if(index.has(name))duplicates.push(h);else index.set(name,i);});
  const missing=Object.entries(FIELDS).filter(([,h])=>!index.has(norm(h))).map(([key])=>key);
  const absent=REQUIRED.filter(k=>missing.includes(k));if(absent.length)throw Error('Нет обязательных колонок: '+absent.map(k=>FIELDS[k]).join(', '));
  const diagnostics={read:0,skipped:[],duplicates,merged:0,missing:missing.map(k=>FIELDS[k]),excluded:0},rows=[],seen=new Map();
  for(let i=at+1;i<parsed.length;i++){
   const cells=parsed[i];if(!cells.some(c=>c.trim()))continue;
   if(cells.length>headers.length&&cells.slice(headers.length).some(c=>c.trim()))throw Error(`В записи ${i+1} больше непустых полей, чем колонок в шапке. Проверьте разделители и кавычки.`);
   diagnostics.read++;
   const r={record:i+1,raw:headers.map((name,j)=>({name,value:cells[j]??''}))};
   for(const [key,name] of Object.entries(FIELDS))r[key]=value(cells[index.get(norm(name))]);
   r.cve=r.cve.toUpperCase();if(!r.task||!r.cve||!r.component){diagnostics.skipped.push(i+1);continue;}
   const key=keyOf(r),canonical=JSON.stringify(Object.keys(FIELDS).map(k=>r[k]).concat(r.raw.map(c=>value(c.value))));
   if(seen.has(key)){const previous=seen.get(key);if(previous.canonical!==canonical)throw Error(`Конфликт дубликатов ${r.task} / ${r.cve} / ${r.component}: записи ${previous.record} и ${i+1}.`);diagnostics.merged++;continue;}
   seen.set(key,{canonical,record:r.record});rows.push(r);if(!eligible(r))diagnostics.excluded++;
  }
  return {sourceName,headers:[...headers],rows,diagnostics,delimiter,encoding:'текст'};
 }
 function read(bytes,sourceName){const decoded=decode(bytes);return {...parse(decoded.text,sourceName),encoding:decoded.encoding,text:decoded.text};}
 return {FIELDS,REQUIRED,norm,value,identity,keyOf,eligible,decode,parse,read};
});
