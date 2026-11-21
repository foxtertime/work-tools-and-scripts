'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const dates = require('../../cvesummary/assets/js/dates.js');
const hours = require('../../cvesummary/assets/js/hours.js');
const pace = require('../../cvesummary/assets/js/pace.js');
const activity = require('../../cvesummary/assets/js/activity.js');
const scope = require('../../cvesummary/assets/js/scope.js');
const D = dates.dayOf('2026-11-02'); // Monday
const row = (dev, start, end = null, status = 'Готов', bad = []) => ({
  dev, start: start === null ? '' : dates.isoOf(start),
  end: end === null ? '' : dates.isoOf(end), status, bad,
});
const five = () => Array.from({ length: 5 }, () => row('X', D, D));
const state = (rows, end) => {
  const speed = scope.split(rows, end).speed;
  return activity.compute(speed, end, hours.compute(speed, end));
};
const steady = end => row('Y', D, end);
const stat = (s, name, from, to) => activity.stats(s.people.get(name), from, to, s.breaks);

test('only completed removed developer work contributes speed and workdays', () => {
  const rows = [row('X', D, D, 'Убрано из эпика'), row('X', D, null, 'Убрано из эпика'),
    row('SecOps', null, null, 'Убрано из эпика')];
  const split = scope.split(rows, D + 8), s = state(rows, D + 8), h = hours.compute(split.speed, D + 8);
  assert.equal(stat(s, 'X', D, D + 8).closed, 1);
  assert.equal(stat(s, 'X', D, D + 8).rate, 1);
  assert.equal(s.people.get('X').breaks.length, 0);
  assert.deepEqual(s.breaks, [{ from: D + 1, to: D + 8, work: 6 }]);
  assert.equal(s.people.has('SecOps'), false);
  assert.deepEqual(h.hours, [8]);
  const rates = pace.rates(split.pool, D + 8, Infinity, D, undefined, s.breaks, split.speed);
  assert.equal(rates.open, 0);
  assert.equal(rates.closed, 1);
});

test('removed SecOps with invalid End stays closed without an invented completion event', () => {
  for (const [end, bad] of [['2026-02-30', ['end']], ['2026-02-30', []], ['2026-11-02', ['end']]]) {
    const rows = [row('X', D, null, 'В работе'), { dev: 'SecOps', status: 'Убрано из эпика', start: '', end, bad }];
    const s = state(rows, D + 3);
    const split = scope.split(rows, D + 3);
    const rates = pace.rates(split.pool, D + 3, Infinity, dates.dayOf('2026-03-02'), undefined, [], split.speed);
    assert.equal(rates.open, 1);
    assert.equal(rates.closed, 0, end + ' must not invent a completion');
    assert.equal(s.people.has('SecOps'), false);
  }
});

test('personal and forecast speeds count review only with a valid observed End date', () => {
  const rows = [row('X', D, D + 1), row('X', D, D + 2, ' ОЖИДАЕТ  ревью '),
    row('X', D, null, 'Ожидает ревью'), row('X', D, D + 4, 'Ожидает ревью'),
    row('X', D, D + 1, 'Ожидает ревью', ['end']),
    { ...row('X', D, null, 'Ожидает ревью'), end: '2026-02-30' },
    row('X', D, D + 2, 'В работе'), row('X', null, D + 3, 'Ожидает ревью')];
  const s = state(rows, D + 3);
  assert.deepEqual(s.people.get('X').closedDays, [D + 1, D + 2, D + 3]);
  assert.deepEqual(stat(s, 'X', D, D + 3), { closed: 3, work: 4, cut: 0, rate: 0.75 });
  assert.deepEqual(activity.team(s, D, D + 3), { outR: 0.75, active: 1, total: 1 });
  assert.equal(stat(s, 'X', D, D + 1).closed, 1);
});

test('five tasks then three idle days: speed 5/4, other people do not change it', () => {
  for (const others of [[], [steady(D + 3), row('Z', D, D + 3)]]) {
    const s = state([...five(), ...others], D + 3);
    assert.equal(stat(s, 'X', D, D + 3).rate, 1.25);
    assert.equal(stat(s, 'X', D + 1, D + 3).rate, 0);
    assert.equal(stat(s, 'X', D + 1, D + 3).work, 3);
  }
});

test('an unfinished task does not change the denominator of a short window', () => {
  const s = state([...five(), row('X', D, null, 'В работе')], D + 3);
  assert.equal(stat(s, 'X', D, D + 3).rate, 1.25);
});

test('personal and common breaks start at five idle weekdays, covering the whole idle run', () => {
  const rows = [...five(), steady(D + 8)];
  const fourth = state(rows, D + 4), fifth = state(rows, D + 7);
  assert.equal(activity.PERSONAL_BREAK_WORKDAYS, pace.BREAK_WORKDAYS);
  assert.deepEqual(fourth.people.get('X').breaks, []);
  assert.equal(stat(fourth, 'X', D, D + 4).rate, 1);
  assert.deepEqual(fifth.people.get('X').breaks, [{ from: D + 1, to: D + 7, work: 5 }]);
  assert.equal(fifth.people.get('X').current, false);
  assert.equal(stat(fifth, 'X', D, D + 7).rate, 5);
  assert.equal(stat(fifth, 'X', D + 2, D + 4).rate, null);
});

test('open work prevents personal breaks regardless of absence of completions', () => {
  const s = state([row('X', D, null, 'В работе')], D + 20);
  assert.deepEqual(s.people.get('X').breaks, []);
  assert.equal(s.people.get('X').current, true);
  assert.equal(stat(s, 'X', D, D + 20).rate, 0);
});

test('resumption follows Start date and sums all periods, tasks and days', () => {
  const rows = [...five(), ...Array.from({ length: 3 }, () => row('X', D + 9, D + 9)), steady(D + 9)];
  const s = state(rows, D + 9);
  assert.deepEqual(s.people.get('X').breaks, [{ from: D + 1, to: D + 8, work: 6 }]);
  assert.equal(s.people.get('X').current, true);
  assert.deepEqual(stat(s, 'X', D, D + 9), { closed: 8, work: 2, cut: 6, rate: 4 });
  const open = state([...five(), steady(D + 9), row('X', D + 9, null, 'В работе')], D + 9);
  assert.equal(open.people.get('X').current, true);
  assert.equal(stat(open, 'X', D, D + 9).rate, 2.5);
});

test('multiple unequal active periods use total tasks / total days', () => {
  const s = state([...five(), row('X', D + 9, D + 10), steady(D + 10)], D + 10);
  assert.equal(stat(s, 'X', D, D + 10).rate, 6 / 3);
});

test('common five-day gaps replace personal breaks without subtracting twice', () => {
  const fifth = state(five(), D + 7), sixth = state(five(), D + 8);
  assert.equal(fifth.breaks[0].work, 5);
  assert.deepEqual(fifth.people.get('X').breaks, []);
  assert.equal(stat(fifth, 'X', D, D + 7).rate, 5);
  assert.deepEqual(stat(sixth, 'X', D, D + 8), { closed: 5, work: 1, cut: 6, rate: 5 });
});

test('common break ends existing personal break and resets the five-weekday countdown afterwards', () => {
  for (const resumed of [D + 19, D + 21]) { // Saturday and Monday: weekends do not advance the new countdown.
    const rows = [...five(), row('Y', D, D + 7), row('Y', resumed, null, 'В работе'),
      row('SecOps', D, null, 'В работе')];
    const fourth = state(rows, D + 24), fifth = state(rows, D + 25);
    assert.deepEqual(fourth.breaks, [{ from: D + 8, to: resumed - 1, work: 9 }]);
    assert.deepEqual(fourth.people.get('X').breaks, [{ from: D + 1, to: D + 7, work: 5 }]);
    assert.deepEqual(stat(fourth, 'X', D, D + 24), { closed: 5, work: 5, cut: 14, rate: 1 });
    assert.equal(fourth.people.get('X').current, true);
    assert.deepEqual(activity.team(fourth, D, D + 24), { outR: resumed === D + 19 ? 1 + 1 / 11 : 1.1, active: 2, total: 2 });
    assert.deepEqual(fifth.people.get('X').breaks, [
      { from: D + 1, to: D + 7, work: 5 }, { from: resumed, to: D + 25, work: 5 },
    ]);
    assert.deepEqual(stat(fifth, 'X', D, D + 25), { closed: 5, work: 1, cut: 19, rate: 5 });
    assert.equal(fifth.people.get('X').current, false);
    assert.equal(activity.team(fifth, D, D + 25).active, 1);
    assert.equal(stat(fourth, 'X', resumed, D + 24).work, 4);
    assert.equal(stat(fifth, 'X', resumed, D + 25).rate, null);
  }
});

test('short personal idle fragments on opposite sides of a common break do not combine', () => {
  const rows = [row('X', D, D), row('Y', D, D + 3), row('Y', D + 14, null, 'В работе')];
  const fourth = state(rows, D + 17), fifth = state(rows, D + 18);
  assert.deepEqual(fourth.breaks, [{ from: D + 4, to: D + 13, work: 6 }]);
  assert.deepEqual(fourth.people.get('X').breaks, []);
  assert.deepEqual(stat(fourth, 'X', D, D + 17), { closed: 1, work: 8, cut: 6, rate: 0.125 });
  assert.deepEqual(fifth.people.get('X').breaks, [{ from: D + 14, to: D + 18, work: 5 }]);
  assert.deepEqual(stat(fifth, 'X', D, D + 18), { closed: 1, work: 4, cut: 11, rate: 0.25 });
});

test('each common break resets idle counting including people without any Start date', () => {
  for (const [task, closed] of [[row('X', null, null, 'В работе'), 0], [row('X', D, D), 1]]) {
    const s = state([task, row('Y', D, D + 3), row('Y', D + 14, D + 17),
      row('Y', D + 28, null, 'В работе')], D + 31);
    assert.deepEqual(s.breaks, [
      { from: D + 4, to: D + 13, work: 6 }, { from: D + 18, to: D + 27, work: 6 },
    ]);
    assert.deepEqual(s.people.get('X').breaks, []);
    assert.deepEqual(stat(s, 'X', D, D + 31), { closed, work: 12, cut: 12, rate: closed / 12 });
    assert.equal(s.people.get('X').current, true);
  }
});

test('weekends do not count towards threshold; actual weekend work counts in personal speed', () => {
  const s = state([row('X', D, D), row('X', D + 5, D + 5)], D + 5);
  assert.deepEqual(stat(s, 'X', D, D + 5), { closed: 2, work: 6, cut: 0, rate: 2 / 6 });
  const weekend = state(five(), D + 6);
  assert.deepEqual(weekend.people.get('X').breaks, []);
});

test('person with no Start date gets short-window zero, then an all-period personal break', () => {
  const rows = [steady(D + 8), row('X', null, null, 'В работе')];
  const short = state(rows, D + 3), long = state(rows, D + 8);
  assert.equal(stat(short, 'X', D, D + 3).rate, 0);
  assert.equal(long.people.get('X').current, false);
  assert.deepEqual(long.people.get('X').breaks, [{ from: D, to: D + 8, work: 7 }]);
  assert.equal(stat(long, 'X', D, D + 8).rate, null);
});

test('team capacity excludes absent people, includes returning people, ignores SecOps', () => {
  const rows = [...five(), steady(D + 8), row('SecOps', D, null, 'В работе')];
  const s = state(rows, D + 8), t = activity.team(s, D, D + 8);
  assert.equal(t.total, 2);
  assert.equal(t.active, 1);
  assert.equal(t.outR, 1 / 7);
  assert.equal(stat(s, 'X', D, D + 8).closed, 5);
  const returned = state([...rows, row('X', D + 9, D + 9)], D + 9);
  assert.equal(activity.team(returned, D, D + 9).active, 2);
  assert.equal(activity.team(returned, D, D + 9).outR, 3 + 1 / 8);
  const allAway = state(five(), D + 8);
  assert.equal(activity.team(allAway, D, D + 8).outR, 0);
});

test('invalid/future completion dates are not observed closures; empty data has no rate', () => {
  const rows = [row('X', D, D + 10), row('X', D, D, 'Готов', ['end'])];
  const s = state(rows, D + 3);
  assert.equal(stat(s, 'X', D, D + 3).closed, 0);
  assert.deepEqual(activity.team(state([], D), D, D), { outR: 0, active: 0, total: 0 });
  assert.equal(stat(s, 'X', D + 1, D).rate, null);
});

test('configurable break threshold preserves the existing default', () => {
  const days = new Set([D]);
  assert.equal(pace.breaks(days, D, D + 7).length, 1);
  assert.equal(pace.breaks(days, D, D + 7, 6).length, 0);
  assert.equal(pace.breaks(days, D, D + 8, 6).length, 1);
});

test('personal and forecast speeds count awaiting comment only with a valid observed End date', () => {
  const rows = [row('X', D, D + 1), row('X', D, D + 2, ' ОЖИДАЕТ  комментарий '),
    row('X', D, null, 'Ожидает комментарий'), row('X', D, D + 4, 'Ожидает комментарий'),
    row('X', D, D + 1, 'Ожидает комментарий', ['end']),
    { ...row('X', D, null, 'Ожидает комментарий'), end: '2026-02-30' },
    row('X', D, D + 2, 'В работе'), row('X', null, D + 3, 'Ожидает комментарий')];
  const s = state(rows, D + 3);
  assert.deepEqual(s.people.get('X').closedDays, [D + 1, D + 2, D + 3]);
  assert.deepEqual(stat(s, 'X', D, D + 3), { closed: 3, work: 4, cut: 0, rate: 0.75 });
  assert.deepEqual(activity.team(s, D, D + 3), { outR: 0.75, active: 1, total: 1 });
  assert.equal(stat(s, 'X', D, D + 1).closed, 1);
});
