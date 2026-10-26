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
  const isTriaged = r => (norm(r.dev) === 'secops' && norm(r.measure) === 'закрыто secops') || norm(r.exec) === 'уа';

  /* dup — строка открытый дубликат (см. duplicates); основание последнее */
  function closeReasons(r, dup) {
    if (isDone(r)) return [];
    const out = [];
    if (norm(r.rstate) === 'fixed') out.push('fixed');
    if (String(r.p || '').trim() === '+') out.push('patch');
    if (String(r.d || '').trim() === '+') out.push('range');
    if (dup) out.push('dup');
    return out;
  }

  /* Задача — пара CVE ID + компонент; строк с одной парой бывает несколько.
     Для каждой строки — индекс основной строки группы, если сама строка
     открытый дубликат, иначе null. Основная: строка «Готов», если такая в
     группе есть (тогда дубликаты все открытые); иначе взятая разработчиком
     с самой ранней Start date; если не взял никто — с самой ранней Task
     date. Нет даты или она не разобралась — после датированных; при
     равенстве — первая в таблице. Без компонента строка не группируется. */
  /* Ключ задачи — пара CVE + компонент; без компонента задачу не с чем
     сопоставить — null. */
  const taskKey = r => (norm(r.comp) ? norm(r.cve) + '\u0000' + norm(r.comp) : null);

  /* Счётчики шапки по тому же правилу, что дубликаты: уникальные задачи —
     пары CVE + компонент (строка без компонента — отдельная задача) — и
     компоненты. */
  function uniques(rows) {
    const keys = rows.map(taskKey);
    return {
      tasks: new Set(keys.filter(k => k !== null)).size + keys.filter(k => k === null).length,
      comps: new Set(rows.map(r => norm(r.comp)).filter(Boolean)).size,
    };
  }

  function duplicates(rows) {
    const day = (r, key) => {
      const v = String(r[key] || '');
      return /^\d{4}-\d{2}-\d{2}$/.test(v) && !(r.bad || []).includes(key) ? v : null;
    };
    const earliest = (idx, key) => idx.reduce((best, i) => {
      const a = day(rows[i], key), b = day(rows[best], key);
      return a !== null && (b === null || a < b) ? i : best;
    });
    const groups = new Map();
    rows.forEach((r, i) => {
      const key = taskKey(r);
      if (key === null) return;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(i);
    });
    const out = rows.map(() => null);
    for (const idx of groups.values()) {
      if (idx.length < 2) continue;
      const done = idx.filter(i => isDone(rows[i]));
      const taken = idx.filter(i => isTaken(rows[i]));
      const main = done.length ? done[0] : taken.length ? earliest(taken, 'start') : earliest(idx, 'tdate');
      for (const i of idx) if (i !== main && isOpen(rows[i])) out[i] = main;
    }
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
    needsAttention, isTriaged, closeReasons, taskKey, uniques, duplicates, sevOf, sevOrder, measureOf, measureOrder,
    SEVERITIES, MEASURES, NO_SEVERITY, NO_MEASURE };
}));
