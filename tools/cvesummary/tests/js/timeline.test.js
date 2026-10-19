'use strict';
var test = require('node:test');
var assert = require('node:assert');
var timeline = require('../../cvesummary/assets/js/timeline.js');

test('layout: помещается — растягивается, нет — минимальный шаг', function () {
  assert.deepStrictEqual(timeline.layout(10, 10, 300), { width: 300, step: 30 });
  assert.deepStrictEqual(timeline.layout(100, 10, 300), { width: 1000, step: 10 });
  assert.deepStrictEqual(timeline.layout(0, 10, 300), { width: 300, step: 300 });
});

test('edges: где есть данные за краем', function () {
  assert.deepStrictEqual(timeline.edges(0, 1000, 300), { left: false, right: true });
  assert.deepStrictEqual(timeline.edges(700, 1000, 300), { left: true, right: false });
  assert.deepStrictEqual(timeline.edges(350, 1000, 300), { left: true, right: true });
  assert.deepStrictEqual(timeline.edges(0, 300, 300), { left: false, right: false });
});

test('scale: не больше шести делений, шаг 1-2-2,5-5 на любом масштабе', function () {
  assert.deepStrictEqual(timeline.scale(0), { yMax: 1, yStep: 1 });
  assert.deepStrictEqual(timeline.scale(5), { yMax: 5, yStep: 1 });
  assert.deepStrictEqual(timeline.scale(12), { yMax: 12, yStep: 2 });
  assert.deepStrictEqual(timeline.scale(30), { yMax: 30, yStep: 5 });
  assert.deepStrictEqual(timeline.scale(150), { yMax: 150, yStep: 25 });
  assert.deepStrictEqual(timeline.scale(6254), { yMax: 8000, yStep: 2000 });
  [3, 7, 45, 333, 999, 1001, 6254, 10000, 123456].forEach(function (top) {
    var s = timeline.scale(top);
    assert.ok(s.yMax >= top && s.yMax / s.yStep <= 6, top + ': ' + JSON.stringify(s));
    assert.strictEqual(s.yStep, Math.round(s.yStep));
  });
});

test('lanes: подпись встаёт в первую свободную строку', function () {
  assert.deepStrictEqual(timeline.lanes([0, 100, 200], 64), [0, 0, 0]);
  assert.deepStrictEqual(timeline.lanes([0, 30, 60], 64), [0, 1, 2]);
  // 0 и 39 близко, 90 далеко от 0 и близко к 39 — первая строка свободна
  assert.deepStrictEqual(timeline.lanes([0, 39, 90], 64), [0, 1, 0]);
});

test('sync: убранный со страницы график не ломается', function () {
  assert.doesNotThrow(function () { timeline.sync({ scrollLeft: 0, scrollWidth: 10, clientWidth: 5, parentElement: null }); });
});
