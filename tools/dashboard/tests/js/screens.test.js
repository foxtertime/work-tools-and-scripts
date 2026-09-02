'use strict';
/* Разделы страницы на настоящей разметке: дерево строится из
   dashboard.html, поэтому пропавший в шаблоне id роняет тест, а не вид
   страницы. Ни данных, ни снапшотов сюда не завозим — модуль о них не
   знает. */
var test = require('node:test');
var assert = require('node:assert');
var domstub = require('./domstub.js');
var screensmod = require('../../dashboard/assets/js/screens.js');

function setup() {
  var dom = domstub.install();
  var screens = screensmod.create({
    isle: dom.id('isle'),
    sections: { builds: dom.id('screen-builds'), cve: dom.id('screen-cve') } });
  return { dom: dom, screens: screens,
           builds: dom.id('screen-builds'), cve: dom.id('screen-cve') };
}

/* Кнопку ищем по разделу, а не по порядку в островке: порядок кнопок —
   дело вида, и тест не должен падать от их перестановки. */
function button(dom, name) {
  var all = dom.id('isle').querySelectorAll('[data-screen]'), i;
  for (i = 0; i < all.length; i++) {
    if (all[i].getAttribute('data-screen') === name) return all[i];
  }
  throw new Error('в островке нет кнопки ' + name);
}

test('страница открывается на билдах', function () {
  var s = setup();
  assert.equal(s.screens.current(), 'builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});

test('клик по кнопке меняет раздел', function () {
  var s = setup();
  button(s.dom, 'cve').click();
  assert.equal(s.screens.current(), 'cve');
  assert.equal(s.builds.hidden, true);
  assert.equal(s.cve.hidden, false);
});

test('активная кнопка помечена, неактивная теряет отметку', function () {
  /* Атрибут снимается целиком, а не ставится в false: aria-current="false"
     читается вслух как признак, а не как его отсутствие. */
  var s = setup();
  assert.equal(button(s.dom, 'builds').getAttribute('aria-current'), 'page');
  assert.equal(button(s.dom, 'cve').getAttribute('aria-current'), null);
  button(s.dom, 'cve').click();
  assert.equal(button(s.dom, 'cve').getAttribute('aria-current'), 'page');
  assert.equal(button(s.dom, 'builds').getAttribute('aria-current'), null);
});

test('незнакомый раздел приводится к билдам, а не роняет страницу', function () {
  var s = setup();
  s.screens.show('cve');
  s.screens.show('нет такого');
  assert.equal(s.screens.current(), 'builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});

test('возврат в билды снова показывает раздел', function () {
  /* Пока билды скрыты, viewport.js меряет нулевую высоту панели и кладёт
     её в --controls-h — отступ липкой шапки таблицы. Значение
     восстанавливается на возврате; проверять это должен тест, а не
     следующий читатель. */
  var s = setup();
  s.screens.show('cve');
  s.screens.show('builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});
