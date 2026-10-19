/* Роли задач по статусу разработчика и справочники из task.md. Task state
   здесь нет и не будет: он из тасктрекера и в расчётах не участвует. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.roles = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const norm = s => String(s == null ? '' : s).trim().replace(/\s+/g, ' ').toLowerCase();
  const DONE = 'готов', REVIEW = 'ожидает ревью', PAUSED = 'на паузе';
  const ATTENTION = ['есть проблема', 'нужна доработка'];
  const SEVERITIES = ['Critical', 'Important', 'Moderate', 'Low'];
  const MEASURES = ['Патч из апстрима', 'Импорт новой версии', 'Тег свежего билда',
    'Пакет пересобран (если в зависимостях)', 'Обоснована неприменимость',
    'Патч из прошлой ветки', 'Самописный патч', 'Было исправлено ранее',
    'Закрыто SecOps', 'Написана мера компенсации', 'Другое'];
  const NO_SEVERITY = 'Нет оценки', NO_MEASURE = 'не указана';

  const devOf = r => String(r.dev == null ? '' : r.dev).trim().replace(/\s+/g, ' ');
  const isTaken = r => devOf(r) !== '';
  const isDone = r => norm(r.status) === DONE;
  const isOpen = r => !isDone(r);
  const isWorking = r => isTaken(r) && !isDone(r);
  const isReview = r => norm(r.status) === REVIEW;
  const isPaused = r => norm(r.status) === PAUSED;
  const needsAttention = r => ATTENTION.includes(norm(r.status));

  function closeReasons(r) {
    if (isDone(r)) return [];
    const out = [];
    if (norm(r.rstate) === 'fixed') out.push('fixed');
    if (String(r.p || '').trim() === '+') out.push('patch');
    if (String(r.d || '').trim() === '+') out.push('range');
    return out;
  }

  /* Значение из справочника — его подписью, чужое — как есть, пустое —
     заглушкой. */
  function pick(raw, known, empty) {
    const k = norm(raw);
    if (!k) return empty;
    return known.find(v => norm(v) === k) || String(raw).trim().replace(/\s+/g, ' ');
  }
  /* Сначала справочник в его порядке, потом чужие по алфавиту, заглушка
     последней. */
  function order(values, known, empty) {
    const rank = v => { const i = known.indexOf(v); return i >= 0 ? i : v === empty ? known.length + 1 : known.length; };
    return [...new Set(values)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, 'ru'));
  }

  const sevOf = r => pick(r.sev, SEVERITIES, NO_SEVERITY);
  const measureOf = r => pick(r.measure, MEASURES, NO_MEASURE);
  const sevOrder = values => order(values, SEVERITIES, NO_SEVERITY);
  const measureOrder = values => order(values, MEASURES, NO_MEASURE);

  return { norm, devOf, isTaken, isDone, isOpen, isWorking, isReview, isPaused,
    needsAttention, closeReasons, sevOf, sevOrder, measureOf, measureOrder,
    SEVERITIES, MEASURES, NO_SEVERITY, NO_MEASURE };
}));
