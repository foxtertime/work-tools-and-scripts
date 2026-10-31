import tempfile
import unittest
from datetime import date
from pathlib import Path

from taskhistory.snapshots import load_snapshots, parse_tasks, snapshot_date


BLOCK = "Состоит из\nTASK-1\nCVE-2026-12345 vim\nВ работу\n01.09.2026\nКМ"


class SnapshotTests(unittest.TestCase):
    def test_six_line_block_and_windows_text(self):
        tasks, warnings = parse_tasks("\ufeff" + BLOCK.replace("\n", "\r\n") + "\r\n", "a.txt")
        self.assertEqual(warnings, [])
        task = tasks["task-1"]
        self.assertEqual((task.task_id, task.cve, task.component, task.state,
                          task.created, task.assignee),
                         ("TASK-1", "CVE-2026-12345", "vim", "В работу", "01.09.2026", "КМ"))

    def test_blank_lines_split_blocks(self):
        tasks, _ = parse_tasks(BLOCK + "\n \t\n" + BLOCK.replace("TASK-1", "TASK-2"), "a")
        self.assertEqual(list(tasks), ["task-1", "task-2"])

    def test_invalid_blocks_name_source_and_block(self):
        for bad in [BLOCK.rsplit("\n", 1)[0], BLOCK.replace("CVE-2026-12345 vim", "other"),
                    BLOCK.replace("CVE-2026-12345 vim", "CVE-2026-12345"),
                    BLOCK.replace("В работу", "Неизвестен")]:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "source.txt.*блок 2"):
                parse_tasks(BLOCK + "\n\n" + bad, "source.txt")

    def test_empty_snapshot_is_error(self):
        with self.assertRaisesRegex(ValueError, "пуст"):
            parse_tasks("\n \n", "a")

    def test_repeated_block_warns_but_conflicting_owner_fails(self):
        tasks, warnings = parse_tasks(BLOCK + "\n\n" + BLOCK, "a")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(warnings), 1)
        with self.assertRaisesRegex(ValueError, "TASK-1"):
            parse_tasks(BLOCK + "\n\n" + BLOCK.replace("КМ", "АБ"), "a")

    def test_parser_tolerates_case_spaces_and_yo(self):
        tasks, _ = parse_tasks(BLOCK.replace("CVE-", "cve-").replace("В работу", " рЕшЁн "), "a")
        self.assertEqual(tasks["task-1"].cve, "CVE-2026-12345")

    def test_date_from_basename_only(self):
        self.assertEqual(snapshot_date(Path("folder-01-01-2000/input-28-10-2026.txt")), date(2026, 10, 28))

    def test_invalid_missing_ambiguous_dates(self):
        for name in ["input.txt", "input-31-02-2026.txt", "a-01-10-2026-02-10-2026.txt",
                     "a-128-10-2026.txt"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                snapshot_date(Path(name))

    def test_load_sorts_by_snapshot_date(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "input-28-10-2026.txt", Path(directory) / "input-21-10-2026.txt"]
            for path in paths:
                path.write_text(BLOCK, encoding="utf-8")
            snapshots, warnings = load_snapshots(paths)
            self.assertEqual([s.date for s in snapshots], [date(2026, 10, 21), date(2026, 10, 28)])
            self.assertEqual(warnings, [])

    def test_duplicate_dates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ["a-28-10-2026.txt", "b-28-10-2026.txt"]]
            for path in paths:
                path.write_text(BLOCK, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "дат"):
                load_snapshots(paths)

    def test_bad_encoding_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input-28-10-2026.txt"
            path.write_bytes(b"\xff")
            with self.assertRaisesRegex(ValueError, "UTF-8"):
                load_snapshots([path])
            path.unlink()
            with self.assertRaisesRegex(ValueError, "input-28-10-2026"):
                load_snapshots([path])
