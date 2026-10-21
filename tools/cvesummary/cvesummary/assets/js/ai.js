/* AI-покрытие: сколько пар CVE + компонент уже прогнано через AI. Пара —
   по тому же правилу, что счётчик задач в шапке (строка без компонента —
   отдельная пара); прогнана, если хотя бы у одной её строки есть
   ai_verdict. Группа пары — как группы шапки: «готово», если хоть одна
   строка готова, иначе «без решения», если такая строка есть, иначе
   «можно закрыть». */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.ai = factory(root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (roles) {
  'use strict';

  const GROUPS = ['done', 'none', 'ready'];  // и порядок старшинства

  /* groupOf(row) — группа строки: 'done', 'none' или 'ready' */
  function coverage(rows, groupOf) {
    const pairs = new Map();
    rows.forEach((r, i) => {
      const key = roles.taskKey(r) ?? '\u0001' + i;
      const p = pairs.get(key) || { covered: false, g: GROUPS.length };
      p.covered = p.covered || !!r.ai_verdict;
      p.g = Math.min(p.g, GROUPS.indexOf(groupOf(r)));
      pairs.set(key, p);
    });
    const groups = Object.fromEntries(GROUPS.map(g => [g, { total: 0, covered: 0 }]));
    let covered = 0;
    for (const p of pairs.values()) {
      covered += p.covered;
      const g = groups[GROUPS[p.g]];
      if (g) { g.total++; g.covered += p.covered; }
    }
    return { total: pairs.size, covered, groups };
  }

  /* Последний прогон — самая поздняя разобранная ai_run (ISO); нет — null */
  function lastRun(rows) {
    let last = null;
    for (const r of rows) {
      const v = r.ai_run;
      if (v && !(r.bad || []).includes('ai_run') && (last === null || v > last)) last = v;
    }
    return last;
  }

  return { GROUPS, coverage, lastRun };
}));
