/* Темп и прогноз в задачах — как в образце сводки. Поступление — по Task
   date, закрытие — «Готов» по End date; всё, что позже даты отчёта, ещё
   не случилось. Новые задачи приходят каждый день, и в выходные: темп
   поступления — на календарный день. Закрывают по рабочим дням (Пн–Пт,
   без праздников): темп закрытия — на рабочий день. Баланс — за неделю:
   5 рабочих дней закрытия против 7 календарных поступления. */
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
    const work = dates.workdays(from + 1, asOf);
    const inR = rows.map(inDay).filter(within).length / win;
    const outR = work ? rows.map(outDay).filter(within).length / work : 0;
    return { inR, outR, net: outR * 5 - inR * 7, open: rows.filter(roles.isOpen).length };
  }

  function simulate(n, inR, outR, asOf, inflowUntil) {
    if (n <= 0) return 0;
    if (outR <= 0) return null;
    let left = n;
    for (let d = 1; d <= HORIZON; d++) {
      const day = asOf + d;
      if (inflowUntil === undefined || (inflowUntil !== null && day < inflowUntil)) left += inR;
      if (dates.isWeekend(day)) continue;
      left -= outR;
      if (left <= EPS) return d;
    }
    return null;
  }

  /* left — рабочих дней после даты отчёта до цели включительно; нет ни
     одного — perDay бесконечен. Новые — по календарным дням до сканфриза */
  function need(n, inR, asOf, stop, target) {
    if (target <= asOf) return null;
    const left = dates.workdays(asOf + 1, target);
    const inflowDays = stop === null ? target - asOf : Math.max(0, Math.min(target, stop - 1) - asOf);
    const incoming = inR * inflowDays;
    return { perDay: left ? (n + incoming) / left : Infinity, left, incoming };
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
