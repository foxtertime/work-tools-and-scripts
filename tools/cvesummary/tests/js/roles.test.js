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

/* Дубликаты: пара CVE + компонент. duplicates(rows) → для каждой строки
   индекс основной строки группы, если эта строка — открытый дубликат,
   иначе null. */
function task(cve, comp, dev, status, extra) {
  return row(dev, status, Object.assign({ cve: cve, comp: comp, start: '', tdate: '', bad: [] }, extra || {}));
}

test('одиночные строки — не дубликаты', function () {
  assert.deepStrictEqual(roles.duplicates([task('CVE-1', 'bash', '', ''), task('CVE-1', 'curl', '', ''),
    task('CVE-2', 'bash', '', '')]), [null, null, null]);
});

test('в группе есть «Готов» — все открытые строки группы дубликаты', function () {
  var rows = [task('CVE-1', 'bash', 'A', 'В работе'), task('CVE-1', 'bash', 'B', 'Готов'),
    task('CVE-1', 'bash', '', ''), task('CVE-1', 'bash', 'C', 'Готов')];
  assert.deepStrictEqual(roles.duplicates(rows), [1, null, 1, null]);
});

test('без «Готов» основная — взятая с самой ранней Start date', function () {
  var rows = [task('CVE-1', 'bash', '', '', { tdate: '2026-01-01' }),
    task('CVE-1', 'bash', 'A', 'В работе', { start: '2026-10-05' }),
    task('CVE-1', 'bash', 'B', 'На паузе', { start: '2026-10-02' }),
    task('CVE-1', 'bash', 'C', 'В работе')];
  assert.deepStrictEqual(roles.duplicates(rows), [2, 2, null, 2]);
});

test('взятые без Start date — первая в таблице', function () {
  var rows = [task('CVE-1', 'bash', '', ''), task('CVE-1', 'bash', 'A', 'В работе'),
    task('CVE-1', 'bash', 'B', 'В работе', { start: '05.10.0206', bad: ['start'] })];
  assert.deepStrictEqual(roles.duplicates(rows), [1, null, 1]);
});

test('никто не взял — основная с самой ранней Task date, без даты — после', function () {
  var rows = [task('CVE-1', 'bash', '', ''), task('CVE-1', 'bash', '', '', { tdate: '2026-10-09' }),
    task('CVE-1', 'bash', '', '', { tdate: '2026-10-01' })];
  assert.deepStrictEqual(roles.duplicates(rows), [2, 2, null]);
});

test('равные даты — первая в таблице', function () {
  var rows = [task('CVE-1', 'bash', '', '', { tdate: '2026-10-01' }), task('CVE-1', 'bash', '', '', { tdate: '2026-10-01' })];
  assert.deepStrictEqual(roles.duplicates(rows), [null, 0]);
});

test('ключ без учёта регистра и пробелов; без компонента не группируется', function () {
  var rows = [task('CVE-2026-1', 'bash', '', ''), task(' cve-2026-1 ', ' Bash ', '', ''),
    task('CVE-2026-2', '', '', ''), task('CVE-2026-2', ' ', '', '')];
  assert.deepStrictEqual(roles.duplicates(rows), [null, 0, null, null]);
});

test('дубликат — последнее основание закрыть, у закрытой строки его нет', function () {
  var r = row('X', 'В работе', { rstate: 'fixed' });
  assert.deepStrictEqual(roles.closeReasons(r, true), ['fixed', 'dup']);
  assert.deepStrictEqual(roles.closeReasons(row('X', 'Готов'), true), []);
  assert.deepStrictEqual(roles.closeReasons(row('X', ''), false), []);
});

test('ключ задачи: пара CVE + компонент без учёта регистра и пробелов; без компонента — null', function () {
  assert.strictEqual(roles.taskKey(task(' cve-2026-1 ', 'Bash ')), roles.taskKey(task('CVE-2026-1', 'bash')));
  assert.notStrictEqual(roles.taskKey(task('CVE-2026-1', 'bash')), roles.taskKey(task('CVE-2026-1', 'curl')));
  assert.strictEqual(roles.taskKey(task('CVE-2026-1', ' ')), null);
});

test('счётчики шапки: уникальные задачи, CVE и компоненты', function () {
  var rows = [task('CVE-1', 'bash'), task('cve-1 ', 'BASH'), task('CVE-1', 'curl'), task('CVE-2', ''), task('CVE-2', '')];
  assert.deepStrictEqual(roles.uniques(rows), { tasks: 4, cves: 2, comps: 2 });
});
