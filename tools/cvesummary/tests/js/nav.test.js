'use strict';
var test = require('node:test');
var assert = require('node:assert');
var nav = require('../../cvesummary/assets/js/nav.js');

var LINE = 65; // низ строки разделов + запас

test('active: последний раздел, чей верх ушёл под строку', function () {
  assert.strictEqual(nav.active([64, 900, 1700], LINE, false), 0);
  assert.strictEqual(nav.active([-800, 40, 600], LINE, false), 1);
  assert.strictEqual(nav.active([-2000, -900, -10], LINE, false), 2);
});

test('active: короткий раздел наверху — он, а не тот, что посередине экрана', function () {
  assert.strictEqual(nav.active([-1200, 30, 420, 900], LINE, false), 1);
});

test('active: шапка ещё видна — ничего', function () {
  assert.strictEqual(nav.active([700, 1500], LINE, false), -1);
  assert.strictEqual(nav.active([], LINE, false), -1);
});

test('active: внизу страницы — последний, даже если до верха не доехал', function () {
  assert.strictEqual(nav.active([-3000, -400, 300], LINE, true), 2);
});
