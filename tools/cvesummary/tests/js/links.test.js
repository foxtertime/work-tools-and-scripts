'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { taskUrl } = require('../../cvesummary/assets/js/links.js');

test('Task ID: идентификатор превращается в адрес портала', () => {
  assert.equal(taskUrl('TASKID-182000'), 'https://portal.works.prod.sbt/swtr/units/current/unit/TASKID-182000');
  assert.equal(taskUrl(182000), 'https://portal.works.prod.sbt/swtr/units/current/unit/182000');
  assert.equal(taskUrl('  TASK-42  '), 'https://portal.works.prod.sbt/swtr/units/current/unit/TASK-42');
});

test('Task ID: идентификатор кодируется как один сегмент пути', () => {
  assert.equal(taskUrl('TASK 42/#?'), 'https://portal.works.prod.sbt/swtr/units/current/unit/TASK%2042%2F%23%3F');
});

test('Task ID: готовый HTTP(S)-адрес сохраняется', () => {
  for (const url of ['https://example.test/task/42', 'HTTP://example.test/task/42']) assert.equal(taskUrl(url), url);
});

test('Task ID: отсутствие значения и сторонние схемы не создают ссылку', () => {
  for (const value of ['', '  ', null, undefined, '-', '—', 'javascript:alert(1)', 'data:text/html,test', '//example.test/42']) {
    assert.equal(taskUrl(value), null, String(value));
  }
});
