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
