(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else(root.CR=root.CR||{}).links=factory();})(globalThis,function(){
 'use strict';
 function safeURL(value){const text=String(value??'').trim();if(!/^https?:\/\//i.test(text)||/[\u0000-\u001f\u007f]/.test(text))return null;try{const u=new URL(text);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
 function validateTemplate(value){const text=String(value??'').trim();if(/\{(?!task\}|component\}|cve\})/.test(text)||!safeURL(text.replace(/\{(task|component|cve)\}/g,'example')))throw Error('Нужен HTTP(S)-шаблон с {task}, {component} или {cve}.');return text;}
 function expand(template,r){return safeURL(String(template).replace(/\{(task|component|cve)\}/g,(_,k)=>encodeURIComponent(r[k])));}
 function forRow(r,settings={}){
  const taskURL=safeURL(r.task)||(settings.taskTemplate?expand(settings.taskTemplate,r):null),repoURL=settings.repoTemplate?expand(settings.repoTemplate,r):null;
  const out=[{id:'task',label:'Тикет '+r.task,url:taskURL,reason:'Настройте ссылку тасктрекера'},{id:'repo',label:'GitLab',url:repoURL,reason:'Настройте ссылку GitLab'},{id:'cve',label:'CVE',url:safeURL(r.link)||safeURL('https://access.redhat.com/security/cve/'+encodeURIComponent(r.cve))}];
  const rhsa=safeURL(r.rhsa);if(rhsa){
   let label='RHSA';try{label=decodeURIComponent(new URL(rhsa).pathname).match(/RHSA-\d{4}:\d+/i)?.[0].toUpperCase()||label;}catch{}
   out.push({id:'rhsa',label,url:rhsa});
  }return out;
 }
 return {safeURL,validateTemplate,forRow};
});
