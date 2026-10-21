'use strict';
var test = require('node:test');
var assert = require('node:assert');
var ai = require('../../cvesummary/assets/js/ai.js');

function row(cve, comp, group, verdict, run) {
  return { cve: cve, comp: comp, g: group, ai_verdict: verdict || '', ai_run: run || '', bad: [] };
}
var groupOf = function (r) { return r.g; };

test('coverage: пара прогнана, если вердикт есть хотя бы у одной её строки', function () {
  var c = ai.coverage([
    row('CVE-1', 'bash', 'none', 'affected'),
    row('CVE-1', 'bash', 'ready'),
    row('CVE-2', 'bash', 'none'),
    row('CVE-1', 'curl', 'done', 'not affected'),
  ], groupOf);
  assert.deepStrictEqual([c.total, c.covered], [3, 2]);
});

test('coverage: пара — по тому же правилу, что счётчик шапки', function () {
  var c = ai.coverage([
    row(' cve-1 ', 'Bash', 'none', 'affected'),
    row('CVE-1', 'bash ', 'none'),
    row('CVE-3', '', 'none', 'affected'),
    row('CVE-3', '', 'none'),
  ], groupOf);
  // CVE-1/bash — одна пара; строки без компонента — каждая сама по себе
  assert.deepStrictEqual([c.total, c.covered], [3, 2]);
});

test('coverage: группа пары — готово, иначе без решения, иначе можно закрыть', function () {
  var c = ai.coverage([
    row('CVE-1', 'bash', 'ready', 'affected'), row('CVE-1', 'bash', 'done'),
    row('CVE-2', 'bash', 'ready'), row('CVE-2', 'bash', 'none'),
    row('CVE-3', 'bash', 'ready', 'affected'),
  ], groupOf);
  assert.deepStrictEqual(c.groups, {
    done: { total: 1, covered: 1 }, none: { total: 1, covered: 0 }, ready: { total: 1, covered: 1 },
  });
  assert.deepStrictEqual(ai.GROUPS, ['done', 'none', 'ready']);
});

test('coverage: пустая таблица', function () {
  var c = ai.coverage([], groupOf);
  assert.deepStrictEqual([c.total, c.covered, c.groups.done], [0, 0, { total: 0, covered: 0 }]);
});

test('lastRun: самая поздняя разобранная дата прогона', function () {
  var bad = row('CVE-4', 'bash', 'none', 'affected', 'вчера');
  bad.bad = ['ai_run'];
  assert.strictEqual(ai.lastRun([
    row('CVE-1', 'bash', 'none', 'affected', '2026-10-20'),
    row('CVE-2', 'bash', 'none', 'affected', '2026-10-21'),
    row('CVE-3', 'bash', 'none'), bad,
  ]), '2026-10-21');
  assert.strictEqual(ai.lastRun([row('CVE-1', 'bash', 'none')]), null);
});
