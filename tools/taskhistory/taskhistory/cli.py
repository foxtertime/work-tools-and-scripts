"""Командная строка и запись CSV-отчёта."""

import argparse
import csv
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Sequence

from . import __version__
from .history import HEADERS, Period, build_history
from .snapshots import load_snapshots, person_key


def write_report(path: Path, periods: Iterable[Period]) -> None:
    # Следуем существующей символической ссылке, сохраняя саму ссылку.
    target = Path(path).resolve()
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(HEADERS)
            writer.writerows(period.cells() for period in periods)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _check_output(output: Path, inputs: Iterable[Path]) -> None:
    target = output.resolve()
    for path in inputs:
        if target == path.resolve() or (target.exists() and os.path.samefile(target, path)):
            raise ValueError(f"{output}: выход совпадает с входным файлом {path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="История задач по снимкам Jira: взятие по смене инициалов, завершение по статусу.",
        epilog="Пример: python3 -m taskhistory input-21-10-2026.txt input-28-10-2026.txt "
               "--assignee КМ --assignee АБ -o history.csv",
    )
    parser.add_argument("snapshots", metavar="FILE", nargs="+", type=Path,
                        help="снимки с датой DD-MM-YYYY в имени, минимум два")
    parser.add_argument("-o", "--output", required=True, type=Path, help="выходной CSV, UTF-8 BOM, разделитель ;")
    parser.add_argument("--assignee", action="append", default=[], metavar="ИНИЦИАЛЫ",
                        help="оставить только этого исполнителя; флаг можно повторить; - — без исполнителя")
    parser.add_argument("--version", action="version", version=f"taskhistory {__version__}")
    args = parser.parse_args(argv)
    if len(args.snapshots) < 2:
        parser.error("нужно минимум два снимка")
    if any(not value.strip() for value in args.assignee):
        parser.error("--assignee: инициалы не могут быть пустыми")

    try:
        snapshots, warnings = load_snapshots(args.snapshots)
        _check_output(args.output, args.snapshots)
        periods = build_history(snapshots)
        available = {person_key(period.task.assignee) for period in periods}
        requested = {person_key(value): value.strip() for value in args.assignee}
        for key, label in requested.items():
            if key not in available:
                warnings.append(f"исполнитель {label!r} не найден в снимках")
        if requested:
            periods = [period for period in periods if person_key(period.task.assignee) in requested]
        periods.sort(key=lambda period: (person_key(period.task.assignee),
                                        period.task.task_id.casefold(), period.number))
        write_report(args.output, periods)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    for message in warnings:
        print(f"Предупреждение: {message}", file=sys.stderr)
    people = len({person_key(period.task.assignee) for period in periods})
    tasks = len({period.task.task_id.casefold() for period in periods})
    print(f"Снимков: {len(snapshots)}; исполнителей: {people}; задач: {tasks}; "
          f"периодов: {len(periods)}. Отчёт: {args.output}", file=sys.stderr)
    return 0
