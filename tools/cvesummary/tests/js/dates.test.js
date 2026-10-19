'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');

var MON = 20731; // 2026-10-05, понедельник

test('ISO ↔ номер дня', function () {
  assert.strictEqual(dates.dayOf('1970-01-01'), 0);
  assert.strictEqual(dates.dayOf('2026-10-05'), MON);
  assert.strictEqual(dates.isoOf(MON), '2026-10-05');
  assert.strictEqual(dates.ruOf(MON), '05.10.2026');
});

test('не ISO — null', function () {
  assert.strictEqual(dates.dayOf(''), null);
  assert.strictEqual(dates.dayOf(undefined), null);
  assert.strictEqual(dates.dayOf('05.10.2026'), null);
});

test('день недели и понедельник', function () {
  assert.strictEqual(dates.weekday(MON), 0);
  assert.strictEqual(dates.weekday(MON + 5), 5);
  assert.strictEqual(dates.isWeekend(MON + 4), false);
  assert.strictEqual(dates.isWeekend(MON + 5), true);
  assert.strictEqual(dates.isWeekend(MON + 6), true);
  assert.strictEqual(dates.mondayOf(MON + 6), MON);
  assert.strictEqual(dates.mondayOf(MON), MON);
});

test('рабочие дни Пн–Пт в отрезке включительно', function () {
  var mon = dates.dayOf('2026-10-05');
  assert.strictEqual(dates.workdays(mon, mon + 6), 5);      // неделя
  assert.strictEqual(dates.workdays(mon + 5, mon + 6), 0);  // выходные
  assert.strictEqual(dates.workdays(mon + 4, mon + 7), 2);  // пятница и понедельник
  assert.strictEqual(dates.workdays(mon, mon + 13), 10);
  assert.strictEqual(dates.workdays(mon + 1, mon), 0);      // пустой отрезок
});
