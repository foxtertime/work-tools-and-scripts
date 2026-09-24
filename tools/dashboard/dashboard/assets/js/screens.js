/* Разделы страницы: какой из них показан. Островок слева переключает
   Builds и CVE, и это всё, что модуль знает. Ни данных, ни таблиц, ни
   файлов он не касается: у разделов и снапшотов общего нет ничего, и
   связь между двумя уровнями заводить незачем. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KP = root.KP || {};
    root.KP.screens = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, () => {
  'use strict';

  const DEFAULT = 'builds';

  function create(deps) {
    const isle = deps.isle, sections = deps.sections;
    let current = DEFAULT;

    function known(name) {
      return Object.prototype.hasOwnProperty.call(sections, name);
    }

    function show(name) {
      /* Незнакомое имя приводим к разделу по умолчанию, а не роняем
         страницу: тем же приёмом showTab приводит diff к state, когда
         сравнивать нечего. */
      current = known(name) ? name : DEFAULT;
      for (const key of Object.keys(sections)) {
        sections[key].hidden = key !== current;
      }
      for (const btn of isle.querySelectorAll('[data-screen]')) {
        /* aria-current, а не aria-selected: тот живёт в паре с ролью tab,
           а островок — навигация по разделам. У неактивной кнопки атрибут
           снимается целиком: "false" читается вслух как признак, а не как
           его отсутствие. */
        if (btn.getAttribute('data-screen') === current) {
          btn.setAttribute('aria-current', 'page');
        } else {
          btn.removeAttribute('aria-current');
        }
      }
    }

    /* Обработчик делегированный и висит на самом островке: кнопки в нём
       заданы разметкой, но искать их поимённо значило бы переписывать
       модуль на каждый новый раздел. */
    isle.addEventListener('click', (e) => {
      let node = e.target;
      while (node && node !== isle) {
        const name = node.getAttribute && node.getAttribute('data-screen');
        if (name) { show(name); return; }
        node = node.parentNode;
      }
    });

    show(DEFAULT);

    return { show: show, current: () => current };
  }

  return { create };
}));
