/* Дни как целые числа — сутки от 1970-01-01 по UTC. Дни складываются,
   сравниваются и не зависят от часового пояса браузера; в строку их
   переводят только для показа. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.dates = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DAY_MS = 864e5;

  function dayOf(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? Date.UTC(+m[1], m[2] - 1, +m[3]) / DAY_MS : null;
  }
  function isoOf(day) { return new Date(day * DAY_MS).toISOString().slice(0, 10); }
  function ruOf(day) { const s = isoOf(day); return `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}`; }
  function weekday(day) { return (new Date(day * DAY_MS).getUTCDay() + 6) % 7; }
  function isWeekend(day) { return weekday(day) >= 5; }
  function mondayOf(day) { return day - weekday(day); }

  return { dayOf, isoOf, ruOf, weekday, isWeekend, mondayOf };
}));
