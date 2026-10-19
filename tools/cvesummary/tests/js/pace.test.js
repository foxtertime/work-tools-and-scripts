'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var pace = require('../../cvesummary/assets/js/pace.js');

var D = 20731;
var iso = dates.isoOf;
function r(tdate, status, end) { return { tdate: iso(tdate), status: status || '', end: end === undefined ? '' : iso(end) }; }

test('rates: поступление и закрытие за окно', function () {
  var rows = [r(D), r(D + 1), r(D + 6, 'Готов', D + 6), r(D + 6, 'Готов', D + 3), r(D - 1), r(D + 9)];
  var got = pace.rates(rows, D + 6, 7);
  assert.strictEqual(got.inR, 4 / 7);   // D-1 вне окна, D+9 после даты отчёта
  assert.strictEqual(got.outR, 2 / 7);
  assert.strictEqual(got.open, 4);
  assert.strictEqual(got.net, 2 / 7 - 4 / 7);
});

test('rates без закрытых и без дат — нули, не NaN', function () {
  var got = pace.rates([{ tdate: '', status: '', end: '' }], D, 14);
  assert.deepStrictEqual(got, { inR: 0, outR: 0, net: 0, open: 1 });
});

test('simulate', function () {
  assert.strictEqual(pace.simulate(0, 1, 1, D), 0);
  assert.strictEqual(pace.simulate(5, 0, 0, D), null);           // не закрываем
  assert.strictEqual(pace.simulate(10, 0, 2, D, null), 5);
  assert.strictEqual(pace.simulate(10, 2, 2, D), null);          // приходит столько же
  assert.strictEqual(pace.simulate(4, 1, 2, 0, 3), 3);           // сканфриз на 3-й день
  assert.strictEqual(pace.simulate(1, 0, 0.1, D, null), 10);     // без ошибки округления
});

test('need', function () {
  assert.strictEqual(pace.need(10, 1, 0, null, 0), null);
  assert.deepStrictEqual(pace.need(10, 1, 0, null, 10), { perDay: 2, left: 10, incoming: 10 });
  assert.deepStrictEqual(pace.need(10, 1, 0, 5, 10), { perDay: 1.4, left: 10, incoming: 4 });
});

test('daily: по дням и среднее за 7', function () {
  var got = pace.daily([r(D), r(D), r(D + 1, 'Готов', D + 1)], D, D + 1);
  assert.deepStrictEqual(got.map(function (s) { return [s.day, s.i, s.o]; }), [[D, 2, 0], [D + 1, 1, 1]]);
  assert.strictEqual(got[1].ia, 1.5);
  assert.strictEqual(got[1].oa, 0.5);
  assert.deepStrictEqual(pace.daily([], D + 1, D), []);
});
