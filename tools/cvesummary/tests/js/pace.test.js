'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var pace = require('../../cvesummary/assets/js/pace.js');

var D = 20731;
var iso = dates.isoOf;
function r(tdate, status, end) { return { tdate: iso(tdate), status: status || '', end: end === undefined ? '' : iso(end) }; }

/* D — понедельник 05.10.2026. Поступление — на календарный день (новые
   приходят и в выходные), закрытие — на рабочий день Пн–Пт */
test('rates: поступление на календарный день, закрытие на рабочий, баланс за неделю', function () {
  var rows = [r(D), r(D + 1), r(D + 6, 'Готов', D + 6), r(D + 6, 'Готов', D + 3), r(D - 1), r(D + 9)];
  var got = pace.rates(rows, D + 6, 7);
  assert.strictEqual(got.inR, 4 / 7);   // окно Пн–Вс; D-1 вне окна, D+9 после даты отчёта
  assert.strictEqual(got.outR, 2 / 5);  // 5 рабочих дней в окне
  assert.strictEqual(got.open, 4);
  assert.strictEqual(got.net, 2 / 5 * 5 - 4 / 7 * 7);  // за неделю: закрыто 5 рабочих дней, пришло 7 календарных
});

test('rates без закрытых и без дат — нули, не NaN', function () {
  var got = pace.rates([{ tdate: '', status: '', end: '' }], D, 14);
  assert.deepStrictEqual(got, { inR: 0, outR: 0, net: 0, open: 1 });
});

test('simulate — приходят каждый день, закрываем по рабочим; результат — календарный сдвиг', function () {
  assert.strictEqual(pace.simulate(0, 1, 1, D), 0);
  assert.strictEqual(pace.simulate(5, 0, 0, D), null);           // не закрываем
  assert.strictEqual(pace.simulate(10, 0, 2, D, null), 7);       // Вт–Пт и Пн: понедельник следующей недели
  assert.strictEqual(pace.simulate(10, 2, 2.8, D), null);        // за неделю 14 приходит, 14 закрываем
  assert.strictEqual(pace.simulate(4, 1, 2, D, D + 3), 3);       // сканфриз в четверг
  assert.strictEqual(pace.simulate(3, 1, 3, D + 4, D + 8), 4);   // в выходные приходят, закрываем с понедельника
  assert.strictEqual(pace.simulate(1, 0, 1, D + 4, null), 3);    // из пятницы — в понедельник
  assert.strictEqual(pace.simulate(1, 0, 0.1, D, null), 14);     // 10 рабочих дней, без ошибки округления
});

test('need — в рабочий день до целевой даты, новые — по календарным дням', function () {
  assert.strictEqual(pace.need(10, 1, D, null, D), null);
  assert.deepStrictEqual(pace.need(10, 1, D, null, D + 14), { perDay: 2.4, left: 10, incoming: 14 });
  assert.deepStrictEqual(pace.need(10, 1, D, D + 5, D + 14), { perDay: 1.4, left: 10, incoming: 4 });
  assert.deepStrictEqual(pace.need(10, 1, D + 4, null, D + 6), { perDay: Infinity, left: 0, incoming: 2 });
});

test('daily: по дням и среднее за 7', function () {
  var got = pace.daily([r(D), r(D), r(D + 1, 'Готов', D + 1)], D, D + 1);
  assert.deepStrictEqual(got.map(function (s) { return [s.day, s.i, s.o]; }), [[D, 2, 0], [D + 1, 1, 1]]);
  assert.strictEqual(got[1].ia, 1.5);
  assert.strictEqual(got[1].oa, 0.5);
  assert.deepStrictEqual(pace.daily([], D + 1, D), []);
});
