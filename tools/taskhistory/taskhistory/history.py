"""Восстановление наблюдаемых событий, без догадок о событиях между снимками."""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from .snapshots import DONE, Snapshot, Task, person_key, state_key


HEADERS = [
    "Исполнитель", "Task ID", "CVE ID", "Компонент", "Дата создания", "Период",
    "Впервые у исполнителя (снимок)", "Взята в работу (снимок)",
    "Завершена (снимок)", "Последний статус", "Наблюдалась до (снимок)",
    "Причина окончания периода", "История изменений", "Примечание",
]


def display_person(task: Task) -> str:
    return task.assignee.strip() if person_key(task.assignee) else "Без исполнителя"


def format_date(value: Optional[date]) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


@dataclass
class Period:
    task: Task
    number: int
    first_seen: date
    last_seen: date
    taken: Optional[date] = None
    finished: Optional[date] = None
    reason: str = "Последний снимок"
    history: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def cells(self) -> List[str]:
        return [display_person(self.task), self.task.task_id, self.task.cve,
                self.task.component, self.task.created, str(self.number),
                format_date(self.first_seen), format_date(self.taken),
                format_date(self.finished), self.task.state, format_date(self.last_seen),
                self.reason, " | ".join(self.history), " | ".join(self.notes)]


def build_history(snapshots: Iterable[Snapshot]) -> List[Period]:
    periods: List[Period] = []
    active: Dict[str, Period] = {}
    last: Dict[str, Tuple[Task, date]] = {}
    numbers: Dict[str, int] = {}

    for snapshot in sorted(snapshots, key=lambda item: item.date):
        when = snapshot.date
        stamp = format_date(when)
        for key in list(active):
            if key not in snapshot.tasks:
                old = active.pop(key)
                old.reason = "Нет в снимке"
                old.history.append(f"{stamp}: нет в снимке")

        for key, task in snapshot.tasks.items():
            previous = last.get(key)
            old = active.get(key)
            prev_task = previous[0] if previous else None
            owner_changed = bool(prev_task and person_key(prev_task.assignee) != person_key(task.assignee))
            was_done = bool(prev_task and state_key(prev_task.state) in DONE)
            is_done = state_key(task.state) in DONE
            reopened = was_done and not is_done
            completed = prev_task is not None and not was_done and is_done

            if old is None or owner_changed or reopened:
                if old is not None:
                    old.reason = (f"Передана исполнителю {display_person(task)}"
                                  if owner_changed else "Повторно открыта")
                    old.history.append(f"{stamp}: {old.reason}")
                number = numbers.get(key, 0) + 1
                numbers[key] = number
                current = Period(task, number, when, when)
                current.history.append(f"{stamp}: {task.state}; исполнитель {display_person(task)}")

                if prev_task is None:
                    current.notes.append("Первое наблюдение; дата взятия неизвестна")
                    if is_done:
                        current.notes.append("Уже завершена; дата завершения неизвестна")
                else:
                    if old is None:
                        current.notes.append(f"После отсутствия; предыдущее наблюдение {format_date(previous[1])}")
                    if owner_changed:
                        if person_key(task.assignee):
                            current.taken = when
                        current.history.append(f"{stamp}: смена исполнителя {display_person(prev_task)} → {display_person(task)}")
                    if reopened:
                        current.notes.append("Повторно открыта")
                    if completed:
                        current.finished = when
                        if owner_changed:
                            current.notes.append("Смена исполнителя и завершение видны в одном снимке; порядок событий неизвестен")
                    elif was_done and is_done:
                        current.notes.append("Ранее завершена; нового завершения не наблюдалось")
                periods.append(current)
                active[key] = current
            else:
                current = old
                current.task = task
                current.last_seen = when
                if state_key(prev_task.state) != state_key(task.state):
                    current.history.append(f"{stamp}: {prev_task.state} → {task.state}")
                if completed:
                    current.finished = when
            last[key] = (task, when)
    return periods
