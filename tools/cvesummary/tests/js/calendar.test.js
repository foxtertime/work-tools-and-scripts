'use strict';
const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const dates = require('../../cvesummary/assets/js/dates.js');
const hours = require('../../cvesummary/assets/js/hours.js');
const pace = require('../../cvesummary/assets/js/pace.js');
const activity = require('../../cvesummary/assets/js/activity.js');
const d = dates.dayOf;
const calendar = { years: [2025, 2026], days: {
  '2026-11-04': { working: false, label: 'День народного единства' },
  '2025-11-01': { working: true, label: 'Рабочая суббота' },
  '2025-11-03': { working: false, label: 'Перенесённый выходной' },
  '2025-11-04': { working: false, label: 'День народного единства' },
} };
const task = (start, end, extra = {}) => ({ dev: 'Алиса', start, end,
  status: end ? 'Готов' : 'В работе', tdate: start, bad: [], ...extra });
afterEach(() => dates.setCalendar());

test('holiday and working Saturday override the calendar, weekday identity stays intact', () => {
  dates.setCalendar(calendar);
  assert.equal(dates.isWeekend(d('2026-11-04')), false);
  assert.equal(dates.isNonWorking(d('2026-11-04')), true);
  assert.equal(dates.isNonWorking(d('2025-11-01')), false);
  assert.equal(dates.dayLabel(d('2026-11-04')), 'День народного единства');
  assert.equal(dates.workdays(d('2026-11-02'), d('2026-11-08')), 4);
  assert.equal(dates.workdays(d('2025-10-27'), d('2025-11-02')), 6);
  assert.equal(dates.workdays(d('2025-11-01'), d('2025-11-04')), 1);
  assert.equal(dates.workdays(d('2026-11-05'), d('2026-11-03')), 0);
  dates.setCalendar();
  assert.equal(dates.workdays(d('2026-11-02'), d('2026-11-08')), 5);
});

test('Nov 4 no longer depresses team or personal rate and does not add hours', () => {
  dates.setCalendar(calendar);
  const rows = Array.from({ length: 4 }, (_, i) => task('2026-11-02', '2026-11-06',
    { status: i ? 'Готов' : 'Ожидает ревью' }));
  const asOf = d('2026-11-06'), H = hours.compute(rows, asOf);
  const A = activity.compute(rows, asOf, H);
  assert.deepEqual(H.hours, [8, 8, 8, 8]);
  assert.equal(H.workdays.get('Алиса').has(d('2026-11-04')), false);
  const R = pace.rates(rows, asOf, Infinity, d('2026-11-02'));
  assert.equal(R.work, 4); assert.equal(R.outR, 1); assert.equal(R.closedTotal, 3);
  assert.equal(activity.stats(A.people.get('Алиса'), d('2026-11-02'), asOf).rate, 1);
  assert.equal(activity.team(A, d('2026-11-02'), asOf).outR, 1);
});

test('actual holiday work still counts, including review with End date', () => {
  dates.setCalendar(calendar);
  const rows = [task('2026-11-04', '2026-11-04', { status: 'Ожидает ревью' })];
  const asOf = d('2026-11-04'), H = hours.compute(rows, asOf);
  const A = activity.compute(rows, asOf, H);
  assert.equal(H.hours[0], 8);
  assert.equal(activity.stats(A.people.get('Алиса'), asOf, asOf).rate, 1);
  assert.equal(pace.rates(rows, asOf, 1, asOf).outR, 1);
});

test('holiday work belongs only to the developer who started or ended a task that day', () => {
  dates.setCalendar(calendar);
  for (const status of ['Готов', 'Ожидает ревью']) {
    const asOf = d('2026-11-04');
    const rows = [task('2026-11-03', ''),
      task('2026-11-03', '2026-11-04', { dev: 'Борис', status }),
      task('2026-11-04', '', { dev: 'Вера' })];
    const H = hours.compute(rows, asOf), A = activity.compute(rows, asOf, H);
    assert.deepEqual(H.hours, [8, 16, 8]);
    assert.equal(H.workdays.get('Алиса').has(asOf), false);
    assert.equal(H.workdays.get('Борис').has(asOf), true);
    assert.equal(H.workdays.get('Вера').has(asOf), true);
    assert.equal(activity.stats(A.people.get('Алиса'), asOf - 1, asOf).work, 1);
    const B = activity.stats(A.people.get('Борис'), asOf - 1, asOf);
    assert.equal(B.work, 2); assert.equal(B.closed, 1); assert.equal(B.rate, 0.5);
    assert.equal(pace.rates(rows, asOf, 2, asOf - 1).closed, 1);
  }
});

test('five-day break threshold ignores holidays', () => {
  dates.setCalendar(calendar);
  const since = d('2026-11-02'), active = new Set([since]);
  assert.deepEqual(pace.breaks(active, since, d('2026-11-09')), []);
  assert.deepEqual(pace.breaks(active, since, d('2026-11-10')),
    [{ from: since + 1, to: d('2026-11-10'), work: 5 }]);
});

test('personal countdown restarts after common break and skips the holiday', () => {
  dates.setCalendar(calendar);
  const rows = [task('2026-10-19', '2026-10-19'),
    task('2026-10-19', '2026-10-23', { dev: 'Борис' }),
    task('2026-11-02', '', { dev: 'Борис' })];
  const state = iso => activity.compute(rows, d(iso), hours.compute(rows, d(iso)));
  const fourth = state('2026-11-06'), fifth = state('2026-11-09');
  assert.deepEqual(fourth.breaks, [{ from: d('2026-10-24'), to: d('2026-11-01'), work: 5 }]);
  assert.deepEqual(fourth.people.get('Алиса').breaks, []);
  assert.equal(fourth.people.get('Алиса').current, true);
  assert.deepEqual(fifth.people.get('Алиса').breaks,
    [{ from: d('2026-11-02'), to: d('2026-11-09'), work: 5 }]);
  assert.equal(fifth.people.get('Алиса').current, false);
});

test('forecast, target capacity and latest start use holidays and working Saturdays', () => {
  dates.setCalendar(calendar);
  assert.equal(pace.simulate(1, 0, 1, d('2026-11-03'), null), 2);
  assert.equal(pace.need(1, 0, d('2026-11-03'), null, d('2026-11-04')).perDay, Infinity);
  assert.equal(pace.need(2, 0, d('2026-11-02'), null, d('2026-11-05')).left, 2);
  assert.equal(pace.latestStart(2, 0, 1, d('2026-11-02'), null, d('2026-11-05')), d('2026-11-03'));
  assert.equal(pace.forecast(1, 0, 1, d('2026-11-02'), null, d('2026-11-05')).margin, 1);
  assert.equal(pace.simulate(1, 0, 1, d('2025-10-31'), null), 1);
  assert.equal(hours.compute([task('2025-10-31', '2025-11-05')], d('2025-11-05')).hours[0], 24);
});
