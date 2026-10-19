'use strict';
var test = require('node:test');
var assert = require('node:assert');
var strips = require('../../cvesummary/assets/js/strips.js');

test('labels: доля — у частей не уже порога, у остальных пусто', function () {
  assert.deepStrictEqual(strips.labels([50, 30, 15, 5], 0.08, 'pct'), ['50%', '30%', '15%', '']);
  assert.deepStrictEqual(strips.labels([1, 2], 0.08, 'pct'), ['33%', '67%']);
});

test('labels: число вместо доли', function () {
  assert.deepStrictEqual(strips.labels([40, 3, 57], 0.06, 'n'), ['40', '', '57']);
});

test('labels: пустая полоса — без подписей', function () {
  assert.deepStrictEqual(strips.labels([0, 0], 0.08, 'pct'), ['', '']);
  assert.deepStrictEqual(strips.labels([], 0.08, 'pct'), []);
});

test('ink: на светлом — тёмный текст, на тёмном — белый', function () {
  assert.strictEqual(strips.ink('rgb(191, 227, 242)'), strips.DARK);
  assert.strictEqual(strips.ink('rgb(46, 125, 79)'), strips.LIGHT);
  assert.strictEqual(strips.ink('rgba(255, 255, 255, 0.9)'), strips.DARK);
});

test('ink: color-mix браузер отдаёт как color(srgb 0…1)', function () {
  assert.strictEqual(strips.ink('color(srgb 0.93 0.96 0.97)'), strips.DARK);
  assert.strictEqual(strips.ink('color(srgb 0.11 0.42 0.54)'), strips.LIGHT);
});

test('ink: незнакомый формат — белый, как на тёмных частях', function () {
  assert.strictEqual(strips.ink(''), strips.LIGHT);
  assert.strictEqual(strips.ink('oklch(0.7 0.1 200)'), strips.LIGHT);
});
