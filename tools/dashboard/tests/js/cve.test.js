'use strict';
/* Заглушка раздела CVE: принимает таблицу и честно говорит, что читать её
   не умеет. Настоящая разметка нужна и здесь — зона, поле, кнопка и место
   под имя берутся из шаблона. */
var test = require('node:test');
var assert = require('node:assert');
var domstub = require('./domstub.js');
var cvemod = require('../../dashboard/assets/js/cve.js');

function setup() {
  var dom = domstub.install();
  var shown = [];
  var cve = cvemod.create({
    toasts: { show: function (spec) { shown.push(spec); } },
    dom: { drop: dom.id('cve-drop'), input: dom.id('cve-input'),
           pick: dom.id('cve-pick'), name: dom.id('cve-file') } });
  return { dom: dom, cve: cve, shown: shown,
           drop: dom.id('cve-drop'), name: dom.id('cve-file') };
}

/* Перенос в терминах браузера. Пока он идёт, сами файлы браузер прячет и
   о них говорит одна запись Files в types; на drop появляются и файлы. */
function dragging() { return { types: ['Files'], files: [] }; }
function dropping() {
  var names = Array.prototype.slice.call(arguments);
  return { types: ['Files'],
           files: names.map(function (n) { return { name: n }; }) };
}

function said(shown) {
  return shown.map(function (s) { return s.lines.join(' '); }).join(' ');
}

test('перетаскивание подсвечивает зону, уход гасит', function () {
  var s = setup();
  s.dom.fire(s.drop, 'dragover', { dataTransfer: dragging() });
  assert.equal(s.drop.className, 'drop over');
  s.dom.fire(s.drop, 'dragleave', {});
  assert.equal(s.drop.className, 'drop');
});

test('xlsx принят: имя показано и сказано, что он не прочитан', function () {
  var s = setup();
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('cve-2026.xlsx') });
  assert.equal(s.name.hidden, false);
  assert.equal(s.name.textContent, 'cve-2026.xlsx');
  assert.equal(s.shown.length, 1);
  assert.equal(s.shown[0].kind, 'warn');
  assert.ok(said(s.shown).indexOf('не прочитано') !== -1, said(s.shown));
});

test('чужое расширение отвергнуто, имя не показано', function () {
  var s = setup();
  /* Сначала роняем файл с нужным расширением, чтобы имя стало видимым. Это
     позволяет проверить, что имя *вернулось* в скрытое состояние при отказе,
     а не просто осталось скрытым с самого начала. */
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('cve-2026.xlsx') });
  assert.equal(s.name.hidden, false);
  /* Теперь роняем файл с неправильным расширением. */
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('снапшот.json') });
  assert.equal(s.name.hidden, true);
  /* Будет два сообщения: первое warn о принятии, второе error об отказе. */
  assert.equal(s.shown.length, 2);
  assert.equal(s.shown[1].kind, 'error');
});

test('из пачки берётся первый файл', function () {
  /* Раздел ждёт одну таблицу, а не набор. Молча съесть второй значило бы
     соврать про то, что принято. */
  var s = setup();
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('первый.xlsx', 'второй.xlsx') });
  assert.equal(s.name.textContent, 'первый.xlsx');
  assert.equal(s.shown.length, 1);
});

test('кнопка открывает диалог выбора', function () {
  var s = setup();
  var input = s.dom.id('cve-input');
  var opened = 0;
  input.click = function () { opened += 1; };
  s.dom.id('cve-pick').click();
  assert.equal(opened, 1);
});

test('содержимое файла не читается вовсе', function () {
  /* Заглушка не притворяется работающей: прочитать и промолчать было бы
     хуже, чем не читать и сказать. */
  var s = setup();
  var reads = 0;
  var Real = global.FileReader;
  global.FileReader = function () { reads += 1; return new Real(); };
  try {
    s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('cve.xlsx') });
  } finally {
    global.FileReader = Real;
  }
  assert.equal(reads, 0);
});
