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
       узлов. Документный слой ниже по файлу устроен грубее и решает
       другую задачу — см. комментарий там. */
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

       В отличие от files.js эта тройка не подсвечивает зону и не зовёт
       accept: highlighting и разбор — дело зоны и только зоны (см. её
       обработчики выше), а мимо зоны прилетевший файл этот раздел не
       принимает и не обсуждает — как будто броска и не было, кроме одного
       эффекта: браузер по нему никуда не уходит. Тройка существует ради
       mine(): пока показан чужой раздел, за отмену браузерной навигации
       отвечает его собственный документный слушатель — у files.js такой
       уже есть, у cve.js теперь тоже, и на любом разделе всегда есть кто-то
       дежурный. */
    document.addEventListener('dragover', (e) => {
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
    });
    document.addEventListener('dragleave', (e) => {
      /* Подсвечивать нечему — на этом уровне подсветки нет. Слушатель
         заведён ради той же формы, что и у dragover/drop, чтобы следующий
         читатель видел одинаковую тройку в обоих модулях, а не гадал,
         почему тут одного обработчика не хватает. */
      if (!mine()) return;
    });
    document.addEventListener('drop', (e) => {
      /* Файл не читаем и не отдаём в accept: зона уже получила бы его сама,
         если бы попали в неё (её drop ниже вызывает stopPropagation и до
         сюда не долетает). Раз долетело — значит, бросили мимо зоны, и
         единственное, что нужно, — не дать браузеру уйти со страницы. */
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
    });

    return { accept: accept };
  }

  return { create };
}));
