/* Пул эпика и отдельно история работы для скорости. Исходные строки
   сохраняются для явных выборок «Убрано из эпика» и истории поступления. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./dates.js'), require('./roles.js'));
  else { root.CS = root.CS || {}; root.CS.scope = factory(root.CS.dates, root.CS.roles); }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles) {
  'use strict';
  function split(rows, asOf) {
    const pool = [], removed = [], speed = [];
    for (const r of rows) {
      if (!roles.isRemoved(r)) { pool.push(r); speed.push(r); continue; }
      removed.push(r);
      if (!roles.isTaken(r) || roles.norm(r.dev) === 'secops' || !roles.isDone(r)) continue;
      const start = dates.dayOf(r.start), end = dates.dayOf(roles.endOf(r));
      if (start !== null && end !== null && start <= end && end <= asOf) speed.push(r);
    }
    return { pool, removed, speed };
  }
  // Task date — дата создания; сам день сканфриза не включается.
  function afterFreeze(rows, stop, asOf) {
    if (stop == null) return [];
    return rows.filter(r => {
      if (roles.isRemoved(r) || (r.bad || []).includes('tdate')) return false;
      const day = dates.dayOf(r.tdate);
      return day !== null && day > stop && day <= asOf;
    });
  }
  return { split, afterFreeze };
}));
