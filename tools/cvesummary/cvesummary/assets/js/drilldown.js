/* Список исходных задач по счётчикам сводки: поиск, сортировка и CSV. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.CS.drilldown = factory(); root.CS.drilldown.mount(root.CS); }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const norm = value => String(value ?? '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('ru');
  const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' });
  const reasonNames = { fixed: 'Фикс в RHEL', patch: 'Устранено ранее', range: 'Вне диапазона', dup: 'Дубликат' };
  const columns = [
    ['row', 'Строка', 'number'], ['task', 'Task ID'], ['cve', 'CVE'], ['comp', 'Компонент'],
    ['sevN', 'Критичность'], ['cvss', 'CVSS', 'number'], ['status', 'Статус'], ['dev', 'Разработчик'],
    ['reasonsText', 'Основания'], ['tdate', 'Поступила', 'date'], ['start', 'Начата', 'date'],
    ['end', 'Завершена', 'date'], ['hours', 'Расч. часы', 'number'], ['rstate', 'RHEL'],
    ['ai_verdict', 'AI'], ['ai_conf', 'Уверенность'], ['ai_rem', 'Remediation'], ['comment', 'Комментарий'],
  ];
  function select(rows, query, key = 'cvss', direction = 'desc') {
    const tokens = norm(query).split(' ').filter(Boolean), col = columns.find(c => c[0] === key);
    const value = r => {
      const v = r[key];
      if (v == null || v === '') return null;
      if (col && col[2] === 'number') { const n = Number(String(v).replace(',', '.')); return Number.isFinite(n) ? n : null; }
      if (col && col[2] === 'date') return /^\d{4}-\d{2}-\d{2}$/.test(v) && !(r.bad || []).includes(key) ? v : null;
      return String(v);
    };
    return rows.filter(r => {
      const haystack = norm(Object.values(r).filter(v => typeof v === 'string' || typeof v === 'number').join(' '));
      return tokens.every(t => haystack.includes(t));
    }).sort((a, b) => {
      const x = value(a), y = value(b);
      if (x === null || y === null) return x === y ? a.row - b.row : x === null ? 1 : -1;
      const diff = typeof x === 'number' ? x - y : collator.compare(x, y);
      return (direction === 'desc' ? -diff : diff) || a.row - b.row;
    });
  }
  function csv(rows) {
    const cols = [...columns, ['measure', 'Принятая мера'], ['slnvr', 'SL NVR'], ['rhnvr', 'RHEL NVR'],
      ['fixdate', 'Fix date'], ['ai_run', 'AI run'], ['link', 'CVE link'], ['rhsa', 'Advisory']];
    const escape = v => '"' + String(v ?? '').replace(/^[=+@\-\t\r\n]/, "'$&").replace(/"/g, '""') + '"';
    return '\ufeff' + [cols.map(c => escape(c[1])).join(';'), ...rows.map(r => cols.map(c => escape(r[c[0]])).join(';'))].join('\r\n');
  }
  function aiRows(rows, roles) {
    const groups = new Map();
    for (const r of rows) {
      const key = roles.taskKey(r) ?? '\u0001' + r.i, prev = groups.get(key);
      const run = v => v.ai_run && !(v.bad || []).includes('ai_run') ? v.ai_run : null;
      if (!prev || (r.ai_verdict && (!prev.ai_verdict || (run(r) !== null && (run(prev) === null || run(r) > run(prev)))))) groups.set(key, r);
    }
    return [...groups.values()];
  }
  function mount(CS) {
    const { roles, hours, dates, ai, strips } = CS;
    const $ = id => document.getElementById(id);
    const data = JSON.parse($('data').textContent), asOf = dates.dayOf(data.meta.as_of);
    const H = hours.compute(data.rows, asOf), dup = roles.duplicates(data.rows);
    const rows = data.rows.map((r, i) => {
      const reasons = roles.closeReasons(r, dup[i] !== null);
      return { ...r, i, hours: H.hours[i], sevN: roles.sevOf(r), measureN: roles.measureOf(r),
        devKey: roles.devOf(r), done: roles.isDone(r), open: roles.isOpen(r), taken: roles.isTaken(r),
        reasons, reasonsText: reasons.map(k => reasonNames[k]).join(', '),
        duplicateRow: dup[i] === null ? '' : data.rows[dup[i]].row };
    });
    const pairs = aiRows(rows, roles), groupOf = r => !r.ai_verdict || norm(r.ai_verdict) === ai.NOT_PROCESSED ? 'none'
      : ['not affected', 'invalid cve', 'rejected cve'].includes(norm(r.ai_verdict)) ? 'no' : 'maybe';
    const pairNote = 'По одной строке на пару CVE + компонент; выбран самый свежий вердикт AI. Строки без компонента учитываются отдельно.';
    const nodes = new WeakMap();
    function bind(node, title, members, note = '') {
      if (!node) return;
      nodes.set(node, { title, rows: members, note });
      node.dataset.drill = '1'; node.classList.add('drill-target'); node.tabIndex = 0;
      node.setAttribute('role', 'button'); node.setAttribute('aria-haspopup', 'dialog');
      node.setAttribute('aria-label', `${title} — открыть список, ${members.length} строк`);
      node.title = 'Открыть задачи: ' + title;
    }
    const make = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const dialog = make('dialog', 'drill-dialog'); dialog.id = 'task-explorer';
    dialog.setAttribute('aria-labelledby', 'drill-title');
    const top = make('div', 'drill-top'), heading = make('div'), kicker = make('div', 'drill-kicker', 'ЗАДАЧИ В ВЫБОРКЕ');
    const title = make('h2', '', ''); title.id = 'drill-title';
    const note = make('p', 'drill-note'); heading.append(kicker, title, note);
    const close = make('button', 'drill-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Закрыть список');
    top.append(heading, close);
    const toolbar = make('div', 'drill-toolbar'), label = make('label', 'drill-search');
    label.append(make('span', '', 'Поиск в выборке'));
    const input = make('input'); input.type = 'search'; input.placeholder = 'CVE, пакет, разработчик, комментарий…'; input.id = 'drill-search'; label.append(input);
    const exportButton = make('button', 'drill-export', 'Скачать CSV'); exportButton.type = 'button';
    toolbar.append(label, exportButton);
    const status = make('div', 'drill-count'); status.id = 'drill-count'; status.setAttribute('role', 'status');
    const wrap = make('div', 'drill-tablewrap'); wrap.tabIndex = 0; wrap.setAttribute('aria-label', 'Таблица задач, прокручивается по горизонтали');
    const table = make('table', 'drill-table'), head = make('thead'), trh = make('tr');
    const visible = ['row', 'task', 'cve', 'comp', 'sevN', 'cvss', 'status', 'dev', 'reasonsText', 'ai_verdict', 'ai_conf', 'ai_rem'];
    const headers = new Map();
    for (const c of columns.filter(c => visible.includes(c[0]))) {
      const th = make('th'), b = make('button', '', c[1]); b.type = 'button'; b.dataset.sort = c[0]; th.scope = 'col';
      th.append(b); trh.append(th); headers.set(c[0], { th, b, name: c[1] });
      b.addEventListener('click', () => { direction = sortKey === c[0] && direction === 'asc' ? 'desc' : 'asc'; sortKey = c[0]; page = 0; draw(); });
    }
    head.append(trh); const tbody = make('tbody'); tbody.id = 'drill-body'; table.append(head, tbody); wrap.append(table);
    const footer = make('div', 'drill-footer'), range = make('span'), prev = make('button', '', '← Назад'), next = make('button', '', 'Далее →');
    prev.type = next.type = 'button'; footer.append(range, prev, next);
    dialog.append(top, toolbar, status, wrap, footer); document.body.append(dialog);
    let current = { rows: [], title: '', note: '' }, filtered = [], sortKey = 'cvss', direction = 'desc', page = 0, opener = null, savedOverflow = '';
    const pageSize = 50;
    const cveLink = (href, text) => {
      if (!/^https?:\/\//i.test(href || '')) return document.createTextNode(text || '—');
      const a = make('a', '', text); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a;
    };
    function draw() {
      filtered = select(current.rows, input.value, sortKey, direction);
      status.textContent = input.value ? `Найдено ${filtered.length} из ${current.rows.length} строк` : `${current.rows.length} строк в выборке`;
      exportButton.disabled = filtered.length === 0;
      for (const [key, h] of headers) { h.th.setAttribute('aria-sort', key === sortKey ? direction === 'asc' ? 'ascending' : 'descending' : 'none'); h.b.textContent = h.name + (key === sortKey ? direction === 'asc' ? ' ↑' : ' ↓' : ''); }
      tbody.replaceChildren();
      for (const r of filtered.slice(page * pageSize, (page + 1) * pageSize)) {
        const tr = make('tr'); tr.dataset.row = r.row;
        for (const c of columns.filter(c => visible.includes(c[0]))) {
          const td = make('td');
          if (c[0] === 'cve') { td.append(cveLink(r.link, r.cve)); td.className = 'mono'; }
          else if (c[0] === 'task') { td.append(cveLink(r.task, r.task)); td.className = 'mono'; }
          else if (c[0] === 'sevN') { const badge = make('span', 'drill-sev', r.sevN); badge.dataset.severity = r.sevN; td.append(badge); }
          else { td.textContent = r[c[0]] == null || r[c[0]] === '' ? '—' : String(r[c[0]]); }
          if (c[0] === 'reasonsText' && r.duplicateRow) td.append(make('small', 'drill-dup', `Основная строка: ${r.duplicateRow}`));
          tr.append(td);
        }
        tbody.append(tr);
      }
      if (!filtered.length) { const tr = make('tr'), td = make('td', 'drill-empty', current.rows.length ? 'Ничего не найдено. Измените поисковый запрос.' : 'В этой выборке пока нет задач.'); td.colSpan = visible.length; tr.append(td); tbody.append(tr); }
      range.textContent = filtered.length ? `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, filtered.length)} из ${filtered.length}` : '0 строк';
      prev.disabled = page === 0; next.disabled = (page + 1) * pageSize >= filtered.length;
      wrap.scrollTop = 0;
    }
    function open(selection, trigger) {
      current = selection; opener = trigger; sortKey = 'cvss'; direction = 'desc'; page = 0; input.value = '';
      title.textContent = selection.title; note.textContent = selection.note || 'Строки исходной таблицы, из которых рассчитан выбранный показатель.';
      draw(); $('tip').hidden = true; savedOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden'; dialog.showModal(); input.focus();
    }
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); dialog.close(); } }, true);
    dialog.addEventListener('click', e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
    dialog.addEventListener('close', () => {
      document.body.style.overflow = savedOverflow;
      // Resize can replace the report controls while the dialog is open.
      const replacement = () => {
        const candidates = [...document.querySelectorAll('[data-drill]')].filter(node => {
          const selection = nodes.get(node);
          return selection && selection.title === current.title && selection.note === current.note
            && selection.rows.length === current.rows.length
            && selection.rows.every((r, i) => r === current.rows[i])
            && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
        });
        const classes = [...opener.classList].filter(c => !['drill-target', 'dim'].includes(c));
        return candidates.find(node => node.tagName === opener.tagName
          && classes.every(c => node.classList.contains(c))) || candidates[0];
      };
      const target = opener && opener.isConnected ? opener : replacement() || $('k-total');
      target.focus({ preventScroll: true });
    });
    input.addEventListener('input', () => { page = 0; draw(); });
    prev.addEventListener('click', () => { page--; draw(); }); next.addEventListener('click', () => { page++; draw(); });
    exportButton.addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([csv(filtered)], { type: 'text/csv;charset=utf-8' }));
      const a = make('a'); a.href = url; a.download = `cvesummary-${data.meta.as_of}-selection.csv`; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    document.addEventListener('click', e => {
      const target = e.target.closest('[data-drill]'); if (!target || !nodes.has(target) || dialog.open) return;
      e.preventDefault(); open(nodes.get(target), target);
    });
    document.addEventListener('keydown', e => {
      const target = e.target.closest('[data-drill]');
      if (target && (e.key === 'Enter' || e.key === ' ') && !dialog.open) { e.preventDefault(); open(nodes.get(target), target); }
    });
    function grid(id, getRows, opts = {}) {
      const host = $(id); if (!host) return;
      const cells = [...host.children];
      let index = 0;
      for (const indexes of strips.rows(cells, c => c.classList.contains('k'), c => c.classList.contains('h'))) {
        const group = indexes.map(i => cells[i]), key = group[0].dataset.key ?? group[0].textContent.trim();
        const members = getRows(key, group[0], index++), n = opts.note || '';
        const bar = group.find(c => c.classList.contains('b'));
        const values = group.filter(c => c !== group[0] && c !== bar);
        const targets = opts.status ? [group[0], bar, ...values.slice(0, 2)] : group;
        for (const node of targets) if (node && !node.textContent.includes(' ч')) bind(node, `${opts.prefix || ''}${key}`, members, n);
        const segments = bar ? [...bar.querySelectorAll(':scope > span > span')] : [];
        if (opts.stat) {
          bind(segments[0], `${key} · готово`, members.filter(r => r.done), n);
          bind(segments[1], `${key} · открыто`, members.filter(r => r.open), n);
        }
        if (opts.stat && !host.classList.contains('short')) {
          bind(values[1], `${key} · открыто`, members.filter(r => r.open), n);
          bind(values[2], `${key} · готово`, members.filter(r => r.done), n);
          bind(values[3], `${key} · готово`, members.filter(r => r.done), n);
        }
        if (opts.conf) {
          ['high','medium','low'].forEach((conf, i) => { if (values[i + 1].textContent !== '—') bind(values[i + 1], `AI: ${key} · ${conf}`, members.filter(r => norm(r.ai_conf) === conf), n); });
          if (segments.length === 4) {
            ['high', 'medium', 'low', 'other'].forEach((conf, i) => {
              const subset = members.filter(r => conf === 'other'
                ? !['high', 'medium', 'low'].includes(norm(r.ai_conf)) : norm(r.ai_conf) === conf);
              bind(segments[i], `AI: ${key} · ${conf}`, subset, n);
            });
          }
        }
      }
    }
    function connect() {
      bind($('k-total'), 'Все задачи', rows);
      bind($('k-comp'), 'Все компоненты', rows, `${roles.uniques(rows).comps} компонентов. В списке — все строки этих компонентов, включая строки без компонента.`);
      const taskGroups = new Map(); for (const r of rows) { const k = roles.taskKey(r) ?? '\u0001' + r.i; if (!taskGroups.has(k) || r.done && !taskGroups.get(k).done) taskGroups.set(k, r); }
      for (const r of rows) if (dup[r.i] !== null) taskGroups.set(roles.taskKey(r), rows[dup[r.i]]);
      bind($('k-cve'), 'Уникальные пары CVE + компонент', [...taskGroups.values()], 'Этот счётчик учитывает пары CVE + компонент. Для повторов показана основная строка.');
      const openRows = rows.filter(r => r.open), ready = openRows.filter(r => r.reasons.length);
      const heroParts = [rows.filter(r=>r.done), openRows.filter(r=>!r.reasons.length), ...['fixed','patch','range','dup'].map(k=>openRows.filter(r=>r.reasons[0]===k))].filter(g=>g.length);
      [...$('hero-bar').children].forEach((node,i)=>bind(node,(node.dataset.tip || '').split(': всего')[0],heroParts[i] || [],'Состав выбранного сегмента: задачи с несколькими основаниями учтены по первому основанию.'));
      const heroGroups = [rows.filter(r=>r.done),openRows.filter(r=>!r.reasons.length),ready].filter(g=>g.length);
      [...$('hero-groups').children].forEach((node,i)=>bind(node.querySelector('.cap'),['Готово','Без решения','Можно закрыть'].filter((_,j)=>[rows.filter(r=>r.done),openRows.filter(r=>!r.reasons.length),ready][j].length)[i],heroGroups[i]));
      const states = [...$('hero-state').children];
      bind(states[0], 'Готово', rows.filter(r=>r.done)); bind(states[1], 'В работе', rows.filter(roles.isWorking)); bind(states[2], 'Не взято', openRows.filter(r=>!r.taken));
      bind($('hero-risk').firstElementChild, 'Есть проблема / нужна доработка', rows.filter(roles.needsAttention));
      bind($('p-open'), 'Открыто сейчас', openRows); bind($('att-sub').querySelector('b'), 'Требует внимания', rows.filter(roles.needsAttention));
      bind($('close-sub').querySelector('b'), 'Можно закрыть', ready);
      grid('sevrows', k=>rows.filter(r=>r.sevN===k), {stat:true});
      grid('measrows', k=>rows.filter(r=>r.measureN===k), {stat:true});
      grid('rhel', k=>rows.filter(r=>(r.rstate || 'не указано')===k), {stat:true});
      grid('devstatus', k=>rows.filter(r=>(String(r.status || '').trim() || (r.taken ? 'Без статуса' : 'Не взята'))===k), {status:true});
      for (const [id, field] of [['sevstrip','sevN'],['measstrip','measureN'],['rhelstrip','rstate']]) {
        for (const node of $(id).children) { const key = node.dataset.key; bind(node,key,rows.filter(r=>(r[field] || 'не указано')===key)); }
      }
      grid('close-why', k=>ready.filter(r=>r.reasons.includes(Object.keys(reasonNames).find(x=>reasonNames[x]===k))));
      const closeCells=[...$('close-why').children];
      for(const indexes of strips.rows(closeCells,c=>c.classList.contains('k'),c=>c.classList.contains('h'))) {
        const group=indexes.map(i=>closeCells[i]), title=group[0].dataset.key, members=ready.filter(r=>r.reasons.includes(Object.keys(reasonNames).find(k=>reasonNames[k]===title)));
        const values=group.filter(c=>c!==group[0]&&!c.classList.contains('b'));
        bind(values[2],`${title} · взято`,members.filter(r=>r.taken)); bind(values[3],`${title} · не взято`,members.filter(r=>!r.taken));
        const segments = group.find(c => c.classList.contains('b')).querySelectorAll(':scope > span > span');
        bind(segments[0], `${title} · взято`, members.filter(r => r.taken));
        bind(segments[1], `${title} · не взято`, members.filter(r => !r.taken));
      }
      const compCells=[...$('components').children];
      for(let i=0;i<compCells.length;i+=3) {
        if (!compCells[i].classList.contains('lab') || !compCells[i+1]) continue;
        const comp=compCells[i].textContent, members=rows.filter(r=>r.comp===comp);
        compCells.slice(i,i+3).forEach(node=>bind(node,`Компонент: ${comp}`,members));
        const mode=$('comp-by').querySelector('[aria-pressed="true"]').dataset.by;
        for(const span of compCells[i+1].querySelectorAll('[data-tip]')) {
          const text=span.dataset.tip, key=text.slice((comp+' · ').length).replace(/: \d+$/,'');
          const subset=members.filter(r=>(mode==='sev'?r.sevN:mode==='measure'?r.measureN:r.rstate || 'не указано')===key);
          bind(span,`${comp} · ${key}`,subset);
        }
      }
      for (const card of $('people').querySelectorAll('.dev')) {
        const dev=card.querySelector('h3').textContent.trim(), mine=rows.filter(r=>r.devKey===dev);
        bind(card.querySelector('.big'), 'Разработчик: '+dev, mine);
        const predicates=[r=>r.done,r=>roles.isWorking(r)&&!roles.isReview(r)&&!roles.isPaused(r)&&!roles.needsAttention(r),
          r=>roles.isWorking(r)&&roles.isReview(r),r=>roles.isWorking(r)&&roles.isPaused(r),r=>roles.isWorking(r)&&roles.needsAttention(r)];
        const names=['готово','в работе','ревью','пауза','проблемы'];
        [...card.querySelector('.dstat').children].forEach((node,i)=>bind(node,dev+' · '+names[i],mine.filter(predicates[i])));
        const barItems=predicates.map((f,i)=>({f,i,n:mine.filter(f).length})).filter(x=>x.n);
        [...card.querySelector('.pbar').children].forEach((node,i)=>bind(node,dev+' · '+names[barItems[i].i],mine.filter(barItems[i].f)));
      }
      const anomalyNumbers=new Set([...$('anom-body').querySelectorAll('tr')].map(tr=>Number(tr.firstElementChild.textContent)).filter(Number.isFinite));
      bind($('anom-n'), 'Аномалии', rows.filter(r=>anomalyNumbers.has(r.row)));
      const heroLegendGroups={'готово':rows.filter(r=>r.done),'без решения':openRows.filter(r=>!r.reasons.length),'можно закрыть':ready,
        ...Object.fromEntries(Object.entries(reasonNames).map(([k,name])=>[norm(name),openRows.filter(r=>r.reasons[0]===k)]))};
      for(const node of $('hero-leg').children) {
        const name=norm(node.textContent).replace(/\s+\d+$/,'');
        if(heroLegendGroups[name]) bind(node,node.textContent.replace(/\s+\d+$/,''),heroLegendGroups[name],
          'Состав сегмента общей полосы: учитывается первое основание закрытия.');
      }
      const S = ai.summary(rows);
      // Select by the source entries, not their translated display labels.
      const verdictGroups = [
        ...S.verdicts.map(v => ({ key: v.k, rows: pairs.filter(r => norm(r.ai_verdict) === norm(v.k)) })),
        ...(S.notRun ? [{ key: 'не прогнано', rows: pairs.filter(r => !r.ai_verdict) }] : []),
      ];
      grid('ai-rows', (key, node, i) => verdictGroups[i].rows, {prefix:'AI: ', note:pairNote, conf:true});
      [...$('aistrip').children].forEach((node, i) => bind(node, `AI: ${verdictGroups[i].key}`, verdictGroups[i].rows, pairNote));
      const groups = {maybe:'возможно затронуто',no:'не затронуто',none:'не прогнано'};
      for(const id of ['ai-groups','rem-groups']) {
        const shown=['maybe','no','none'].filter(g=>pairs.some(r=>groupOf(r)===g));
        [...$(id).children].forEach((node, i) => {
          const title = `AI: ${groups[shown[i]]}`, members = pairs.filter(r => groupOf(r) === shown[i]);
          bind(node.querySelector('.cap'), title, members, pairNote);
          bind($(id === 'ai-groups' ? 'ai-leg' : 'rem-leg').children[i], title, members, pairNote);
        });
      }
      bind($('ai-total').querySelector('.n'), 'AI: осталось прогнать', pairs.filter(r=>groupOf(r)==='none'),pairNote);
      bind($('ai-total').querySelector('.s b'), 'AI: прогнано', pairs.filter(r=>groupOf(r)!=='none'),pairNote);
      // Remediation labels may repeat between verdict groups: keep each group's own membership.
      const remGroups = [
        ...S.remediations.map(item => ({ key: item.k || 'не указана', g: item.g,
          rows: pairs.filter(r => groupOf(r) === item.g && norm(r.ai_rem) === norm(item.k)) })),
        ...(S.notProcessed ? [{ key: `нет (${ai.NOT_PROCESSED})`, g: 'none',
          rows: pairs.filter(r => norm(r.ai_verdict) === ai.NOT_PROCESSED) }] : []),
        ...(S.notRun ? [{ key: 'не прогнано', g: 'none', rows: pairs.filter(r => !r.ai_verdict) }] : []),
      ];
      const remCells=[...$('rem-rows').children], remGrid=strips.rows(remCells,c=>c.classList.contains('k'),c=>c.classList.contains('h'));
      remGrid.forEach((indexes,i)=>indexes.forEach(j=>bind(remCells[j],`Remediation: ${remGroups[i].key} · ${groups[remGroups[i].g]}`,remGroups[i].rows,pairNote)));
      [...$('remstrip').children].forEach((node,i)=>bind(node,`Remediation: ${remGroups[i].key} · ${groups[remGroups[i].g]}`,remGroups[i].rows,pairNote));
    }
    const hint=make('p','drill-hint','Нажмите на число или сегмент, чтобы открыть список задач.');
    document.querySelector('.hero .wrap').append(hint);
    connect();
    let queued=false;
    const observer=new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(()=>{queued=false;connect();});}});
    observer.observe(document.querySelector('main'),{childList:true,subtree:true});
    observer.observe(document.querySelector('.hero'),{childList:true,subtree:true});
  }
  return { columns, select, csv, aiRows, mount };
}));
