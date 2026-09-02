/* Заглушка раздела CVE: принимает таблицу xlsx и честно говорит, что
   читать её ещё не умеет.

   Устроена как files.js — владеет своей зоной, полем и кнопкой, получает
   узлы через deps.dom, о результате рассказывает через toasts, но окошка
   не рисует: показывать сообщения дело toasts, а дело этого модуля —
   принять файл. Содержимое не читается вовсе: прочитать и промолчать
   было бы хуже, чем не читать и сказать. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KP = root.KP || {};
    root.KP.cve = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, () => {
  'use strict';

  function create(deps) {
    const toasts = deps.toasts;
    const drop = deps.dom.drop, input = deps.dom.input;
    const pick = deps.dom.pick, nameBox = deps.dom.name;

    function markOver(on) { drop.className = on ? 'drop over' : 'drop'; }

    function accept(list) {
      /* Берём первый файл пачки: раздел ждёт одну таблицу, а не набор. */
      const file = list && list.length ? list[0] : null;
      if (!file) return;
      if (!/\.xlsx$/i.test(String(file.name))) {
        nameBox.hidden = true;
        toasts.show({ kind: 'error', title: 'Не та таблица',
                      lines: [`${file.name}: раздел ждёт файл .xlsx`] });
        return;
      }
      nameBox.textContent = file.name;
      nameBox.hidden = false;
      toasts.show({ kind: 'warn', title: 'Файл принят',
                    lines: [`${file.name}: разбор xlsx ещё не сделан, `
                            + `содержимое не прочитано`] });
    }

    /* Спрашиваем два признака, потому что до отпускания доступен только
       первый: пока перенос идёт, сами файлы браузер прячет. Слово в слово
       как в files.js — там же сказано, почему. */
    function hasFiles(e) {
      const data = e.dataTransfer;
      if (!data) return false;
      if (data.files && data.files.length) return true;
      return Array.from(data.types || []).indexOf('Files') !== -1;
    }

    pick.addEventListener('click', () => input.click());

    input.addEventListener('change', () => {
      accept(input.files);
      /* Тот же файл, выбранный второй раз, не даёт события, пока в поле
         лежит его прежнее значение. */
      input.value = '';
    });

    /* Слушаем свою зону, а не документ: документ уже слушает files.js, и
       второй слушатель на нём означал бы, что один брошенный файл приняли
       дважды. На этом разделе кроме зоны ничего и нет. */
    drop.addEventListener('dragover', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      /* Зона обрабатывает свои переносы полностью и не отпускает их на
         слушателя по документу, который читал бы файл, который это модуль
         намеренно не читает. */
      e.stopPropagation();
      markOver(true);
    });
    drop.addEventListener('dragleave', (e) => {
      /* Зона обрабатывает все события перетаскивания, включая уход. */
      e.stopPropagation();
      /* Dragleave возникает на каждой границе дочерних узлов; проверяем, что
         указатель вышел из зоны целиком, а не прошёл между её детьми. */
      if (e.relatedTarget) {
        var at = e.relatedTarget;
        while (at) {
          if (at === drop) return;
          at = at.parentNode;
        }
      }
      markOver(false);
    });
    drop.addEventListener('drop', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      e.stopPropagation();
      markOver(false);
      accept(e.dataTransfer.files);
    });

    return { accept: accept };
  }

  return { create };
}));
