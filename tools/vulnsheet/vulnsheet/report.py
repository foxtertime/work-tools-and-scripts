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
