/* Данные AI (колонки ai_*, их пишет vulnsheet --ai из results.json плагина
   rhel-security): что AI сказал по парам CVE + компонент и сколько ещё не
   прогнано. Пара — по тому же правилу, что счётчик задач в шапке (строка
   без компонента — отдельная пара). Её данные — из строки с вердиктом и
   самой поздней ai_run; при равной или неразобранной — из первой такой.
   Прогнана — пара с настоящим вердиктом; not processed (пара была в
   прогоне, но не разобрана) и пара без вердикта — ещё осталось прогнать.
   Значения сравниваются без учёта регистра; знакомые пишутся по
   справочнику, незнакомые — как пришли. */
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
  const VERDICTS = ['affected', 'not affected', 'unclear', 'invalid CVE', 'rejected CVE', NOT_PROCESSED];
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

  /* Счётчик значений: знакомые — в порядке справочника и его написанием,
     незнакомые — следом, по убыванию числа, затем по алфавиту */
  function tally(known) {
    const by = new Map();
    return {
      add(raw, extra) {
        const k = roles.norm(raw), i = known.findIndex(v => roles.norm(v) === k);
        if (!by.has(k)) by.set(k, Object.assign({ k: i >= 0 ? known[i] : String(raw).trim(), known: i >= 0, n: 0, rank: i }, extra && extra()));
        const x = by.get(k); x.n++; return x;
      },
      list() {
        return [...by.values()].sort((a, b) => (a.known === b.known ? (a.known ? a.rank - b.rank : b.n - a.n || a.k.localeCompare(b.k)) : a.known ? -1 : 1))
          .map(({ rank, ...x }) => x);
      },
    };
  }

  function summary(rows) {
    const verdicts = tally(VERDICTS), remediations = tally(REMEDIATIONS);
    const s = { total: 0, run: 0, notProcessed: 0, notRun: 0, noRemediation: 0, last: null };
    for (const r of pairs(rows)) {
      s.total++;
      if (r === null) { s.notRun++; continue; }
      const v = verdicts.add(r.ai_verdict, () => ({ conf: { high: 0, medium: 0, low: 0, other: 0 } }));
      const c = roles.norm(r.ai_conf);
      v.conf[CONFIDENCE.includes(c) ? c : 'other']++;
      if (roles.norm(r.ai_verdict) === NOT_PROCESSED) { s.notProcessed++; continue; }
      s.run++;
      if (r.ai_rem) remediations.add(r.ai_rem); else s.noRemediation++;
    }
    for (const r of rows) { const run = runOf(r); if (run !== null && (s.last === null || run > s.last)) s.last = run; }
    s.left = s.notRun + s.notProcessed;
    s.verdicts = verdicts.list();
    s.remediations = remediations.list();
    return s;
  }

  return { VERDICTS, CONFIDENCE, REMEDIATIONS, NOT_PROCESSED, summary };
}));
