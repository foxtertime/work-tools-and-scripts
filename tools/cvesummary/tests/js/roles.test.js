'use strict';
var test = require('node:test');
var assert = require('node:assert');
var roles = require('../../cvesummary/assets/js/roles.js');

function row(dev, status, extra) {
  return Object.assign({ dev: dev, status: status, sev: '', measure: '', rstate: '', p: '', d: '' }, extra || {});
}

test('«Готов» — закрыта, без учёта регистра и пробелов', function () {
  ['Готов', ' готов ', 'ГОТОВ'].forEach(function (s) {
    assert.strictEqual(roles.isDone(row('X', s)), true, s);
    assert.strictEqual(roles.isOpen(row('X', s)), false, s);
  });
});

test('статус вне набора — в работе, «Готово» не закрывает', function () {
  var r = row('X', 'Готово');
  assert.strictEqual(roles.isDone(r), false);
  assert.strictEqual(roles.isWorking(r), true);
});

test('без разработчика: не взята, но «Готов» всё равно закрыта', function () {
  assert.strictEqual(roles.isTaken(row(' ', '')), false);
  assert.strictEqual(roles.isWorking(row('', '')), false);
  var done = row('', 'Готов');
  assert.strictEqual(roles.isDone(done), true);
  assert.strictEqual(roles.isTaken(done), false);
});

test('ревью, пауза, внимание — открытые', function () {
  assert.strictEqual(roles.isReview(row('X', 'Ожидает ревью')), true);
  assert.strictEqual(roles.isOpen(row('X', 'Ожидает ревью')), true);
  assert.strictEqual(roles.isPaused(row('X', 'на паузе')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'Есть проблема')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'Нужна  доработка')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'В работе')), false);
});

test('devOf срезает и схлопывает пробелы', function () {
  assert.strictEqual(roles.devOf(row(' Иванов  И.И. ', '')), 'Иванов И.И.');
});

test('критичность: канон, незнакомое как есть, пусто — «Нет оценки»', function () {
  assert.strictEqual(roles.sevOf(row('', '', { sev: 'important' })), 'Important');
  assert.strictEqual(roles.sevOf(row('', '', { sev: 'Severe' })), 'Severe');
  assert.strictEqual(roles.sevOf(row('', '', { sev: '' })), roles.NO_SEVERITY);
  assert.deepStrictEqual(roles.sevOrder(['Low', 'X', 'Нет оценки', 'Critical', 'A', 'Low']),
    ['Critical', 'Low', 'A', 'X', 'Нет оценки']);
});

test('меры: подпись из списка, незнакомое как есть, порядок task.md', function () {
  assert.strictEqual(roles.measureOf(row('', '', { measure: 'патч из апстрима ' })), 'Патч из апстрима');
  assert.strictEqual(roles.measureOf(row('', '', { measure: 'Своё' })), 'Своё');
  assert.strictEqual(roles.measureOf(row('', '', { measure: '' })), roles.NO_MEASURE);
  assert.deepStrictEqual(roles.measureOrder(['Другое', 'Своё', 'не указана', 'Патч из апстрима']),
    ['Патч из апстрима', 'Другое', 'Своё', 'не указана']);
  assert.strictEqual(roles.MEASURES.length, 11);
});

test('основания закрыть — только у открытых', function () {
  var r = row('X', 'В работе', { rstate: 'fixed', p: '+', d: '+' });
  assert.deepStrictEqual(roles.closeReasons(r), ['fixed', 'patch', 'range']);
  assert.deepStrictEqual(roles.closeReasons(row('X', 'Готов', { rstate: 'Fixed' })), []);
  assert.deepStrictEqual(roles.closeReasons(row('X', '', { p: '-', d: '' })), []);
});
