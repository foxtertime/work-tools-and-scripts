# vulnsheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Новая тулза `tools/vulnsheet/`: принимает текстовые блоки задач из тасктрекера, дополняет их данными Red Hat CSAF/VEX и последним билдом из koji и пишет CSV из 20 колонок.

**Architecture:** Python-пакет по образцу `tools/dashboard`: модули с узкими интерфейсами (`tasks` — разбор входа, `kojiclient` — latest-билды, `vex` — загрузка и интерпретация CSAF, `report` — строка таблицы и CSV), связанные в `cli`. Логирование — модуль `logs`, единственное место, где ставится хендлер. Логика интерпретации VEX переносится из `.tmp/vex.py` с зашитыми значениями его флагов по умолчанию.

**Tech Stack:** Python 3.9+, стандартная библиотека, `koji` (системный пакет, импортируется лениво), `unittest`.

**Spec:** `tools/vulnsheet/docs/superpowers/specs/2026-09-24-vulnsheet-design.md`

## Global Constraints

- Все пути ниже — от корня репозитория; команды тестов запускаются из `tools/vulnsheet/`: `python3 -m unittest discover -s tests -v`.
- Python 3.9+: без `X | None`, без `match`; аннотации через `typing`.
- Зависимости: только стандартная библиотека и `koji`. `koji` импортируется только внутри `kojiclient.connect`; в этом окружении `koji` не установлен — тесты его не импортируют.
- Упаковка как у `dashboard`: метаданные в `setup.cfg`, в `pyproject.toml` только `[build-system]` (setuptools 53 в RHEL 9). Версия — только в `vulnsheet/__init__.py`, первая версия `1.0.0`.
- В именах файлов, модулей и тестов нет слова «cve».
- Доступ к koji только на чтение: вызываются лишь `getTag` и `getLatestBuilds`.
- CSV: UTF-8 без BOM, разделитель `;`, строки через `\n`, пустая ячейка — `-`, даты — `dd.mm.yyyy`.
- Логи, сообщения и комментарии в коде — на русском; коммиты — на английском в Conventional Commits со скоупом `vulnsheet`, с футером `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Тесты без сети: koji — `FakeKojiSession`, VEX — подмена `vulnsheet.vex.download`.
- Работа в ветке `feature/vulnsheet`. `.tmp/` и `task.md` в корне не трогать и не коммитить.

## Review Focus

1. **Вход, сохранённый в Windows-редакторе с BOM** — первый блок должен разбираться как обычный, а не уходить в отбраковку из-за `\ufeff` в первой строке. Тест: `test_leading_bom_is_ignored` (Task 2).
2. **Вход не в UTF-8 (cp1251)** — человек ждёт одну понятную строку «вход не в UTF-8» и код 2, а не трейсбек. Тест: `test_non_utf8_input_is_fatal` (Task 7).
3. **Опечатка в имени тега koji** — ждут фатальную ошибку «нет тега …», а не таблицу, где у каждой строки `ERROR`. Тесты: `test_unknown_tag_is_fatal` (Task 3 и Task 7).
4. **Один CVE или компонент в нескольких блоках** — строки на каждый блок в порядке входа, но VEX и koji спрашиваются по одному разу. Тест: `test_order_duplicates_and_single_requests` (Task 7).
5. **Табы и лишние пробелы в строке `CVE-… компонент`, CVE в нижнем регистре** — строка разбирается, CVE приводится к верхнему регистру. Тесты: `test_crlf_and_padding_are_tolerated`, `test_lowercase_cve_is_normalised` (Task 2).

---

## File Structure

```text
tools/vulnsheet/
├── README.md            # Task 8 — точка входа для человека
├── TODO.md              # Task 8
├── CHANGELOG.md         # Task 1 — история версий тулзы
├── pyproject.toml       # Task 1 — только [build-system]
├── setup.cfg            # Task 1 — метаданные, console_scripts
├── vulnsheet/
│   ├── __init__.py      # Task 1 — __version__
│   ├── __main__.py      # Task 7 — python3 -m vulnsheet
│   ├── logs.py          # Task 1 — настройка логирования
│   ├── tasks.py         # Task 2 — Task, Reject, parse()
│   ├── kojiclient.py    # Task 3 — connect(), latest_builds()
│   ├── vex.py           # Task 4 — интерпретация; Task 5 — загрузка и кэш
│   ├── report.py        # Task 6 — COLUMNS, row(), write()
│   └── cli.py           # Task 7 — main(), коды возврата, файл отбраковки
└── tests/
    ├── __init__.py      # Task 1
    ├── fakes.py         # Task 3 — FakeKojiSession; Task 4 — csaf()
    ├── test_logs.py     # Task 1
    ├── test_version.py  # Task 1
    ├── test_tasks.py    # Task 2
    ├── test_kojiclient.py  # Task 3
    ├── test_vex.py      # Task 4, Task 5
    ├── test_report.py   # Task 6
    └── test_cli.py      # Task 7
```

Корень репозитория (Task 8): `README.md` (строка в таблице тулз), `TODO.md` (ссылка в индексе), `CHANGELOG.md` (запись в `[Unreleased]`).

---

### Task 1: Каркас пакета, логирование, версия

**Files:**
- Create: `tools/vulnsheet/pyproject.toml`
- Create: `tools/vulnsheet/setup.cfg`
- Create: `tools/vulnsheet/CHANGELOG.md`
- Create: `tools/vulnsheet/vulnsheet/__init__.py`
- Create: `tools/vulnsheet/vulnsheet/logs.py`
- Create: `tools/vulnsheet/tests/__init__.py`
- Test: `tools/vulnsheet/tests/test_logs.py`, `tools/vulnsheet/tests/test_version.py`

**Interfaces:**
- Produces: `vulnsheet.__version__: str` (`"1.0.0"`); `vulnsheet.logs.LEVELS: Dict[str, int]`, `logs.DEFAULT_LEVEL = "info"`, `logs.configure(level: str = "info", stream=None) -> None` (поднимает `ValueError` на неизвестный уровень; `stream=None` — `sys.stderr`, читаемый в момент вызова).

- [ ] **Step 1: Создать упаковку и пустой пакет**

`tools/vulnsheet/pyproject.toml`:

```toml
# Только объявление сборщика. Метаданные лежат в setup.cfg: setuptools
# читает [project] из pyproject лишь с 61-й версии, а в RHEL 9 стоит 53-я.
[build-system]
requires = ["setuptools>=40.8"]
build-backend = "setuptools.build_meta"
```

`tools/vulnsheet/setup.cfg`:

```ini
[metadata]
name = vulnsheet
# Номер версии написан в одном месте — vulnsheet/__init__.py.
version = attr: vulnsheet.__version__
description = Таблица задач по уязвимостям с данными Red Hat VEX и koji

[options]
packages = vulnsheet
python_requires = >=3.9
# koji здесь не перечислен нарочно: его ставят системным пакетом
# (python3-koji), собранным под тот же питон, см. README.

[options.entry_points]
console_scripts =
    vulnsheet = vulnsheet.cli:main
```

`tools/vulnsheet/vulnsheet/__init__.py`:

```python
"""vulnsheet — таблица задач по уязвимостям с данными Red Hat VEX и koji."""

__version__ = "1.0.0"
```

`tools/vulnsheet/tests/__init__.py` — пустой файл.

`tools/vulnsheet/CHANGELOG.md`:

```markdown
# Changelog — vulnsheet

Изменения тулзы `vulnsheet`, от свежих к старым. Версия тулзы независима от
версии репозитория.

## 1.0.0 — 2026-09-24

Первая версия. Один запуск вместо трёх скриптов: блоки задач из тасктрекера
разбираются, для каждой CVE и компонента из Red Hat CSAF/VEX берутся статус,
severity, CVSS и данные фикса, из koji — последний билд компонента в теге, и
всё это пишется в CSV из двадцати колонок. Битые блоки не теряются, а
дословно уходят в отдельный файл, чтобы их можно было поправить и подать
снова.
```

- [ ] **Step 2: Написать падающие тесты логирования и версии**

`tools/vulnsheet/tests/test_logs.py`:

```python
import io
import logging
import unittest

from vulnsheet import logs


class ConfigureTest(unittest.TestCase):
    def tearDown(self):
        logs.configure("info", stream=io.StringIO())

    def _handlers(self):
        return [h for h in logging.getLogger("vulnsheet").handlers
                if not isinstance(h, logging.NullHandler)]

    def test_repeated_configure_keeps_one_handler(self):
        # Второй хендлер задвоил бы каждую строку журнала.
        logs.configure("info", stream=io.StringIO())
        logs.configure("info", stream=io.StringIO())
        self.assertEqual(len(self._handlers()), 1)

    def test_module_name_is_shortened(self):
        stream = io.StringIO()
        logs.configure("info", stream=stream)
        logging.getLogger("vulnsheet.kojiclient").warning("нет тега")
        self.assertRegex(stream.getvalue(),
                         r"^\d\d:\d\d:\d\d WARNING koji: нет тега\n$")

    def test_debug_adds_thread_name(self):
        stream = io.StringIO()
        logs.configure("debug", stream=stream)
        logging.getLogger("vulnsheet.vex").debug("из кэша")
        self.assertIn("[MainThread] vex: из кэша", stream.getvalue())

    def test_records_below_level_are_dropped(self):
        stream = io.StringIO()
        logs.configure("warning", stream=stream)
        logging.getLogger("vulnsheet.cli").info("написан report.csv")
        self.assertEqual(stream.getvalue(), "")

    def test_unknown_level_is_rejected(self):
        with self.assertRaises(ValueError):
            logs.configure("verbose")
```

`tools/vulnsheet/tests/test_version.py`:

```python
"""Номер версии живёт в vulnsheet/__init__.py; тесты сторожат его форму и
запись в CHANGELOG тулзы. Флаг --version проверяет test_cli."""
import os
import unittest

from vulnsheet import __version__

CHANGELOG = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")


class VersionTest(unittest.TestCase):
    def test_version_is_three_numbers(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_changelog_names_the_current_version(self):
        # Покрасневший тест значит забытую запись в CHANGELOG, а не
        # сломанный код.
        with open(CHANGELOG, encoding="utf-8") as handle:
            self.assertIn("## %s " % __version__, handle.read())
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: `test_logs` падает с `ImportError: cannot import name 'logs'`; `test_version` проходит.

- [ ] **Step 4: Написать `logs.py`**

`tools/vulnsheet/vulnsheet/logs.py`:

```python
"""Настройка логирования — единственное место, где ставятся хендлеры.

Модули пакета только пишут через logging.getLogger(__name__); настраивает
всё исключительно CLI, чтобы импорт пакета чужим кодом не менял его
логирование.
"""
import logging
import sys

ROOT = "vulnsheet"
DEFAULT_LEVEL = "info"
LEVELS = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

_TIME_FORMAT = "%H:%M:%S"
_FORMAT = "%(asctime)s %(levelname)-7s %(shortname)s: %(message)s"
# VEX грузится пулом потоков: без имени потока дебажный лог не читается
_DEBUG_FORMAT = ("%(asctime)s %(levelname)-7s [%(threadName)s] "
                 "%(shortname)s: %(message)s")


class _ShortName(logging.Filter):
    """vulnsheet.kojiclient → koji, vulnsheet.cli → cli."""

    def filter(self, record) -> bool:
        name = record.name.split(".")[-1]
        if name.endswith("client"):
            name = name[:-len("client")]
        record.shortname = name
        return True


def configure(level: str = DEFAULT_LEVEL, stream=None) -> None:
    """Ставит единственный хендлер на логгер пакета.

    Повторный вызов заменяет хендлер, а не добавляет второй: иначе тесты и
    повторная инициализация давали бы дублирующиеся строки.
    """
    if level not in LEVELS:
        raise ValueError("неизвестный уровень логирования: %s" % level)
    numeric = LEVELS[level]

    logger = logging.getLogger(ROOT)
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    fmt = _DEBUG_FORMAT if numeric <= logging.DEBUG else _FORMAT
    handler.setFormatter(logging.Formatter(fmt, _TIME_FORMAT))
    handler.addFilter(_ShortName())
    handler.setLevel(numeric)

    logger.addHandler(handler)
    logger.setLevel(numeric)
    # записи пакета не должны уходить в корневой логгер: если приложение
    # настроило свой basicConfig, строки задвоятся
    logger.propagate = False
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: 7 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/pyproject.toml tools/vulnsheet/setup.cfg tools/vulnsheet/CHANGELOG.md \
        tools/vulnsheet/vulnsheet/__init__.py tools/vulnsheet/vulnsheet/logs.py \
        tools/vulnsheet/tests/__init__.py tools/vulnsheet/tests/test_logs.py tools/vulnsheet/tests/test_version.py
git commit -m "feat(vulnsheet): add package skeleton with logging setup

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Разбор блоков входа

**Files:**
- Create: `tools/vulnsheet/vulnsheet/tasks.py`
- Test: `tools/vulnsheet/tests/test_tasks.py`

**Interfaces:**
- Produces:
  - `Task(NamedTuple)`: `task_id: str, cve: str, component: str, state: str, date: str, assignee: str`
  - `Reject(NamedTuple)`: `number: int` (номер блока с единицы, считая и годные), `text: str` (блок дословно, строки через `\n`), `reason: str`
  - `parse(text: str) -> Tuple[List[Task], List[Reject]]`

- [ ] **Step 1: Написать падающие тесты**

`tools/vulnsheet/tests/test_tasks.py`:

```python
import unittest

from vulnsheet.tasks import Reject, Task, parse

BLOCK = "Состоит из\nTASKID-181229\nCVE-2026-73070 vim\nОтменен\n22.09.2026\nКМ"
VIM = Task("TASKID-181229", "CVE-2026-73070", "vim", "Отменен", "22.09.2026", "КМ")


class ParseTest(unittest.TestCase):
    def test_block_from_the_task(self):
        self.assertEqual(parse(BLOCK + "\n"), ([VIM], []))

    def test_blocks_split_by_blank_lines_keep_order(self):
        second = BLOCK.replace("181229", "181230").replace("vim", "openssl")
        tasks, rejects = parse(BLOCK + "\n\n\n" + second + "\n")
        self.assertEqual([t.task_id for t in tasks], ["TASKID-181229", "TASKID-181230"])
        self.assertEqual([t.component for t in tasks], ["vim", "openssl"])
        self.assertEqual(rejects, [])

    def test_whitespace_only_line_separates_blocks(self):
        tasks, rejects = parse(BLOCK + "\n   \t\n" + BLOCK)
        self.assertEqual(tasks, [VIM, VIM])
        self.assertEqual(rejects, [])

    def test_crlf_and_padding_are_tolerated(self):
        text = ("  Состоит из \r\n TASKID-181229\r\nCVE-2026-73070\t  vim  \r\n"
                "Отменен\r\n22.09.2026\r\nКМ \r\n")
        self.assertEqual(parse(text), ([VIM], []))

    def test_lowercase_cve_is_normalised(self):
        tasks, _ = parse(BLOCK.replace("CVE-2026-73070", "cve-2026-73070"))
        self.assertEqual(tasks[0].cve, "CVE-2026-73070")

    def test_leading_bom_is_ignored(self):
        # Файлы из Windows-редакторов начинаются с BOM.
        self.assertEqual(parse("\ufeff" + BLOCK), ([VIM], []))

    def test_empty_input(self):
        self.assertEqual(parse(""), ([], []))
        self.assertEqual(parse("\n  \n\n"), ([], []))


class RejectTest(unittest.TestCase):
    def _only_reject(self, text):
        tasks, rejects = parse(text)
        self.assertEqual(tasks, [])
        self.assertEqual(len(rejects), 1)
        return rejects[0]

    def test_five_lines(self):
        reject = self._only_reject(BLOCK.rsplit("\n", 1)[0])
        self.assertIn("5 строк", reject.reason)

    def test_seven_lines(self):
        self.assertIn("7 строк", self._only_reject(BLOCK + "\nлишнее").reason)

    def test_dashes_are_an_ordinary_line(self):
        # Разделитель блоков — только пустая строка.
        self.assertIn("7 строк", self._only_reject("---\n" + BLOCK).reason)

    def test_third_line_without_component(self):
        reject = self._only_reject(BLOCK.replace("CVE-2026-73070 vim", "CVE-2026-73070"))
        self.assertIn("нет компонента", reject.reason)

    def test_third_line_without_cve(self):
        reject = self._only_reject(BLOCK.replace("CVE-2026-73070 vim", "vim CVE-2026-73070"))
        self.assertIn("CVE-ID", reject.reason)

    def test_reject_keeps_number_and_block_verbatim(self):
        bad = "Состоит из\nTASKID-2\n  CVE-2026-73070\nВ работу\n23.09.2026\nКМ"
        tasks, rejects = parse(BLOCK + "\n\n" + bad + "\n\n" + BLOCK)
        self.assertEqual(tasks, [VIM, VIM])
        self.assertEqual([(r.number, r.text) for r in rejects], [(2, bad)])
        self.assertIsInstance(rejects[0], Reject)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_tasks -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.tasks'`.

- [ ] **Step 3: Написать `tasks.py`**

`tools/vulnsheet/vulnsheet/tasks.py`:

```python
"""Разбор блоков задач, скопированных из тасктрекера.

Блок — шесть непустых строк, блоки разделены пустой строкой:

    Состоит из
    TASKID-181229
    CVE-2026-73070 vim
    Отменен
    22.09.2026
    КМ
"""
import re
from typing import List, NamedTuple, Tuple

BLOCK_LINES = 6
CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")


class Task(NamedTuple):
    task_id: str
    cve: str
    component: str
    state: str
    date: str
    assignee: str


class Reject(NamedTuple):
    """Блок, который не удалось разобрать: номер, текст дословно и причина."""
    number: int
    text: str
    reason: str


def parse(text: str) -> Tuple[List[Task], List[Reject]]:
    tasks, rejects = [], []
    for number, raw in enumerate(_split_blocks(text), 1):
        try:
            tasks.append(_task(raw))
        except ValueError as exc:
            rejects.append(Reject(number, raw, str(exc)))
    return tasks, rejects


def _split_blocks(text: str) -> List[str]:
    """Блоки как есть; разделитель — только пустая (или пробельная) строка."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks, current = [], []
    for line in text.split("\n"):
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def _task(raw: str) -> Task:
    lines = [line.strip() for line in raw.split("\n")]
    if len(lines) != BLOCK_LINES:
        raise ValueError("в блоке %d строк, ожидается %d" % (len(lines), BLOCK_LINES))
    head = lines[2].split(None, 1)
    cve = head[0].upper()
    if not CVE_RE.match(cve):
        raise ValueError("третья строка не начинается с CVE-ID: %r" % lines[2])
    if len(head) < 2:
        raise ValueError("в третьей строке нет компонента: %r" % lines[2])
    return Task(task_id=lines[1], cve=cve, component=head[1].strip(),
                state=lines[3], date=lines[4], assignee=lines[5])
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_tasks -v`
Expected: 13 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/tasks.py tools/vulnsheet/tests/test_tasks.py
git commit -m "feat(vulnsheet): parse task blocks and collect malformed ones

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Последние билды из koji

**Files:**
- Create: `tools/vulnsheet/vulnsheet/kojiclient.py`
- Create: `tools/vulnsheet/tests/fakes.py`
- Test: `tools/vulnsheet/tests/test_kojiclient.py`

**Interfaces:**
- Produces:
  - `kojiclient.NOT_FOUND = "NOT_FOUND"`, `kojiclient.ERROR = "ERROR"`
  - `class KojiError(Exception)` — хаб недоступен, тега нет, модуль `koji` не установлен
  - `connect(hub_url: str)` → `koji.ClientSession`
  - `latest_builds(session, tag: str, packages: Iterable[str]) -> Dict[str, str]` — `{пакет: NVR | NOT_FOUND | ERROR}` по уникальным пакетам
  - `tests.fakes.FakeKojiSession(builds=None, errors=None, tags=("sl9",), hub_down=False, multicall_down=False)` с атрибутом `calls: List[Tuple[str, str]]` — `(tag, package)` каждого `getLatestBuilds`

- [ ] **Step 1: Написать подделку сессии koji**

`tools/vulnsheet/tests/fakes.py`:

```python
"""Подделки внешних систем для тестов. Сети здесь нет."""


class _Call:
    """Отложенный результат, как koji.VirtualCall: ошибка — при чтении .result."""

    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error

    @property
    def result(self):
        if self._error is not None:
            raise self._error
        return self._value


class _Multicall:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self._session.multicall_down:
            raise ConnectionError("multicall: соединение сброшено")
        return False

    def getLatestBuilds(self, tag, package=None):
        self._session.calls.append((tag, package))
        if package in self._session.errors:
            return _Call(error=RuntimeError(self._session.errors[package]))
        nvr = self._session.builds.get(package)
        return _Call([{"nvr": nvr}] if nvr else [])


class FakeKojiSession:
    """koji.ClientSession в объёме, нужном kojiclient: getTag и multicall."""

    def __init__(self, builds=None, errors=None, tags=("sl9",),
                 hub_down=False, multicall_down=False):
        self.builds = dict(builds or {})
        self.errors = dict(errors or {})
        self.tags = set(tags)
        self.hub_down = hub_down
        self.multicall_down = multicall_down
        self.calls = []

    def getTag(self, tag):
        if self.hub_down:
            raise ConnectionError("хаб недоступен")
        return {"name": tag} if tag in self.tags else None

    def multicall(self, strict=False):
        return _Multicall(self)
```

- [ ] **Step 2: Написать падающие тесты**

`tools/vulnsheet/tests/test_kojiclient.py`:

```python
import sys
import unittest
from unittest import mock

from tests.fakes import FakeKojiSession
from vulnsheet.kojiclient import ERROR, NOT_FOUND, KojiError, connect, latest_builds


class LatestBuildsTest(unittest.TestCase):
    def test_found_missing_and_failed_packages(self):
        session = FakeKojiSession(builds={"vim": "vim-8.2-1.sl9"}, errors={"bash": "boom"})
        with self.assertLogs("vulnsheet", "WARNING") as caught:
            got = latest_builds(session, "sl9", ["vim", "zsh", "bash"])
        self.assertEqual(got, {"vim": "vim-8.2-1.sl9", "zsh": NOT_FOUND, "bash": ERROR})
        joined = "\n".join(caught.output)
        self.assertIn("zsh", joined)
        self.assertIn("boom", joined)

    def test_each_package_is_asked_once(self):
        session = FakeKojiSession(builds={"vim": "vim-8.2-1.sl9"})
        latest_builds(session, "sl9", ["vim", "vim", "vim"])
        self.assertEqual(session.calls, [("sl9", "vim")])

    def test_no_packages_means_no_calls(self):
        session = FakeKojiSession(hub_down=True)
        self.assertEqual(latest_builds(session, "sl9", []), {})

    def test_unknown_tag_is_fatal(self):
        # Опечатка в теге — одна ошибка, а не таблица из одних ERROR.
        with self.assertRaises(KojiError) as caught:
            latest_builds(FakeKojiSession(tags=["sl9"]), "sl-9", ["vim"])
        self.assertIn("sl-9", str(caught.exception))

    def test_unreachable_hub_is_fatal(self):
        with self.assertRaises(KojiError):
            latest_builds(FakeKojiSession(hub_down=True), "sl9", ["vim"])

    def test_failed_multicall_is_fatal(self):
        with self.assertRaises(KojiError):
            latest_builds(FakeKojiSession(multicall_down=True), "sl9", ["vim"])


class ConnectTest(unittest.TestCase):
    def test_missing_koji_module_is_reported(self):
        with mock.patch.dict(sys.modules, {"koji": None}):
            with self.assertRaises(KojiError) as caught:
                connect("https://koji.example.com/kojihub")
        self.assertIn("koji", str(caught.exception))
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_kojiclient -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.kojiclient'`.

- [ ] **Step 4: Написать `kojiclient.py`**

`tools/vulnsheet/vulnsheet/kojiclient.py`:

```python
"""Последние билды пакетов в koji-теге. Доступ только на чтение."""
import logging
import time
from typing import Dict, Iterable

logger = logging.getLogger(__name__)

NOT_FOUND = "NOT_FOUND"
ERROR = "ERROR"


class KojiError(Exception):
    """Хаб недоступен, тега нет или не установлен модуль koji."""


def connect(hub_url: str):
    try:
        import koji  # системный пакет python3-koji; нужен только здесь
    except ImportError as exc:
        raise KojiError("не установлен модуль koji (python3-koji): %s" % exc)
    return koji.ClientSession(hub_url)


def latest_builds(session, tag: str, packages: Iterable[str]) -> Dict[str, str]:
    """{пакет: NVR последнего билда в теге | NOT_FOUND | ERROR}.

    Каждый пакет спрашивается один раз, все — одним multicall.
    """
    packages = list(dict.fromkeys(packages))
    if not packages:
        return {}
    started = time.monotonic()
    try:
        if session.getTag(tag) is None:
            raise KojiError("в koji нет тега %s" % tag)
        with session.multicall(strict=False) as multicall:
            calls = [multicall.getLatestBuilds(tag, package=pkg) for pkg in packages]
    except KojiError:
        raise
    except Exception as exc:
        raise KojiError("хаб не ответил по тегу %s: %s" % (tag, exc))
    logger.debug("getLatestBuilds %s: %d пакетов за %.2f с", tag, len(packages),
                 time.monotonic() - started)

    result = {}
    for pkg, call in zip(packages, calls):
        try:
            builds = call.result
        except Exception as exc:  # ошибка по одному пакету не роняет остальные
            logger.warning("koji не ответил по пакету %s: %s", pkg, exc)
            result[pkg] = ERROR
            continue
        result[pkg] = builds[0]["nvr"] if builds else NOT_FOUND

    missing = [pkg for pkg in packages if result[pkg] == NOT_FOUND]
    if missing:
        logger.warning("в теге %s нет пакетов (%d): %s", tag, len(missing),
                       ", ".join(missing))
    return result
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_kojiclient -v`
Expected: 7 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/vulnsheet/kojiclient.py tools/vulnsheet/tests/fakes.py tools/vulnsheet/tests/test_kojiclient.py
git commit -m "feat(vulnsheet): look up latest koji builds per package

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Интерпретация VEX

Логика переносится из `.tmp/vex.py` (функции `rhel_version`, `index_tree`, `index_relationships`, `build_indices`, `split_product`, `component_name`, `build_remediation_index`, `state_for`, `cvss_for`, `errata_for`, `nvr_for`, `lookup`) с зашитыми значениями бывших флагов: `--match exact`, без `--include-minor`, без `--include-variants`, без `--with-epoch`. Запросы module-стримов вида `nginx:1.26` не поддерживаются: компонент во входе — имя пакета.

**Files:**
- Create: `tools/vulnsheet/vulnsheet/vex.py`
- Modify: `tools/vulnsheet/tests/fakes.py` (дописать в конец)
- Test: `tools/vulnsheet/tests/test_vex.py`

**Interfaces:**
- Produces:
  - `Verdict(NamedTuple)`: `state: str = ""`, `severity: str = ""`, `cvss: str = ""`, `fixed_nvr: str = ""`, `fix_date: str = ""` (ISO `YYYY-MM-DD`), `advisory_url: str = ""`
  - константы `NO_RECORD = "no VEX record"`, `NOT_LISTED = "not listed"`, `FETCH_ERROR = "fetch error"`, `FIXED = "Fixed"`
  - `parse_rhel(value: str) -> str` — `ValueError` на невалидное
  - `build_index(doc: dict) -> dict` — `KeyError`/`IndexError`/`TypeError` на испорченный документ
  - `lookup(index: Optional[dict], component: str, rhel: str) -> Verdict`
  - `tests.fakes.csaf(cve, statuses, severity="Moderate", scores=(), remediations=())`, `tests.fakes.pid(platform, component) -> str`, платформы `RHEL9`, `APPSTREAM96`, `BASEOS96`, `EUS92`, `RHEL_AI`

- [ ] **Step 1: Дописать сборщик CSAF в `tests/fakes.py`**

Добавить в конец `tools/vulnsheet/tests/fakes.py`:

```python
# Платформы CSAF: (product_id, cpe). Версию RHEL тулза берёт из cpe.
RHEL9 = ("red_hat_enterprise_linux_9", "cpe:/o:redhat:enterprise_linux:9")
APPSTREAM96 = ("AppStream-9.6.0.Z.MAIN", "cpe:/a:redhat:enterprise_linux:9::appstream")
BASEOS96 = ("BaseOS-9.6.0.Z.MAIN", "cpe:/o:redhat:enterprise_linux:9::baseos")
EUS92 = ("AppStream-9.2.0.Z.EUS", "cpe:/a:redhat:rhel_eus:9.2::appstream")
RHEL_AI = ("RHEL-AI-9", "cpe:/a:redhat:enterprise_linux_ai:9")


def pid(platform, component):
    """Составной product_id, каким его пишет Red Hat: платформа:компонент."""
    return "%s:%s" % (platform[0], component)


def csaf(cve, statuses, severity="Moderate", scores=(), remediations=()):
    """Минимальный CSAF/VEX-документ.

    statuses — [(bucket, платформа, component_id)], где bucket — ключ
    product_status (fixed, known_affected, known_not_affected,
    under_investigation).
    """
    platforms, relationships, status = {}, [], {}
    for bucket, platform, component in statuses:
        platforms[platform[0]] = platform[1]
        composite = pid(platform, component)
        relationships.append({
            "full_product_name": {"product_id": composite},
            "relates_to_product_reference": platform[0],
            "product_reference": component,
        })
        status.setdefault(bucket, []).append(composite)
    branches = [{"product": {"product_id": product_id,
                             "product_identification_helper": {"cpe": cpe}}}
                for product_id, cpe in platforms.items()]
    return {
        "document": {"aggregate_severity": {"text": severity}},
        "product_tree": {"branches": branches, "relationships": relationships},
        "vulnerabilities": [{"cve": cve, "product_status": status,
                             "scores": list(scores),
                             "remediations": list(remediations)}],
    }
```

- [ ] **Step 2: Написать падающие тесты**

`tools/vulnsheet/tests/test_vex.py`:

```python
import unittest

from tests.fakes import APPSTREAM96, BASEOS96, EUS92, RHEL9, RHEL_AI, csaf, pid
from vulnsheet.vex import NO_RECORD, Verdict, build_index, lookup, parse_rhel

CVE = "CVE-2026-1000"
FIXED_VIM = "vim-2:8.2.2637-22.el9_6.x86_64"
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"


def vendor_fix(*pids, date="2026-09-02T00:00:00+00:00", url=RHSA):
    return {"category": "vendor_fix", "product_ids": list(pids), "url": url, "date": date}


def score(value, *pids):
    return {"cvss_v3": {"baseScore": value, "vectorString": "CVSS:3.1/AV:L"},
            "products": list(pids)}


class LookupTest(unittest.TestCase):
    def verdict(self, doc, component="vim", rhel="9"):
        return lookup(build_index(doc), component, rhel)

    def test_fixed_carries_nvr_date_and_advisory(self):
        fixed = pid(APPSTREAM96, FIXED_VIM)
        doc = csaf(CVE, [("fixed", APPSTREAM96, FIXED_VIM)],
                   scores=[score(7.8, fixed)], remediations=[vendor_fix(fixed)])
        self.assertEqual(self.verdict(doc), Verdict(
            state="Fixed", severity="Moderate", cvss="7.8",
            fixed_nvr="vim-8.2.2637-22.el9_6", fix_date="2026-09-02",
            advisory_url=RHSA))

    def test_will_not_fix_comes_from_remediation(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")], remediations=[
            {"category": "no_fix_planned", "details": "Will not fix",
             "product_ids": [pid(RHEL9, "vim")]}])
        verdict = self.verdict(doc)
        self.assertEqual(verdict.state, "Will not fix")
        self.assertEqual((verdict.fixed_nvr, verdict.advisory_url), ("", ""))

    def test_affected_without_remediation(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")])
        self.assertEqual(self.verdict(doc).state, "Affected")

    def test_under_investigation_takes_the_agreed_score(self):
        # Продукта нет ни в одном блоке оценок, но все блоки согласны.
        doc = csaf(CVE, [("under_investigation", RHEL9, "vim")],
                   scores=[score(5.5, "другой-продукт")])
        verdict = self.verdict(doc)
        self.assertEqual((verdict.state, verdict.cvss), ("Under investigation", "5.5"))

    def test_not_affected(self):
        doc = csaf(CVE, [("known_not_affected", RHEL9, "vim")])
        self.assertEqual(self.verdict(doc).state, "Not affected")

    def test_zero_cvss_is_kept(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")],
                   scores=[score(0.0, pid(RHEL9, "vim"))])
        self.assertEqual(self.verdict(doc).cvss, "0.0")

    def test_flatpak_stream_is_not_the_package(self):
        fixed = pid(APPSTREAM96, "firefox-0:128.0-1.el9_6.x86_64")
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak"),
                         ("fixed", APPSTREAM96, "firefox-0:128.0-1.el9_6.x86_64")],
                   remediations=[vendor_fix(fixed)])
        verdict = self.verdict(doc, "firefox")
        self.assertEqual((verdict.state, verdict.fixed_nvr),
                         ("Fixed", "firefox-128.0-1.el9_6"))

    def test_stream_is_reported_when_nothing_else(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak")])
        self.assertEqual(self.verdict(doc, "firefox").state, "Affected")

    def test_minor_stream_only_is_not_listed_with_hint(self):
        doc = csaf(CVE, [("fixed", EUS92, "vim-2:8.2.2637-20.el9_2.x86_64")])
        verdict = self.verdict(doc)
        self.assertEqual(verdict.state, "not listed (present for 9.2)")
        self.assertEqual(verdict.severity, "Moderate")

    def test_absent_component_is_not_listed(self):
        doc = csaf(CVE, [("fixed", APPSTREAM96, FIXED_VIM)])
        self.assertEqual(self.verdict(doc, "emacs").state, "not listed")

    def test_component_match_is_exact(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim-enhanced")])
        self.assertEqual(self.verdict(doc).state, "not listed")

    def test_other_red_hat_products_are_ignored(self):
        doc = csaf(CVE, [("known_affected", RHEL_AI, "vim")])
        self.assertEqual(self.verdict(doc).state, "not listed")

    def test_most_exposed_verdict_wins(self):
        fixed = pid(BASEOS96, FIXED_VIM)
        doc = csaf(CVE, [("fixed", BASEOS96, FIXED_VIM),
                         ("known_affected", APPSTREAM96, "vim")],
                   remediations=[vendor_fix(fixed)])
        verdict = self.verdict(doc)
        self.assertEqual((verdict.state, verdict.fixed_nvr, verdict.advisory_url),
                         ("Affected", "", ""))

    def test_no_document_means_no_record(self):
        self.assertEqual(lookup(None, "vim", "9"), Verdict(state=NO_RECORD))


class ParseRhelTest(unittest.TestCase):
    def test_accepted_spellings(self):
        for value, want in [("9", "9"), ("9.2", "9.2"), ("RHEL 9", "9"),
                            ("rhel-9", "9"), ("el9", "9"), ("RHEL9.4", "9.4")]:
            with self.subTest(value=value):
                self.assertEqual(parse_rhel(value), want)

    def test_rejected_values(self):
        for value in ["", "nine", "9.x", "rhel"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_rhel(value)
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.vex'`.

- [ ] **Step 4: Написать интерпретирующую часть `vex.py`**

`tools/vulnsheet/vulnsheet/vex.py`:

```python
"""Статус CVE для компонента в RHEL по Red Hat CSAF/VEX.

Лента VEX на security.access.redhat.com — тот же источник, из которого
рисуется портал CVE Red Hat, и самый свежий: legacy API /hydra отстаёт на
недели.
"""
import logging
import re
from typing import NamedTuple, Optional

logger = logging.getLogger(__name__)

NO_RECORD = "no VEX record"
NOT_LISTED = "not listed"
FETCH_ERROR = "fetch error"
FIXED = "Fixed"

VERSION_RE = re.compile(r"^\d+(\.\d+)*$")

# Семейства CPE, означающие саму ОС RHEL во всех потоках поддержки. Всё
# остальное — другой продукт с похожей на RHEL версией (enterprise_linux_ai,
# rhel_software_collections, ceph_storage…), и за RHEL его выдавать нельзя.
RHEL_FAMILIES = {
    "enterprise_linux", "enterprise_linux_eus", "rhel_eus", "rhel_e4s",
    "rhel_aus", "rhel_tus", "rhel_els", "rhel_eus_long_life",
    "rhel_mission_critical", "rhel_extras_rt",
}
CPE_RE = re.compile(r"cpe:/[oah]:redhat:([a-z_0-9]+):(\d+(?:\.\d+)*)")
ARCH_SUFFIX = re.compile(
    r"\.(src|noarch|i[3-6]86|x86_64|ia64|aarch64|armv7hl|armv7hnl|"
    r"ppc|ppc64|ppc64le|s390|s390x|riscv64)$")

# Корзина product_status → состояние, как его пишет портал. known_affected
# уточняется ремедиацией (см. _state_for).
BUCKET_STATE = {
    "fixed": FIXED,
    "known_not_affected": "Not affected",
    "under_investigation": "Under investigation",
    "known_affected": "Affected",
}

# Если у одного компонента под одной версией RHEL несколько вердиктов
# (BaseOS и AppStream расходятся), побеждает самый опасный: фикс в одном
# репозитории не должен прятать уязвимость в другом.
STATE_RANK = {
    "Affected": 0,
    "Fix deferred": 1,
    "Will not fix": 2,
    "Out of support scope": 3,
    "Under investigation": 4,
    FIXED: 5,
    "Not affected": 6,
}


class Verdict(NamedTuple):
    state: str = ""
    severity: str = ""
    cvss: str = ""
    fixed_nvr: str = ""
    fix_date: str = ""  # ISO, YYYY-MM-DD
    advisory_url: str = ""


def parse_rhel(value: str) -> str:
    """'RHEL 9' / 'rhel-9' / 'el9' → '9'; '9.2' остаётся '9.2'."""
    rhel = re.sub(r"^(rhel|el)[-_ ]*", "", str(value).strip(), flags=re.I)
    if not VERSION_RE.match(rhel):
        raise ValueError("версия RHEL должна быть вида 9 или 9.2, получено %r" % value)
    return rhel


# --------------------------------------------------------------------------
# индекс документа
# --------------------------------------------------------------------------

def build_index(doc: dict) -> dict:
    """Всё, что нужно lookup, — один раз на CVE, а не на каждую строку."""
    vuln = doc["vulnerabilities"][0]
    cpes, pkgs = _index_tree(doc)
    return {
        "cve": vuln.get("cve", ""),
        "vuln": vuln,
        "cpes": cpes,
        "pkgs": pkgs,
        "rels": {rel["full_product_name"]["product_id"]:
                 (rel["relates_to_product_reference"], rel["product_reference"])
                 for rel in doc.get("product_tree", {}).get("relationships", [])},
        "rem": _remediation_index(vuln),
        "severity": doc["document"].get("aggregate_severity", {}).get("text", ""),
    }


def _index_tree(doc):
    """product_id → cpe и product_id → имя пакета (из purl)."""
    cpes, pkgs = {}, {}

    def walk(branches):
        for branch in branches:
            product = branch.get("product")
            if product:
                product_id = product["product_id"]
                helper = product.get("product_identification_helper", {})
                if helper.get("cpe"):
                    cpes[product_id] = helper["cpe"]
                match = re.match(r"pkg:[^/]+/(?:redhat/)?([^@?]+)", helper.get("purl") or "")
                if match:
                    pkgs[product_id] = match.group(1)
            walk(branch.get("branches", []))

    walk(doc.get("product_tree", {}).get("branches", []))
    return cpes, pkgs


def _remediation_index(vuln):
    index = {}
    for rem in vuln.get("remediations", []):
        for product_id in rem.get("product_ids", []):
            index.setdefault(product_id, []).append(rem)
    return index


# --------------------------------------------------------------------------
# разбор одного продукта
# --------------------------------------------------------------------------

def _rhel_version(cpe):
    """'cpe:/o:redhat:enterprise_linux:9::baseos' → '9'; не RHEL → None."""
    match = CPE_RE.match(cpe or "")
    if not match:
        return None
    family, version = match.groups()
    return version if family in RHEL_FAMILIES else None


def _split_product(product_id, rels):
    if product_id in rels:
        return rels[product_id]
    platform, _, component = product_id.partition(":")
    return platform, component


def _component_name(component_id, pkgs):
    if component_id in pkgs:
        return pkgs[component_id]
    plain = component_id.split("::", 1)[0]
    return ARCH_SUFFIX.sub("", re.sub(r"-\d+:.*$", "", plain))


def _state_for(product_id, bucket, rem_index):
    """Для known_affected точное состояние ('Will not fix', 'Fix deferred',
    'Out of support scope') Red Hat пишет в details ремедиации."""
    if bucket != "known_affected":
        return BUCKET_STATE.get(bucket, bucket)
    for rem in rem_index.get(product_id, []):
        if rem.get("category") in ("no_fix_planned", "none_available"):
            details = (rem.get("details") or "").strip()
            if details:
                return details
    return "Affected"


def _cvss_for(product_id, vuln):
    """Оценка продукта. Если продукта нет ни в одном блоке — только когда
    все блоки согласны: чужая оценка хуже, чем никакой."""
    scores = vuln.get("scores", [])
    chosen = next((s for s in scores if product_id in s.get("products", [])), None)
    if chosen is None:
        distinct = set()
        for block in scores:
            for key in ("cvss_v4", "cvss_v3"):
                if block.get(key):
                    distinct.add(block[key].get("baseScore", ""))
                    break
        return distinct.pop() if len(distinct) == 1 else ""
    for key in ("cvss_v4", "cvss_v3"):
        if chosen.get(key):
            return chosen[key].get("baseScore", "")
    return ""


def _date_key(date):
    """Свежие errata первыми, без даты — последними."""
    try:
        return tuple(-int(part) for part in date.split("-"))
    except ValueError:
        return (0, 0, 0)


def _errata_for(product_id, rem_index):
    """(url, дата ISO) самой свежей vendor_fix-ремедиации."""
    fixes = [r for r in rem_index.get(product_id, [])
             if r.get("category") == "vendor_fix" and r.get("url")]
    if not fixes:
        return "", ""
    newest = min(fixes, key=lambda r: _date_key((r.get("date") or "")[:10]))
    return newest["url"], (newest.get("date") or "")[:10]


def _nvr_for(component_id):
    """'openssl-1:3.5.8-1.el9_8.x86_64' → 'openssl-3.5.8-1.el9_8'.

    Эпоха срезается, чтобы NVR сравнивался с выводом `rpm -q`. Имя RPM не
    содержит двоеточия, поэтому первое '-<цифры>:' — всегда эпоха. У
    неисправленного продукта версии нет — пустая строка.
    """
    plain = component_id.split("::", 1)[0]
    if ":" not in plain:
        return ""
    return re.sub(r"-\d+:", "-", ARCH_SUFFIX.sub("", plain), count=1)


# --------------------------------------------------------------------------
# вердикт
# --------------------------------------------------------------------------

def lookup(index: Optional[dict], component: str, rhel: str) -> Verdict:
    """Вердикт для компонента под версией RHEL; index=None — записи у Red Hat нет."""
    if index is None:
        return Verdict(state=NO_RECORD)
    vuln, rem_index, cve = index["vuln"], index["rem"], index["cve"]

    candidates = []
    siblings = {}  # версия → состояния, для соседних минорных потоков
    for bucket, product_ids in vuln.get("product_status", {}).items():
        for product_id in product_ids:
            platform_id, component_id = _split_product(product_id, index["rels"])
            found = _rhel_version(index["cpes"].get(platform_id))
            if found is None:
                continue
            if _component_name(component_id, index["pkgs"]).lower() != component.lower():
                continue
            state = _state_for(product_id, bucket, rem_index)
            if found != rhel:
                if found.split(".")[0] == rhel.split(".")[0]:
                    siblings.setdefault(found, set()).add(state)
                continue
            url, date = _errata_for(product_id, rem_index)
            candidates.append({
                "state": state, "url": url, "date": date,
                "cvss": _cvss_for(product_id, vuln),
                "nvr": _nvr_for(component_id),
                "variant": component_id.split("::", 1)[1] if "::" in component_id else "",
            })

    # Спрашивали обычный пакет; module/flatpak-стрим — другой продукт с тем
    # же именем. Берём стримы, только если ничего другого под этим именем нет.
    plain = [c for c in candidates if not c["variant"]]
    streams = sorted({c["variant"] for c in candidates if c["variant"]})
    if plain:
        if streams:
            logger.debug("%s %s: стримы %s не учитываются", cve, component, ", ".join(streams))
        candidates = plain
    elif streams:
        logger.debug("%s %s: обычного пакета нет, взяты стримы %s", cve, component,
                     ", ".join(streams))

    if not candidates:
        # Отсутствие в VEX — не «Not affected»: Red Hat перечисляет только то,
        # что оценил. Если есть соседние минорные потоки — говорим об этом.
        state = NOT_LISTED
        if siblings:
            state += " (present for " + ", ".join(sorted(siblings)) + ")"
        return Verdict(state=state, severity=index["severity"])

    best = min(candidates, key=lambda c: (STATE_RANK.get(c["state"], 3.5),
                                          _date_key(c["date"])))
    states = sorted({c["state"] for c in candidates})
    if len(states) > 1:
        logger.debug("%s %s: несколько вердиктов под RHEL %s (%s), взят %s",
                     cve, component, rhel, ", ".join(states), best["state"])
    divergent = sorted(v for v, found_states in siblings.items()
                       if found_states - {best["state"]})
    if divergent:
        logger.debug("%s %s: у потоков %s другой вердикт", cve, component,
                     ", ".join(divergent))

    # NVR фикса — только у Fixed и только по той errata, что в строке.
    fixed_nvr = "|".join(sorted({c["nvr"] for c in candidates
                                 if c["nvr"] and c["state"] == FIXED
                                 and c["url"] == best["url"]}))
    return Verdict(state=best["state"], severity=index["severity"],
                   cvss=str(best["cvss"]), fixed_nvr=fixed_nvr,
                   fix_date=best["date"], advisory_url=best["url"])
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: 16 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/vulnsheet/vex.py tools/vulnsheet/tests/fakes.py tools/vulnsheet/tests/test_vex.py
git commit -m "feat(vulnsheet): interpret Red Hat CSAF VEX verdicts

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Загрузка VEX с кэшем

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/vex.py` (импорты и новый раздел «загрузка»)
- Test: `tools/vulnsheet/tests/test_vex.py` (дописать классы)

**Interfaces:**
- Consumes: `build_index(doc)` из Task 4.
- Produces:
  - `vex_url(cve: str) -> str`
  - `download(url: str) -> Optional[bytes]` — `None` при 404, иначе исключение; единственная точка сети, тесты подменяют её
  - `class VexError(Exception)`
  - `fetch(cve: str, cache_dir: Optional[str] = None, ttl: int = CACHE_TTL) -> Optional[dict]`
  - `prepare_cache(path: str) -> Optional[str]`
  - `fetch_all(cves: Iterable[str], cache_dir: Optional[str] = None, jobs: int = JOBS) -> Tuple[Dict[str, Optional[dict]], Dict[str, str]]` — индексы (`None` — записи нет) и `{cve: текст ошибки}`
  - константы `CACHE_TTL = 3600`, `JOBS = 8`

- [ ] **Step 1: Дописать падающие тесты**

В начало `tools/vulnsheet/tests/test_vex.py` добавить импорты (рядом с существующими):

```python
import json
import os
import shutil
import tempfile
from unittest import mock

from vulnsheet.vex import VexError, fetch, fetch_all, prepare_cache, vex_url
```

В конец файла:

```python
DOC = csaf(CVE, [("under_investigation", RHEL9, "vim")])
BODY = json.dumps(DOC).encode()


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)
        self.sleep = mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def cached(self):
        return os.path.join(self.cache, "cve-2026-1000.json")

    def test_url(self):
        self.assertEqual(vex_url(CVE), "https://security.access.redhat.com/"
                                       "data/csaf/v2/vex/2026/cve-2026-1000.json")

    def test_downloads_once_then_reads_cache(self):
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, self.cache), DOC)
            self.assertEqual(fetch(CVE, self.cache), DOC)
        download.assert_called_once_with(vex_url(CVE))

    def test_404_means_no_record(self):
        with mock.patch("vulnsheet.vex.download", return_value=None):
            self.assertIsNone(fetch(CVE, self.cache))

    def test_corrupt_cache_falls_back_to_network(self):
        with open(self.cached(), "w") as handle:
            handle.write("{оборвано")
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, self.cache), DOC)
        download.assert_called_once()

    def test_stale_cache_is_refetched(self):
        with open(self.cached(), "w") as handle:
            json.dump({"старый": True}, handle)
        os.utime(self.cached(), (0, 0))
        with mock.patch("vulnsheet.vex.download", return_value=BODY):
            self.assertEqual(fetch(CVE, self.cache), DOC)

    def test_retries_then_gives_up(self):
        with mock.patch("vulnsheet.vex.download", side_effect=OSError("сеть")) as download:
            with self.assertRaises(VexError):
                fetch(CVE)
        self.assertEqual(download.call_count, 3)
        self.assertEqual([c.args for c in self.sleep.call_args_list], [(1,), (2,)])

    def test_retry_recovers(self):
        with mock.patch("vulnsheet.vex.download", side_effect=[OSError("сеть"), BODY]):
            self.assertEqual(fetch(CVE), DOC)


class FetchAllTest(unittest.TestCase):
    def setUp(self):
        mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_indices_failures_and_missing_records(self):
        def download(url):
            if "1002" in url:
                raise OSError("сеть")
            return BODY if "1000" in url else None

        with mock.patch("vulnsheet.vex.download", side_effect=download) as fake:
            with self.assertLogs("vulnsheet", "WARNING") as caught:
                indices, failures = fetch_all(
                    [CVE, "CVE-2026-1001", "CVE-2026-1002", CVE], jobs=2)
        self.assertEqual(sorted(indices), [CVE, "CVE-2026-1001"])
        self.assertIsNone(indices["CVE-2026-1001"])
        self.assertEqual(lookup(indices[CVE], "vim", "9").state, "Under investigation")
        self.assertEqual(list(failures), ["CVE-2026-1002"])
        self.assertIn("CVE-2026-1002", "\n".join(caught.output))
        # 1000 и 1001 — по одному разу, 1002 — три попытки
        self.assertEqual(fake.call_count, 5)

    def test_malformed_document_is_a_failure(self):
        with mock.patch("vulnsheet.vex.download", return_value=b'{"document": {}}'):
            with self.assertLogs("vulnsheet", "WARNING"):
                indices, failures = fetch_all([CVE])
        self.assertEqual((indices, list(failures)), ({}, [CVE]))


class PrepareCacheTest(unittest.TestCase):
    def test_creates_directory(self):
        room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, room)
        path = os.path.join(room, "vulnsheet")
        self.assertEqual(prepare_cache(path), path)
        self.assertTrue(os.path.isdir(path))

    def test_unusable_path_disables_cache(self):
        with tempfile.NamedTemporaryFile() as blocker:
            with self.assertLogs("vulnsheet", "WARNING"):
                self.assertIsNone(prepare_cache(os.path.join(blocker.name, "sub")))
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: FAIL — `ImportError: cannot import name 'VexError' from 'vulnsheet.vex'`.

- [ ] **Step 3: Дописать загрузку в `vex.py`**

Заменить блок импортов в начале `tools/vulnsheet/vulnsheet/vex.py` на:

```python
import json
import logging
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, NamedTuple, Optional, Tuple

from . import __version__
```

После строки `FIXED = "Fixed"` добавить:

```python
VEX_URL = "https://security.access.redhat.com/data/csaf/v2/vex/{year}/{cve}.json"
USER_AGENT = "vulnsheet/%s (+CSAF VEX client)" % __version__
CACHE_TTL = 3600  # секунд
JOBS = 8
RETRIES = 3
TIMEOUT = 30  # секунд
```

В конец файла добавить:

```python
# --------------------------------------------------------------------------
# загрузка
# --------------------------------------------------------------------------

class VexError(Exception):
    """Документ VEX не получен после всех попыток."""


def vex_url(cve: str) -> str:
    return VEX_URL.format(year=cve.split("-")[1], cve=cve.lower())


def download(url: str) -> Optional[bytes]:
    """Тело ответа; None при 404 (у Red Hat нет записи). Остальное — исключение."""
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        logger.debug("GET %s → %d за %.2f с", url, exc.code, time.monotonic() - started)
        if exc.code == 404:
            return None
        raise
    logger.debug("GET %s → %d за %.2f с", url, code, time.monotonic() - started)
    return body


def _read_cache(path, ttl):
    """Документ из кэша или None: нет, устарел или испорчен — идём в сеть."""
    try:
        if time.time() - os.path.getmtime(path) >= ttl:
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _write_cache(path, body):
    """Атомарно: оборванная запись не должна отравить кэш. Ошибка — не повод
    ронять прогон."""
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
    except OSError as exc:
        logger.debug("кэш %s не записан: %s", path, exc)


def prepare_cache(path: str) -> Optional[str]:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        logger.warning("кэш VEX отключён: %s", exc)
        return None
    return path


def fetch(cve: str, cache_dir: Optional[str] = None,
          ttl: int = CACHE_TTL) -> Optional[dict]:
    """Документ VEX; None, если у Red Hat записи нет; VexError — не получен."""
    cached = os.path.join(cache_dir, cve.lower() + ".json") if cache_dir else None
    if cached:
        doc = _read_cache(cached, ttl)
        if doc is not None:
            logger.debug("%s: из кэша", cve)
            return doc
    url = vex_url(cve)
    last = None
    for attempt in range(RETRIES):
        try:
            body = download(url)
            if body is None:
                return None
            doc = json.loads(body)
        except Exception as exc:  # сеть и мусор в ответе — повторяем
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
            continue
        if cached:
            _write_cache(cached, body)
        return doc
    raise VexError("%s: %s" % (url, last))


def fetch_all(cves: Iterable[str], cache_dir: Optional[str] = None,
              jobs: int = JOBS) -> Tuple[Dict[str, Optional[dict]], Dict[str, str]]:
    """Индексы документов по уникальным CVE и ошибки загрузки.

    Индекс None — у Red Hat записи нет. CVE с ошибкой в индексы не попадает.
    """
    cves = list(dict.fromkeys(cves))
    indices, failures = {}, {}
    lock = threading.Lock()
    done = 0
    step = max(1, len(cves) // 10)

    def load(cve):
        nonlocal done
        try:
            doc = fetch(cve, cache_dir)
            index = build_index(doc) if doc is not None else None
        except Exception as exc:  # в том числе испорченный документ
            with lock:
                failures[cve] = str(exc)
            logger.warning("VEX для %s не получен: %s", cve, exc)
        else:
            with lock:
                indices[cve] = index
        with lock:
            done += 1
            if done % step == 0 or done == len(cves):
                logger.info("VEX: %d/%d CVE", done, len(cves))

    with ThreadPoolExecutor(max_workers=max(1, jobs), thread_name_prefix="w") as pool:
        list(pool.map(load, cves))
    return indices, failures
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: 27 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/vex.py tools/vulnsheet/tests/test_vex.py
git commit -m "feat(vulnsheet): fetch VEX documents in parallel with a disk cache

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Строка таблицы и CSV

**Files:**
- Create: `tools/vulnsheet/vulnsheet/report.py`
- Test: `tools/vulnsheet/tests/test_report.py`

**Interfaces:**
- Consumes: `Task` (Task 2), `Verdict` и `FIXED` (Task 4).
- Produces: `COLUMNS: List[str]` (20 имён), `EMPTY = "-"`, `format_date(value: str) -> str`, `row(task, nvr: str, verdict) -> List[str]`, `write(rows: Iterable[List[str]], handle) -> None`.

- [ ] **Step 1: Написать падающие тесты**

`tools/vulnsheet/tests/test_report.py`:

```python
import io
import unittest

from vulnsheet.report import COLUMNS, format_date, row, write
from vulnsheet.tasks import Task
from vulnsheet.vex import Verdict

TASK = Task("TASKID-181229", "CVE-2026-73070", "vim", "Отменен", "22.09.2026", "КМ")
EXAMPLE = ("-;-;-;-;-;TASKID-181229;CVE-2026-73070;Отменен;22.09.2026;КМ;vim;"
           "vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;Moderate;5.5;-;"
           "https://access.redhat.com/security/cve/CVE-2026-73070;-")
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"


class RowTest(unittest.TestCase):
    def cells(self, nvr, verdict):
        return dict(zip(COLUMNS, row(TASK, nvr, verdict)))

    def test_columns(self):
        self.assertEqual(COLUMNS, [
            "Разработчик", "Статус", "Start date", "End date", "Принятая мера",
            "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель",
            "Компонент", "SL NVR (latest build)", "RHEL NVR (if fixed)",
            "Fix date", "RHEL state", "RHEL severity", "RHEL CVSS",
            "Advisory (RHSA)", "CVE Link", "Комментарий"])

    def test_example_from_the_task(self):
        verdict = Verdict(state="Under investigation", severity="Moderate", cvss="5.5")
        self.assertEqual(";".join(row(TASK, "vim-8.2.2637-26.sl9_8.6^4", verdict)), EXAMPLE)

    def test_fixed_fills_nvr_date_and_advisory(self):
        cells = self.cells("vim-8.2.2637-26.sl9_8.6^4", Verdict(
            "Fixed", "Important", "7.8", "vim-8.2.2637-22.el9_6", "2026-09-02", RHSA))
        self.assertEqual((cells["RHEL NVR (if fixed)"], cells["Fix date"],
                          cells["Advisory (RHSA)"]),
                         ("vim-8.2.2637-22.el9_6", "02.09.2026", RHSA))

    def test_fix_fields_only_when_fixed(self):
        cells = self.cells("x", Verdict("Affected", "Low", "3.1", "vim-1-1", "2026-09-02", RHSA))
        self.assertEqual((cells["RHEL NVR (if fixed)"], cells["Fix date"],
                          cells["Advisory (RHSA)"]), ("-", "-", "-"))

    def test_zero_cvss_survives(self):
        self.assertEqual(self.cells("x", Verdict("Affected", cvss="0.0"))["RHEL CVSS"], "0.0")

    def test_markers_pass_through(self):
        cells = self.cells("NOT_FOUND", Verdict(state="no VEX record"))
        self.assertEqual((cells["SL NVR (latest build)"], cells["RHEL state"],
                          cells["RHEL severity"], cells["CVE Link"]),
                         ("NOT_FOUND", "no VEX record", "-",
                          "https://access.redhat.com/security/cve/CVE-2026-73070"))


class FormatDateTest(unittest.TestCase):
    def test_values(self):
        for value, want in [("2026-09-02", "02.09.2026"),
                            ("2026-09-02T10:00:00+00:00", "02.09.2026"),
                            ("когда-нибудь", "когда-нибудь"), ("", "")]:
            with self.subTest(value=value):
                self.assertEqual(format_date(value), want)


class WriteTest(unittest.TestCase):
    def test_header_then_rows_with_unix_newlines(self):
        out = io.StringIO()
        write([row(TASK, "vim-8.2.2637-26.sl9_8.6^4",
                   Verdict(state="Under investigation", severity="Moderate", cvss="5.5"))], out)
        self.assertEqual(out.getvalue(), ";".join(COLUMNS) + "\n" + EXAMPLE + "\n")
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_report -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.report'`.

- [ ] **Step 3: Написать `report.py`**

`tools/vulnsheet/vulnsheet/report.py`:

```python
"""Строка итоговой таблицы и запись CSV.

Формат фиксирован процессом: 20 колонок, разделитель ';', пустая ячейка —
'-', даты — dd.mm.yyyy. Колонки процесса (разработчик, статус, даты работ,
принятая мера, комментарий) заполняют люди, здесь они — прочерки.
"""
import csv
import re
from typing import Iterable, List

from .vex import FIXED

EMPTY = "-"
CVE_PAGE = "https://access.redhat.com/security/cve/{cve}"
COLUMNS = [
    "Разработчик", "Статус", "Start date", "End date", "Принятая мера",
    "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель",
    "Компонент", "SL NVR (latest build)", "RHEL NVR (if fixed)",
    "Fix date", "RHEL state", "RHEL severity", "RHEL CVSS",
    "Advisory (RHSA)", "CVE Link", "Комментарий",
]
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def format_date(value: str) -> str:
    """'2026-09-02' → '02.09.2026'; нераспознанное — как есть."""
    match = _ISO_DATE.match(value or "")
    if not match:
        return value
    year, month, day = match.groups()
    return "%s.%s.%s" % (day, month, year)


def row(task, nvr: str, verdict) -> List[str]:
    fixed = verdict.state == FIXED
    cells = [
        "", "", "", "", "",
        task.task_id, task.cve, task.state, task.date, task.assignee,
        task.component, nvr,
        verdict.fixed_nvr if fixed else "",
        format_date(verdict.fix_date) if fixed else "",
        verdict.state, verdict.severity, verdict.cvss,
        verdict.advisory_url if fixed else "",
        CVE_PAGE.format(cve=task.cve),
        "",
    ]
    # пустое — только None и "": CVSS 0.0 — настоящее значение
    return [EMPTY if cell is None or cell == "" else cell for cell in cells]


def write(rows: Iterable[List[str]], handle) -> None:
    writer = csv.writer(handle, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_report -v`
Expected: 8 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/report.py tools/vulnsheet/tests/test_report.py
git commit -m "feat(vulnsheet): build the 20-column report rows and write CSV

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: CLI — связывание, файл отбраковки, коды возврата

**Files:**
- Create: `tools/vulnsheet/vulnsheet/cli.py`
- Create: `tools/vulnsheet/vulnsheet/__main__.py`
- Test: `tools/vulnsheet/tests/test_cli.py`

**Interfaces:**
- Consumes: `logs.configure`, `logs.LEVELS`, `logs.DEFAULT_LEVEL` (Task 1); `tasks.parse` (Task 2); `kojiclient.connect`, `kojiclient.latest_builds`, `kojiclient.KojiError`, `kojiclient.NOT_FOUND`, `kojiclient.ERROR` (Task 3); `vex.parse_rhel`, `vex.lookup`, `vex.Verdict`, `vex.FETCH_ERROR`, `vex.fetch_all`, `vex.prepare_cache` (Tasks 4–5); `report.row`, `report.write` (Task 6).
- Produces: `cli.main(argv: Optional[List[str]] = None) -> int`; `cli.rejects_path(output: str, explicit: Optional[str]) -> str`; `EXIT_OK = 0`, `EXIT_PARTIAL = 1`, `EXIT_FATAL = 2`.

- [ ] **Step 1: Написать падающие тесты**

`tools/vulnsheet/tests/test_cli.py`:

```python
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from tests.fakes import RHEL9, FakeKojiSession, csaf, pid
from vulnsheet import __version__
from vulnsheet.cli import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL, main, rejects_path
from vulnsheet.report import COLUMNS
from vulnsheet.vex import vex_url

BLOCK = "Состоит из\nTASKID-181229\nCVE-2026-73070 vim\nОтменен\n22.09.2026\nКМ"
BAD = "Состоит из\nTASKID-181231\nCVE-2026-73072 bash\nВ работу\n23.09.2026"
HEADER = ";".join(COLUMNS)
EXPECTED = ("-;-;-;-;-;TASKID-181229;CVE-2026-73070;Отменен;22.09.2026;КМ;vim;"
            "vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;Moderate;5.5;-;"
            "https://access.redhat.com/security/cve/CVE-2026-73070;-")
VIM_DOC = csaf("CVE-2026-73070", [("under_investigation", RHEL9, "vim")],
               scores=[{"cvss_v3": {"baseScore": 5.5}, "products": [pid(RHEL9, "vim")]}])


class CliCase(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)
        mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.path("cache")}).start()
        self.session = FakeKojiSession(builds={"vim": "vim-8.2.2637-26.sl9_8.6^4"})
        self.connect = mock.patch("vulnsheet.kojiclient.connect",
                                  return_value=self.session).start()
        self.docs = {vex_url("CVE-2026-73070"): VIM_DOC}
        self.download = mock.patch("vulnsheet.vex.download",
                                   side_effect=self._download).start()
        mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)
        self.log = ""

    def _download(self, url):
        doc = self.docs.get(url)
        if isinstance(doc, Exception):
            raise doc
        return None if doc is None else json.dumps(doc).encode()

    def path(self, name):
        return os.path.join(self.room, name)

    def run_cli(self, *extra, text=BLOCK + "\n", data=None):
        src = self.path("tasks.txt")
        with open(src, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        argv = ["--rhel", "9", "--koji-url", "https://koji.example.com/kojihub",
                "--tag", "sl9", src, "-o", self.path("report.csv")] + list(extra)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(argv)
        self.log = err.getvalue()
        return code

    def report_lines(self):
        with open(self.path("report.csv"), encoding="utf-8") as handle:
            return handle.read().splitlines()


class HappyPathTest(CliCase):
    def test_example_from_the_task(self):
        self.assertEqual(self.run_cli(), EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        self.assertFalse(os.path.exists(self.path("report.rejected.txt")))
        self.assertIn("Under investigation 1", self.log)
        self.assertIn("написан", self.log)

    def test_order_duplicates_and_single_requests(self):
        second = (BLOCK.replace("181229", "181230").replace("73070", "73071")
                  .replace("vim", "openssl"))
        code = self.run_cli(text=BLOCK + "\n\n" + second + "\n\n" + BLOCK + "\n")
        lines = self.report_lines()
        self.assertEqual(code, EXIT_OK)  # NOT_FOUND и no VEX record — не ошибки
        self.assertEqual(len(lines), 4)
        self.assertEqual((lines[1], lines[3]), (EXPECTED, EXPECTED))
        self.assertIn(";openssl;NOT_FOUND;", lines[2])
        self.assertIn(";no VEX record;", lines[2])
        self.assertEqual(self.session.calls, [("sl9", "vim"), ("sl9", "openssl")])
        self.assertEqual(self.download.call_count, 2)

    def test_vex_cache_lives_under_xdg_cache_home(self):
        self.run_cli()
        self.assertTrue(os.path.exists(self.path("cache/vulnsheet/cve-2026-73070.json")))

    def test_stdout_when_no_output_given(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--rhel", "9", "--koji-url", "https://k/kojihub",
                         "--tag", "sl9", src])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out.getvalue(), HEADER + "\n" + EXPECTED + "\n")


class RejectsTest(CliCase):
    def test_bad_block_goes_to_rejects_file(self):
        code = self.run_cli(text=BLOCK + "\n\n" + BAD + "\n")
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        with open(self.path("report.rejected.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), BAD + "\n")
        self.assertIn("блок 2", self.log)
        self.assertIn("5 строк", self.log)

    def test_explicit_rejects_path(self):
        self.run_cli("--rejects", self.path("bad.txt"), text=BAD)
        self.assertTrue(os.path.exists(self.path("bad.txt")))

    def test_stale_rejects_file_is_removed(self):
        with open(self.path("report.rejected.txt"), "w") as handle:
            handle.write("старьё")
        self.assertEqual(self.run_cli(), EXIT_OK)
        self.assertFalse(os.path.exists(self.path("report.rejected.txt")))

    def test_all_blocks_rejected_writes_header_and_skips_koji(self):
        self.assertEqual(self.run_cli(text=BAD), EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER])
        self.connect.assert_not_called()

    def test_default_rejects_path(self):
        self.assertEqual(rejects_path("report.csv", None), "report.rejected.txt")
        self.assertEqual(rejects_path("out/report", None), "out/report.rejected.txt")
        self.assertEqual(rejects_path("-", None), "vulnsheet.rejected.txt")
        self.assertEqual(rejects_path("report.csv", "bad.txt"), "bad.txt")


class PartialTest(CliCase):
    def test_fetch_error_marks_row(self):
        self.docs[vex_url("CVE-2026-73070")] = OSError("сеть")
        self.assertEqual(self.run_cli(), EXIT_PARTIAL)
        self.assertIn(";fetch error;", self.report_lines()[1])

    def test_koji_error_for_package_marks_row(self):
        self.session.errors["vim"] = "boom"
        self.assertEqual(self.run_cli(), EXIT_PARTIAL)
        self.assertIn(";vim;ERROR;", self.report_lines()[1])


class FatalTest(CliCase):
    def assertFatal(self, code, needle):
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn(needle, self.log)
        self.assertNotIn("Traceback", self.log)

    def test_unknown_tag_is_fatal(self):
        self.session.tags = {"sl9-other"}
        self.assertFatal(self.run_cli(), "sl9")

    def test_empty_input_is_fatal(self):
        self.assertFatal(self.run_cli(text="\n \n"), "ни одного блока")

    def test_non_utf8_input_is_fatal(self):
        self.assertFatal(self.run_cli(data=BLOCK.encode("cp1251")), "UTF-8")

    def test_missing_input_is_fatal(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--rhel", "9", "--koji-url", "https://k", "--tag", "sl9",
                         self.path("нет-такого.txt"), "-o", self.path("r.csv")])
        self.log = err.getvalue()
        self.assertFatal(code, "вход")

    def test_unwritable_output_fails_before_network(self):
        code = self.run_cli("-o", self.path("нет-каталога/report.csv"))
        self.assertFatal(code, "выход")
        self.connect.assert_not_called()

    def test_bad_rhel_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--rhel", "nine", "--koji-url", "https://k", "--tag", "sl9"])
        self.assertEqual(caught.exception.code, 2)


class VersionFlagTest(unittest.TestCase):
    def test_prints_version_without_other_arguments(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "vulnsheet " + __version__)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_cli -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.cli'`.

- [ ] **Step 3: Написать `cli.py` и `__main__.py`**

`tools/vulnsheet/vulnsheet/cli.py`:

```python
"""Точка входа: блоки задач → koji и VEX → CSV и файл отбраковки."""
import argparse
import logging
import os
import sys
import time
from collections import Counter
from typing import List, Optional

from . import __version__, kojiclient, logs, report, vex
from .tasks import parse

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_PARTIAL = 1  # CSV записан, но есть отбраковка, ERROR koji или fetch error
EXIT_FATAL = 2

STDIO = "-"
REJECTS_SUFFIX = ".rejected.txt"
REJECTS_STDOUT = "vulnsheet" + REJECTS_SUFFIX


class _Fatal(Exception):
    """Ошибка, после которой таблицу не построить."""


def _rhel(value):
    try:
        return vex.parse_rhel(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vulnsheet",
        description="Блоки задач из тасктрекера → CSV с данными Red Hat VEX и koji.")
    parser.add_argument("input", nargs="?", default=STDIO,
                        help="файл с блоками задач (по умолчанию stdin)")
    parser.add_argument("--rhel", required=True, type=_rhel,
                        help="версия RHEL: 9 — только 9, 9.2 — только 9.2")
    parser.add_argument("--koji-url", required=True, help="URL kojihub")
    parser.add_argument("--tag", required=True, help="koji-тег")
    parser.add_argument("-o", "--output", default=STDIO,
                        help="CSV (по умолчанию stdout)")
    parser.add_argument("--rejects",
                        help="файл для битых блоков (по умолчанию <выход>%s)"
                             % REJECTS_SUFFIX)
    parser.add_argument("--log-level", choices=list(logs.LEVELS),
                        default=logs.DEFAULT_LEVEL,
                        help="подробность журнала в stderr (по умолчанию %s)"
                             % logs.DEFAULT_LEVEL)
    parser.add_argument("--version", action="version",
                        version="vulnsheet " + __version__)
    return parser


def rejects_path(output: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if output == STDIO:
        return REJECTS_STDOUT
    return os.path.splitext(output)[0] + REJECTS_SUFFIX


def _cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "vulnsheet")


def _read_input(path: str) -> str:
    try:
        if path == STDIO:
            return sys.stdin.read()
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except UnicodeDecodeError as exc:
        raise _Fatal("вход не в UTF-8: %s" % exc)
    except OSError as exc:
        raise _Fatal("вход не читается: %s" % exc)


def _open_output(path: str):
    if path == STDIO:
        return sys.stdout
    try:
        return open(path, "w", newline="", encoding="utf-8")
    except OSError as exc:
        raise _Fatal("выход не пишется: %s" % exc)


def _write_rejects(path: str, rejects) -> None:
    if rejects:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n\n".join(r.text for r in rejects) + "\n")
        except OSError as exc:
            raise _Fatal("файл отбраковки не пишется: %s" % exc)
        logger.warning("битые блоки (%d) записаны в %s", len(rejects), path)
    elif os.path.exists(path):
        os.remove(path)
        logger.info("удалён %s от прошлого прогона: битых блоков нет", path)


def _summary(builds: List[str], verdicts) -> None:
    states = Counter(v.state.split(" (", 1)[0] for v in verdicts)
    if states:
        logger.info("RHEL state: %s", ", ".join(
            "%s %d" % item for item in sorted(states.items(), key=lambda kv: (-kv[1], kv[0]))))
    marks = Counter(b if b in (kojiclient.NOT_FOUND, kojiclient.ERROR) else "found"
                    for b in builds)
    logger.info("SL NVR: найдено %d, NOT_FOUND %d, ERROR %d", marks["found"],
                marks[kojiclient.NOT_FOUND], marks[kojiclient.ERROR])


def _run(args) -> int:
    tasks, rejects = parse(_read_input(args.input))
    if not tasks and not rejects:
        raise _Fatal("во входе нет ни одного блока")
    for reject in rejects:
        logger.warning("блок %d «%s» отбракован: %s", reject.number,
                       reject.text.split("\n", 1)[0].strip(), reject.reason)
    cves = list(dict.fromkeys(t.cve for t in tasks))
    packages = list(dict.fromkeys(t.component for t in tasks))
    logger.info("хаб %s, тег %s, RHEL %s", args.koji_url, args.tag, args.rhel)
    logger.info("блоков %d, отбраковано %d; CVE %d, пакетов %d",
                len(tasks) + len(rejects), len(rejects), len(cves), len(packages))

    # выход открываем до сети: неверный путь должен падать сразу
    out = _open_output(args.output)
    try:
        nvrs, indices, failures = {}, {}, {}
        if tasks:
            session = kojiclient.connect(args.koji_url)
            nvrs = kojiclient.latest_builds(session, args.tag, packages)
            indices, failures = vex.fetch_all(cves, vex.prepare_cache(_cache_dir()))
        builds = [nvrs[t.component] for t in tasks]
        verdicts = [vex.Verdict(state=vex.FETCH_ERROR) if t.cve in failures
                    else vex.lookup(indices[t.cve], t.component, args.rhel)
                    for t in tasks]
        report.write([report.row(t, b, v) for t, b, v in zip(tasks, builds, verdicts)], out)
    finally:
        if out is not sys.stdout:
            out.close()
    if args.output != STDIO:
        logger.info("написан %s", args.output)

    _write_rejects(rejects_path(args.output, args.rejects), rejects)
    _summary(builds, verdicts)
    partial = rejects or failures or kojiclient.ERROR in builds
    return EXIT_PARTIAL if partial else EXIT_OK


def _fatal(message: str) -> int:
    """Одна строка пользователю, трейсбек — только на debug."""
    logger.error("%s", message)
    logger.debug("трейсбек", exc_info=True)
    return EXIT_FATAL


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    logs.configure(args.log_level)
    started = time.monotonic()
    try:
        code = _run(args)
    except _Fatal as exc:
        return _fatal(str(exc))
    except kojiclient.KojiError as exc:
        return _fatal("koji: %s" % exc)
    except Exception as exc:  # непредвиденное не должно ронять CLI трейсбеком
        return _fatal("фатальная ошибка: %s" % exc)
    logger.info("всего за %.1f с", time.monotonic() - started)
    return code
```

`tools/vulnsheet/vulnsheet/__main__.py`:

```python
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_cli -v`
Expected: 18 tests, OK.

- [ ] **Step 5: Прогнать весь набор и `--version`**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v && python3 -m vulnsheet --version`
Expected: все тесты OK; последняя строка — `vulnsheet 1.0.0`.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/vulnsheet/cli.py tools/vulnsheet/vulnsheet/__main__.py tools/vulnsheet/tests/test_cli.py
git commit -m "feat(vulnsheet): wire the pipeline into a CLI with rejects file and exit codes

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Документация тулзы и репозитория

**Files:**
- Create: `tools/vulnsheet/README.md`
- Create: `tools/vulnsheet/TODO.md`
- Modify: `README.md` (таблица «Тулзы»)
- Modify: `TODO.md` (раздел «Списки тулз»)
- Modify: `CHANGELOG.md` (`## [Unreleased]` → `### Добавлено`)

**Interfaces:**
- Consumes: CLI и коды возврата из Task 7, колонки из Task 6.

- [ ] **Step 1: Написать `tools/vulnsheet/README.md`**

````markdown
# vulnsheet

Собирает рабочую таблицу по задачам на устранение уязвимостей. На вход —
блоки задач, скопированные из тасктрекера; для каждой пары «CVE — компонент»
тулза берёт у Red Hat (CSAF/VEX) статус в нужной версии RHEL, severity, CVSS
и данные фикса, а у koji — последний билд компонента в теге, и пишет CSV из
двадцати колонок в том виде, в каком таблицу ведёт процесс.

Заменяет три отдельных скрипта: разбор блоков, запрос к VEX и запрос к koji.

**Версия:** 1.0.0 (номер — в `vulnsheet/__init__.py`, выводится по
`--version`; история — [CHANGELOG.md](CHANGELOG.md)).

## Требования

- Python 3.9+
- `koji` — клиент koji-хаба, ставится системным пакетом (`python3-koji`) или
  `pip install koji`. Импортируется только при обращении к хабу.
- Сеть до koji-хаба (только чтение: `getTag`, `getLatestBuilds`) и до
  `https://security.access.redhat.com`.

Переменных окружения и токенов не нужно. Кэш VEX лежит в
`$XDG_CACHE_HOME/vulnsheet` (по умолчанию `~/.cache/vulnsheet`) и живёт час.

## Установка

Из каталога тулзы, без установки:

```bash
python3 -m vulnsheet --version
```

Или пакетом, тогда появляется команда `vulnsheet`:

```bash
pip install --no-build-isolation -e .
```

`--no-build-isolation` — чтобы pip не ходил в сеть за свежим `setuptools`.
Метаданные лежат в `setup.cfg`: `setuptools` в RHEL 9 (53-й) не понимает
`[project]` в `pyproject.toml`.

## Запуск

```bash
python3 -m vulnsheet --rhel 9 --koji-url https://koji.example.com/kojihub \
    --tag sl9-updates tasks.txt -o report.csv
```

| Аргумент | Смысл |
|---|---|
| `input` | файл с блоками; без него или `-` — stdin |
| `--rhel` | версия RHEL, обязательный: `9` — только 9, `9.2` — только 9.2; `RHEL 9`, `el9` тоже годятся |
| `--koji-url` | URL kojihub, обязательный |
| `--tag` | koji-тег, обязательный |
| `-o`, `--output` | CSV; без него — stdout |
| `--rejects` | файл для битых блоков (см. ниже) |
| `--log-level` | `error` / `warning` / `info` / `debug`, по умолчанию `info` |
| `--version` | версия тулзы |

Из буфера обмена:

```bash
xclip -o | python3 -m vulnsheet --rhel 9 --koji-url https://koji.example.com/kojihub \
    --tag sl9-updates -o report.csv
```

## Вход

Блоки по шесть строк, между блоками — пустая строка. Других разделителей
нет. Пробелы по краям строк, `\r\n` и BOM в начале файла допускаются.
Кодировка — UTF-8.

```text
Состоит из
TASKID-181229
CVE-2026-73070 vim
Отменен
22.09.2026
КМ
```

Строки: тип связи (не используется), Task ID, `CVE-ID компонент`, статус
задачи, дата задачи, исполнитель.

## Выход

CSV в UTF-8 без BOM, разделитель `;`, первая строка — заголовок. Одна строка
на каждый годный блок, в порядке входа, с повторами. Пустая ячейка — `-`.

| Колонка | Откуда |
|---|---|
| `Разработчик`, `Статус`, `Start date`, `End date`, `Принятая мера` | всегда `-` — их заполняют люди |
| `Task ID`, `CVE ID`, `Task state`, `Task date`, `Исполнитель`, `Компонент` | из блока |
| `SL NVR (latest build)` | последний билд компонента в теге; `NOT_FOUND` — пакета в теге нет, `ERROR` — koji не ответил по пакету |
| `RHEL NVR (if fixed)` | билд RHEL с фиксом; только при `Fixed`, несколько — через `\|` |
| `Fix date` | дата errata, `dd.mm.yyyy`; только при `Fixed` |
| `RHEL state` | `Fixed`, `Affected`, `Will not fix`, `Fix deferred`, `Out of support scope`, `Under investigation`, `Not affected`; см. маркеры ниже |
| `RHEL severity` | общая severity CVE по Red Hat |
| `RHEL CVSS` | базовая оценка CVSS (v4, иначе v3) |
| `Advisory (RHSA)` | ссылка на errata; только при `Fixed` |
| `CVE Link` | `https://access.redhat.com/security/cve/<CVE ID>` |
| `Комментарий` | всегда `-` |

Маркеры в `RHEL state`:

- `not listed` — у Red Hat есть запись по CVE, но компонента под этой версией
  RHEL в ней нет. Это не «Not affected»: Red Hat перечисляет только то, что
  оценил.
- `not listed (present for 9.2, 9.4)` — компонент оценён только в соседних
  минорных потоках.
- `no VEX record` — у Red Hat записи по CVE нет.
- `fetch error` — документ VEX не получен (подробности — в журнале).

Как выбирается вердикт: имя компонента сравнивается точно (`vim` не совпадает
с `vim-enhanced`); module- и flatpak-стримы не считаются компонентом, если
есть обычный пакет; если под одной версией RHEL вердиктов несколько (BaseOS и
AppStream расходятся), побеждает самый опасный; эпоха в NVR срезается, чтобы
он сравнивался с `rpm -q`.

## Битые блоки

Блок, в котором не шесть строк, третья строка не начинается с CVE-ID или в ней
нет компонента, в CSV не попадает. Такие блоки дословно, через пустую строку,
пишутся в отдельный файл — поправьте его и подайте на вход ещё раз. Причина
отказа — в журнале, строкой вида:

```
14:02:11 WARNING cli: блок 7 «Состоит из» отбракован: в блоке 5 строк, ожидается 6
```

Путь файла — `--rejects`, по умолчанию он рядом с выходом: `report.csv` →
`report.rejected.txt`; при выводе в stdout — `vulnsheet.rejected.txt` в
текущем каталоге. Файл создаётся, только если битые блоки есть; оставшийся
от прошлого прогона файл по тому же пути удаляется.

## Журнал

Журнал идёт в stderr, поэтому `-o` и `2>run.log` друг другу не мешают.

| Уровень | Что видно |
|---|---|
| `error` | фатальная ошибка — одна строка |
| `warning` | битые блоки, пакеты `NOT_FOUND`, ошибки koji по пакету, ошибки загрузки VEX, отключённый кэш |
| `info` (по умолчанию) | хаб, тег, RHEL; число блоков, CVE и пакетов; прогресс загрузки VEX; сводка по `RHEL state` и `SL NVR`; записанные файлы; общее время |
| `debug` | каждый запрос к VEX и koji, попадания в кэш, пояснения к вердиктам (проигнорированные стримы, несколько вердиктов), трейсбек фатальной ошибки |

## Коды возврата

| Код | Когда |
|---|---|
| `0` | CSV записан, ошибок нет. `NOT_FOUND`, `not listed` и `no VEX record` — ответы источников, не ошибки |
| `1` | CSV записан, но есть битые блоки, `ERROR` от koji или `fetch error` |
| `2` | фатально: неверные аргументы; вход не читается, не в UTF-8 или пуст; выход не пишется; хаб koji недоступен, тега нет или не установлен `koji` |

## Разработка

Устройство пакета:

| Модуль | За что отвечает |
|---|---|
| `tasks.py` | разбор блоков, отбраковка |
| `kojiclient.py` | последние билды тега одним `multicall` |
| `vex.py` | загрузка CSAF/VEX с кэшем и выбор вердикта |
| `report.py` | строка из 20 колонок и запись CSV |
| `cli.py` | аргументы, связывание, файл отбраковки, коды возврата |
| `logs.py` | единственное место, где ставится хендлер журнала |

Тесты — без сети: koji подменён `tests/fakes.py:FakeKojiSession`, VEX —
подменой `vulnsheet.vex.download` и документами из `tests/fakes.py:csaf`.

```bash
python3 -m unittest discover -s tests -v
```

Версия тулзы независима от версии репозитория. Номер живёт в
`vulnsheet/__init__.py` и поднимается тем же коммитом, что и изменение:
сломали формат входа, выхода или флаг — старший, новая возможность —
средний, исправление — младший. Вместе с номером — запись в
[CHANGELOG.md](CHANGELOG.md) тулзы и строка «`vulnsheet` (X.Y.Z): …» в
корневом `CHANGELOG.md`. Что запись есть, сторожит `tests/test_version.py`.

Соглашения репозитория — [../../CLAUDE.md](../../CLAUDE.md). Задачи по
тулзе — [TODO.md](TODO.md).
````

- [ ] **Step 2: Написать `tools/vulnsheet/TODO.md`**

```markdown
# TODO — vulnsheet

Задачи по этой тулзе: баги, фичи, технический долг, идеи. Пишем сюда оба —
и пользователь, и Claude.

> **Правило работы со списком.** Этот файл — только хранилище задач.
> Claude не берёт отсюда ничего в работу по собственной инициативе: ни при
> «заодно поправь», ни когда задача выглядит тривиальной, ни когда она рядом
> с тем, что уже правится. Работа над пунктом начинается только по явному
> указанию пользователя на конкретный пункт.

## Баги

_Пусто._

## Фичи

_Пусто._

## Технический долг

_Пусто._

## Идеи

_Пусто._
```

- [ ] **Step 3: Обновить корневые документы**

В `README.md`, в таблицу «Тулзы», после строки `dashboard` добавить:

```markdown
| [vulnsheet](tools/vulnsheet/) | Таблица задач по уязвимостям: разбирает блоки задач из тасктрекера, дополняет их статусом из Red Hat CSAF/VEX и последним билдом из koji и пишет CSV из двадцати колонок. |
```

В `TODO.md`, в список «Списки тулз», после строки `dashboard` добавить:

```markdown
- [`tools/vulnsheet/TODO.md`](tools/vulnsheet/TODO.md)
```

В `CHANGELOG.md`, в `## [Unreleased]` → `### Добавлено`, после записи про `dashboard` добавить:

```markdown
- `vulnsheet` (1.0.0): таблица задач по уязвимостям — разбирает блоки задач
  из тасктрекера, для каждой пары «CVE — компонент» берёт статус, severity,
  CVSS и данные фикса из Red Hat CSAF/VEX и последний билд из koji-тега и
  пишет CSV из двадцати колонок. Битые блоки дословно уходят в отдельный
  файл. Заменяет три разрозненных скрипта.
```

- [ ] **Step 4: Прогнать корневые проверки и тесты**

Run из корня репозитория:

```bash
find tools -name '*.sh' -exec bash -n {} \;
git add -N tools/vulnsheet
git ls-files -s tools | grep -v '^100755' | cut -f2 | while read -r f; do
  if [ "$(head -c2 "$f" 2>/dev/null)" = '#!' ]; then echo "NOT EXECUTABLE: $f"; fi
done
for d in tools/*/; do
  for f in README.md TODO.md; do
    [ -e "$d$f" ] || echo "MISSING: $d$f"
  done
done
for d in tools/*/; do
  grep -oh '](\.\?/\?[^):]*)' "$d"README.md "$d"TODO.md 2>/dev/null |
    sed 's/](//;s/)$//' | grep -v '^#' | sort -u | while read -r f; do
      [ -e "$d$f" ] || echo "BROKEN: $d$f"
    done
done
(cd tools/vulnsheet && python3 -m unittest discover -s tests)
```

Expected: ни одной строки `NOT EXECUTABLE` / `MISSING` / `BROKEN`; тесты — `OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/README.md tools/vulnsheet/TODO.md README.md TODO.md CHANGELOG.md
git commit -m "docs(vulnsheet): add README, TODO and register the tool in the repository

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
