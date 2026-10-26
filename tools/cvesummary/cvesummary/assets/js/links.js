/* Адрес задачи из Task ID; сам идентификатор остаётся подписью ссылки. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else { root.CS = root.CS || {}; root.CS.links = factory(); }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const TASK_BASE = 'https://portal.works.prod.sbt/swtr/units/current/unit/';
  function taskUrl(value) {
    const id = String(value ?? '').trim();
    if (!id || id === '-' || id === '—') return null;
    if (/^https?:\/\//i.test(id)) return id;
    if (/^[a-z][a-z\d+.-]*:/i.test(id) || id.startsWith('//')) return null;
    return TASK_BASE + encodeURIComponent(id);
  }
  return { taskUrl };
}));
