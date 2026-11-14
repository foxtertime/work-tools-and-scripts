/* Throwaway UI spike. All vulnerability and build data below are fictional. */
const variant = Number(document.body.dataset.variant);
const icons = {
  check:'<path d="m5 12 4 4L19 6"/>', alert:'<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v4m0 3v.2"/>',
  arrow:'<path d="M7 17 17 7M7 7h10v10"/>', search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  git:'<circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10m0-5c8 0 12 0 12-4"/>',
  inbox:'<path d="m5 4-3 10v6h20v-6L19 4H5Z"/><path d="M2 14h6l2 3h4l2-3h6"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  back:'<path d="M9 4 3 10l6 6M3 10h11a7 7 0 0 1 7 7"/>', settings:'<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', close:'<path d="m6 6 12 12M6 18 18 6"/>',
  users:'<circle cx="9" cy="7" r="4"/><path d="M2 21v-3a7 7 0 0 1 14 0v3M17 3a4 4 0 0 1 0 8m2 3a6 6 0 0 1 3 5v2"/>',
  focus:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="4"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.arrow}</svg>`;
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = ['Карточки', 'Входящие', 'Доска', 'Фокус', 'По разработчикам'];
const files = ['01-cards.html','02-inbox.html','03-board.html','04-focus.html','05-team.html'];
const descriptions = ['Весь контекст — в карточке. Выбирайте любую задачу из очереди.', 'Очередь под рукой. Детали выбранной задачи — на большом экране.', 'Видно движение задач и то, что ждёт доработки.', 'Одна задача. Весь контекст. Одно решение.', 'Ревью решений команды, сгруппированных по разработчикам.'];
// Fictional advisories, like the rest of the prototype data.
const demoAdvisories = {openssl:'https://access.redhat.com/errata/RHSA-2026:99901',curl:'https://access.redhat.com/errata/RHSA-2026:99902'};
const seed = [
  ['openssl','CVE-2026-10421','48101','А. Морозов','Critical',9.1,'Пропатчено','3.0.7-46.sl9','3.0.7-49.el9',true,false,'Перенесён патч из апстрима, добавлена проверка границы буфера.','10.11.2026'],
  ['curl','CVE-2026-10862','48124','М. Волкова','Important',8.1,'Обновлено','7.76.1-31.sl9','7.76.1-33.el9',false,true,'Обновлена версия пакета. Проверены HTTP/2 и работа через прокси.','11.11.2026'],
  ['libxml2','CVE-2026-11307','48137','И. Соколов','Important',7.8,'Пропатчено','2.9.13-7.sl9','2.9.13-8.el9',true,false,'Бэкпорт исправления парсера. Приложен минимальный reproducer.','11.11.2026'],
  ['kernel','CVE-2026-11954','48145','А. Морозов','Important',7.0,'Не затронуто','5.14.0-503.sl9','—',false,false,'Уязвимый модуль отключён в конфигурации целевого ядра.','12.11.2026'],
  ['python3','CVE-2026-12018','48152','Е. Лебедева','Moderate',6.5,'Пропатчено','3.9.21-2.sl9','3.9.21-3.el9',true,false,'Добавлена валидация входных данных и regression test.','12.11.2026'],
  ['sqlite','CVE-2026-12379','48168','М. Волкова','Moderate',5.5,'Обновлено','3.34.1-8.sl9','3.34.1-9.el9',false,true,'Обновление до исправленного релиза, smoke-тесты пройдены.','13.11.2026'],
  ['zlib','CVE-2026-12410','48173','И. Соколов','Moderate',5.3,'Пропатчено','1.2.11-42.sl9','1.2.11-43.el9',true,false,'Перенесено исправление обработки повреждённого архива.','13.11.2026'],
  ['libarchive','CVE-2026-12506','48182','Е. Лебедева','Important',7.5,'Пропатчено','3.5.3-5.sl9','3.5.3-6.el9',true,false,'Патч приложен, сборка готова.','13.11.2026','problem','В PATCH есть исправление, но в spec-файле нет его применения. Добавить и пересобрать пакет.'],
  ['expat','CVE-2026-12588','48193','А. Морозов','Moderate',6.1,'Не затронуто','2.5.0-4.sl9','—',false,false,'Проверен уязвимый путь исполнения.','13.11.2026','problem','Нужно приложить обоснование: какой именно код недостижим в нашей конфигурации.'],
  ['nghttp2','CVE-2026-12601','48204','И. Соколов','Moderate',5.9,'Обновлено','1.43.0-7.sl9','1.43.0-8.el9',false,true,'Исправленная версия, тесты HTTP/2 пройдены.','13.11.2026','done'],
  ['systemd','CVE-2026-12700','48211',' SecOps ','Low',3.1,'Закрыто SecOps','252-46.sl9','—',false,false,'Задача SecOps для демонстрации исключения.','13.11.2026'],
  ['tar','CVE-2026-12708','48215','М. Волкова','Low',3.3,'Другое','1.34-8.sl9','—',false,false,'Задача ещё в работе.','13.11.2026','work']
].map((a,i) => ({id:String(i),component:a[0],cve:a[1],task:a[2],rhsa:demoAdvisories[a[0]] || '',dev:a[3],severity:a[4],cvss:a[5],measure:a[6],sl:a[7],rh:a[8],p:a[9],d:a[10],comment:a[11],end:a[12],pool:a[13] || 'pending',reviewComment:a[14] || '',status:a[13] === 'work' ? 'В работе' : 'Ожидает ревью'}));
const eligible = seed.filter(r => r.dev.trim().toLowerCase() !== 'secops' && r.status === 'Ожидает ревью');
const reviewChecks = [
  {key:'measure',label:'Мера обоснована',hint:'Принятая мера соответствует уязвимости и нашей конфигурации.'},
  {key:'changes',label:'Изменения проверены',hint:'Проверены патч, обновление версии или обоснование «не затронуто».'},
  {key:'build',label:'Сборка проверена',hint:'Нужные изменения входят в указанный билд пакета.'},
  {key:'tests',label:'Проверки / тесты',hint:'Результаты тестов или проверок подтверждают принятое решение.'},
];
function withChecks(r) {
  if(variant !== 1)return {...r};
  return {...r,checks:Object.fromEntries(reviewChecks.map(check=>[check.key,
    [-1,0,1].includes(r.checks?.[check.key])?r.checks[check.key]:(r.pool === 'done'?1:0)]))};
}
const reviewComplete = r => reviewChecks.every(check=>[-1,1].includes(r.checks?.[check.key]));
const storageKey = `cvereview-ui-spike-v1-${variant}`;
let storageAvailable = true;
const read = (key,fallback) => { try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { storageAvailable = false; return fallback; } };
let saved = read(storageKey, {});
let links = read('cvereview-ui-links-v1', {task:'https://tracker.example.internal/task/{task}',repo:'https://gitlab.example.internal/rpms/{component}'});
let rows = eligible.map(r => withChecks({...r,...(['pending','problem','done'].includes(saved[r.id]?.pool) ? saved[r.id] : {})}));
let pool = 'pending', query = '', dev = '', severity = '', order = 'severity', selected = null, undo = null;
const poolNames = {pending:'На ревью',problem:'Проблемы',done:'Ревьювед'};
const poolIcons = {pending:'inbox',problem:'alert',done:'check'};
const counts = () => Object.fromEntries(Object.keys(poolNames).map(p => [p, rows.filter(r=>r.pool === p).length]));
const persist = () => {try { localStorage.setItem(storageKey, JSON.stringify(Object.fromEntries(rows.map(r=>[r.id,{pool:r.pool,reviewComment:r.reviewComment,...(variant === 1?{checks:r.checks}:{})}]))));} catch { storageAvailable = false; }};
const initials = name => name.replaceAll('.','').split(' ').filter(Boolean).map(s=>s[0]).join('').slice(0,2);
const btn = (label, action, id, type='', ic='') => `<button class="btn ${type}" data-action="${action}" ${id != null ? `data-id="${id}"` : ''}>${ic ? icon(ic) : ''}${label}</button>`;
function external(url,label,ic='arrow') { return `<a class="btn link-btn" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${icon(ic)}${label}${icon('arrow')}</a>`; }
function makeURL(template,r) { const result = String(template).replace(/\{(task|component|cve)\}/g, (_,k)=>encodeURIComponent(r[k])); try {const u = new URL(result); return ['http:','https:'].includes(u.protocol) ? u.href : '#';} catch {return '#';} }
function actions(r) { return `<div class="actions">${r.pool !== 'done' ? btn('Ревьювед','done',r.id,'primary','check') : ''}${r.pool === 'pending' ? btn('Есть проблема','problem',r.id,'danger-outline','alert') : btn('Вернуть на ревью','pending',r.id,'','back')}${r.pool === 'problem' ? btn('Комментарий','problem',r.id,'quiet') : ''}</div>`; }
function badges(r) { return `<span class="badge severity ${r.severity.toLowerCase()}">${r.severity} <b>${r.cvss.toFixed(1)}</b></span><span class="badge measure">${esc(r.measure)}</span>`; }
function advisoryLink(value) {
  const url=String(value ?? '').trim();
  if(!/^https?:\/\//i.test(url))return '';
  try {new URL(url);} catch {return '';}
  return external(url,'RHSA');
}
function rowLinks(r) {return `<div class="links">${external(makeURL(links.task,r),'Тикет '+r.task)}${external(makeURL(links.repo,r),'GitLab','git')}${external('https://access.redhat.com/security/cve/'+r.cve,'CVE')}${advisoryLink(r.rhsa)}</div>`;}
const field = (label,value) => `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`;
function rawFields(r) {
  const fields = [['Разработчик',r.dev],['Статус',r.status],['Start date','09.11.2026'],['End date',r.end],['Принятая мера',r.measure],['Task ID',r.task],['CVE ID',r.cve],['Task state','In progress'],['Task date','06.11.2026'],['Исполнитель',r.dev],['Компонент',r.component],['P',r.p?'+':'-'],['D',r.d?'+':'-'],['SL NVR (latest build)',r.sl],['RHEL NVR (if fixed)',r.rh],['Fix date',r.rh === '—'?'—':'02.11.2026'],['RHEL state',r.rh === '—'?'Affected':'Fixed'],['RHEL severity',r.severity],['RHEL CVSS',r.cvss],['Advisory (RHSA)',r.rhsa || '—'],['CVE link','https://access.redhat.com/security/cve/'+r.cve],['ai_nvr',r.sl],['ai_verdict','—'],['ai_confidence','—'],['ai_remediation','—'],['ai_run','—'],['Комментарий',r.comment]];
  return `<details class="raw"><summary>Все 27 полей строки vulnsheet</summary><dl>${fields.map(([k,v])=>field(k,v)).join('')}</dl></details>`;
}
function context(r,full=false) { return `<div class="context"><dl class="facts">${field('Разработчик',r.dev)}${field('Передано на ревью',r.end)}${field('Статус разработчика',r.status)}${field('RHEL state',r.rh === '—'?'Affected':'Fixed')}</dl><div class="builds"><div><span class="label">SL · последний билд</span><code>${esc(r.sl)}</code></div><div><span class="label">RHEL · исправлено в</span><code>${esc(r.rh)}</code></div></div><div class="signals"><span class="signal ${r.p?'positive':''}" title="P: патч под CVE найден в PATCH коммита сборки">P ${r.p?'+':'−'} <span>${r.p?'Патч найден':'Нет подтверждения патча'}</span></span><span class="signal ${r.d?'positive':''}" title="D: апстрим-версия вне известных уязвимых диапазонов">D ${r.d?'+':'−'} <span>${r.d?'Вне диапазона':'Нет подтверждения по версии'}</span></span></div><div class="dev-note"><span class="label">Комментарий разработчика</span><p>${esc(r.comment)}</p></div>${r.reviewComment ? `<div class="review-note"><span class="label">Замечание ревьювера</span><p>${esc(r.reviewComment)}</p></div>` : ''}${full ? rawFields(r) : `<details class="more"><summary>Подробности строки</summary>${rawFields(r)}</details>`}</div>`; }
function card(r,compact=false) { return `<article class="task-card ${compact?'compact':''}" data-card="${r.id}"><div class="card-heading"><span class="package">${esc(r.component)}</span><span class="task-id mono">#${r.task}</span></div><h3 class="cve mono">${r.cve}</h3><div class="badges">${badges(r)}</div>${compact ? `<div class="compact-meta"><span>${esc(r.dev)}</span><span>${r.end}</span></div><p class="compact-note">${esc(r.comment)}</p>${r.reviewComment?`<div class="review-note"><span class="label">Замечание ревьювера</span><p>${esc(r.reviewComment)}</p></div>`:''}<details class="more"><summary>Контекст и поля строки</summary>${context(r,true)}</details>`:context(r)}${rowLinks(r)}${actions(r)}</article>`; }
function pools(vertical=false) {const c=counts();return `<nav class="pools ${vertical?'vertical':''}" aria-label="Пулы ревью">${Object.keys(poolNames).map(p=>`<button class="pool ${pool === p?'active':''} ${p}" data-action="pool" data-pool="${p}" ${pool === p?'aria-current="page"':''}>${icon(poolIcons[p])}<span>${poolNames[p]}</span><b>${c[p]}</b></button>`).join('')}</nav>`;}
function listCard(r) {
  return `<article class="task-card list-card" data-card="${r.id}">
    <div class="list-card-main">
    <div class="list-card-heading"><span class="package">${esc(r.component)}</span><h3 class="cve mono">${r.cve}</h3><div class="badges">${badges(r)}</div><span class="list-date">${icon('clock')}${r.end}</span><span class="task-id mono">#${r.task}</span></div>
    <div class="list-card-body">
      <dl class="facts">${field('Разработчик',r.dev)}${field('Статус разработчика',r.status)}${field('RHEL state',r.rh === '—'?'Affected':'Fixed')}</dl>
      <div class="list-build-block"><div class="builds"><div><span class="label">SL</span><code>${esc(r.sl)}</code></div><div><span class="label">RHEL</span><code>${esc(r.rh)}</code></div></div><div class="signals"><span class="signal ${r.p?'positive':''}" title="P: патч под CVE найден в PATCH коммита сборки">P ${r.p?'+':'−'} <span>${r.p?'Патч найден':'Нет подтверждения патча'}</span></span><span class="signal ${r.d?'positive':''}" title="D: апстрим-версия вне известных уязвимых диапазонов">D ${r.d?'+':'−'} <span>${r.d?'Вне диапазона':'Нет подтверждения по версии'}</span></span></div></div>
      <div class="dev-note"><span class="label">Комментарий разработчика</span><p>${esc(r.comment)}</p></div>
    </div>
    ${r.reviewComment?`<div class="review-note"><span class="label">Замечание ревьювера</span><p>${esc(r.reviewComment)}</p></div>`:''}
    <div class="list-card-footer">${rowLinks(r)}</div>
    ${rawFields(r)}
    </div>
    ${reviewChecklist(r)}
  </article>`;
}
function reviewChecklist(r) {
  const checked=reviewChecks.filter(c=>[-1,1].includes(r.checks[c.key])).length;
  const failed=reviewChecks.filter(c=>r.checks[c.key] === -1).length;
  const states=[{value:0,label:'Не смотрелось',mark:'<i class="unseen-square"></i>',name:'unseen'},
    {value:1,label:'ОК',mark:'✓',name:'ok'},{value:-1,label:'Не ОК',mark:'✕',name:'bad'}];
  return `<aside class="review-checklist" aria-label="Чеклист ${r.cve}">
    <div class="check-summary"><h4>Чеклист ревью</h4><span class="check-count ${failed?'has-failures':''}">${checked} / ${reviewChecks.length}</span></div>
    <div class="check-legend">□ не смотрел · ✓ ок · ✕ не ок</div>
    <div class="check-items">${reviewChecks.map(check=>`<div class="check-row"><span id="check-label-${r.id}-${check.key}" title="${esc(check.hint)}">${check.label}</span><div class="check-options" role="group" aria-labelledby="check-label-${r.id}-${check.key}">${states.map(state=>`<label class="check-option ${state.name}" title="${esc(check.label+': '+state.label)}"><input type="radio" name="check-${r.id}-${check.key}" value="${state.value}" aria-label="${state.label}" data-review-check="${check.key}" data-id="${r.id}" ${r.checks[check.key] === state.value?'checked':''} ${r.pool === 'done'?'disabled':''}><span aria-hidden="true">${state.mark}</span></label>`).join('')}</div></div>`).join('')}</div>
    <p class="check-hint ${failed?'has-failures':''}">${failed?`Не ОК: ${failed}. Можно отправить в проблемы.`:checked === reviewChecks.length?'Все пункты проверены.':'Для завершения отметьте каждый пункт.'}</p>
    <div class="check-actions">${r.pool === 'done'?`<span class="check-done">${icon('check')}Ревью завершено</span>${btn('Вернуть на ревью','pending',r.id,'','back')}`:`<button class="btn primary" data-action="done" data-id="${r.id}" ${reviewComplete(r)?'':'disabled'}>${icon('check')}Ревьювед</button>${r.pool === 'pending'?btn('Есть проблема','problem',r.id,'danger-outline','alert'):btn('Комментарий','problem',r.id,'danger-outline','alert')+btn('Вернуть на ревью','pending',r.id,'quiet','back')}`}</div>
  </aside>`;
}
function stats() {const c=counts();return `<div class="stats"><div><span class="label">Ожидают решения</span><b>${String(c.pending).padStart(2,'0')}</b><span>задач разработчиков</span></div><div><span class="label">Нужна доработка</span><b>${String(c.problem).padStart(2,'0')}</b><span>с замечаниями</span></div><div><span class="label">Ревью завершено</span><b>${String(c.done).padStart(2,'0')}</b><span>задач проверено</span></div></div>`;}
function filters() { const people=[...new Set(rows.map(r=>r.dev))];return `<div class="filters"><label class="search">${icon('search')}<input id="search" type="search" placeholder="CVE, компонент, тикет…" value="${esc(query)}" aria-label="Поиск задач"></label><select id="dev" aria-label="Разработчик"><option value="">Все разработчики</option>${people.map(p=>`<option ${p === dev?'selected':''}>${esc(p)}</option>`).join('')}</select><select id="severity" aria-label="Критичность"><option value="">Любая критичность</option>${['Critical','Important','Moderate','Low'].map(s=>`<option ${s === severity?'selected':''}>${s}</option>`).join('')}</select><select id="order" aria-label="Порядок задач"><option value="severity" ${order === 'severity'?'selected':''}>Сначала критичные</option><option value="oldest" ${order === 'oldest'?'selected':''}>Сначала старые</option></select></div>`;}
function filtered(p=pool) {return rows.filter(r => r.pool === p && (!dev||r.dev === dev) && (!severity||r.severity === severity) && [r.component,r.cve,r.task,r.dev,r.comment,r.reviewComment].join(' ').toLowerCase().includes(query.toLowerCase())).sort((a,b)=>order === 'severity'? b.cvss-a.cvss:a.end.split('.').reverse().join('').localeCompare(b.end.split('.').reverse().join('')) || a.task.localeCompare(b.task));}
function empty() {return `<div class="empty">${icon('check')}<h3>${pool === 'pending' && !query && !dev && !severity?'Всё проверено':'Здесь пока нет задач'}</h3><p>${query||dev||severity?'Попробуйте изменить фильтры.':'Можно перейти к другому пулу.'}</p></div>`;}
function detail(r) {return `<article class="detail task-card" data-card="${r.id}"><div class="detail-top"><span class="package">${esc(r.component)}</span><span class="badge">${poolNames[r.pool]}</span></div><h2 class="mono">${r.cve}</h2><div class="badges">${badges(r)}</div>${rowLinks(r)}${context(r,true)}<div class="decision"><span class="label">Ваше решение</span>${actions(r)}</div></article>`;}
function queueItem(r) {return `<button class="queue-item ${selected === r.id?'selected':''}" data-action="select" data-id="${r.id}"><div><b>${esc(r.component)}</b><span class="sev-dot ${r.severity.toLowerCase()}"></span></div><span class="mono">${r.cve}</span><small>${esc(r.dev)} <span>→</span></small></button>`;}
function teamSummary(list) {
  const c=counts(), people=[...new Set(list.map(r=>r.dev))];
  const allPeople=[...new Set(rows.map(r=>r.dev))];
  const statusLegend = values => Object.keys(poolNames).map(p=>`<span class="${p}"><i class="sw"></i>${poolNames[p]} <b>${values[p]}</b></span>`).join('');
  const statusBar = (values,tag='span') => Object.keys(poolNames).filter(p=>values[p]).map(p=>`<${tag} class="${p}" style="flex:${values[p]}">${tag === 'span'?values[p]:''}</${tag}>`).join('');
  const hero = `<header class="hero summary-hero"><div class="wrap">
    <div class="hero-top"><div><div class="eyebrow">Ревью решений разработчиков</div><h1>Ревью по CVE</h1><p class="asof"><b>9.3.2</b> на 14.11.2026</p></div>
    <div class="hero-total"><div class="n">${rows.length}</div><div class="s">задач · <b>${new Set(rows.map(r=>r.cve)).size}</b> CVE · <b>${allPeople.length}</b> разработчика</div></div></div>
    <div class="hero-mix"><div class="mixbar" role="img" aria-label="${Object.keys(poolNames).map(p=>poolNames[p]+': '+c[p]).join(', ')}">${statusBar(c)}</div><div class="hero-leg">${statusLegend(c)}</div></div>
    <div class="summary-source"><p>vulnsheet-demo.xlsx<br>Только «Ожидает ревью» · SecOps исключены</p><div class="head-tools">${btn('Ссылки','settings',null,'','settings')}${btn('Сбросить демо','reset',null,'quiet','back')}</div></div>
  </div></header>`;
  const groups = people.map(person => {
    const tasks=list.filter(r=>r.dev === person), all=rows.filter(r=>r.dev === person);
    const values=Object.fromEntries(Object.keys(poolNames).map(p=>[p,all.filter(r=>r.pool === p).length]));
    const color=allPeople.indexOf(person)%4+1;
    return `<section class="team-group" style="--dc:var(--c${color})">
      <div class="person-heading"><div><h2><i></i>${esc(person)}</h2><p>Разработчик</p></div>
      <div class="person-current"><span class="big">${tasks.length}<small>задач</small></span><span class="person-caption">${poolNames[pool]}</span></div>
      <div class="person-progress"><div class="person-mix" aria-hidden="true">${statusBar(values,'i')}</div><div class="person-statuses">${statusLegend(values)}</div></div></div>
      <div class="team-tasks">${tasks.map(r=>`<article class="team-task" data-card="${r.id}">
        <div class="team-task-top"><span class="package">${esc(r.component)}</span><h3 class="mono">${r.cve}</h3>${badges(r)}<span class="task-id mono">#${r.task}</span></div>
        <div class="team-task-bottom"><p>${esc(r.comment)}</p></div>
        ${r.reviewComment?`<div class="review-note"><span class="label">Замечание ревьювера</span><p>${esc(r.reviewComment)}</p></div>`:''}
        <div class="team-row-footer">${rowLinks(r)}${actions(r)}</div>
        <details class="team-details"><summary>Контекст, сборки и все поля строки</summary>${context(r,true)}</details>
      </article>`).join('')}</div>
    </section>`;
  }).join('');
  return `${hero}<div class="summary-nav"><div class="wrap">${pools()}<span class="summary-nav-note">По разработчикам</span></div></div><main class="wrap summary-main">${filters()}
    <section class="team-panel"><div class="section-line"><h2>${poolNames[pool]} <span class="cnt">${list.length}</span></h2><span>${people.length} разработчика · решения ревьювера</span></div><div class="team-groups">${groups || empty()}</div></section>
  </main>`;
}
function render() {
  const list=filtered(); if(!list.some(r=>r.id === selected)) selected=list[0]?.id || null;
  document.body.className='v'+variant;
  const c=counts();
  document.getElementById('variant-nav').innerHTML = `<a class="lab-brand" href="index.html">${icon('grid')} UI LAB <span>/ cvereview</span></a><nav aria-label="Варианты интерфейса">${names.map((n,i)=>`<a href="${files[i]}" ${i+1 === variant?'aria-current="page"':''}><b>0${i+1}</b><span>${n}</span></a>`).join('')}</nav><span class="demo-label">Прототип · демоданные</span>`;
  const header = `<header class="page-head"><div><div class="eyebrow">DEVELOPER REVIEW / 9.3.2</div><h1>${variant === 4?'Время проверить.':variant === 5?'Решения команды.':'Ревью уязвимостей'}</h1><p>${descriptions[variant-1]}</p></div><div class="head-tools">${btn('Ссылки','settings',null,'','settings')}${btn('Сбросить демо','reset',null,'quiet','back')}</div></header>`;
  let content='';
  if(variant === 1) content=`<div class="hero"><div class="wrap">${header}${stats()}<div class="hero-foot"><span>vulnsheet-demo.xlsx <span class="dot">·</span> 14 ноября 2026</span><span>Только разработчики <span class="dot">·</span> SecOps исключены</span></div></div></div><main class="wrap">${pools()}${filters()}<div class="section-line"><h2>${poolNames[pool]} <span>${list.length}</span></h2><span>Решение ревьювера не меняет статус исходной строки</span></div><div class="card-grid">${list.map(listCard).join('') || empty()}</div></main>`;
  if(variant === 2) content=`<div class="inbox-shell"><aside class="rail"><div class="product-mark">${icon('inbox')}<strong>cve<span>review</span></strong></div><div class="label">Рабочее пространство</div>${pools(true)}<div class="rail-bottom"><span class="avatar">Я</span><div><b>Ревьювер</b><small>Релиз 9.3.2</small></div></div></aside><main class="inbox-main">${header}${filters()}<div class="inbox-layout"><section class="queue"><div class="queue-heading"><h2>${poolNames[pool]}</h2><span>${list.length} задач</span></div>${list.map(queueItem).join('') || empty()}</section><div class="detail-wrap">${list.length?detail(list.find(r=>r.id === selected)):empty()}</div></div><div class="source-line">vulnsheet-demo.xlsx · Только разработчики · SecOps исключены</div></main></div>`;
  if(variant === 3) content=`<main class="wrap board-wrap">${header}<div class="board-info"><span>${icon('git')} Релиз 9.3.2 <span class="dot">/</span> vulnsheet-demo.xlsx</span><span>Только разработчики · SecOps исключены</span></div>${filters()}<div class="board">${Object.keys(poolNames).map(p=>`<section class="board-col ${p}"><div class="col-heading">${icon(poolIcons[p])}<h2>${poolNames[p]}</h2><b>${filtered(p).length}</b></div><div class="col-note">${{pending:'Готовы к вашей проверке',problem:'Ждут исправлений разработчика',done:'Проверены и убраны из очереди'}[p]}</div><div class="board-stack">${filtered(p).map(r=>card(r,true)).join('') || '<div class="board-empty">Задач нет</div>'}</div></section>`).join('')}</div></main>`;
  if(variant === 4) content=`<main class="wrap focus-wrap">${header}<div class="focus-meta"><span>${icon('focus')} СЕССИЯ РЕВЬЮ <span class="dot">/</span> vulnsheet-demo.xlsx</span><span>${c.done} из ${rows.length} проверено</span></div><div class="progress"><i style="width:${c.done/rows.length*100}%"></i></div>${pools()}${filters()}<div class="focus-layout"><section class="focus-stage">${list.length?detail(list.find(r=>r.id === selected)):empty()}</section><aside class="up-next"><div class="queue-heading"><h2>${poolNames[pool]}</h2><span>${list.length}</span></div><p>Выберите задачу или завершите текущую — следующая откроется сама.</p>${list.map(queueItem).join('')}<div class="focus-note">${icon('clock')} Решения сохраняются в этом браузере. SecOps исключены.</div></aside></div></main>`;
  if(variant === 5) content=teamSummary(list);
  document.getElementById('app').innerHTML=content;
  document.getElementById('footnote').textContent=`UI-прототип 0${variant} / ${names[variant-1]} · Все CVE, сборки и решения вымышленные · ${storageAvailable?'Решения хранятся локально':'Хранилище недоступно — решения только в этой вкладке'}`;
  document.getElementById('search')?.addEventListener('input', e=>{const position=e.target.selectionStart;query=e.target.value;render();const input=document.getElementById('search');input.focus();input.setSelectionRange(position,position);});
  ['dev','severity','order'].forEach(id=>document.getElementById(id)?.addEventListener('change',e=>{if(id === 'dev')dev=e.target.value;if(id === 'severity')severity=e.target.value;if(id === 'order')order=e.target.value;render();}));
}
function toast(message) { const t=document.getElementById('toast');t.innerHTML=`${icon('check')}<span>${esc(message)}</span>${undo?btn('Отменить','undo',null,'quiet'):''}`;t.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.hidden=true,6500); }
function update(id,next,comment) {const r=rows.find(r=>r.id === id);if(variant === 1 && next === 'done' && !reviewComplete(r))return;undo={...r};r.pool=next;if(comment != null)r.reviewComment=comment;persist();render();toast(next === 'done'?'Проверено. Задача убрана из очереди.':next === 'problem'?'Задача перенесена в «Проблемы».':'Задача возвращена на ревью.');}
let dialogTrigger=null;
function openDialog(id){dialogTrigger=document.activeElement;document.getElementById(id).showModal();}
function closeDialog(id){document.getElementById(id).close();if(dialogTrigger?.isConnected)dialogTrigger.focus();}
function openProblem(id) {const r=rows.find(r=>r.id === id);const form=document.getElementById('problem-form');form.dataset.id=id;document.getElementById('problem-context').textContent=`${r.component} / ${r.cve} / ${r.dev}`;const input=document.getElementById('problem-comment');input.value=r.reviewComment;input.setCustomValidity('');openDialog('problem-dialog');input.focus();}
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-action]');if(!b)return;const {action,id}=b.dataset;
 if(action === 'pool'){pool=b.dataset.pool;selected=null;render();}
 if(action === 'select'){selected=id;render();}
 if(action === 'done'||action === 'pending')update(id,action);
 if(action === 'problem')openProblem(id);
 if(action === 'undo' && undo){rows=rows.map(r=>r.id === undo.id?{...undo}:r);selected=undo.id;undo=null;persist();render();toast('Последнее решение отменено.');}
 if(action === 'reset'){rows=eligible.map(withChecks);pool='pending';selected=null;dev='';query='';severity='';order='severity';undo=null;persist();render();toast('Исходные демоданные восстановлены.');}
 if(action === 'close-dialog')closeDialog(b.dataset.dialog);
 if(action === 'settings'){document.getElementById('task-template').value=links.task;document.getElementById('repo-template').value=links.repo;openDialog('settings-dialog');}
});
document.addEventListener('change',e=>{
 const input=e.target.closest('[data-review-check]');if(!input || variant !== 1)return;
 const r=rows.find(row=>row.id === input.dataset.id),key=input.dataset.reviewCheck,value=Number(input.value);
 if(!r || r.pool === 'done' || !reviewChecks.some(check=>check.key === key) || ![-1,0,1].includes(value))return;
 r.checks={...r.checks,[key]:value};persist();
 const aside=input.closest('.review-checklist');aside.outerHTML=reviewChecklist(r);
 document.querySelector(`[data-id="${r.id}"][data-review-check="${key}"][value="${value}"]`)?.focus({preventScroll:true});
});
document.getElementById('problem-comment').addEventListener('input',e=>e.target.setCustomValidity(''));
document.getElementById('problem-form').addEventListener('submit',e=>{e.preventDefault();const input=document.getElementById('problem-comment');const value=input.value.trim();if(!value){input.setCustomValidity('Опишите, что нужно исправить.');input.reportValidity();return;}const id=e.target.dataset.id;closeDialog('problem-dialog');update(id,'problem',value);});
document.getElementById('settings-form').addEventListener('submit',e=>{e.preventDefault();const task=document.getElementById('task-template'),repo=document.getElementById('repo-template');for(const input of [task,repo]){input.setCustomValidity('');try{const u=new URL(input.value.replace(/\{[^}]+\}/g,'example'));if(!['https:','http:'].includes(u.protocol))throw Error();}catch{input.setCustomValidity('Укажите адрес https://… с нужными плейсхолдерами.');input.reportValidity();return;}}links={task:task.value.trim(),repo:repo.value.trim()};try{localStorage.setItem('cvereview-ui-links-v1',JSON.stringify(links));}catch{storageAvailable=false;}closeDialog('settings-dialog');render();toast('Шаблоны ссылок сохранены.');});
['task-template','repo-template'].forEach(id=>document.getElementById(id).addEventListener('input',e=>e.target.setCustomValidity('')));
render();
