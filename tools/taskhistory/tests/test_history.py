import unittest
from datetime import date
from pathlib import Path

from taskhistory.history import build_history
from taskhistory.snapshots import Snapshot, Task


def task(owner="КМ", state="В работу", task_id="TASK-1"):
    return Task(task_id, "CVE-2026-12345", "vim", state, "01.09.2026", owner)


def snapshot(day, *tasks):
    return Snapshot(date(2026, 10, day), Path(f"input-{day:02d}-10-2026.txt"),
                    {t.task_id.casefold(): t for t in tasks})


class HistoryTests(unittest.TestCase):
    def test_three_snapshots_takeover_then_completion(self):
        periods = build_history([snapshot(21, task()), snapshot(28, task("АБ")),
                                 snapshot(31, task("АБ", "Выполнен"))])
        self.assertEqual(len(periods), 2)
        old, new = periods
        self.assertEqual((old.task.assignee, old.taken, old.finished, old.last_seen),
                         ("КМ", None, None, date(2026, 10, 21)))
        self.assertIn("АБ", old.reason)
        self.assertEqual((new.task.assignee, new.taken, new.finished, new.last_seen),
                         ("АБ", date(2026, 10, 28), date(2026, 10, 31), date(2026, 10, 31)))
        self.assertEqual(new.cells()[6:9], ["28.10.2026", "28.10.2026", "31.10.2026"])

    def test_status_changes_do_not_count_as_takeover(self):
        periods = build_history([snapshot(21, task()), snapshot(28, task(state="В работе")),
                                 snapshot(31, task())])
        self.assertEqual(len(periods), 1)
        self.assertIsNone(periods[0].taken)
        self.assertEqual(periods[0].last_seen, date(2026, 10, 31))
        self.assertIn("28.10.2026", " ".join(periods[0].history))

    def test_all_terminal_statuses_complete(self):
        for state in ["Отменен", "Выполнен", "Решен", "рЕшЁн"]:
            with self.subTest(state=state):
                periods = build_history([snapshot(21, task()), snapshot(28, task(state=state))])
                self.assertEqual(periods[0].finished, date(2026, 10, 28))

    def test_initial_closed_task_has_unknown_event_dates(self):
        p, = build_history([snapshot(21, task(state="Решен")), snapshot(28, task(state="Решен"))])
        self.assertIsNone(p.taken)
        self.assertIsNone(p.finished)
        self.assertIn("завершения неизвестна", " ".join(p.notes))

    def test_first_appearance_in_later_snapshot_is_not_proven_takeover(self):
        periods = build_history([snapshot(21, task(task_id="OTHER")), snapshot(28, task())])
        p = next(p for p in periods if p.task.task_id == "TASK-1")
        self.assertIsNone(p.taken)
        self.assertEqual(p.first_seen, date(2026, 10, 28))

    def test_unassigned_to_person_is_takeover(self):
        old, new = build_history([snapshot(21, task("-")), snapshot(28, task())])
        self.assertEqual(old.cells()[0], "Без исполнителя")
        self.assertEqual(new.taken, date(2026, 10, 28))

    def test_removing_owner_does_not_mean_takeover_or_completion(self):
        old, new = build_history([snapshot(21, task()), snapshot(28, task("-"))])
        self.assertIsNone(new.taken)
        self.assertIsNone(old.finished)

    def test_simultaneous_takeover_and_completion_belong_to_new_owner(self):
        old, new = build_history([snapshot(21, task()), snapshot(28, task("АБ", "Решен"))])
        self.assertIsNone(old.finished)
        self.assertEqual(new.taken, date(2026, 10, 28))
        self.assertEqual(new.finished, date(2026, 10, 28))
        self.assertIn("порядок", " ".join(new.notes))

    def test_transfer_of_closed_task_is_not_another_completion(self):
        periods = build_history([snapshot(21, task()), snapshot(24, task(state="Решен")),
                                 snapshot(28, task("АБ", "Решен"))])
        self.assertEqual(periods[0].finished, date(2026, 10, 24))
        self.assertIsNone(periods[1].finished)
        self.assertEqual(periods[1].taken, date(2026, 10, 28))

    def test_terminal_to_terminal_keeps_first_completion(self):
        p, = build_history([snapshot(21, task()), snapshot(24, task(state="Решен")),
                            snapshot(28, task(state="Отменен"))])
        self.assertEqual(p.finished, date(2026, 10, 24))
        self.assertEqual(p.task.state, "Отменен")

    def test_reopening_preserves_previous_finish_without_false_takeover(self):
        periods = build_history([snapshot(21, task()), snapshot(24, task(state="Решен")),
                                 snapshot(28, task()), snapshot(31, task(state="Выполнен"))])
        self.assertEqual(len(periods), 2)
        self.assertEqual([p.finished for p in periods], [date(2026, 10, 24), date(2026, 10, 31)])
        self.assertIsNone(periods[1].taken)
        self.assertIn("Повторно открыта", " ".join(periods[1].notes))

    def test_reopening_and_takeover_create_one_period(self):
        old, new = build_history([snapshot(21, task(state="Решен")), snapshot(28, task("АБ"))])
        self.assertEqual(new.number, 2)
        self.assertEqual(new.taken, date(2026, 10, 28))

    def test_disappearance_is_not_completion_and_return_creates_period(self):
        periods = build_history([snapshot(21, task()), snapshot(24, task(task_id="OTHER")),
                                 snapshot(28, task())])
        periods = [p for p in periods if p.task.task_id == "TASK-1"]
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0].reason, "Нет в снимке")
        self.assertIsNone(periods[0].finished)
        self.assertEqual(periods[0].last_seen, date(2026, 10, 21))
        self.assertIsNone(periods[1].taken)
        self.assertIn("После отсутствия", " ".join(periods[1].notes))

    def test_return_after_gap_compares_with_last_known_owner_and_status(self):
        periods = build_history([snapshot(21, task()), snapshot(24, task(task_id="OTHER")),
                                 snapshot(28, task("АБ", "Решен"))])
        new = periods[-1]
        self.assertEqual(new.taken, date(2026, 10, 28))
        self.assertEqual(new.finished, date(2026, 10, 28))

    def test_case_and_yo_do_not_create_events(self):
        p, = build_history([snapshot(21, task(state="Решен")),
                            snapshot(28, task(" км ", " рЕшЁн "))])
        self.assertIsNone(p.taken)
        self.assertIsNone(p.finished)
        self.assertEqual(len(p.history), 1)

    def test_return_to_previous_owner_creates_new_takeover(self):
        periods = build_history([snapshot(21, task()), snapshot(24, task("АБ")), snapshot(28, task())])
        self.assertEqual([p.number for p in periods], [1, 2, 3])
        self.assertEqual(periods[2].taken, date(2026, 10, 28))

    def test_unchanged_snapshots_produce_single_period(self):
        p, = build_history([snapshot(21, task()), snapshot(24, task()), snapshot(28, task())])
        self.assertEqual(p.reason, "Последний снимок")
        self.assertEqual(len(p.history), 1)
