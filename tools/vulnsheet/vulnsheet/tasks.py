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
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
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
