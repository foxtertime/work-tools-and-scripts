/* Отрисовка сводки. Данные — из блока #data; роли, часы, темп и ширина
   графиков, подсветка строки разделов — модули dates, roles, hours, pace,
   timeline, nav; здесь только DOM. */
(function () {
  'use strict';
  const { dates, roles, hours: Hm, pace, timeline, nav } = window.CS;
  const DATA = JSON.parse(document.getElementById('data').textContent);
  const AS_OF = dates.dayOf(DATA.meta.as_of);
  const NS = 'http://www.w3.org/2000/svg';
  const AXIS_W = 32;
  /* минимальный шаг по оси: меньше — график листается по горизонтали.
     Столбики по дням шире линий, чтобы их было видно и в них попадал курсор */
  const DAY_STEP = 10, WEEK_STEP = 28, BAR_DAY_STEP = 18;

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
  const tasks = n => `${n} ${plural(n, 'задачу', 'задачи', 'задач')}`;
  const wdays = n => `${n} ${plural(n, 'рабочий день', 'рабочих дня', 'рабочих дней')}`;
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
      const tr = el('div', 'track'), w = el('span'); w.style.width = (it.n / max * 100) + '%'; tr.append(w);
      const segs = it.segs || [{ n: it.n, color: opts.color || '--accent', name: '' }];
      for (const s of segs) { if (!s.n) continue;
        const sp = el('span'); sp.style.flexGrow = s.n; sp.style.background = css(s.color);
        sp.dataset.tip = `${it.label}${s.name ? ' · ' + s.name : ''}: ${s.n}`; w.append(sp); }
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
  /* меры — в порядке справочника, цвета общие для разреза мер и «Компонентов» */
  const MEAS_KEYS = roles.measureOrder(recs.map(r => r.measureN));
  /* 11 разных цветов — по числу мер в справочнике; чужие меры идут по кругу */
  const MEAS_PALETTE = ['--accent', '--c3', '--c4', '--c7', '--c5', '--c2', '--c1', '--c6', '--c8', '--sev-crit', '--muted'];
  const measColor = k => (k === roles.NO_MEASURE ? '--sev-none' : MEAS_PALETTE[MEAS_KEYS.filter(x => x !== roles.NO_MEASURE).indexOf(k) % MEAS_PALETTE.length]);
  /* начало работы — первая Start date у взятых задач: окно темпа не
     уходит раньше него */
  const START = pace.workStart(recs, AS_OF);
  const allDays = recs.flatMap(r => [r.tdateD, r.startD, r.endD]).filter(d => d !== null && d <= AS_OF);
  const FIRST = allDays.length ? minOf(allDays, Infinity) : null;
  const statusKey = r => String(r.status || '').trim() || (r.taken ? 'Без статуса' : 'Не взята');
  const roleColor = r => r.done ? '--ok' : r.attention ? '--bad' : r.paused ? '--warn' : r.review ? '--c7' : r.taken ? '--accent' : '--sev-none';
  const hoursText = r => (r.hours === null ? '—' : f1(r.hours));

  /* ---------- графики по времени ---------- */
  const scale = timeline.scale;
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
    /* ось шире, если не влезает число: 10000 задач — пять цифр */
    const axisW = o.axis === false ? 0 : Math.max(AXIS_W, String(o.yMax).length * 8 + 8);
    const box = el('div', 'tl-scroll');
    host.style.setProperty('--axis', axisW + 'px');  // левый градиент прокрутки — за осью
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

  /* Отметки дат на графиках темпа — отчёт, сканфриз, цель: пунктирная
     вертикаль и подпись на подложке цвета фона; близкие отметки разносятся
     по строкам. Подписи возвращаются — их добавляют поверх линий в конце. */
  function dateMarks(F, x, first, end, stop, target, start = null) {
    const marks = [[AS_OF, 'отчёт'], [stop, 'сканфриз'], [target, 'цель'], [start, 'старт']]
      .filter(([d]) => d !== null && d >= first && d <= end).sort((a, b) => a[0] - b[0]);
    const xs = marks.map(([d]) => x(d - first)), rows = timeline.lanes(xs, 64);
    return marks.map(([, label], j) => {
      const xi = xs[j];
      F.plot.append(mk('line', { x1: xi, x2: xi, y1: 8, y2: 208, class: 'vmark' }));
      const right = xi + 64 > F.width, t = mk('text', { x: right ? xi - 4 : xi + 4, y: 18 + rows[j] * 13, class: 'vlab', 'text-anchor': right ? 'end' : 'start' });
      t.textContent = label; return t;
    });
  }
  /* Выходные — светло-серая заливка во всю высоту поля, по суббот-
     воскресным отрезкам; поверх окна темпа, под сеткой и данными. */
  function weekends(F, from, n, top, bottom) {
    const g = mk('g', { class: 'wkend', fill: 'var(--weekend)' });
    for (let i = 0; i < n; i++) {
      if (!dates.isWeekend(from + i)) continue;
      let j = i; while (j + 1 < n && dates.isWeekend(from + j + 1)) j++;
      g.append(mk('rect', { x: F.step * i, y: top, width: F.step * (j - i + 1), height: bottom - top }));
      i = j;
    }
    F.plot.insertBefore(g, F.plot.querySelector('.gl'));
  }
  /* будущая дата в пределах двух лет — иначе ось до даты отчёта */
  const nearDay = d => (d !== null && d > AS_OF && d <= AS_OF + 2 * 365 ? d : AS_OF);

  /* Плановые дни после отчёта для «Потока»: поступление и закрытие по
     дням из pace.project и их среднее за 7 дней — окно захватывает
     последние дни факта, чтобы линия не прыгала на стыке */
  function planDaily(series, proj) {
    const out = [], tail = series.slice(-6);
    let pi = 0, po = 0;
    proj.forEach(p => {
      const d = { day: p.day, i: p.inc - pi, o: p.out - po, plan: true }; pi = p.inc; po = p.out;
      const w = tail.concat(out, [d]).slice(-7);
      d.ia = w.reduce((a, y) => a + y.i, 0) / w.length; d.oa = w.reduce((a, y) => a + y.o, 0) / w.length;
      out.push(d);
    });
    return out;
  }

  function drawPace(series, win, stop, target, plan) {
    const host = $('pace-chart');
    if (!series.length) { host.replaceChildren(el('div', 'empty', 'Нет дат в Task date и End date')); return; }
    /* в режиме «Когда начать» после отчёта — симуляция пунктиром */
    const fut = plan ? planDaily(series, plan.proj) : [], all = series.concat(fut);
    const { yMax, yStep } = scale(maxOf(all.map(s => Math.max(s.i, s.o)), 0));
    /* ось продолжается до сканфриза или цели — будущее пустое, но отметки видны */
    const first = series[0].day, end = Math.max(AS_OF, nearDay(stop), nearDay(target), plan ? plan.end : AS_OF), n = end - first + 1;
    const fresh = !POS.has(host.id);
    const F = frame(host, { count: n, minStep: DAY_STEP, height: 230, yMax, yStep, pad: { t: 8, b: 22 } });
    const x = i => F.step * i + F.step / 2;
    /* при первом показе дата отчёта — на 70 % ширины, а не пустое будущее */
    if (fresh) { const box = F.plot.parentNode; box.scrollLeft = Math.max(0, x(series.length - 1) - box.clientWidth * 0.7); timeline.sync(box); }
    const fi = Math.max(0, win.from - first), li = Math.min(series.length - 1, win.to - first);
    if (li >= fi) F.plot.prepend(mk('rect', { x: F.step * fi, y: 8, width: F.step * (li - fi + 1), height: 230 - 30, fill: 'var(--accent-soft)' }));
    weekends(F, first, n, 8, 208);
    const labels = dateMarks(F, x, first, end, stop, target, plan ? plan.start : null);
    const path = (k, c, w, op) => F.plot.append(mk('path', { d: series.map((s, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + F.y(s[k]).toFixed(1)).join(''), fill: 'none', stroke: c, 'stroke-width': w, 'stroke-opacity': op, 'stroke-linejoin': 'round' }));
    path('i', 'var(--sev-imp)', 1, 0.4); path('o', 'var(--ok)', 1, 0.4);
    path('ia', 'var(--sev-imp)', 2.5, 1); path('oa', 'var(--ok)', 2.5, 1);
    const l = series.length - 1;
    if (fut.length) [['ia', 'var(--sev-imp)'], ['oa', 'var(--ok)']].forEach(([k, c]) => F.plot.append(mk('path', { d: all.slice(l).map((s, j) => (j ? 'L' : 'M') + x(l + j).toFixed(1) + ',' + F.y(s[k]).toFixed(1)).join(''), fill: 'none', stroke: c, 'stroke-width': 2, 'stroke-dasharray': '6 4', 'stroke-linejoin': 'round' })));
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
      dots.forEach(([k, d]) => { d.setAttribute('cx', x(i)); d.setAttribute('cy', F.y(all[i][k])); });
      mark.classList.add('on');
    };
    F.plot.addEventListener('pointerover', e => { const h = e.target.closest('rect[data-i]'); if (h) show(+h.dataset.i); });
    F.plot.addEventListener('pointerleave', () => mark.classList.remove('on'));
    for (let i = 0; i < n; i++) {
      if ((l - i) % every !== 0) continue;
      const edge = x(i) + 18 > F.width, start = x(i) < 18;
      const t = mk('text', { x: edge ? F.width - 2 : start ? 2 : x(i), y: 230 - 8, 'text-anchor': edge ? 'end' : start ? 'start' : 'middle' });
      t.textContent = fmt(first + i).slice(0, 5); F.plot.append(t);
    }
    all.forEach((s, i) => {
      const hit = mk('rect', { x: F.step * i, y: 8, width: F.step, height: 200, fill: 'transparent', 'data-i': i });
      hit.dataset.tip = s.plan ? `${fmt(s.day)} · симуляция: поступит ${f1(s.i)}, закроем ${f1(s.o)} · среднее за 7 дней ${f1(s.ia)} / ${f1(s.oa)}`
        : `${fmt(s.day)}: поступило ${s.i}, закрыто ${s.o} · среднее за 7 дней ${f1(s.ia)} / ${f1(s.oa)}`;
      F.plot.append(hit);
    });
    labels.forEach(t => F.plot.append(t));
    F.plot.append(mark);
  }

  /* Вид графика темпа: поток (поступило и закрыто по дням), burn-up
     (накопленные итоги) или burn-down (остаток); выбор помнится */
  let paceBy = ['flow', 'up', 'down'].includes(LS.get('cve.paceBy')) ? LS.get('cve.paceBy') : 'flow', paceCtx = null;
  const BURN_HORIZON = 365, BURN_STEP = 3;
  /* третий элемент пункта — спрятать, но оставить место: легенда в обоих
     режимах одной высоты */
  function paceLegend(items) {
    const leg = $('pace-leg'); leg.replaceChildren();
    for (const [label, style, hide] of items) { const s = el('span'); const i = el('i'); i.setAttribute('style', style); s.append(i, label); if (hide) { s.style.visibility = 'hidden'; s.setAttribute('aria-hidden', 'true'); } leg.append(s); }
  }
  function drawPaceChart() {
    if (!paceCtx) return;
    for (const b of $('pace-by').querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.by === paceBy));
    if (paceBy === 'flow') {
      paceLegend([['поступило', 'background:var(--sev-imp)'], ['закрыто', 'background:var(--ok)'], ['по дням', 'background:var(--muted);height:1px;opacity:.6'], ['среднее за 7 дней', 'background:var(--muted)'],
        ['окно расчёта', 'background:var(--accent-soft);height:10px;vertical-align:-1px'],
        ['симуляция', 'background:repeating-linear-gradient(90deg,var(--muted) 0 5px,transparent 5px 8px)', !paceCtx.plan]]);
      $('pace-chart').setAttribute('aria-label', 'Поступление и закрытие задач по дням');
      drawPace(FIRST === null ? [] : pace.daily(recs, FIRST, AS_OF), paceCtx.WINDOW, paceCtx.stop, paceCtx.target, paceCtx.plan);
    } else drawBurn(paceBy);
  }

  /* Burn-up и burn-down: факт до даты отчёта сплошной линией, прогноз
     после — пунктиром той же моделью, что строки прогноза справа;
     отметки даты отчёта, сканфриза и цели; у burn-down — идеальная линия
     от сегодняшнего остатка к нулю в целевую дату */
  function drawBurn(mode) {
    const host = $('pace-chart'), up = mode === 'up';
    const legendFor = forecast => paceLegend(up
      ? [['всего поступило', 'background:var(--sev-imp)'], ['всего закрыто', 'background:var(--ok)'], [forecast, 'background:repeating-linear-gradient(90deg,var(--muted) 0 5px,transparent 5px 8px)']]
      : [['открыто', 'background:var(--accent)'], [forecast, 'background:repeating-linear-gradient(90deg,var(--accent) 0 5px,transparent 5px 8px)'],
        ['идеально к цели', 'background:repeating-linear-gradient(90deg,var(--muted) 0 2px,transparent 2px 5px)', !!paceCtx.plan]]);
    const plan = paceCtx.plan, word = plan ? 'симуляция' : 'прогноз', pre = plan ? plan.pre : 0;
    legendFor(word);
    host.setAttribute('aria-label', up ? 'Burn-up: всего поступило и всего закрыто по дням' : 'Burn-down: открытые задачи по дням');
    if (FIRST === null) { host.replaceChildren(el('div', 'empty', 'Нет дат в Task date и End date')); return; }
    const { R, stop, target } = paceCtx;
    const hist = pace.cumulative(recs, FIRST, AS_OF), last = hist[hist.length - 1];
    const proj = plan ? plan.proj : pace.project(last.open, R.inR, R.outR, AS_OF, stop !== null ? stop : undefined, BURN_HORIZON);
    if (proj.length && proj[proj.length - 1].open > 0) legendFor(`${word} — не сходится, показан год`);
    /* цель и сканфриз — в пределах двух лет, чтобы идеальная линия дошла до нуля */
    const end = Math.max(proj.length ? proj[proj.length - 1].day : AS_OF, nearDay(stop), nearDay(target), plan ? plan.end : AS_OF);
    const n = end - FIRST + 1, ai = AS_OF - FIRST;
    const at = i => (i <= ai ? hist[i] : proj[i - ai - 1]
      ? { inc: last.inc + proj[i - ai - 1].inc, out: last.out + pre + proj[i - ai - 1].out, open: proj[i - ai - 1].open } : null);
    /* идеальная линия — только в прогнозе: в симуляции до старта не закрываем */
    const ideal = i => (!plan && target !== null && target > AS_OF && i >= ai && FIRST + i <= target ? last.open * (1 - (i - ai) / (target - AS_OF)) : null);
    const keys = up ? ['inc', 'out'] : ['open'];
    let top = 0;
    for (let i = 0; i < n; i++) { const v = at(i); if (v) keys.forEach(k => { top = Math.max(top, v[k]); }); }
    const { yMax, yStep } = scale(top);
    const key = 'pace:' + mode, first = !POS.has(key);
    const F = frame(host, { count: n, minStep: BURN_STEP, height: 230, yMax, yStep, pad: { t: 8, b: 22 }, key });
    const x = i => F.step * i + F.step / 2;
    /* при первом показе вида дата отчёта — на 70 % ширины, а не хвост прогноза */
    if (first) { const box = F.plot.parentNode; box.scrollLeft = Math.max(0, x(ai) - box.clientWidth * 0.7); timeline.sync(box); }
    const line = (pts, color, w, dash) => { if (pts.length < 2) return; F.plot.append(mk('path', Object.assign({ d: pts.map(([i, v], j) => (j ? 'L' : 'M') + x(i).toFixed(1) + ',' + F.y(v).toFixed(1)).join(''), fill: 'none', stroke: color, 'stroke-width': w, 'stroke-linejoin': 'round' }, dash ? { 'stroke-dasharray': dash } : {}))); };
    weekends(F, FIRST, n, 8, 208);
    const labels = dateMarks(F, x, FIRST, end, stop, target, plan ? plan.start : null);
    const color = { inc: 'var(--sev-imp)', out: 'var(--ok)', open: 'var(--accent)' };
    const factPts = k => hist.map((v, i) => [i, v[k]]);
    const projPts = k => { const p = [[ai, last[k]]]; for (let i = ai + 1; i < n; i++) { const v = at(i); if (v) p.push([i, v[k]]); } return p; };
    if (!up) { const p = []; for (let i = ai; i < n; i++) { const v = ideal(i); if (v !== null) p.push([i, v]); } line(p, 'var(--muted)', 1.5, '2 4'); }
    keys.forEach(k => { line(projPts(k), color[k], 2, '6 4'); line(factPts(k), color[k], 2.5); });
    /* метка дня под курсором — как на графике потока */
    const mark = mk('g', { class: 'mark' });
    mark.append(mk('line', { y1: 8, y2: 208, class: 'guide' }));
    const dots = keys.map(k => { const d = mk('circle', { r: 4.5, fill: color[k], stroke: 'var(--panel)', 'stroke-width': 2 }); mark.append(d); return [k, d]; });
    const show = i => {
      const v = at(i); if (!v) return;
      mark.firstChild.setAttribute('x1', x(i)); mark.firstChild.setAttribute('x2', x(i));
      dots.forEach(([k, d]) => { d.setAttribute('cx', x(i)); d.setAttribute('cy', F.y(v[k])); });
      mark.classList.add('on');
    };
    F.plot.addEventListener('pointerover', e => { const h = e.target.closest('rect[data-i]'); if (h) show(+h.dataset.i); });
    F.plot.addEventListener('pointerleave', () => mark.classList.remove('on'));
    const every = Math.ceil(48 / F.step), R0 = v => Math.round(v);
    for (let i = 0; i < n; i++) {
      const day = FIRST + i, v = at(i);
      if ((i - ai) % every === 0) {
        const edge = x(i) + 18 > F.width, start = x(i) < 18;
        const t = mk('text', { x: edge ? F.width - 2 : start ? 2 : x(i), y: 230 - 8, 'text-anchor': edge ? 'end' : start ? 'start' : 'middle' });
        t.textContent = fmt(day).slice(0, 5); F.plot.append(t);
      }
      if (!v) continue;
      const hit = mk('rect', { x: F.step * i, y: 8, width: F.step, height: 200, fill: 'transparent', 'data-i': i });
      const when = fmt(day) + (day > AS_OF ? ` · ${word}` : '');
      const id = ideal(i);
      hit.dataset.tip = up ? `${when}: всего поступило ${R0(v.inc)}, закрыто ${R0(v.out)}, открыто ${R0(v.inc) - R0(v.out)}`
        : `${when}: открыто ${R0(v.open)}` + (id !== null && day > AS_OF ? ` · по идеальной линии ${R0(id)}` : '');
      F.plot.append(hit);
    }
    labels.forEach(t => F.plot.append(t));
    F.plot.append(mark);
  }

  function weeksOf(items, cats) {
    if (FIRST === null) return [];
    const lo = dates.mondayOf(FIRST), hi = dates.mondayOf(AS_OF), weeks = [];
    for (let t = lo; t <= hi; t += 7) { const w = { t, all: 0 }; cats.forEach(c => { w[c.k] = 0; }); weeks.push(w); }
    for (const [d, k] of items) { if (d === null || d > AS_OF || d < lo) continue; const w = weeks[(dates.mondayOf(d) - lo) / 7]; w.all++; w[k]++; }
    return weeks;
  }
  /* то же по дням: от первой даты до даты отчёта */
  function daysOf(items, cats, from = FIRST) {
    if (from === null) return [];
    const out = [];
    for (let t = from; t <= AS_OF; t++) { const w = { t, all: 0 }; cats.forEach(c => { w[c.k] = 0; }); out.push(w); }
    for (const [d, k] of items) { if (d === null || d > AS_OF || d < from) continue; const w = out[d - from]; w.all++; w[k]++; }
    return out;
  }

  /* stackChart — из образца, перенесён на frame(): x считается от F.step,
     высота — F.y, ось — в рамке. byDay — столбик на день, а не на неделю;
     opts.height и opts.key — для маленьких графиков в карточках; opts.window
     ({ from, to } — дни) — подсветка окна темпа, как на графике темпа */
  function stackChart(host, weeks, cats, what, byDay, opts = {}) {
    if (!weeks.length) { host.replaceChildren(el('div', 'empty', 'Нет данных с датами')); return; }
    const H2 = opts.height || 230;
    const { yMax, yStep } = scale(maxOf(weeks.map(w => w.all), 0));
    const F = frame(host, { count: weeks.length, minStep: byDay ? BAR_DAY_STEP : WEEK_STEP, height: H2, yMax, yStep, pad: { t: 16, b: 24 }, key: opts.key || host.id + (byDay ? ':d' : ':w') });
    const barW = Math.max(3, Math.min(56, F.step - (byDay ? 4 : 6))), GAP = barW >= 10 ? 2 : 1;
    if (opts.window) {
      const span = byDay ? 1 : 7, { from, to } = opts.window;
      const hit = weeks.map((w, i) => (w.t <= to && w.t + span - 1 >= from ? i : -1)).filter(i => i >= 0);
      if (hit.length) F.plot.prepend(mk('rect', { x: F.step * hit[0], y: 16, width: F.step * (hit[hit.length - 1] - hit[0] + 1), height: H2 - 40, fill: 'var(--accent-soft)' }));
    }
    if (byDay) weekends(F, weeks[0].t, weeks.length, 16, H2 - 24);
    F.plot.classList.add('hlg');
    weeks.forEach((w, i) => {
      /* неделя — одна группа: под курсором она яркая, остальные приглушены */
      const col = mk('g', { class: 'hl' }); F.plot.append(col);
      const x = i * F.step + (F.step - barW) / 2;
      const segs = cats.filter(s => w[s.k] > 0);
      let acc = 0;
      segs.forEach((s, j) => {
        /* сегмент стоит на верхушке нижнего (y0), зазор до следующего — сверху;
           так нижний сегмент всегда доходит до оси */
        const n = w[s.k], y0 = F.y(acc), y1 = F.y(acc + n) + (j < segs.length - 1 ? GAP : 0); acc += n;
        const h = Math.max(1, y0 - y1), top = y0 - h;
        if (j === segs.length - 1 && h > 4) { const r = Math.min(3, barW / 2); col.append(mk('path', { d: `M${x},${y0}V${top + r}Q${x},${top} ${x + r},${top}H${x + barW - r}Q${x + barW},${top} ${x + barW},${top + r}V${y0}Z`, fill: css(s.c) })); }
        else col.append(mk('rect', { x, y: top, width: barW, height: h, fill: css(s.c) }));
      });
      const hit = mk('rect', { x: i * F.step, y: 16, width: F.step, height: H2 - 40, fill: 'transparent' });
      hit.dataset.tip = `${byDay ? fmt(w.t) : 'Неделя с ' + fmt(w.t)}: ${what} ${w.all}` + (w.all ? ' · ' + cats.filter(s => w[s.k]).map(s => `${s.k} ${w[s.k]}`).join(', ') : '');
      col.append(hit);
      if (w.all && F.step >= 26) { const t = mk('text', { x: x + barW / 2, y: F.y(w.all) - 5, 'text-anchor': 'middle' }); t.textContent = w.all; t.style.fill = 'var(--fg)'; col.append(t); }
      const every = Math.ceil(44 / F.step);
      if ((weeks.length - 1 - i) % every === 0) {
        /* подпись у правого края не должна обрезаться — прижимаем её к краю */
        const cx = x + barW / 2, edge = cx + 18 > F.width;
        const lab = mk('text', { x: edge ? F.width - 2 : cx, y: H2 - 6, 'text-anchor': edge ? 'end' : 'middle' });
        lab.textContent = fmt(w.t).slice(0, 5); F.plot.append(lab);
      }
    });
  }

  /* ---------- блоки ---------- */
  function renderHead() {
    const N = recs.length, pct = n => (N ? Math.round(n / N * 100) : 0);
    const tds = recs.map(r => r.tdateD).filter(d => d !== null).sort((a, b) => a - b);
    $('period').textContent = tds.length ? `Период задач: ${fmt(tds[0])} — ${fmt(tds[tds.length - 1])}` : 'Период: даты задач не найдены';
    /* релиз из --release — перед датой отчёта и во вкладке браузера */
    const release = DATA.meta.release;
    $('asof').textContent = (release ? `${release} ` : '') + `на ${fmt(AS_OF)}`;
    if (release) document.title = `Сводка по CVE — ${release}`;
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
    $('k-total').style.setProperty('--len', String(N).length);  // кегль под число знаков — см. .total .n
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
    const crit = open.filter(r => r.sevN === 'Critical').length, imp = open.filter(r => r.sevN === 'Important').length;
    const cl = $('k-ci-l');
    cl.textContent = `Critical ${crit} · Important ${imp}`;
    cl.dataset.tip = `открытых Critical ${crit}, Important ${imp}`;
    set('k-att', recs.filter(r => r.attention).length, '#FF8A6B');
    const problem = recs.filter(r => roles.norm(r.status) === 'есть проблема').length, rework = recs.filter(r => roles.norm(r.status) === 'нужна доработка').length;
    const al = $('k-att-l');
    al.textContent = `проблема ${problem} · доработка ${rework}`;
    al.dataset.tip = `есть проблема ${problem}, нужна доработка ${rework}`;
    const s = Hm.summary(closedWithHours(recs));
    $('k-hours').textContent = s.n ? f1(s.mean) : '—';
    $('k-hours-l').textContent = s.n ? `часов на задачу, медиана ${f1(s.median)} · по\u00a0${s.n} ${plural(s.n, 'задаче', 'задачам', 'задачам')} за всё время` : 'часов на задачу: закрытых с датами нет';

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

  /* строки статусов: «готово/открыто» тут — сам статус, поэтому колонки
     другие: доля, у скольких разработчиков, вложенные часы */
  function statusTable(boxId, title, groups) {
    const box = $(boxId); box.replaceChildren(); const mx = maxOf(groups.map(g => g.recs.length), 1), N = recs.length;
    const mob = matchMedia('(max-width:560px)').matches;
    [[title, 'h l'], ['', 'h bar'], ['Всего', 'h'], ['% от всех', 'h'], ['Разраб.', 'h'], ['Часов', 'h'], ['Ср. часов', 'h']].forEach(([x, c]) => box.append(el('div', c, x)));
    if (!groups.length) { const e = el('div', 'p', 'Нет данных'); e.style.gridColumn = '1/-1'; e.style.textAlign = 'left'; box.append(e); return; }
    for (const g of groups) {
      const n = g.recs.length, devs = new Set(g.recs.map(r => r.devKey).filter(Boolean)).size;
      const hrs = g.recs.map(r => r.hours).filter(h => h !== null), sum = hrs.reduce((a, h) => a + h, 0);
      const k = el('div', 'k'); const i = el('i'); i.style.background = css(g.c); k.append(i, g.k); k.title = g.k;
      const b = el('div', 'b'); const w = el('span'); w.style.width = (n / mx * 100) + '%';
      const c1 = el('span'); c1.style.flexGrow = 1; c1.style.background = css(g.c); w.append(c1); b.append(w);
      b.dataset.tip = `${g.k}: ${n} из ${N}`;
      const cells = [k, b, el('div', 'n', String(n)), el('div', 'p', (N ? Math.round(n / N * 100) : 0) + '%'), el('div', 'n', String(devs)),
        el('div', 'n', sum ? f1(sum) + ' ч' : '—'), el('div', 'n', hrs.length && sum ? f1(sum / hrs.length) + ' ч' : '—')];
      if (sum) { cells[5].dataset.tip = 'Часы, вложенные в задачи этого статуса по модели часов'; cells[6].dataset.tip = `В среднем на задачу, по ${hrs.length} задачам с часами`; }
      if (mob) box.append(cells[0], ...cells.slice(2), cells[1]); else cells.forEach(x => box.append(x));
    }
  }

  function renderCuts() {
    const N = recs.length;
    const sevC = SEV.map(s => Object.assign({}, s, { recs: recs.filter(r => r.sevN === s.k) }));
    const strip = $('sevstrip'); strip.replaceChildren();
    for (const s of sevC) { if (!s.recs.length) continue; const sp = el('span'); sp.style.flexGrow = s.recs.length; sp.style.background = css(s.c); sp.dataset.tip = `${s.k}: ${s.recs.length} (${Math.round(s.recs.length / N * 100)}%)`; strip.append(sp); }
    statTable('sevrows', 'Критичность', sevC);
    const mg = MEAS_KEYS.filter(k => k !== roles.NO_MEASURE).map(k => ({ k, c: measColor(k), recs: recs.filter(r => r.measureN === k) }));
    statTable('measrows', 'Мера', mg);
    const st = $('measstrip'); st.replaceChildren(); const tot = mg.reduce((a, g) => a + g.recs.length, 0);
    for (const g of mg) { const sp = el('span'); sp.style.flexGrow = g.recs.length; sp.style.background = css(g.c); sp.dataset.tip = `${g.k}: ${g.recs.length} (${tot ? Math.round(g.recs.length / tot * 100) : 0}%)`; st.append(sp); }
  }

  function pill(r) { const p = el('span', 'pill'); const i = el('i'); i.style.background = css(sevColor(r.sevN)); p.append(i, r.sevN); const td = el('td'); td.append(p); return td; }
  function cveCell(r) { const td = el('td', 'mono'); td.append(link(r.link, r.cve) || r.cve); return td; }
  function emptyRow(body, cols, text) { const tr = el('tr'); const td = el('td', 'empty', text); td.colSpan = cols; tr.append(td); body.append(tr); }
  const byCvss = (a, b) => b.cvssN - a.cvssN || a.cve.localeCompare(b.cve);

  /* «Можно закрыть» сверху — как разрезы в блоке CVE: полоса (каждая задача
     один раз, по первому основанию) и строки оснований (задача может быть
     в нескольких) */
  const CLOSE_WHY = [['Фикс в RHEL', 'fixed', '--ok', 'RHEL state = Fixed'], ['Устранено ранее', 'patch', '--accent', 'P = +: патч лежит в PATCH, последний билд собран с ним'], ['Вне диапазона', 'range', '--c1', 'D = +: версия вне уязвимых диапазонов'], ['Дубликат', 'dup', '--c7', 'та же пара CVE ID + Компонент, что у основной строки']];
  function renderCloseWhy(ready) {
    const strip = $('close-strip'); strip.replaceChildren();
    const nOpen = recs.filter(r => r.open).length, pctOpen = n => (nOpen ? Math.round(n / nOpen * 100) : 0);
    for (const [label, k, c] of CLOSE_WHY) {
      const n = ready.filter(r => r.reasons[0] === k).length; if (!n) continue;
      const sp = el('span'); sp.style.flexGrow = n; sp.style.background = css(c);
      sp.dataset.tip = `${label}: ${n} из ${ready.length}`; strip.append(sp);
    }
    const box = $('close-why'); box.replaceChildren();
    [['Основание', 'h l'], ['', 'h bar'], ['Задач', 'h'], ['% открытых', 'h'], ['Взято', 'h'], ['Не взято', 'h'], ['Часов', 'h']].forEach(([x, c]) => {
      const h = el('div', c, x);
      if (c === 'h bar') { const lg = el('div', 'cve-leg'); const a = el('span'); const i1 = el('i'); i1.style.background = css('--muted'); a.append(i1, 'взято'); const b = el('span'); const i2 = el('i', 'lite'); i2.style.background = css('--muted'); b.append(i2, 'не взято'); lg.append(a, b); h.append(lg); }
      box.append(h);
    });
    const mob = matchMedia('(max-width:560px)').matches;
    const rows = CLOSE_WHY.map(([label, k, c, rule]) => ({ label, c, rule, recs: ready.filter(r => r.reasons.includes(k)) }));
    const mx = maxOf(rows.map(g => g.recs.length), 1);
    for (const g of rows) {
      const n = g.recs.length, taken = g.recs.filter(r => r.taken).length;
      const hours = g.recs.reduce((a, r) => a + (r.hours || 0), 0);
      const k = el('div', 'k'); const i = el('i'); i.style.background = css(g.c); k.append(i, g.label); k.dataset.tip = `${g.label}: ${g.rule}`;
      const b = el('div', 'b'); const w = el('span'); w.style.width = (n / mx * 100) + '%';
      const c1 = el('span'); c1.style.flexGrow = taken; c1.style.background = css(g.c);
      const c2 = el('span'); c2.style.flexGrow = n - taken; c2.style.background = css(g.c); c2.style.opacity = '.3';
      w.append(c1, c2); b.append(w); b.dataset.tip = `${g.label}: взято ${taken}, не взято ${n - taken}`;
      const cells = [k, b, el('div', 'n', String(n)), el('div', 'p', pctOpen(n) + '%'), el('div', 'n', String(taken)), el('div', 'n', String(n - taken)), el('div', 'n', hours ? f1(hours) + ' ч' : '—')];
      if (hours) cells[6].dataset.tip = 'Часы, уже вложенные в эти задачи по модели часов';
      if (mob) box.append(cells[0], ...cells.slice(2), cells[1]); else cells.forEach(x => box.append(x));
    }
  }

  function renderTables() {
    const att = recs.filter(r => r.attention).sort(byCvss);
    /* счётчик — в подписи под заголовком, жирным */
    const counted = (id, n, forms, rest) => { const p = $(id); p.replaceChildren(el('b', null, String(n)), ` ${plural(n, ...forms)}${rest}`); };
    $('nb-att').textContent = att.length;
    counted('att-sub', att.length, ['задача', 'задачи', 'задач'], ' со статусом «Есть проблема» или «Нужна доработка». Отсортировано по CVSS.');
    const tb = $('att-body'); tb.replaceChildren();
    if (!att.length) emptyRow(tb, 9, 'Задач со статусом «Есть проблема» или «Нужна доработка» нет');
    for (const r of att) {
      const c6 = el('td', 'mono'); c6.append(link(r.rhsa, r.rhnvr || r.rhsa.split('/').pop()) || r.rhnvr || '—');
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), el('td', null, r.rstate || '—'), c6, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      tb.append(tr);
    }

    const ready = recs.filter(r => r.open && r.reasons.length);
    renderCloseWhy(ready);
    $('nb-close').textContent = ready.length;
    counted('close-sub', ready.length, ['открытая задача', 'открытые задачи', 'открытых задач'], ', по которым решение уже есть; одна задача может иметь несколько оснований');
    const cb = $('close-body'); cb.replaceChildren();
    if (!ready.length) emptyRow(cb, 8, 'Открытых задач с готовым решением нет');
    for (const r of [...ready].sort(byCvss)) {
      const c5 = el('td', 'why');
      /* у пилюли основания — квадратик его цвета, как в полосе выше */
      const why = (k, p) => { const i = el('i'); i.style.background = css(CLOSE_WHY.find(w => w[1] === k)[2]); p.prepend(i); c5.append(p); return p; };
      if (r.reasons.includes('fixed')) why('fixed', link(r.rhsa, r.rhnvr || 'RHEL Fixed', 'pill') || el('span', 'pill', r.rhnvr || 'RHEL Fixed'));
      if (r.reasons.includes('patch')) why('patch', el('span', 'pill', 'устранено ранее'));
      if (r.reasons.includes('range')) why('range', el('span', 'pill', 'вне диапазона'));
      if (r.reasons.includes('dup')) {
        const main = recs[r.dupOf];
        why('dup', el('span', 'pill', 'дубликат')).dataset.tip = `основная — строка ${main.row}` + (main.task ? `, ${main.task}` : '') + (main.done ? ', готова' : '');
      }
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), c5, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      cb.append(tr);
    }
  }

  /* вердикт RHEL — RHEL state как есть; цвета общие для «Компонентов» и
     графика RHEL state, незнакомые значения — серые */
  const NO_VERDICT = 'не указано';
  const verdictOf = r => r.rstate || NO_VERDICT;
  const VERDICT_COLOR = { fixed: '--ok', affected: '--bad', 'under investigation': '--warn', 'fix deferred': '--c2', 'will not fix': '--c5', 'not affected': '--c1' };
  const verdictColor = k => VERDICT_COLOR[k.toLowerCase()] || '--sev-none';
  /* разбивка «Компонентов»: по критичности или по вердикту; выбор помнится */
  const COMP_BY = {
    sev: { of: r => r.sevN, cats: () => SEV, sub: 'критичности' },
    verdict: { of: verdictOf, cats: () => count(recs, verdictOf).map(([k]) => ({ k, c: verdictColor(k) })).sort((a, b) => (a.k === NO_VERDICT) - (b.k === NO_VERDICT)), sub: 'вердикту RHEL (RHEL state)' },
    measure: { of: r => r.measureN, cats: () => MEAS_KEYS.map(k => ({ k, c: measColor(k) })), sub: 'принятой мере' },
  };
  let compBy = COMP_BY[LS.get('cve.compBy')] ? LS.get('cve.compBy') : 'sev';

  function renderComps() {
    const mode = COMP_BY[compBy], cats = mode.cats(), of = mode.of;
    const comps = count(recs, r => r.comp);
    hbars('components', comps.map(([c, n]) => ({ label: c, n, segs: cats.map(s => ({ name: s.k, color: s.c, n: recs.filter(r => r.comp === c && of(r) === s.k).length })) })), comps.length ? comps[0][1] : 1);
    legend('compleg', cats);
    $('comp-sub').textContent = `Сколько CVE приходится на пакет, с разбивкой по ${mode.sub}. Все пакеты, по убыванию; список листается.`;
    for (const b of $('comp-by').querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.by === compBy));
  }

  /* поступление: по неделям или по дням; выбор помнится */
  let inflowBy = LS.get('cve.inflowBy') === 'day' ? 'day' : 'week';
  function renderInflow() {
    const byDay = inflowBy === 'day', items = recs.map(r => [r.tdateD, r.sevN]);
    $('weeks-sub').textContent = `По полю Task date${byDay ? '' : ', неделя начинается в понедельник'}, с разбивкой по критичности (RHEL severity)`;
    $('weeks').setAttribute('aria-label', `Количество задач по ${byDay ? 'дням' : 'неделям'}`);
    for (const b of $('inflow-by').querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.by === inflowBy));
    stackChart($('weeks'), byDay ? daysOf(items, SEV) : weeksOf(items, SEV), SEV, 'поступило', byDay);
  }

  function renderBars() {
    renderComps();
    /* состояние в RHEL и статус задач — как разрезы в блоке CVE: полоса
       состава и строки с готово/открыто и часами */
    const strip = (id, groups) => {
      const st = $(id); st.replaceChildren(); const N = recs.length;
      for (const g of groups) { const sp = el('span'); sp.style.flexGrow = g.recs.length; sp.style.background = css(g.c); sp.dataset.tip = `${g.k}: ${g.recs.length} (${N ? Math.round(g.recs.length / N * 100) : 0}%)`; st.append(sp); }
    };
    const rg = count(recs, verdictOf).map(([k]) => ({ k, c: verdictColor(k), recs: recs.filter(r => verdictOf(r) === k) }))
      .sort((a, b) => (a.k === NO_VERDICT) - (b.k === NO_VERDICT));
    strip('rhelstrip', rg); statTable('rhel', 'Состояние', rg);
    const dsColor = k => roleColor(recs.find(r => statusKey(r) === k));
    const dg = count(recs, statusKey).map(([k]) => ({ k, c: dsColor(k), recs: recs.filter(r => statusKey(r) === k) }));
    strip('statusstrip', dg); statusTable('devstatus', 'Статус', dg);
    legend('weekleg', SEV);
    renderInflow();
  }

  /* «Закончить к …»: сколько закрывать в рабочий день и хватает ли
     текущего темпа; возвращает [дата-колонка, пояснение] */
  function needText(nd, R, stop, target) {
    const out = (cls, d, s) => [el('div', cls, d), el('div', 's', s)];
    if (nd === null) return out('d bad', 'дата прошла', `Выберите дату позже ${fmt(AS_OF)}.`);
    const coming = Math.round(nd.incoming);
    const untilStop = stop !== null && stop <= target ? ` до сканфриза ${fmt(stop)}` : '';
    if (R.open === 0 && coming === 0) return out('d ok', 'не нужно', 'Открытых задач нет, новых до этой даты не ожидается.');
    if (!nd.left) return out('d bad', 'нет рабочих дней', `До ${fmt(target)} не осталось рабочих дней. Выберите дату позже.`);
    const fresh = `≈ ${coming} ${plural(coming, 'новую', 'новые', 'новых')}${untilStop}`;
    const what = R.open === 0 ? fresh : `${tasks(R.open)}` + (coming ? ` и ${fresh}` : '');
    const head = `Столько нужно закрывать в рабочий день, чтобы за ${wdays(nd.left)} закрыть ${what}.`;
    const ratio = R.outR ? nd.perDay / R.outR : Infinity;
    const now = !R.outR ? ' Сейчас задачи не закрываются.'
      : ratio <= 1 ? ` Сейчас закрываем ${f1(R.outR)} в рабочий день — темпа хватает.`
        : ratio < 2 ? ` Сейчас закрываем ${f1(R.outR)} в рабочий день — нужно на ${Math.ceil((ratio - 1) * 100)}% быстрее.`
          : ` Сейчас закрываем ${f1(R.outR)} в рабочий день — нужно в ${f1(ratio)} раза быстрее.`;
    const per = nd.perDay < 0.05 ? '< 0,1' : f1(nd.perDay);
    return out('d', `${per}/день`, (R.open === 0 ? 'Открытых задач нет. ' : '') + head + now);
  }

  /* Режим «Когда начать»: поступление — реальное за период темпа, закрытие —
     заданное: разработчиков × задач в рабочий день на одного, со дня
     старта; до старта задачи только копятся. Остальная страница — по факту. */
  let paceMode = LS.get('cve.paceMode') === 'plan' ? 'plan' : 'fact';
  function renderPlan(R, WINDOW, stop, target, shown) {
    /* по умолчанию — сколько людей закрывали задачи в период темпа и их
       средний темп; никто не закрывал — 1 человек по 1 задаче */
    const active = new Set(recs.filter(r => r.done && r.devKey && r.endD !== null && r.endD >= WINDOW.from && r.endD <= WINDOW.to).map(r => r.devKey)).size;
    const devs0 = active || 1, rate0 = active && R.outR ? Math.max(0.01, Math.round(R.outR / active * 100) / 100) : 1;
    const pdI = $('plan-devs'), prI = $('plan-rate');
    if (!pdI.value) pdI.value = LS.get('cve.planDevs') || devs0;
    if (!prI.value) prI.value = LS.get('cve.planRate') || rate0;
    /* мусор в полях — значение по умолчанию; очищенное пишется обратно,
       чтобы поле показывало то, по чему считаем */
    let devs = Math.round(+pdI.value); if (!isFinite(devs) || devs < 1) devs = devs0;
    let rate = +String(prI.value).replace(',', '.'); if (!isFinite(rate) || rate <= 0) rate = rate0;
    pdI.value = devs; prI.value = rate;
    LS.set('cve.planDevs', String(devs)); LS.set('cve.planRate', String(rate));
    const P = devs * rate, inflow = stop === null ? undefined : stop;
    const people = `${devs} ${plural(devs, 'разработчик', 'разработчика', 'разработчиков')}`;
    /* галка «без задач с готовым решением»: их закрываем сразу, считаем
       только остальные — весь правый блок и симуляция на графике */
    const readyN = recs.filter(r => r.open && r.reasons.length).length, skip = $('plan-ready').checked && readyN > 0;
    const N = skip ? R.open - readyN : R.open;
    const none = skip && R.open ? 'Все открытые задачи — с готовым решением: их осталось только закрыть.' : 'Открытых задач нет.';
    /* сколько их — в подсказке галки, а не в строках прогноза: от галки
       меняются только числа, тексты той же длины, и блок не прыгает */
    $('plan-ready').closest('label').dataset.tip = `Без задач с готовым решением (${readyN}): их закрываем сразу и в расчёт не берём`;
    const f2 = x => String(Math.round(x * 100) / 100).replace('.', ',');  // темп — до сотых, как в поле

    $('pace-sub-plan').textContent = `На ${fmt(AS_OF)} · симуляция: ${people} по ${f2(rate)} — ${f2(P)} в рабочий день; поступление — по факту с ${fmt(WINDOW.from)} по ${fmt(WINDOW.to)}`;
    $('pace-note-plan').textContent = `Симуляция на дату отчёта ${fmt(AS_OF)}: до старта задачи только поступают, со старта закрываем заданным темпом по рабочим дням, Пн–Пт, без учёта праздников. Новые приходят каждый календарный день в темпе периода с ${fmt(WINDOW.from)} по ${fmt(WINDOW.to)} (если задан сканфриз — до него). «Начать не позднее» — самый поздний день старта, при котором всё закрывается к цели. Разработчики и остальные блоки страницы считаются по фактическим данным.`;
    if (shown) {
      $('p-out').textContent = f2(P); $('p-out-l').textContent = 'по плану в рабочий день';
      $('p-out').parentElement.dataset.tip = `${people} × ${f2(rate)} в рабочий день`;
      const wk = Math.round(R.inR * 7 - P * 5), pn = $('p-net');
      pn.textContent = (wk > 0 ? '+' : wk < 0 ? '−' : '') + Math.abs(wk); pn.className = 'v ' + (wk < 0 ? 'ok' : wk > 0 ? 'bad' : '');
      $('p-net-l').textContent = 'бэклог за неделю по плану';  // знак и цвет — куда
      pn.parentElement.dataset.tip = `За неделю работы по плану: придёт ≈ ${f1(R.inR * 7)}, закроем ${f2(P * 5)}`;
    }

    const fc = $('forecast-plan'); fc.replaceChildren();
    const line = (main, title, cls, text, sub) => { const r = el('div', main ? 'fc-main' : 'fc-row'); r.append(el('div', main ? 'e' : 't', title), el('div', cls, text), el('div', 's', sub)); fc.append(r); };
    const wd = (a, b) => wdays(dates.workdays(a, b));
    /* цель дальше горизонта симуляции (10 лет) не считаем: огромный год в
       поле даты повесил бы вкладку */
    const far = target !== null && target > AS_OF + pace.HORIZON;
    const noTarget = target === null || target <= AS_OF || far;
    const askTarget = target === null ? 'Укажите дату «Хотим закончить к» — от неё считается старт.'
      : far ? 'Цель дальше чем через 10 лет — выберите дату ближе.' : `Выберите дату «Хотим закончить к» позже ${fmt(AS_OF)}.`;
    const S = N === 0 || noTarget ? null : pace.latestStart(N, R.inR, P, AS_OF, stop, target);

    /* 1. самый поздний старт */
    const T1 = 'Начать не позднее';
    if (N === 0) line(true, T1, 'd ok', skip ? 'только закрыть' : 'не нужно', none);
    else if (noTarget) line(true, T1, 'd bad', target === null ? 'нет цели' : far ? 'слишком далеко' : 'дата прошла', askTarget);
    else if (S === null) line(true, T1, 'd bad', 'не успеть', `Даже со старта завтра по ${f2(P)} в рабочий день к ${fmt(target)} не закрыть. Сколько людей нужно — ниже.`);
    else {
      const end = AS_OF + pace.simulate(N, R.inR, P, AS_OF, inflow, S);
      const c = Math.round(R.inR * Math.max(0, (stop === null ? end : Math.min(end, stop - 1)) - AS_OF));
      const fresh = c ? ` и ≈ ${c} ${plural(c, 'новую', 'новые', 'новых')}${stop !== null && stop <= end ? ' до сканфриза' : ''}` : '';
      line(true, T1, 'd', fmt(S), `Закрыть ${tasks(N)}${fresh} по ${f2(P)} в рабочий день — ≈ ${wd(S, end)}, до ${fmt(end)}.` + (S === AS_OF + 1 ? ' Начинать нужно уже завтра.' : ''));
    }

    /* 2. старт завтра */
    const T2 = 'Если начать завтра';
    const d1 = pace.simulate(N, R.inR, P, AS_OF, inflow, AS_OF + 1);
    if (d1 === 0) line(false, T2, 'd ok', skip ? 'только закрыть' : 'завершено', none);
    else if (d1 === null) line(false, T2, 'd bad', 'не завершится', `Задач приходит не меньше, чем закрываем по ${f2(P)} в рабочий день. ` + (stop === null ? 'Задайте сканфриз или увеличьте темп.' : 'Увеличьте темп.'));
    else {
      const end = AS_OF + d1, z = noTarget ? 0 : dates.workdays(end + 1, target);
      const vs = noTarget ? '' : end > target ? ` Опоздание к цели — ${wd(target + 1, end)}.` : z ? ` Запас до цели — ${wdays(z)}.` : ' Укладываемся к цели.';
      line(false, T2, !noTarget && end > target ? 'd bad' : 'd', fmt(end), `≈ ${wd(AS_OF + 1, end)}.${vs}`);
    }

    /* 3. сколько людей нужно со старта завтра */
    const T3 = 'Разработчиков нужно';
    if (N === 0) line(false, T3, 'd ok', '0', none);
    else if (noTarget) line(false, T3, 'd', '—', askTarget);
    else {
      const k = pace.devsNeeded(N, R.inR, rate, AS_OF, stop, target);
      if (k === null) line(false, T3, 'd bad', 'не успеть', `До ${fmt(target)} не осталось рабочих дней.`);
      else line(false, T3, k <= devs ? 'd ok' : 'd bad', String(k), `Чтобы закончить к ${fmt(target)}, начав завтра, по ${f2(rate)} в рабочий день на одного. ` + (k <= devs ? `Задано ${devs} — хватает.` : `Задано ${devs} — не хватает ${k - devs}.`));
    }

    /* «сколько нужно к цели» — серая строка, как «Закончить к …» в прогнозе */
    fc.lastChild.classList.add('need');

    /* старт для графика: самый поздний, а если его нет — завтра */
    const start = S !== null ? S : AS_OF + 1;
    /* год симуляции считается от старта, а не от отчёта */
    const proj = N > 0 ? pace.project(N, R.inR, P, AS_OF, inflow, start - AS_OF + BURN_HORIZON, start) : [];
    /* ось симуляции — до конца ряда и до цели, если она в горизонте */
    const pend = Math.max(proj.length ? proj[proj.length - 1].day : AS_OF, noTarget ? AS_OF : target);
    /* pre — закрытые сразу задачи с готовым решением: ступенька на burn-графиках */
    return { P, start: N > 0 ? start : null, proj, end: pend, pre: skip ? readyN : 0 };
  }

  function renderPace() {
    /* период темпа — две даты: конец не позже даты отчёта, начало не раньше
       начала работы разработчиков; перепутаны — меняются местами */
    const pf = $('pace-from'), pt = $('pace-to');
    if (!pt.value) pt.value = LS.get('cve.paceTo') || dates.isoOf(AS_OF);
    if (!pf.value) pf.value = LS.get('cve.paceFrom') || dates.isoOf(AS_OF - 13);
    let wa = dates.dayOf(pf.value), wb = dates.dayOf(pt.value);
    if (wb === null || wb > AS_OF) wb = AS_OF;
    if (wa === null) wa = wb - 13;
    if (wa > wb) [wa, wb] = [wb, wa];
    const R = pace.rates(recs, AS_OF, wb - wa + 1, START, wb);
    const WINDOW = { from: wb - R.days + 1, to: wb };
    $('pace').classList.toggle('plan', paceMode === 'plan');
    for (const b of $('pace-mode').querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.by === paceMode));
    $('p-out-l').textContent = 'закрывается в рабочий день';
    const ready = recs.filter(r => r.open && r.reasons.length).length;
    const fc = $('forecast'); fc.replaceChildren();
    $('pace-sub').textContent = `На ${fmt(AS_OF)} · темп с ${fmt(WINDOW.from)} по ${fmt(WINDOW.to)}: ${days(R.days)}, из них ${wdays(R.work)}` + (WINDOW.from > wa ? ` — начало прижато к началу работы` : '');
    $('pace-note').textContent = `Всё посчитано на дату отчёта ${fmt(AS_OF)}: темп — за выбранный период (не позже неё и не раньше начала работы разработчиков), прогноз — со следующего дня; даты в таблице позже неё не учитываются. Закрытая задача — со статусом «Готов» и заполненным End date. Новые задачи приходят каждый календарный день (до сканфриза — в текущем темпе), закрываем по рабочим дням, Пн–Пт, без учёта праздников.`;
    /* средние — за период, в подсказке — сколько это задач; баланс — сколько
       реально пришло минус закрыто за выбранный период */
    const inN = Math.round(R.inR * R.days), outN = Math.round(R.outR * R.work), bal = inN - outN;
    $('p-in').textContent = f1(R.inR);
    $('p-in').parentElement.dataset.tip = `За период поступило ${inN} за ${days(R.days)}`;
    $('p-out').textContent = f1(R.outR);
    $('p-out').parentElement.dataset.tip = `За период закрыто ${outN} за ${wdays(R.work)}`;
    const pn = $('p-net'); pn.textContent = (bal > 0 ? '+' : bal < 0 ? '−' : '') + Math.abs(bal); pn.className = 'v ' + (bal < 0 ? 'ok' : bal > 0 ? 'bad' : '');
    const span = `за ${days(R.days)}`;
    $('p-net-l').textContent = bal > 0 ? `бэклог вырос ${span}` : bal < 0 ? `бэклог сократился ${span}` : `бэклог не изменился ${span}`;
    pn.parentElement.dataset.tip = `Поступило ${inN}, закрыто ${outN}`;
    $('p-open').textContent = R.open;
    const sd = $('stop-date'), td = $('target-date');
    if (!sd.value) sd.value = LS.get('cve.stopDate');
    if (!td.value) td.value = LS.get('cve.targetDate') || dates.isoOf(AS_OF + 30);
    const stop = dates.dayOf(sd.value), target = dates.dayOf(td.value);
    /* row — из образца, дни вместо миллисекунд */
    const row = (title, d, sub, main, n) => {
      const r = el('div', main ? 'fc-main' : 'fc-row');
      /* ноль: открытых нет — «завершено» (в главной строке с эмодзи, ниже
         просто слово); открытые есть, но у всех готовое решение (строка «без
         задач с готовым решением») — «только закрыть» */
      const dt = d === 0 ? el('div', 'd ok', R.open === 0 ? (main ? 'завершено 🎉' : 'завершено') : 'только закрыть') : d === null ? el('div', 'd bad', 'не завершится') : el('div', 'd', fmt(AS_OF + d));
      /* sub-функция пишет описание целиком, строка — после «N задач · ≈ дни» */
      const meta = el('div', 's', typeof sub === 'function' ? sub(d) : (d ? `${n} ${plural(n, 'задача', 'задачи', 'задач')} · ≈ ${wdays(dates.workdays(AS_OF + 1, AS_OF + d))}. ` : '') + sub);
      if (main) r.append(el('div', 'e', title), dt, meta); else r.append(el('div', 't', title), dt, meta);
      fc.append(r);
    };
    if (stop !== null) {
      const coming = Math.round(R.inR * Math.max(0, stop - AS_OF - 1));
      row('Расчётная дата завершения', pace.simulate(R.open, R.inR, R.outR, AS_OF, stop),
        R.open === 0 ? 'Открытых задач нет.' + (coming ? ` До сканфриза придёт ещё ≈ ${coming}.` : '')
          : `До сканфриза придёт ещё ≈ ${coming}, дальше только закрываем по ${f1(R.outR)} в рабочий день.`, true, R.open);
    } else {
      row('Расчётная дата завершения', R.open === 0 || R.net > 0 ? pace.simulate(R.open, R.inR, R.outR, AS_OF) : null, R.open === 0 ? 'Открытых задач нет.' : R.net > 0 ? 'Сканфриз не задан: новые задачи поступают в текущем темпе.' : 'Сканфриз не задан, а задач приходит не меньше, чем закрывается. Укажите дату сканфриза.', true, R.open);
    }
    const rest = R.open - ready;
    const comingToStop = stop !== null ? Math.round(R.inR * Math.max(0, stop - AS_OF - 1)) : 0;
    row('Без задач с готовым решением', pace.simulate(rest, R.inR, R.outR, AS_OF, stop === null ? null : stop), d => {
      if (d === 0) return (R.open === 0 ? 'Открытых задач нет.' : `Все открытые задачи (${R.open}) — с готовым решением: их осталось только закрыть.`)
        + (comingToStop ? ` До сканфриза придёт ещё ≈ ${comingToStop}.` : '');
      const head = `Если сразу закрыть ${tasks(ready)} с готовым решением, останется ${rest}`;
      if (d === null) return `${head}, и при текущем темпе их не закрыть.`;
      const span = wdays(dates.workdays(AS_OF + 1, AS_OF + d));
      return `${head}. ` + (stop === null ? `Без новых задач — ≈ ${span}.` : `С новыми до сканфриза ${fmt(stop)} — ≈ ${span}.`);
    }, false, rest);
    if (target !== null) {
      const r = el('div', 'fc-row need'); r.append(el('div', 't', `Закончить к ${fmt(target)}`));
      r.append(...needText(pace.need(R.open, R.inR, AS_OF, stop, target), R, stop, target));
      fc.append(r);
    }
    /* оба режима собираются всегда — видимый один, другой держит место */
    const plan = paceMode === 'plan', pctx = renderPlan(R, WINDOW, stop, target, plan);
    [['pace-sub', !plan], ['pace-sub-plan', plan], ['forecast', !plan], ['forecast-plan', plan], ['pace-note', !plan], ['pace-note-plan', plan]]
      .forEach(([id, on]) => { $(id).classList.toggle('off', !on); $(id).setAttribute('aria-hidden', String(!on)); });
    paceCtx = { R, stop, target, WINDOW, plan: plan ? pctx : null };
    drawPaceChart();
    return WINDOW;
  }

  function renderPeople(W) {
    const devs = count(recs, r => r.devKey);
    const devColor = new Map(devs.map(([d], i) => [d, i < 8 ? `--c${i + 1}` : '--sev-none']));
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
      /* статусы — сеткой: метка цвета сегмента полосы, название, число;
         нулевые бледнее, но на месте, чтобы карточки не прыгали */
      const stat = el('div', 'dstat');
      [[cnt.g, '--ok', 'готово'], [cnt.w, '--accent', 'в работе'], [cnt.rv, '--c7', 'ревью'], [cnt.u, '--warn', 'пауза'], [cnt.p, '--bad', 'проблемы']].forEach(([k, c, s]) => {
        const row = el('div', k ? null : 'zero'); const i = el('i'); i.style.background = css(c);
        row.append(i, el('span', null, s), el('b', null, String(k))); stat.append(row);
      });
      c1.append(stat);
      /* нагрузка: сколько задач висит на нём в дату отчёта и сколько часов
         его дня достаётся каждой (8 ч делятся поровну) */
      /* меньше 0,1 ч — в минутах, иначе выйдет «по 0 ч» */
      const perTask = h => (h >= 0.1 ? f1(h) + ' ч' : h * 60 < 1 ? 'меньше минуты' : Math.round(h * 60) + ' мин');
      const hanging = (H.load.get(d) && H.load.get(d).get(AS_OF)) || 0;
      const now = el('div', 'dnow');
      if (hanging) {
        now.append('Сейчас на нём ', el('b', null, String(hanging)), ` ${plural(hanging, 'задача', 'задачи', 'задач')} — по `, el('b', null, perTask(Hm.HOURS_PER_DAY / hanging)), ' в день на каждую');
        const today = mine.filter(r => r.done && r.endD === AS_OF).length;
        now.dataset.tip = `Его ${Hm.HOURS_PER_DAY}-часовой рабочий день делится поровну между задачами, которые на нём висят` + (today ? `; включая закрытые сегодня: ${today}` : '');
      } else now.append('Сейчас задач на нём нет');
      c1.append(now);
      card.append(c1);

      const c3 = el('div'); c3.append(el('div', 'cap', `Сделано по принятой мере · ${done.length}`));
      /* меры — в их общих цветах; справа — сколько часов в среднем на задачу */
      const kv3 = el('div', 'kv kv4'); const maxM = maxOf(measKeys.map(k => done.filter(r => r.measureN === k).length), 1);
      kv3.append(el('span'), el('span'), el('span', 'kh', 'задач'), el('span', 'kh', 'ч на задачу'));
      measKeys.forEach(k => {
        const mk3 = done.filter(r => r.measureN === k), v = mk3.length; if (!v) return;
        kvRow(kv3, k, v, maxM, measColor(k), `${d} · ${k}: ${v}`);
        const s = Hm.summary(closedWithHours(mk3)), h = el('span', 'h', s.n ? f1(s.mean) + ' ч' : '—');
        if (s.n) h.dataset.tip = `${k}: в среднем ${f1(s.mean)} ч, медиана ${f1(s.median)} ч, по ${s.n} ${plural(s.n, 'задаче', 'задачам', 'задачам')}`;
        kv3.append(h);
      });
      c3.append(kv3);
      card.append(c3);

      const c4 = el('div'); c4.append(el('div', 'cap', 'Скорость'));
      const s = Hm.summary(closedWithHours(mine));
      const closedDays = done.map(r => r.endD).filter(x => x !== null && x <= AS_OF);
      const work = H.workdays.get(d) || new Set();
      const recent = Hm.rate(closedDays, work, W.from, W.to);
      const overall = Hm.rate(closedDays, work, -Infinity, AS_OF);
      const sp = el('div', 'speed');
      const sv = (v, l, t) => { const x = el('div'); x.append(el('span', 'v', v), el('span', 'l', l)); if (t) x.dataset.tip = t; sp.append(x); };
      sv(s.n ? f1(s.mean) : '—', s.n ? `ч на задачу, медиана ${f1(s.median)}` : 'ч на задачу', `По ${s.n} закрытым задачам`);
      sv(recent === null ? '—' : f1(recent), `задач за рабочий день, ${days(W.to - W.from + 1)}`, `Закрыто с ${fmt(W.from)} по ${fmt(W.to)} / рабочих дней разработчика за этот период`);
      sv(overall === null ? '—' : f1(overall), 'задач за рабочий день, всего', `${closedDays.length} задач за ${work.size} рабочих дней`);
      c4.append(sp);
      const starts = mine.map(r => r.startD).filter(x => x !== null && x <= AS_OF);
      if (starts.length) {
        /* закрытия по дням, столбики разбиты по принятой мере в её цветах —
           как график поступления, только меньше */
        const sh = el('div', 'tl dev-tl'); c4.append(sh);
        card.append(c4); ppl.append(card);
        /* ось у всех личных графиков общая — от начала работы, чтобы один
           день стоял на одной вертикали; прокрутка связана (см. ниже) */
        const first = START !== null ? START : minOf(starts, Infinity);
        const mcats = measKeys.map(k => ({ k, c: measColor(k) }));
        stackChart(sh, daysOf(done.map(r => [r.endD, r.measureN]), mcats, first), mcats, 'закрыто', true, { height: 130, key: 'dev:all', window: W });
        continue;
      }
      card.append(c4); ppl.append(card);
    }
    /* личные графики листаются вместе: прокрутка одного двигает остальные */
    const boxes = [...ppl.querySelectorAll('.dev-tl .tl-scroll')];
    let syncing = false;
    boxes.forEach(b => b.addEventListener('scroll', () => {
      if (syncing) return;
      syncing = true;
      boxes.forEach(o => { if (o !== b && o.scrollLeft !== b.scrollLeft) { o.scrollLeft = b.scrollLeft; timeline.sync(o); } });
      syncing = false;
    }, { passive: true }));
    const names = [...devColor.keys()];
    const cats = names.slice(0, 8).map(k => ({ k, c: devColor.get(k) }));
    if (names.length > 8) cats.push({ k: 'Другие', c: '--sev-none' });
    legend('burnleg', cats.concat([{ k: 'окно темпа', c: '--accent-soft' }]));
    burnData = { cats, window: W, items: recs.filter(r => r.done && r.taken).map(r => [r.endD, names.indexOf(r.devKey) < 8 ? r.devKey : 'Другие']) };
    renderBurn();
  }

  /* сжигание: по неделям или по дням; выбор помнится */
  let burnBy = LS.get('cve.burnBy') === 'day' ? 'day' : 'week', burnData = null;
  function renderBurn() {
    if (!burnData) return;
    const byDay = burnBy === 'day', { cats, items, window } = burnData;
    $('burn').setAttribute('aria-label', `Закрытые задачи по ${byDay ? 'дням' : 'неделям'} и разработчикам`);
    for (const b of $('burn-by').querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.by === burnBy));
    stackChart($('burn'), byDay ? daysOf(items, cats) : weeksOf(items, cats), cats, 'закрыто', byDay, { window });
  }

  function renderAnomalies() {
    const label = { tdate: 'Task date', start: 'Start date', end: 'End date', fixdate: 'Fix date' };
    const items = H.anomalies.map(a => ({ r: recs[a.index], why: Hm.REASONS[a.reason] }));
    const listed = new Set(H.anomalies.map(a => a.index));
    recs.forEach(r => { if (!listed.has(r.i) && r.bad && r.bad.length) items.push({ r, why: 'не разобрана дата: ' + r.bad.map(k => label[k]).join(', ') }); });
    items.sort((a, b) => a.r.row - b.r.row);
    $('anom-n').textContent = items.length; $('nb-anom').textContent = items.length;
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
    const W = renderPace();
    renderPeople(W); renderAnomalies();
    navSync();
  }

  /* строка разделов: подсвечен раздел, чей верх ушёл под неё (модуль nav).
     По клику подсвечен выбранный, и прокрутка до него подсветку не
     перебивает — пока она не утихнет */
  const NAV_WRAP = $('secnav').querySelector('.wrap');
  const navLinks = [...NAV_WRAP.querySelectorAll('a')];
  const navSecs = navLinks.map(a => $(a.getAttribute('href').slice(1)));
  let navK = -1, navPinned = false, navRaf = 0, navT;
  function navOn(k) {
    if (k === navK) return;
    navK = k;
    navLinks.forEach((a, i) => a.classList.toggle('on', i === k));
    /* на узком экране строка листается: подсвеченный якорь — к её середине,
       без подсветки — к началу */
    if (k < 0) { NAV_WRAP.scrollTo({ left: 0, behavior: 'smooth' }); return; }
    const a = navLinks[k].getBoundingClientRect(), w = NAV_WRAP.getBoundingClientRect();
    NAV_WRAP.scrollBy({ left: a.left + a.width / 2 - (w.left + w.width / 2), behavior: 'smooth' });
  }
  function navSync() {
    navRaf = 0;
    if (navPinned) return;
    /* раздел, к которому перешли по якорю, встаёт ровно на scroll-margin-top */
    const line = parseFloat(getComputedStyle(navSecs[0]).scrollMarginTop) + 1;
    const atBottom = innerHeight + scrollY >= document.documentElement.scrollHeight - 2;
    navOn(nav.active(navSecs.map(s => s.getBoundingClientRect().top), line, atBottom));
  }
  addEventListener('scroll', () => {
    if (navPinned) { clearTimeout(navT); navT = setTimeout(() => { navPinned = false; navSync(); }, 150); return; }
    if (!navRaf) navRaf = requestAnimationFrame(navSync);
  }, { passive: true });
  navLinks.forEach((a, i) => a.addEventListener('click', () => { navPinned = true; navOn(i); }));

  ['stop-date', 'target-date', 'pace-from', 'pace-to'].forEach(id => $(id).addEventListener('change', () => {
    LS.set('cve.stopDate', $('stop-date').value); LS.set('cve.targetDate', $('target-date').value);
    LS.set('cve.paceFrom', $('pace-from').value); LS.set('cve.paceTo', $('pace-to').value);
    render();
  }));
  $('comp-by').addEventListener('click', e => {
    const b = e.target.closest('button[data-by]');
    if (!b || b.dataset.by === compBy) return;
    compBy = b.dataset.by; LS.set('cve.compBy', compBy); renderComps();
  });
  $('inflow-by').addEventListener('click', e => {
    const b = e.target.closest('button[data-by]');
    if (!b || b.dataset.by === inflowBy) return;
    inflowBy = b.dataset.by; LS.set('cve.inflowBy', inflowBy); renderInflow();
  });
  $('burn-by').addEventListener('click', e => {
    const b = e.target.closest('button[data-by]');
    if (!b || b.dataset.by === burnBy) return;
    burnBy = b.dataset.by; LS.set('cve.burnBy', burnBy); renderBurn();
  });
  $('pace-mode').addEventListener('click', e => {
    const b = e.target.closest('button[data-by]');
    if (!b || b.dataset.by === paceMode) return;
    paceMode = b.dataset.by; LS.set('cve.paceMode', paceMode);
    /* ось у режимов разной длины — график снова встаёт на дату отчёта */
    ['pace-chart', 'pace:up', 'pace:down'].forEach(k => POS.delete(k));
    renderPace();
  });
  $('plan-ready').checked = LS.get('cve.planReady') === '1';
  ['plan-devs', 'plan-rate', 'plan-ready'].forEach(id => $(id).addEventListener('change', () => {
    LS.set('cve.planDevs', $('plan-devs').value); LS.set('cve.planRate', $('plan-rate').value);
    LS.set('cve.planReady', $('plan-ready').checked ? '1' : '0');
    renderPace();
  }));
  $('pace-by').addEventListener('click', e => {
    const b = e.target.closest('button[data-by]');
    if (!b || b.dataset.by === paceBy) return;
    paceBy = b.dataset.by; LS.set('cve.paceBy', paceBy); drawPaceChart();
  });
  let rT; addEventListener('resize', () => { resizing = true; clearTimeout(rT); rT = setTimeout(() => { render(); setTimeout(() => { resizing = false; }, 100); }, 150); });
  render();
}());
