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
  /* столько рабочих дней подряд без работы — уже перерыв, а не простой */
  const BREAK_WORKDAYS = 5;

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

  /* Перерывы в работе — отрезки [from, to] от начала работы since до даты
     отчёта, где нет ни одного дня работы (active — дни, когда на ком-то из
     команды висела задача) и рабочих дней подряд не меньше
     BREAK_WORKDAYS; хвост перед датой отчёта — тоже. Короткий простой —
     обычные дни. Дней работы нет вовсе — сравнивать не с чем, перерывов нет. */
  function breaks(active, since, asOf) {
    const out = [];
    if (since == null || !active.size) return out;
    let from = null;
    for (let d = since; d <= asOf + 1; d++) {
      const idle = d <= asOf && !active.has(d);
      if (idle && from === null) from = d;
      if (!idle && from !== null) {
        const work = dates.workdays(from, d - 1);
        if (work >= BREAK_WORKDAYS) out.push({ from, to: d - 1, work });
        from = null;
      }
    }
    return out;
  }
  const inBreak = (gaps, d) => gaps.some(g => d >= g.from && d <= g.to);

  /* Окно (from, end]: win дней, кончающихся в end (по умолчанию и не позже
     даты отчёта), но не раньше начала работы since; win = Infinity — весь
     период от since (нет since — от первой даты в данных). days —
     календарных дней в окне, work — рабочих за вычетом перерывов gaps
     (сколько вычтено — cut), closed — закрытых в окне вне перерывов, на
     них темп; closedTotal — всех закрытых в окне, для баланса очереди.
     Поступление перерывы не трогают. Открытые — на дату отчёта. */
  function rates(rows, asOf, win, since, end, gaps = []) {
    end = end === undefined || end === null ? asOf : Math.min(end, asOf);
    let from = end - win;
    if (since !== undefined && since !== null) from = Math.max(from, since - 1);
    if (!isFinite(from)) {
      const seen = rows.flatMap(r => [inDay(r), outDay(r)]).filter(d => d !== null && d <= end);
      from = seen.reduce((a, d) => Math.min(a, d), end) - 1;
    }
    from = Math.min(from, end - 1);
    const within = d => d !== null && d > from && d <= end;
    const cut = gaps.reduce((a, g) => a + dates.workdays(Math.max(g.from, from + 1), Math.min(g.to, end)), 0);
    const days = end - from, work = dates.workdays(from + 1, end) - cut;
    const shut = rows.map(outDay).filter(within), closed = shut.filter(d => !inBreak(gaps, d)).length;
    const inR = rows.map(inDay).filter(within).length / days;
    const outR = work ? closed / work : 0;
    return { inR, outR, net: outR * 5 - inR * 7, open: rows.filter(roles.isOpen).length, days, work, cut, closed, closedTotal: shut.length };
  }

  // null и undefined одинаково означают отсутствие сканфриза.
  const incomingOn = (inR, stop, day) => (stop == null || day < stop ? inR : 0);
  const futureInflow = (inR, stop, day) => inR > 0 && (stop == null || day + 1 < stop);
  const finished = (left, inR, stop, day) => left <= EPS && !futureInflow(inR, stop, day);

  /* Один дневной шаг для графиков, даты завершения и остатка к цели.
     Сначала поступление, затем закрытие; свободная мощность сгорает.
     Нулевая очередь до последних поступлений не завершает ряд. */
  function* projection(n, inR, outR, asOf, stop, horizon, start) {
    let left = Math.max(0, n), inc = 0, out = 0;
    if (finished(left, inR, stop, asOf)) return;
    for (let d = 1; d <= horizon; d++) {
      const day = asOf + d, fresh = incomingOn(inR, stop, day);
      left += fresh; inc += fresh;
      if (!dates.isWeekend(day) && (start == null || day >= start)) {
        const closed = Math.min(Math.max(0, outR), left);
        left -= closed; out += closed;
      }
      if (left <= EPS) left = 0;
      yield { day, inc, out, open: left };
      if (finished(left, inR, stop, day)) return;
    }
  }

  /* start — день начала закрытия; до него задачи только поступают.
     Без сканфриза при положительном поступлении конечной даты нет. */
  function simulate(n, inR, outR, asOf, stop, start) {
    if (finished(n, inR, stop, asOf)) return 0;
    if ((inR > 0 && stop == null) || outR <= 0) return null;
    const lim = (start == null ? 0 : Math.max(0, start - asOf - 1)) + HORIZON;
    for (const p of projection(n, inR, outR, asOf, stop, lim, start)) {
      if (finished(p.open, inR, stop, p.day)) return p.day - asOf;
    }
    return null;
  }

  /* Минимальный постоянный темп для нулевой очереди к target. Проверяем
     каждый суффикс периода: будущие поступления нельзя закрыть заранее.
     Если после последнего рабочего дня приходят задачи — темп бесконечен. */
  function need(n, inR, asOf, stop, target) {
    if (target <= asOf || target > asOf + HORIZON) return null;
    let incoming = 0, left = 0, perDay = 0;
    for (let day = target; day > asOf; day--) {
      incoming += incomingOn(inR, stop, day);
      if (!dates.isWeekend(day)) left++;
      const backlog = incoming + (day === asOf + 1 ? n : 0);
      perDay = Math.max(perDay, left ? backlog / left : backlog > EPS ? Infinity : 0);
    }
    return { perDay, left, incoming };
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

  /* Ряд до завершения всего объёма или горизонта, включая временные нули. */
  function project(n, inR, outR, asOf, stop, horizon, start) {
    return [...projection(n, inR, outR, asOf, stop, horizon, start)];
  }

  /* Чистые результаты для интерфейса. Остаток на дату цели известен даже
     при бессрочном поступлении; запас — только при известном завершении. */
  function forecast(n, inR, outR, asOf, stop, target, start) {
    const days = simulate(n, inR, outR, asOf, stop, start);
    const state = days !== null ? 'dated' : inR > 0 && stop == null ? 'open-ended' : outR <= 0 ? 'stalled' : 'horizon';
    const valid = target != null && target >= asOf && target <= asOf + HORIZON;
    let remaining = null, margin = null;
    if (valid) {
      const series = project(n, inR, outR, asOf, stop, target - asOf, start);
      remaining = series.length ? series[series.length - 1].open : Math.max(0, n);
      if (days !== null) {
        const end = asOf + days;
        margin = end <= target ? dates.workdays(end + 1, target) : -dates.workdays(target + 1, end);
      }
    }
    return { days, remaining, margin, state };
  }

  function scenarios(rows, asOf, since, stop, target, end, gaps = []) {
    const to = end == null ? asOf : Math.min(end, asOf);
    return [7, 14, 30].map(window => {
      const R = rates(rows, asOf, window, since, to, gaps);
      const from = to - R.days + 1;
      return { window, from, to, closed: R.closed, rates: R,
        forecast: forecast(R.open, R.inR, R.outR, asOf, stop, target) };
    });
  }

  /* Режим «Когда начать». latestStart — самый поздний день старта (от
     завтра до цели), при котором n открытых и новые до сканфриза stop
     закрываются к target темпом rate в рабочий день; не успеть и со
     старта завтра — null. Чем позже старт, тем позже конец, поэтому
     ищем делением пополам: успеваем со старта lo, не успеваем после hi. */
  function fits(n, inR, rate, asOf, stop, target, start) {
    // сканфриза нет — новые приходят всё время, как в need()
    const d = simulate(n, inR, rate, asOf, stop, start);
    return d !== null && asOf + d <= target;
  }
  function latestStart(n, inR, rate, asOf, stop, target) {
    const ok = s => fits(n, inR, rate, asOf, stop, target, s);
    if (target <= asOf || !ok(asOf + 1)) return null;
    let lo = asOf + 1, hi = target;
    while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (ok(mid)) lo = mid; else hi = mid - 1; }
    return lo;
  }
  /* Сколько разработчиков по perDev задач в рабочий день нужно, чтобы со
     старта завтра закончить к target; рабочих дней до цели нет или темп
     нулевой — null. Верхняя граница — из need() (удваивается, пока не
     хватает), дальше делением пополам до наименьшего числа: need() считает
     ограничения поступлений и рабочих дней, в том числе у цели в выходной. */
  function devsNeeded(n, inR, perDev, asOf, stop, target) {
    if (finished(n, inR, stop, asOf)) return 0;
    if (perDev <= 0 || target <= asOf || futureInflow(inR, stop, target)) return null;
    const nd = need(n, inR, asOf, stop, target);
    if (nd === null || !nd.left || !isFinite(nd.perDay)) return null;
    const ok = k => fits(n, inR, k * perDev, asOf, stop, target, asOf + 1);
    if (ok(1)) return 1;
    let lo = 1, hi = Math.max(2, Math.ceil(nd.perDay / perDev - EPS));
    while (!ok(hi)) { lo = hi; hi *= 2; }
    while (hi - lo > 1) { const mid = Math.floor((lo + hi) / 2); if (ok(mid)) hi = mid; else lo = mid; }
    return hi;
  }

  return { HORIZON, BREAK_WORKDAYS, workStart, breaks, inBreak, rates, simulate, need, daily, cumulative, project, latestStart, devsNeeded, forecast, scenarios };
}));
