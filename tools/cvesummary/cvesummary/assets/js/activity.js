/* Время наблюдения разработчиков: короткий простой входит в скорость,
   подтверждённый перерыв исключается. Часы задач считаются отдельно. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./dates.js'), require('./roles.js'), require('./pace.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.activity = factory(root.CS.dates, root.CS.roles, root.CS.pace);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles, pace) {
  'use strict';

  const PERSONAL_BREAK_WORKDAYS = pace.BREAK_WORKDAYS;
  const observedDay = (r, key) => (r.bad || []).includes(key) ? null : dates.dayOf(key === 'end' ? roles.endOf(r) : r[key]);

  function compute(rows, asOf, hours) {
    const since = pace.workStart(rows.filter(r => !(r.bad || []).includes('start')), asOf);
    const people = new Map(), active = new Set();
    for (const r of rows) {
      const name = roles.devOf(r);
      if (!name) continue;
      if (!people.has(name)) people.set(name, {
        name, since, asOf, days: hours.workdays.get(name) || new Set(), closedDays: [], breaks: [], current: false,
      });
      const end = observedDay(r, 'end');
      if (roles.isDone(r) && end !== null && end <= asOf) people.get(name).closedDays.push(end);
    }
    for (const person of people.values()) {
      if (roles.norm(person.name) !== 'secops') person.days.forEach(d => active.add(d));
      if (person.days.size) person.breaks = pace.breaks(person.days, since, asOf, PERSONAL_BREAK_WORKDAYS);
      else if (since !== null && dates.workdays(since, asOf) >= PERSONAL_BREAK_WORKDAYS) {
        person.breaks = [{ from: since, to: asOf, work: dates.workdays(since, asOf) }];
      }
    }
    const breaks = pace.breaks(active, since, asOf);
    for (const person of people.values()) {
      person.current = since !== null && !pace.inBreak(breaks, asOf) && !pace.inBreak(person.breaks, asOf);
    }
    return { since, breaks, people };
  }

  function stats(person, from, to, commonBreaks = []) {
    let work = 0, cut = 0, closed = 0;
    if (person && person.since !== null) {
      from = Math.max(from, person.since); to = Math.min(to, person.asOf);
      const gaps = commonBreaks.concat(person.breaks);
      for (let d = from; d <= to; d++) {
        if (dates.isWeekend(d) && !person.days.has(d)) continue;
        if (pace.inBreak(gaps, d)) cut++; else work++;
      }
      closed = person.closedDays.filter(d => d >= from && d <= to && !pace.inBreak(gaps, d)).length;
    }
    return { closed, work, cut, rate: work ? closed / work : null };
  }

  function team(state, from, to) {
    let outR = 0, active = 0, total = 0;
    for (const person of state.people.values()) {
      if (roles.norm(person.name) === 'secops') continue;
      total++;
      if (!person.current) continue;
      active++;
      outR += stats(person, from, to, state.breaks).rate || 0;
    }
    return { outR, active, total };
  }

  return { PERSONAL_BREAK_WORKDAYS, compute, stats, team };
}));
