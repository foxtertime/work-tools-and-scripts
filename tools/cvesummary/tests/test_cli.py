import datetime
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cvesummary import __version__, cli
from tests.xlsxmake import write

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)
REQUIRED = ["CVE ID", "Компонент", "RHEL state", "RHEL severity"]
HEADER = ["Разработчик", "Статус", "Start date", "End date"] + REQUIRED
ROWS = [HEADER, ["Иванов", "Готов", "05.10.2026", "07.10.2026", "CVE-1", "bash", "Affected", "Low"],
        ["", "", "", "", "", "bash", "", ""]]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.table = self.path("t.xlsx")
        write(self.table, ROWS)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def run_cli(self, *args):
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(list(args))
        return code, err.getvalue()

    def data(self, path):
        with open(path, encoding="utf-8") as handle:
            return json.loads(DATA_RE.search(handle.read()).group(1))


class WriteTest(Base):
    def test_default_output_next_to_table(self):
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        data = self.data(self.path("t.html"))
        self.assertEqual([r["cve"] for r in data["rows"]], ["CVE-1"])
        self.assertEqual(data["meta"]["as_of"], "2026-10-19")
        self.assertEqual(data["meta"]["skipped"], 1)
        self.assertEqual(data["meta"]["source"], "t.xlsx")
        self.assertIn("записано", log)
        self.assertIn("без CVE ID пропущено: 1", log)

    def test_explicit_output(self):
        code, _ = self.run_cli(self.table, "-o", self.path("x.html"), "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue(os.path.exists(self.path("x.html")))

    def test_overwrite_warns(self):
        self.run_cli(self.table, "--as-of", "2026-10-19")
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("перезаписан", log)

    def test_as_of_defaults_to_today(self):
        with mock.patch.object(cli, "_today", return_value=datetime.date(2026, 1, 2)):
            self.run_cli(self.table)
        self.assertEqual(self.data(self.path("t.html"))["meta"]["as_of"], "2026-01-02")

    def test_page_is_readable_by_others(self):
        self.run_cli(self.table, "--as-of", "2026-10-19")
        mode = os.stat(self.path("t.html")).st_mode & 0o777
        self.assertEqual(mode, 0o666 & ~cli._umask())

    def test_only_required_columns(self):
        write(self.table, [REQUIRED, ["CVE-1", "bash", "Affected", "Low"]])
        code, log = self.run_cli(self.table, "--as-of", "2026-10-19")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("Разработчик", log)  # названа среди отсутствующих
        self.assertEqual(self.data(self.path("t.html"))["rows"][0]["dev"], "")


class FailTest(Base):
    def test_bad_as_of(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.main([self.table, "--as-of", "19.10.2026"])
        self.assertEqual(caught.exception.code, cli.EXIT_FATAL)

    def test_not_xlsx(self):
        with open(self.table, "wb") as handle:
            handle.write(b"nope")
        code, log = self.run_cli(self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        self.assertIn(self.table, log)
        self.assertFalse(os.path.exists(self.path("t.html")))

    def test_missing_required_columns(self):
        write(self.table, [["CVE ID"], ["CVE-1"]])
        code, log = self.run_cli(self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        self.assertIn("Компонент", log)

    def test_output_cannot_be_the_table(self):
        with open(self.table, "rb") as handle:
            before = handle.read()
        code, log = self.run_cli(self.table, "-o", self.table)
        self.assertEqual(code, cli.EXIT_FATAL)
        with open(self.table, "rb") as handle:
            self.assertEqual(handle.read(), before)
        html_named = self.path("t.html")
        write(html_named, ROWS)
        code, _ = self.run_cli(html_named)
        self.assertEqual(code, cli.EXIT_FATAL)

    def test_version(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["--version"])
        self.assertIn(__version__, out.getvalue())
