/* Графики по времени показывают весь период. Если он в ширину карточки
   не помещается, столбики листаются внутри графика: полосы прокрутки не
   видно, у края с продолжением — градиент, мышью можно тащить. Колесо,
   Shift+колесо, тачпад и палец работают сами — это обычный overflow-x. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.timeline = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SLOP = 1;     // px: дробная прокрутка у края — ещё не «есть данные»
  const DRAG = 3;     // px: меньше — это клик, а не перетаскивание

  function layout(count, minStep, avail) {
    const width = Math.max(avail, count * minStep);
    return { width, step: count ? width / count : width };
  }

  function edges(left, scrollWidth, clientWidth) {
    return { left: left > SLOP, right: left + clientWidth < scrollWidth - SLOP };
  }

  /* Шкала значений: самый мелкий шаг из 1, 2, 2,5, 5 × 10ⁿ (2,5 — только
     с 25), при котором делений не больше шести — и на десятке задач, и на
     десятках тысяч. */
  const MAX_TICKS = 6;
  function scale(top) {
    top = Math.max(1, top);
    for (let p = 1; ; p *= 10) {
      for (const m of p === 1 ? [1, 2, 5] : [1, 2, 2.5, 5]) {
        const step = m * p;
        if (Math.ceil(top / step) <= MAX_TICKS) return { yMax: Math.ceil(top / step) * step, yStep: step };
      }
    }
  }

  /* Строки подписей по возрастающим x: подпись встаёт в первую строку, где
     ближайшая левая подпись дальше gap. */
  function lanes(xs, gap) {
    const last = [];
    return xs.map(x => {
      let row = 0;
      while (row < last.length && x - last[row] < gap) row++;
      last[row] = x;
      return row;
    });
  }

  function sync(box) {
    // график могли перерисовать, а прокрутка старого ещё доходит
    if (!box.parentElement) return;
    const e = edges(box.scrollLeft, box.scrollWidth, box.clientWidth);
    box.parentElement.classList.toggle('fade-l', e.left);
    box.parentElement.classList.toggle('fade-r', e.right);
  }

  function attach(box) {
    box.addEventListener('scroll', () => sync(box), { passive: true });
    let drag = null;
    box.addEventListener('pointerdown', ev => {
      if (ev.pointerType !== 'mouse' || ev.button !== 0) return;
      drag = { x: ev.clientX, left: box.scrollLeft, id: ev.pointerId };
    });
    const stop = () => { drag = null; box.classList.remove('dragging'); };
    box.addEventListener('pointermove', ev => {
      if (!drag || ev.pointerId !== drag.id) return;
      // кнопку отпустили за пределами графика до порога: pointerup сюда не дошёл
      if (ev.buttons === 0) { stop(); return; }
      const dx = ev.clientX - drag.x;
      if (Math.abs(dx) < DRAG && !box.classList.contains('dragging')) return;
      if (!box.classList.contains('dragging')) { box.classList.add('dragging'); box.setPointerCapture(drag.id); }
      box.scrollLeft = drag.left - dx;
    });
    box.addEventListener('pointerup', stop);
    box.addEventListener('pointercancel', stop);
  }

  return { layout, edges, scale, lanes, sync, attach };
}));
