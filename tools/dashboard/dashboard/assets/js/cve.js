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
    const screen = deps.dom.screen;

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

    /* Пока раздел CVE скрыт, документные события не наши: бросок на билдах
       ждут другие руки, а принять его здесь значило бы читать имя файла,
       который человек не целился в эту зону. Слово в слово как mine() в
       files.js — там же сказано, почему проверяем именно секцию, а не
       видимость зоны. */
    function mine() { return !screen || !screen.hidden; }

    pick.addEventListener('click', () => input.click());

    input.addEventListener('change', () => {
      accept(input.files);
      /* Тот же файл, выбранный второй раз, не даёт события, пока в поле
         лежит его прежнее значение. */
      input.value = '';
    });

    /* Зона отвечает за точность: свой containment walk на dragleave ниже
       нужен только ей, чтобы подсветка не мигала на границах дочерних
       узлов. Документный слой ниже подхватывает то, что мимо зоны, но не
       подсвечивает — подсветка была бы обещанием попадания в зону, а его
       здесь нет. */
    drop.addEventListener('dragover', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      /* Не даём событию подняться до документа: там его тоже отменили бы,
         но без подсветки, а подсветка — дело зоны. */
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
      /* stopPropagation здесь — единственное, что мешает документному
         обработчику ниже принять тот же файл второй раз: бросок в зону
         обязан быть обработан один раз, а не дважды. */
      e.stopPropagation();
      markOver(false);
      accept(e.dataTransfer.files);
    });

    /* Ронять файл можно на весь раздел CVE, а не только на зону: .wrap
       центрирован и ограничен по ширине, и поля по бокам, заголовок и всё
       ниже зоны — по-прежнему часть страницы, на которую браузер по
       умолчанию откроет брошенный файл вместо неё. Без preventDefault
       здесь окно бы уехало на xlsx (или на снапшот — с этого раздела не
       видно, что несли), а дашборд — со всеми снапшотами, которые живут
       только в памяти страницы, — исчез бы.

       Долетевший сюда файл (зона не перехватила — её stopPropagation
       остановил бы его раньше) не выбрасывается молча: раздел CVE обязан
       сам сказать, что он думает про этот файл, точно так же, как сказал
       бы, попади он прямо в зону. Отвечать отменой без единого слова —
       худший вариант именно для этого раздела: он и так уже честно
       заявляет о себе через toasts при каждом принятом или отклонённом
       файле, и бросок мимо дашборд-бокса на 30 пикселей не повод внезапно
       промолчать. Симметрично files.js: там файл, брошенный где угодно на
       билдах, тоже уезжает в разбор, а не теряется просто потому, что
       мимо зоны. */
    document.addEventListener('dragover', (e) => {
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
    });
    document.addEventListener('drop', (e) => {
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
      accept(e.dataTransfer.files);
    });

    return { accept: accept };
  }

  return { create };
}));
