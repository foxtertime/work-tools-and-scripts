'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const roles = require('../../cvesummary/assets/js/roles.js');
// Missing module is checked as an assertion so RED describes the missing feature.
let segments; try { segments = require('../../cvesummary/assets/js/segments.js'); } catch (_) {}
const row = (status, extra = {}) => ({ dev: 'X', status, reasons: [], ...extra });
const removed = extra => row('Убрано из эпика', extra);
const size = parts => Object.fromEntries(parts.map(p => [p.key, p.rows.length]));

test('ten tasks: graphite 2, green 6, blue 2, semantic closed 8', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [...Array.from({ length: 6 }, () => row('Готов')),
    removed({ start: '2026-11-02', end: '2026-11-05' }), removed({ dev: 'SecOps' }),
    row('В работе'), row('В работе')];
  assert.deepEqual(size(segments.person(rows)), { removed: 2, done: 6, work: 2 });
  assert.deepEqual(size(segments.hero(rows)), { removed: 2, done: 6, none: 2 });
  assert.equal(rows.filter(roles.isDone).length, 8);
  for (const fn of [segments.person, segments.hero]) {
    const parts = fn(rows);
    assert.equal(parts[0].key, 'removed');
    assert.equal(new Set(parts.flatMap(p => p.rows)).size, 10);
    assert.equal(parts.reduce((n, p) => n + p.rows.length, 0), 10);
    if (fn === segments.person) assert.match(parts.find(p => p.key === 'done').label, /без убранных/);
    else assert.equal(parts.find(p => p.key === 'done').label, 'Готово');
    assert.equal(segments.groups(parts).flatMap(g => g.rows).length, 10);
  }
});

test('header state counts removed separately from ordinary done, working and unassigned tasks', () => {
  assert.equal(typeof segments.heroState, 'function');
  const rows = [row('Готов'), row('В работе'), row('', { dev: '' }),
    removed({ dev: 'SecOps' }), removed({ start: '2026-11-02' }), removed({ dev: '' })];
  const states = segments.heroState(rows);
  assert.deepEqual(size(states), { removed: 3, done: 1, work: 1, none: 1 });
  assert.equal(new Set(states.flatMap(s => s.rows)).size, rows.length);
  assert.equal(states.flatMap(s => s.rows).length, rows.length);
  assert.deepEqual(size(segments.heroState([])), { removed: 0, done: 0, work: 0, none: 0 });
  assert.ok(segments.hero(rows).every(p => !p.label.includes('без убранных')));
  assert.ok(segments.groups(segments.hero(rows)).every(p => !p.label.includes('без убранных')));
});

test('mixed removed roles occupy only graphite; ordinary ready groups remain disjoint', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [removed({ dev: 'SecOps' }), removed({ start: '2026-11-02', reasons: ['patch'] }),
    removed({ dev: '' }), row('В работе', { reasons: ['fixed', 'patch'] }), row('В работе', { reasons: ['dup'] })];
  assert.deepEqual(size(segments.hero(rows)), { removed: 3, fixed: 1, dup: 1 });
  assert.deepEqual(size(segments.groups(segments.hero(rows))), { removed: 3, ready: 2 });
  assert.deepEqual(size(segments.person(rows.filter(roles.isTaken))), { removed: 2, work: 2 });
  assert.equal(segments.person([row('Готов')])[0].label, 'Готово');
  assert.deepEqual(size(segments.hero([removed({ dev: 'SecOps' })])), { removed: 1 });
});

test('unique representatives prefer ordinary rows but all-removed pairs remain visible', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [removed({ cve: 'CVE-1', comp: 'bash', dev: 'SecOps' }),
    row('В работе', { cve: 'CVE-1', comp: 'bash' }),
    removed({ cve: 'CVE-2', comp: 'curl' }), removed({ cve: 'CVE-2', comp: 'curl' }),
    row('В работе', { cve: 'CVE-1', comp: 'bash' }), removed({ cve: 'CVE-3', comp: '' })];
  assert.deepEqual(segments.uniqueRows(rows, roles.duplicates(rows)), [rows[1], rows[2], rows[5]]);
});
