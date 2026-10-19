/* Темп и прогноз в задачах — как в образце сводки. Поступление — по Task
   date, закрытие — «Готов» по End date; всё, что позже даты отчёта, ещё
   не случилось. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./dates.js'), require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.pace = factory(root.CS.dates, root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles) {
  'use strict';

  const HORIZON = 3650;
  const EPS = 1e-9;

  const inDay = r => dates.dayOf(r.tdate);
  const outDay = r => (roles.isDone(r) ? dates.dayOf(r.end) : null);

  function rates(rows, asOf, win) {
    const from = asOf - win;
    const within = d => d !== null && d > from && d <= asOf;
    const inR = rows.map(inDay).filter(within).length / win;
    const outR = rows.map(outDay).filter(within).length / win;
    return { inR, outR, net: outR - inR, open: rows.filter(roles.isOpen).length };
  }

  function simulate(n, inR, outR, asOf, inflowUntil) {
    if (n <= 0) return 0;
    if (outR <= 0) return null;
    let left = n;
    for (let d = 1; d <= HORIZON; d++) {
      const day = asOf + d;
      if (inflowUntil === undefined || (inflowUntil !== null && day < inflowUntil)) left += inR;
      left -= outR;
      if (left <= EPS) return d;
    }
    return null;
  }

  function need(n, inR, asOf, stop, target) {
    const left = target - asOf;
    if (left <= 0) return null;
    const inflowDays = stop === null ? left : Math.max(0, Math.min(left, stop - asOf - 1));
    const incoming = inR * inflowDays;
    return { perDay: (n + incoming) / left, left, incoming };
  }

  function daily(rows, from, to) {
    const n = to - from + 1;
    if (n <= 0) return [];
    const s = [];
    for (let k = 0; k < n; k++) s.push({ day: from + k, i: 0, o: 0, ia: 0, oa: 0 });
    const put = (d, key) => { if (d !== null && d >= from && d <= to) s[d - from][key]++; };
    rows.forEach(r => { put(inDay(r), 'i'); put(outDay(r), 'o'); });
    s.forEach((x, k) => {
      const w = s.slice(Math.max(0, k - 6), k + 1);
      x.ia = w.reduce((a, y) => a + y.i, 0) / w.length;
      x.oa = w.reduce((a, y) => a + y.o, 0) / w.length;
    });
    return s;
  }

  return { rates, simulate, need, daily };
}));
