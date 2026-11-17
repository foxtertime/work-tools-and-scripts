'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const scope = require('../../cvesummary/assets/js/scope.js');
const dates = require('../../cvesummary/assets/js/dates.js');
const hours = require('../../cvesummary/assets/js/hours.js');
const activity = require('../../cvesummary/assets/js/activity.js');
const D = dates.dayOf('2026-11-02');
const removed = extra => ({ dev: 'X', status: 'Убрано из эпика', start: '2026-11-02', end: '2026-11-05', ...extra });

test('pool excludes all removed rows; speed retains only completed non-SecOps developer work', () => {
  const ordinary = { dev: 'X', status: 'В работе', start: '2026-11-02', end: '' };
  const completed = removed({});
  const excluded = [removed({ dev: ' SecOps ' }), removed({ dev: '' }), removed({ end: '' }),
    removed({ start: '' }), removed({ end: '2026-11-06' }), removed({ start: '2026-11-06' }),
    removed({ end: '2026-02-30' }), removed({ start: '2026-11-04', end: '2026-11-03' }),
    removed({ bad: ['start'] }), removed({ bad: ['end'] })];
  const rows = Object.freeze([ordinary, completed, ...excluded].map(Object.freeze));
  const got = scope.split(rows, D + 3);
  assert.deepEqual(got.pool, [ordinary]);
  assert.deepEqual(got.removed, [completed, ...excluded]);
  assert.deepEqual(got.speed, [ordinary, completed]);
  assert.deepEqual(scope.split([], D), { pool: [], removed: [], speed: [] });
});

test('removed workload cannot dilute pool hours or keep a developer active', () => {
  const active = { dev: 'X', status: 'В работе', start: '2026-11-02', end: '' };
  const got = scope.split([active, removed({}), removed({ end: '' })], D + 3);
  assert.deepEqual(hours.compute(got.pool, D + 3).hours, [32]);
  const old = scope.split([removed({ end: '2026-11-02' }), removed({ end: '' }), removed({ dev: 'SecOps' })], D + 8);
  const state = activity.compute(old.speed, D + 8, hours.compute(old.speed, D + 8));
  assert.equal(state.people.size, 1);
  assert.equal(state.people.get('X').current, false);
  const stats = activity.stats(state.people.get('X'), D, D + 8, state.breaks);
  assert.deepEqual([stats.closed, stats.work, stats.rate], [1, 1, 1]);
  assert.deepEqual(old.pool, []);
});

test('after freeze uses creation date strictly after freeze through report date, only in pool', () => {
  const rows = [
    { row: 1, tdate: '2026-11-02' }, { row: 2, tdate: '2026-11-03' },
    { row: 3, tdate: '2026-11-04', status: 'Ожидает ревью' },
    { row: 4, tdate: '2026-11-05', status: 'Готов' },
    { row: 5, tdate: '2026-11-06' }, removed({ row: 6, tdate: '2026-11-04' }),
    { row: 7, tdate: '' }, { row: 8, tdate: '2026-02-30' },
    { row: 9, tdate: '2026-11-04', bad: ['tdate'] },
    { row: 10, tdate: '2026-11-02', start: '2026-11-04' },
  ];
  assert.deepEqual(scope.afterFreeze(rows, D + 1, D + 3).map(r => r.row), [3, 4]);
  assert.deepEqual(scope.afterFreeze(rows, D + 2, D + 3).map(r => r.row), [4]);
  assert.deepEqual(scope.afterFreeze(rows, null, D + 3), []);
  assert.deepEqual(scope.afterFreeze(rows, D + 4, D + 3), []);
});
