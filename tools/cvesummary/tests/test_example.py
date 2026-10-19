import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr
import io

from cvesummary import cli
from tests import example

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)


class ExampleTest(unittest.TestCase):
    def test_example_builds_a_page(self):
        with tempfile.TemporaryDirectory() as folder:
            table = os.path.join(folder, "пример.xlsx")
            example.main([table])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main([table, "--as-of", "2026-10-19"]), cli.EXIT_OK)
            with open(os.path.join(folder, "пример.html"), encoding="utf-8") as handle:
                data = json.loads(DATA_RE.search(handle.read()).group(1))
        self.assertEqual(len(data["rows"]), 100)
        self.assertEqual(data["meta"]["header_row"], 2)
        self.assertTrue(any(r["status"] == "Ожидает ревью" for r in data["rows"]))

    def test_example_as_csv_gives_the_same_rows(self):
        pages = {}
        with tempfile.TemporaryDirectory() as folder:
            for name in ("пример.xlsx", "пример.csv"):
                table = os.path.join(folder, name)
                example.main([table])
                output = os.path.join(folder, name + ".html")
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main([table, "-o", output, "--as-of", "2026-10-19"]),
                                     cli.EXIT_OK)
                with open(output, encoding="utf-8") as handle:
                    pages[name] = json.loads(DATA_RE.search(handle.read()).group(1))
        self.assertEqual(pages["пример.csv"]["rows"], pages["пример.xlsx"]["rows"])
        self.assertEqual(pages["пример.csv"]["meta"]["header_row"], 2)
