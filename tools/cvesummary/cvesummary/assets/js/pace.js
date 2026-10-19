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

  /* Начало работы — самая ранняя Start date у взятой задачи, не позже даты
     отчёта; нет такой — null */
  function workStart(rows, asOf) {
    let lo = null;
    for (const r of rows) {
      if (!roles.isTaken(r)) continue;
      const d = dates.dayOf(r.start);
      if (d !== null && d <= asOf && (lo === null || d < lo)) lo = d;
    }
    return lo;
  }

  /* Окно (from, end]: win дней, кончающихся в end (по умолчанию и не позже
     даты отчёта), но не раньше начала работы since; win = Infinity — весь
     период от since (нет since — от первой даты в данных). days —
     календарных дней в окне, work — рабочих. Открытые — на дату отчёта. */
  function rates(rows, asOf, win, since, end) {
    end = end === undefined || end === null ? asOf : Math.min(end, asOf);
    let from = end - win;
    if (since !== undefined && since !== null) from = Math.max(from, since - 1);
    if (!isFinite(from)) {
      const seen = rows.flatMap(r => [inDay(r), outDay(r)]).filter(d => d !== null && d <= end);
      from = seen.reduce((a, d) => Math.min(a, d), end) - 1;
    }
    from = Math.min(from, end - 1);
    const within = d => d !== null && d > from && d <= end;
    const days = end - from, work = dates.workdays(from + 1, end);
    const inR = rows.map(inDay).filter(within).length / days;
    const outR = work ? rows.map(outDay).filter(within).length / work : 0;
    return { inR, outR, net: outR * 5 - inR * 7, open: rows.filter(roles.isOpen).length, days, work };
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

  /* Накопительные ряды по дням from..to для burn-up и burn-down: всего
     поступило (inc), всего закрыто (out), открыто (open). Задача без Task
     date — в бэклоге с начала; закрыта не раньше, чем поступила; «Готов»
     без End date закрыт сразу, как поступил. Даты позже to прижимаются к
     to: на последний день открыты ровно не «Готов», как в rates().open. */
  function cumulative(rows, from, to) {
    const n = to - from + 1;
    if (n <= 0) return [];
    const inc = new Array(n).fill(0), out = new Array(n).fill(0);
    const put = (arr, d) => { arr[Math.min(n - 1, Math.max(0, d - from))]++; };
    rows.forEach(r => {
      const a = inDay(r) === null ? -Infinity : inDay(r);
      put(inc, a);
      if (roles.isDone(r)) put(out, Math.max(a, outDay(r) === null ? -Infinity : outDay(r)));
    });
    const s = [];
    let ci = 0, co = 0;
    for (let k = 0; k < n; k++) { ci += inc[k]; co += out[k]; s.push({ day: from + k, inc: ci, out: co, open: ci - co }); }
    return s;
  }

  /* Прогноз по дням после asOf тем же шагом, что simulate: поступление
     каждый день до inflowUntil, закрытие по рабочим дням. inc и out —
     прибавка к накопленному на asOf; ряд кончается, когда открытых не
     осталось, или на горизонте. */
  function project(n, inR, outR, asOf, inflowUntil, horizon) {
    const s = [];
    if (n <= 0) return s;
    let left = n, inc = 0, out = 0;
    for (let d = 1; d <= horizon; d++) {
      const day = asOf + d;
      if (inflowUntil === undefined || (inflowUntil !== null && day < inflowUntil)) { left += inR; inc += inR; }
      if (!dates.isWeekend(day)) { const c = Math.min(outR, left); left -= c; out += c; }
      if (left <= EPS) { s.push({ day, inc, out: out + left, open: 0 }); return s; }
      s.push({ day, inc, out, open: left });
    }
    return s;
  }

  return { workStart, rates, simulate, need, daily, cumulative, project };
}));
