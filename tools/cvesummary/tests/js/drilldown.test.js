'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const drilldown = require('../../cvesummary/assets/js/drilldown.js');
const roles = require('../../cvesummary/assets/js/roles.js');
const ai = require('../../cvesummary/assets/js/ai.js');

test('поиск: регистр, пробелы, несколько слов и скрытые поля', () => {
  const rows = [
    { row: 3, comp: 'OpenSSL', dev: 'Иванов', comment: 'ждём апстрим' },
    { row: 4, comp: 'openssl', dev: 'Петров', comment: '' },
    { row: 5, comp: 'curl', dev: 'Иванов', comment: '' },
  ];
  assert.deepEqual(drilldown.select(rows, '  OPENSSL  иванов ').map(r => r.row), [3]);
  assert.deepEqual(drilldown.select(rows, 'АПСТРИМ').map(r => r.row), [3]);
  assert.deepEqual(drilldown.select(rows, 'не существует'), []);
});

test('сортировка CVSS: числа, десятичная запятая, ноль и неизвестное', () => {
  const rows = [
    { row: 3, cvss: '' }, { row: 4, cvss: '9,8' }, { row: 5, cvss: '7.5' },
    { row: 6, cvss: '0' }, { row: 7, cvss: 'неизвестно' },
  ];
  assert.deepEqual(drilldown.select(rows, '').map(r => r.row), [4, 5, 6, 3, 7]);
  assert.deepEqual(drilldown.select(rows, '', 'cvss', 'asc').map(r => r.row), [6, 5, 4, 3, 7]);
});

test('сортировка: естественный порядок названий и стабильные совпадения', () => {
  const rows = [{ row: 5, comp: 'pkg10' }, { row: 4, comp: 'pkg2' }, { row: 3, comp: 'pkg2' }];
  assert.deepEqual(drilldown.select(rows, '', 'comp', 'asc').map(r => r.row), [3, 4, 5]);
  assert.deepEqual(drilldown.select(rows, '', 'comp', 'desc').map(r => r.row), [5, 3, 4]);
});

test('сортировка дат: неразобранные и отсутствующие даты идут последними', () => {
  const rows = [
    { row: 3, start: '2026-10-20', bad: [] }, { row: 4, start: '', bad: [] },
    { row: 5, start: '2026-10-19', bad: ['start'] }, { row: 6, start: '2026-10-18', bad: [] },
  ];
  assert.deepEqual(drilldown.select(rows, '', 'start', 'asc').map(r => r.row), [6, 3, 4, 5]);
});

test('выборка не изменяет исходный массив или записи', () => {
  const rows = [Object.freeze({ row: 4, cvss: '2' }), Object.freeze({ row: 3, cvss: '9' })];
  Object.freeze(rows);
  assert.deepEqual(drilldown.select(rows, '').map(r => r.row), [3, 4]);
  assert.deepEqual(rows.map(r => r.row), [4, 3]);
});

test('CSV: UTF-8 BOM, разделитель, кавычки, переводы строк и дополнительные поля', () => {
  const csv = drilldown.csv([{ row: 3, cve: 'CVE-2026-1234', comment: 'a;"b"\nc', slnvr: 'pkg-1-2', link: 'https://example.test/cve' }]);
  assert.ok(csv.startsWith('\ufeff"Строка";"Task ID";"CVE"'));
  assert.ok(csv.includes('"a;""b""\nc"'));
  assert.ok(csv.includes('"pkg-1-2"'));
  assert.ok(csv.includes('"https://example.test/cve"'));
  assert.equal(csv.split('\r\n').length, 2);
});

test('CSV: потенциальные формулы экранируются, обычные значения сохраняются', () => {
  for (const task of ['=1+1', '+1+1', '-1+1', '@SUM(A1)', '\t=1+1', '\r=1+1', '\n=1+1']) {
    assert.ok(drilldown.csv([{ task }]).includes('"\'' + task + '"'));
  }
  assert.ok(drilldown.csv([{ task: 'TASK-123' }]).includes('"TASK-123"'));
  assert.equal(drilldown.csv([]).split('\r\n').length, 1);
});

function aiRow(i, extra) {
  return { i, row: i + 3, cve: 'CVE-2026-1001', comp: 'openssl', ai_verdict: '', ai_run: '', bad: [], ...extra };
}

test('AI: самый свежий вердикт пары совпадает с выбором сводки', () => {
  const rows = [
    aiRow(0, { ai_verdict: 'affected', ai_run: '2026-10-18' }),
    aiRow(1, { comp: ' OPENSSL ', ai_verdict: 'not affected', ai_run: '2026-10-19' }),
    aiRow(2, { ai_verdict: 'unclear' }),
    aiRow(3, { comp: 'curl' }),
  ];
  const selected = drilldown.aiRows(rows, roles);
  assert.deepEqual(selected.map(r => r.i), [1, 3]);
  const summary = ai.summary(rows);
  assert.equal(selected.length, summary.total);
  assert.equal(selected.filter(r => r.ai_verdict).length, summary.run);
});

test('AI: равные даты сохраняют первый вердикт, неразобранная дата не заменяет его', () => {
  const rows = [
    aiRow(0, { ai_verdict: 'affected', ai_run: '2026-10-18' }),
    aiRow(1, { ai_verdict: 'not affected', ai_run: '2026-10-18' }),
    aiRow(2, { ai_verdict: 'unclear', ai_run: '2026-10-21', bad: ['ai_run'] }),
  ];
  assert.equal(drilldown.aiRows(rows, roles)[0], rows[0]);
});

test('AI: настоящий вердикт заменяет строку без вердикта, not processed сохраняется', () => {
  const rows = [aiRow(0), aiRow(1, { ai_verdict: 'not processed' })];
  assert.equal(drilldown.aiRows(rows, roles)[0], rows[1]);
  assert.equal(ai.summary(rows).notProcessed, 1);
});

test('AI: строки без компонента остаются отдельными, пустая выборка допустима', () => {
  const rows = [aiRow(0, { comp: '' }), aiRow(1, { comp: '' })];
  assert.equal(drilldown.aiRows(rows, roles).length, 2);
  assert.deepEqual(drilldown.aiRows([], roles), []);
});
