'use strict';
var test = require('node:test');
var assert = require('node:assert');
var ai = require('../../cvesummary/assets/js/ai.js');

function row(cve, comp, verdict, conf, rem, run) {
  return { cve: cve, comp: comp, ai_verdict: verdict || '', ai_conf: conf || '', ai_rem: rem || '',
    ai_run: run || '', bad: [] };
}
function counts(list) {
  return list.map(function (x) { return [x.k, x.n]; });
}

test('summary: прогнано — пары с настоящим вердиктом; осталось — не прогнанные и not processed', function () {
  var s = ai.summary([
    row('CVE-1', 'bash', 'affected', 'high', 'backport prepared'),
    row('CVE-1', 'bash'),
    row('CVE-2', 'bash', 'not processed'),
    row('CVE-3', 'bash'),
    row('CVE-4', 'curl', 'not affected', 'low', 'not required'),
  ]);
  assert.deepStrictEqual([s.total, s.run, s.notProcessed, s.notRun, s.left], [4, 2, 1, 1, 2]);
});

test('summary: пара — по тому же правилу, что счётчик шапки', function () {
  var s = ai.summary([
    row(' cve-1 ', 'Bash', 'affected'), row('CVE-1', 'bash '),
    row('CVE-3', '', 'affected'), row('CVE-3', ''),
  ]);
  // CVE-1/bash — одна пара; строки без компонента — каждая сама по себе
  assert.deepStrictEqual([s.total, s.run, s.notRun], [3, 2, 1]);
});

test('summary: вердикты по группам — возможно затронуто, не затронуто, не прогнано', function () {
  var s = ai.summary([
    row('CVE-1', 'a', 'maybe'), row('CVE-2', 'a', 'Not Affected'), row('CVE-3', 'a', 'AFFECTED'),
    row('CVE-4', 'a', 'not processed'), row('CVE-5', 'a', 'odd'), row('CVE-6', 'a', 'odd'),
    row('CVE-7', 'a', 'invalid cve'), row('CVE-8', 'a', 'unclear'), row('CVE-9', 'a'),
  ]);
  // незнакомый вердикт — среди возможно затронутых, после знакомых, по числу
  assert.deepStrictEqual(counts(s.verdicts), [['affected', 1], ['unclear', 1], ['odd', 2], ['maybe', 1],
    ['not affected', 1], ['invalid CVE', 1], ['not processed', 1]]);
  assert.deepStrictEqual(s.verdicts.map(function (v) { return v.g; }),
    ['maybe', 'maybe', 'maybe', 'maybe', 'no', 'no', 'none']);
  assert.deepStrictEqual(s.verdicts.map(function (v) { return v.known; }), [true, true, false, false, true, true, true]);
  assert.deepStrictEqual(s.groups, { maybe: 5, no: 2, none: 2 });
  assert.deepStrictEqual(ai.GROUPS, ['maybe', 'no', 'none']);
});

test('summary: уверенность по вердикту; незнакомая и пустая — только в общем числе', function () {
  var s = ai.summary([
    row('CVE-1', 'a', 'affected', 'High'), row('CVE-2', 'a', 'affected', 'low'),
    row('CVE-3', 'a', 'affected', 'certain'), row('CVE-4', 'a', 'affected'),
  ]);
  assert.deepStrictEqual(s.verdicts[0], { k: 'affected', known: true, n: 4, g: 'maybe',
    conf: { high: 1, medium: 0, low: 1, other: 2 } });
});

test('summary: remediation — в группе вердикта пары, по справочнику; незнакомая и пустая — в конце группы', function () {
  var s = ai.summary([
    row('CVE-1', 'a', 'not affected', 'high', 'not required'),
    row('CVE-2', 'a', 'affected', 'high', 'Backport Prepared'),
    row('CVE-3', 'a', 'affected', 'high', 'magic'),
    row('CVE-4', 'a', 'affected', 'high'),
    row('CVE-7', 'a', 'unclear', 'low', 'not determined'),
    row('CVE-8', 'a', 'not affected', 'medium'),
    row('CVE-5', 'a', 'not processed'),
    row('CVE-6', 'a'),
  ]);
  assert.deepStrictEqual(s.remediations.map(function (r) { return [r.g, r.k, r.n]; }), [
    ['maybe', 'backport prepared', 1], ['maybe', 'not determined', 1], ['maybe', 'magic', 1], ['maybe', '', 1],
    ['no', 'not required', 1], ['no', '', 1]]);
  assert.deepStrictEqual([s.noRemediation, s.notProcessed, s.notRun], [2, 1, 1]);
});

test('summary: у пары с разными данными AI берётся строка с самым поздним прогоном', function () {
  var s = ai.summary([
    row('CVE-1', 'a', 'affected', 'high', 'pending', '2026-10-20'),
    row('CVE-1', 'a', 'not affected', 'medium', 'not required', '2026-10-21'),
    row('CVE-1', 'a', 'unclear', 'low', 'not determined'),
  ]);
  assert.deepStrictEqual(counts(s.verdicts), [['not affected', 1]]);
  assert.deepStrictEqual(counts(s.remediations), [['not required', 1]]);
});

test('summary: при равном или неразобранном прогоне — первая строка с вердиктом', function () {
  var late = row('CVE-1', 'a', 'unclear', 'low', '', 'вчера');
  late.bad = ['ai_run'];
  var s = ai.summary([row('CVE-1', 'a'), row('CVE-1', 'a', 'affected'), late]);
  assert.deepStrictEqual(counts(s.verdicts), [['affected', 1]]);
});

test('summary: пустая таблица и последний прогон', function () {
  var s = ai.summary([]);
  assert.deepStrictEqual([s.total, s.run, s.left, s.verdicts, s.remediations, s.last], [0, 0, 0, [], [], null]);
  assert.deepStrictEqual(s.groups, { maybe: 0, no: 0, none: 0 });
  var bad = row('CVE-4', 'a', 'affected', '', '', 'вчера');
  bad.bad = ['ai_run'];
  assert.strictEqual(ai.summary([row('CVE-1', 'a', 'affected', '', '', '2026-10-20'),
    row('CVE-2', 'a', 'affected', '', '', '2026-10-21'), bad]).last, '2026-10-21');
});
