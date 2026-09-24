# vulnsheet: обновление существующей таблицы — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Помимо построения таблицы с нуля из блоков (режим 1), `vulnsheet` умеет обновлять существующую таблицу. Режим 2 обновляет только данные koji и VEX. Режим 3 синхронизирует таблицу с блоками: совпавшие строки обновляются, пропавшие помечаются `Missing`, новые дописываются в конец. Ручные колонки в обоих режимах сохраняются.

**Architecture:**
- `report.py` описывает группы колонок: срезы и индексы.
- Новый `table.py` читает и проверяет прежний CSV.
- Новый `merge.py` — чистые функции без файлов и сети. `pairs()` говорит, какие пары (CVE, компонент) нужны. `build`/`refresh`/`sync` собирают итоговые строки из прежней таблицы, задач и ответов источников (`Fresh`).
- `cli.py` получает флаги `--blocks`/`--table` вместо позиционного входа, выбирает режим, опрашивает koji и VEX по нужным парам, ведёт журнал и выставляет код возврата.

**Tech Stack:** Python 3.9+, стандартная библиотека (`csv`), `koji`, PyYAML (только при конфиге), `unittest`.

**Spec:** `tools/vulnsheet/docs/superpowers/specs/2026-09-24-vulnsheet-update-modes-design.md` (дополняет `2026-09-24-vulnsheet-design.md` и `2026-09-24-vulnsheet-config-design.md`; где расходятся — действует он).

## Global Constraints

- Все пути ниже — от корня репозитория. Тесты запускаются из `tools/vulnsheet/` командой `python3 -m unittest discover -s tests -v`. До начала работ тестов 133, все зелёные.
- Python 3.9+: без `X | None` и `match`, аннотации через `typing`.
- Зависимости:
  - стандартная библиотека;
  - `koji` — только внутри `kojiclient.connect`;
  - PyYAML — только внутри `config`.

  Новых зависимостей нет.
- koji — только чтение: `getTag` и `getLatestBuilds`. Новых вызовов koji нет.
- Формат таблицы:
  - `;`, UTF-8, 20 колонок `report.COLUMNS`;
  - пустая ячейка `-`, даты `dd.mm.yyyy`;
  - ячейки прежней таблицы переносятся дословно.
- Маркер пропавшей задачи — ровно `Missing`.
- Тройка сопоставления — (Task ID, CVE ID, Компонент):
  - `Task ID` и `Компонент` обрезаются по краям;
  - `CVE ID` обрезается и переводится в верхний регистр.
- Без откатов по RHEL и стримам, как раньше: `vex_streams` действует во всех режимах по компоненту строки.
- Режим определяется флагами:
  - только `--blocks` — 1;
  - только `--table` — 2;
  - оба — 3;
  - ни одного — ошибка argparse, код 2;
  - `--table -` — тоже ошибка argparse.
- Коды возврата: `0`, `1` (CSV записан, но есть битые блоки, `fetch error`, koji `ERROR` или строки, по которым нечего спрашивать), `2` (фатально). `Missing` сам по себе кода 1 не даёт.
- Версия тулзы остаётся `1.0.0`, потому что тулза не выпущена. CHANGELOG-и дополняются, новая версия не заводится.
- Язык:
  - логи, сообщения и комментарии в коде — на русском;
  - коммиты — на английском в Conventional Commits со скоупом `vulnsheet`, с футером `Co-Authored-By:`, где названа модель, которая писала коммит.
- Слова «cve» нет в именах файлов, модулей и тестов.
- Работа идёт в ветке `feature/vulnsheet`.
  - `.tmp/` и `task.md` в корне не трогать и не коммитить.
  - `__pycache__` и случайные `*.rejected.txt` не коммитить.

## Review Focus

1. **`-o` указывает на тот же файл, что `--table`** (обновление на месте). Ожидается, что таблица будет прочитана целиком до записи и заменена атомарно; при сбое прогона прежняя таблица остаётся целой. Тесты: `test_refresh_in_place` и `test_broken_table_is_fatal_and_keeps_output` (Task 3).
2. **Сбой сети при повторном прогоне.** VEX или koji не ответили, а в строке уже хорошие данные. Ожидается, что прежние значения останутся, а код будет 1. Тесты: `test_koji_error_keeps_previous_nvr`, `test_fetch_error_keeps_previous_vex_group` и `test_failures_keep_old_values_but_new_row_gets_markers` (Task 2), `test_refresh_keeps_previous_vex_on_fetch_error` (Task 3).
3. **Таблица побывала в редакторе таблиц.** В ней BOM, `\r\n`, ячейка с `;` или переводом строки в кавычках. Ожидается, что всё прочитается и ячейки сохранятся дословно. Тесты: `test_bom_and_crlf` и `test_quoted_cell_with_separator_and_newline_is_kept` (Task 1).
4. **Строка, которую человек добавил руками** (в `CVE ID` стоит `-`, компонент пустой). Ожидается, что строка останется как есть, без `Missing` и без падения, с предупреждением и кодом 1. Тесты: `test_row_without_cve_or_component_is_left_as_is` и `test_row_with_nothing_to_ask_is_not_marked_missing` (Task 2), `test_refresh_row_without_cve_is_partial` (Task 3).
5. **Пустые блоки в режиме 3.** Файл с блоками пустой или не тот. Ожидается фатальная ошибка, а не таблица, где все строки молча стали `Missing`. Тест: `test_sync_with_empty_blocks_is_fatal` (Task 3).

---

## File Structure

```text
tools/vulnsheet/
├── vulnsheet/
│   ├── report.py      # Task 1 — группы колонок, индексы, MISSING
│   ├── table.py       # Task 1 — новый: чтение прежней таблицы
│   ├── merge.py       # Task 2 — новый: слияние, чистые функции
│   └── cli.py         # Task 3 — --blocks/--table, режимы, журнал
├── tests/
│   ├── test_report.py # Task 1 — группы
│   ├── test_table.py  # Task 1 — новый
│   ├── test_merge.py  # Task 2 — новый
│   └── test_cli.py    # Task 3 — --blocks вместо позиционного, режимы 2 и 3
├── README.md          # Task 4
└── CHANGELOG.md       # Task 4
CHANGELOG.md           # Task 4 — строка vulnsheet в [Unreleased]
```

---

### Task 1: группы колонок и чтение таблицы

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/report.py` (после `COLUMNS`)
- Create: `tools/vulnsheet/vulnsheet/table.py`
- Modify: `tools/vulnsheet/tests/test_report.py`
- Create: `tools/vulnsheet/tests/test_table.py`

**Interfaces:**
- Consumes: `report.COLUMNS`, `report.row(task, nvr, verdict) -> List[str]` (как есть).
- Produces:
  - `report.MISSING = "Missing"`;
  - срезы `report.DEVELOPER`, `TASK`, `KOJI`, `VEX`, `LINK`, `COMMENT`;
  - индексы `report.TASK_ID`, `CVE_ID`, `TASK_STATE`, `TASK_DATE`, `ASSIGNEE`, `COMPONENT`, `SL_NVR`, `RHEL_STATE`;
  - `table.TableError(Exception)`;
  - `table.Record(NamedTuple)` с полями `number: int` (номер записи в файле, заголовок — 1) и `cells: List[str]`;
  - `table.read(path: str) -> List[Record]` — только строки данных, без заголовка.

- [ ] **Step 1: Write the failing tests**

В `tools/vulnsheet/tests/test_report.py` поменять импорт:

```python
from vulnsheet import report
from vulnsheet.report import COLUMNS, format_date, row, write
```

и дописать в конец файла:

```python
class GroupsTest(unittest.TestCase):
    GROUPS = [report.DEVELOPER, report.TASK, report.KOJI, report.VEX,
              report.LINK, report.COMMENT]

    def test_groups_cover_all_columns_in_order(self):
        self.assertEqual(sum((COLUMNS[group] for group in self.GROUPS), []), COLUMNS)

    def test_group_contents(self):
        self.assertEqual(COLUMNS[report.DEVELOPER], [
            "Разработчик", "Статус", "Start date", "End date", "Принятая мера"])
        self.assertEqual(COLUMNS[report.TASK], [
            "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент"])
        self.assertEqual(COLUMNS[report.KOJI], ["SL NVR (latest build)"])
        self.assertEqual(COLUMNS[report.VEX], [
            "RHEL NVR (if fixed)", "Fix date", "RHEL state", "RHEL severity",
            "RHEL CVSS", "Advisory (RHSA)"])
        self.assertEqual(COLUMNS[report.LINK], ["CVE Link"])
        self.assertEqual(COLUMNS[report.COMMENT], ["Комментарий"])

    def test_row_fields_land_on_named_indices(self):
        cells = row(TASK, "vim-1", Verdict(state="Affected"))
        indices = [report.TASK_ID, report.CVE_ID, report.TASK_STATE, report.TASK_DATE,
                   report.ASSIGNEE, report.COMPONENT, report.SL_NVR, report.RHEL_STATE]
        self.assertEqual([cells[i] for i in indices], [
            "TASKID-181229", "CVE-2026-73070", "Отменен", "22.09.2026", "КМ", "vim",
            "vim-1", "Affected"])

    def test_missing_marker(self):
        self.assertEqual(report.MISSING, "Missing")
```

Создать `tools/vulnsheet/tests/test_table.py`:

```python
import csv
import io
import os
import shutil
import tempfile
import unittest

from vulnsheet.report import COLUMNS
from vulnsheet.table import Record, TableError, read

HEADER = ";".join(COLUMNS)
ROW = ["Иванов", "В работе", "01.09.2026", "-", "-",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       "https://access.redhat.com/security/cve/CVE-2026-0001", "-"]
LINE = ";".join(ROW)


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)

    def write(self, text="", data=None):
        path = os.path.join(self.room, "old.csv")
        with open(path, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        return path

    def assertRejected(self, needle, text="", data=None):
        with self.assertRaises(TableError) as caught:
            read(self.write(text, data))
        self.assertIn(needle, str(caught.exception))
        return caught.exception

    def test_rows_come_back_verbatim_with_record_numbers(self):
        self.assertEqual(read(self.write(HEADER + "\n" + LINE + "\n")), [Record(2, ROW)])

    def test_bom_and_crlf(self):
        data = ("﻿" + HEADER + "\r\n" + LINE + "\r\n").encode("utf-8")
        self.assertEqual(read(self.write(data=data)), [Record(2, ROW)])

    def test_quoted_cell_with_separator_and_newline_is_kept(self):
        cells = list(ROW)
        cells[-1] = "ждём; апстрим\nи RHSA"
        buffer = io.StringIO()
        csv.writer(buffer, delimiter=";", lineterminator="\n").writerow(cells)
        rows = read(self.write(HEADER + "\n" + buffer.getvalue()))
        self.assertEqual(rows, [Record(2, cells)])

    def test_blank_records_are_skipped_but_counted(self):
        self.assertEqual(read(self.write(HEADER + "\n\n" + LINE + "\n")), [Record(3, ROW)])

    def test_header_only_is_an_empty_table(self):
        self.assertEqual(read(self.write(HEADER + "\n")), [])

    def test_bad_tables(self):
        cases = [
            ("", "нет заголовка"),
            ("\n \n", "нет заголовка"),
            (HEADER.replace("Task ID", "Task") + "\n", "заголовок"),
            (HEADER + "\n" + ";".join(ROW[:19]) + "\n", "запись 2: ячеек 19"),
            (HEADER + "\n" + LINE + ";x\n", "запись 2: ячеек 21"),
        ]
        for text, needle in cases:
            with self.subTest(text=text):
                self.assertRejected(needle, text)

    def test_error_names_the_file(self):
        self.assertIn("old.csv", str(self.assertRejected("заголовок", "a;b\n")))

    def test_not_utf8(self):
        self.assertRejected("UTF-8", data=(HEADER + "\n").encode("cp1251"))

    def test_missing_file(self):
        with self.assertRaises(TableError) as caught:
            read(os.path.join(self.room, "нет.csv"))
        self.assertIn("не читается", str(caught.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_report tests.test_table -v`
Expected: FAIL. `test_table` не импортируется (`No module named 'vulnsheet.table'`), в `GroupsTest` — `AttributeError: module 'vulnsheet.report' has no attribute 'DEVELOPER'`.

- [ ] **Step 3: Implement**

В `tools/vulnsheet/vulnsheet/report.py` сразу после списка `COLUMNS` вставить:

```python
MISSING = "Missing"  # Task state строки, чьей задачи больше нет в блоках

# Группы колонок для режимов обновления: что в каком режиме откуда берётся,
# см. docs/superpowers/specs/2026-09-24-vulnsheet-update-modes-design.md.
DEVELOPER = slice(0, 5)   # Разработчик … Принятая мера
TASK = slice(5, 11)       # Task ID … Компонент
KOJI = slice(11, 12)      # SL NVR
VEX = slice(12, 18)       # RHEL NVR … Advisory
LINK = slice(18, 19)      # CVE Link
COMMENT = slice(19, 20)   # Комментарий

TASK_ID = COLUMNS.index("Task ID")
CVE_ID = COLUMNS.index("CVE ID")
TASK_STATE = COLUMNS.index("Task state")
TASK_DATE = COLUMNS.index("Task date")
ASSIGNEE = COLUMNS.index("Исполнитель")
COMPONENT = COLUMNS.index("Компонент")
SL_NVR = COLUMNS.index("SL NVR (latest build)")
RHEL_STATE = COLUMNS.index("RHEL state")
```

Создать `tools/vulnsheet/vulnsheet/table.py`:

```python
"""Чтение прежней таблицы vulnsheet — входа режимов обновления.

Таблица — ровно то, что пишет report.write: UTF-8 (BOM допускается), ';',
кавычки по правилам CSV, заголовок report.COLUMNS, в каждой записи 20
ячеек. Ячейки отдаются дословно: в них ручные данные людей. Любое
отклонение — TableError: выбросить «кривую» строку нельзя.
"""
import csv
from typing import List, NamedTuple

from .report import COLUMNS


class TableError(Exception):
    """Таблица не читается или не в формате vulnsheet."""


class Record(NamedTuple):
    """Строка таблицы: номер записи в файле (заголовок — 1) и ячейки."""
    number: int
    cells: List[str]


def read(path: str) -> List[Record]:
    """Строки данных без заголовка; полностью пустые записи пропускаются."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            raw = list(csv.reader(handle, delimiter=";"))
    except UnicodeDecodeError as exc:
        raise TableError("%s: не в UTF-8: %s" % (path, exc))
    except OSError as exc:
        raise TableError("%s: не читается: %s" % (path, exc))
    except csv.Error as exc:
        raise TableError("%s: ошибка CSV: %s" % (path, exc))

    records = [Record(number, cells) for number, cells in enumerate(raw, 1)
               if any(cell.strip() for cell in cells)]
    if not records:
        raise TableError("%s: пустой файл, нет заголовка" % path)
    header, rows = records[0], records[1:]
    if [cell.strip() for cell in header.cells] != COLUMNS:
        raise TableError("%s: запись %d: заголовок не как у vulnsheet"
                         % (path, header.number))
    for record in rows:
        if len(record.cells) != len(COLUMNS):
            raise TableError("%s: запись %d: ячеек %d, ожидается %d"
                             % (path, record.number, len(record.cells), len(COLUMNS)))
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: всё зелёное, 146 тестов (133 + 4 в `GroupsTest` + 9 в `test_table`).

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/report.py tools/vulnsheet/vulnsheet/table.py \
        tools/vulnsheet/tests/test_report.py tools/vulnsheet/tests/test_table.py
git commit -m "feat(vulnsheet): read an existing table and name column groups"
```

---

### Task 2: слияние (`merge.py`)

**Files:**
- Create: `tools/vulnsheet/vulnsheet/merge.py`
- Create: `tools/vulnsheet/tests/test_merge.py`

**Interfaces:**
- Consumes:
  - из Task 1: `report.DEVELOPER`/`TASK`/`KOJI`/`VEX`/`COMMENT`, индексы `report.TASK_ID`/`CVE_ID`/`TASK_STATE`/`TASK_DATE`/`ASSIGNEE`/`COMPONENT`, `report.MISSING`, `report.EMPTY`, `table.Record`;
  - `report.row(task, nvr, verdict)`;
  - `tasks.Task(task_id, cve, component, state, date, assignee)`, `tasks.CVE_RE`;
  - `kojiclient.ERROR`, `vex.FETCH_ERROR`, `vex.Verdict`.
- Produces (для Task 3):
  - `merge.Fresh(NamedTuple)`: `nvrs: Mapping[str, str]` (компонент → NVR, `NOT_FOUND` или `ERROR`), `verdicts: Mapping[Tuple[str, str], Verdict]` (ключ — (CVE в верхнем регистре, компонент без крайних пробелов));
  - `merge.Note(NamedTuple)`: `number: int`, `cve: str`, `component: str` — ячейки как есть;
  - `merge.Outcome(NamedTuple)`: `rows: List[List[str]]`, `matched: int`, `missing: int`, `added: int`, `repeated: int`, `kept_koji: Tuple[Note, ...]`, `kept_vex: Tuple[Note, ...]`, `skipped: Tuple[Note, ...]`;
  - `merge.pairs(records: Optional[Sequence[Record]], tasks: Optional[Sequence[Task]]) -> List[Tuple[str, str]]` — одна пара на каждую обновляемую строку выхода, в порядке строк, с повторами;
  - `merge.build(tasks, fresh) -> Outcome` — режим 1;
  - `merge.refresh(records, fresh) -> Outcome` — режим 2;
  - `merge.sync(records, tasks, fresh) -> Outcome` — режим 3.
  - `Fresh` обязан содержать ответы на все пары из `pairs(records, tasks)`, иначе будет `KeyError`.

- [ ] **Step 1: Write the failing tests**

Создать `tools/vulnsheet/tests/test_merge.py`:

```python
import unittest

from vulnsheet import report
from vulnsheet.kojiclient import ERROR, NOT_FOUND
from vulnsheet.merge import Fresh, Note, build, pairs, refresh, sync
from vulnsheet.table import Record
from vulnsheet.tasks import Task
from vulnsheet.vex import FETCH_ERROR, Verdict

LINK = "https://access.redhat.com/security/cve/"
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"

# Строки, которые люди уже вели: ручные колонки заполнены, koji и VEX старые.
OLD = ["Иванов", "В работе", "01.09.2026", "-", "обновить",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       LINK + "CVE-2026-0001", "ждём апстрим"]
BASH = ["Петров", "Готово", "02.09.2026", "03.09.2026", "обновлено",
        "TASKID-2", "CVE-2026-0002", "Выполнена", "02.09.2026", "КМ", "bash",
        "bash-4-1.sl9", "-", "-", "Affected", "Moderate", "5.5", "-",
        LINK + "CVE-2026-0002", "-"]

FRESH = Fresh(
    nvrs={"vim": "vim-2-1.sl9", "bash": "bash-5-1.sl9", "openssl": NOT_FOUND},
    verdicts={
        ("CVE-2026-0001", "vim"): Verdict("Fixed", "Important", "7.8", "vim-2-1.el9",
                                          "2026-09-02", RHSA),
        ("CVE-2026-0002", "bash"): Verdict("Affected", "Moderate", "5.5"),
        ("CVE-2026-0003", "openssl"): Verdict("not listed"),
    })
# колонки SL NVR … Advisory строки OLD по FRESH
UPDATED = ["vim-2-1.sl9", "vim-2-1.el9", "02.09.2026", "Fixed", "Important", "7.8", RHSA]
DATA = slice(report.KOJI.start, report.VEX.stop)  # SL NVR … Advisory


def changed(cells, changes):
    """Копия строки с заменой ячеек: {индекс колонки: значение}."""
    cells = list(cells)
    for index, value in changes.items():
        cells[index] = value
    return cells


def task(task_id="TASKID-1", cve="CVE-2026-0001", component="vim",
         state="Отменен", date="22.09.2026", assignee="ПП"):
    return Task(task_id, cve, component, state, date, assignee)


OPENSSL = task("TASKID-3", "CVE-2026-0003", "openssl", "В работу", "23.09.2026", "КМ")
# OLD, совпавшая с task(): данные задачи из блока, ручные колонки прежние
MATCHED = (OLD[:5] + ["TASKID-1", "CVE-2026-0001", "Отменен", "22.09.2026", "ПП", "vim"]
           + UPDATED + OLD[18:])
# BASH, чьей задачи нет в блоках
BASH_MISSING = (BASH[:7] + [report.MISSING] + BASH[8:11]
                + ["bash-5-1.sl9", "-", "-", "Affected", "Moderate", "5.5", "-"] + BASH[18:])
# новая строка из OPENSSL
NEW = (["-"] * 5 + ["TASKID-3", "CVE-2026-0003", "В работу", "23.09.2026", "КМ", "openssl",
                    NOT_FOUND, "-", "-", "not listed", "-", "-", "-",
                    LINK + "CVE-2026-0003", "-"])


class PairsTest(unittest.TestCase):
    def test_mode1_keeps_every_block(self):
        tasks = [task(), task(), OPENSSL]
        self.assertEqual(pairs(None, tasks), [("CVE-2026-0001", "vim")] * 2
                         + [("CVE-2026-0003", "openssl")])

    def test_mode2_takes_rows_with_something_to_ask(self):
        records = [Record(2, changed(OLD, {report.CVE_ID: " cve-2026-0001 "})),
                   Record(3, changed(OLD, {report.CVE_ID: "-"})),
                   Record(4, changed(OLD, {report.COMPONENT: "-"})),
                   Record(5, BASH)]
        self.assertEqual(pairs(records, None),
                         [("CVE-2026-0001", "vim"), ("CVE-2026-0002", "bash")])

    def test_mode3_rows_then_new_triples_once(self):
        records = [Record(2, OLD), Record(3, BASH)]
        self.assertEqual(pairs(records, [task(), OPENSSL, OPENSSL]), [
            ("CVE-2026-0001", "vim"), ("CVE-2026-0002", "bash"),
            ("CVE-2026-0003", "openssl")])


class BuildTest(unittest.TestCase):
    def test_row_per_block_with_repeats(self):
        expected = report.row(task(), "vim-2-1.sl9", FRESH.verdicts[("CVE-2026-0001", "vim")])
        self.assertEqual(build([task(), task()], FRESH).rows, [expected, expected])


class RefreshTest(unittest.TestCase):
    def test_manual_and_task_columns_stay_koji_and_vex_update(self):
        before = list(OLD)
        out = refresh([Record(2, OLD)], FRESH)
        self.assertEqual(out.rows, [OLD[:11] + UPDATED + OLD[18:]])
        self.assertEqual((out.kept_koji, out.kept_vex, out.skipped), ((), (), ()))
        self.assertEqual(OLD, before)  # вход не изменён

    def test_koji_error_keeps_previous_nvr(self):
        out = refresh([Record(2, OLD)], FRESH._replace(nvrs={"vim": ERROR}))
        self.assertEqual(out.rows[0][DATA], [OLD[report.SL_NVR]] + UPDATED[1:])
        self.assertEqual(out.kept_koji, (Note(2, "CVE-2026-0001", "vim"),))
        self.assertEqual(out.kept_vex, ())

    def test_fetch_error_keeps_previous_vex_group(self):
        fresh = FRESH._replace(
            verdicts={("CVE-2026-0001", "vim"): Verdict(state=FETCH_ERROR)})
        out = refresh([Record(2, OLD)], fresh)
        self.assertEqual(out.rows[0], OLD[:11] + ["vim-2-1.sl9"] + OLD[12:])
        self.assertEqual(out.kept_vex, (Note(2, "CVE-2026-0001", "vim"),))

    def test_answers_overwrite_previous_values(self):
        fresh = Fresh(nvrs={"vim": NOT_FOUND},
                      verdicts={("CVE-2026-0001", "vim"): Verdict("not listed")})
        row = refresh([Record(2, OLD)], fresh).rows[0]
        self.assertEqual(row[DATA], [NOT_FOUND, "-", "-", "not listed", "-", "-", "-"])

    def test_row_without_cve_or_component_is_left_as_is(self):
        rows = [changed(OLD, {report.CVE_ID: "-"}), changed(OLD, {report.COMPONENT: " "})]
        out = refresh([Record(2, rows[0]), Record(3, rows[1])], Fresh({}, {}))
        self.assertEqual(out.rows, rows)
        self.assertEqual(out.skipped, (Note(2, "-", "vim"), Note(3, "CVE-2026-0001", " ")))

    def test_cve_cell_is_matched_loosely_but_kept_verbatim(self):
        cells = changed(OLD, {report.CVE_ID: " cve-2026-0001"})
        row = refresh([Record(2, cells)], FRESH).rows[0]
        self.assertEqual(row[report.CVE_ID], " cve-2026-0001")
        self.assertEqual(row[DATA], UPDATED)
        self.assertEqual(row[report.LINK], [LINK + "CVE-2026-0001"])


class SyncTest(unittest.TestCase):
    def test_match_missing_and_new(self):
        out = sync([Record(2, OLD), Record(3, BASH)], [OPENSSL, task()], FRESH)
        self.assertEqual(out.rows, [MATCHED, BASH_MISSING, NEW])
        self.assertEqual((out.matched, out.missing, out.added, out.repeated), (1, 1, 1, 0))

    def test_existing_order_kept_new_in_block_order(self):
        tasks = [task("TASKID-9", "CVE-2026-0003", "openssl"),
                 task("TASKID-2", "CVE-2026-0002", "bash"),
                 task("TASKID-8", "CVE-2026-0003", "openssl"), task()]
        out = sync([Record(2, BASH), Record(3, OLD)], tasks, FRESH)
        self.assertEqual([r[report.TASK_ID] for r in out.rows],
                         ["TASKID-2", "TASKID-1", "TASKID-9", "TASKID-8"])

    def test_missing_row_back_in_blocks_takes_block_state(self):
        cells = changed(OLD, {report.TASK_STATE: report.MISSING})
        self.assertEqual(sync([Record(2, cells)], [task()], FRESH).rows, [MATCHED])

    def test_key_is_trimmed_and_cve_case_insensitive(self):
        cells = changed(OLD, {report.TASK_ID: " TASKID-1 ", report.CVE_ID: "cve-2026-0001",
                              report.COMPONENT: "vim "})
        out = sync([Record(2, cells)], [task()], FRESH)
        self.assertEqual((out.matched, out.missing, out.added), (1, 0, 0))

    def test_same_cve_and_component_other_task_is_not_a_match(self):
        out = sync([Record(2, OLD)], [task(task_id="TASKID-7")], FRESH)
        self.assertEqual((out.matched, out.missing, out.added), (0, 1, 1))

    def test_repeated_block_triple_first_wins(self):
        out = sync([Record(2, OLD)], [task(), task(state="Выполнена")], FRESH)
        self.assertEqual(out.rows, [MATCHED])
        self.assertEqual(out.repeated, 1)

    def test_repeated_new_triple_is_added_once(self):
        out = sync([], [OPENSSL, OPENSSL], FRESH)
        self.assertEqual(out.rows, [NEW])
        self.assertEqual((out.added, out.repeated), (1, 1))

    def test_duplicate_table_rows_each_take_the_block(self):
        out = sync([Record(2, OLD), Record(3, OLD)], [task()], FRESH)
        self.assertEqual(out.rows, [MATCHED, MATCHED])
        self.assertEqual((out.matched, out.added), (2, 0))

    def test_failures_keep_old_values_but_new_row_gets_markers(self):
        fresh = Fresh(nvrs={"vim": ERROR, "openssl": ERROR}, verdicts={
            ("CVE-2026-0001", "vim"): Verdict(state=FETCH_ERROR),
            ("CVE-2026-0003", "openssl"): Verdict(state=FETCH_ERROR)})
        out = sync([Record(2, OLD)], [task(), OPENSSL], fresh)
        self.assertEqual(out.rows[0][DATA], OLD[DATA])
        self.assertEqual(out.rows[1][DATA], [ERROR, "-", "-", FETCH_ERROR, "-", "-", "-"])
        note = Note(2, "CVE-2026-0001", "vim")
        self.assertEqual((out.kept_koji, out.kept_vex), ((note,), (note,)))

    def test_row_with_nothing_to_ask_is_not_marked_missing(self):
        cells = changed(OLD, {report.CVE_ID: "-"})
        out = sync([Record(2, cells)], [OPENSSL], FRESH)
        self.assertEqual(out.rows, [cells, NEW])
        self.assertEqual((out.missing, out.skipped), (0, (Note(2, "-", "vim"),)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_merge -v`
Expected: FAIL: `ModuleNotFoundError: No module named 'vulnsheet.merge'`.

- [ ] **Step 3: Implement**

Создать `tools/vulnsheet/vulnsheet/merge.py`:

```python
"""Строки выхода из блоков, прежней таблицы и свежих данных koji и VEX.

Чистые функции — ни файлов, ни сети. cli сначала спрашивает pairs(), какие
пары (CVE, компонент) нужны строкам выхода, получает по ним ответы koji и
VEX и отдаёт их сюда записью Fresh. Что в каком режиме откуда берётся —
таблица групп колонок в
docs/superpowers/specs/2026-09-24-vulnsheet-update-modes-design.md.
"""
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from . import report
from .kojiclient import ERROR
from .table import Record
from .tasks import CVE_RE, Task
from .vex import FETCH_ERROR, Verdict

Pair = Tuple[str, str]       # (CVE, компонент)
Key = Tuple[str, str, str]   # (Task ID, CVE, компонент)


class Fresh(NamedTuple):
    """Ответы источников: компонент → NVR (или NOT_FOUND/ERROR);
    (CVE, компонент) → вердикт (FETCH_ERROR — документ не получен)."""
    nvrs: Mapping[str, str]
    verdicts: Mapping[Pair, Verdict]


class Note(NamedTuple):
    """Строка таблицы для журнала: номер записи, CVE и компонент как есть."""
    number: int
    cve: str
    component: str


class Outcome(NamedTuple):
    rows: List[List[str]]
    matched: int = 0
    missing: int = 0
    added: int = 0
    repeated: int = 0                 # повторы троек в блоках
    kept_koji: Tuple[Note, ...] = ()  # koji ERROR — оставлен прежний SL NVR
    kept_vex: Tuple[Note, ...] = ()   # fetch error — оставлены прежние VEX
    skipped: Tuple[Note, ...] = ()    # спрашивать нечего — строка как есть


class _Notes:
    def __init__(self):
        self.kept_koji, self.kept_vex, self.skipped = [], [], []

    def fields(self) -> dict:
        return {"kept_koji": tuple(self.kept_koji), "kept_vex": tuple(self.kept_vex),
                "skipped": tuple(self.skipped)}


def pairs(records: Optional[Sequence[Record]],
          tasks: Optional[Sequence[Task]]) -> List[Pair]:
    """Пара на каждую строку выхода, которую надо обновить, в порядке строк.

    records=None — режим 1 (каждый блок, с повторами); tasks=None — режим 2;
    оба — режим 3: строки таблицы, затем новые тройки из блоков.
    """
    if records is None:
        return [_task_pair(task) for task in tasks or ()]
    result, known = [], set()
    for record in records:
        pair = _pair(record)
        if pair is not None:
            result.append(pair)
            known.add(_record_key(record, pair))
    first, _ = _first_tasks(tasks or ())
    result.extend(_task_pair(task) for key, task in first.items() if key not in known)
    return result


def build(tasks: Sequence[Task], fresh: Fresh) -> Outcome:
    """Режим 1: строка на каждый блок, в порядке блоков, с повторами."""
    return Outcome(rows=[_fresh_row(task, fresh) for task in tasks])


def refresh(records: Sequence[Record], fresh: Fresh) -> Outcome:
    """Режим 2: обновить koji и VEX, остальное как есть."""
    notes, rows = _Notes(), []
    for record in records:
        pair = _pair(record)
        if pair is None:
            notes.skipped.append(_note(record))
            rows.append(list(record.cells))
            continue
        cells = _updated(record, _as_task(record, pair), pair, fresh, notes)
        cells[report.TASK] = record.cells[report.TASK]
        rows.append(cells)
    return Outcome(rows=rows, **notes.fields())


def sync(records: Sequence[Record], tasks: Sequence[Task], fresh: Fresh) -> Outcome:
    """Режим 3: строки таблицы сверяются с блоками по тройке.

    Совпавшие берут данные задачи из блока; пропавшие получают Missing;
    новые тройки дописываются в конец, в порядке блоков. Порядок прежних
    строк не меняется.
    """
    first, repeated = _first_tasks(tasks)
    notes, rows, seen = _Notes(), [], set()
    matched = missing = 0
    for record in records:
        pair = _pair(record)
        if pair is None:
            notes.skipped.append(_note(record))
            rows.append(list(record.cells))
            continue
        key = _record_key(record, pair)
        task = first.get(key)
        if task is not None:
            seen.add(key)
            matched += 1
            rows.append(_updated(record, task, pair, fresh, notes))
        else:
            missing += 1
            cells = _updated(record, _as_task(record, pair), pair, fresh, notes)
            cells[report.TASK] = record.cells[report.TASK]
            cells[report.TASK_STATE] = report.MISSING
            rows.append(cells)
    new = [task for key, task in first.items() if key not in seen]
    rows.extend(_fresh_row(task, fresh) for task in new)
    return Outcome(rows=rows, matched=matched, missing=missing, added=len(new),
                   repeated=repeated, **notes.fields())


def _pair(record: Record) -> Optional[Pair]:
    """(CVE, компонент) строки таблицы; None — спрашивать нечего."""
    cve = record.cells[report.CVE_ID].strip().upper()
    component = record.cells[report.COMPONENT].strip()
    if not CVE_RE.match(cve) or component in ("", report.EMPTY):
        return None
    return cve, component


def _record_key(record: Record, pair: Pair) -> Key:
    return (record.cells[report.TASK_ID].strip(),) + pair


def _task_pair(task: Task) -> Pair:
    return task.cve.strip().upper(), task.component.strip()


def _first_tasks(tasks: Sequence[Task]) -> Tuple[Dict[Key, Task], int]:
    """Первый блок каждой тройки, в порядке блоков, и число повторов."""
    first, repeated = {}, 0
    for task in tasks:
        key = (task.task_id.strip(),) + _task_pair(task)
        if key in first:
            repeated += 1
        else:
            first[key] = task
    return first, repeated


def _as_task(record: Record, pair: Pair) -> Task:
    """Задача из ячеек строки — чтобы собрать свежую строку report.row."""
    cells = record.cells
    return Task(task_id=cells[report.TASK_ID], cve=pair[0], component=pair[1],
                state=cells[report.TASK_STATE], date=cells[report.TASK_DATE],
                assignee=cells[report.ASSIGNEE])


def _fresh_row(task: Task, fresh: Fresh) -> List[str]:
    pair = _task_pair(task)
    return report.row(task, fresh.nvrs[pair[1]], fresh.verdicts[pair])


def _note(record: Record) -> Note:
    return Note(record.number, record.cells[report.CVE_ID], record.cells[report.COMPONENT])


def _updated(record: Record, task: Task, pair: Pair, fresh: Fresh, notes: _Notes) -> List[str]:
    """Свежая строка по задаче поверх прежней: ручные колонки — из прежней,
    при сбое источника — его прежние колонки."""
    old = record.cells
    cells = _fresh_row(task, fresh)
    cells[report.DEVELOPER] = old[report.DEVELOPER]
    cells[report.COMMENT] = old[report.COMMENT]
    if fresh.nvrs[pair[1]] == ERROR:
        cells[report.KOJI] = old[report.KOJI]
        notes.kept_koji.append(_note(record))
    if fresh.verdicts[pair].state == FETCH_ERROR:
        cells[report.VEX] = old[report.VEX]
        notes.kept_vex.append(_note(record))
    return cells
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: всё зелёное, 166 тестов (146 + 20 в `test_merge`).

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/merge.py tools/vulnsheet/tests/test_merge.py
git commit -m "feat(vulnsheet): merge an existing table with blocks and fresh data"
```

---

### Task 3: CLI — `--blocks`, `--table`, три режима

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/cli.py` (парсер, `main`, `_run`, `_summary`; новые `_read_table`, `_merge`, `_report_outcome`)
- Modify: `tools/vulnsheet/tests/test_cli.py`

**Interfaces:**
- Consumes:
  - `table.read`, `table.TableError`;
  - `merge.pairs`, `merge.build`, `merge.refresh`, `merge.sync`, `merge.Fresh`, `merge.Outcome` (поля — см. Task 2);
  - `report.RHEL_STATE`, `report.SL_NVR`, `report.EMPTY`.
- Produces: CLI `vulnsheet [--blocks FILE|-] [--table FILE] …`. Позиционного `input` больше нет.

- [ ] **Step 1: Migrate existing CLI tests to `--blocks` and write the failing new ones**

В `tools/vulnsheet/tests/test_cli.py`:

1. После `HEADER = …` добавить:

```python
COMMON = ["--rhel", "9", "--koji-url", "https://koji.example.com/kojihub", "--tag", "sl9"]
```

2. В `CliCase` заменить `run_cli` на пару методов:

```python
    def run_main(self, *argv):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(COMMON + list(argv))
        self.log = err.getvalue()
        return code

    def run_cli(self, *extra, text=BLOCK + "\n", data=None):
        src = self.path("tasks.txt")
        with open(src, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        return self.run_main("--blocks", src, "-o", self.path("report.csv"), *extra)
```

3. Там, где `main` вызывается с позиционным файлом, перед этим файлом поставить `"--blocks"`:
   - `test_stdout_when_no_output_given`: `main(["--rhel", "9", "--koji-url", "https://k/kojihub", "--tag", "sl9", "--blocks", src])`;
   - `test_missing_input_is_fatal`: `…, "--blocks", self.path("нет-такого.txt"), "-o", self.path("r.csv")]`;
   - `test_missing_required_value_is_fatal`: `main(["--rhel", "9", "--tag", "sl9", "--blocks", src, "-o", self.path("r.csv")])`;
   - `ConfigTest.run_raw`: `main(["--blocks", src, "-o", self.path("report.csv")] + list(argv))`;
   - `BrokenPipeTest`: `main(["--rhel", "9", "--koji-url", "https://k/kojihub", "--tag", "sl9", "--blocks", src])`.

4. Перед `class BrokenPipeTest` вставить:

```python
# строка прежней таблицы: ручные колонки заполнены, koji и VEX устарели
OLD_ROW = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
           "В работу;01.09.2026;КМ;vim;vim-8.2.2637-20.sl9;-;-;Affected;Low;3.1;-;"
           "https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# OLD_ROW после режима 2: обновлены только koji и VEX
REFRESHED = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
             "В работу;01.09.2026;КМ;vim;vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;"
             "Moderate;5.5;-;https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# OLD_ROW после режима 3 с BLOCK: данные задачи — из блока
SYNCED = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
          "Отменен;22.09.2026;КМ;vim;vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;"
          "Moderate;5.5;-;https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# задача, которой больше нет в блоках
GONE_ROW = ("Петров;Готово;-;-;-;TASKID-100000;CVE-2026-73071;Выполнена;01.08.2026;КМ;"
            "openssl;openssl-3-1.sl9;-;-;Fixed;Low;2.0;-;"
            "https://access.redhat.com/security/cve/CVE-2026-73071;-")
GONE_MISSING = ("Петров;Готово;-;-;-;TASKID-100000;CVE-2026-73071;Missing;01.08.2026;КМ;"
                "openssl;NOT_FOUND;-;-;no VEX record;-;-;-;"
                "https://access.redhat.com/security/cve/CVE-2026-73071;-")
NEW_BLOCK = BLOCK.replace("181229", "181230").replace("73070", "73071").replace("vim", "openssl")
NEW_ROW = ("-;-;-;-;-;TASKID-181230;CVE-2026-73071;Отменен;22.09.2026;КМ;openssl;NOT_FOUND;"
           "-;-;no VEX record;-;-;-;https://access.redhat.com/security/cve/CVE-2026-73071;-")


class UsageTest(CliCase):
    def assertUsageError(self, argv, needle):
        with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(needle, err.getvalue())

    def test_neither_blocks_nor_table(self):
        self.assertUsageError(COMMON, "нужен --blocks или --table")

    def test_table_from_stdin_is_refused(self):
        self.assertUsageError(COMMON + ["--table", "-"], "только файл")

    def test_blocks_from_stdin(self):
        with mock.patch("sys.stdin", io.StringIO(BLOCK)):
            code = self.run_main("--blocks", "-", "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        self.assertIn("режим: новая таблица", self.log)


class UpdateModesTest(CliCase):
    def write_table(self, *rows, name="old.csv"):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join((HEADER,) + rows) + "\n")
        return path

    def write_blocks(self, text):
        path = self.path("tasks.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_refresh_updates_only_koji_and_vex(self):
        code = self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, REFRESHED])
        self.assertIn("режим: обновление koji и VEX", self.log)
        self.assertIn("old.csv: строк 1", self.log)

    def test_refresh_in_place(self):
        table = self.write_table(OLD_ROW, name="report.csv")
        self.assertEqual(self.run_main("--table", table, "-o", table), EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, REFRESHED])

    def test_refresh_keeps_previous_vex_on_fetch_error(self):
        self.docs[vex_url("CVE-2026-73070")] = OSError("сеть")
        code = self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines()[1],
                         OLD_ROW.replace("vim-8.2.2637-20.sl9", "vim-8.2.2637-26.sl9_8.6^4"))
        self.assertIn("оставлены прежние данные VEX", self.log)

    def test_refresh_row_without_cve_is_partial(self):
        row = OLD_ROW.replace("CVE-2026-73070;", "-;", 1)
        code = self.run_main("--table", self.write_table(row), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER, row])
        self.assertIn("строка оставлена как есть", self.log)
        self.connect.assert_not_called()

    def test_refresh_does_not_touch_rejects_file(self):
        with open(self.path("report.rejected.txt"), "w") as handle:
            handle.write("старьё")
        self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertTrue(os.path.exists(self.path("report.rejected.txt")))

    def test_header_only_table_skips_network(self):
        code = self.run_main("--table", self.write_table(), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER])
        self.connect.assert_not_called()

    def test_sync_matches_marks_missing_and_appends(self):
        blocks = self.write_blocks(BLOCK + "\n\n" + NEW_BLOCK + "\n")
        code = self.run_main("--table", self.write_table(OLD_ROW, GONE_ROW),
                             "--blocks", blocks, "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, SYNCED, GONE_MISSING, NEW_ROW])
        self.assertIn("режим: синхронизация с блоками", self.log)
        self.assertIn("совпало 1, Missing 1, новых 1", self.log)

    def test_sync_with_empty_blocks_is_fatal(self):
        code = self.run_main("--table", self.write_table(OLD_ROW),
                             "--blocks", self.write_blocks("\n"), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("ни одного блока", self.log)
        self.connect.assert_not_called()

    def test_broken_table_is_fatal_and_keeps_output(self):
        with open(self.path("report.csv"), "w", encoding="utf-8") as handle:
            handle.write("прошлый отчёт\n")
        table = self.path("old.csv")
        with open(table, "w", encoding="utf-8") as handle:
            handle.write("не та таблица\n")
        code = self.run_main("--table", table, "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("old.csv", self.log)
        self.assertIn("заголовок", self.log)
        self.assertNotIn("Traceback", self.log)
        self.connect.assert_not_called()
        with open(self.path("report.csv"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "прошлый отчёт\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_cli -v`
Expected: FAIL. Почти все прежние тесты падают с `SystemExit: 2`, потому что `unrecognized arguments: --blocks`, а новые — на неизвестных флагах.

- [ ] **Step 3: Implement**

В `tools/vulnsheet/vulnsheet/cli.py`:

Шапку модуля и импорт заменить на:

```python
"""Точка входа: блоки задач и/или прежняя таблица → koji и VEX → CSV."""
```

```python
from . import __version__, config, kojiclient, logs, merge, report, table, vex
```

После `REJECTS_STDOUT = …` добавить:

```python
# режим по (есть --blocks, есть --table)
MODES = {
    (True, False): "новая таблица",
    (False, True): "обновление koji и VEX",
    (True, True): "синхронизация с блоками",
}
```

В `_parser()` заменить `description` и позиционный `input`:

```python
    parser = argparse.ArgumentParser(
        prog="vulnsheet",
        description="Блоки задач из тасктрекера и/или прежняя таблица → CSV "
                    "с данными Red Hat VEX и koji.")
    parser.add_argument("--blocks", metavar="FILE",
                        help="файл с блоками задач; - — stdin")
    parser.add_argument("--table", metavar="FILE",
                        help="прежняя таблица vulnsheet: без --blocks — обновить в ней "
                             "koji и VEX, с --blocks — сверить с блоками")
```

Остальные флаги остаются как есть.

После `_read_input` добавить:

```python
def _read_table(path: str):
    try:
        return table.read(path)
    except table.TableError as exc:
        raise _Fatal("таблица %s" % exc)
```

`_summary` заменить на версию, которая считает по строкам выхода:

```python
def _summary(rows) -> None:
    """Сводка по строкам выхода; прочерки — строки, где спрашивать было нечего."""
    states = Counter(r[report.RHEL_STATE].split(" (", 1)[0] for r in rows
                     if r[report.RHEL_STATE] != report.EMPTY)
    if states:
        logger.info("RHEL state: %s", ", ".join(
            "%s %d" % item for item in sorted(states.items(), key=lambda kv: (-kv[1], kv[0]))))
    marks = Counter(r[report.SL_NVR] if r[report.SL_NVR] in (kojiclient.NOT_FOUND, kojiclient.ERROR)
                    else "found" for r in rows if r[report.SL_NVR] != report.EMPTY)
    logger.info("SL NVR: найдено %d, NOT_FOUND %d, ERROR %d", marks["found"],
                marks[kojiclient.NOT_FOUND], marks[kojiclient.ERROR])
```

Перед `_run` добавить:

```python
def _merge(records, tasks, fresh):
    if records is None:
        return merge.build(tasks, fresh)
    if tasks is None:
        return merge.refresh(records, fresh)
    return merge.sync(records, tasks, fresh)


def _report_outcome(outcome, synced: bool) -> None:
    if synced:
        logger.info("совпало %d, Missing %d, новых %d",
                    outcome.matched, outcome.missing, outcome.added)
        if outcome.repeated:
            logger.info("повторов троек в блоках %d — действует первый блок",
                        outcome.repeated)
    for note in outcome.kept_koji:
        logger.warning("запись %d (%s %s): koji не ответил — оставлен прежний SL NVR",
                       note.number, note.cve, note.component)
    for note in outcome.kept_vex:
        logger.warning("запись %d (%s %s): VEX не получен — оставлены прежние данные VEX",
                       note.number, note.cve, note.component)
    for note in outcome.skipped:
        logger.warning("запись %d (%s %s): нет CVE-ID или компонента — строка оставлена как есть",
                       note.number, note.cve, note.component)
```

`_run` заменить целиком:

```python
def _run(args) -> int:
    cfg, rhel, hub, tag = _settings(args)
    logger.info("режим: %s", MODES[(args.blocks is not None, args.table is not None)])
    records = None
    if args.table is not None:
        records = _read_table(args.table)
        logger.info("таблица %s: строк %d", args.table, len(records))
    tasks, rejects = None, []
    if args.blocks is not None:
        tasks, rejects = parse(_read_input(args.blocks))
        # в режиме 3 пустые блоки иначе молча сделали бы все строки Missing
        if not tasks and not rejects:
            raise _Fatal("во входе нет ни одного блока")
        for reject in rejects:
            logger.warning("блок %d «%s» отбракован: %s", reject.number,
                           reject.text.split("\n", 1)[0].strip(), reject.reason)

    wanted = merge.pairs(records, tasks)  # пара на строку выхода, с повторами
    unique = list(dict.fromkeys(wanted))
    cves = list(dict.fromkeys(cve for cve, _ in unique))
    packages = list(dict.fromkeys(component for _, component in unique))
    logger.info("хаб %s, тег %s, RHEL %s", hub, tag, rhel)
    streams = {name: cfg.stream_for(name, rhel) for name in packages}
    applied = Counter(name for _, name in wanted if streams[name])
    if applied:
        logger.info("стримы VEX для RHEL %s: %s", rhel, ", ".join(
            "%s → %s (%d)" % (name, streams[name], count) for name, count in applied.items()))
    if tasks is not None:
        logger.info("блоков %d, отбраковано %d; CVE %d, пакетов %d",
                    len(tasks) + len(rejects), len(rejects), len(cves), len(packages))
    else:
        logger.info("CVE %d, пакетов %d", len(cves), len(packages))

    # выход открываем до сети: неверный путь должен падать сразу, и не
    # затирать прежний отчёт — пишем во временник рядом, подменяем в конце;
    # таблица к этому моменту прочитана целиком, так что -o может быть ею
    out, tmp_path, final_path = _open_output(args.output)
    if args.rejects and args.blocks is not None:
        _check_rejects_dir(args.rejects)
    try:
        nvrs, indices, failures = {}, {}, {}
        if unique:
            session = kojiclient.connect(hub)
            nvrs = kojiclient.latest_builds(session, tag, packages)
            settings = cfg.vex._replace(
                cache_dir=vex.prepare_cache(cfg.vex.cache_dir or _cache_dir()))
            indices, failures = vex.fetch_all(cves, settings)
        verdicts = {(cve, name): vex.Verdict(state=vex.FETCH_ERROR) if cve in failures
                    else vex.lookup(indices[cve], name, rhel, streams[name])
                    for cve, name in unique}
        outcome = _merge(records, tasks, merge.Fresh(nvrs, verdicts))
        report.write(outcome.rows, out)
    except BaseException:
        if tmp_path is not None:
            out.close()
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    else:
        if tmp_path is not None:
            out.close()
            os.replace(tmp_path, final_path)
    if args.output != STDIO:
        logger.info("написан %s", args.output)

    # файл отбраковки — дело блоков: в режиме 2 его не трогаем
    if args.blocks is not None:
        _write_rejects(rejects_path(args.output, args.rejects), rejects)
    _report_outcome(outcome, synced=records is not None and tasks is not None)
    _summary(outcome.rows)
    partial = (rejects or failures or kojiclient.ERROR in nvrs.values()
               or outcome.skipped)
    return EXIT_PARTIAL if partial else EXIT_OK
```

В `main` заменить первую строку `args = _parser().parse_args(argv)` на:

```python
    parser = _parser()
    args = parser.parse_args(argv)
    if args.blocks is None and args.table is None:
        parser.error("нужен --blocks или --table")
    if args.table == STDIO:
        parser.error("--table: таблица — только файл, не stdin")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: всё зелёное, 178 тестов (166 + 3 в `UsageTest` + 9 в `UpdateModesTest`).

Проверить вручную, что справка собирается и позиционного входа нет:

Run: `cd tools/vulnsheet && python3 -m vulnsheet --help | head -20`
Expected: в справке есть `--blocks FILE` и `--table FILE`, нет `input`.

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/cli.py tools/vulnsheet/tests/test_cli.py
git commit -m "feat(vulnsheet): update an existing table via --table and --blocks"
```

---

### Task 4: документация

**Files:**
- Modify: `tools/vulnsheet/README.md`
- Modify: `tools/vulnsheet/CHANGELOG.md`
- Modify: `CHANGELOG.md` (корень)

**Interfaces:**
- Consumes: поведение из Tasks 1–3 и спек.
- Produces: документация. Кода нет.

- [ ] **Step 1: README — вступление**

Абзац «Заменяет три отдельных скрипта: …» заменить на:

```markdown
Заменяет три отдельных скрипта: разбор блоков, запрос к VEX и запрос к koji.

Умеет и обновлять уже ведущуюся таблицу, не трогая колонок, которые
заполняют люди: освежить в ней данные koji и VEX или сверить её с новой
выгрузкой блоков (см. «Режимы»).
```

- [ ] **Step 2: README — «Запуск»**

Первый пример в разделе «Запуск» заменить на:

```bash
python3 -m vulnsheet --rhel 9 --koji-url https://koji.example.com/kojihub \
    --tag sl9-updates --blocks tasks.txt -o report.csv
```

В таблице аргументов строку `input` заменить двумя строками:

```markdown
| `--blocks` | файл с блоками; `-` — stdin |
| `--table` | прежняя таблица vulnsheet, только файл (см. «Режимы»). Нужен `--blocks`, `--table` или оба |
```

Пример «Из буфера обмена» — `xclip -o | python3 -m vulnsheet … --tag sl9-updates --blocks - -o report.csv`. Пример «С конфигом» — `python3 -m vulnsheet --config vulnsheet.yaml --blocks tasks.txt -o report.csv`.

- [ ] **Step 3: README — раздел «Режимы»**

Вставить сразу перед разделом `## Конфиг`:

````markdown
## Режимы

Режим задаётся тем, что подано на вход:

| Вход | Режим | Что делает |
|---|---|---|
| `--blocks` | новая таблица | строит таблицу с нуля |
| `--table` | обновление koji и VEX | в прежней таблице обновляет только данные koji и VEX |
| `--table` и `--blocks` | синхронизация с блоками | обновляет данные задач из блоков, koji и VEX; пропавшие задачи помечает, новые дописывает |

```bash
# освежить koji и VEX в той же таблице
python3 -m vulnsheet --config vulnsheet.yaml --table report.csv -o report.csv

# сверить таблицу с новой выгрузкой задач
python3 -m vulnsheet --config vulnsheet.yaml --table report.csv --blocks tasks.txt -o report.csv
```

`-o` может совпадать с `--table`: таблица читается целиком до работы, а
выход заменяется атомарно, поэтому при сбое прогона прежняя таблица
остаётся цела.

Что происходит с колонками:

| Колонки | Новая таблица | Обновление koji и VEX | Синхронизация: строка совпала | Синхронизация: `Missing` | Синхронизация: новая строка |
|---|---|---|---|---|---|
| Разработчик … Принятая мера | `-` | как есть | как есть | как есть | `-` |
| Task ID … Компонент | из блока | как есть | из блока | как есть, `Task state` → `Missing` | из блока |
| `SL NVR` | koji | koji | koji | koji | koji |
| RHEL NVR … Advisory | VEX | VEX | VEX | VEX | VEX |
| `CVE Link` | по CVE | по CVE | по CVE | по CVE | по CVE |
| `Комментарий` | `-` | как есть | как есть | как есть | `-` |

- **Синхронизация** сопоставляет строку и блок по тройке (Task ID, CVE ID,
  Компонент). Пробелы по краям и регистр CVE при этом не важны.
  - Строка, чьей тройки нет в блоках, не удаляется: в `Task state` ставится
    `Missing`.
  - Тройка, которой нет в таблице, становится новой строкой в конце, в
    порядке блоков.
  - Порядок прежних строк не меняется.
  - Если тройка повторяется в блоках, действует первый блок.
  - Строка с битым блоком тоже получает `Missing`: битый блок виден в
    файле отбраковки и по коду 1.
- **Сбой сети.** Если koji вернул `ERROR` или VEX — `fetch error`, у прежней
  строки остаются прежние значения этой группы колонок, а в журнале
  появляется предупреждение. `NOT_FOUND` и `not listed` — это ответы, они
  перезаписывают прежние значения.
- **Строка, по которой нечего спрашивать** (в `CVE ID` не CVE-ID или нет
  компонента), остаётся целиком как есть и не получает `Missing`.
- **Таблица на входе** — ровно то, что пишет vulnsheet: UTF-8 (BOM
  допускается), `;`, кавычки по правилам CSV, тот же заголовок, 20 ячеек в
  каждой строке. Иначе это фатальная ошибка с номером записи: строку с
  ручными данными выбросить нельзя.
````

- [ ] **Step 4: README — «Битые блоки», «Журнал», «Коды возврата», «Разработка»**

- В «Битые блоки» после абзаца о пути файла добавить: «Файл отбраковки ведётся только при `--blocks`: обновление по одной таблице его не трогает.»
- В «Журнал»:
  - строку `warning` дополнить: «строки таблицы, где при сбое оставлены прежние koji или VEX, и строки, по которым нечего спрашивать»;
  - строку `info` начать с «режим; таблица и число строк в ней; при синхронизации — `совпало N, Missing M, новых K`;».
- В «Коды возврата»:
  - строку `1` заменить на: «CSV записан, но есть битые блоки, `ERROR` от koji, `fetch error` (в том числе там, где оставлены прежние значения) или строки таблицы, по которым нечего спрашивать. `Missing` — не ошибка»;
  - в строку `2` после «неверные аргументы» вставить «(в том числе нет ни `--blocks`, ни `--table`, или `--table -`)»;
  - «вход не читается, не в UTF-8 или пуст» заменить на «блоки не читаются, не в UTF-8 или пусты; таблица не читается или не в формате vulnsheet».
- В «Разработка», в таблицу модулей после `report.py` добавить:

```markdown
| `table.py` | чтение и проверка прежней таблицы |
| `merge.py` | слияние прежней таблицы, блоков и ответов koji и VEX — без файлов и сети |
```

  а описание `cli.py` сделать таким: «аргументы, выбор режима, связывание, файл отбраковки, коды возврата».

- [ ] **Step 5: CHANGELOG-и**

В `tools/vulnsheet/CHANGELOG.md` в конец записи `## 1.0.0 — 2026-09-24` дописать абзац:

```markdown
Кроме построения таблицы с нуля (`--blocks`) тулза обновляет уже ведущуюся
таблицу (`--table`), не трогая колонок, которые заполняют люди. Одна
таблица — освежаются только данные koji и VEX. Таблица и блоки — таблица
сверяется с блоками: данные задач обновляются, пропавшие задачи помечаются
`Missing`, новые дописываются в конец. При сбое koji или VEX в строке
остаются прежние значения.
```

В корневом `CHANGELOG.md`, в пункте `vulnsheet` (1.0.0) раздела `[Unreleased]`, перед «Заменяет три разрозненных скрипта.» вставить: «Умеет обновлять уже ведущуюся таблицу, сохраняя ручные колонки: освежать данные koji и VEX или сверять её с новыми блоками — пропавшие задачи помечаются `Missing`, новые дописываются в конец.»

- [ ] **Step 6: Verify**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests && grep -n "input" README.md`
Expected: 178 тестов, OK; в README не осталось строки таблицы аргументов с `input`.

Корневые проверки из `CLAUDE.md` (запускать из корня репозитория):

```bash
for d in tools/*/; do
  grep -oh '](\.\?/\?[^):]*)' "$d"README.md "$d"TODO.md 2>/dev/null |
    sed 's/](//;s/)$//' | grep -v '^#' | sort -u | while read -r f; do
      [ -e "$d$f" ] || echo "BROKEN: $d$f"
    done
done
```

Expected: пусто.

- [ ] **Step 7: Commit**

```bash
git add tools/vulnsheet/README.md tools/vulnsheet/CHANGELOG.md CHANGELOG.md
git commit -m "docs(vulnsheet): document table update modes"
```
