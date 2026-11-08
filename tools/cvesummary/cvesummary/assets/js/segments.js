/* Единые непересекающиеся сегменты для полос и их выборок по клику.
   В отдельном блоке убранных завершённая работа разбивается по мерам,
   оставшиеся задачи — по группам AI-вердикта исходной строки. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./roles.js'), require('./scope.js'), require('./ai.js'));
  else { root.CS = root.CS || {}; root.CS.segments = factory(root.CS.roles, root.CS.scope, root.CS.ai); }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (roles, scope, ai) {
  'use strict';
  const removedPart = { key: 'removed', label: 'Убрано из эпика', color: '--st-removed', group: 'removed', test: roles.isRemoved };
  function removed(rows, asOf) {
    const split = scope.split(rows, asOf), completed = new Set(split.speed);
    const done = split.removed.filter(r => completed.has(r)), measures = new Map();
    for (const r of done) {
      const measure = roles.measureOf(r);
      if (!measures.has(measure)) measures.set(measure, []);
      measures.get(measure).push(r);
    }
    const rest = split.removed.filter(r => !completed.has(r));
    const aiLabels = { maybe: 'Возможно затронуто', no: 'Не затронуто', none: 'Не прогнано' };
    return [
      { key: 'done', label: 'Готово', color: '--st-done', rows: done,
        parts: roles.measureOrder([...measures.keys()]).map((measure, i) => ({
          key: 'done-measure-' + i, label: measure, measure, group: 'done', rows: measures.get(measure),
        })) },
      { key: 'removed', label: 'Убрано', color: '--st-removed', rows: rest,
        parts: ai.GROUPS.map(aiGroup => ({
          key: 'removed-ai-' + aiGroup, label: aiLabels[aiGroup], aiGroup, group: 'removed',
          rows: rest.filter(r => ai.groupOf(r.ai_verdict) === aiGroup),
        })).filter(p => p.rows.length) },
    ];
  }
  function partition(rows, definitions, qualify = true) {
    const hasRemoved = qualify && rows.some(roles.isRemoved);
    return [removedPart, ...definitions].map(p => ({
      key: p.key, label: p.label + (hasRemoved && p.key !== 'removed' ? ' (без убранных)' : ''),
      color: p.color, group: p.group,
      rows: rows.filter(r => p.key === 'removed' ? roles.isRemoved(r) : !roles.isRemoved(r) && p.test(r)),
    })).filter(p => p.rows.length);
  }
  function hero(rows) {
    return partition(rows.filter(r => !roles.isRemoved(r)), [
      { key: 'done', label: 'Готово', color: '--st-done', group: 'done', test: roles.isDone },
      { key: 'review', label: 'Ревью', color: '--st-review', group: 'review', test: roles.isReview },
      { key: 'work', label: 'В работе', color: '--st-work', group: 'work', test: r => roles.isWorking(r) && !roles.isReview(r) },
      { key: 'none', label: 'Не взято', color: '--rs-none', group: 'none', test: r => roles.isOpen(r) && !roles.isReview(r) && !roles.isWorking(r) && !r.reasons.length },
      ...[['fixed', 'Фикс в RHEL'], ['patch', 'Устранено ранее'], ['range', 'Вне диапазона'], ['dup', 'Дубликат']]
        .map(([key, label]) => ({ key, label, color: '--rs-' + key, group: 'ready', test: r => roles.isOpen(r) && !roles.isReview(r) && !roles.isWorking(r) && r.reasons[0] === key })),
    ], false);
  }
  // Категории блока «Состояние» не пересекаются; нулевые счётчики остаются.
  function heroState(rows) {
    return [removedPart,
      { key: 'done', label: 'Готов', color: '--st-done', test: roles.isDone },
      { key: 'work', label: 'В работе', color: '--st-work', test: roles.isWorking },
      { key: 'none', label: 'Не взято', color: '--st-idle', test: r => roles.isOpen(r) && !roles.isTaken(r) },
    ].map(p => ({ key: p.key, label: p.label, color: p.color,
      rows: rows.filter(r => p.key === 'removed' ? roles.isRemoved(r) : !roles.isRemoved(r) && p.test(r)),
    }));
  }
  const personRoles = [
    { key: 'done', label: 'Готово', color: '--st-done', test: roles.isDone },
    { key: 'work', label: 'В работе', color: '--st-work', test: r => roles.isWorking(r) && !roles.isReview(r) && !roles.isPaused(r) && !roles.needsAttention(r) },
    { key: 'review', label: 'Ожидает ревью', color: '--st-review', test: r => roles.isWorking(r) && roles.isReview(r) },
    { key: 'pause', label: 'На паузе', color: '--st-pause', test: r => roles.isWorking(r) && roles.isPaused(r) },
    { key: 'bad', label: 'Проблемы', color: '--st-bad', test: r => roles.isWorking(r) && roles.needsAttention(r) },
  ];
  const person = rows => partition(rows, personRoles.map(p => ({ ...p, group: p.key })));
  // Семантические счётчики включают убранные задачи и сохраняют нулевые строки.
  const personCounts = rows => personRoles.map(p => ({ ...p, rows: rows.filter(p.test) }));
  function groups(parts) {
    const out = new Map();
    for (const p of parts) {
      if (!out.has(p.group)) out.set(p.group, { key: p.group,
        label: p.group === 'ready' ? 'Можно закрыть' : p.label, rows: [] });
      out.get(p.group).rows.push(...p.rows);
    }
    return [...out.values()];
  }
  function uniqueRows(rows, duplicates) {
    const out = new Map();
    rows.forEach((r, i) => {
      const key = roles.taskKey(r) ?? '\u0001' + i, prev = out.get(key);
      if (!prev || (roles.isRemoved(prev) && !roles.isRemoved(r)) ||
        (roles.isRemoved(prev) === roles.isRemoved(r) && roles.isDone(r) && !roles.isDone(prev))) out.set(key, r);
    });
    rows.forEach((r, i) => { if (duplicates[i] !== null && duplicates[i] !== undefined) out.set(roles.taskKey(r), rows[duplicates[i]]); });
    return [...out.values()];
  }
  return { hero, heroState, person, personCounts, groups, uniqueRows, removed };
}));
