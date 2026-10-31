"""Проверка и чтение независимых снимков задач."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


STATES = {"в работу", "в работе", "выполнен", "отменен", "решен"}
DONE = {"выполнен", "отменен", "решен"}
DATE_RE = re.compile(r"(?<![0-9])[0-9]{2}-[0-9]{2}-[0-9]{4}(?![0-9])")
CVE_RE = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}\Z", re.IGNORECASE)


def person_key(text: str) -> str:
    value = text.strip().casefold()
    return "" if value in {"", "-", "—"} else value


def state_key(text: str) -> str:
    return text.strip().casefold().replace("ё", "е")


@dataclass(frozen=True)
class Task:
    task_id: str
    cve: str
    component: str
    state: str
    created: str
    assignee: str


@dataclass(frozen=True)
class Snapshot:
    date: date
    path: Path
    tasks: Dict[str, Task]


def snapshot_date(path: Path) -> date:
    matches = DATE_RE.findall(Path(path).name)
    if len(matches) != 1:
        raise ValueError(f"{path}: ожидается одна дата DD-MM-YYYY в имени файла")
    try:
        return datetime.strptime(matches[0], "%d-%m-%Y").date()
    except ValueError as exc:
        raise ValueError(f"{path}: невозможная дата {matches[0]}") from exc


def parse_tasks(text: str, source: str) -> Tuple[Dict[str, Task], List[str]]:
    blocks = re.split(r"\n\s*\n", text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip())
    if not text.lstrip("\ufeff").strip():
        raise ValueError(f"{source}: пустой снимок")
    tasks: Dict[str, Task] = {}
    warnings: List[str] = []
    for number, block in enumerate(blocks, 1):
        where = f"{source}: блок {number}"
        lines = [line.strip() for line in block.split("\n")]
        if len(lines) != 6 or any(not line for line in lines):
            raise ValueError(f"{where}: ожидается 6 непустых строк, получено {len(lines)}")
        head = lines[2].split(None, 1)
        if len(head) != 2 or not CVE_RE.fullmatch(head[0]):
            raise ValueError(f"{where}: третья строка должна содержать CVE-ID и компонент")
        if state_key(lines[3]) not in STATES:
            raise ValueError(f"{where}: неизвестный статус {lines[3]!r}")
        task = Task(lines[1], head[0].upper(), head[1].strip(), lines[3], lines[4], lines[5])
        key = task.task_id.casefold()
        if key in tasks:
            if tasks[key] != task:
                raise ValueError(f"{where}: конфликтующие блоки задачи {task.task_id}")
            warnings.append(f"{where}: повтор задачи {task.task_id} пропущен")
        else:
            tasks[key] = task
    return tasks, warnings


def load_snapshots(paths: Iterable[Path]) -> Tuple[List[Snapshot], List[str]]:
    snapshots: List[Snapshot] = []
    warnings: List[str] = []
    dates = {}
    sources = {}
    for item in paths:
        path = Path(item)
        when = snapshot_date(path)
        if when in dates:
            raise ValueError(f"{path}: дата снимка {when:%d.%m.%Y} уже задана файлом {dates[when]}")
        dates[when] = path
        try:
            info = path.stat()
            identity = (info.st_dev, info.st_ino)
            if identity in sources:
                raise ValueError(f"{path}: повторный вход — тот же файл уже задан как {sources[identity]}")
            sources[identity] = path
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ValueError(f"{path}: файл должен быть в UTF-8") from exc
        except OSError as exc:
            raise ValueError(f"{path}: не удалось прочитать файл: {exc}") from exc
        tasks, messages = parse_tasks(text, str(path))
        warnings.extend(messages)
        snapshots.append(Snapshot(when, path, tasks))
    return sorted(snapshots, key=lambda snapshot: snapshot.date), warnings
