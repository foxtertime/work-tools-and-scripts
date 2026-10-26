/* Часы работы по задачам. В рабочий день разработчика его 8 часов
   делятся поровну между задачами, которые на нём висят: от Start date до
   End date включительно, у открытой — до даты отчёта. Когда внутри дня
   задача закрыта, неизвестно, поэтому день закрытия делится наравне с
   остальными. Выходной рабочий, если в этот день разработчик взял или
   закрыл задачу. Часы задачи — сумма её долей. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./dates.js'), require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.hours = factory(root.CS.dates, root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles) {
  'use strict';

  const HOURS_PER_DAY = 8;
  const REASONS = {
    'no-start': 'нет Start date',
    'end-before-start': 'End date раньше Start date',
    'done-no-end': '«Готов» без End date',
    'bad-date': 'Start date или End date не разобрана',
  };

  /* Интервал задачи или причина, по которой его нет. Не взятая задача —
     ни того, ни другого. */
  function spanOf(r, asOf) {
    if (!roles.isTaken(r)) return { span: null, reason: null };
    if ((r.bad || []).some(k => k === 'start' || k === 'end')) return { span: null, reason: 'bad-date' };
    const from = dates.dayOf(r.start), end = dates.dayOf(r.end);
    if (from === null && roles.norm(r.dev) !== 'secops') return { span: null, reason: 'no-start' };
    if (from !== null && end !== null && end < from) return { span: null, reason: 'end-before-start' };
    if (end === null && roles.isDone(r)) return { span: null, reason: 'done-no-end' };
    if (from === null || from > asOf) return { span: null, reason: null };
    return { span: { from, to: Math.min(end === null ? asOf : end, asOf), end }, reason: null };
  }

  function compute(rows, asOf) {
    const hours = rows.map(() => null);
    const anomalies = [];
    const byDev = new Map();
    rows.forEach((r, i) => {
      const { span, reason } = spanOf(r, asOf);
      if (reason) { anomalies.push({ index: i, reason }); return; }
      if (!roles.isTaken(r)) return;
      if (!span) {
        if (dates.dayOf(r.start) !== null) hours[i] = 0;
        return;
      }
      hours[i] = 0;
      const dev = roles.devOf(r);
      if (!byDev.has(dev)) byDev.set(dev, []);
      byDev.get(dev).push(Object.assign({ i }, span));
    });

    const workdays = new Map(), load = new Map();
    for (const [dev, spans] of byDev) {
      const edges = new Set();
      spans.forEach(s => { edges.add(s.from); if (s.end !== null) edges.add(s.end); });
      let lo = Infinity, hi = -Infinity;
      for (const s of spans) { if (s.from < lo) lo = s.from; if (s.to > hi) hi = s.to; }
      const days = new Set(), counts = new Map();
      for (let d = lo; d <= hi; d++) {
        const on = spans.filter(s => s.from <= d && d <= s.to);
        if (!on.length) continue;
        counts.set(d, on.length);
        if (dates.isWeekend(d) && !edges.has(d)) continue;
        days.add(d);
        const share = HOURS_PER_DAY / on.length;
        on.forEach(s => { hours[s.i] += share; });
      }
      workdays.set(dev, days);
      load.set(dev, counts);
    }
    return { hours, anomalies, workdays, load };
  }

  function summary(values) {
    const v = values.filter(x => typeof x === 'number' && isFinite(x)).sort((a, b) => a - b);
    if (!v.length) return { n: 0, mean: null, median: null };
    const mid = v.length >> 1;
    return {
      n: v.length,
      mean: v.reduce((a, b) => a + b, 0) / v.length,
      median: v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2,
    };
  }

  function rate(closedDays, workdays, from, to) {
    let worked = 0;
    workdays.forEach(d => { if (d >= from && d <= to) worked++; });
    if (!worked) return null;
    return closedDays.filter(d => d >= from && d <= to).length / worked;
  }

  return { HOURS_PER_DAY, REASONS, compute, summary, rate };
}));
