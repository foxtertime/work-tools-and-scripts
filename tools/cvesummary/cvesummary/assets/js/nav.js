/* Строка разделов: какой якорь подсвечен. Активен последний раздел, чей
   верх уже ушёл под строку; внизу страницы — последний раздел, даже если
   до верха он не доехал. Пока видна шапка — ни один. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.nav = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /* tops — верх разделов относительно окна, в порядке якорей;
     line — граница под строкой разделов */
  function active(tops, line, atBottom) {
    if (atBottom) return tops.length - 1;
    let k = -1;
    tops.forEach((top, i) => { if (top <= line) k = i; });
    return k;
  }

  return { active };
}));
