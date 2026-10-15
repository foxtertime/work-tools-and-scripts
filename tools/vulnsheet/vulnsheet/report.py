"""Строка итоговой таблицы и запись CSV.

Формат фиксирован процессом: 20 колонок, разделитель ';', пустая ячейка —
'-', даты — dd.mm.yyyy. Колонки процесса (разработчик, статус, даты работ,
принятая мера, комментарий) заполняют люди, здесь они — прочерки. В
комментарий тулза дописывает только пометку о найденном патче.
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
    "Advisory (RHSA)", "CVE link", "Комментарий",
]

MISSING = "Missing"  # Task state строки, чьей задачи больше нет в блоках
# в каталоге патчей билда есть файл с CVE строки в имени
PATCH_NOTE = "патч присутствует"

# Группы колонок для режимов обновления: что в каком режиме откуда берётся,
# см. docs/superpowers/specs/2026-09-24-vulnsheet-update-modes-design.md.
DEVELOPER = slice(0, 5)   # Разработчик … Принятая мера
TASK = slice(5, 11)       # Task ID … Компонент
KOJI = slice(11, 12)      # SL NVR
VEX = slice(12, 18)       # RHEL NVR … Advisory
LINK = slice(18, 19)      # CVE link
COMMENT = slice(19, 20)   # Комментарий

TASK_ID = COLUMNS.index("Task ID")
CVE_ID = COLUMNS.index("CVE ID")
TASK_STATE = COLUMNS.index("Task state")
TASK_DATE = COLUMNS.index("Task date")
ASSIGNEE = COLUMNS.index("Исполнитель")
COMPONENT = COLUMNS.index("Компонент")
SL_NVR = COLUMNS.index("SL NVR (latest build)")
RHEL_STATE = COLUMNS.index("RHEL state")
COMMENT_INDEX = COLUMNS.index("Комментарий")

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def format_date(value: str) -> str:
    """'2026-09-02' → '02.09.2026'; нераспознанное — как есть."""
    match = _ISO_DATE.match(value or "")
    if not match:
        return value
    year, month, day = match.groups()
    return "%s.%s.%s" % (day, month, year)


def with_patch_note(comment: str, patched: bool) -> str:
    """Комментарий с пометкой о патче: пустую ячейку она заменяет, к тексту
    людей дописывается через «; », второй раз не ставится. Без патча ячейка
    не трогается — и пометку прошлого прогона тулза не снимает: в ручной
    колонке своя пометка от написанной людьми не отличима."""
    if not patched or PATCH_NOTE in comment:
        return comment
    if comment.strip() in ("", EMPTY):
        return PATCH_NOTE
    return "%s; %s" % (comment, PATCH_NOTE)


def row(task, nvr: str, verdict, patched: bool = False) -> List[str]:
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
        PATCH_NOTE if patched else "",
    ]
    # пустое — только None и "": CVSS 0.0 — настоящее значение
    return [EMPTY if cell is None or cell == "" else cell for cell in cells]


def write(rows: Iterable[List[str]], handle) -> None:
    writer = csv.writer(handle, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
