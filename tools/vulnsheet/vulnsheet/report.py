"""Строка итоговой таблицы и запись CSV.

Формат фиксирован процессом: 27 колонок, разделитель ';', пустая ячейка —
'-', даты — dd.mm.yyyy. Колонки процесса (разработчик, статус, даты работ,
принятая мера, комментарий) заполняют люди, здесь они — прочерки. P и D —
признаки про билд из SL NVR: «+» — патч под CVE лежит в каталоге PATCH
коммита сборки (P), апстрим-версия вне уязвимых диапазонов (D); «-» —
нет патча, версия в диапазоне или проверить не удалось. ai_* — поля
результата из JSON с AI-вердиктами (--ai) по паре CVE + компонент, перед
комментарием; нет результата — прочерки.
"""
import csv
import re
from typing import Iterable, List, Sequence

from .vex import FIXED

EMPTY = "-"
YES = "+"
NO = "-"
CVE_PAGE = "https://access.redhat.com/security/cve/{cve}"
COLUMNS = [
    "Разработчик", "Статус", "Start date", "End date", "Принятая мера",
    "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель",
    "Компонент", "P", "D", "SL NVR (latest build)", "RHEL NVR (if fixed)",
    "Fix date", "RHEL state", "RHEL severity", "RHEL CVSS",
    "Advisory (RHSA)", "CVE link",
    "ai_nvr", "ai_verdict", "ai_confidence", "ai_remediation", "ai_run",
    "Комментарий",
]
AI_EMPTY = (EMPTY,) * 5

MISSING = "Missing"  # Task state строки, чьей задачи больше нет в блоках


def _group(first: str, last: str) -> slice:
    return slice(COLUMNS.index(first), COLUMNS.index(last) + 1)


# Группы колонок для режимов обновления: что в каком режиме откуда берётся,
# см. таблицу в README, «Режимы» (дизайн-документ
# docs/superpowers/specs/2026-09-24-vulnsheet-update-modes-design.md писался
# до колонок P и D).
DEVELOPER = _group("Разработчик", "Принятая мера")
TASK = _group("Task ID", "Компонент")
MARKS = _group("P", "D")
KOJI = _group("SL NVR (latest build)", "SL NVR (latest build)")
VEX = _group("RHEL NVR (if fixed)", "Advisory (RHSA)")
LINK = _group("CVE link", "CVE link")
COMMENT = _group("Комментарий", "Комментарий")
AI = _group("ai_nvr", "ai_run")

TASK_ID = COLUMNS.index("Task ID")
CVE_ID = COLUMNS.index("CVE ID")
TASK_STATE = COLUMNS.index("Task state")
TASK_DATE = COLUMNS.index("Task date")
ASSIGNEE = COLUMNS.index("Исполнитель")
COMPONENT = COLUMNS.index("Компонент")
PATCH = COLUMNS.index("P")
RANGE = COLUMNS.index("D")
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


def row(task, nvr: str, verdict, patch: str = NO, ranged: str = NO,
        ai: Sequence[str] = AI_EMPTY) -> List[str]:
    fixed = verdict.state == FIXED
    cells = [
        "", "", "", "", "",
        task.task_id, task.cve, task.state, task.date, task.assignee,
        task.component, patch, ranged, nvr,
        verdict.fixed_nvr if fixed else "",
        format_date(verdict.fix_date) if fixed else "",
        verdict.state, verdict.severity, verdict.cvss,
        verdict.advisory_url if fixed else "",
        CVE_PAGE.format(cve=task.cve),
    ] + list(ai) + [
        "",
    ]
    # пустое — только None и "": CVSS 0.0 — настоящее значение
    return [EMPTY if cell is None or cell == "" else cell for cell in cells]


def write(rows: Iterable[List[str]], handle) -> None:
    writer = csv.writer(handle, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
