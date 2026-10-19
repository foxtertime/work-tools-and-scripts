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
