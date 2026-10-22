'use strict';
var test = require('node:test');
var assert = require('node:assert');
var strips = require('../../cvesummary/assets/js/strips.js');

test('labels: доля — у каждой непустой части, влезет ли — решает страница', function () {
  assert.deepStrictEqual(strips.labels([50, 30, 15, 5], 'pct'), ['50%', '30%', '15%', '5%']);
  assert.deepStrictEqual(strips.labels([1, 2], 'pct'), ['33%', '67%']);
});

test('labels: число вместо доли', function () {
  assert.deepStrictEqual(strips.labels([40, 3, 57], 'n'), ['40', '3', '57']);
});

test('labels: пустая часть и пустая полоса — без подписей', function () {
  assert.deepStrictEqual(strips.labels([4, 0], 'n'), ['4', '']);
  assert.deepStrictEqual(strips.labels([0, 0], 'pct'), ['', '']);
  assert.deepStrictEqual(strips.labels([], 'pct'), []);
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

test('rows: строка разреза — от ячейки-ключа до следующей, шапка не входит', function () {
  var cells = [{ h: 1 }, { h: 1 }, { k: 'a' }, {}, {}, { k: 'b' }, {}, { h: 1 }, {}];
  var isKey = function (c) { return !!c.k; }, isHead = function (c) { return !!c.h; };
  assert.deepStrictEqual(strips.rows(cells, isKey, isHead), [[2, 3, 4], [5, 6, 8]]);
});

test('rows: без строк — пусто', function () {
  var isKey = function (c) { return !!c.k; }, isHead = function (c) { return !!c.h; };
  assert.deepStrictEqual(strips.rows([{ h: 1 }, {}], isKey, isHead), []);
  assert.deepStrictEqual(strips.rows([], isKey, isHead), []);
});
