# cvesummary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** новая тулза `tools/cvesummary/`: xlsx таблицы процесса устранения
CVE → одна HTML-страница сводки вида `Сводка по CVE.html`.

**Architecture:** Python (только stdlib) читает первый лист xlsx своим
разбором (`zipfile` + `ElementTree`), находит шапку и колонки по именам,
нормализует строки и вшивает их JSON-ом в страницу. Всё остальное — роли
статусов, часы, темп, прогноз, графики — считает JS страницы. Чистые
JS-модули (`dates`, `roles`, `hours`, `pace`, `timeline`) тестируются в
`node --test`, отрисовка (`render.js`) проверяется в браузере.

**Tech Stack:** Python 3.9+ (`unittest`), ванильный JS (ES2018, без
сборки), `node --test` (Node 18+), playwright для ручной проверки.

**Spec:** `tools/cvesummary/docs/superpowers/specs/2026-10-19-cvesummary-design.md`

## Global Constraints

- Python 3.9+, только стандартная библиотека; синтаксис проверяется
  `ast.parse(..., feature_version=(3, 9))`. Никаких `match`, `X | Y` в
  аннотациях, `str.removeprefix` можно (3.9).
- Без `openpyxl` и любых внешних пакетов; конфига нет.
- Запуск: `python3 -m cvesummary ТАБЛИЦА.xlsx [-o СВОДКА.html] [--as-of ГГГГ-ММ-ДД]`, `--version`.
- Коды возврата: `0` — страница записана; `2` — вход не читается, нет шапки или обязательных колонок, неверная дата в `--as-of`.
- Обязательные колонки: `CVE ID`, `Компонент`, `RHEL state`, `RHEL severity`. `Task state` не читается и нигде не используется.
- Роли — только по `Статус`, без учёта регистра и крайних пробелов: «Готов» — закрыта; «Ожидает ревью» — на ревью; «На паузе» — на паузе; «Есть проблема», «Нужна доработка» — требует внимания; разработчик есть и не «Готов» — в работе; разработчика нет и не «Готов» — не взята.
- Часы: 8 ч в рабочий день разработчика делятся поровну между висящими на нём задачами; интервал `Start date`…`End date` включительно (без `End` — до даты отчёта, конец обрезается датой отчёта); выходной рабочий, если в этот день у разработчика `Start date` или `End date` задачи.
- Прогноз — в задачах, не в часах.
- Графики по времени — весь период, мин. ширина дня 10 px, недели 28 px; горизонтальная прокрутка внутри графика без видимой полосы, стартовая позиция — конец.
- Шрифты — Google Fonts, как в образце; CSS и JS встроены в страницу.
- Документы на русском, коммиты — Conventional Commits на английском, скоуп `cvesummary`, футер `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Работа в ветке `feature/cvesummary` (уже создана, в ней спека).
- Все пути ниже — от `tools/cvesummary/`, если не сказано иное; команды запускаются из этого каталога.

## Review Focus

1. `-o` указывает на сам входной xlsx (или вход назван `x.html` и вывод по умолчанию совпадает с ним) — тулза отказывается с кодом 2 и таблицу не трогает. Тест — Task 7.
2. Имя колонки в шапке с переносом строки или двойным пробелом (`SL NVR⏎(latest build)`, `RHEL  state`) — та же колонка. Тест — Task 2.
3. Колонки процесса пусты у всех строк (так выглядит реальная выгрузка из `task.md`) — страница собирается, часов нет, прогноз «не завершится», никаких `NaN`. Тесты — Task 4 (`hours`), Task 5 (`pace`), Task 7 (CLI на таблице только из обязательных колонок).
4. Дата Excel со временем (`46314.75`) и дата текстом с временем (`2026-10-01T00:00:00`) — берётся только день. Тесты — Task 1, Task 2.
5. Один и тот же человек с хвостовым пробелом (`«Иванов »` и `«Иванов»`) — один разработчик, один общий 8-часовой день. Тест — Task 4.

---

## File Structure

```text
tools/cvesummary/
├── README.md  TODO.md  CHANGELOG.md          # Task 9
├── setup.cfg  pyproject.toml                  # Task 1
├── cvesummary/
│   ├── __init__.py    # __version__ = "1.0.0"               Task 1
│   ├── __main__.py    # python3 -m cvesummary               Task 1
│   ├── xlsx.py        # zip → первый лист → строки Cell     Task 1
│   ├── table.py       # шапка, колонки, нормализация         Task 2
│   ├── page.py        # шаблон + css + js + JSON → HTML      Task 6
│   ├── cli.py         # argparse, журнал, запись            Task 7
│   └── assets/
│       ├── summary.html   # разметка с маркерами             Task 6
│       ├── summary.css    # стили образца + графики          Task 6
│       └── js/
│           ├── dates.js     # дни как целые числа            Task 3
│           ├── roles.js     # роли, меры, критичность        Task 3
│           ├── hours.js     # модель часов                   Task 4
│           ├── pace.js      # темп и прогноз                 Task 5
│           ├── timeline.js  # ширина и прокрутка графиков    Task 5
│           └── render.js    # DOM                            Task 6 (каркас), Task 8
└── tests/
    ├── __init__.py
    ├── xlsxmake.py      # сборка xlsx для тестов и примера   Task 1
    ├── example.py       # пример на 100 строк                Task 8
    ├── test_version.py  test_xlsx.py  test_table.py  test_page.py  test_cli.py  test_example.py
    └── js/
        ├── dates.test.js  roles.test.js  hours.test.js  pace.test.js  timeline.test.js
```

Каждый JS-модуль — UMD-обёртка, как в `dashboard`: в node — `module.exports`,
в браузере — `globalThis.CS.<имя>`. `page.py` склеивает модули в порядке
`dates, roles, hours, pace, timeline, render`.

---

### Task 1: каркас пакета и чтение xlsx

**Files:**
- Create: `cvesummary/__init__.py`, `cvesummary/__main__.py`, `cvesummary/xlsx.py`, `setup.cfg`, `pyproject.toml`
- Create: `tests/__init__.py`, `tests/xlsxmake.py`, `tests/test_version.py`, `tests/test_xlsx.py`

**Interfaces:**
- Produces: `xlsx.read(path: str) -> Sheet`; `Sheet(name: str, rows: List[Row], date1904: bool)`; `Row(number: int, cells: List[Cell])`; `Cell(text: str, number: Optional[float] = None, date: Optional[datetime.date] = None)`; `xlsx.serial_date(number: float, date1904: bool = False) -> datetime.date` (ValueError вне диапазона); `xlsx.is_date_format(code: str) -> bool`; `xlsx.XlsxError` (сообщение без пути к файлу — путь добавляет CLI).
- Produces (tests): `tests.xlsxmake.make(rows, **options) -> bytes`, `write(path, rows, **options)`, `replace(path, name, text)`, обёртки `Num(value, style=0)`, `Rich(runs)`, `Formula(text)`, `Bool(value)`, `Error(text)`.

- [ ] **Step 1: каркас**

`cvesummary/__init__.py`:

```python
"""Сводка по CVE: xlsx таблицы процесса → одна HTML-страница."""
__version__ = "1.0.0"
```

`cvesummary/__main__.py`:

```python
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

`pyproject.toml`:

```toml
# Только объявление сборщика. Метаданные лежат в setup.cfg: setuptools
# читает [project] из pyproject лишь с 61-й версии, а в RHEL 9 стоит 53-я.
[build-system]
requires = ["setuptools>=40.8"]
build-backend = "setuptools.build_meta"
```

`setup.cfg`:

```ini
[metadata]
name = cvesummary
# Номер версии написан в одном месте — cvesummary/__init__.py.
version = attr: cvesummary.__version__
description = Сводка по CVE: xlsx таблицы процесса в одну HTML-страницу

[options]
packages = cvesummary
python_requires = >=3.9
include_package_data = True

[options.package_data]
# Шаблон, стили и скрипты — часть пакета: без них страницу не собрать.
cvesummary =
    assets/*.html
    assets/*.css
    assets/js/*.js

[options.entry_points]
console_scripts =
    cvesummary = cvesummary.cli:main
```

`tests/__init__.py` — пустой файл.

`tests/test_version.py`:

```python
import re
import unittest

from cvesummary import __version__


class VersionTest(unittest.TestCase):
    def test_semver(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
```

- [ ] **Step 2: генератор xlsx для тестов**

`tests/xlsxmake.py`:

```python
"""xlsx для тестов и примера: ровно те части книги, что читает cvesummary.

Ячейка в строке: str — строка (общая или inline), int/float — число,
Num(value, style) — число со стилем (индекс в cellXfs), Rich — общая строка
из нескольких кусков, Formula — результат формулы (t="str"), Bool, Error,
None — ячейки нет, её адрес пропущен. Строка None — пропущенный номер
строки. Content_Types и _rels/.rels пишутся, чтобы книгу открывали Excel и
LibreOffice; читателю они не нужны.
"""
import io
import zipfile
from typing import NamedTuple, Sequence
from xml.sax.saxutils import escape, quoteattr

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"


class Num(NamedTuple):
    value: float
    style: int = 0


class Rich(NamedTuple):
    runs: Sequence[str]


class Formula(NamedTuple):
    text: str


class Bool(NamedTuple):
    value: bool


class Error(NamedTuple):
    text: str


def column(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def _t(text):
    return '<t xml:space="preserve">%s</t>' % escape(text)


def _cell(ref, value, strings, shared):
    if isinstance(value, Rich):
        strings.append("".join("<r>%s</r>" % _t(run) for run in value.runs))
        return '<c r="%s" t="s"><v>%d</v></c>' % (ref, len(strings) - 1)
    if isinstance(value, str):
        if shared:
            strings.append(_t(value))
            return '<c r="%s" t="s"><v>%d</v></c>' % (ref, len(strings) - 1)
        return '<c r="%s" t="inlineStr"><is>%s</is></c>' % (ref, _t(value))
    if isinstance(value, Formula):
        return '<c r="%s" t="str"><f>X</f><v>%s</v></c>' % (ref, escape(value.text))
    if isinstance(value, Bool):
        return '<c r="%s" t="b"><v>%d</v></c>' % (ref, int(value.value))
    if isinstance(value, Error):
        return '<c r="%s" t="e"><v>%s</v></c>' % (ref, escape(value.text))
    if isinstance(value, Num):
        return '<c r="%s" s="%d"><v>%r</v></c>' % (ref, value.style, value.value)
    return '<c r="%s"><v>%r</v></c>' % (ref, value)


def _sheet(rows, strings, shared):
    out = ['<worksheet xmlns="%s"><sheetData>' % MAIN]
    for number, row in enumerate(rows, 1):
        if row is None:
            continue
        cells = [_cell("%s%d" % (column(i), number), value, strings, shared)
                 for i, value in enumerate(row) if value is not None]
        out.append('<row r="%d">%s</row>' % (number, "".join(cells)))
    out.append("</sheetData></worksheet>")
    return "".join(out)


def make(rows, *, sheet="Лист1", shared=True, xfs=(0,), numfmts=None, date1904=False,
         second=None, absolute=False, swap=False) -> bytes:
    """Книга одним буфером.

    xfs — numFmtId для каждого стиля cellXfs; numfmts — {id: formatCode};
    second — строки второго листа «Второй»; absolute — Target в rels от
    корня пакета (/xl/…); swap — первый лист лежит в sheet2.xml, второй — в
    sheet1.xml: порядок листов задаёт <sheets>, а не имена файлов.
    """
    strings = []
    first_xml = _sheet(rows, strings, shared)
    second_xml = _sheet(second, strings, shared) if second is not None else None
    names = ("sheet2.xml", "sheet1.xml") if swap else ("sheet1.xml", "sheet2.xml")
    prefix = "/xl/worksheets/" if absolute else "worksheets/"
    sheets = ['<sheet name=%s sheetId="1" r:id="rId1"/>' % quoteattr(sheet)]
    rels = ['<Relationship Id="rId1" Type="%s/worksheet" Target="%s%s"/>'
            % (REL, prefix, names[0])]
    parts = [names[0]]
    if second_xml is not None:
        sheets.append('<sheet name="Второй" sheetId="2" r:id="rId2"/>')
        rels.append('<Relationship Id="rId2" Type="%s/worksheet" Target="%s%s"/>'
                    % (REL, prefix, names[1]))
        parts.append(names[1])
    pr = '<workbookPr date1904="1"/>' if date1904 else ""
    fmts = ""
    if numfmts:
        fmts = '<numFmts count="%d">%s</numFmts>' % (len(numfmts), "".join(
            '<numFmt numFmtId="%d" formatCode=%s/>' % (k, quoteattr(v))
            for k, v in numfmts.items()))
    styles = '<styleSheet xmlns="%s">%s<cellXfs count="%d">%s</cellXfs></styleSheet>' % (
        MAIN, fmts, len(xfs), "".join('<xf numFmtId="%d"/>' % x for x in xfs))
    types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             + ('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                if strings else "")
             + "".join('<Override PartName="/xl/worksheets/%s" ContentType="%s"/>' % (p, _SHEET_TYPE)
                       for p in parts)
             + "</Types>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" '
                   'Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>'
                   % (PKG, REL))
        z.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s">%s<sheets>%s</sheets>'
                   '</workbook>' % (MAIN, REL, pr, "".join(sheets)))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s">%s'
                   '<Relationship Id="rIdS" Type="%s/styles" Target="styles.xml"/>'
                   '</Relationships>' % (PKG, "".join(rels), REL))
        z.writestr("xl/styles.xml", styles)
        if strings:
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="%s">%s</sst>'
                       % (MAIN, "".join("<si>%s</si>" % s for s in strings)))
        z.writestr("xl/worksheets/" + names[0], first_xml)
        if second_xml is not None:
            z.writestr("xl/worksheets/" + names[1], second_xml)
    return buffer.getvalue()


def write(path, rows, **options):
    with open(path, "wb") as handle:
        handle.write(make(rows, **options))


def replace(path, name, text):
    """Подменить (или убрать при text=None) часть уже записанной книги."""
    with zipfile.ZipFile(path) as z:
        members = {info.filename: z.read(info) for info in z.infolist()}
    if text is None:
        members.pop(name, None)
    else:
        members[name] = text.encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        for member, data in members.items():
            z.writestr(member, data)
```

- [ ] **Step 3: падающие тесты чтения**

`tests/test_xlsx.py`:

```python
import datetime
import os
import tempfile
import unittest

from cvesummary import xlsx
from tests.xlsxmake import Bool, Error, Formula, Num, Rich, replace, write

DAY = datetime.date(2026, 10, 19)
SERIAL = 46314            # DAY в системе 1900
SERIAL_1904 = 46314 - 1462


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def book(self, rows, **options):
        path = os.path.join(self.dir.name, "t.xlsx")
        write(path, rows, **options)
        return path

    def texts(self, path):
        return [[cell.text for cell in row.cells] for row in xlsx.read(path).rows]


class CellsTest(Base):
    def test_shared_and_inline_strings(self):
        for shared in (True, False):
            with self.subTest(shared=shared):
                self.assertEqual(self.texts(self.book([["a", "б"]], shared=shared)), [["a", "б"]])

    def test_rich_text_is_joined(self):
        self.assertEqual(self.texts(self.book([[Rich(["CVE-", "2026"])]])), [["CVE-2026"]])

    def test_formula_bool_error(self):
        row = [Formula("x"), Bool(True), Bool(False), Error("#N/A")]
        self.assertEqual(self.texts(self.book([row])), [["x", "TRUE", "FALSE", "#N/A"]])

    def test_numbers(self):
        cells = xlsx.read(self.book([[5, 7.5, Num(46000.0)]])).rows[0].cells
        self.assertEqual([c.text for c in cells], ["5", "7.5", "46000"])
        self.assertEqual(cells[1].number, 7.5)
        self.assertIsNone(cells[0].date)

    def test_missing_cells_are_empty(self):
        self.assertEqual(self.texts(self.book([["a", None, "c"]])), [["a", "", "c"]])

    def test_row_numbers_follow_the_sheet(self):
        sheet = xlsx.read(self.book([["a"], None, ["c"]]))
        self.assertEqual([row.number for row in sheet.rows], [1, 3])


class DatesTest(Base):
    def cell(self, value, **options):
        return xlsx.read(self.book([[value]], **options)).rows[0].cells[0]

    def test_builtin_date_style(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 14))
        self.assertEqual((cell.date, cell.text), (DAY, "19.10.2026"))

    def test_custom_date_format(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 164), numfmts={164: "dd.mm.yyyy"})
        self.assertEqual(cell.date, DAY)

    def test_time_is_dropped(self):
        self.assertEqual(self.cell(Num(SERIAL + 0.75, 1), xfs=(0, 22)).date, DAY)

    def test_date1904(self):
        self.assertEqual(self.cell(Num(SERIAL_1904, 1), xfs=(0, 14), date1904=True).date, DAY)

    def test_number_format_is_not_a_date(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 164), numfmts={164: '0" дней"'})
        self.assertEqual((cell.date, cell.text), (None, "46314"))

    def test_date_out_of_range_stays_a_number(self):
        cell = self.cell(Num(1e10, 1), xfs=(0, 14))
        self.assertEqual((cell.date, cell.text), (None, "10000000000"))

    def test_is_date_format(self):
        for code in ("dd.mm.yyyy", "yyyy-mm-dd", "d mmm", "DD/MM/YY", "[$-419]d mmmm yyyy"):
            self.assertTrue(xlsx.is_date_format(code), code)
        for code in ("0.00", '0" дней"', "[Red]#,##0", "General", "\\d0", "0_)"):
            self.assertFalse(xlsx.is_date_format(code), code)

    def test_serial_date(self):
        self.assertEqual(xlsx.serial_date(SERIAL), DAY)
        self.assertEqual(xlsx.serial_date(SERIAL_1904, True), DAY)
        with self.assertRaises(ValueError):
            xlsx.serial_date(1e10)


class SheetTest(Base):
    def test_first_sheet_by_workbook_order(self):
        sheet = xlsx.read(self.book([["first"]], second=[["second"]], swap=True))
        self.assertEqual(sheet.name, "Лист1")
        self.assertEqual([[c.text for c in r.cells] for r in sheet.rows], [["first"]])

    def test_absolute_target(self):
        self.assertEqual(self.texts(self.book([["a"]], absolute=True)), [["a"]])


class ErrorsTest(Base):
    def assertFails(self, path, fragment):
        with self.assertRaises(xlsx.XlsxError) as caught:
            xlsx.read(path)
        self.assertIn(fragment, str(caught.exception))

    def test_not_a_zip(self):
        path = os.path.join(self.dir.name, "t.xlsx")
        with open(path, "wb") as handle:
            handle.write(b"not a zip")
        self.assertFails(path, "zip")

    def test_missing_file(self):
        self.assertFails(os.path.join(self.dir.name, "none.xlsx"), "не открывается")

    def test_no_workbook(self):
        path = self.book([["a"]])
        replace(path, "xl/workbook.xml", None)
        self.assertFails(path, "xl/workbook.xml")

    def test_no_sheets(self):
        path = self.book([["a"]])
        replace(path, "xl/workbook.xml", '<workbook xmlns="%s"><sheets/></workbook>'
                % "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
        self.assertFails(path, "нет листов")

    def test_broken_xml(self):
        path = self.book([["a"]])
        replace(path, "xl/worksheets/sheet1.xml", "<worksheet")
        self.assertFails(path, "XML")
```

- [ ] **Step 4: убедиться, что тесты падают**

Run: `python3 -m unittest discover -s tests -v`
Expected: `ImportError`/`ModuleNotFoundError` на `cvesummary.xlsx` (и на `cvesummary.cli` нет — `__main__` не импортируется); `test_version` проходит.

- [ ] **Step 5: реализация `cvesummary/xlsx.py`**

```python
"""Первый лист xlsx: своим разбором, без openpyxl — в RHEL 9 его нет.

Читаются только книга (порядок листов), связи листа, общие строки и стили
— последние ради одного: отличить дату от числа. Ошибки — XlsxError без
пути к файлу; путь добавляет вызывающий.
"""
import datetime
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, NamedTuple, Optional

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# встроенные форматы дат и времени, ECMA-376 часть 1, 18.8.30
_DATE_IDS = frozenset(range(14, 23)) | {45, 46, 47}
# в коде формата не считаются: текст в кавычках, [цвет]/[$-локаль],
# экранированный символ и пробел/заполнитель под символ (_x, *x)
_NOT_CODE = re.compile(r'"[^"]*"|\[[^\]]*\]|\\.|[_*].')
_REF = re.compile(r"([A-Z]+)(\d+)$")
# Отсчёт системы 1900 — 30.12.1899: так серийные номера после 28.02.1900
# сходятся с Excel, который считает несуществующее 29.02.1900.
_EPOCH_1900 = datetime.date(1899, 12, 30)
_EPOCH_1904 = datetime.date(1904, 1, 1)


class XlsxError(Exception):
    """Файл не читается как xlsx."""


class Cell(NamedTuple):
    text: str                             # как показать
    number: Optional[float] = None        # число, если ячейка числовая
    date: Optional[datetime.date] = None  # дата, если число со стилем даты


class Row(NamedTuple):
    number: int        # номер строки листа, с 1
    cells: List[Cell]  # с колонки A; пропущенные ячейки — Cell("")


class Sheet(NamedTuple):
    name: str
    rows: List[Row]
    date1904: bool


def read(path: str) -> Sheet:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise XlsxError("не xlsx (не zip-архив): %s" % exc)
    except OSError as exc:
        raise XlsxError("не открывается: %s" % exc)
    with archive:
        try:
            return _read(archive)
        except KeyError as exc:
            raise XlsxError("в книге нет части: %s" % exc)
        except ET.ParseError as exc:
            raise XlsxError("битый XML: %s" % exc)
        except zipfile.BadZipFile as exc:
            raise XlsxError("битый архив: %s" % exc)


def serial_date(number: float, date1904: bool = False) -> datetime.date:
    """Серийный номер Excel → дата; время (дробная часть) отбрасывается."""
    epoch = _EPOCH_1904 if date1904 else _EPOCH_1900
    try:
        return epoch + datetime.timedelta(days=int(number))
    except (OverflowError, ValueError) as exc:
        raise ValueError("дата вне диапазона: %r (%s)" % (number, exc))


def is_date_format(code: str) -> bool:
    """Код формата числа — дата: d, m или y вне кавычек, […] и экранирования."""
    bare = _NOT_CODE.sub("", code).lower()
    return any(ch in bare for ch in "dmy")


def _read(archive) -> Sheet:
    book = _xml(archive, "xl/workbook.xml")
    pr = book.find(MAIN + "workbookPr")
    date1904 = pr is not None and pr.get("date1904") in ("1", "true")
    sheet = book.find(MAIN + "sheets/" + MAIN + "sheet")
    if sheet is None:
        raise XlsxError("в книге нет листов")
    target = _target(archive, sheet.get(REL + "id"))
    rows = _rows(_xml(archive, target), _shared(archive), _date_styles(archive), date1904)
    return Sheet(sheet.get("name", ""), rows, date1904)


def _xml(archive, name):
    with archive.open(name) as handle:
        return ET.parse(handle).getroot()


def _target(archive, rid) -> str:
    for rel in _xml(archive, "xl/_rels/workbook.xml.rels").iter(PKG + "Relationship"):
        if rel.get("Id") == rid:
            target = rel.get("Target", "")
            if target.startswith("/"):
                return target[1:]
            return posixpath.normpath(posixpath.join("xl", target))
    raise XlsxError("связь листа %s не найдена в xl/_rels/workbook.xml.rels" % rid)


def _shared(archive) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    return [_text(si) for si in _xml(archive, "xl/sharedStrings.xml").iter(MAIN + "si")]


def _text(node) -> str:
    """Текст <si>/<is>: простой <t> или куски <r><t>; фонетика <rPh> не в счёт."""
    parts = []
    for child in node:
        if child.tag == MAIN + "t":
            parts.append(child.text or "")
        elif child.tag == MAIN + "r":
            t = child.find(MAIN + "t")
            if t is not None:
                parts.append(t.text or "")
    return "".join(parts)


def _date_styles(archive) -> List[bool]:
    """Для каждого стиля cellXfs по порядку: дата ли это."""
    if "xl/styles.xml" not in archive.namelist():
        return []
    root = _xml(archive, "xl/styles.xml")
    custom = {}
    fmts = root.find(MAIN + "numFmts")
    if fmts is not None:
        for fmt in fmts.iter(MAIN + "numFmt"):
            custom[int(fmt.get("numFmtId", "0"))] = fmt.get("formatCode", "")
    xfs = root.find(MAIN + "cellXfs")
    if xfs is None:
        return []
    result = []
    for xf in xfs.iter(MAIN + "xf"):
        fid = int(xf.get("numFmtId", "0"))
        code = custom.get(fid)
        result.append(is_date_format(code) if code is not None else fid in _DATE_IDS)
    return result


def _column(ref: str) -> int:
    match = _REF.match(ref)
    if not match:
        raise XlsxError("неверный адрес ячейки %r" % ref)
    index = 0
    for ch in match.group(1):
        index = index * 26 + ord(ch) - 64
    return index - 1


def _rows(root, shared, date_styles, date1904) -> List[Row]:
    data = root.find(MAIN + "sheetData")
    if data is None:
        return []
    rows, last = [], 0
    for row in data.iter(MAIN + "row"):
        last = int(row.get("r") or last + 1)
        cells, nxt = [], 0
        for c in row.iter(MAIN + "c"):
            ref = c.get("r")
            index = _column(ref) if ref else nxt
            nxt = index + 1
            if index >= len(cells):
                cells.extend([Cell("")] * (index + 1 - len(cells)))
            cells[index] = _cell(c, shared, date_styles, date1904)
        rows.append(Row(last, cells))
    return rows


def _cell(c, shared, date_styles, date1904) -> Cell:
    kind = c.get("t", "n")
    value = c.find(MAIN + "v")
    raw = value.text if value is not None and value.text is not None else ""
    if kind == "s":
        if raw == "":
            return Cell("")
        try:
            return Cell(shared[int(raw)])
        except (ValueError, IndexError):
            raise XlsxError("ячейка %s: нет общей строки %r" % (c.get("r"), raw))
    if kind == "inlineStr":
        node = c.find(MAIN + "is")
        return Cell(_text(node) if node is not None else "")
    if kind in ("str", "e", "d"):
        return Cell(raw)
    if kind == "b":
        return Cell("TRUE" if raw == "1" else "FALSE")
    if raw == "":
        return Cell("")
    try:
        number = float(raw)
    except ValueError:
        raise XlsxError("ячейка %s: не число %r" % (c.get("r"), raw))
    style = int(c.get("s", "0"))
    if style < len(date_styles) and date_styles[style]:
        try:
            day = serial_date(number, date1904)
        except ValueError:
            pass  # «дата» вне календаря — показываем как число
        else:
            return Cell(day.strftime("%d.%m.%Y"), number, day)
    return Cell(_number_text(number), number)


def _number_text(number: float) -> str:
    """7.5 → «7.5», 46000.0 → «46000»: Excel хранит целые с точкой не всегда."""
    if number.is_integer():
        return str(int(number))
    return repr(number)
```

- [ ] **Step 6: тесты проходят**

Run: `python3 -m unittest discover -s tests -v`
Expected: все тесты `test_xlsx` и `test_version` — OK.

Run: `python3 -c "import ast,pathlib;[ast.parse(p.read_text(),feature_version=(3,9)) for p in pathlib.Path('.').rglob('*.py')]"`
Expected: без вывода.

- [ ] **Step 7: commit**

```bash
git add tools/cvesummary/cvesummary tools/cvesummary/tests tools/cvesummary/setup.cfg tools/cvesummary/pyproject.toml
git commit -m "feat(cvesummary): read the first sheet of an xlsx without openpyxl

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: шапка, колонки, нормализация строк

**Files:**
- Create: `cvesummary/table.py`, `tests/test_table.py`

**Interfaces:**
- Consumes: `xlsx.Sheet`, `xlsx.Row`, `xlsx.Cell`, `xlsx.serial_date`.
- Produces: `table.build(sheet: Sheet) -> Table`; `Table(header_row: int, rows: List[dict], skipped: int, missing: List[str], duplicates: List[str], bad_dates: int)`; `table.FIELDS` — кортеж `(ключ, имя колонки)`; `table.TableError`; `table.parse_date(cell: Cell, date1904: bool = False) -> Optional[datetime.date]`. Строка данных — dict с ключами `row`, все ключи `FIELDS`, `bad` (список ключей дат, не разобранных). Значения — строки; даты — ISO `ГГГГ-ММ-ДД`; «нет значения» — `""`.

- [ ] **Step 1: падающие тесты**

`tests/test_table.py`:

```python
import datetime
import unittest

from cvesummary import table
from cvesummary.xlsx import Cell, Row, Sheet

HEADER = ["Разработчик", "Статус", "Start date", "End date", "Принятая мера", "Task ID",
          "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент", "P", "D",
          "SL NVR (latest build)", "RHEL NVR (if fixed)", "Fix date", "RHEL state",
          "RHEL severity", "RHEL CVSS", "Advisory (RHSA)", "CVE link", "Комментарий"]
ROW = ["Иванов И.И.", "Готов", "01.10.2026", "03.10.2026", "Патч из апстрима", "TASKID-1",
       "CVE-2026-1", "Выполнена", "28.09.2026", "КМ", "openssl", "+", "-",
       "openssl-3.2.2-6.sl9", "-", "-", "Affected", "Important", "7.5", "-",
       "https://access.redhat.com/security/cve/CVE-2026-1", "-"]
EXPECTED = {"row": 2, "dev": "Иванов И.И.", "status": "Готов", "start": "2026-10-01",
            "end": "2026-10-03", "measure": "Патч из апстрима", "task": "TASKID-1",
            "cve": "CVE-2026-1", "tdate": "2026-09-28", "exec": "КМ", "comp": "openssl",
            "p": "+", "d": "", "slnvr": "openssl-3.2.2-6.sl9", "rhnvr": "", "fixdate": "",
            "rstate": "Affected", "sev": "Important", "cvss": "7.5", "rhsa": "",
            "link": "https://access.redhat.com/security/cve/CVE-2026-1", "comment": "",
            "bad": []}
REQUIRED = ["CVE ID", "Компонент", "RHEL state", "RHEL severity"]


def sheet(*rows, date1904=False):
    """Лист из строк: ячейка — str или готовая Cell; номера строк с 1."""
    return Sheet("Лист1", [Row(n, [c if isinstance(c, Cell) else Cell(c) for c in row])
                           for n, row in enumerate(rows, 1)], date1904)


def one(*rows, **options):
    return table.build(sheet(*rows, **options)).rows[0]


class HeaderTest(unittest.TestCase):
    def test_full_row(self):
        self.assertEqual(one(HEADER, ROW), EXPECTED)

    def test_task_state_is_not_read(self):
        self.assertNotIn("Выполнена", one(HEADER, ROW).values())

    def test_group_row_above_header(self):
        result = table.build(sheet(["AG21", "", "SberLinux", "RedHat"], HEADER, ROW))
        self.assertEqual(result.header_row, 2)
        self.assertEqual(result.rows[0]["row"], 3)

    def test_columns_by_name_any_order_extra_ignored(self):
        got = one(["Заметки"] + HEADER[::-1], ["x"] + ROW[::-1])
        self.assertEqual(got, EXPECTED)

    def test_header_names_ignore_case_and_whitespace(self):
        header = [" cve id ", "КОМПОНЕНТ", "RHEL  state", "rhel\nseverity", "SL NVR\n(latest build)"]
        got = one(header, ["CVE-1", "bash", "Affected", "Low", "bash-5.1-1.sl9"])
        self.assertEqual((got["cve"], got["rstate"], got["sev"], got["slnvr"]),
                         ("CVE-1", "Affected", "Low", "bash-5.1-1.sl9"))

    def test_missing_required(self):
        with self.assertRaises(table.TableError) as caught:
            table.build(sheet(["CVE ID", "RHEL severity"], ["CVE-1", "Low"]))
        self.assertIn("Компонент, RHEL state", str(caught.exception))

    def test_no_header(self):
        with self.assertRaises(table.TableError) as caught:
            table.build(sheet(["a", "b"], ["c", "d"]))
        self.assertIn("CVE ID", str(caught.exception))

    def test_optional_missing_are_reported_and_empty(self):
        result = table.build(sheet(REQUIRED, ["CVE-1", "bash", "Affected", "Low"]))
        self.assertEqual(len(result.missing), len(table.FIELDS) - 4)
        self.assertIn("Разработчик", result.missing)
        self.assertEqual(result.rows[0]["dev"], "")

    def test_duplicate_column_first_wins(self):
        result = table.build(sheet(REQUIRED + ["Компонент"], ["CVE-1", "bash", "Affected", "Low", "zsh"]))
        self.assertEqual(result.rows[0]["comp"], "bash")
        self.assertEqual(result.duplicates, ["Компонент"])


class ValuesTest(unittest.TestCase):
    def test_dash_and_emdash_are_empty(self):
        got = one(REQUIRED + ["Разработчик", "Статус", "Комментарий"],
                  ["CVE-1", "bash", "Affected", "Low", "-", "—", "   "])
        self.assertEqual((got["dev"], got["status"], got["comment"]), ("", "", ""))

    def test_values_are_stripped(self):
        self.assertEqual(one(REQUIRED, [" CVE-1 ", "bash", "Affected", "Low"])["cve"], "CVE-1")

    def test_rows_without_cve_are_skipped_and_counted(self):
        result = table.build(sheet(REQUIRED, ["", "bash", "Affected", "Low"], ["", "", "", ""],
                                   ["CVE-2", "zsh", "Fixed", "Low"]))
        self.assertEqual(([r["cve"] for r in result.rows], result.skipped), (["CVE-2"], 1))

    def test_short_row_is_padded(self):
        self.assertEqual(one(REQUIRED + ["Комментарий"], ["CVE-1", "bash"])["sev"], "")


class DatesTest(unittest.TestCase):
    HEAD = REQUIRED + ["Start date"]

    def start(self, cell, **options):
        return one(self.HEAD, ["CVE-1", "bash", "Affected", "Low", cell], **options)

    def test_formats(self):
        cases = {"01.10.2026": "2026-10-01", "1.2.2026": "2026-02-01",
                 "2026-10-01": "2026-10-01", "2026-10-01T00:00:00": "2026-10-01",
                 "46314": "2026-10-19"}
        for text, iso in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.start(text)["start"], iso)

    def test_date_cells_and_numbers(self):
        day = datetime.date(2026, 10, 19)
        self.assertEqual(self.start(Cell("19.10.2026", 46314.0, day))["start"], "2026-10-19")
        self.assertEqual(self.start(Cell("46314", 46314.0))["start"], "2026-10-19")
        self.assertEqual(self.start(Cell("44852", 44852.0), date1904=True)["start"], "2026-10-19")

    def test_bad_date_stays_text_and_is_counted(self):
        for text in ("31.02.2026", "завтра"):
            with self.subTest(text=text):
                result = table.build(sheet(self.HEAD, ["CVE-1", "bash", "Affected", "Low", text]))
                self.assertEqual(result.rows[0]["start"], text)
                self.assertEqual(result.rows[0]["bad"], ["start"])
                self.assertEqual(result.bad_dates, 1)

    def test_parse_date(self):
        self.assertEqual(table.parse_date(Cell("05.10.2026")), datetime.date(2026, 10, 5))
        self.assertIsNone(table.parse_date(Cell("-")))
```

- [ ] **Step 2: тесты падают**

Run: `python3 -m unittest tests.test_table -v`
Expected: `ModuleNotFoundError: No module named 'cvesummary.table'`.

- [ ] **Step 3: реализация `cvesummary/table.py`**

```python
"""Строки таблицы процесса из листа: шапка, колонки по именам, нормализация.

Шапка — первая строка, где есть «CVE ID»; строки выше (группировка)
пропускаются. Колонки ищутся по имени без учёта регистра, с пробелами и
переносами, схлопнутыми в один пробел. Значения — строки без крайних
пробелов, «-» и «—» — пусто. Даты — ISO; нераспознанная остаётся текстом
и попадает в bad. Task state не читается.
"""
import datetime
import re
from typing import List, NamedTuple, Optional

from .xlsx import Cell, Sheet, serial_date

# ключ в данных страницы → имя колонки vulnsheet 2.0 (без Task state)
FIELDS = (
    ("dev", "Разработчик"), ("status", "Статус"), ("start", "Start date"),
    ("end", "End date"), ("measure", "Принятая мера"), ("task", "Task ID"),
    ("cve", "CVE ID"), ("tdate", "Task date"), ("exec", "Исполнитель"),
    ("comp", "Компонент"), ("p", "P"), ("d", "D"),
    ("slnvr", "SL NVR (latest build)"), ("rhnvr", "RHEL NVR (if fixed)"),
    ("fixdate", "Fix date"), ("rstate", "RHEL state"), ("sev", "RHEL severity"),
    ("cvss", "RHEL CVSS"), ("rhsa", "Advisory (RHSA)"), ("link", "CVE link"),
    ("comment", "Комментарий"),
)
REQUIRED = ("cve", "comp", "rstate", "sev")
DATES = ("tdate", "start", "end", "fixdate")
HEADER_KEY = "CVE ID"
_NAMES = dict(FIELDS)
_EMPTY = ("-", "—")
_DMY = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
_SERIAL = re.compile(r"\d+(?:\.\d+)?$")


class TableError(Exception):
    """Лист — не таблица процесса."""


class Table(NamedTuple):
    header_row: int
    rows: List[dict]
    skipped: int           # строк с данными, но без CVE ID
    missing: List[str]     # необязательные колонки, которых нет
    duplicates: List[str]  # колонки, чьё имя повторилось (взята первая)
    bad_dates: int         # ячеек дат, которые не разобрались


def build(sheet: Sheet) -> Table:
    header = next((row for row in sheet.rows
                   if any(_key(c.text) == _key(HEADER_KEY) for c in row.cells)), None)
    if header is None:
        raise TableError("нет шапки: ни в одной строке листа «%s» нет ячейки «%s»"
                         % (sheet.name, HEADER_KEY))
    known = {_key(name) for _, name in FIELDS}
    index, duplicates = {}, []
    for i, cell in enumerate(header.cells):
        name = _key(cell.text)
        if not name:
            continue
        if name in index:
            if name in known:
                duplicates.append(" ".join(cell.text.split()))
            continue
        index[name] = i
    columns = {key: index.get(_key(name)) for key, name in FIELDS}
    lacking = [_NAMES[key] for key in REQUIRED if columns[key] is None]
    if lacking:
        raise TableError("нет обязательных колонок: %s" % ", ".join(lacking))
    missing = [name for key, name in FIELDS if columns[key] is None]

    rows, skipped, bad = [], 0, 0
    for row in sheet.rows:
        if row.number <= header.number or not any(c.text.strip() for c in row.cells):
            continue
        cells = {key: _at(row.cells, columns[key]) for key, _ in FIELDS}
        record = {"row": row.number}
        record.update((key, _value(cell)) for key, cell in cells.items())
        if not record["cve"]:
            skipped += 1
            continue
        record["bad"] = []
        for key in DATES:
            if not record[key]:
                continue
            day = parse_date(cells[key], sheet.date1904)
            if day is None:
                record["bad"].append(key)
                bad += 1
            else:
                record[key] = day.isoformat()
        rows.append(record)
    return Table(header.number, rows, skipped, missing, duplicates, bad)


def parse_date(cell: Cell, date1904: bool = False) -> Optional[datetime.date]:
    """Дата из ячейки: дата Excel, дд.мм.гггг, гггг-мм-дд[…], серийный номер."""
    if cell.date is not None:
        return cell.date
    text = cell.text.strip()
    try:
        match = _DMY.match(text)
        if match:
            return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        match = _ISO.match(text)
        if match:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if cell.number is not None:
            return serial_date(cell.number, date1904)
        if _SERIAL.match(text):
            return serial_date(float(text), date1904)
    except ValueError:
        return None
    return None


def _key(text: str) -> str:
    return " ".join(text.split()).lower()


def _at(cells: List[Cell], index: Optional[int]) -> Cell:
    if index is None or index >= len(cells):
        return Cell("")
    return cells[index]


def _value(cell: Cell) -> str:
    text = cell.text.strip()
    return "" if text in _EMPTY else text
```

- [ ] **Step 4: тесты проходят**

Run: `python3 -m unittest discover -s tests -v`
Expected: OK.

- [ ] **Step 5: commit**

```bash
git add tools/cvesummary/cvesummary/table.py tools/cvesummary/tests/test_table.py
git commit -m "feat(cvesummary): find the header and read columns by name

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: JS — дни и роли

**Files:**
- Create: `cvesummary/assets/js/dates.js`, `cvesummary/assets/js/roles.js`
- Test: `tests/js/dates.test.js`, `tests/js/roles.test.js`

**Interfaces:**
- Produces `CS.dates`: `dayOf(iso) -> number|null` (сутки от 1970-01-01 UTC), `isoOf(day) -> 'ГГГГ-ММ-ДД'`, `ruOf(day) -> 'ДД.ММ.ГГГГ'`, `weekday(day) -> 0..6` (0 — пн), `isWeekend(day)`, `mondayOf(day)`.
- Produces `CS.roles`: `norm(s)`, `devOf(r) -> string` (имя с крайними пробелами срезанными и внутренними схлопнутыми), `isTaken`, `isDone`, `isOpen`, `isWorking`, `isReview`, `isPaused`, `needsAttention` (все `(row) -> boolean`), `closeReasons(row) -> Array<'fixed'|'patch'|'range'>`, `sevOf(row) -> string`, `sevOrder(values) -> string[]`, `measureOf(row) -> string`, `measureOrder(values) -> string[]`, константы `SEVERITIES`, `MEASURES`, `NO_SEVERITY = 'Нет оценки'`, `NO_MEASURE = 'не указана'`.

- [ ] **Step 1: падающие тесты**

`tests/js/dates.test.js`:

```js
'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');

var MON = 20731; // 2026-10-05, понедельник

test('ISO ↔ номер дня', function () {
  assert.strictEqual(dates.dayOf('1970-01-01'), 0);
  assert.strictEqual(dates.dayOf('2026-10-05'), MON);
  assert.strictEqual(dates.isoOf(MON), '2026-10-05');
  assert.strictEqual(dates.ruOf(MON), '05.10.2026');
});

test('не ISO — null', function () {
  assert.strictEqual(dates.dayOf(''), null);
  assert.strictEqual(dates.dayOf(undefined), null);
  assert.strictEqual(dates.dayOf('05.10.2026'), null);
});

test('день недели и понедельник', function () {
  assert.strictEqual(dates.weekday(MON), 0);
  assert.strictEqual(dates.weekday(MON + 5), 5);
  assert.strictEqual(dates.isWeekend(MON + 4), false);
  assert.strictEqual(dates.isWeekend(MON + 5), true);
  assert.strictEqual(dates.isWeekend(MON + 6), true);
  assert.strictEqual(dates.mondayOf(MON + 6), MON);
  assert.strictEqual(dates.mondayOf(MON), MON);
});
```

`tests/js/roles.test.js`:

```js
'use strict';
var test = require('node:test');
var assert = require('node:assert');
var roles = require('../../cvesummary/assets/js/roles.js');

function row(dev, status, extra) {
  return Object.assign({ dev: dev, status: status, sev: '', measure: '', rstate: '', p: '', d: '' }, extra || {});
}

test('«Готов» — закрыта, без учёта регистра и пробелов', function () {
  ['Готов', ' готов ', 'ГОТОВ'].forEach(function (s) {
    assert.strictEqual(roles.isDone(row('X', s)), true, s);
    assert.strictEqual(roles.isOpen(row('X', s)), false, s);
  });
});

test('статус вне набора — в работе, «Готово» не закрывает', function () {
  var r = row('X', 'Готово');
  assert.strictEqual(roles.isDone(r), false);
  assert.strictEqual(roles.isWorking(r), true);
});

test('без разработчика: не взята, но «Готов» всё равно закрыта', function () {
  assert.strictEqual(roles.isTaken(row(' ', '')), false);
  assert.strictEqual(roles.isWorking(row('', '')), false);
  var done = row('', 'Готов');
  assert.strictEqual(roles.isDone(done), true);
  assert.strictEqual(roles.isTaken(done), false);
});

test('ревью, пауза, внимание — открытые', function () {
  assert.strictEqual(roles.isReview(row('X', 'Ожидает ревью')), true);
  assert.strictEqual(roles.isOpen(row('X', 'Ожидает ревью')), true);
  assert.strictEqual(roles.isPaused(row('X', 'на паузе')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'Есть проблема')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'Нужна  доработка')), true);
  assert.strictEqual(roles.needsAttention(row('X', 'В работе')), false);
});

test('devOf срезает и схлопывает пробелы', function () {
  assert.strictEqual(roles.devOf(row(' Иванов  И.И. ', '')), 'Иванов И.И.');
});

test('критичность: канон, незнакомое как есть, пусто — «Нет оценки»', function () {
  assert.strictEqual(roles.sevOf(row('', '', { sev: 'important' })), 'Important');
  assert.strictEqual(roles.sevOf(row('', '', { sev: 'Severe' })), 'Severe');
  assert.strictEqual(roles.sevOf(row('', '', { sev: '' })), roles.NO_SEVERITY);
  assert.deepStrictEqual(roles.sevOrder(['Low', 'X', 'Нет оценки', 'Critical', 'A', 'Low']),
    ['Critical', 'Low', 'A', 'X', 'Нет оценки']);
});

test('меры: подпись из списка, незнакомое как есть, порядок task.md', function () {
  assert.strictEqual(roles.measureOf(row('', '', { measure: 'патч из апстрима ' })), 'Патч из апстрима');
  assert.strictEqual(roles.measureOf(row('', '', { measure: 'Своё' })), 'Своё');
  assert.strictEqual(roles.measureOf(row('', '', { measure: '' })), roles.NO_MEASURE);
  assert.deepStrictEqual(roles.measureOrder(['Другое', 'Своё', 'не указана', 'Патч из апстрима']),
    ['Патч из апстрима', 'Другое', 'Своё', 'не указана']);
  assert.strictEqual(roles.MEASURES.length, 11);
});

test('основания закрыть — только у открытых', function () {
  var r = row('X', 'В работе', { rstate: 'fixed', p: '+', d: '+' });
  assert.deepStrictEqual(roles.closeReasons(r), ['fixed', 'patch', 'range']);
  assert.deepStrictEqual(roles.closeReasons(row('X', 'Готов', { rstate: 'Fixed' })), []);
  assert.deepStrictEqual(roles.closeReasons(row('X', '', { p: '-', d: '' })), []);
});
```

- [ ] **Step 2: тесты падают**

Run: `node --test tests/js/`
Expected: `Cannot find module '../../cvesummary/assets/js/dates.js'`.

- [ ] **Step 3: `cvesummary/assets/js/dates.js`**

```js
/* Дни как целые числа — сутки от 1970-01-01 по UTC. Дни складываются,
   сравниваются и не зависят от часового пояса браузера; в строку их
   переводят только для показа. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.dates = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DAY_MS = 864e5;

  function dayOf(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? Date.UTC(+m[1], m[2] - 1, +m[3]) / DAY_MS : null;
  }
  function isoOf(day) { return new Date(day * DAY_MS).toISOString().slice(0, 10); }
  function ruOf(day) { const s = isoOf(day); return `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}`; }
  function weekday(day) { return (new Date(day * DAY_MS).getUTCDay() + 6) % 7; }
  function isWeekend(day) { return weekday(day) >= 5; }
  function mondayOf(day) { return day - weekday(day); }

  return { dayOf, isoOf, ruOf, weekday, isWeekend, mondayOf };
}));
```

- [ ] **Step 4: `cvesummary/assets/js/roles.js`**

```js
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
```

- [ ] **Step 5: тесты проходят**

Run: `node --test tests/js/`
Expected: все `pass`, `fail 0`.

- [ ] **Step 6: commit**

```bash
git add tools/cvesummary/cvesummary/assets/js/dates.js tools/cvesummary/cvesummary/assets/js/roles.js tools/cvesummary/tests/js
git commit -m "feat(cvesummary): add day arithmetic and status roles for the page

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: JS — модель часов

**Files:**
- Create: `cvesummary/assets/js/hours.js`
- Test: `tests/js/hours.test.js`

**Interfaces:**
- Consumes: `CS.dates.dayOf`, `CS.dates.isWeekend`; `CS.roles.isTaken`, `isDone`, `devOf`.
- Produces `CS.hours`:
  - `HOURS_PER_DAY = 8`;
  - `REASONS` — `{ 'no-start': 'нет Start date', 'end-before-start': 'End date раньше Start date', 'done-no-end': '«Готов» без End date', 'bad-date': 'Start date или End date не разобрана' }`;
  - `compute(rows, asOf) -> { hours: Array<number|null>, anomalies: Array<{index, reason}>, workdays: Map<dev, Set<day>>, load: Map<dev, Map<day, N>> }` — `hours[i]` `null`, если задача не взята или аномалия; `0`, если старт позже даты отчёта;
  - `summary(values) -> { n, mean, median }` (пусто — `{ n: 0, mean: null, median: null }`);
  - `rate(closedDays, workdays, from, to) -> number|null` — закрыто за рабочий день разработчика в `[from, to]`.

- [ ] **Step 1: падающие тесты**

`tests/js/hours.test.js`:

```js
'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var hours = require('../../cvesummary/assets/js/hours.js');

var MON = 20731; // 2026-10-05
var iso = function (day) { return day === null ? '' : dates.isoOf(day); };
function t(dev, start, end, status, bad) {
  return { dev: dev, start: iso(start), end: iso(end), status: status || 'В работе', bad: bad || [] };
}
var H = function (rows, asOf) { return hours.compute(rows, asOf).hours; };

test('одна задача пн–ср — 24 ч', function () {
  assert.deepStrictEqual(H([t('X', MON, MON + 2, 'Готов')], MON + 10), [24]);
});

test('две параллельно — по 4 ч в день', function () {
  assert.deepStrictEqual(H([t('X', MON, MON), t('X', MON, MON)], MON), [4, 4]);
});

test('выходной без старта и закрытия не считается', function () {
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 7, 'Готов')], MON + 10), [16]);
});

test('выходной со стартом — рабочий', function () {
  // A пт–пн; B взята в вс, открыта. сб не рабочий, вс и пн делятся на двоих
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 7, 'Готов'), t('X', MON + 6, null)], MON + 7), [16, 8]);
});

test('выходной с закрытием — рабочий', function () {
  assert.deepStrictEqual(H([t('X', MON + 4, MON + 5, 'Готов')], MON + 10), [16]);
});

test('старт и закрытие в один день — 8 ч', function () {
  assert.deepStrictEqual(H([t('X', MON, MON, 'Готов')], MON + 10), [8]);
});

test('открытая — до даты отчёта; конец обрезается датой отчёта', function () {
  assert.deepStrictEqual(H([t('X', MON, null)], MON + 2), [24]);
  assert.deepStrictEqual(H([t('X', MON, MON + 10)], MON + 1), [16]);
});

test('старт после даты отчёта — 0 ч, не аномалия', function () {
  var got = hours.compute([t('X', MON + 5, null)], MON);
  assert.deepStrictEqual(got.hours, [0]);
  assert.deepStrictEqual(got.anomalies, []);
});

test('пример из спеки: 16, 32, 8', function () {
  var rows = [t('X', MON, MON + 2, 'Готов'), t('X', MON + 1, MON + 7, 'Готов'), t('X', MON + 4, MON + 5, 'Готов')];
  assert.deepStrictEqual(H(rows, MON + 14), [16, 32, 8]);
});

test('пример пользователя: первая задача — 12 ч', function () {
  var rows = [t('X', MON, MON + 2, 'Готов'), t('X', MON + 1, null), t('X', MON + 1, null), t('X', MON + 1, null)];
  assert.strictEqual(H(rows, MON + 2)[0], 12);
});

test('разные разработчики не делят день; пробелы в имени — тот же человек', function () {
  assert.deepStrictEqual(H([t('X', MON, MON), t('Y', MON, MON)], MON), [8, 8]);
  assert.deepStrictEqual(H([t('Иванов ', MON, MON), t('Иванов', MON, MON)], MON), [4, 4]);
});

test('аномалии и не взятые', function () {
  var rows = [
    t('X', MON + 2, MON),               // End раньше Start
    t('X', MON, null, 'Готов'),         // «Готов» без End
    t('X', null, null),                 // нет Start
    t('X', MON, MON, 'В работе', ['start']), // дата не разобрана
    t('', null, null),                  // не взята
  ];
  var got = hours.compute(rows, MON + 3);
  assert.deepStrictEqual(got.hours, [null, null, null, null, null]);
  assert.deepStrictEqual(got.anomalies.map(function (a) { return [a.index, a.reason]; }),
    [[0, 'end-before-start'], [1, 'done-no-end'], [2, 'no-start'], [3, 'bad-date']]);
  Object.keys(hours.REASONS).forEach(function (k) { assert.ok(hours.REASONS[k]); });
});

test('колонки процесса пусты у всех — часов нет, ничего не падает', function () {
  var got = hours.compute([{ dev: '', status: '', start: '', end: '', bad: [] }], MON);
  assert.deepStrictEqual(got.hours, [null]);
  assert.strictEqual(got.workdays.size, 0);
});

test('загрузка и рабочие дни', function () {
  var got = hours.compute([t('X', MON, MON), t('X', MON, MON + 7)], MON + 7);
  assert.strictEqual(got.load.get('X').get(MON), 2);
  assert.deepStrictEqual([...got.workdays.get('X')].sort(function (a, b) { return a - b; }), [MON, MON + 1, MON + 2, MON + 3, MON + 4, MON + 7]);
});

test('summary: среднее и медиана', function () {
  assert.deepStrictEqual(hours.summary([]), { n: 0, mean: null, median: null });
  assert.deepStrictEqual(hours.summary([1, 3, 2, 10]), { n: 4, mean: 4, median: 2.5 });
  assert.deepStrictEqual(hours.summary([5]), { n: 1, mean: 5, median: 5 });
});

test('rate: закрыто за рабочий день', function () {
  var days = new Set([MON, MON + 1, MON + 2, MON + 3]);
  assert.strictEqual(hours.rate([MON, MON + 1], days, MON, MON + 3), 0.5);
  assert.strictEqual(hours.rate([MON], new Set(), MON, MON + 3), null);
});
```

- [ ] **Step 2: тесты падают**

Run: `node --test tests/js/`
Expected: `Cannot find module '../../cvesummary/assets/js/hours.js'`.

- [ ] **Step 3: `cvesummary/assets/js/hours.js`**

```js
/* Часы работы по задачам. В рабочий день разработчика его 8 часов
   делятся поровну между задачами, которые на нём висят: от Start date до
   End date включительно, у открытой — до даты отчёта. Когда внутри дня
   задача закрыта, неизвестно, поэтому день закрытия делится наравне с
   остальными. Выходной рабочий, если в этот день разработчик взял или
   закрыл задачу. Часы задачи — сумма её долей. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./dates.js'), require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.hours = factory(root.CS.dates, root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles) {
  'use strict';

  const HOURS_PER_DAY = 8;
  const REASONS = {
    'no-start': 'нет Start date',
    'end-before-start': 'End date раньше Start date',
    'done-no-end': '«Готов» без End date',
    'bad-date': 'Start date или End date не разобрана',
  };

  /* Интервал задачи или причина, по которой его нет. Не взятая задача —
     ни того, ни другого. */
  function spanOf(r, asOf) {
    if (!roles.isTaken(r)) return { span: null, reason: null };
    if ((r.bad || []).some(k => k === 'start' || k === 'end')) return { span: null, reason: 'bad-date' };
    const from = dates.dayOf(r.start), end = dates.dayOf(r.end);
    if (from === null) return { span: null, reason: 'no-start' };
    if (end !== null && end < from) return { span: null, reason: 'end-before-start' };
    if (end === null && roles.isDone(r)) return { span: null, reason: 'done-no-end' };
    if (from > asOf) return { span: null, reason: null };
    return { span: { from, to: Math.min(end === null ? asOf : end, asOf), end }, reason: null };
  }

  function compute(rows, asOf) {
    const hours = rows.map(() => null);
    const anomalies = [];
    const byDev = new Map();
    rows.forEach((r, i) => {
      const { span, reason } = spanOf(r, asOf);
      if (reason) { anomalies.push({ index: i, reason }); return; }
      if (!roles.isTaken(r)) return;
      hours[i] = 0;
      if (!span) return;
      const dev = roles.devOf(r);
      if (!byDev.has(dev)) byDev.set(dev, []);
      byDev.get(dev).push(Object.assign({ i }, span));
    });

    const workdays = new Map(), load = new Map();
    for (const [dev, spans] of byDev) {
      const edges = new Set();
      spans.forEach(s => { edges.add(s.from); if (s.end !== null) edges.add(s.end); });
      const lo = Math.min(...spans.map(s => s.from)), hi = Math.max(...spans.map(s => s.to));
      const days = new Set(), counts = new Map();
      for (let d = lo; d <= hi; d++) {
        const on = spans.filter(s => s.from <= d && d <= s.to);
        if (!on.length) continue;
        counts.set(d, on.length);
        if (dates.isWeekend(d) && !edges.has(d)) continue;
        days.add(d);
        const share = HOURS_PER_DAY / on.length;
        on.forEach(s => { hours[s.i] += share; });
      }
      workdays.set(dev, days);
      load.set(dev, counts);
    }
    return { hours, anomalies, workdays, load };
  }

  function summary(values) {
    const v = values.filter(x => typeof x === 'number' && isFinite(x)).sort((a, b) => a - b);
    if (!v.length) return { n: 0, mean: null, median: null };
    const mid = v.length >> 1;
    return {
      n: v.length,
      mean: v.reduce((a, b) => a + b, 0) / v.length,
      median: v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2,
    };
  }

  function rate(closedDays, workdays, from, to) {
    let worked = 0;
    workdays.forEach(d => { if (d >= from && d <= to) worked++; });
    if (!worked) return null;
    return closedDays.filter(d => d >= from && d <= to).length / worked;
  }

  return { HOURS_PER_DAY, REASONS, compute, summary, rate };
}));
```

- [ ] **Step 4: тесты проходят**

Run: `node --test tests/js/`
Expected: `fail 0`.

- [ ] **Step 5: commit**

```bash
git add tools/cvesummary/cvesummary/assets/js/hours.js tools/cvesummary/tests/js/hours.test.js
git commit -m "feat(cvesummary): split a developer's 8-hour day between hanging tasks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: JS — темп, прогноз, ширина графиков

**Files:**
- Create: `cvesummary/assets/js/pace.js`, `cvesummary/assets/js/timeline.js`
- Test: `tests/js/pace.test.js`, `tests/js/timeline.test.js`

**Interfaces:**
- Consumes: `CS.dates.dayOf`, `CS.roles.isDone`, `CS.roles.isOpen`.
- Produces `CS.pace`:
  - `rates(rows, asOf, win) -> { inR, outR, net, open }` — задач в календарный день за окно `(asOf − win, asOf]`; закрытие — «Готов» по `End date`;
  - `simulate(n, inR, outR, asOf, inflowUntil) -> number|null` — дней до нуля; `inflowUntil`: `undefined` — поступление бессрочно, `null` — новых нет, число — новые приходят в дни `< inflowUntil`; `null` в ответе — не дойдёт за 3650 дней;
  - `need(n, inR, asOf, stop, target) -> { perDay, left, incoming }|null` — `null`, если `target ≤ asOf`;
  - `daily(rows, from, to) -> Array<{ day, i, o, ia, oa }>` — поступило / закрыто за день и средние за 7 дней.
- Produces `CS.timeline`:
  - `layout(count, minStep, avail) -> { width, step }`;
  - `edges(scrollLeft, scrollWidth, clientWidth) -> { left, right }` — есть ли данные за левым и правым краем;
  - `attach(box)` — перетаскивание мышью и градиенты у краёв (только браузер);
  - `sync(box)` — пересчитать градиенты.

- [ ] **Step 1: падающие тесты**

`tests/js/pace.test.js`:

```js
'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var pace = require('../../cvesummary/assets/js/pace.js');

var D = 20731;
var iso = dates.isoOf;
function r(tdate, status, end) { return { tdate: iso(tdate), status: status || '', end: end === undefined ? '' : iso(end) }; }

test('rates: поступление и закрытие за окно', function () {
  var rows = [r(D), r(D + 1), r(D + 6, 'Готов', D + 6), r(D + 6, 'Готов', D + 3), r(D - 1), r(D + 9)];
  var got = pace.rates(rows, D + 6, 7);
  assert.strictEqual(got.inR, 4 / 7);   // D-1 вне окна, D+9 после даты отчёта
  assert.strictEqual(got.outR, 2 / 7);
  assert.strictEqual(got.open, 4);
  assert.strictEqual(got.net, 2 / 7 - 4 / 7);
});

test('rates без закрытых и без дат — нули, не NaN', function () {
  var got = pace.rates([{ tdate: '', status: '', end: '' }], D, 14);
  assert.deepStrictEqual(got, { inR: 0, outR: 0, net: 0, open: 1 });
});

test('simulate', function () {
  assert.strictEqual(pace.simulate(0, 1, 1, D), 0);
  assert.strictEqual(pace.simulate(5, 0, 0, D), null);           // не закрываем
  assert.strictEqual(pace.simulate(10, 0, 2, D, null), 5);
  assert.strictEqual(pace.simulate(10, 2, 2, D), null);          // приходит столько же
  assert.strictEqual(pace.simulate(4, 1, 2, 0, 3), 3);           // сканфриз на 3-й день
  assert.strictEqual(pace.simulate(1, 0, 0.1, D, null), 10);     // без ошибки округления
});

test('need', function () {
  assert.strictEqual(pace.need(10, 1, 0, null, 0), null);
  assert.deepStrictEqual(pace.need(10, 1, 0, null, 10), { perDay: 2, left: 10, incoming: 10 });
  assert.deepStrictEqual(pace.need(10, 1, 0, 5, 10), { perDay: 1.4, left: 10, incoming: 4 });
});

test('daily: по дням и среднее за 7', function () {
  var got = pace.daily([r(D), r(D), r(D + 1, 'Готов', D + 1)], D, D + 1);
  assert.deepStrictEqual(got.map(function (s) { return [s.day, s.i, s.o]; }), [[D, 2, 0], [D + 1, 1, 1]]);
  assert.strictEqual(got[1].ia, 1.5);
  assert.strictEqual(got[1].oa, 0.5);
  assert.deepStrictEqual(pace.daily([], D + 1, D), []);
});
```

`tests/js/timeline.test.js`:

```js
'use strict';
var test = require('node:test');
var assert = require('node:assert');
var timeline = require('../../cvesummary/assets/js/timeline.js');

test('layout: помещается — растягивается, нет — минимальный шаг', function () {
  assert.deepStrictEqual(timeline.layout(10, 10, 300), { width: 300, step: 30 });
  assert.deepStrictEqual(timeline.layout(100, 10, 300), { width: 1000, step: 10 });
  assert.deepStrictEqual(timeline.layout(0, 10, 300), { width: 300, step: 300 });
});

test('edges: где есть данные за краем', function () {
  assert.deepStrictEqual(timeline.edges(0, 1000, 300), { left: false, right: true });
  assert.deepStrictEqual(timeline.edges(700, 1000, 300), { left: true, right: false });
  assert.deepStrictEqual(timeline.edges(350, 1000, 300), { left: true, right: true });
  assert.deepStrictEqual(timeline.edges(0, 300, 300), { left: false, right: false });
});
```

- [ ] **Step 2: тесты падают**

Run: `node --test tests/js/`
Expected: `Cannot find module '../../cvesummary/assets/js/pace.js'`.

- [ ] **Step 3: `cvesummary/assets/js/pace.js`**

```js
/* Темп и прогноз в задачах — как в образце сводки. Поступление — по Task
   date, закрытие — «Готов» по End date; всё, что позже даты отчёта, ещё
   не случилось. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./dates.js'), require('./roles.js'));
  } else {
    root.CS = root.CS || {};
    root.CS.pace = factory(root.CS.dates, root.CS.roles);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dates, roles) {
  'use strict';

  const HORIZON = 3650;
  const EPS = 1e-9;

  const inDay = r => dates.dayOf(r.tdate);
  const outDay = r => (roles.isDone(r) ? dates.dayOf(r.end) : null);

  function rates(rows, asOf, win) {
    const from = asOf - win;
    const within = d => d !== null && d > from && d <= asOf;
    const inR = rows.map(inDay).filter(within).length / win;
    const outR = rows.map(outDay).filter(within).length / win;
    return { inR, outR, net: outR - inR, open: rows.filter(roles.isOpen).length };
  }

  function simulate(n, inR, outR, asOf, inflowUntil) {
    if (n <= 0) return 0;
    if (outR <= 0) return null;
    let left = n;
    for (let d = 1; d <= HORIZON; d++) {
      const day = asOf + d;
      if (inflowUntil === undefined || (inflowUntil !== null && day < inflowUntil)) left += inR;
      left -= outR;
      if (left <= EPS) return d;
    }
    return null;
  }

  function need(n, inR, asOf, stop, target) {
    const left = target - asOf;
    if (left <= 0) return null;
    const inflowDays = stop === null ? left : Math.max(0, Math.min(left, stop - asOf - 1));
    const incoming = inR * inflowDays;
    return { perDay: (n + incoming) / left, left, incoming };
  }

  function daily(rows, from, to) {
    const n = to - from + 1;
    if (n <= 0) return [];
    const s = [];
    for (let k = 0; k < n; k++) s.push({ day: from + k, i: 0, o: 0, ia: 0, oa: 0 });
    const put = (d, key) => { if (d !== null && d >= from && d <= to) s[d - from][key]++; };
    rows.forEach(r => { put(inDay(r), 'i'); put(outDay(r), 'o'); });
    s.forEach((x, k) => {
      const w = s.slice(Math.max(0, k - 6), k + 1);
      x.ia = w.reduce((a, y) => a + y.i, 0) / w.length;
      x.oa = w.reduce((a, y) => a + y.o, 0) / w.length;
    });
    return s;
  }

  return { rates, simulate, need, daily };
}));
```

- [ ] **Step 4: `cvesummary/assets/js/timeline.js`**

```js
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

  function sync(box) {
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
    box.addEventListener('pointermove', ev => {
      if (!drag || ev.pointerId !== drag.id) return;
      const dx = ev.clientX - drag.x;
      if (Math.abs(dx) < DRAG && !box.classList.contains('dragging')) return;
      if (!box.classList.contains('dragging')) { box.classList.add('dragging'); box.setPointerCapture(drag.id); }
      box.scrollLeft = drag.left - dx;
    });
    const stop = () => { drag = null; box.classList.remove('dragging'); };
    box.addEventListener('pointerup', stop);
    box.addEventListener('pointercancel', stop);
  }

  return { layout, edges, sync, attach };
}));
```

- [ ] **Step 5: тесты проходят**

Run: `node --test tests/js/`
Expected: `fail 0`.

- [ ] **Step 6: commit**

```bash
git add tools/cvesummary/cvesummary/assets/js/pace.js tools/cvesummary/cvesummary/assets/js/timeline.js tools/cvesummary/tests/js
git commit -m "feat(cvesummary): add pace, forecast and scrollable time chart helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: сборка страницы, разметка, стили, каркас отрисовки

**Files:**
- Create: `cvesummary/page.py`, `cvesummary/assets/summary.html`, `cvesummary/assets/summary.css`, `cvesummary/assets/js/render.js` (каркас), `tests/test_page.py`
- Source (только чтение): `../../Сводка по CVE.html` — образец, лежит в корне рабочей копии, не в git.

**Interfaces:**
- Consumes: JS-модули из Task 3–5.
- Produces: `page.render(data: dict) -> str`; `page.data_json(data: dict) -> str`; `page.SCRIPTS` — порядок модулей; `page.ASSETS` — каталог. Маркеры шаблона: `/*@css*/` внутри `<style>`, `@data@` внутри `<script type="application/json" id="data">`, `/*@js*/` внутри последнего `<script>`. id элементов разметки — в `summary.html` ниже; `render.js` (Task 8) пользуется ровно ими.

- [ ] **Step 1: падающие тесты**

`tests/test_page.py`:

```python
import json
import os
import re
import unittest

from cvesummary import page

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)
DATA = {"meta": {"version": "1.0.0", "as_of": "2026-10-19"},
        "rows": [{"cve": "CVE-1", "comment": "</script><script>alert(1)</script><!-- & >"}]}


class DataJsonTest(unittest.TestCase):
    def test_escapes_markup(self):
        text = page.data_json(DATA)
        for ch in "<>&":
            self.assertNotIn(ch, text)
        self.assertEqual(json.loads(text), DATA)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.html = page.render(DATA)

    def test_data_round_trips(self):
        self.assertEqual(json.loads(DATA_RE.search(self.html).group(1)), DATA)

    def test_cell_cannot_close_a_script(self):
        self.assertEqual(self.html.count("</script>"), 2)

    def test_markers_are_replaced(self):
        for marker in ("/*@css*/", "@data@", "/*@js*/"):
            self.assertNotIn(marker, self.html)

    def test_scripts_in_dependency_order(self):
        positions = [self.html.index("root.CS.%s =" % name[:-3]) for name in page.SCRIPTS
                     if name != "render.js"]
        self.assertEqual(positions, sorted(positions))
        self.assertGreater(self.html.index("JSON.parse(document.getElementById('data')"), positions[-1])

    def test_css_is_inlined(self):
        self.assertIn(".tl-scroll{", self.html)


class AssetsTest(unittest.TestCase):
    def test_assets_cannot_break_out_of_their_tags(self):
        names = ["summary.css"] + ["js/" + n for n in page.SCRIPTS]
        for name in names:
            with open(os.path.join(page.ASSETS, name), encoding="utf-8") as handle:
                text = handle.read().lower()
            with self.subTest(name=name):
                self.assertNotIn("</script", text)
                self.assertNotIn("</style", text)
                self.assertNotIn("<!--", text)
```

- [ ] **Step 2: тесты падают**

Run: `python3 -m unittest tests.test_page -v`
Expected: `ModuleNotFoundError: No module named 'cvesummary.page'`.

- [ ] **Step 3: `cvesummary/page.py`**

```python
"""Страница сводки одним файлом: шаблон, стили, скрипты и данные.

Данные — JSON в <script type="application/json">; «<», «>» и «&» в нём
заменены \\u-последовательностями, поэтому ячейка с «</script>» или «<!--»
блок не закроет. Маркеры заменяются только в шаблоне: в стилях и скриптах
такие же строки ни на что не влияют.
"""
import json
import os
import re

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
# порядок важен: модуль ниже пользуется теми, что выше
SCRIPTS = ("dates.js", "roles.js", "hours.js", "pace.js", "timeline.js", "render.js")
_CSS, _DATA, _JS = "/*@css*/", "@data@", "/*@js*/"


def data_json(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render(data: dict) -> str:
    template = _asset("summary.html")
    parts = {
        _CSS: _asset("summary.css"),
        _DATA: data_json(data),
        _JS: "\n".join(_asset(os.path.join("js", name)) for name in SCRIPTS),
    }
    for marker in parts:
        if template.count(marker) != 1:
            raise RuntimeError("шаблон summary.html: маркер %s должен встречаться один раз" % marker)
    pattern = re.compile("|".join(re.escape(marker) for marker in parts))
    return pattern.sub(lambda match: parts[match.group(0)], template)


def _asset(name: str) -> str:
    with open(os.path.join(ASSETS, name), encoding="utf-8") as handle:
        return handle.read()
```

- [ ] **Step 4: `cvesummary/assets/summary.html`**

Разметка образца с заменами из спеки: плитки по ролям, графики по времени
— контейнеры `.tl`, колонка «Часов», блок «Аномалии», новые пояснения.

```html
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Сводка по CVE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;700&family=Onest:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>/*@css*/</style>
</head>
<body>
<div id="tip" hidden></div>

<header class="hero">
  <div class="wrap">
    <div class="hero-top">
      <div>
        <div class="eyebrow" id="period">Период: —</div>
        <h1>Сводка по CVE</h1>
        <p class="asof" id="asof">—</p>
      </div>
    </div>
    <div class="board">
      <div class="total">
        <span class="e">Всего задач</span>
        <span class="n" id="k-total">—</span>
        <span class="s"><b id="k-cve">—</b> уникальных CVE · <b id="k-comp">—</b> компонентов</span>
        <div class="mixbar" id="mixbar"></div>
        <div class="mixleg" id="mixleg"></div>
      </div>
      <div class="groups">
        <div class="grp">
          <div class="grp-h"><b>Состояние</b></div>
          <div class="tiles">
            <div class="kpi" style="--k:#5CC48A"><span class="v" id="k-closed">—</span><span class="l">готово</span></div>
            <div class="kpi" style="--k:#FF8A6B"><span class="v" id="k-work">—</span><span class="l" id="k-work-l">в работе</span></div>
            <div class="kpi" style="--k:#4A5B6A"><span class="v" id="k-free">—</span><span class="l">не взято</span></div>
          </div>
        </div>
        <div class="grp">
          <div class="grp-h"><b>Можно закрыть</b><span id="k-ready">—</span></div>
          <div class="tiles">
            <div class="kpi" style="--k:#BFE3F2"><span class="v" id="k-fixed">—</span><span class="l">фикс в RHEL (Fixed)</span></div>
            <div class="kpi" style="--k:#7FC6E4"><span class="v" id="k-own">—</span><span class="l">есть свой патч (P = +)</span></div>
            <div class="kpi" style="--k:#3E9CC4"><span class="v" id="k-out">—</span><span class="l">версия вне диапазона (D = +)</span></div>
          </div>
        </div>
        <div class="grp">
          <div class="grp-h"><b>Риски и темп</b></div>
          <div class="tiles">
            <div class="kpi hot"><span class="v" id="k-ci">—</span><span class="l">Critical и Important открыты</span></div>
            <div class="kpi"><span class="v" id="k-att">—</span><span class="l">есть проблема / нужна доработка</span></div>
            <div class="kpi"><span class="v" id="k-hours">—</span><span class="l" id="k-hours-l">часов на задачу</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</header>

<main>
  <div class="wrap">
    <section class="card wide" id="cve">
      <div class="cve-grid">
        <div class="cve-sum">
          <h2>CVE</h2>
          <p class="sub" style="margin:0">по критичности, RHEL severity</p>
          <div class="sevstrip" id="sevstrip"></div>
        </div>
        <div class="cve-rows" id="sevrows"></div>
      </div>
      <hr class="cve-div">
      <div class="cve-grid">
        <div class="cve-sum">
          <h3 class="cve-h3">Принятые меры</h3>
          <p class="sub" style="margin:0">для задач, где мера указана</p>
          <div class="sevstrip" id="measstrip"></div>
        </div>
        <div class="cve-rows" id="measrows"></div>
      </div>
    </section>

    <section class="card wide" id="pace">
      <div class="pace-head">
        <div><h2>Темп и прогноз</h2><p class="sub" id="pace-sub">—</p></div>
        <div class="pace-ctl">
          <label for="stop-date">Сканфриз<input type="date" id="stop-date"></label>
          <label for="target-date">Хотим закончить к<input type="date" id="target-date"></label>
          <label for="pace-win">Темп за<select id="pace-win"><option value="7">7 дней</option><option value="14" selected>14 дней</option><option value="30">30 дней</option></select></label>
        </div>
      </div>
      <div class="pace-body">
        <div class="pace-left">
          <div class="pace-stats">
            <div class="ps"><span class="v" id="p-in">—</span><span class="l">поступает в день</span></div>
            <div class="ps"><span class="v" id="p-out">—</span><span class="l">закрывается в день</span></div>
            <div class="ps"><span class="v" id="p-net">—</span><span class="l" id="p-net-l">баланс в день</span></div>
            <div class="ps"><span class="v" id="p-open">—</span><span class="l">открыто сейчас</span></div>
          </div>
          <div class="pace-chart">
            <div class="pace-leg"><span><i style="background:var(--sev-imp)"></i>поступило</span><span><i style="background:var(--ok)"></i>закрыто</span><span><i style="background:var(--muted);height:1px;opacity:.6"></i>по дням</span><span><i style="background:var(--muted)"></i>среднее за 7 дней</span><span><i style="background:var(--accent-soft);height:10px;vertical-align:-1px"></i>окно расчёта</span></div>
            <div class="tl pace-tl" id="pace-chart" role="img" aria-label="Поступление и закрытие задач по дням"></div>
          </div>
        </div>
        <div class="fc" id="forecast"></div>
      </div>
      <p class="pace-note" id="pace-note"></p>
    </section>

    <section class="card wide" id="attention">
      <h2>Требует внимания<span class="cnt" id="att-n"></span></h2>
      <p class="sub">Задачи со статусом «Есть проблема» или «Нужна доработка». Отсортировано по CVSS.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>CVE</th><th>Компонент</th><th>Критичность</th><th>CVSS</th><th>RHEL</th><th>Сборка RHEL</th><th>Статус</th><th>Разработчик</th><th>Часов</th></tr></thead>
        <tbody id="att-body"></tbody>
      </table></div>
    </section>

    <section class="card wide" id="closable">
      <h2>Можно закрыть<span class="cnt" id="close-n"></span></h2>
      <p class="sub">Открытые задачи, по которым решение уже есть. Одна задача может иметь несколько оснований.</p>
      <div class="hbars" id="close-why"></div>
      <div class="tablewrap"><table>
        <thead><tr><th>CVE</th><th>Компонент</th><th>Критичность</th><th>CVSS</th><th>Основание</th><th>Статус</th><th>Разработчик</th><th>Часов</th></tr></thead>
        <tbody id="close-body"></tbody>
      </table></div>
    </section>

    <section class="card wide">
      <h2>Компоненты</h2>
      <p class="sub">Сколько CVE приходится на пакет, с разбивкой по критичности. Первые 12.</p>
      <div class="sevlegend comp-leg" id="compleg"></div>
      <div class="hbars" id="components"></div>
    </section>

    <section class="card">
      <h2>Состояние в RHEL</h2>
      <p class="sub">Поле RHEL state</p>
      <div class="hbars" id="rhel"></div>
    </section>

    <section class="card">
      <h2>Статус задач</h2>
      <p class="sub">Статус у разработчика</p>
      <div class="hbars" id="devstatus"></div>
    </section>

    <section class="card wide">
      <h2>Поступление задач по неделям</h2>
      <p class="sub">По полю Task date, неделя начинается в понедельник, с разбивкой по критичности (RHEL severity)</p>
      <div class="sevlegend comp-leg" id="weekleg"></div>
      <div class="tl" id="weeks" role="img" aria-label="Количество задач по неделям"></div>
    </section>

    <section class="card wide">
      <h2>Разработчики</h2>
      <p class="sub">Сжигание по неделям: задачи со статусом «Готов» по End date, с разбивкой по разработчикам</p>
      <div class="sevlegend comp-leg" id="burnleg"></div>
      <div class="tl" id="burn" role="img" aria-label="Закрытые задачи по неделям и разработчикам"></div>
      <div class="sevlegend comp-leg" id="statleg"></div>
      <div class="people" id="people"></div>
    </section>

    <section class="card wide" id="anomalies">
      <h2>Аномалии<span class="cnt" id="anom-n"></span></h2>
      <p class="sub">Строки, которые не попали в расчёт часов, и даты, которые не разобрались. Строка — номер строки листа.</p>
      <ul class="anom-notes" id="anom-notes"></ul>
      <div class="tablewrap"><table>
        <thead><tr><th>Строка</th><th>CVE</th><th>Компонент</th><th>Разработчик</th><th>Статус</th><th>Start date</th><th>End date</th><th>Причина</th></tr></thead>
        <tbody id="anom-body"></tbody>
      </table></div>
    </section>

    <dl class="foot">
      <div><dt>Готово:</dt> <dd>статус разработчика «Готов».</dd></div>
      <div><dt>В работе:</dt> <dd>разработчик назначен, статус не «Готов». На ревью — «Ожидает ревью», на паузе — «На паузе»; обе открытые.</dd></div>
      <div><dt>Не взято:</dt> <dd>разработчик не назначен.</dd></div>
      <div><dt>Требует внимания:</dt> <dd>«Есть проблема» или «Нужна доработка».</dd></div>
      <div><dt>Часы:</dt> <dd>в рабочий день разработчика его 8 часов делятся поровну между задачами, которые на нём висят — от Start date до End date включительно, у открытых до даты отчёта. Выходной рабочий, если в этот день он взял или закрыл задачу. Часы задачи — сумма её долей.</dd></div>
      <div><dt>Можно закрыть:</dt> <dd>открытая задача, у которой RHEL state = Fixed, или P = + (патч уже у нас), или D = + (наша версия вне уязвимого диапазона).</dd></div>
      <div><dt>Флаги P и D</dt> <dd>по всем задачам: <span id="pd">—</span>.</dd></div>
      <div><dt>Пустые значения</dt> <dd>«-» и пустые ячейки считаются отсутствующими. Task state в расчётах не участвует.</dd></div>
      <div><dt>Источник:</dt> <dd id="src">—</dd></div>
    </dl>
  </div>
</main>

<script type="application/json" id="data">@data@</script>
<script>/*@js*/</script>
</body>
</html>
```

- [ ] **Step 5: `cvesummary/assets/summary.css` — стили образца плюс графики**

Скопировать стили образца и убрать правила SVG, которые заменены
контейнером `.tl` (строки, начинающиеся с `.pace-box`, `.pace-svg`,
`.cols`, `.dev .spark`, и комментарий `/* weekly columns */`):

```bash
python3 - "../../Сводка по CVE.html" cvesummary/assets/summary.css <<'EOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
start = s.index("<style>", s.index("fonts.googleapis.com/css2")) + len("<style>")
css = s[start:s.index("</style>", start)]
css = re.sub(r"(?m)^(\.pace-box|\.pace-svg|\.cols|\.dev \.spark|/\* weekly columns \*/)[^\n]*\n", "", css)
open(dst, "w", encoding="utf-8").write(css.strip() + "\n")
EOF
grep -c "pace-svg\|\.cols\|\.spark" cvesummary/assets/summary.css
```

Expected: `0`.

Дописать в конец `cvesummary/assets/summary.css`:

```css

/* cvesummary: базовые правила, которые образец получал от обёртки страницы */
body{margin:0}
img{max-width:100%}
[hidden]{display:none!important}

/* Графики по времени: ось значений стоит, столбики листаются внутри
   карточки, полосы прокрутки не видно; градиент — у края, за которым
   есть ещё дни. */
.tl{position:relative;display:flex;min-width:0}
.tl-axis{flex:0 0 auto;display:block}
.tl-scroll{flex:1 1 auto;min-width:0;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;overscroll-behavior-x:contain;cursor:grab}
.tl-scroll::-webkit-scrollbar{display:none}
.tl-scroll.dragging{cursor:grabbing;user-select:none}
.tl-plot{display:block}
.tl text{fill:var(--muted);font:11.5px var(--f-body)}
.tl .gl{stroke:var(--grid)}
.tl::before,.tl::after{content:"";position:absolute;top:0;bottom:0;width:28px;pointer-events:none;opacity:0;transition:opacity .15s}
.tl::before{left:var(--axis,32px);background:linear-gradient(to right,var(--fade,var(--panel)),transparent)}
.tl::after{right:0;background:linear-gradient(to left,var(--fade,var(--panel)),transparent)}
.tl.fade-l::before,.tl.fade-r::after{opacity:1}
.pace-tl{flex:1;min-height:230px}
.spark-tl{--axis:0px}
.anom-notes{margin:0;padding-left:18px;color:var(--muted);font-size:13.5px}
.anom-notes:empty{display:none}
```

- [ ] **Step 6: каркас `cvesummary/assets/js/render.js`**

Минимальный, чтобы страница открывалась; полный — Task 8.

```js
/* Отрисовка сводки: данные — из блока #data, считают модули dates, roles,
   hours, pace и timeline; здесь только DOM. */
(function () {
  'use strict';
  const DATA = JSON.parse(document.getElementById('data').textContent);
  document.getElementById('k-total').textContent = DATA.rows.length;
}());
```

- [ ] **Step 7: тесты проходят**

Run: `python3 -m unittest discover -s tests -v && node --test tests/js/`
Expected: OK, `fail 0`.

- [ ] **Step 8: commit**

```bash
git add tools/cvesummary/cvesummary/page.py tools/cvesummary/cvesummary/assets tools/cvesummary/tests/test_page.py
git commit -m "feat(cvesummary): assemble the summary page from assets and data

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: CLI

**Files:**
- Create: `cvesummary/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `xlsx.read`, `xlsx.XlsxError`, `table.build`, `table.TableError`, `page.render`.
- Produces: `cli.main(argv: Optional[List[str]] = None) -> int`; `cli.EXIT_OK = 0`, `cli.EXIT_FATAL = 2`; `cli.default_output(path) -> str`; `cli._today() -> datetime.date` (подменяется в тестах).
- Данные страницы: `{"meta": {"version", "source", "sheet", "header_row", "as_of", "skipped", "missing", "bad_dates"}, "rows": [...]}`.

- [ ] **Step 1: падающие тесты**

`tests/test_cli.py`:

```python
import datetime
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cvesummary import __version__, cli
from tests.xlsxmake import write

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)
REQUIRED = ["CVE ID", "Компонент", "RHEL state", "RHEL severity"]
HEADER = ["Разработчик", "Статус", "Start date", "End date"] + REQUIRED
ROWS = [HEADER, ["Иванов", "Готов", "05.10.2026", "07.10.2026", "CVE-1", "bash", "Affected", "Low"],
        ["", "", "", "", "", "bash", "", ""]]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.table = self.path("t.xlsx")
        write(self.table, ROWS)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def run_cli(self, *args):
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(list(args))
        return code, err.getvalue()

    def data(self, path):
        with open(path, encoding="utf-8") as handle:
            return json.loads(DATA_RE.search(handle.read()).group(1))


class WriteTest(Base):
    def test_default_output_next_to_table(self):
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        data = self.data(self.path("t.html"))
        self.assertEqual([r["cve"] for r in data["rows"]], ["CVE-1"])
        self.assertEqual(data["meta"]["as_of"], "2026-10-19")
        self.assertEqual(data["meta"]["skipped"], 1)
        self.assertEqual(data["meta"]["source"], "t.xlsx")
        self.assertIn("записано", log)
        self.assertIn("без CVE ID пропущено: 1", log)

    def test_explicit_output(self):
        code, _ = self.run_cli(self.table, "-o", self.path("x.html"), "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue(os.path.exists(self.path("x.html")))

    def test_overwrite_warns(self):
        self.run_cli(self.table, "--as-of", "2026-10-19")
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("перезаписан", log)

    def test_as_of_defaults_to_today(self):
        with mock.patch.object(cli, "_today", return_value=datetime.date(2026, 1, 2)):
            self.run_cli(self.table)
        self.assertEqual(self.data(self.path("t.html"))["meta"]["as_of"], "2026-01-02")

    def test_page_is_readable_by_others(self):
        self.run_cli(self.table, "--as-of", "2026-10-19")
        mode = os.stat(self.path("t.html")).st_mode & 0o777
        self.assertEqual(mode, 0o666 & ~cli._umask())

    def test_only_required_columns(self):
        write(self.table, [REQUIRED, ["CVE-1", "bash", "Affected", "Low"]])
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("Разработчик", log)  # названа среди отсутствующих
        self.assertEqual(self.data(self.path("t.html"))["rows"][0]["dev"], "")


class FailTest(Base):
    def test_bad_as_of(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.main([self.table, "--as-of", "19.10.2026"])
        self.assertEqual(caught.exception.code, cli.EXIT_FATAL)

    def test_not_xlsx(self):
        with open(self.table, "wb") as handle:
            handle.write(b"nope")
        code, log = self.run_cli(self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        self.assertIn(self.table, log)
        self.assertFalse(os.path.exists(self.path("t.html")))

    def test_missing_required_columns(self):
        write(self.table, [["CVE ID"], ["CVE-1"]])
        code, log = self.run_cli(self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        self.assertIn("Компонент", log)

    def test_output_cannot_be_the_table(self):
        before = open(self.table, "rb").read()
        code, log = self.run_cli(self.table, "-o", self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        self.assertEqual(open(self.table, "rb").read(), before)
        html_named = self.path("t.html")
        write(html_named, ROWS)
        code, _ = self.run_cli(html_named)
        self.assertEqual(code, cli.EXIT_FATAL)

    def test_version(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["--version"])
        self.assertIn(__version__, out.getvalue())
```

- [ ] **Step 2: тесты падают**

Run: `python3 -m unittest tests.test_cli -v`
Expected: `ImportError: cannot import name 'cli'`.

- [ ] **Step 3: `cvesummary/cli.py`**

```python
"""Точка входа: xlsx таблицы процесса → HTML-сводка."""
import argparse
import datetime
import logging
import os
import sys
import tempfile
from typing import List, Optional

from . import __version__, page, table, xlsx

logger = logging.getLogger("cvesummary")

EXIT_OK = 0
EXIT_FATAL = 2


def _today() -> datetime.date:
    return datetime.date.today()


def _date(text: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("дата нужна в виде ГГГГ-ММ-ДД: %r" % text)


def default_output(path: str) -> str:
    return os.path.splitext(path)[0] + ".html"


def _parse(argv):
    parser = argparse.ArgumentParser(
        prog="cvesummary",
        description="Сводка по CVE: xlsx таблицы процесса → одна HTML-страница.")
    parser.add_argument("table", help="xlsx таблицы процесса; читается первый лист")
    parser.add_argument("-o", "--output",
                        help="куда записать страницу; по умолчанию рядом с таблицей, <имя>.html")
    parser.add_argument("--as-of", type=_date,
                        help="дата отчёта ГГГГ-ММ-ДД; по умолчанию сегодня")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser.parse_args(argv)


def _setup_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse(argv)
    _setup_logging()
    as_of = args.as_of or _today()
    output = args.output or default_output(args.table)
    if (os.path.exists(output) and os.path.exists(args.table)
            and os.path.samefile(output, args.table)):
        logger.error("%s: страница записалась бы поверх таблицы — задайте другой -o", output)
        return EXIT_FATAL
    try:
        sheet = xlsx.read(args.table)
        found = table.build(sheet)
    except (xlsx.XlsxError, table.TableError) as exc:
        logger.error("%s: %s", args.table, exc)
        return EXIT_FATAL

    logger.info("лист «%s», шапка в строке %d", sheet.name, found.header_row)
    if found.missing:
        logger.info("нет колонок, читаются пустыми: %s", ", ".join(found.missing))
    for name in found.duplicates:
        logger.warning("колонка «%s» повторяется — взята первая", name)
    logger.info("строк: %d; без CVE ID пропущено: %d; дат не разобрано: %d",
                len(found.rows), found.skipped, found.bad_dates)
    if not found.rows:
        logger.warning("строк с CVE ID нет — страница будет пустой")
    logger.info("дата отчёта: %s", as_of.isoformat())

    data = {
        "meta": {"version": __version__, "source": os.path.basename(args.table),
                 "sheet": sheet.name, "header_row": found.header_row,
                 "as_of": as_of.isoformat(), "skipped": found.skipped,
                 "missing": found.missing, "bad_dates": found.bad_dates},
        "rows": found.rows,
    }
    existed = os.path.exists(output)
    try:
        _write(output, page.render(data))
    except OSError as exc:
        logger.error("%s: не записывается: %s", output, exc)
        return EXIT_FATAL
    if existed:
        logger.warning("%s: файл уже был — перезаписан", output)
    logger.info("записано: %s", output)
    return EXIT_OK


def _write(path: str, text: str) -> None:
    """Через временный файл рядом: оборванная запись не оставит полстраницы."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".cvesummary-", suffix=".html", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        # mkstemp создаёт файл 0600, а страницу пересылают людям
        os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask
```

- [ ] **Step 4: тесты проходят**

Run: `python3 -m unittest discover -s tests -v`
Expected: OK.

- [ ] **Step 5: commit**

```bash
git add tools/cvesummary/cvesummary/cli.py tools/cvesummary/tests/test_cli.py
git commit -m "feat(cvesummary): add the command line entry point

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: отрисовка страницы, пример на 100 строк, проверка в браузере

**Files:**
- Modify: `cvesummary/assets/js/render.js` (замена каркаса целиком)
- Create: `tests/example.py`, `tests/test_example.py`
- Source (только чтение): `../../Сводка по CVE.html` — функции `hbars`, тултип, `set` плиток и `statTable` переносятся оттуда с правками ниже.

**Interfaces:**
- Consumes: `CS.dates`, `CS.roles`, `CS.hours`, `CS.pace`, `CS.timeline` (Task 3–5), id разметки из Task 6, данные из Task 7.
- Produces: `python3 -m tests.example OUT.xlsx` — пример на 100 строк со статусами и мерами из `task.md`, группировкой над шапкой, двумя аномалиями и стартами в выходные; `tests.example.rows() -> list` для теста.

- [ ] **Step 1: пример на 100 строк и падающий тест**

`tests/example.py`:

```python
"""Пример таблицы процесса на 100 строк — для ручной проверки страницы.

python3 -m tests.example пример.xlsx

Данные вымышленные, детерминированные (seed). Над шапкой — строка
группировки, даты — текстом дд.мм.гггг, как в живой выгрузке; две строки
— намеренные аномалии («Готов» без End date, End раньше Start).
"""
import datetime
import random
import sys

from tests.xlsxmake import write

AS_OF = datetime.date(2026, 10, 19)
HEADER = ["Разработчик", "Статус", "Start date", "End date", "Принятая мера", "Task ID",
          "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент", "P", "D",
          "SL NVR (latest build)", "RHEL NVR (if fixed)", "Fix date", "RHEL state",
          "RHEL severity", "RHEL CVSS", "Advisory (RHSA)", "CVE link", "Комментарий"]
GROUPS = ["AG21", "", "", "", "", "SberLinux"] + [""] * 10 + ["RedHat"] + [""] * 5
DEVS = ["Иванов И.И.", "Петров П.П.", "Сидорова А.А.", "Кузнецов Д.В.", "Смирнова Е.Н."]
STATUSES = ["В работе"] * 4 + ["Готов"] * 8 + ["На паузе", "Есть проблема",
                                               "Нужна доработка", "Ожидает ревью"]
MEASURES = ["Патч из апстрима", "Импорт новой версии", "Тег свежего билда",
            "Пакет пересобран (если в зависимостях)", "Обоснована неприменимость",
            "Патч из прошлой ветки", "Самописный патч", "Было исправлено ранее",
            "Закрыто SecOps", "Написана мера компенсации", "Другое"]
PACKAGES = ["openssl", "bash", "curl", "httpd", "glibc", "systemd", "git", "libxml2",
            "sudo", "openssh", "nodejs", "postgresql", "kernel", "podman", "samba"]
SEVERITY = [("Low", "3.3"), ("Moderate", "5.5"), ("Moderate", "6.5"), ("Important", "7.5"),
            ("Important", "8.1"), ("Critical", "9.8"), ("", "")]
STATES = ["Affected"] * 4 + ["Fixed"] * 3 + ["Under investigation", "Will not fix", "not listed"]


def _d(day):
    return day.strftime("%d.%m.%Y")


def rows():
    rnd = random.Random(20261019)
    out = [GROUPS, HEADER]
    for n in range(100):
        pkg = rnd.choice(PACKAGES)
        cve = "CVE-2026-%05d" % (70000 + n * 37)
        tdate = AS_OF - datetime.timedelta(days=rnd.randrange(60))
        sev, cvss = rnd.choice(SEVERITY)
        state = rnd.choice(STATES)
        fixed = state == "Fixed"
        dev = status = start = end = measure = "-"
        if rnd.random() < 0.7:
            dev = rnd.choice(DEVS)
            status = rnd.choice(STATUSES)
            begin = min(AS_OF, tdate + datetime.timedelta(days=rnd.randrange(10)))
            start = _d(begin)
            if status == "Готов" or (status == "Ожидает ревью" and rnd.random() < 0.5):
                end = _d(min(AS_OF, begin + datetime.timedelta(days=rnd.randrange(6))))
            if status == "Готов":
                measure = rnd.choice(MEASURES)
        if n == 7:
            dev, status, start, end = DEVS[0], "Готов", _d(AS_OF), "-"
        if n == 8:
            dev, status, start, end = DEVS[1], "В работе", _d(AS_OF), _d(AS_OF - datetime.timedelta(days=3))
        out.append([dev, status, start, end, measure, "TASKID-%d" % (182000 + n), cve,
                    rnd.choice(["В работу", "В работе", "Выполнена"]), _d(tdate),
                    rnd.choice(["КМ", "ПП", "АС", "ДВ"]), pkg,
                    "+" if rnd.random() < 0.2 else "-", "+" if rnd.random() < 0.15 else "-",
                    "%s-1.0-1.sl9" % pkg, "%s-1.0-2.el9_6" % pkg if fixed else "-",
                    _d(tdate - datetime.timedelta(days=20)) if fixed else "-", state,
                    sev or "-", cvss or "-",
                    "https://access.redhat.com/errata/RHSA-2026:%d" % (1000 + n) if fixed else "-",
                    "https://access.redhat.com/security/cve/" + cve,
                    rnd.choice(["-", "-", "-", "ждём апстрим", "согласовано с ИБ"])])
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    write(argv[0], rows())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`tests/test_example.py`:

```python
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr
import io

from cvesummary import cli
from tests import example

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)


class ExampleTest(unittest.TestCase):
    def test_example_builds_a_page(self):
        with tempfile.TemporaryDirectory() as folder:
            table = os.path.join(folder, "пример.xlsx")
            example.main([table])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main([table, "--as-of", "2026-10-19"]), cli.EXIT_OK)
            with open(os.path.join(folder, "пример.html"), encoding="utf-8") as handle:
                data = json.loads(DATA_RE.search(handle.read()).group(1))
        self.assertEqual(len(data["rows"]), 100)
        self.assertEqual(data["meta"]["header_row"], 2)
        self.assertTrue(any(r["status"] == "Ожидает ревью" for r in data["rows"]))
```

Run: `python3 -m unittest tests.test_example -v`
Expected: PASS уже сейчас (страница собирается и с каркасом `render.js`) — этот тест страхует сборку, а не отрисовку; отрисовку проверяет Step 4.

- [ ] **Step 2: `cvesummary/assets/js/render.js` целиком**

Заменить каркас. Код ниже; функции, помеченные «из образца», —
дословно из `<script>` образца, только с переименованиями, указанными в
комментарии над ними.

```js
/* Отрисовка сводки. Данные — из блока #data; роли, часы, темп и ширина
   графиков — модули dates, roles, hours, pace, timeline; здесь только DOM. */
(function () {
  'use strict';
  const { dates, roles, hours: Hm, pace, timeline } = window.CS;
  const DATA = JSON.parse(document.getElementById('data').textContent);
  const AS_OF = dates.dayOf(DATA.meta.as_of);
  const NS = 'http://www.w3.org/2000/svg';
  const AXIS_W = 32;
  const DAY_STEP = 10, WEEK_STEP = 28, SPARK_STEP = 6;

  const $ = id => document.getElementById(id);
  const css = t => `var(${t})`;
  const f1 = x => (Math.round(x * 10) / 10).toString().replace('.', ',');
  const fmt = d => (d === null || d === undefined ? '—' : dates.ruOf(d));
  const mk = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  const count = (arr, f) => { const m = new Map(); for (const x of arr) { const k = f(x); if (k == null || k === '') continue; m.set(k, (m.get(k) || 0) + 1); } return [...m].sort((a, b) => b[1] - a[1]); };
  const plural = (n, a, b, c) => { n = Math.abs(n) % 100; const n1 = n % 10; return n > 10 && n < 20 ? c : n1 > 1 && n1 < 5 ? b : n1 === 1 ? a : c; };
  const days = n => `${n} ${plural(n, 'день', 'дня', 'дней')}`;
  const LS = { get(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* без хранилища поля просто не запоминаются */ } } };
  const SEV_COLOR = { Critical: '--sev-crit', Important: '--sev-imp', Moderate: '--sev-mod', Low: '--sev-low' };
  const sevColor = k => SEV_COLOR[k] || '--sev-none';
  const link = (href, text, cls) => { if (!/^https?:\/\//.test(href || '')) return null; const a = el('a', cls || null, text); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a; };

  /* тултип — из образца, дословно */
  const tip = $('tip');
  document.addEventListener('pointermove', e => {
    const t = e.target.closest('[data-tip]');
    if (!t) { tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let x = e.clientX + 12, y = e.clientY + 14;
    if (x + w > innerWidth - 8) x = e.clientX - w - 12;
    if (y + h > innerHeight - 8) y = e.clientY - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  });

  /* hbars — из образца, дословно */
  function hbars(target, items, max, opts = {}) {
    const box = $(target); box.replaceChildren();
    if (!items.length) { box.append(el('div', 'empty', 'Нет данных')); return; }
    for (const it of items) {
      box.append(el('div', 'lab', it.label));
      const tr = el('div', 'track');
      const segs = it.segs || [{ n: it.n, color: opts.color || '--accent', name: '' }];
      for (const s of segs) { if (!s.n) continue;
        const sp = el('span'); sp.style.flexBasis = (s.n / max * 100) + '%'; sp.style.background = css(s.color);
        sp.dataset.tip = `${it.label}${s.name ? ' · ' + s.name : ''}: ${s.n}`; tr.append(sp); }
      box.append(tr);
      box.append(el('div', 'val num', it.valText ?? String(it.n)));
    }
  }
  function legend(id, cats) { const leg = $(id); leg.replaceChildren(); for (const s of cats) { const li = el('span'); const sw = el('i', 'sw'); sw.style.background = css(s.c); li.append(sw, s.k); leg.append(li); } }

  /* ---------- данные ---------- */
  const H = Hm.compute(DATA.rows, AS_OF);
  const recs = DATA.rows.map((r, i) => Object.assign({}, r, {
    i, devKey: roles.devOf(r), sevN: roles.sevOf(r), measureN: roles.measureOf(r),
    done: roles.isDone(r), open: roles.isOpen(r), taken: roles.isTaken(r), working: roles.isWorking(r),
    review: roles.isReview(r), paused: roles.isPaused(r), attention: roles.needsAttention(r),
    reasons: roles.closeReasons(r), cvssN: parseFloat(String(r.cvss).replace(',', '.')) || 0,
    tdateD: dates.dayOf(r.tdate), startD: dates.dayOf(r.start), endD: dates.dayOf(r.end), hours: H.hours[i],
  }));
  const closedWithHours = list => list.filter(r => r.done && r.endD !== null && r.hours !== null).map(r => r.hours);
  const SEV_KEYS = roles.sevOrder(recs.map(r => r.sevN));
  const SEV = SEV_KEYS.map(k => ({ k, c: sevColor(k) }));
  const allDays = recs.flatMap(r => [r.tdateD, r.startD, r.endD]).filter(d => d !== null && d <= AS_OF);
  const FIRST = allDays.length ? Math.min(...allDays) : null;
  const statusKey = r => String(r.status || '').trim() || (r.taken ? 'Без статуса' : 'Не взята');
  const roleColor = r => r.done ? '--ok' : r.attention ? '--bad' : r.paused ? '--warn' : r.review ? '--c7' : r.taken ? '--accent' : '--sev-none';
  const hoursText = r => (r.hours === null ? '—' : f1(r.hours));

  /* ---------- графики по времени ---------- */
  function scale(top) {
    top = Math.max(1, top);
    const step = top <= 5 ? 1 : top <= 12 ? 2 : top <= 30 ? 5 : top <= 60 ? 10 : top <= 150 ? 25 : 50;
    return { yMax: Math.ceil(top / step) * step, yStep: step };
  }
  /* Рамка: слева ось значений (стоит на месте), справа листаемая область
     со столбиками. Если пользователь отлистал график назад, перерисовка
     оставляет его там же; иначе график стоит в конце — на последних днях. */
  function frame(host, o) {
    const old = host.querySelector('.tl-scroll');
    const keep = old && timeline.edges(old.scrollLeft, old.scrollWidth, old.clientWidth).right ? old.scrollLeft : null;
    host.replaceChildren();
    const axisW = o.axis === false ? 0 : AXIS_W;
    const box = el('div', 'tl-scroll');
    let axis = null;
    if (axisW) { axis = mk('svg', { class: 'tl-axis', width: axisW, height: o.height, viewBox: `0 0 ${axisW} ${o.height}` }); host.append(axis); }
    host.append(box);
    const avail = Math.max(1, box.clientWidth || host.clientWidth - axisW);
    const { width, step } = timeline.layout(o.count, o.minStep, avail);
    const plot = mk('svg', { class: 'tl-plot', width, height: o.height, viewBox: `0 0 ${width} ${o.height}` });
    box.append(plot);
    const y = n => o.pad.t + (o.height - o.pad.t - o.pad.b) * (1 - n / o.yMax);
    if (axis) {
      for (let g = 0; g <= o.yMax; g += o.yStep) {
        plot.append(mk('line', { x1: 0, x2: width, y1: y(g), y2: y(g), class: 'gl' }));
        const t = mk('text', { x: axisW - 6, y: y(g) + 4, 'text-anchor': 'end' }); t.textContent = g; axis.append(t);
      }
    }
    timeline.attach(box);
    box.scrollLeft = keep === null ? box.scrollWidth : keep;
    timeline.sync(box);
    return { plot, step, width, y, height: o.height };
  }

  function drawPace(series, from) {
    const host = $('pace-chart');
    if (!series.length) { host.replaceChildren(el('div', 'empty', 'Нет дат в Task date и End date')); return; }
    const { yMax, yStep } = scale(Math.max(...series.map(s => Math.max(s.i, s.o))));
    const F = frame(host, { count: series.length, minStep: DAY_STEP, height: 230, yMax, yStep, pad: { t: 8, b: 22 } });
    const x = i => F.step * i + F.step / 2;
    const fi = series.findIndex(s => s.day > from);
    if (fi >= 0) F.plot.prepend(mk('rect', { x: F.step * fi, y: 8, width: F.width - F.step * fi, height: 230 - 30, fill: 'var(--accent-soft)' }));
    const path = (k, c, w, op) => F.plot.append(mk('path', { d: series.map((s, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + F.y(s[k]).toFixed(1)).join(''), fill: 'none', stroke: c, 'stroke-width': w, 'stroke-opacity': op, 'stroke-linejoin': 'round' }));
    path('i', 'var(--sev-imp)', 1, 0.4); path('o', 'var(--ok)', 1, 0.4);
    path('ia', 'var(--sev-imp)', 2.5, 1); path('oa', 'var(--ok)', 2.5, 1);
    const l = series.length - 1;
    [['ia', 'var(--sev-imp)'], ['oa', 'var(--ok)']].forEach(([k, c]) => F.plot.append(mk('circle', { cx: x(l), cy: F.y(series[l][k]), r: 4, fill: c, stroke: 'var(--panel)', 'stroke-width': 2 })));
    const every = Math.ceil(48 / F.step);
    series.forEach((s, i) => {
      if ((l - i) % every === 0) { const t = mk('text', { x: x(i), y: 230 - 8, 'text-anchor': 'middle' }); t.textContent = fmt(s.day).slice(0, 5); F.plot.append(t); }
      const hit = mk('rect', { x: F.step * i, y: 8, width: F.step, height: 200, fill: 'transparent' });
      hit.dataset.tip = `${fmt(s.day)}: поступило ${s.i}, закрыто ${s.o} · среднее за 7 дней ${f1(s.ia)} / ${f1(s.oa)}`;
      F.plot.append(hit);
    });
  }

  function weeksOf(items, cats) {
    if (FIRST === null) return [];
    const lo = dates.mondayOf(FIRST), hi = dates.mondayOf(AS_OF), weeks = [];
    for (let t = lo; t <= hi; t += 7) { const w = { t, all: 0 }; cats.forEach(c => { w[c.k] = 0; }); weeks.push(w); }
    for (const [d, k] of items) { if (d === null || d > AS_OF || d < lo) continue; const w = weeks[(dates.mondayOf(d) - lo) / 7]; w.all++; w[k]++; }
    return weeks;
  }

  /* stackChart — из образца, перенесён на frame(): x считается от F.step,
     высота — F.y, ось — в рамке */
  function stackChart(host, weeks, cats, what) {
    if (!weeks.length) { host.replaceChildren(el('div', 'empty', 'Нет данных с датами')); return; }
    const H2 = 230;
    const { yMax, yStep } = scale(Math.max(...weeks.map(w => w.all)));
    const F = frame(host, { count: weeks.length, minStep: WEEK_STEP, height: H2, yMax, yStep, pad: { t: 16, b: 24 } });
    const barW = Math.max(3, Math.min(56, F.step - 6)), GAP = barW >= 10 ? 2 : 1;
    weeks.forEach((w, i) => {
      const x = i * F.step + (F.step - barW) / 2;
      const segs = cats.filter(s => w[s.k] > 0);
      let acc = 0;
      segs.forEach((s, j) => {
        const n = w[s.k], y1 = F.y(acc + n), y0 = F.y(acc); acc += n;
        const h = Math.max(1, y0 - y1 - (j < segs.length - 1 ? GAP : 0));
        if (j === segs.length - 1 && h > 4) { const r = Math.min(3, barW / 2); F.plot.append(mk('path', { d: `M${x},${y1 + h}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + barW - r}Q${x + barW},${y1} ${x + barW},${y1 + r}V${y1 + h}Z`, fill: css(s.c) })); }
        else F.plot.append(mk('rect', { x, y: y1, width: barW, height: h, fill: css(s.c) }));
      });
      const hit = mk('rect', { x: i * F.step, y: 16, width: F.step, height: H2 - 40, fill: 'transparent' });
      hit.dataset.tip = `Неделя с ${fmt(w.t)}: ${what} ${w.all}` + (w.all ? ' · ' + cats.filter(s => w[s.k]).map(s => `${s.k} ${w[s.k]}`).join(', ') : '');
      F.plot.append(hit);
      if (w.all && F.step >= 26) { const t = mk('text', { x: x + barW / 2, y: F.y(w.all) - 5, 'text-anchor': 'middle' }); t.textContent = w.all; t.style.fill = 'var(--fg)'; F.plot.append(t); }
      const every = Math.ceil(44 / F.step);
      if ((weeks.length - 1 - i) % every === 0) { const lab = mk('text', { x: x + barW / 2, y: H2 - 6, 'text-anchor': 'middle' }); lab.textContent = fmt(w.t).slice(0, 5); F.plot.append(lab); }
    });
  }

  function spark(host, dayCounts, from, color, who) {
    const n = AS_OF - from + 1;
    if (n <= 0) { host.replaceChildren(); return; }
    const top = Math.max(1, ...dayCounts.values());
    const F = frame(host, { count: n, minStep: SPARK_STEP, height: 40, yMax: top, yStep: top, pad: { t: 2, b: 0 }, axis: false });
    for (let i = 0; i < n; i++) {
      const d = from + i, v = dayCounts.get(d) || 0, hh = Math.max(v ? 2 : 1, v / top * 36);
      const r = mk('rect', { x: i * F.step + 0.75, y: 40 - hh, width: Math.max(1, F.step - 1.5), height: hh, fill: v ? css(color) : 'var(--grid)' });
      r.dataset.tip = `${who} · ${fmt(d)}: закрыто ${v}`; F.plot.append(r);
    }
  }

  /* ---------- блоки ---------- */
  function renderHead() {
    const N = recs.length, pct = n => (N ? Math.round(n / N * 100) : 0);
    const tds = recs.map(r => r.tdateD).filter(d => d !== null).sort((a, b) => a - b);
    $('period').textContent = tds.length ? `Период задач: ${fmt(tds[0])} — ${fmt(tds[tds.length - 1])}` : 'Период: даты задач не найдены';
    $('asof').textContent = `на ${fmt(AS_OF)}`;
    $('src').textContent = `${DATA.meta.source}, лист «${DATA.meta.sheet}», шапка в строке ${DATA.meta.header_row}; cvesummary ${DATA.meta.version}`;
    /* set — из образца: значение плитки, мини-полоса и процент */
    const set = (id, n, color) => {
      const v = $(id); v.textContent = n; const tile = v.parentElement;
      tile.querySelectorAll('.mini,.pc').forEach(x => x.remove());
      const m = el('div', 'mini'); const i = el('i'); i.style.width = pct(n) + '%'; i.style.color = color || '#8FA6B8'; m.append(i);
      m.dataset.tip = `${n} из ${N} задач`;
      tile.append(m, el('span', 'pc', `${pct(n)}% от всех`));
    };
    const open = recs.filter(r => r.open), working = recs.filter(r => r.working);
    const ready = open.filter(r => r.reasons.length);
    $('k-total').textContent = N;
    $('k-cve').textContent = new Set(recs.map(r => r.cve)).size;
    $('k-comp').textContent = new Set(recs.map(r => r.comp).filter(Boolean)).size;
    set('k-closed', recs.filter(r => r.done).length, '#5CC48A');
    set('k-work', working.length, '#FF8A6B');
    $('k-work-l').textContent = `в работе, из них на ревью ${working.filter(r => r.review).length}, на паузе ${working.filter(r => r.paused).length}`;
    set('k-free', recs.filter(r => !r.taken && !r.done).length, '#8FA6B8');
    $('k-ready').textContent = `${ready.length} задач без повторов · ${pct(ready.length)}% от всех`;
    set('k-fixed', ready.filter(r => r.reasons.includes('fixed')).length, '#BFE3F2');
    set('k-own', ready.filter(r => r.reasons.includes('patch')).length, '#7FC6E4');
    set('k-out', ready.filter(r => r.reasons.includes('range')).length, '#3E9CC4');
    set('k-ci', open.filter(r => r.sevN === 'Critical' || r.sevN === 'Important').length, '#FF8A6B');
    set('k-att', recs.filter(r => r.attention).length, '#FF8A6B');
    const s = Hm.summary(closedWithHours(recs));
    $('k-hours').textContent = s.n ? f1(s.mean) : '—';
    $('k-hours-l').textContent = s.n ? `часов на задачу, медиана ${f1(s.median)} · по ${s.n} задачам` : 'часов на задачу: закрытых с датами нет';

    const grp = [
      { k: 'Готово', c: '#5CC48A', f: r => r.done },
      { k: 'Фикс в RHEL', c: '#BFE3F2', f: r => r.open && r.reasons.includes('fixed') },
      { k: 'Свой патч', c: '#7FC6E4', f: r => r.open && !r.reasons.includes('fixed') && r.reasons.includes('patch') },
      { k: 'Вне диапазона', c: '#3E9CC4', f: r => r.open && r.reasons.length === 1 && r.reasons[0] === 'range' },
      { k: 'Без решения', c: '#FF8A6B', f: r => r.open && !r.reasons.length },
    ];
    const mb = $('mixbar'), ml = $('mixleg'); mb.replaceChildren(); ml.replaceChildren();
    for (const g of grp) {
      const n = recs.filter(g.f).length; if (!n) continue;
      const sp = el('span', null, pct(n) >= 8 ? pct(n) + '%' : ''); sp.style.flexGrow = n; sp.style.background = g.c; sp.dataset.tip = `${g.k}: ${n} из ${N} (${pct(n)}%)`; mb.append(sp);
      const li = el('span'); const sw = el('i', 'sw'); sw.style.background = g.c; li.append(sw, `${g.k} `, el('b', null, `${n}`), ` · ${pct(n)}%`); ml.append(li);
    }
    const P = recs.filter(r => String(r.p).trim() === '+').length, D = recs.filter(r => String(r.d).trim() === '+').length;
    $('pd').textContent = `P отмечен у ${P}, D у ${D} из ${N} задач`;
  }

  /* statTable — из образца; колонка «Ср. срок» → «Ср. часов» по закрытым */
  function statTable(boxId, title, groups) {
    const box = $(boxId); box.replaceChildren(); const mx = Math.max(1, ...groups.map(g => g.recs.length));
    const mob = matchMedia('(max-width:560px)').matches;
    [[title, 'h l'], ['', 'h bar'], ['Всего', 'h'], ['Открыто', 'h'], ['Готово', 'h'], ['% готово', 'h'], ['Ср. часов', 'h']].forEach(([x, c]) => {
      const h = el('div', c, x);
      if (c === 'h bar') { const lg = el('div', 'cve-leg'); const a = el('span'); const i1 = el('i'); i1.style.background = css(groups[0]?.c || '--muted'); a.append(i1, 'готово'); const b = el('span'); const i2 = el('i', 'lite'); i2.style.background = css(groups[0]?.c || '--muted'); b.append(i2, 'не готово'); lg.append(a, b); h.append(lg); }
      box.append(h);
    });
    if (!groups.length) { const e = el('div', 'p', 'Нет данных'); e.style.gridColumn = '1/-1'; e.style.textAlign = 'left'; box.append(e); return; }
    for (const g of groups) {
      const n = g.recs.length, closed = g.recs.filter(r => r.done).length, opn = g.recs.filter(r => r.open).length;
      const s = Hm.summary(closedWithHours(g.recs));
      const k = el('div', 'k'); const i = el('i'); i.style.background = css(g.c); k.append(i, g.k); k.title = g.k;
      const b = el('div', 'b'); const w = el('span'); w.style.width = (n / mx * 100) + '%';
      const c1 = el('span'); c1.style.flexGrow = closed; c1.style.background = css(g.c);
      const c2 = el('span'); c2.style.flexGrow = n - closed; c2.style.background = css(g.c); c2.style.opacity = '.3';
      w.append(c1, c2); b.append(w); b.dataset.tip = `${g.k}: готово ${closed}, открыто ${opn}`;
      const cells = [k, b, el('div', 'n', String(n)), el('div', 'n', String(opn)), el('div', 'n', String(closed)), el('div', 'p', (n ? Math.round(closed / n * 100) : 0) + '%'), el('div', 'n', s.n ? f1(s.mean) + ' ч' : '—')];
      if (s.n) cells[6].dataset.tip = `Среднее по ${s.n} закрытым задачам, медиана ${f1(s.median)} ч`;
      if (mob) box.append(cells[0], ...cells.slice(2), cells[1]); else cells.forEach(x => box.append(x));
    }
  }

  function renderCuts() {
    const N = recs.length;
    const sevC = SEV.map(s => Object.assign({}, s, { recs: recs.filter(r => r.sevN === s.k) }));
    const strip = $('sevstrip'); strip.replaceChildren();
    for (const s of sevC) { if (!s.recs.length) continue; const sp = el('span'); sp.style.flexGrow = s.recs.length; sp.style.background = css(s.c); sp.dataset.tip = `${s.k}: ${s.recs.length} (${Math.round(s.recs.length / N * 100)}%)`; strip.append(sp); }
    statTable('sevrows', 'Критичность', sevC);
    const palette = ['--accent', '--c3', '--c4', '--c7', '--c5', '--c2'];
    const keys = roles.measureOrder(recs.map(r => r.measureN)).filter(k => k !== roles.NO_MEASURE);
    const mg = keys.map((k, i) => ({ k, c: palette[i % palette.length], recs: recs.filter(r => r.measureN === k) }));
    statTable('measrows', 'Мера', mg);
    const st = $('measstrip'); st.replaceChildren(); const tot = mg.reduce((a, g) => a + g.recs.length, 0);
    for (const g of mg) { const sp = el('span'); sp.style.flexGrow = g.recs.length; sp.style.background = css(g.c); sp.dataset.tip = `${g.k}: ${g.recs.length} (${tot ? Math.round(g.recs.length / tot * 100) : 0}%)`; st.append(sp); }
  }

  function pill(r) { const p = el('span', 'pill'); const i = el('i'); i.style.background = css(sevColor(r.sevN)); p.append(i, r.sevN); const td = el('td'); td.append(p); return td; }
  function cveCell(r) { const td = el('td', 'mono'); td.append(link(r.link, r.cve) || r.cve); return td; }
  function emptyRow(body, cols, text) { const tr = el('tr'); const td = el('td', 'empty', text); td.colSpan = cols; tr.append(td); body.append(tr); }
  const byCvss = (a, b) => b.cvssN - a.cvssN || a.cve.localeCompare(b.cve);

  function renderTables() {
    const att = recs.filter(r => r.attention).sort(byCvss);
    $('att-n').textContent = att.length;
    const tb = $('att-body'); tb.replaceChildren();
    if (!att.length) emptyRow(tb, 9, 'Задач со статусом «Есть проблема» или «Нужна доработка» нет');
    for (const r of att) {
      const c6 = el('td', 'mono'); c6.append(link(r.rhsa, r.rhnvr || r.rhsa.split('/').pop()) || r.rhnvr || '—');
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), el('td', null, r.rstate || '—'), c6, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      tb.append(tr);
    }

    const ready = recs.filter(r => r.open && r.reasons.length);
    const why = [['Фикс в RHEL (RHEL state = Fixed)', 'fixed', '--ok'], ['Есть свой патч (P = +)', 'patch', '--accent'], ['Версия вне уязвимого диапазона (D = +)', 'range', '--sev-none']];
    hbars('close-why', why.map(([l, k, c]) => { const n = ready.filter(r => r.reasons.includes(k)).length; return { label: l, n, segs: [{ n, color: c, name: '' }] }; })
      .concat([{ label: 'Всего задач, без повторов', n: ready.length, segs: [{ n: ready.length, color: '--fg', name: '' }] }]), Math.max(1, ready.length));
    $('close-n').textContent = ready.length;
    const cb = $('close-body'); cb.replaceChildren();
    if (!ready.length) emptyRow(cb, 8, 'Открытых задач с готовым решением нет');
    for (const r of [...ready].sort(byCvss)) {
      const c5 = el('td'); c5.style.display = 'flex'; c5.style.gap = '6px';
      if (r.reasons.includes('fixed')) c5.append(link(r.rhsa, r.rhnvr || 'RHEL Fixed', 'pill') || el('span', 'pill', r.rhnvr || 'RHEL Fixed'));
      if (r.reasons.includes('patch')) c5.append(el('span', 'pill', 'свой патч'));
      if (r.reasons.includes('range')) c5.append(el('span', 'pill', 'вне диапазона'));
      const tr = el('tr');
      tr.append(cveCell(r), el('td', null, r.comp), pill(r), el('td', 'num', r.cvss || '—'), c5, el('td', null, r.status || '—'), el('td', null, r.dev || 'не назначен'), el('td', 'num', hoursText(r)));
      cb.append(tr);
    }
  }

  function renderBars() {
    const comps = count(recs, r => r.comp).slice(0, 12);
    hbars('components', comps.map(([c, n]) => ({ label: c, n, segs: SEV.map(s => ({ name: s.k, color: s.c, n: recs.filter(r => r.comp === c && r.sevN === s.k).length })) })), comps.length ? comps[0][1] : 1);
    legend('compleg', SEV);
    const rs = count(recs, r => r.rstate || 'не указано');
    const rsColor = k => ({ fixed: '--ok', affected: '--bad', 'under investigation': '--warn', 'fix deferred': '--warn' })[k.toLowerCase()] || '--sev-none';
    hbars('rhel', rs.map(([k, n]) => ({ label: k, n, segs: [{ n, color: rsColor(k), name: '' }] })), rs.length ? rs[0][1] : 1);
    const ds = count(recs, statusKey);
    const dsColor = k => roleColor(recs.find(r => statusKey(r) === k));
    hbars('devstatus', ds.map(([k, n]) => ({ label: k, n, segs: [{ n, color: dsColor(k), name: '' }] })), ds.length ? ds[0][1] : 1);
    legend('weekleg', SEV);
    stackChart($('weeks'), weeksOf(recs.map(r => [r.tdateD, r.sevN]), SEV), SEV, 'поступило');
  }

  function renderPace() {
    const WIN = +$('pace-win').value || 14;
    const R = pace.rates(recs, AS_OF, WIN);
    const ready = recs.filter(r => r.open && r.reasons.length).length;
    const fc = $('forecast'); fc.replaceChildren();
    $('pace-sub').textContent = `На ${fmt(AS_OF)} · темп за ${days(WIN)}`;
    $('pace-note').textContent = `Точка отсчёта — дата отчёта (${fmt(AS_OF)}). Закрытой считается задача со статусом «Готов» и заполненным End date. Дни календарные. До сканфриза новые задачи прибывают в текущем темпе.`;
    $('p-in').textContent = f1(R.inR);
    $('p-out').textContent = f1(R.outR);
    const pn = $('p-net'); pn.textContent = (R.net > 0 ? '−' : R.net < 0 ? '+' : '') + f1(Math.abs(R.net)); pn.className = 'v ' + (R.net > 0 ? 'ok' : R.net < 0 ? 'bad' : '');
    $('p-net-l').textContent = R.net > 0 ? 'бэклог сокращается в день' : R.net < 0 ? 'бэклог растёт в день' : 'бэклог не меняется';
    $('p-open').textContent = R.open;
    const sd = $('stop-date'), td = $('target-date');
    if (!sd.value) sd.value = LS.get('cve.stopDate');
    if (!td.value) td.value = LS.get('cve.targetDate') || dates.isoOf(AS_OF + 30);
    const stop = dates.dayOf(sd.value), target = dates.dayOf(td.value);
    /* row — из образца, дни вместо миллисекунд */
    const row = (title, d, sub, main, n) => {
      const r = el('div', main ? 'fc-main' : 'fc-row');
      const dt = d === 0 ? el('div', 'd', 'уже 0') : d === null ? el('div', 'd bad', 'не завершится') : el('div', 'd', fmt(AS_OF + d));
      const meta = el('div', 's', (d ? `${n} задач · ≈ ${days(d)}. ` : '') + sub);
      if (main) r.append(el('div', 'e', title), dt, meta); else r.append(el('div', 't', title), dt, meta);
      fc.append(r);
    };
    if (stop !== null) {
      const inflowDays = Math.max(0, stop - AS_OF - 1);
      row(`Сканфриз ${fmt(stop)}`, pace.simulate(R.open, R.inR, R.outR, AS_OF, stop), `До этой даты придёт ещё ≈ ${Math.round(R.inR * inflowDays)}, дальше только закрываем по ${f1(R.outR)} в день.`, true, R.open);
    } else {
      row('При текущем темпе, без сканфриза', R.net > 0 ? pace.simulate(R.open, R.inR, R.outR, AS_OF) : null, R.net > 0 ? 'Новые задачи продолжают поступать в том же темпе.' : 'Приходит не меньше, чем закрывается. Укажите дату сканфриза.', true, R.open);
    }
    row('Если новые перестанут поступать сегодня', pace.simulate(R.open, R.inR, R.outR, AS_OF, null), `По ${f1(R.outR)} в день.`, false, R.open);
    row('Без задач с готовым решением', pace.simulate(R.open - ready, R.inR, R.outR, AS_OF, stop === null ? null : stop), `Если ${ready} задач с готовым решением закрыть сразу.` + (stop === null ? ' Без новых.' : ` С новыми до ${fmt(stop)}.`), false, R.open - ready);
    if (target !== null) {
      const r = el('div', 'fc-row need'); r.append(el('div', 't', `Закончить к ${fmt(target)}`));
      const nd = pace.need(R.open, R.inR, AS_OF, stop, target);
      if (nd === null) r.append(el('div', 'd bad', 'дата прошла'), el('div', 's', 'Выберите дату позже ' + fmt(AS_OF) + '.'));
      else r.append(el('div', 'd', `${f1(nd.perDay)}/день`), el('div', 's', `Нужно закрывать в день. ${days(nd.left)}, с учётом ≈ ${Math.round(nd.incoming)} новых. ${R.outR ? (nd.perDay <= R.outR ? 'Текущего темпа хватает.' : `В ${f1(nd.perDay / R.outR)} раза больше текущего.`) : ''}`));
      fc.append(r);
    }
    drawPace(FIRST === null ? [] : pace.daily(recs, FIRST, AS_OF), AS_OF - WIN);
    return WIN;
  }

  function renderPeople(WIN) {
    const devs = count(recs, r => r.devKey);
    const devColor = new Map(devs.map(([d], i) => [d, i < 8 ? `--c${i + 1}` : '--sev-none']));
    legend('statleg', [{ k: 'Готово', c: '--ok' }, { k: 'В работе', c: '--accent' }, { k: 'Ожидает ревью', c: '--c7' }, { k: 'На паузе', c: '--warn' }, { k: 'Есть проблема / Нужна доработка', c: '--bad' }]);
    const doneKeys = recs.filter(r => r.taken && r.done);
    const measKeys = roles.measureOrder(doneKeys.map(r => r.measureN));
    const ppl = $('people'); ppl.replaceChildren();
    const kvRow = (box, label, n, max, color, tipText) => {
      box.append(el('span', 'k', label));
      const b = el('span', 'b'); const s = el('span'); s.style.width = (n / max * 100) + '%'; s.style.background = css(color); b.append(s); b.dataset.tip = tipText; box.append(b);
      box.append(el('span', 'n', String(n)));
    };
    for (const [d, n] of devs) {
      const mine = recs.filter(r => r.devKey === d), done = mine.filter(r => r.done), col = devColor.get(d);
      const card = el('article', 'dev'); card.style.setProperty('--dc', css(col));
      const c1 = el('div');
      const h = el('h3'); const sw = el('i'); sw.style.background = css(col); h.append(sw, d); c1.append(h);
      const big = el('div', 'big', String(n)); big.append(el('small', null, 'задач назначено')); c1.append(big);
      const cnt = { g: done.length, rv: mine.filter(r => r.working && r.review).length, u: mine.filter(r => r.working && r.paused).length, p: mine.filter(r => r.working && r.attention).length };
      cnt.w = mine.filter(r => r.working).length - cnt.rv - cnt.u - cnt.p;
      const bar = el('div', 'pbar');
      [[cnt.g, '--ok', 'Готово'], [cnt.w, '--accent', 'В работе'], [cnt.rv, '--c7', 'Ожидает ревью'], [cnt.u, '--warn', 'На паузе'], [cnt.p, '--bad', 'Проблемы']].forEach(([k, c, s]) => { if (!k) return; const sp = el('span'); sp.style.flexGrow = k; sp.style.background = css(c); sp.dataset.tip = `${d} · ${s}: ${k}`; bar.append(sp); });
      c1.append(bar);
      const load = el('div', 'load');
      const li = (lab, v, cls) => { const s = el('span'); s.append(lab + ' ', el('b', cls || null, String(v))); load.append(s); };
      li('готово', cnt.g); li('в работе', cnt.w); li('ревью', cnt.rv); li('пауза', cnt.u); li('проблемы', cnt.p, cnt.p ? 'bad' : null);
      const hanging = (H.load.get(d) && H.load.get(d).get(AS_OF)) || 0;
      li('висит сейчас', hanging ? `${hanging}, по ${f1(Hm.HOURS_PER_DAY / hanging)} ч` : '0');
      c1.append(load);
      card.append(c1);

      const c2 = el('div'); c2.append(el('div', 'cap', `Сделано по критичности · ${done.length}`));
      const kv2 = el('div', 'kv'); const maxS = Math.max(1, ...SEV.map(s => done.filter(r => r.sevN === s.k).length));
      SEV.forEach(s => { const v = done.filter(r => r.sevN === s.k).length; if (v) kvRow(kv2, s.k, v, maxS, s.c, `${d} · ${s.k}: ${v}`); });
      c2.append(kv2);
      const c3 = el('div'); c3.append(el('div', 'cap', `Сделано по принятой мере · ${done.length}`));
      const kv3 = el('div', 'kv'); const maxM = Math.max(1, ...measKeys.map(k => done.filter(r => r.measureN === k).length));
      measKeys.forEach(k => { const v = done.filter(r => r.measureN === k).length; if (v) kvRow(kv3, k, v, maxM, col, `${d} · ${k}: ${v}`); });
      c3.append(kv3);
      card.append(c2, c3);

      const c4 = el('div'); c4.append(el('div', 'cap', 'Скорость'));
      const s = Hm.summary(closedWithHours(mine));
      const closedDays = done.map(r => r.endD).filter(x => x !== null && x <= AS_OF);
      const work = H.workdays.get(d) || new Set();
      const recent = Hm.rate(closedDays, work, AS_OF - WIN + 1, AS_OF);
      const overall = Hm.rate(closedDays, work, -Infinity, AS_OF);
      const sp = el('div', 'speed');
      const sv = (v, l, t) => { const x = el('div'); x.append(el('span', 'v', v), el('span', 'l', l)); if (t) x.dataset.tip = t; sp.append(x); };
      sv(s.n ? f1(s.mean) : '—', s.n ? `ч на задачу, медиана ${f1(s.median)}` : 'ч на задачу', `По ${s.n} закрытым задачам`);
      sv(recent === null ? '—' : f1(recent), `задач за рабочий день, ${days(WIN)}`, 'Закрыто за окно / рабочих дней разработчика в окне');
      sv(overall === null ? '—' : f1(overall), 'задач за рабочий день, всего', `${closedDays.length} задач за ${work.size} рабочих дней`);
      c4.append(sp);
      const starts = mine.map(r => r.startD).filter(x => x !== null && x <= AS_OF);
      if (starts.length) {
        const sh = el('div', 'tl spark-tl'); c4.append(sh);
        const per = new Map(); closedDays.forEach(x => per.set(x, (per.get(x) || 0) + 1));
        card.append(c4); ppl.append(card);
        spark(sh, per, Math.min(...starts), col, d);
        c4.append(el('div', 'cap', `закрыто по дням с ${fmt(Math.min(...starts))} по ${fmt(AS_OF)}`));
        continue;
      }
      card.append(c4); ppl.append(card);
    }
    const names = [...devColor.keys()];
    const cats = names.slice(0, 8).map(k => ({ k, c: devColor.get(k) }));
    if (names.length > 8) cats.push({ k: 'Другие', c: '--sev-none' });
    legend('burnleg', cats);
    stackChart($('burn'), weeksOf(recs.filter(r => r.done && r.taken).map(r => [r.endD, names.indexOf(r.devKey) < 8 ? r.devKey : 'Другие']), cats), cats, 'закрыто');
  }

  function renderAnomalies() {
    const label = { tdate: 'Task date', start: 'Start date', end: 'End date', fixdate: 'Fix date' };
    const items = H.anomalies.map(a => ({ r: recs[a.index], why: Hm.REASONS[a.reason] }));
    const listed = new Set(H.anomalies.map(a => a.index));
    recs.forEach(r => { if (!listed.has(r.i) && r.bad && r.bad.length) items.push({ r, why: 'не разобрана дата: ' + r.bad.map(k => label[k]).join(', ') }); });
    items.sort((a, b) => a.r.row - b.r.row);
    $('anom-n').textContent = items.length;
    const notes = $('anom-notes'); notes.replaceChildren();
    if (DATA.meta.skipped) notes.append(el('li', null, `Строк без CVE ID пропущено: ${DATA.meta.skipped}.`));
    if (DATA.meta.missing.length) notes.append(el('li', null, `Нет колонок (читаются пустыми): ${DATA.meta.missing.join(', ')}.`));
    const body = $('anom-body'); body.replaceChildren();
    if (!items.length) emptyRow(body, 8, 'Аномалий нет');
    for (const { r, why } of items) {
      const tr = el('tr');
      tr.append(el('td', 'num', String(r.row)), cveCell(r), el('td', null, r.comp), el('td', null, r.dev || '—'), el('td', null, r.status || '—'), el('td', null, r.start || '—'), el('td', null, r.end || '—'), el('td', null, why));
      body.append(tr);
    }
  }

  function render() {
    renderHead(); renderCuts(); renderTables(); renderBars();
    const WIN = renderPace();
    renderPeople(WIN); renderAnomalies();
  }

  ['stop-date', 'target-date', 'pace-win'].forEach(id => $(id).addEventListener('change', () => {
    LS.set('cve.stopDate', $('stop-date').value); LS.set('cve.targetDate', $('target-date').value);
    render();
  }));
  let rT; addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(render, 150); });
  render();
}());
```

Проверить, что в `summary.css` образца есть классы, которыми пользуется
код (`fc-main`, `fc-row`, `need`, `mini`, `pc`, `mixbar`, `sevstrip`,
`cve-rows`, `kv`, `speed`, `load`, `pbar`, `mono`, `num`):

```bash
for c in fc-main fc-row need mini pc mixbar sevstrip cve-rows kv speed load pbar mono num; do
  grep -q "\.$c\b" cvesummary/assets/summary.css || echo "нет класса $c"
done
```

Expected: без вывода (иначе — найти правило в образце и перенести).

- [ ] **Step 3: тесты и синтаксис**

Run: `python3 -m unittest discover -s tests -v && node --test tests/js/ && node --check cvesummary/assets/js/render.js`
Expected: OK, `fail 0`, без ошибок синтаксиса.

- [ ] **Step 4: проверка в браузере (playwright)**

```bash
python3 -m tests.example "$TMPDIR/пример.xlsx"
python3 -m cvesummary "$TMPDIR/пример.xlsx" --as-of 2026-10-19
```

(`$TMPDIR` — каталог scratchpad сессии.) Открыть
`file://$TMPDIR/пример.html` через `browser_navigate` и проверить:

1. `browser_console_messages` — ошибок нет.
2. `browser_snapshot` — заполнены: «Всего задач» = 100; плитки «Состояние», «Можно закрыть», «Риски и темп» с числами; «часов на задачу» — число; таблицы «Требует внимания», «Можно закрыть»; карточки разработчиков (5); блок «Аномалии» с двумя строками (строки листа 10 и 11 — номера 7 и 8 в `example.rows` плюс две строки шапки и группировки).
3. `browser_evaluate`:
   ```js
   () => [...document.querySelectorAll('.tl-scroll')].map(b => ({ w: b.scrollWidth, c: b.clientWidth, left: b.scrollLeft }))
   ```
   у дневного графика (`#pace-chart`) при ширине окна 800 px
   `scrollWidth > clientWidth` и `scrollLeft + clientWidth ≈ scrollWidth`
   (стоит в конце); у `#pace-chart` класс `fade-l`, без `fade-r`.
4. `browser_resize` 390×844 →
   `browser_evaluate(() => document.documentElement.scrollWidth <= innerWidth)` — `true`.
5. `browser_emulate_media` с `colorScheme: 'dark'` → `browser_take_screenshot` — тёмная тема читается.
6. Таблица из одних обязательных колонок (как в `test_only_required_columns`) — страница открывается без ошибок в консоли, «часов на задачу: закрытых с датами нет», прогноз «не завершится».

Найденное — чинить в `render.js`/`summary.css` и повторять проверку.

- [ ] **Step 5: commit**

```bash
git add tools/cvesummary/cvesummary/assets tools/cvesummary/tests/example.py tools/cvesummary/tests/test_example.py
git commit -m "feat(cvesummary): render the summary blocks, hours and scrollable time charts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: документы тулзы и репозитория

**Files:**
- Create: `README.md`, `TODO.md`, `CHANGELOG.md` (в `tools/cvesummary/`)
- Modify: `../../README.md` (таблица тулз), `../../TODO.md` (индекс списков), `../../CHANGELOG.md` (`[Unreleased]`)

- [ ] **Step 1: `README.md` тулзы**

Разделы и содержание (текст писать для людей, по-русски):

1. Заголовок `# cvesummary` и абзац: что делает (xlsx таблицы процесса →
   одна HTML-страница сводки: состояние, «можно закрыть», риски, разрезы
   по критичности и мерам, темп и прогноз со сканфризом, карточки
   разработчиков с часами, аномалии) и когда применять (показать, где
   встала работа, на ком сколько висит, успеваем ли к релизу).
2. «Версия» — `1.0.0`, лежит в `cvesummary/__init__.py`, выводится
   `python3 -m cvesummary --version`.
3. «Требования» — Python 3.9+, только стандартная библиотека; для
   страницы — браузер; шрифты грузятся с Google Fonts, без сети страница
   открывается на запасных шрифтах.
4. «Запуск» — три примера: `python3 -m cvesummary таблица.xlsx`,
   `-o сводка.html`, `--as-of 2026-10-19`; что без `-o` страница ложится
   рядом с таблицей и перезаписывается; коды возврата 0 и 2; что пишется в
   журнал.
5. «Что читается из xlsx» — первый лист; шапка — первая строка с `CVE ID`;
   колонки по имени (регистр, пробелы, переносы); обязательные и
   необязательные; `-` и пусто; даты (текст `дд.мм.гггг`, `гггг-мм-дд`,
   дата Excel, серийный номер); `Task state` не читается.
6. «Роли статусов» — таблица из спеки.
7. «Часы» — правило словами и пример из спеки (таблица 16/32/8) плюс пример
   «первая задача — 12 ч»; где часы используются; что попадает в аномалии.
8. «Прогноз» — в задачах: окно 7/14/30, сканфриз, целевая дата,
   запоминаются в браузере.
9. «Графики по времени» — весь период, листаются внутри карточки
   перетаскиванием, Shift+колесом, тачпадом, пальцем.
10. «Разработка» — `python3 -m unittest discover -s tests -v`,
    `node --test tests/js/`, пример `python3 -m tests.example пример.xlsx`;
    раскладка модулей таблицей; ссылка на спеку
    `docs/superpowers/specs/2026-10-19-cvesummary-design.md`; соглашения —
    `../../CLAUDE.md`.

- [ ] **Step 2: `TODO.md` тулзы**

```markdown
# TODO — cvesummary

Задачи по этой тулзе: баги, фичи, технический долг, идеи. Пишем сюда оба —
и пользователь, и Claude.

> **Правило работы со списком.** Этот файл — только хранилище задач.
> Claude не берёт отсюда ничего в работу по собственной инициативе: ни при
> «заодно поправь», ни когда задача выглядит тривиальной, ни когда она рядом
> с тем, что уже правится. Работа над пунктом начинается только по явному
> указанию пользователя на конкретный пункт.

Формат пункта — код `ТИП-П-ГГММ-NN`, строки «Область», «Источник» и
«Приоритет», порядок внутри раздела — в [`../../CLAUDE.md`](../../CLAUDE.md),
«Список задач». Пути — относительно каталога тулзы.

Последние выданные номера (обновляются при добавлении пункта): пока нет.

## Баги

_Пусто._

## Фичи

_Пусто._

## Технический долг

_Пусто._

## Идеи

_Пусто._
```

- [ ] **Step 3: `CHANGELOG.md` тулзы**

```markdown
# Changelog — cvesummary

Изменения тулзы `cvesummary`, от свежих к старым. Версия тулзы независима от
версии репозитория.

## 1.0.0 — 2026-10-19

Первая версия. xlsx таблицы процесса устранения CVE превращается в одну
HTML-страницу сводки: состояние задач по статусам разработчиков, задачи,
которые можно закрыть (Fixed в RHEL, свой патч, версия вне диапазона),
риски, разрезы по критичности и принятым мерам, темп и прогноз со
сканфризом и целевой датой, карточки разработчиков и аномалии в данных.
Скорость считается в часах: 8 часов рабочего дня разработчика делятся
между задачами, которые на нём висят. Графики по времени показывают весь
период и листаются внутри карточки. Разбор xlsx — свой, без openpyxl.
```

- [ ] **Step 4: корневые документы**

`../../README.md` — строка в таблицу «Тулзы» перед `dashboard` (по алфавиту):

```markdown
| [cvesummary](tools/cvesummary/) | Сводка по CVE: из xlsx таблицы процесса устранения уязвимостей собирает одну HTML-страницу — состояние задач, что можно закрыть, риски, темп и прогноз к релизу, нагрузка и скорость разработчиков в часах. |
```

`../../TODO.md` — в «Списки тулз» первой строкой (по алфавиту):

```markdown
- [`tools/cvesummary/TODO.md`](tools/cvesummary/TODO.md)
```

`../../CHANGELOG.md` — под `## [Unreleased]`:

```markdown

### Добавлено

- `cvesummary` (1.0.0): сводка по CVE — из xlsx таблицы процесса
  собирается одна HTML-страница: состояние задач, что можно закрыть, риски,
  разрезы по критичности и мерам, темп и прогноз со сканфризом, карточки
  разработчиков со скоростью в часах и аномалии в данных.
```

- [ ] **Step 5: корневые проверки и тесты**

Run (из корня репозитория): блок проверок из `CLAUDE.md`, «Проверки».
Expected: без вывода.

Run (из `tools/cvesummary/`): `python3 -m unittest discover -s tests -v && node --test tests/js/`
Expected: OK, `fail 0`.

- [ ] **Step 6: commit**

```bash
git add tools/cvesummary/README.md tools/cvesummary/TODO.md tools/cvesummary/CHANGELOG.md README.md TODO.md CHANGELOG.md
git commit -m "docs(cvesummary): add readme, todo and changelog

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-Review

- **Покрытие спеки:** запуск и коды — Task 7; чтение xlsx — Task 1; шапка,
  колонки, значения, даты — Task 2; данные в странице и экранирование —
  Task 6; роли, меры, критичность — Task 3; часы — Task 4; темп и прогноз
  — Task 5 (расчёт) и Task 8 (блок); блоки страницы, аномалии, пояснения —
  Task 6 (разметка) и Task 8; графики по времени и прокрутка — Task 5
  (`timeline`), Task 6 (CSS), Task 8 (`frame`), проверка — Task 8 Step 4;
  журнал — Task 7; раскладка — File Structure; тесты — в каждой задаче;
  документы — Task 9.
- **Имена между задачами:** `CS.hours.compute(...).load/.workdays/.anomalies`,
  `Hm.summary`, `Hm.rate`, `pace.rates/simulate/need/daily`,
  `timeline.layout/edges/attach/sync`, `roles.devOf/closeReasons/sevOrder/measureOrder`
  — одинаковы в Task 3–5 и в `render.js` Task 8; ключи строк (`dev`,
  `status`, `start`, `end`, `tdate`, `bad`, …) — из `table.FIELDS` Task 2.
- **Review Focus** — у каждой строки есть тест в своей задаче (Task 1, 2,
  4, 5, 7).
