'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var hours = require('../../cvesummary/assets/js/hours.js');

var MON = 20731; // 2026-10-05
var iso = function (day) { return day === null ? '' : dates.isoOf(day); };
function t(dev, start, end, status, bad) {
  return { dev: dev, start: iso(start), end: iso(end), status: status || 'В работе', bad: bad || [] };
}
var H = function (rows, asOf) { return hours.compute(rows, asOf).hours; };

test('одна задача пн–ср — 24 ч', function () {
  assert.deepStrictEqual(H([t('X', MON, MON + 2, 'Готов')], MON + 10), [24]);
});

test('две параллельно — по 4 ч в день', function () {
  assert.deepStrictEqual(H([t('X', MON, MON), t('X', MON, MON)], MON), [4, 4]);
});

test('выходной без старта и закрытия не считается', function () {
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 7, 'Готов')], MON + 10), [16]);
});

test('выходной со стартом — рабочий', function () {
  // A пт–пн; B взята в вс, открыта. сб не рабочий, вс и пн делятся на двоих
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 7, 'Готов'), t('X', MON + 6, null)], MON + 7), [16, 8]);
});

test('выходной с закрытием — рабочий', function () {
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 5, 'Готов')], MON + 10), [16]);
});

test('старт и закрытие в один день — 8 ч', function () {
  assert.deepStrictEqual(H([t('X', MON, MON, 'Готов')], MON + 10), [8]);
});

test('открытая — до даты отчёта; конец обрезается датой отчёта', function () {
  assert.deepStrictEqual(H([t('X', MON, null)], MON + 2), [24]);
  assert.deepStrictEqual(H([t('X', MON, MON + 10)], MON + 1), [16]);
});

test('старт после даты отчёта — 0 ч, не аномалия', function () {
  var got = hours.compute([t('X', MON + 5, null)], MON);
  assert.deepStrictEqual(got.hours, [0]);
  assert.deepStrictEqual(got.anomalies, []);
});

test('пример из спеки: 16, 32, 8', function () {
  var rows = [t('X', MON, MON + 2, 'Готов'), t('X', MON + 1, MON + 7, 'Готов'), t('X', MON + 4, MON + 5, 'Готов')];
  assert.deepStrictEqual(H(rows, MON + 14), [16, 32, 8]);
});

test('пример пользователя: первая задача — 12 ч', function () {
  var rows = [t('X', MON, MON + 2, 'Готов'), t('X', MON + 1, null), t('X', MON + 1, null), t('X', MON + 1, null)];
  assert.strictEqual(H(rows, MON + 2)[0], 12);
});

test('разные разработчики не делят день; пробелы в имени — тот же человек', function () {
  assert.deepStrictEqual(H([t('X', MON, MON), t('Y', MON, MON)], MON), [8, 8]);
  assert.deepStrictEqual(H([t('Иванов ', MON, MON), t('Иванов', MON, MON)], MON), [4, 4]);
});

test('аномалии и не взятые', function () {
  var rows = [
    t('X', MON + 2, MON),               // End раньше Start
    t('X', MON, null, 'Готов'),         // «Готов» без End
    t('X', null, null),                 // нет Start
    t('X', MON, MON, 'В работе', ['start']), // дата не разобрана
    t('', null, null),                  // не взята
  ];
  var got = hours.compute(rows, MON + 3);
  assert.deepStrictEqual(got.hours, [null, null, null, null, null]);
  assert.deepStrictEqual(got.anomalies.map(function (a) { return [a.index, a.reason]; }),
    [[0, 'end-before-start'], [1, 'done-no-end'], [2, 'no-start'], [3, 'bad-date']]);
  Object.keys(hours.REASONS).forEach(function (k) { assert.ok(hours.REASONS[k]); });
});

test('SecOps без Start date допустим, часы остаются неизвестными', function () {
  var got = hours.compute([
    t('SecOps', null, null),
    t(' secops ', null, MON, 'Готов'),
    t('SECOPS', null, MON),
  ], MON + 3);
  assert.deepStrictEqual(got.anomalies, []);
  assert.deepStrictEqual(got.hours, [null, null, null]);
  assert.strictEqual(got.workdays.size, 0);
  assert.strictEqual(got.load.size, 0);
});

test('отсутствие Start date у других разработчиков остаётся аномалией', function () {
  var got = hours.compute([
    t('Иванов', null, null),
    t('SecOps team', null, MON, 'Готов'),
    t('', null, null),
  ], MON + 3);
  assert.deepStrictEqual(got.anomalies, [
    { index: 0, reason: 'no-start' }, { index: 1, reason: 'no-start' },
  ]);
  assert.deepStrictEqual(got.hours, [null, null, null]);
});

test('SecOps: «Готов» без End date разрешён, неизвестные часы не делят день открытой задачи', function () {
  var got = hours.compute([
    t('SecOps', MON, null, 'Готов'),
    t(' secops ', null, null, 'Готов'),
    t('SECOPS', MON + 5, null, 'Готов'),
    t('SecOps', MON, null),
    t('SecOps', MON + 5, MON + 6, 'Готов'),
  ], MON + 1);
  assert.deepStrictEqual(got.anomalies, []);
  assert.deepStrictEqual(got.hours, [null, null, null, 16, 0]);
  assert.strictEqual(got.load.get('SecOps').get(MON), 1);
});

test('другие разработчики: «Готов» без End date остаётся аномалией', function () {
  var got = hours.compute([
    t('Иванов', MON, null, 'Готов'),
    t('SecOps team', MON, null, 'Готов'),
  ], MON + 1);
  assert.deepStrictEqual(got.anomalies, [
    { index: 0, reason: 'done-no-end' }, { index: 1, reason: 'done-no-end' },
  ]);
  assert.deepStrictEqual(got.hours, [null, null]);
});

test('SecOps: остальные аномалии и расчёт часов с датой старта сохраняются', function () {
  var got = hours.compute([
    t('SecOps', MON + 2, MON),
    t('SecOps', MON, null, 'Готов'),
    t('SecOps', null, null, 'Готов'),
    t('SecOps', null, MON, 'В работе', ['start']),
    t('SecOps', null, null, 'В работе', ['end']),
    t('SecOps', MON, MON, 'Готов'),
    t('SecOps', MON + 5, null),
  ], MON + 3);
  assert.deepStrictEqual(got.anomalies, [
    { index: 0, reason: 'end-before-start' }, { index: 3, reason: 'bad-date' },
    { index: 4, reason: 'bad-date' },
  ]);
  assert.deepStrictEqual(got.hours, [null, null, null, null, null, 8, 0]);
});

test('колонки процесса пусты у всех — часов нет, ничего не падает', function () {
  var got = hours.compute([{ dev: '', status: '', start: '', end: '', bad: [] }], MON);
  assert.deepStrictEqual(got.hours, [null]);
  assert.strictEqual(got.workdays.size, 0);
});

test('загрузка и рабочие дни', function () {
  var got = hours.compute([t('X', MON, MON), t('X', MON, MON + 7)], MON + 7);
  assert.strictEqual(got.load.get('X').get(MON), 2);
  assert.deepStrictEqual([...got.workdays.get('X')].sort(function (a, b) { return a - b; }), [MON, MON + 1, MON + 2, MON + 3, MON + 4, MON + 7]);
});

test('summary: среднее и медиана', function () {
  assert.deepStrictEqual(hours.summary([]), { n: 0, mean: null, median: null });
  assert.deepStrictEqual(hours.summary([1, 3, 2, 10]), { n: 4, mean: 4, median: 2.5 });
  assert.deepStrictEqual(hours.summary([5]), { n: 1, mean: 5, median: 5 });
});

test('rate: закрыто за рабочий день', function () {
  var days = new Set([MON, MON + 1, MON + 2, MON + 3]);
  assert.strictEqual(hours.rate([MON, MON + 1], days, MON, MON + 3), 0.5);
  assert.strictEqual(hours.rate([MON], new Set(), MON, MON + 3), null);
});

test('сотни тысяч задач одного разработчика не переполняют стек', function () {
  var rows = [];
  for (var i = 0; i < 300000; i++) rows.push(t('X', MON, MON, 'Готов'));
  var h = H(rows, MON);
  assert.strictEqual(h.length, 300000);
  assert.ok(Math.abs(h[0] - 8 / 300000) < 1e-12);
});
