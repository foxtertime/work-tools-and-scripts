'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const roles = require('../../cvesummary/assets/js/roles.js');
const dates = require('../../cvesummary/assets/js/dates.js');
const scope = require('../../cvesummary/assets/js/scope.js');
// Missing module is checked as an assertion so RED describes the missing feature.
let segments; try { segments = require('../../cvesummary/assets/js/segments.js'); } catch (_) {}
const row = (status, extra = {}) => ({ dev: 'X', status, reasons: [], ...extra });
const removed = extra => row('Убрано из эпика', extra);
const size = parts => Object.fromEntries(parts.map(p => [p.key, p.rows.length]));

test('header done splits by normalized developer into SecOps and remaining done rows', () => {
  const secops = [row('Готов', { dev: 'SecOps' }), row(' ГОТОВ ', { dev: ' secOPS ' })];
  const developers = [row('Готов'), row('Готов', { dev: '', end: '' }),
    row('Готов', { measure: 'Закрыто SecOps' })];
  const review = row('Ожидает ревью', { dev: 'SecOps', end: '2026-11-05' });
  const rows = [...secops, ...developers, review, removed({ dev: 'SecOps' }),
    removed({ start: '2026-11-02', end: '2026-11-05' })];
  const parts = segments.hero(rows);
  assert.deepEqual(parts.map(p => [p.key, p.label, p.group, p.rows]), [
    ['done-secops', 'SecOps', 'done', secops], ['done-dev', 'Разработчики', 'done', developers],
    ['review', 'Ревью', 'review', [review]],
  ]);
  assert.deepEqual(segments.groups(parts)[0], { key: 'done', label: 'Готово', rows: [...secops, ...developers] });
  assert.equal(new Set(parts.flatMap(p => p.rows)).size, 6);
  for (const [rows, key] of [[secops, 'done-secops'], [developers, 'done-dev']]) {
    assert.deepEqual(size(segments.hero(rows)), { [key]: rows.length });
    assert.equal(segments.groups(segments.hero(rows))[0].label, 'Готово');
  }
});

test('removed block partitions completed developer work and the remainder using speed eligibility', () => {
  const asOf = dates.dayOf('2026-11-05');
  const completed = extra => removed({ start: '2026-11-02', end: '2026-11-05', ...extra });
  const rows = [row('Готов'), completed(), completed({ dev: ' SecOps ' }), completed({ end: '' }),
    completed({ end: '2026-11-06' }), completed({ start: '2026-11-05', end: '2026-11-02' }),
    completed({ bad: ['start'] }), completed({ dev: '' })];
  const parts = segments.removed(rows, asOf);
  assert.deepEqual(size(parts), { done: 1, removed: 6 });
  assert.deepEqual(parts.map(p => p.label), ['Готово', 'Убрано']);
  assert.deepEqual(parts[0].rows, scope.split(rows, asOf).speed.filter(roles.isRemoved));
  assert.deepEqual(new Set(parts.flatMap(p => p.rows)), new Set(rows.slice(1)));
  assert.equal(parts.flatMap(p => p.rows).length, 7);
  assert.deepEqual(size(segments.removed([], asOf)), { done: 0, removed: 0 });
  assert.deepEqual(size(segments.removed([completed()], asOf)), { done: 1, removed: 0 });
});

test('completed removed work is partitioned by normalized accepted measure without losing missing or custom measures', () => {
  const asOf = dates.dayOf('2026-11-05');
  const completed = measure => removed({ start: '2026-11-02', end: '2026-11-05', measure });
  const rows = [completed('Патч из апстрима'), completed('  патч  из АПСТРИМА '),
    completed('Импорт новой версии'), completed(''), completed('Своя "мера"'),
    { ...completed('Только SecOps'), dev: 'SecOps' },
    { ...completed('Незавершённая мера'), end: '' }, row('Готов', { measure: 'Мера пула' })];
  const [done, rest] = segments.removed(rows, asOf);
  assert.deepEqual(done.parts.map(p => [p.label, p.rows.length]), [
    ['Патч из апстрима', 2], ['Импорт новой версии', 1], ['Своя "мера"', 1], [roles.NO_MEASURE, 1],
  ]);
  assert.deepEqual(new Set(done.parts.flatMap(p => p.rows)), new Set(done.rows));
  assert.equal(done.parts.flatMap(p => p.rows).length, done.rows.length);
  assert.deepEqual(rest.rows, rows.slice(5, 7));
  assert.equal(new Set(done.parts.map(p => p.key)).size, 4);
  assert.ok(done.parts.every(p => p.group === 'done' && p.measure === p.label));
  assert.deepEqual(segments.removed([], asOf)[0].parts, []);
});

test('remaining removed tasks split into AI groups per source row, excluding completed work and the pool', () => {
  const asOf = dates.dayOf('2026-11-05');
  const verdicts = [' AFFECTED ', 'Unclear', 'custom verdict', 'Not Affected', 'invalid CVE',
    'REJECTED CVE', 'not processed', '', null, '   '];
  const rest = verdicts.map(ai_verdict => removed({ cve: 'CVE-1', comp: 'bash', ai_verdict }));
  rest[0] = { ...rest[0], dev: 'SecOps', start: '2026-11-02', end: '2026-11-05' };
  const done = removed({ start: '2026-11-02', end: '2026-11-05', ai_verdict: 'affected' });
  const parts = segments.removed([...rest, done, row('Готов', { ai_verdict: 'not affected' })], asOf);
  assert.deepEqual(size(parts), { done: 1, removed: 10 });
  assert.deepEqual(parts[1].parts.map(p => [p.aiGroup, p.label, p.rows.length]), [
    ['maybe', 'Возможно затронуто', 3], ['no', 'Не затронуто', 3], ['none', 'Не прогнано', 4],
  ]);
  assert.deepEqual(parts[1].parts.map(p => p.rows), [rest.slice(0, 3), rest.slice(3, 6), rest.slice(6)]);
  assert.ok(parts[1].parts.every(p => p.group === 'removed'));
  assert.deepEqual(segments.removed([], asOf)[1].parts, []);
  assert.deepEqual(segments.removed([done], asOf)[1].parts, []);
  assert.equal(segments.removed([removed({})], asOf)[1].parts[0].aiGroup, 'none');
});

test('header excludes two removed tasks while personal segments and semantic counts retain them', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [...Array.from({ length: 6 }, () => row('Готов')),
    removed({ start: '2026-11-02', end: '2026-11-05' }), removed({ dev: 'SecOps' }),
    row('В работе'), row('В работе')];
  assert.deepEqual(size(segments.person(rows)), { removed: 2, done: 6, work: 2 });
  assert.deepEqual(size(segments.hero(rows)), { 'done-dev': 6, work: 2 });
  assert.equal(rows.filter(roles.isDone).length, 8);
  for (const fn of [segments.person, segments.hero]) {
    const parts = fn(rows);
    const expected = fn === segments.person ? rows : rows.filter(r => !roles.isRemoved(r));
    assert.equal(parts[0].key, fn === segments.person ? 'removed' : 'done-dev');
    assert.deepEqual(new Set(parts.flatMap(p => p.rows)), new Set(expected));
    assert.equal(parts.reduce((n, p) => n + p.rows.length, 0), expected.length);
    if (fn === segments.person) assert.match(parts.find(p => p.key === 'done').label, /без убранных/);
    else assert.equal(segments.groups(parts).find(p => p.key === 'done').label, 'Готово');
    assert.equal(segments.groups(parts).flatMap(g => g.rows).length, expected.length);
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

test('header excludes every removed role and retains ordinary working tasks with closure reasons', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [removed({ dev: 'SecOps' }), removed({ start: '2026-11-02', reasons: ['patch'] }),
    removed({ dev: '' }), row('В работе', { reasons: ['fixed', 'patch'] }), row('В работе', { reasons: ['dup'] })];
  assert.deepEqual(size(segments.hero(rows)), { work: 2 });
  assert.deepEqual(size(segments.groups(segments.hero(rows))), { work: 2 });
  assert.deepEqual(size(segments.person(rows.filter(roles.isTaken))), { removed: 2, work: 2 });
  assert.equal(segments.person([row('Готов')])[0].label, 'Готово');
  assert.deepEqual(segments.hero([removed({ dev: 'SecOps' }), removed({ dev: '' })]), []);
  assert.deepEqual(segments.hero([]), []);
});

test('header moves review and working tasks out of every right-hand segment without changing pool membership', () => {
  const reasons = [[], ['fixed', 'patch'], ['patch'], ['range'], ['dup']];
  const reviews = reasons.map(reasons => row('Ожидает ревью', { reasons }));
  reviews[4] = row('  ОЖИДАЕТ  ревью ', { dev: '', reasons: ['dup'] });
  const working = reasons.map(reasons => row('В работе', { reasons })).concat(
    ['На паузе', 'Есть проблема', 'Нужна доработка', '', 'Свой статус'].map(status => row(status)));
  const pending = reasons.map(reasons => row('В работе', { dev: '', reasons }));
  const rows = [row('Готов'), ...reviews, ...working, ...pending, removed({ dev: 'SecOps' })];
  const parts = segments.hero(rows);
  assert.deepEqual(parts.map(p => p.key), ['done-dev', 'review', 'work', 'none', 'fixed', 'patch', 'range', 'dup']);
  assert.deepEqual(size(parts), { 'done-dev': 1, review: 5, work: 10, none: 1, fixed: 1, patch: 1, range: 1, dup: 1 });
  assert.deepEqual(parts.find(p => p.key === 'review').rows, reviews);
  assert.deepEqual(parts.find(p => p.key === 'work').rows, working);
  assert.deepEqual(parts.slice(3).flatMap(p => p.rows), pending);
  assert.equal(parts.flatMap(p => p.rows).length, 21);
  assert.equal(new Set(parts.flatMap(p => p.rows)).size, 21);
  assert.deepEqual(size(segments.groups(parts)), { done: 1, review: 5, work: 10, none: 1, ready: 4 });
});

test('unique representatives prefer ordinary rows but all-removed pairs remain visible', () => {
  assert.ok(segments, 'shared segments module must exist');
  const rows = [removed({ cve: 'CVE-1', comp: 'bash', dev: 'SecOps' }),
    row('В работе', { cve: 'CVE-1', comp: 'bash' }),
    removed({ cve: 'CVE-2', comp: 'curl' }), removed({ cve: 'CVE-2', comp: 'curl' }),
    row('В работе', { cve: 'CVE-1', comp: 'bash' }), removed({ cve: 'CVE-3', comp: '' })];
  assert.deepEqual(segments.uniqueRows(rows, roles.duplicates(rows)), [rows[1], rows[2], rows[5]]);
});

test('header shows awaiting comment as its own segment right after review, out of every right-hand segment', () => {
  const reasons = [[], ['fixed'], ['patch'], ['range'], ['dup']];
  const comments = reasons.map(reasons => row('Ожидает комментарий', { reasons }));
  comments[4] = row('  ОЖИДАЕТ  комментарий ', { dev: '', reasons: ['dup'] });
  const review = row('Ожидает ревью', { reasons: ['fixed'] });
  const working = [row('В работе'), row('На паузе')];
  const pending = reasons.map(reasons => row('В работе', { dev: '', reasons }));
  const parts = segments.hero([row('Готов'), review, ...comments, ...working, ...pending]);
  assert.deepEqual(parts.map(p => [p.key, p.label]), [['done-dev', 'Разработчики'], ['review', 'Ревью'],
    ['comment', 'Комментарий'], ['work', 'В работе'], ['none', 'Не взято'], ['fixed', 'Фикс в RHEL'],
    ['patch', 'Устранено ранее'], ['range', 'Вне диапазона'], ['dup', 'Дубликат']]);
  assert.equal(parts.find(p => p.key === 'comment').color, '--st-comment');
  assert.deepEqual(parts.find(p => p.key === 'comment').rows, comments);
  assert.deepEqual(parts.find(p => p.key === 'review').rows, [review]);
  assert.deepEqual(parts.find(p => p.key === 'work').rows, working);
  assert.deepEqual(parts.slice(4).flatMap(p => p.rows), pending);
  assert.deepEqual(size(segments.groups(parts)), { done: 1, review: 1, comment: 5, work: 2, none: 1, ready: 4 });
});

test('personal roles put awaiting comment between review and pause and keep it out of work', () => {
  const rows = [row('Готов'), row('В работе'), row('Ожидает ревью'), row('Ожидает комментарий'),
    row(' ожидает  КОММЕНТАРИЙ'), row('На паузе'), row('Есть проблема')];
  const parts = segments.person(rows);
  assert.deepEqual(parts.map(p => [p.key, p.rows.length]), [['done', 1], ['work', 1], ['review', 1],
    ['comment', 2], ['pause', 1], ['bad', 1]]);
  const comment = segments.personCounts([row('Готов')]).find(p => p.key === 'comment');
  assert.deepEqual([comment.label, comment.color, comment.rows.length], ['Ожидает комментарий', '--st-comment', 0]);
});
