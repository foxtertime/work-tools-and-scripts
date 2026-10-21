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

# ключ в данных страницы → имя колонки vulnsheet 3.0 (без Task state; из ai_* —
# только то, что нужно блоку «AI-покрытие»)
FIELDS = (
    ("dev", "Разработчик"), ("status", "Статус"), ("start", "Start date"),
    ("end", "End date"), ("measure", "Принятая мера"), ("task", "Task ID"),
    ("cve", "CVE ID"), ("tdate", "Task date"), ("exec", "Исполнитель"),
    ("comp", "Компонент"), ("p", "P"), ("d", "D"),
    ("slnvr", "SL NVR (latest build)"), ("rhnvr", "RHEL NVR (if fixed)"),
    ("fixdate", "Fix date"), ("rstate", "RHEL state"), ("sev", "RHEL severity"),
    ("cvss", "RHEL CVSS"), ("rhsa", "Advisory (RHSA)"), ("link", "CVE link"),
    ("comment", "Комментарий"), ("ai_verdict", "ai_verdict"), ("ai_run", "ai_run"),
)
REQUIRED = ("cve", "comp", "rstate", "sev")
DATES = ("tdate", "start", "end", "fixdate", "ai_run")
HEADER_KEY = "CVE ID"
_NAMES = dict(FIELDS)
_EMPTY = ("-", "—")
_DMY = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[ T].*)?$")
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
_SERIAL = re.compile(r"\d+(?:\.\d+)?$")
# правдоподобные даты: опечатка вроде 01.10.0206 или число 5 вместо даты
# растянули бы графики на сотни тысяч дней
_MIN_DATE = datetime.date(2000, 1, 1)
_MAX_DATE = datetime.date(2099, 12, 31)


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
        where = " листа «%s»" % sheet.name if sheet.name else ""
        raise TableError("нет шапки: ни в одной строке%s нет ячейки «%s»" % (where, HEADER_KEY))
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
    """Дата из ячейки: дата Excel, дд.мм.гггг[ чч:мм], гггг-мм-дд[…], серийный номер.

    Дата вне 2000-01-01..2099-12-31 считается нераспознанной.
    """
    day = _parse(cell, date1904)
    if day is None or not _MIN_DATE <= day <= _MAX_DATE:
        return None
    return day


def _parse(cell: Cell, date1904: bool) -> Optional[datetime.date]:
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
