/* Данные AI (колонки ai_*, их пишет vulnsheet --ai из results.json плагина
   rhel-security): что AI сказал по парам CVE + компонент и сколько ещё не
   прогнано. Пара — по тому же правилу, что счётчик задач в шапке (строка
   без компонента — отдельная пара). Её данные — из строки с вердиктом и
   самой поздней ai_run; при равной или неразобранной — из первой такой.
   Прогнана — пара с настоящим вердиктом; not processed (пара была в
   прогоне, но не разобрана) и пара без вердикта — ещё осталось прогнать.
   Значения сравниваются без учёта регистра; знакомые пишутся по
   справочнику, незнакомые — как пришли.
   Группы — по вердикту пары: «возможно затронуто» (affected, unclear и
   незнакомые вердикты), «не затронуто» (not affected, invalid CVE,
   rejected CVE), «не прогнано» (not processed и пары без вердикта).
   Remediation пары — в группе её вердикта. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.ai = factory(root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (roles) {
  'use strict';

  const NOT_PROCESSED = 'not processed';
  const GROUPS = ['maybe', 'no', 'none'];
  /* справочник в порядке групп; группа незнакомого вердикта — maybe */
  const VERDICTS = ['affected', 'unclear', 'not affected', 'invalid CVE', 'rejected CVE', NOT_PROCESSED];
  const VERDICT_GROUP = { 'affected': 'maybe', 'unclear': 'maybe', 'not affected': 'no', 'invalid CVE': 'no',
    'rejected CVE': 'no', [NOT_PROCESSED]: 'none' };
  const CONFIDENCE = ['high', 'medium', 'low'];
  /* сначала фикс есть или готов, потом ручная работа, блокеры, в конце —
     решения без работы */
  const REMEDIATIONS = ['backport prepared', 'vendor update available', 'rebuild required',
    'manual integration required', 'manual remediation required', 'upstream fix unavailable',
    'pending', 'not determined', 'not required'];

  const runOf = r => (r.ai_run && !(r.bad || []).includes('ai_run') ? r.ai_run : null);

  /* Строка с данными AI на каждую пару; у пары без вердикта — null */
  function pairs(rows) {
    const out = new Map();
    rows.forEach((r, i) => {
      const key = roles.taskKey(r) ?? '\u0001' + i;
      const best = out.get(key) ?? null;
      if (!r.ai_verdict) { if (!out.has(key)) out.set(key, null); return; }
      const run = runOf(r);
      if (best === null || (run !== null && (runOf(best) === null || run > runOf(best)))) out.set(key, r);
    });
    return [...out.values()];
  }

  /* Счётчик значений по группам: внутри группы знакомые — в порядке
     справочника и его написанием, незнакомые — следом, по убыванию числа,
     затем по алфавиту; пустое значение (k: '') — последним */
  function tally(known) {
    const by = new Map();
    return {
      add(g, raw, extra) {
        const k = roles.norm(raw), i = k ? known.findIndex(v => roles.norm(v) === k) : -1, key = g + '\u0000' + k;
        if (!by.has(key)) by.set(key, Object.assign({ k: i >= 0 ? known[i] : String(raw || '').trim(), known: i >= 0, n: 0, g, rank: i }, extra && extra()));
        const x = by.get(key); x.n++; return x;
      },
      list() {
        const tier = x => (x.known ? 0 : x.k ? 1 : 2);
        return [...by.values()].sort((a, b) => GROUPS.indexOf(a.g) - GROUPS.indexOf(b.g) || tier(a) - tier(b)
          || (tier(a) === 0 ? a.rank - b.rank : b.n - a.n || a.k.localeCompare(b.k)))
          .map(({ rank, ...x }) => x);
      },
    };
  }

  const groupOf = verdict => VERDICT_GROUP[VERDICTS.find(v => roles.norm(v) === roles.norm(verdict))] || 'maybe';

  function summary(rows) {
    const verdicts = tally(VERDICTS), remediations = tally(REMEDIATIONS);
    const s = { total: 0, run: 0, notProcessed: 0, notRun: 0, noRemediation: 0, last: null,
      groups: Object.fromEntries(GROUPS.map(g => [g, 0])) };
    for (const r of pairs(rows)) {
      s.total++;
      if (r === null) { s.notRun++; s.groups.none++; continue; }
      const g = groupOf(r.ai_verdict);
      s.groups[g]++;
      const v = verdicts.add(g, r.ai_verdict, () => ({ conf: { high: 0, medium: 0, low: 0, other: 0 } }));
      const c = roles.norm(r.ai_conf);
      v.conf[CONFIDENCE.includes(c) ? c : 'other']++;
      if (g === 'none') { s.notProcessed++; continue; }
      s.run++;
      remediations.add(g, r.ai_rem);
      if (!r.ai_rem) s.noRemediation++;
    }
    for (const r of rows) { const run = runOf(r); if (run !== null && (s.last === null || run > s.last)) s.last = run; }
    s.left = s.notRun + s.notProcessed;
    s.verdicts = verdicts.list();
    s.remediations = remediations.list();
    return s;
  }

  return { GROUPS, VERDICTS, CONFIDENCE, REMEDIATIONS, NOT_PROCESSED, summary };
}));
