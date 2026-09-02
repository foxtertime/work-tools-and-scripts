# Разделы страницы: островок слева, Builds и CVE — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поднять над вкладками страницы уровень разделов: висячий островок слева переключает Builds — всё нынешнее содержимое — и CVE, заглушку, которая принимает xlsx и говорит, что читать его ещё не умеет.

**Architecture:** Два новых самостоятельных модуля в общем стиле проекта (UMD + `create(deps)`): `screens.js` знает только, какой раздел показан, `cve.js` владеет зоной загрузки своего раздела. Содержимое `.wrap` заворачивается в `<section id="screen-builds">`, рядом встаёт `<section id="screen-cve" hidden>`. `ui.js` получает два вызова `create`, существующая машинерия вкладок не трогается.

**Tech Stack:** Ванильный ES6 без сборщика и зависимостей; UMD-обёртка `(function (root, factory) {...})`; тесты — `node --test` поверх `tests/js/domstub.js`, который строит дерево из настоящего `dashboard/assets/dashboard.html`; питоновская сборка страницы — `dashboard/build.py`, тесты `python3 -m unittest`.

**Spec:** `tools/dashboard/docs/superpowers/specs/2026-09-02-screens-isle-design.md`

## Global Constraints

- Все команды в плане запускаются из каталога тулзы: `tools/dashboard/`.
- Работа идёт в ветке `feature/dashboard-screens`, уже отведённой от `develop`.
- Язык интерфейса и комментариев в коде — русский; подписи двух кнопок островка — `Builds` и `CVE`, по-английски, это заказано.
- Никаких внешних зависимостей: страница открывается с диска, сети у неё нет.
- Новый файл в `assets/js/` обязан быть дописан в `SCRIPTS`, новый в `assets/css/` — в `STYLES` внутри `dashboard/build.py`; `tests/test_build.py` сверяет эти списки с содержимым каталогов и уронит сборку, если файл забыт.
- Порядок в `SCRIPTS` — по зависимостям: `ui.js` идёт последним и должен видеть оба новых модуля уже положенными в `KP`.
- Порядок в `STYLES` решает каскад: `isle.css` обязан стоять после `layout.css`, иначе общее правило `button` перебьёт `.isle-btn`.
- Версия тулзы поднимается один раз, в последней задаче, до `3.6.0`; `tests/test_version.py` требует, чтобы в `CHANGELOG.md` была запись ровно с этим номером, поэтому номер и запись едут одним коммитом.
- Полные наборы тестов: `python3 -m unittest discover -s tests` и `node --test tests/js/*.test.js`.

---

### Task 1: Разметка разделов, островок и его стили

Первая задача — разметка, потому что тесты обоих модулей строят дерево из настоящего `dashboard.html`: без новых `id` они не запустятся вовсе.

**Files:**
- Modify: `dashboard/assets/dashboard.html`
- Create: `dashboard/assets/css/isle.css`
- Modify: `dashboard/build.py:28-29` (кортеж `STYLES`)
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: ничего.
- Produces: узлы `#isle` с кнопками `[data-screen="builds"]` и `[data-screen="cve"]`, секции `#screen-builds` и `#screen-cve`, внутри второй — `#cve-drop`, `#cve-pick`, `#cve-file`, `#cve-input`. На эти имена опираются задачи 2, 3 и 4.

- [ ] **Step 1: Написать падающий тест на разметку**

В `tests/test_build.py` найдите класс с docstring `"""Разметка, на которую опирается ui.js, и обещания README."""` (около строки 95) и добавьте в него два метода:

```python
    def test_page_has_two_screens(self):
        # Разделы держатся на этих четырёх узлах: островок с кнопками и две
        # секции. Пропади любой — screens.js найдёт None и страница
        # перестанет переключаться молча.
        html = build_html("1.0.0")
        for needle in ('id="isle"',
                       'data-screen="builds"',
                       'data-screen="cve"',
                       'id="screen-builds"',
                       'id="screen-cve"'):
            self.assertIn(needle, html, needle)

    def test_cve_screen_is_hidden_and_asks_for_xlsx(self):
        # Заглушка приходит скрытой и принимает только xlsx: раздел
        # открывается на билдах, а поле выбора не должно предлагать
        # человеку файлы, которые всё равно будут отвергнуты.
        html = build_html("1.0.0")
        self.assertIn('id="screen-cve" hidden', html)
        self.assertIn('id="cve-input"', html)
        self.assertIn('accept=".xlsx"', html)
        for needle in ('id="cve-drop"', 'id="cve-pick"', 'id="cve-file"'):
            self.assertIn(needle, html, needle)
```

- [ ] **Step 2: Прогнать тест и убедиться, что он падает**

```bash
python3 -m unittest tests.test_build -v
```

Ожидается: `FAIL` на обоих новых методах — `'id="isle"' not found`.

- [ ] **Step 3: Завернуть содержимое в секции и добавить островок**

Три точечные замены в `dashboard/assets/dashboard.html`. Отступы существующих строк не трогайте: перевыравнивание превратило бы дифф задачи в переписывание файла.

**Замена 1.** Найдите две строки:

```html
<body>
<div class="wrap">
```

Замените их на:

```html
<body>
<!-- Островок разделов стоит до .wrap, потому что он не её часть: страница
     центрирована, а он висит у края окна. -->
<nav class="isle" id="isle" aria-label="Разделы">
  <button class="isle-btn" data-screen="builds" aria-current="page">Builds</button>
  <button class="isle-btn" data-screen="cve">CVE</button>
</nav>
<div class="wrap">
```

**Замена 2.** Найдите строку с заголовком:

```html
  <h1>dashboard <span class="ver">__DASHBOARD_VERSION__</span></h1>
```

Допишите под ней открытие секции — заголовок остаётся снаружи обеих секций, он про страницу, а не про раздел:

```html
  <h1>dashboard <span class="ver">__DASHBOARD_VERSION__</span></h1>
  <section id="screen-builds">
```

**Замена 3.** Найдите конец файла `.wrap` — закрывающий `</section>` вкладки «Изменения», за которым идёт `</div>`:

```html
    </table></div>
  </section>
</div>
```

Замените на:

```html
    </table></div>
  </section>
  </section>
  <section id="screen-cve" hidden>
    <div class="drop" id="cve-drop">
      <p class="dropmain">Перетащите таблицу CVE сюда</p>
      <p class="dropsub">или <button type="button" class="linkish" id="cve-pick">выберите файл</button>.
        Это xlsx. Разбирать его страница пока не умеет.</p>
      <!-- Имя принятого файла. Пусто и скрыто, пока файла не было: пустая
           строка на месте имени читалась бы как «файл принят, а имя
           потерялось». -->
      <p class="dropsub" id="cve-file" hidden></p>
    </div>
    <input type="file" id="cve-input" accept=".xlsx" hidden>
  </section>
</div>
```

Обратите внимание на две подряд идущие закрывающие строки `</section>`: первая закрывает вкладку «Изменения», вторая — новую секцию билдов.

- [ ] **Step 4: Написать `isle.css`**

Создайте `dashboard/assets/css/isle.css`:

```css
/* Островок разделов. Висит поверх страницы, как кнопка «наверх» и тосты:
   .wrap центрирована и шириной до 1400px, и любой вариант «в потоке»
   отобрал бы у таблицы ширину на всех окнах ради двух кнопок.

   Цена известна и принята: на узком окне островок закроет левый край
   первой колонки, и прокруткой его оттуда не убрать — таблица ездит вбок
   внутри .tablewrap, а островок привязан к окну. */
.isle { position: fixed; left: 1.25rem; top: 50%;
  transform: translateY(-50%); z-index: 90;
  display: flex; flex-direction: column; gap: .25rem;
  padding: .35rem; border: 1px solid var(--line); border-radius: 14px;
  background: var(--card); box-shadow: var(--lift); }

/* Радиус меньше кнопочного и подпись прижата влево: две кнопки внутри
   коробки должны читаться группой, а не двумя отдельными пилюлями. */
.isle-btn { border-radius: 10px; text-align: left; }

/* Активный раздел метится тем же приёмом, что нажатый переключатель в
   панели фильтров: цветом, а не заливкой. Селектор по наличию атрибута —
   у неактивной кнопки его нет вовсе. */
.isle-btn[aria-current] { border-color: var(--accent); color: var(--accent); }
```

- [ ] **Step 5: Дописать `isle.css` в `STYLES`**

В `dashboard/build.py` замените кортеж `STYLES` на:

```python
STYLES = ("base.css", "layout.css", "rail.css", "cards.css", "table.css",
          "filters.css", "isle.css", "toasts.css", "tip.css")
```

Место выбрано не наугад: после `layout.css`, иначе общее правило `button` перебило бы `.isle-btn`; и рядом с `toasts.css` и `tip.css` — это тоже чрома поверх страницы.

- [ ] **Step 6: Прогнать тесты и убедиться, что они проходят**

```bash
python3 -m unittest discover -s tests
node --test tests/js/*.test.js
```

Ожидается: питоновский набор `OK`; набор для Node — все тесты проходят. Заглушка DOM строит дерево из шаблона, и завёрнутые в секцию узлы обязаны находиться по-прежнему: `ui.test.js` — это и есть проверка, что разметка не разъехалась со скриптом.

- [ ] **Step 7: Коммит**

```bash
git add dashboard/assets/dashboard.html dashboard/assets/css/isle.css \
        dashboard/build.py tests/test_build.py
git commit -m "feat(dashboard): add section markup and the isle stylesheet

Wrap the page in a builds section, add a hidden CVE section with its own
drop zone, and put the fixed isle above both."
```

---

### Task 2: Модуль `screens.js`

**Files:**
- Create: `dashboard/assets/js/screens.js`
- Create: `tests/js/screens.test.js`
- Modify: `dashboard/build.py:20-24` (кортеж `SCRIPTS`)

**Interfaces:**
- Consumes: узлы `#isle`, `#screen-builds`, `#screen-cve` из задачи 1.
- Produces: `KP.screens.create({ isle, sections })` → `{ show(name), current() }`. `sections` — объект вида `{ builds: <node>, cve: <node> }`. `show` принимает строку, незнакомую приводит к `'builds'`. `current()` возвращает имя показанного раздела строкой. Этим пользуется задача 4.

- [ ] **Step 1: Написать падающий тест**

Создайте `tests/js/screens.test.js`:

```js
'use strict';
/* Разделы страницы на настоящей разметке: дерево строится из
   dashboard.html, поэтому пропавший в шаблоне id роняет тест, а не вид
   страницы. Ни данных, ни снапшотов сюда не завозим — модуль о них не
   знает. */
var test = require('node:test');
var assert = require('node:assert');
var domstub = require('./domstub.js');
var screensmod = require('../../dashboard/assets/js/screens.js');

function setup() {
  var dom = domstub.install();
  var screens = screensmod.create({
    isle: dom.id('isle'),
    sections: { builds: dom.id('screen-builds'), cve: dom.id('screen-cve') } });
  return { dom: dom, screens: screens,
           builds: dom.id('screen-builds'), cve: dom.id('screen-cve') };
}

/* Кнопку ищем по разделу, а не по порядку в островке: порядок кнопок —
   дело вида, и тест не должен падать от их перестановки. */
function button(dom, name) {
  var all = dom.id('isle').querySelectorAll('[data-screen]'), i;
  for (i = 0; i < all.length; i++) {
    if (all[i].getAttribute('data-screen') === name) return all[i];
  }
  throw new Error('в островке нет кнопки ' + name);
}

test('страница открывается на билдах', function () {
  var s = setup();
  assert.equal(s.screens.current(), 'builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});

test('клик по кнопке меняет раздел', function () {
  var s = setup();
  button(s.dom, 'cve').click();
  assert.equal(s.screens.current(), 'cve');
  assert.equal(s.builds.hidden, true);
  assert.equal(s.cve.hidden, false);
});

test('активная кнопка помечена, неактивная теряет отметку', function () {
  /* Атрибут снимается целиком, а не ставится в false: aria-current="false"
     читается вслух как признак, а не как его отсутствие. */
  var s = setup();
  assert.equal(button(s.dom, 'builds').getAttribute('aria-current'), 'page');
  assert.equal(button(s.dom, 'cve').getAttribute('aria-current'), null);
  button(s.dom, 'cve').click();
  assert.equal(button(s.dom, 'cve').getAttribute('aria-current'), 'page');
  assert.equal(button(s.dom, 'builds').getAttribute('aria-current'), null);
});

test('незнакомый раздел приводится к билдам, а не роняет страницу', function () {
  var s = setup();
  s.screens.show('cve');
  s.screens.show('нет такого');
  assert.equal(s.screens.current(), 'builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});

test('возврат в билды снова показывает раздел', function () {
  /* Пока билды скрыты, viewport.js меряет нулевую высоту панели и кладёт
     её в --controls-h — отступ липкой шапки таблицы. Значение
     восстанавливается на возврате; проверять это должен тест, а не
     следующий читатель. */
  var s = setup();
  s.screens.show('cve');
  s.screens.show('builds');
  assert.equal(s.builds.hidden, false);
  assert.equal(s.cve.hidden, true);
});
```

- [ ] **Step 2: Прогнать тест и убедиться, что он падает**

```bash
node --test tests/js/screens.test.js
```

Ожидается: `Cannot find module '../../dashboard/assets/js/screens.js'`.

- [ ] **Step 3: Написать модуль**

Создайте `dashboard/assets/js/screens.js`:

```js
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
```

- [ ] **Step 4: Прогнать тест и убедиться, что он проходит**

```bash
node --test tests/js/screens.test.js
```

Ожидается: пять тестов, `# fail 0`.

- [ ] **Step 5: Дописать `screens.js` в `SCRIPTS`**

В `dashboard/build.py` замените кортеж `SCRIPTS` на:

```python
SCRIPTS = ("vercmp.js", "rpms.js", "diff.js", "viewmodel.js", "store.js",
           "text.js", "query.js", "labels.js", "search.js", "page.js",
           "markup.js", "tables.js", "cards.js", "filters.js", "rail.js",
           "files.js", "tips.js", "toasts.js", "copy.js", "viewport.js",
           "notices.js", "screens.js", "ui.js")
```

`screens.js` встаёт перед `ui.js`, потому что тот его зовёт; своих зависимостей у модуля нет.

- [ ] **Step 6: Прогнать полные наборы**

```bash
python3 -m unittest discover -s tests
node --test tests/js/*.test.js
```

Ожидается: оба `OK` / `# fail 0`. Питоновский набор здесь важен: `test_build.py` сверяет `SCRIPTS` с содержимым каталога и поймал бы забытую строку.

- [ ] **Step 7: Коммит**

```bash
git add dashboard/assets/js/screens.js tests/js/screens.test.js dashboard/build.py
git commit -m "feat(dashboard): add the screens module behind the isle

One module, one fact: which section is shown. An unknown name falls back
to builds instead of leaving the page with nothing visible."
```

---

### Task 3: Модуль `cve.js` — заглушка раздела

**Files:**
- Create: `dashboard/assets/js/cve.js`
- Create: `tests/js/cve.test.js`
- Modify: `dashboard/build.py:20-24` (кортеж `SCRIPTS`)

**Interfaces:**
- Consumes: узлы `#cve-drop`, `#cve-input`, `#cve-pick`, `#cve-file` из задачи 1; `toasts.show({ kind, title, lines })`, где `kind` — `'error'` или `'warn'`, `title` — строка, `lines` — массив строк.
- Produces: `KP.cve.create({ dom: { drop, input, pick, name }, toasts })` → `{ accept(list) }`, где `list` — массив файлов с полем `name`. Этим пользуется задача 4.

- [ ] **Step 1: Написать падающий тест**

Создайте `tests/js/cve.test.js`:

```js
'use strict';
/* Заглушка раздела CVE: принимает таблицу и честно говорит, что читать её
   не умеет. Настоящая разметка нужна и здесь — зона, поле, кнопка и место
   под имя берутся из шаблона. */
var test = require('node:test');
var assert = require('node:assert');
var domstub = require('./domstub.js');
var cvemod = require('../../dashboard/assets/js/cve.js');

function setup() {
  var dom = domstub.install();
  var shown = [];
  var cve = cvemod.create({
    toasts: { show: function (spec) { shown.push(spec); } },
    dom: { drop: dom.id('cve-drop'), input: dom.id('cve-input'),
           pick: dom.id('cve-pick'), name: dom.id('cve-file') } });
  return { dom: dom, cve: cve, shown: shown,
           drop: dom.id('cve-drop'), name: dom.id('cve-file') };
}

/* Перенос в терминах браузера. Пока он идёт, сами файлы браузер прячет и
   о них говорит одна запись Files в types; на drop появляются и файлы. */
function dragging() { return { types: ['Files'], files: [] }; }
function dropping() {
  var names = Array.prototype.slice.call(arguments);
  return { types: ['Files'],
           files: names.map(function (n) { return { name: n }; }) };
}

function said(shown) {
  return shown.map(function (s) { return s.lines.join(' '); }).join(' ');
}

test('перетаскивание подсвечивает зону, уход гасит', function () {
  var s = setup();
  s.dom.fire(s.drop, 'dragover', { dataTransfer: dragging() });
  assert.equal(s.drop.className, 'drop over');
  s.dom.fire(s.drop, 'dragleave', {});
  assert.equal(s.drop.className, 'drop');
});

test('xlsx принят: имя показано и сказано, что он не прочитан', function () {
  var s = setup();
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('cve-2026.xlsx') });
  assert.equal(s.name.hidden, false);
  assert.equal(s.name.textContent, 'cve-2026.xlsx');
  assert.equal(s.shown.length, 1);
  assert.equal(s.shown[0].kind, 'warn');
  assert.ok(said(s.shown).indexOf('не прочитано') !== -1, said(s.shown));
});

test('чужое расширение отвергнуто, имя не показано', function () {
  var s = setup();
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('снапшот.json') });
  assert.equal(s.name.hidden, true);
  assert.equal(s.shown.length, 1);
  assert.equal(s.shown[0].kind, 'error');
});

test('из пачки берётся первый файл', function () {
  /* Раздел ждёт одну таблицу, а не набор. Молча съесть второй значило бы
     соврать про то, что принято. */
  var s = setup();
  s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('первый.xlsx', 'второй.xlsx') });
  assert.equal(s.name.textContent, 'первый.xlsx');
  assert.equal(s.shown.length, 1);
});

test('кнопка открывает диалог выбора', function () {
  var s = setup();
  var input = s.dom.id('cve-input');
  var opened = 0;
  input.click = function () { opened += 1; };
  s.dom.id('cve-pick').click();
  assert.equal(opened, 1);
});

test('содержимое файла не читается вовсе', function () {
  /* Заглушка не притворяется работающей: прочитать и промолчать было бы
     хуже, чем не читать и сказать. */
  var s = setup();
  var reads = 0;
  var Real = global.FileReader;
  global.FileReader = function () { reads += 1; return new Real(); };
  try {
    s.dom.fire(s.drop, 'drop', { dataTransfer: dropping('cve.xlsx') });
  } finally {
    global.FileReader = Real;
  }
  assert.equal(reads, 0);
});
```

- [ ] **Step 2: Прогнать тест и убедиться, что он падает**

```bash
node --test tests/js/cve.test.js
```

Ожидается: `Cannot find module '../../dashboard/assets/js/cve.js'`.

- [ ] **Step 3: Написать модуль**

Создайте `dashboard/assets/js/cve.js`:

```js
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
      markOver(true);
    });
    drop.addEventListener('dragleave', () => markOver(false));
    drop.addEventListener('drop', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      markOver(false);
      accept(e.dataTransfer.files);
    });

    return { accept: accept };
  }

  return { create };
}));
```

- [ ] **Step 4: Прогнать тест и убедиться, что он проходит**

```bash
node --test tests/js/cve.test.js
```

Ожидается: шесть тестов, `# fail 0`.

- [ ] **Step 5: Дописать `cve.js` в `SCRIPTS`**

В `dashboard/build.py` замените кортеж `SCRIPTS` на:

```python
SCRIPTS = ("vercmp.js", "rpms.js", "diff.js", "viewmodel.js", "store.js",
           "text.js", "query.js", "labels.js", "search.js", "page.js",
           "markup.js", "tables.js", "cards.js", "filters.js", "rail.js",
           "files.js", "tips.js", "toasts.js", "copy.js", "viewport.js",
           "notices.js", "screens.js", "cve.js", "ui.js")
```

- [ ] **Step 6: Прогнать полные наборы**

```bash
python3 -m unittest discover -s tests
node --test tests/js/*.test.js
```

Ожидается: оба чистые.

- [ ] **Step 7: Коммит**

```bash
git add dashboard/assets/js/cve.js tests/js/cve.test.js dashboard/build.py
git commit -m "feat(dashboard): add the CVE screen stub

It takes an xlsx, shows the name and says plainly that parsing is not
written yet. The file is never read: reading it and staying silent would
be worse than not reading it and saying so."
```

---

### Task 4: Проводка в `ui.js` и молчание `files.js` на чужом разделе

**Files:**
- Modify: `dashboard/assets/js/ui.js` (шапка UMD, строки 8-33; блок «владельцы участков страницы», около строк 413-425)
- Modify: `dashboard/assets/js/files.js` (создание модуля и документные обработчики)
- Test: `tests/js/ui.test.js`

**Interfaces:**
- Consumes: `KP.screens.create({ isle, sections })` из задачи 2, `KP.cve.create({ dom, toasts })` из задачи 3.
- Produces: `filesmod.create` начинает принимать `dom.screen` — узел секции, при скрытой которой модуль не отвечает на документные `dragover` и `drop`. Ничего наружу страницы не отдаёт.

- [ ] **Step 1: Написать падающие тесты**

В конец `tests/js/ui.test.js` добавьте:

```js
/* ---------- разделы ---------- */

function isleButton(dom, name) {
  var all = dom.id('isle').querySelectorAll('[data-screen]'), i;
  for (i = 0; i < all.length; i++) {
    if (all[i].getAttribute('data-screen') === name) return all[i];
  }
  throw new Error('в островке нет кнопки ' + name);
}

test('страница поднимается на разделе билдов', function () {
  var dom = load();
  assert.equal(dom.id('screen-builds').hidden, false);
  assert.equal(dom.id('screen-cve').hidden, true);
  /* Островок виден и на пустой странице: syncEmpty прячет вкладки и
     секции, но до него не дотягивается. У CVE свой источник данных, и
     требовать сначала подгрузить снапшоты билдов было бы бессмыслицей. */
  assert.equal(dom.id('isle').hidden, false);
});

test('островок переключает разделы и возвращает обратно', function () {
  var dom = load();
  isleButton(dom, 'cve').click();
  assert.equal(dom.id('screen-builds').hidden, true);
  assert.equal(dom.id('screen-cve').hidden, false);
  isleButton(dom, 'builds').click();
  assert.equal(dom.id('screen-builds').hidden, false);
  assert.equal(dom.id('screen-cve').hidden, true);
});

test('на разделе CVE брошенный файл не уезжает в разбор снапшотов', function () {
  /* files.js слушает бросок на всём документе — иначе браузер открыл бы
     файл вместо страницы. Пока показан чужой раздел, отвечать на это
     нельзя: xlsx получил бы отказ «не JSON», то есть сообщение про
     формат, которого человек не называл. */
  var dom = load();
  isleButton(dom, 'cve').click();
  dom.fire(dom.document, 'drop', {
    dataTransfer: { types: ['Files'],
                    files: [domstub.file('таблица.xlsx', 'не json')] } });
  return dom.tick().then(function () {
    assert.equal(noteText(dom), '');
  });
});

test('на разделе билдов бросок на страницу работает по-прежнему', function () {
  var dom = load();
  dom.fire(dom.document, 'drop', {
    dataTransfer: { types: ['Files'],
                    files: [domstub.file('a.json',
                      JSON.stringify(snap('os-9.1', '2026-07-01T00:00:00+03:00')))] } });
  return dom.tick().then(function () {
    assert.equal(store.list().length, 1);
  });
});

test('заглушка CVE принимает xlsx и говорит, что не прочитала', function () {
  var dom = load();
  isleButton(dom, 'cve').click();
  dom.fire(dom.id('cve-drop'), 'drop', {
    dataTransfer: { types: ['Files'], files: [{ name: 'таблица.xlsx' }] } });
  assert.equal(dom.id('cve-file').hidden, false);
  assert.equal(dom.id('cve-file').textContent, 'таблица.xlsx');
  assert.ok(noteText(dom).indexOf('не прочитано') !== -1, noteText(dom));
});
```

- [ ] **Step 2: Прогнать тесты и убедиться, что они падают**

```bash
node --test tests/js/ui.test.js
```

Ожидается: `FAIL` — `ui.js` пока не создаёт ни `screens`, ни `cve`, и файл на разделе CVE уезжает в разбор.

- [ ] **Step 3: Научить `files.js` молчать на чужом разделе**

В `dashboard/assets/js/files.js` в начале `create` добавьте узел секции к остальным:

```js
    const input = deps.dom.input, dropZone = deps.dom.drop;
    const pickBtn = deps.dom.pick, screen = deps.dom.screen;
```

Рядом с `hasFiles` добавьте:

```js
    /* Пока раздел билдов скрыт, документные события не наши: брошенный
       файл там ждут другие руки, а разбор его как снапшота дал бы отказ
       про формат, которого человек не называл.

       Спрашиваем секцию, а не видимость самой зоны: #tab-empty скрывается,
       как только снапшоты подгружены, и проверка по зоне отняла бы
       работающий сегодня бросок на страницу с таблицей. */
    function mine() { return !screen || !screen.hidden; }
```

И поставьте эту проверку первой в трёх документных обработчиках:

```js
    document.addEventListener('dragover', (e) => {
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
      markOver(true);
    });
    document.addEventListener('dragleave', (e) => {
      if (!mine()) return;
      if (!e.relatedTarget) markOver(false);
    });
    document.addEventListener('drop', (e) => {
      if (!mine() || !hasFiles(e)) return;
      e.preventDefault();
      markOver(false);
      loadFiles(e.dataTransfer.files);
    });
```

Кнопка и поле выбора проверки не получают: они живут внутри своей секции и на чужом разделе до них не дотянуться.

- [ ] **Step 4: Подключить оба модуля в `ui.js`**

В UMD-шапке `dashboard/assets/js/ui.js` добавьте два модуля. В ветке `module.exports`:

```js
    module.exports = factory(require('./viewmodel.js'), require('./store.js'),
                             require('./diff.js'), require('./text.js'),
                             require('./labels.js'), require('./markup.js'),
                             require('./tables.js'), require('./cards.js'),
                             require('./page.js'), require('./rail.js'),
                             require('./files.js'), require('./tips.js'),
                             require('./toasts.js'), require('./filters.js'),
                             require('./search.js'), require('./copy.js'),
                             require('./viewport.js'), require('./notices.js'),
                             require('./query.js'), require('./screens.js'),
                             require('./cve.js'));
```

В ветке браузера:

```js
    root.KP.ui = factory(root.KP.viewmodel, root.KP.store, root.KP.diff,
                         root.KP.text, root.KP.labels, root.KP.markup,
                         root.KP.tables, root.KP.cards, root.KP.page,
                         root.KP.rail, root.KP.files, root.KP.tips,
                         root.KP.toasts, root.KP.filters, root.KP.search,
                         root.KP.copy, root.KP.viewport, root.KP.notices,
                         root.KP.query, root.KP.screens, root.KP.cve);
```

И в списке доводов фабрики:

```js
  function (viewmodel, store, diffmod, text, labels, markup, tables, cards,
            pagemod, railmod, filesmod, tipsmod, toastsmod, filtersmod,
            searchmod, copymod, viewportmod, noticesmod, querymod,
            screensmod, cvemod) {
```

В блоке «владельцы участков страницы» — там, где создаются `tips`, `toasts`, `rail`, `files` — замените создание `files` и добавьте два вызова следом:

```js
  let files = filesmod.create({ store: store, toasts: toasts,
    dom: { input: fileInput, drop: dropZone, pick: pickBtn,
           screen: document.getElementById('screen-builds') } });
  /* Разделы и заглушка CVE держат свои узлы сами; здесь про них известно
     только то, чем их зовут. Ссылку не храним: звать их отсюда неоткуда —
     островок слушает себя сам. */
  screensmod.create({
    isle: document.getElementById('isle'),
    sections: { builds: document.getElementById('screen-builds'),
                cve: document.getElementById('screen-cve') } });
  cvemod.create({ toasts: toasts,
    dom: { drop: document.getElementById('cve-drop'),
           input: document.getElementById('cve-input'),
           pick: document.getElementById('cve-pick'),
           name: document.getElementById('cve-file') } });
```

- [ ] **Step 5: Прогнать тесты и убедиться, что они проходят**

```bash
node --test tests/js/ui.test.js
node --test tests/js/*.test.js
python3 -m unittest discover -s tests
```

Ожидается: всё чистое. Если упал `files.test.js` или старые тесты броска в `ui.test.js` — значит `mine()` отняла работающий сегодня бросок; проверьте, что в `create` передан `screen`, и что это секция, а не зона.

- [ ] **Step 6: Коммит**

```bash
git add dashboard/assets/js/ui.js dashboard/assets/js/files.js tests/js/ui.test.js
git commit -m "feat(dashboard): wire the isle into the page

The root creates the two screen modules, and the snapshot loader stops
answering page-wide drops while its own section is hidden: an xlsx
dropped on the CVE screen would otherwise be refused as bad JSON."
```

---

### Task 5: Документация и версия

**Files:**
- Modify: `dashboard/__init__.py:8`
- Modify: `CHANGELOG.md` (тулзы)
- Modify: `README.md` (тулзы)
- Modify: `../../CHANGELOG.md` (корневой, секция `[Unreleased]`)
- Test: `tests/test_version.py` (существующий, менять не нужно)

**Interfaces:**
- Consumes: всё сделанное в задачах 1-4.
- Produces: версию `3.6.0`.

- [ ] **Step 1: Убедиться, что тест версии сейчас падать не должен**

```bash
python3 -m unittest tests.test_version -v
```

Ожидается: `OK` — версия `3.5.1` и запись о ней в `CHANGELOG.md` пока на месте. Это отправная точка: следующим шагом номер поднимется, и тест покраснеет, пока не появится запись.

- [ ] **Step 2: Поднять номер**

В `dashboard/__init__.py` замените:

```python
__version__ = "3.6.0"
```

- [ ] **Step 3: Прогнать тест и убедиться, что он падает**

```bash
python3 -m unittest tests.test_version -v
```

Ожидается: `FAIL` в `test_changelog_names_the_current_version` — `'## 3.6.0 ' not found`.

- [ ] **Step 4: Написать запись в `CHANGELOG.md` тулзы**

Вставьте новую запись сразу над `## 3.5.1 — 2026-08-12`:

```markdown
## 3.6.0 — 2026-09-02

**У страницы появились разделы, и переключает их островок слева.** Всё, что
страница показывала до сих пор, стало разделом **Builds**; рядом встал
**CVE**, куда приедет таблица уязвимостей в xlsx. Разделы — уровень выше
вкладок: «Состояние» и «Изменения» переключают срез одних и тех же
снапшотов, а раздел меняет предмет разговора, и у CVE своих снапшотов нет
вовсе.

Островок висит у левого края окна и не уезжает при прокрутке. На узком окне
он закроет левый край первой колонки таблицы — это плата за то, что на
широком он стоит в полях и не отбирает у таблицы ширину.

**Раздел CVE пока заглушка.** Он принимает файл — броском на зону или
кнопкой, — показывает его имя и прямо говорит, что разбор xlsx ещё не
написан и содержимое не прочитано. Файл действительно не читается: молча
принять и ничего не сделать было бы хуже.

Выбранный раздел не переживает перезагрузку — как и всё остальное на этой
странице: снапшоты в неё подгружают заново каждый раз.

Бросок файла на страницу мимо зоны теперь слушается только на своём
разделе. Раньше он ловился на всём документе всегда; на разделе CVE это
значило бы, что таблица xlsx получает отказ «не JSON» — сообщение про
формат, которого никто не называл.
```

- [ ] **Step 5: Прогнать тест и убедиться, что он проходит**

```bash
python3 -m unittest tests.test_version -v
```

Ожидается: `OK`.

- [ ] **Step 6: Поправить README тулзы**

Четыре правки.

Первая — в разделе `## Дашборд`, сразу после заголовка и до `### Как в него попадают снапшоты`, вставьте:

```markdown
### Разделы

Страница разбита на два раздела, и переключает их островок у левого края
окна. **Builds** — всё, что описано ниже: снапшоты, вкладки, таблицы,
фильтры и поиск. **CVE** — место под таблицу уязвимостей в xlsx; сейчас там
заглушка, которая файл принимает, имя его показывает и честно говорит, что
разбирать его ещё не умеет.

Разделы стоят уровнем выше вкладок и значат другое: вкладка меняет срез
одних и тех же снапшотов, раздел — предмет разговора. Выбранный раздел не
сохраняется: страница открывается на Builds.
```

Вторая — в `### Как в него попадают снапшоты` замените скобку в первом абзаце:

```markdown
(ронять можно на всё окно, не только на зону, пока открыт раздел Builds)
```

Третья — в `### Стили` замените «Восемь файлов» на «Девять файлов» и добавьте строку в таблицу, между `filters.css` и `toasts.css`:

```markdown
| `isle.css` | островок разделов у левого края окна |
```

Четвёртая — в `### Скрипты`, в таблицу «Владельцы участков DOM», добавьте две строки в конец:

```markdown
| `screens.js` | какой раздел страницы показан; островок слева |
| `cve.js` | заглушка раздела CVE: приём файла xlsx |
```

Число в фразе «Двадцать четыре файла в `assets/js/`» трогать не нужно: файлов было двадцать два при написанных двадцати четырёх, и с этими двумя фраза наконец стала верной.

- [ ] **Step 7: Дописать строку в корневой `CHANGELOG.md`**

В `../../CHANGELOG.md` (корень репозитория) в секцию `## [Unreleased]` добавьте подраздел `### Добавлено`, если его там нет, и строку:

```markdown
- `dashboard` (3.6.0): у страницы появились разделы — островок слева
  переключает Builds, всё нынешнее содержимое, и CVE, пока заглушку под
  таблицу уязвимостей в xlsx.
```

- [ ] **Step 8: Прогнать всё**

```bash
python3 -m unittest discover -s tests
node --test tests/js/*.test.js
```

Ожидается: `OK` и `# fail 0`.

- [ ] **Step 9: Собрать страницу и посмотреть на неё глазами**

```bash
python3 -m dashboard page -o /tmp/dashboard.html
```

Проверьте в браузере: островок висит слева, `Builds` помечен, клик по `CVE` показывает зону под xlsx, клик обратно возвращает таблицу. Страница открывается прямо с диска — сети ей не нужно.

- [ ] **Step 10: Коммит**

```bash
git add dashboard/__init__.py CHANGELOG.md README.md ../../CHANGELOG.md
git commit -m "docs(dashboard): release 3.6.0 with the section isle

Bump the tool version, write the changelog entry, and document the two
sections in the README."
```

---

## Что проверить в конце

- [ ] `python3 -m unittest discover -s tests` — зелёный.
- [ ] `node --test tests/js/*.test.js` — `# fail 0`.
- [ ] `python3 -m dashboard --version` печатает `dashboard 3.6.0`.
- [ ] Собранная страница открывается с диска и переключает разделы.
- [ ] Из корня репозитория: `git ls-files -s tools | grep -v '^100755' | cut -f2` — ни один новый файл не несёт шебанг без исполняемого бита.
