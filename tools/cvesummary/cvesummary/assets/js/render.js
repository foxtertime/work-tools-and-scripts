/* Отрисовка сводки. Данные — из блока #data; роли, часы, темп и ширина
   графиков — модули dates, roles, hours, pace, timeline; здесь только DOM. */
(function () {
  'use strict';
  const { dates, roles, hours: Hm, pace, timeline } = window.CS;
  const DATA = JSON.parse(document.getElementById('data').textContent);
  const AS_OF = dates.dayOf(DATA.meta.as_of);
  const NS = 'http://www.w3.org/2000/svg';
  const AXIS_W = 32;
  const DAY_STEP = 10, WEEK_STEP = 28;

  const $ = id => document.getElementById(id);
  const css = t => `var(${t})`;
  const f1 = x => (Math.round(x * 10) / 10).toString().replace('.', ',');
  const fmt = d => (d === null || d === undefined ? '—' : dates.ruOf(d));
  const mk = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  /* Math.max(...arr) на большом массиве валит стек вызовов — данные таблицы любого размера */
  const maxOf = (arr, init) => { let m = init; for (const x of arr) if (x > m) m = x; return m; };
  const minOf = (arr, init) => { let m = init; for (const x of arr) if (x < m) m = x; return m; };
  const count = (arr, f) => { const m = new Map(); for (const x of arr) { const k = f(x); if (k == null || k === '') continue; m.set(k, (m.get(k) || 0) + 1); } return [...m].sort((a, b) => b[1] - a[1]); };
  const plural = (n, a, b, c) => { n = Math.abs(n) % 100; const n1 = n % 10; return n > 10 && n < 20 ? c : n1 > 1 && n1 < 5 ? b : n1 === 1 ? a : c; };
  const days = n => `${n} ${plural(n, 'день', 'дня', 'дней')}`;
  const LS = { get(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* без хранилища поля просто не запоминаются */ } } };
  const SEV_COLOR = { Critical: '--sev-crit', Important: '--sev-imp', Moderate: '--sev-mod', Low: '--sev-low' };
  const sevColor = k => SEV_COLOR[k] || '--sev-none';
  const link = (href, text, cls) => { if (!/^https?:\/\//.test(href || '')) return null; const a = el('a', cls || null, text); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a; };

  /* тултип — из образца, дословно */
  const tip = $('tip');
  document.addEventListener('pointermove', e => {
    const t = e.target.closest('[data-tip]');
    if (!t) { tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let x = e.clientX + 12, y = e.clientY + 14;
    if (x + w > innerWidth - 8) x = e.clientX - w - 12;
    if (y + h > innerHeight - 8) y = e.clientY - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  });

  /* hbars — из образца, дословно */
  function hbars(target, items, max, opts = {}) {
    const box = $(target); box.replaceChildren();
    if (!items.length) { box.append(el('div', 'empty', 'Нет данных')); return; }
    for (const it of items) {
      box.append(el('div', 'lab', it.label));
      const tr = el('div', 'track');
      const segs = it.segs || [{ n: it.n, color: opts.color || '--accent', name: '' }];
      for (const s of segs) { if (!s.n) continue;
        const sp = el('span'); sp.style.flexBasis = (s.n / max * 100) + '%'; sp.style.background = css(s.color);
        sp.dataset.tip = `${it.label}${s.name ? ' · ' + s.name : ''}: ${s.n}`; tr.append(sp); }
      box.append(tr);
      box.append(el('div', 'val num', it.valText ?? String(it.n)));
    }
  }
  function legend(id, cats) { const leg = $(id); leg.replaceChildren(); for (const s of cats) { const li = el('span'); const sw = el('i', 'sw'); sw.style.background = css(s.c); li.append(sw, s.k); leg.append(li); } }

  /* ---------- данные ---------- */
  const H = Hm.compute(DATA.rows, AS_OF);
  const DUP = roles.duplicates(DATA.rows);
  const recs = DATA.rows.map((r, i) => Object.assign({}, r, {
    i, devKey: roles.devOf(r), sevN: roles.sevOf(r), measureN: roles.measureOf(r),
    done: roles.isDone(r), open: roles.isOpen(r), taken: roles.isTaken(r), working: roles.isWorking(r),
    review: roles.isReview(r), paused: roles.isPaused(r), attention: roles.needsAttention(r),
    reasons: roles.closeReasons(r, DUP[i] !== null), dupOf: DUP[i], cvssN: parseFloat(String(r.cvss).replace(',', '.')) || 0,
    tdateD: dates.dayOf(r.tdate), startD: dates.dayOf(r.start), endD: dates.dayOf(r.end), hours: H.hours[i],
  }));
  const closedWithHours = list => list.filter(r => r.done && r.endD !== null && r.hours !== null).map(r => r.hours);
  const SEV_KEYS = roles.sevOrder(recs.map(r => r.sevN));
  const SEV = SEV_KEYS.map(k => ({ k, c: sevColor(k) }));
  const allDays = recs.flatMap(r => [r.tdateD, r.startD, r.endD]).filter(d => d !== null && d <= AS_OF);
  const FIRST = allDays.length ? minOf(allDays, Infinity) : null;
  const statusKey = r => String(r.status || '').trim() || (r.taken ? 'Без статуса' : 'Не взята');
  const roleColor = r => r.done ? '--ok' : r.attention ? '--bad' : r.paused ? '--warn' : r.review ? '--c7' : r.taken ? '--accent' : '--sev-none';
  const hoursText = r => (r.hours === null ? '—' : f1(r.hours));

  /* ---------- графики по времени ---------- */
  function scale(top) {
    top = Math.max(1, top);
    const step = top <= 5 ? 1 : top <= 12 ? 2 : top <= 30 ? 5 : top <= 60 ? 10 : top <= 150 ? 25 : 50;
    return { yMax: Math.ceil(top / step) * step, yStep: step };
  }
  /* Рамка: слева ось значений (стоит на месте), справа листаемая область
     со столбиками. Положение запоминается как расстояние до правого края
     (0 — график в конце, на последних днях) по прокрутке самого
     пользователя; при перерисовке оно восстанавливается. Прокрутка,
     которую делает браузер при изменении размера окна, не считается:
     пока идёт resize, расстояние не обновляется. */
  const POS = new Map();
  let resizing = false;
  function frame(host, o) {
    const key = o.key || host.id;
    const st = POS.get(key) || { dist: 0 };
    POS.set(key, st);
    host.replaceChildren();
    const axisW = o.axis === false ? 0 : AXIS_W;
    const box = el('div', 'tl-scroll');
    let axis = null;
    if (axisW) { axis = mk('svg', { class: 'tl-axis', width: axisW, height: o.height, viewBox: `0 0 ${axisW} ${o.height}` }); host.append(axis); }
    host.append(box);
    const avail = Math.max(1, box.clientWidth || host.clientWidth - axisW);
    const { width, step } = timeline.layout(o.count, o.minStep, avail);
    const plot = mk('svg', { class: 'tl-plot', width, height: o.height, viewBox: `0 0 ${width} ${o.height}` });
    box.append(plot);
    const y = n => o.pad.t + (o.height - o.pad.t - o.pad.b) * (1 - n / o.yMax);
    if (axis) {
      for (let g = 0; g <= o.yMax; g += o.yStep) {
        plot.append(mk('line', { x1: 0, x2: width, y1: y(g), y2: y(g), class: 'gl' }));
        const t = mk('text', { x: axisW - 6, y: y(g) + 4, 'text-anchor': 'end' }); t.textContent = g; axis.append(t);
      }
    }
    timeline.attach(box);
    box.addEventListener('scroll', () => { if (!resizing) st.dist = Math.max(0, box.scrollWidth - box.clientWidth - box.scrollLeft); }, { passive: true });
    box.scrollLeft = Math.max(0, box.scrollWidth - box.clientWidth - st.dist);
    timeline.sync(box);
    return { plot, step, width, y, height: o.height };
  }

  function drawPace(series, from) {
    const host = $('pace-chart');
    if (!series.length) { host.replaceChildren(el('div', 'empty', 'Нет дат в Task date и End date')); return; }
    const { yMax, yStep } = scale(maxOf(series.map(s => Math.max(s.i, s.o)), 0));
    const F = frame(host, { count: series.length, minStep: DAY_STEP, height: 230, yMax, yStep, pad: { t: 8, b: 22 } });
    const x = i => F.step * i + F.step / 2;
    const fi = series.findIndex(s => s.day > from);
    if (fi >= 0) F.plot.prepend(mk('rect', { x: F.step * fi, y: 8, width: F.width - F.step * fi, height: 230 - 30, fill: 'var(--accent-soft)' }));
    const path = (k, c, w, op) => F.plot.append(mk('path', { d: series.map((s, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + F.y(s[k]).toFixed(1)).join(''), fill: 'none', stroke: c, 'stroke-width': w, 'stroke-opacity': op, 'stroke-linejoin': 'round' }));
    path('i', 'var(--sev-imp)', 1, 0.4); path('o', 'var(--ok)', 1, 0.4);
    path('ia', 'var(--sev-imp)', 2.5, 1); path('oa', 'var(--ok)', 2.5, 1);
    const l = series.length - 1;
    [['ia', 'var(--sev-imp)'], ['oa', 'var(--ok)']].forEach(([k, c]) => F.plot.append(mk('circle', { cx: x(l), cy: F.y(series[l][k]), r: 4, fill: c, stroke: 'var(--panel)', 'stroke-width': 2 })));
    const every = Math.ceil(48 / F.step);
    /* метка дня под курсором: направляющая и точки на всех линиях; одна на
       график, переезжает за курсором */
    const mark = mk('g', { class: 'mark' });
    mark.append(mk('line', { y1: 8, y2: 208, class: 'guide' }));
    const dots = [['i', 'var(--sev-imp)', 2.5], ['o', 'var(--ok)', 2.5], ['ia', 'var(--sev-imp)', 4.5], ['oa', 'var(--ok)', 4.5]]
      .map(([k, c, r]) => { const d = mk('circle', { r, fill: c, stroke: 'var(--panel)', 'stroke-width': 2 }); mark.append(d); return [k, d]; });
    const show = i => {
      mark.firstChild.setAttribute('x1', x(i)); mark.firstChild.setAttribute('x2', x(i));
      dots.forEach(([k, d]) => { d.setAttribute('cx', x(i)); d.setAttribute('cy', F.y(series[i][k])); });
      mark.classList.add('on');
    };
    F.plot.addEventListener('pointerover', e => { const h = e.target.closest('rect[data-i]'); if (h) show(+h.dataset.i); });
    F.plot.addEventListener('pointerleave', () => mark.classList.remove('on'));
    series.forEach((s, i) => {
      if ((l - i) % every === 0) { const t = mk('text', { x: x(i), y: 230 - 8, 'text-anchor': i === l ? 'end' : i === 0 ? 'start' : 'middle' }); if (i === l) t.setAttribute('x', F.width - 2); if (i === 0) t.setAttribute('x', 2); t.textContent = fmt(s.day).slice(0, 5); F.plot.append(t); }
      const hit = mk('rect', { x: F.step * i, y: 8, width: F.step, height: 200, fill: 'transparent', 'data-i': i });
      hit.dataset.tip = `${fmt(s.day)}: поступило ${s.i}, закрыто ${s.o} · среднее за 7 дней ${f1(s.ia)} / ${f1(s.oa)}`;
      F.plot.append(hit);
    });
    F.plot.append(mark);
  }

  function weeksOf(items, cats) {
    if (FIRST === null) return [];
    const lo = dates.mondayOf(FIRST), hi = dates.mondayOf(AS_OF), weeks = [];
    for (let t = lo; t <= hi; t += 7) { const w = { t, all: 0 }; cats.forEach(c => { w[c.k] = 0; }); weeks.push(w); }
    for (const [d, k] of items) { if (d === null || d > AS_OF || d < lo) continue; const w = weeks[(dates.mondayOf(d) - lo) / 7]; w.all++; w[k]++; }
    return weeks;
  }

  /* stackChart — из образца, перенесён на frame(): x считается от F.step,
     высота — F.y, ось — в рамке */
  function stackChart(host, weeks, cats, what) {
    if (!weeks.length) { host.replaceChildren(el('div', 'empty', 'Нет данных с датами')); return; }
    const H2 = 230;
    const { yMax, yStep } = scale(maxOf(weeks.map(w => w.all), 0));
    const F = frame(host, { count: weeks.length, minStep: WEEK_STEP, height: H2, yMax, yStep, pad: { t: 16, b: 24 } });
    const barW = Math.max(3, Math.min(56, F.step - 6)), GAP = barW >= 10 ? 2 : 1;
    F.plot.classList.add('hlg');
    weeks.forEach((w, i) => {
      /* неделя — одна группа: под курсором она яркая, остальные приглушены */
      const col = mk('g', { class: 'hl' }); F.plot.append(col);
      const x = i * F.step + (F.step - barW) / 2;
      const segs = cats.filter(s => w[s.k] > 0);
      let acc = 0;
      segs.forEach((s, j) => {
        const n = w[s.k], y1 = F.y(acc + n), y0 = F.y(acc); acc += n;
        const h = Math.max(1, y0 - y1 - (j < segs.length - 1 ? GAP : 0));
        if (j === segs.length - 1 && h > 4) { const r = Math.min(3, barW / 2); col.append(mk('path', { d: `M${x},${y1 + h}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + barW - r}Q${x + barW},${y1} ${x + barW},${y1 + r}V${y1 + h}Z`, fill: css(s.c) })); }
        else col.append(mk('rect', { x, y: y1, width: barW, height: h, fill: css(s.c) }));
      });
      const hit = mk('rect', { x: i * F.step, y: 16, width: F.step, height: H2 - 40, fill: 'transparent' });
      hit.dataset.tip = `Неделя с ${fmt(w.t)}: ${what} ${w.all}` + (w.all ? ' · ' + cats.filter(s => w[s.k]).map(s => `${s.k} ${w[s.k]}`).join(', ') : '');
      col.append(hit);
      if (w.all && F.step >= 26) { const t = mk('text', { x: x + barW / 2, y: F.y(w.all) - 5, 'text-anchor': 'middle' }); t.textContent = w.all; t.style.fill = 'var(--fg)'; col.append(t); }
      const every = Math.ceil(44 / F.step);
      if ((weeks.length - 1 - i) % every === 0) { const lab = mk('text', { x: x + barW / 2, y: H2 - 6, 'text-anchor': 'middle' }); lab.textContent = fmt(w.t).slice(0, 5); F.plot.append(lab); }
    });
  }

  function spark(host, dayCounts, from, color, who) {
    const n = AS_OF - from + 1;
    if (n <= 0) { host.replaceChildren(); return; }
    const top = maxOf(dayCounts.values(), 1);
    const F = frame(host, { count: n, minStep: DAY_STEP, height: 40, yMax: top, yStep: top, pad: { t: 2, b: 0 }, axis: false, key: 'spark:' + who });
    F.plot.classList.add('hlg');
    for (let i = 0; i < n; i++) {
      const d = from + i, v = dayCounts.get(d) || 0, hh = Math.max(v ? 2 : 1, v / top * 36);
      const r = mk('rect', { class: 'hl', x: i * F.step + 0.75, y: 40 - hh, width: Math.max(1, F.step - 1.5), height: hh, fill: v ? css(color) : 'var(--grid)' });
      r.dataset.tip = `${who} · ${fmt(d)}: закрыто ${v}`; F.plot.append(r);
    }
  }

  /* ---------- блоки ---------- */
  function renderHead() {
    const N = recs.length, pct = n => (N ? Math.round(n / N * 100) : 0);
    const tds = recs.map(r => r.tdateD).filter(d => d !== null).sort((a, b) => a - b);
    $('period').textContent = tds.length ? `Период задач: ${fmt(tds[0])} — ${fmt(tds[tds.length - 1])}` : 'Период: даты задач не найдены';
    $('asof').textContent = `на ${fmt(AS_OF)}`;
    const where = DATA.meta.sheet == null ? 'CSV' : `лист «${DATA.meta.sheet}»`;
    $('src').textContent = `${DATA.meta.source}, ${where}, шапка в строке ${DATA.meta.header_row}; cvesummary ${DATA.meta.version}`;
    /* set — из образца: значение плитки, мини-полоса и процент */
    const set = (id, n, color) => {
      const v = $(id); v.textContent = n; const tile = v.parentElement;
      tile.querySelectorAll('.mini,.pc').forEach(x => x.remove());
      const m = el('div', 'mini'); const i = el('i'); i.style.width = pct(n) + '%'; i.style.color = color || '#8FA6B8'; m.append(i);
      m.dataset.tip = `${n} из ${N} задач`;
      tile.append(m, el('span', 'pc', `${pct(n)}% от всех`));
    };
    const open = recs.filter(r => r.open), working = recs.filter(r => r.working);
    const ready = open.filter(r => r.reasons.length);
    $('k-total').textContent = N;
    const u = roles.uniques(recs);
    $('k-cve').textContent = u.tasks;
    $('k-comp').textContent = u.comps;
    set('k-closed', recs.filter(r => r.done).length, '#5CC48A');
    set('k-work', working.length, '#5DB3D6');
    const review = working.filter(r => r.review).length, paused = working.filter(r => r.paused).length;
    const wl = $('k-work-l');
    wl.textContent = `в работе · ревью ${review} · пауза ${paused}`;
    wl.dataset.tip = `в работе ${working.length}, из них на ревью ${review}, на паузе ${paused}`;
    set('k-free', recs.filter(r => !r.taken && !r.done).length, '#8FA6B8');
    $('k-ready').textContent = `${ready.length} задач · ${pct(ready.length)}% от всех`;
    set('k-fixed', ready.filter(r => r.reasons.includes('fixed')).length, '#BFE3F2');
    set('k-own', ready.filter(r => r.reasons.includes('patch')).length, '#7FC6E4');
    set('k-out', ready.filter(r => r.reasons.includes('range')).length, '#3E9CC4');
    set('k-dup', ready.filter(r => r.reasons.includes('dup')).length, '#9AA9D6');
    set('k-ci', open.filter(r => r.sevN === 'Critical' || r.sevN === 'Important').length, '#FF8A6B');
    set('k-att', recs.filter(r => r.attention).length, '#FF8A6B');
    const s = Hm.summary(closedWithHours(recs));
    $('k-hours').textContent = s.n ? f1(s.mean) : '—';
    $('k-hours-l').textContent = s.n ? `часов на задачу, медиана ${f1(s.median)} · по ${s.n} задачам` : 'часов на задачу: закрытых с датами нет';

    /* каждая задача — в одном сегменте: по первому основанию закрыть,
       основания идут в порядке fixed, patch, range, dup */
    const grp = [
      { k: 'Готово', c: '#5CC48A', f: r => r.done },
      { k: 'Фикс в RHEL', c: '#BFE3F2', f: r => r.open && r.reasons[0] === 'fixed' },
      { k: 'Устранено ранее', c: '#7FC6E4', f: r => r.open && r.reasons[0] === 'patch' },
      { k: 'Вне диапазона', c: '#3E9CC4', f: r => r.open && r.reasons[0] === 'range' },
      { k: 'Дубликат', c: '#9AA9D6', f: r => r.open && r.reasons[0] === 'dup' },
      { k: 'Без решения', c: '#FF8A6B', f: r => r.open && !r.reasons.length },
    ];
    const mb = $('mixbar'), ml = $('mixleg'); mb.replaceChildren(); ml.replaceChildren();
    for (const g of grp) {
      const n = recs.filter(g.f).length; if (!n) continue;
      const sp = el('span', null, pct(n) >= 8 ? pct(n) + '%' : ''); sp.style.flexGrow = n; sp.style.background = g.c; sp.dataset.tip = `${g.k}: ${n} из ${N} (${pct(n)}%)`; mb.append(sp);
      const li = el('span'); const sw = el('i', 'sw'); sw.style.background = g.c; li.append(sw, `${g.k} `, el('b', null, `${n}`), ` · ${pct(n)}%`); ml.append(li);
    }
    const P = recs.filter(r => String(r.p).trim() === '+').length, D = recs.filter(r => String(r.d).trim() === '+').length;
    $('pd').textContent = `P отмечен у ${P}, D у ${D} из ${N} задач`;
  }

  /* statTable — из образца; колонка «Ср. срок» → «Ср. часов» по закрытым */
  function statTable(boxId, title, groups) {
    const box = $(boxId); box.replaceChildren(); const mx = maxOf(groups.map(g => g.recs.length), 1);
    const mob = matchMedia('(max-width:560px)').matches;
    [[title, 'h l'], ['', 'h bar'], ['Всего', 'h'], ['Открыто', 'h'], ['Готово', 'h'], ['% готово', 'h'], ['Ср. часов', 'h']].forEach(([x, c]) => {
      const h = el('div', c, x);
      if (c === 'h bar') { const lg = el('div', 'cve-leg'); const a = el('span'); const i1 = el('i'); i1.style.background = css(groups[0]?.c || '--muted'); a.append(i1, 'готово'); const b = el('span'); const i2 = el('i', 'lite'); i2.style.background = css(groups[0]?.c || '--muted'); b.append(i2, 'не готово'); lg.append(a, b); h.append(lg); }
      box.append(h);
    });
    if (!groups.length) { const e = el('div', 'p', 'Нет данных'); e.style.gridColumn = '1/-1'; e.style.textAlign = 'left'; box.append(e); return; }
    for (const g of groups) {
      const n = g.recs.length, closed = g.recs.filter(r => r.done).length, opn = g.recs.filter(r => r.open).length;
      const s = Hm.summary(closedWithHours(g.recs));
      const k = el('div', 'k'); const i = el('i'); i.style.background = css(g.c); k.append(i, g.k); k.title = g.k;
      const b = el('div', 'b'); const w = el('span'); w.style.width = (n / mx * 100) + '%';
      const c1 = el('span'); c1.style.flexGrow = closed; c1.style.background = css(g.c);
      const c2 = el('span'); c2.style.flexGrow = n - closed; c2.style.background = css(g.c); c2.style.opacity = '.3';
      w.append(c1, c2); b.append(w); b.dataset.tip = `${g.k}: готово ${closed}, открыто ${opn}`;
      const cells = [k, b, el('div', 'n', String(n)), el('div', 'n', String(opn)), el('div', 'n', String(closed)), el('div', 'p', (n ? Math.round(closed / n * 100) : 0) + '%'), el('div', 'n', s.n ? f1(s.mean) + ' ч' : '—')];
      if (s.n) cells[6].dataset.tip = `Среднее по ${s.n} закрытым задачам, медиана ${f1(s.median)} ч`;
      if (mob) box.append(cells[0], ...cells.slice(2), cells[1]); else cells.forEach(x => box.append(x));
    }
  }

  function renderCuts() {
    const N = recs.length;
    const sevC = SEV.map(s => Object.assign({}, s, { recs: recs.filter(r => r.sevN === s.k) }));
    const strip = $('sevstrip'); strip.replaceChildren();
    for (const s of sevC) { if (!s.recs.length) continue; const sp = el('span'); sp.style.flexGrow = s.recs.length; sp.style.background = css(s.c); sp.dataset.tip = `${s.k}: ${s.recs.length} (${Math.round(s.recs.length / N * 100)}%)`; strip.append(sp); }
    statTable('sevrows', 'Критичность', sevC);
    const palette = ['--accent', '--c3', '--c4', '--c7', '--c5', '--c2'];
    const keys = roles.measureOrder(recs.map(r => r.measureN)).filter(k => k !== roles.NO_MEASURE);
    const mg = keys.map((k, i) => ({ k, c: palette[i % palette.length], recs: recs.filter(r => r.measureN === k) }));
    statTable('measrows', 'Мера', mg);
    const st = $('measstrip'); st.replaceChildren(); const tot = mg.reduce((a, g) => a + g.recs.length, 0);
    for (const g of mg) { const sp = el('span'); sp.style.flexGrow = g.recs.length; sp.style.background = css(g.c); sp.dataset.tip = `${g.k}: ${g.recs.length} (${tot ? Math.round(g.recs.length / tot * 100) : 0}%)`; st.append(sp); }
  }

  function pill(r) { const p = el('span', 'pill'); const i = el('i'); i.style.background = css(sevColor(r.sevN)); p.append(i, r.sevN); const td = el('td'); td.append(p); return td; }
  function cveCell(r) { const td = el('td', 'mono'); td.append(link(r.link, r.cve) || r.cve); return td; }
  function emptyRow(body, cols, text) { const tr = el('tr'); const td = el('td', 'empty', text); td.colSpan = cols; tr.append(td); body.append(tr); }
  const byCvss = (a, b) => b.cvssN - a.cvssN || a.cve.localeCompare(b.cve);

  function renderTables() {
    const att = recs.filter(r => r.attention).sort(byCvss);
    $('att-n').textContent = att.length;
    const tb = $('att-body'); tb.replaceChildren();
    if (!att.length) emptyRow(tb, 9, 'Задач со статусом «Есть проблема» или «Нужна доработка» нет');
    for (const r of att) {
      const c6 = el('td', 'mono'); c6.append(link(r.rhsa, r.rhnvr || r.rhsa.split('/').pop()) || r.rhnvr || '—');
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), el('td', null, r.rstate || '—'), c6, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      tb.append(tr);
    }

    const ready = recs.filter(r => r.open && r.reasons.length);
    const why = [['Фикс в RHEL (RHEL state = Fixed)', 'fixed', '--ok'], ['Устранено ранее (P = +)', 'patch', '--accent'], ['Версия вне уязвимого диапазона (D = +)', 'range', '--sev-none'], ['Дубликат (та же пара CVE + компонент)', 'dup', '--c7']];
    hbars('close-why', why.map(([l, k, c]) => { const n = ready.filter(r => r.reasons.includes(k)).length; return { label: l, n, segs: [{ n, color: c, name: '' }] }; })
      .concat([{ label: 'Всего задач', n: ready.length, segs: [{ n: ready.length, color: '--fg', name: '' }] }]), Math.max(1, ready.length));
    $('close-n').textContent = ready.length;
    const cb = $('close-body'); cb.replaceChildren();
    if (!ready.length) emptyRow(cb, 8, 'Открытых задач с готовым решением нет');
    for (const r of [...ready].sort(byCvss)) {
      const c5 = el('td'); c5.style.display = 'flex'; c5.style.gap = '6px';
      if (r.reasons.includes('fixed')) c5.append(link(r.rhsa, r.rhnvr || 'RHEL Fixed', 'pill') || el('span', 'pill', r.rhnvr || 'RHEL Fixed'));
      if (r.reasons.includes('patch')) c5.append(el('span', 'pill', 'устранено ранее'));
      if (r.reasons.includes('range')) c5.append(el('span', 'pill', 'вне диапазона'));
      if (r.reasons.includes('dup')) {
        const main = recs[r.dupOf], p = el('span', 'pill', 'дубликат');
        p.dataset.tip = `основная — строка ${main.row}` + (main.task ? `, ${main.task}` : '') + (main.done ? ', готова' : '');
        c5.append(p);
      }
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), c5, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      cb.append(tr);
    }
  }

  function renderBars() {
    const comps = count(recs, r => r.comp).slice(0, 12);
    hbars('components', comps.map(([c, n]) => ({ label: c, n, segs: SEV.map(s => ({ name: s.k, color: s.c, n: recs.filter(r => r.comp === c && r.sevN === s.k).length })) })), comps.length ? comps[0][1] : 1);
    legend('compleg', SEV);
    const rs = count(recs, r => r.rstate || 'не указано');
    const rsColor = k => ({ fixed: '--ok', affected: '--bad', 'under investigation': '--warn', 'fix deferred': '--warn' })[k.toLowerCase()] || '--sev-none';
    hbars('rhel', rs.map(([k, n]) => ({ label: k, n, segs: [{ n, color: rsColor(k), name: '' }] })), rs.length ? rs[0][1] : 1);
    const ds = count(recs, statusKey);
    const dsColor = k => roleColor(recs.find(r => statusKey(r) === k));
    hbars('devstatus', ds.map(([k, n]) => ({ label: k, n, segs: [{ n, color: dsColor(k), name: '' }] })), ds.length ? ds[0][1] : 1);
    legend('weekleg', SEV);
    stackChart($('weeks'), weeksOf(recs.map(r => [r.tdateD, r.sevN]), SEV), SEV, 'поступило');
  }

  function renderPace() {
    const WIN = +$('pace-win').value || 14;
    const R = pace.rates(recs, AS_OF, WIN);
    const ready = recs.filter(r => r.open && r.reasons.length).length;
    const fc = $('forecast'); fc.replaceChildren();
    $('pace-sub').textContent = `На ${fmt(AS_OF)} · темп за ${days(WIN)}`;
    $('pace-note').textContent = `Точка отсчёта — дата отчёта (${fmt(AS_OF)}). Закрытой считается задача со статусом «Готов» и заполненным End date. Дни календарные. До сканфриза новые задачи прибывают в текущем темпе.`;
    $('p-in').textContent = f1(R.inR);
    $('p-out').textContent = f1(R.outR);
    const pn = $('p-net'); pn.textContent = (R.net > 0 ? '−' : R.net < 0 ? '+' : '') + f1(Math.abs(R.net)); pn.className = 'v ' + (R.net > 0 ? 'ok' : R.net < 0 ? 'bad' : '');
    $('p-net-l').textContent = R.net > 0 ? 'бэклог сокращается в день' : R.net < 0 ? 'бэклог растёт в день' : 'бэклог не меняется';
    $('p-open').textContent = R.open;
    const sd = $('stop-date'), td = $('target-date');
    if (!sd.value) sd.value = LS.get('cve.stopDate');
    if (!td.value) td.value = LS.get('cve.targetDate') || dates.isoOf(AS_OF + 30);
    const stop = dates.dayOf(sd.value), target = dates.dayOf(td.value);
    /* row — из образца, дни вместо миллисекунд */
    const row = (title, d, sub, main, n) => {
      const r = el('div', main ? 'fc-main' : 'fc-row');
      /* главная строка при нуле открытых — «завершено»; у остальных строк
         ноль значит другое и пока подписан по-старому */
      const dt = d === 0 ? (main ? el('div', 'd ok', 'завершено 🎉') : el('div', 'd', 'уже 0')) : d === null ? el('div', 'd bad', 'не завершится') : el('div', 'd', fmt(AS_OF + d));
      const meta = el('div', 's', (d ? `${n} задач · ≈ ${days(d)}. ` : '') + sub);
      if (main) r.append(el('div', 'e', title), dt, meta); else r.append(el('div', 't', title), dt, meta);
      fc.append(r);
    };
    if (stop !== null) {
      const inflowDays = Math.max(0, stop - AS_OF - 1), coming = Math.round(R.inR * inflowDays);
      row(`Сканфриз ${fmt(stop)}`, pace.simulate(R.open, R.inR, R.outR, AS_OF, stop),
        R.open === 0 ? 'Открытых задач нет.' + (coming ? ` До сканфриза придёт ещё ≈ ${coming}.` : '')
          : `До этой даты придёт ещё ≈ ${coming}, дальше только закрываем по ${f1(R.outR)} в день.`, true, R.open);
    } else {
      row('При текущем темпе, без сканфриза', R.open === 0 || R.net > 0 ? pace.simulate(R.open, R.inR, R.outR, AS_OF) : null, R.open === 0 ? 'Открытых задач нет.' : R.net > 0 ? 'Новые задачи продолжают поступать в том же темпе.' : 'Приходит не меньше, чем закрывается. Укажите дату сканфриза.', true, R.open);
    }
    row('Без задач с готовым решением', pace.simulate(R.open - ready, R.inR, R.outR, AS_OF, stop === null ? null : stop), `Если ${ready} задач с готовым решением закрыть сразу.` + (stop === null ? ' Без новых.' : ` С новыми до ${fmt(stop)}.`), false, R.open - ready);
    if (target !== null) {
      const r = el('div', 'fc-row need'); r.append(el('div', 't', `Закончить к ${fmt(target)}`));
      const nd = pace.need(R.open, R.inR, AS_OF, stop, target);
      if (nd === null) r.append(el('div', 'd bad', 'дата прошла'), el('div', 's', 'Выберите дату позже ' + fmt(AS_OF) + '.'));
      else r.append(el('div', 'd', `${f1(nd.perDay)}/день`), el('div', 's', `Нужно закрывать в день. ${days(nd.left)}, с учётом ≈ ${Math.round(nd.incoming)} новых. ${R.outR ? (nd.perDay <= R.outR ? 'Текущего темпа хватает.' : `В ${f1(nd.perDay / R.outR)} раза больше текущего.`) : ''}`));
      fc.append(r);
    }
    drawPace(FIRST === null ? [] : pace.daily(recs, FIRST, AS_OF), AS_OF - WIN);
    return WIN;
  }

  function renderPeople(WIN) {
    const devs = count(recs, r => r.devKey);
    const devColor = new Map(devs.map(([d], i) => [d, i < 8 ? `--c${i + 1}` : '--sev-none']));
    legend('statleg', [{ k: 'Готово', c: '--ok' }, { k: 'В работе', c: '--accent' }, { k: 'Ожидает ревью', c: '--c7' }, { k: 'На паузе', c: '--warn' }, { k: 'Есть проблема / Нужна доработка', c: '--bad' }]);
    const doneKeys = recs.filter(r => r.taken && r.done);
    const measKeys = roles.measureOrder(doneKeys.map(r => r.measureN));
    const ppl = $('people'); ppl.replaceChildren();
    const kvRow = (box, label, n, max, color, tipText) => {
      box.append(el('span', 'k', label));
      const b = el('span', 'b'); const s = el('span'); s.style.width = (n / max * 100) + '%'; s.style.background = css(color); b.append(s); b.dataset.tip = tipText; box.append(b);
      box.append(el('span', 'n', String(n)));
    };
    for (const [d, n] of devs) {
      const mine = recs.filter(r => r.devKey === d), done = mine.filter(r => r.done), col = devColor.get(d);
      const card = el('article', 'dev'); card.style.setProperty('--dc', css(col));
      const c1 = el('div');
      const h = el('h3'); const sw = el('i'); sw.style.background = css(col); h.append(sw, d); c1.append(h);
      const big = el('div', 'big', String(n)); big.append(el('small', null, 'задач назначено')); c1.append(big);
      const cnt = { g: done.length, rv: mine.filter(r => r.working && r.review).length, u: mine.filter(r => r.working && r.paused).length, p: mine.filter(r => r.working && r.attention).length };
      cnt.w = mine.filter(r => r.working).length - cnt.rv - cnt.u - cnt.p;
      const bar = el('div', 'pbar');
      [[cnt.g, '--ok', 'Готово'], [cnt.w, '--accent', 'В работе'], [cnt.rv, '--c7', 'Ожидает ревью'], [cnt.u, '--warn', 'На паузе'], [cnt.p, '--bad', 'Проблемы']].forEach(([k, c, s]) => { if (!k) return; const sp = el('span'); sp.style.flexGrow = k; sp.style.background = css(c); sp.dataset.tip = `${d} · ${s}: ${k}`; bar.append(sp); });
      c1.append(bar);
      const load = el('div', 'load');
      const li = (lab, v, cls) => { const s = el('span'); s.append(lab + ' ', el('b', cls || null, String(v))); load.append(s); };
      li('готово', cnt.g); li('в работе', cnt.w); li('ревью', cnt.rv); li('пауза', cnt.u); li('проблемы', cnt.p, cnt.p ? 'bad' : null);
      const hanging = (H.load.get(d) && H.load.get(d).get(AS_OF)) || 0;
      li('висит сейчас', hanging ? `${hanging}, по ${f1(Hm.HOURS_PER_DAY / hanging)} ч` : '0');
      c1.append(load);
      card.append(c1);

      const c2 = el('div'); c2.append(el('div', 'cap', `Сделано по критичности · ${done.length}`));
      const kv2 = el('div', 'kv'); const maxS = Math.max(1, ...SEV.map(s => done.filter(r => r.sevN === s.k).length));
      SEV.forEach(s => { const v = done.filter(r => r.sevN === s.k).length; if (v) kvRow(kv2, s.k, v, maxS, s.c, `${d} · ${s.k}: ${v}`); });
      c2.append(kv2);
      const c3 = el('div'); c3.append(el('div', 'cap', `Сделано по принятой мере · ${done.length}`));
      const kv3 = el('div', 'kv'); const maxM = maxOf(measKeys.map(k => done.filter(r => r.measureN === k).length), 1);
      measKeys.forEach(k => { const v = done.filter(r => r.measureN === k).length; if (v) kvRow(kv3, k, v, maxM, col, `${d} · ${k}: ${v}`); });
      c3.append(kv3);
      card.append(c2, c3);

      const c4 = el('div'); c4.append(el('div', 'cap', 'Скорость'));
      const s = Hm.summary(closedWithHours(mine));
      const closedDays = done.map(r => r.endD).filter(x => x !== null && x <= AS_OF);
      const work = H.workdays.get(d) || new Set();
      const recent = Hm.rate(closedDays, work, AS_OF - WIN + 1, AS_OF);
      const overall = Hm.rate(closedDays, work, -Infinity, AS_OF);
      const sp = el('div', 'speed');
      const sv = (v, l, t) => { const x = el('div'); x.append(el('span', 'v', v), el('span', 'l', l)); if (t) x.dataset.tip = t; sp.append(x); };
      sv(s.n ? f1(s.mean) : '—', s.n ? `ч на задачу, медиана ${f1(s.median)}` : 'ч на задачу', `По ${s.n} закрытым задачам`);
      sv(recent === null ? '—' : f1(recent), `задач за рабочий день, ${days(WIN)}`, 'Закрыто за окно / рабочих дней разработчика в окне');
      sv(overall === null ? '—' : f1(overall), 'задач за рабочий день, всего', `${closedDays.length} задач за ${work.size} рабочих дней`);
      c4.append(sp);
      const starts = mine.map(r => r.startD).filter(x => x !== null && x <= AS_OF);
      if (starts.length) {
        const sh = el('div', 'tl spark-tl'); c4.append(sh);
        const per = new Map(); closedDays.forEach(x => per.set(x, (per.get(x) || 0) + 1));
        card.append(c4); ppl.append(card);
        const first = minOf(starts, Infinity);
        spark(sh, per, first, col, d);
        c4.append(el('div', 'cap', `закрыто по дням с ${fmt(first)} по ${fmt(AS_OF)}`));
        continue;
      }
      card.append(c4); ppl.append(card);
    }
    const names = [...devColor.keys()];
    const cats = names.slice(0, 8).map(k => ({ k, c: devColor.get(k) }));
    if (names.length > 8) cats.push({ k: 'Другие', c: '--sev-none' });
    legend('burnleg', cats);
    stackChart($('burn'), weeksOf(recs.filter(r => r.done && r.taken).map(r => [r.endD, names.indexOf(r.devKey) < 8 ? r.devKey : 'Другие']), cats), cats, 'закрыто');
  }

  function renderAnomalies() {
    const label = { tdate: 'Task date', start: 'Start date', end: 'End date', fixdate: 'Fix date' };
    const items = H.anomalies.map(a => ({ r: recs[a.index], why: Hm.REASONS[a.reason] }));
    const listed = new Set(H.anomalies.map(a => a.index));
    recs.forEach(r => { if (!listed.has(r.i) && r.bad && r.bad.length) items.push({ r, why: 'не разобрана дата: ' + r.bad.map(k => label[k]).join(', ') }); });
    items.sort((a, b) => a.r.row - b.r.row);
    $('anom-n').textContent = items.length;
    const notes = $('anom-notes'); notes.replaceChildren();
    if (DATA.meta.skipped) notes.append(el('li', null, `Строк без CVE ID пропущено: ${DATA.meta.skipped}.`));
    if (DATA.meta.missing.length) notes.append(el('li', null, `Нет колонок (читаются пустыми): ${DATA.meta.missing.join(', ')}.`));
    const body = $('anom-body'); body.replaceChildren();
    if (!items.length) emptyRow(body, 8, 'Аномалий нет');
    for (const { r, why } of items) {
      const tr = el('tr');
      tr.append(el('td', 'num', String(r.row)), cveCell(r), el('td', null, r.comp), el('td', null, r.dev || '—'), el('td', null, r.status || '—'), el('td', null, r.start || '—'), el('td', null, r.end || '—'), el('td', null, why));
      body.append(tr);
    }
  }

  function render() {
    renderHead(); renderCuts(); renderTables(); renderBars();
    const WIN = renderPace();
    renderPeople(WIN); renderAnomalies();
  }

  ['stop-date', 'target-date', 'pace-win'].forEach(id => $(id).addEventListener('change', () => {
    LS.set('cve.stopDate', $('stop-date').value); LS.set('cve.targetDate', $('target-date').value); LS.set('cve.paceWin', $('pace-win').value);
    render();
  }));
  let rT; addEventListener('resize', () => { resizing = true; clearTimeout(rT); rT = setTimeout(() => { render(); setTimeout(() => { resizing = false; }, 100); }, 150); });
  { const w = LS.get('cve.paceWin'); if (['7', '14', '30'].includes(w)) $('pace-win').value = w; }
  render();
}());
