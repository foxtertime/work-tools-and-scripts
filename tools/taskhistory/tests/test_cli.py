import contextlib
import csv
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from taskhistory.cli import main


ROOT = Path(__file__).resolve().parents[1]
BLOCK = "Состоит из\nTASK-1\nCVE-2026-12345 vim\nВ работу\n01.09.2026\nКМ\n"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.paths = [self.root / f"input-{day}-10-2026.txt" for day in (21, 28, 31)]
        for path, text in zip(self.paths, [BLOCK, BLOCK.replace("КМ", "АБ"),
                              BLOCK.replace("КМ", "АБ").replace("В работу", "Решен")]):
            path.write_text(text, encoding="utf-8")
        self.output = self.root / "history.csv"

    def run_cli(self, *extra, paths=None, output=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = [str(p) for p in (self.paths if paths is None else paths)]
        args += ["-o", str(self.output if output is None else output), *extra]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(args)
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def rows(self):
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream, delimiter=";"))

    def test_csv_has_bom_and_correct_dates_sorted_by_person(self):
        code, stdout, stderr = self.run_cli(paths=list(reversed(self.paths)))
        self.assertEqual((code, stdout), (0, ""), stderr)
        self.assertTrue(self.output.read_bytes().startswith(b"\xef\xbb\xbf"))
        rows = self.rows()
        self.assertEqual([r["Исполнитель"] for r in rows], ["АБ", "КМ"])
        self.assertEqual(len(rows[0]), 14)
        self.assertEqual((rows[0]["Взята в работу (снимок)"], rows[0]["Завершена (снимок)"]),
                         ("28.10.2026", "31.10.2026"))
        self.assertEqual(rows[1]["Взята в работу (снимок)"], "")
        self.assertIn("3", stderr)

    def test_filter_is_applied_after_reconstructing_takeover(self):
        code, _, stderr = self.run_cli("--assignee", " аб ")
        self.assertEqual(code, 0, stderr)
        row, = self.rows()
        self.assertEqual(row["Исполнитель"], "АБ")
        self.assertEqual(row["Взята в работу (снимок)"], "28.10.2026")
        self.assertIn("КМ", row["История изменений"])

    def test_repeat_filter_selects_multiple_people(self):
        code, _, stderr = self.run_cli("--assignee", "КМ", "--assignee", "АБ")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.rows()), 2)

    def test_filter_can_select_unassigned(self):
        self.paths[0].write_text(BLOCK.replace("КМ", "-"), encoding="utf-8")
        code, _, stderr = self.run_cli("--assignee", "-")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.rows()[0]["Исполнитель"], "Без исполнителя")

    def test_unknown_initials_warn_and_produce_header_only(self):
        code, _, stderr = self.run_cli("--assignee", "ЯЯ")
        self.assertEqual(code, 0)
        self.assertEqual(self.rows(), [])
        self.assertIn("ЯЯ", stderr)

    def test_csv_quotes_semicolons_and_quotes(self):
        for path in self.paths:
            path.write_text(path.read_text(encoding="utf-8").replace(" vim", ' vim; "enhanced"'), encoding="utf-8")
        code, _, stderr = self.run_cli()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.rows()[0]["Компонент"], 'vim; "enhanced"')

    def test_invalid_block_preserves_previous_report(self):
        self.output.write_bytes(b"previous report")
        self.paths[-1].write_text("broken", encoding="utf-8")
        code, _, stderr = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(self.output.read_bytes(), b"previous report")
        self.assertIn(self.paths[-1].name, stderr)
        self.assertNotIn("Traceback", stderr)

    def test_refuses_output_that_is_an_input(self):
        original = self.paths[0].read_bytes()
        code, _, stderr = self.run_cli(output=self.paths[0])
        self.assertEqual(code, 2)
        self.assertEqual(self.paths[0].read_bytes(), original)
        self.assertIn("вход", stderr)

    def test_refuses_symlink_and_hardlink_to_input(self):
        for kind in ["symlink", "hardlink"]:
            with self.subTest(kind=kind):
                alias = self.root / kind
                if kind == "symlink":
                    alias.symlink_to(self.paths[0])
                else:
                    os.link(self.paths[0], alias)
                original = self.paths[0].read_bytes()
                code, _, stderr = self.run_cli(output=alias)
                self.assertEqual(code, 2, stderr)
                self.assertEqual(self.paths[0].read_bytes(), original)

    def test_output_symlink_updates_target_and_preserves_link(self):
        target = self.root / "real.csv"
        target.write_text("old", encoding="utf-8")
        self.output.symlink_to(target)
        code, _, stderr = self.run_cli()
        self.assertEqual(code, 0, stderr)
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(len(self.rows()), 2)

    def test_requires_two_snapshots(self):
        code, _, _ = self.run_cli(paths=self.paths[:1])
        self.assertEqual(code, 2)
        self.assertFalse(self.output.exists())

    def test_refuses_repeated_input_through_differently_dated_links(self):
        for kind in ["symlink", "hardlink"]:
            with self.subTest(kind=kind):
                alias = self.root / f"{kind}-24-10-2026.txt"
                if kind == "symlink":
                    alias.symlink_to(self.paths[0])
                else:
                    os.link(self.paths[0], alias)
                self.output.write_bytes(b"previous report")
                code, _, stderr = self.run_cli(paths=[self.paths[0], alias])
                self.assertEqual(code, 2, stderr)
                self.assertIn("повтор", stderr.casefold())
                self.assertEqual(self.output.read_bytes(), b"previous report")

    def test_output_errors_are_reported_without_traceback(self):
        code, _, stderr = self.run_cli(output=self.root / "missing" / "r.csv")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", stderr)
        code, _, stderr = self.run_cli(output=self.root)
        self.assertEqual(code, 2)
        self.assertFalse(list(self.root.glob(".*.tmp")))

    def test_empty_filter_is_error(self):
        code, _, _ = self.run_cli("--assignee", "   ")
        self.assertEqual(code, 2)
        self.assertFalse(self.output.exists())

    def test_module_entrypoint_and_version(self):
        result = subprocess.run([sys.executable, "-m", "taskhistory", "--version"],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.1.0", result.stdout)
        result = subprocess.run([sys.executable, "-m", "taskhistory", "--help"],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--assignee", result.stdout)

    def test_real_module_execution(self):
        result = subprocess.run([sys.executable, "-m", "taskhistory", *map(str, self.paths),
                                 "--assignee", "АБ", "-o", str(self.output)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.rows()[0]["Завершена (снимок)"], "31.10.2026")
