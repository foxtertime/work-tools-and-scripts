import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from tests.fakes import RHEL9, FakeKojiSession, csaf, pid
from vulnsheet import __version__
from vulnsheet.cli import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL, main, rejects_path
from vulnsheet.report import COLUMNS
from vulnsheet.vex import vex_url

BLOCK = "Состоит из\nTASKID-181229\nCVE-2026-73070 vim\nОтменен\n22.09.2026\nКМ"
BAD = "Состоит из\nTASKID-181231\nCVE-2026-73072 bash\nВ работу\n23.09.2026"
HEADER = ";".join(COLUMNS)
EXPECTED = ("-;-;-;-;-;TASKID-181229;CVE-2026-73070;Отменен;22.09.2026;КМ;vim;"
            "vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;Moderate;5.5;-;"
            "https://access.redhat.com/security/cve/CVE-2026-73070;-")
VIM_DOC = csaf("CVE-2026-73070", [("under_investigation", RHEL9, "vim")],
               scores=[{"cvss_v3": {"baseScore": 5.5}, "products": [pid(RHEL9, "vim")]}])


class CliCase(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)
        mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.path("cache")}).start()
        self.session = FakeKojiSession(builds={"vim": "vim-8.2.2637-26.sl9_8.6^4"})
        self.connect = mock.patch("vulnsheet.kojiclient.connect",
                                  return_value=self.session).start()
        self.docs = {vex_url("CVE-2026-73070"): VIM_DOC}
        self.download = mock.patch("vulnsheet.vex.download",
                                   side_effect=self._download).start()
        mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)
        self.log = ""

    def _download(self, url, timeout=None):
        doc = self.docs.get(url)
        if isinstance(doc, Exception):
            raise doc
        return None if doc is None else json.dumps(doc).encode()

    def path(self, name):
        return os.path.join(self.room, name)

    def run_cli(self, *extra, text=BLOCK + "\n", data=None):
        src = self.path("tasks.txt")
        with open(src, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        argv = ["--rhel", "9", "--koji-url", "https://koji.example.com/kojihub",
                "--tag", "sl9", src, "-o", self.path("report.csv")] + list(extra)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(argv)
        self.log = err.getvalue()
        return code

    def report_lines(self):
        with open(self.path("report.csv"), encoding="utf-8") as handle:
            return handle.read().splitlines()


class HappyPathTest(CliCase):
    def test_example_from_the_task(self):
        self.assertEqual(self.run_cli(), EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        self.assertFalse(os.path.exists(self.path("report.rejected.txt")))
        self.assertIn("Under investigation 1", self.log)
        self.assertIn("написан", self.log)

    def test_order_duplicates_and_single_requests(self):
        second = (BLOCK.replace("181229", "181230").replace("73070", "73071")
                  .replace("vim", "openssl"))
        code = self.run_cli(text=BLOCK + "\n\n" + second + "\n\n" + BLOCK + "\n")
        lines = self.report_lines()
        self.assertEqual(code, EXIT_OK)  # NOT_FOUND и no VEX record — не ошибки
        self.assertEqual(len(lines), 4)
        self.assertEqual((lines[1], lines[3]), (EXPECTED, EXPECTED))
        self.assertIn(";openssl;NOT_FOUND;", lines[2])
        self.assertIn(";no VEX record;", lines[2])
        self.assertEqual(self.session.calls, [("sl9", "vim"), ("sl9", "openssl")])
        self.assertEqual(self.download.call_count, 2)

    def test_vex_cache_lives_under_xdg_cache_home(self):
        self.run_cli()
        self.assertTrue(os.path.exists(self.path("cache/vulnsheet/cve-2026-73070.json")))

    def test_stdout_when_no_output_given(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--rhel", "9", "--koji-url", "https://k/kojihub",
                         "--tag", "sl9", src])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out.getvalue(), HEADER + "\n" + EXPECTED + "\n")


class RejectsTest(CliCase):
    def test_bad_block_goes_to_rejects_file(self):
        code = self.run_cli(text=BLOCK + "\n\n" + BAD + "\n")
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        with open(self.path("report.rejected.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), BAD + "\n")
        self.assertIn("блок 2", self.log)
        self.assertIn("5 строк", self.log)

    def test_explicit_rejects_path(self):
        self.run_cli("--rejects", self.path("bad.txt"), text=BAD)
        self.assertTrue(os.path.exists(self.path("bad.txt")))

    def test_stale_rejects_file_is_removed(self):
        with open(self.path("report.rejected.txt"), "w") as handle:
            handle.write("старьё")
        self.assertEqual(self.run_cli(), EXIT_OK)
        self.assertFalse(os.path.exists(self.path("report.rejected.txt")))

    def test_all_blocks_rejected_writes_header_and_skips_koji(self):
        self.assertEqual(self.run_cli(text=BAD), EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER])
        self.connect.assert_not_called()

    def test_default_rejects_path(self):
        self.assertEqual(rejects_path("report.csv", None), "report.rejected.txt")
        self.assertEqual(rejects_path("out/report", None), "out/report.rejected.txt")
        self.assertEqual(rejects_path("-", None), "vulnsheet.rejected.txt")
        self.assertEqual(rejects_path("report.csv", "bad.txt"), "bad.txt")


class PartialTest(CliCase):
    def test_fetch_error_marks_row(self):
        self.docs[vex_url("CVE-2026-73070")] = OSError("сеть")
        self.assertEqual(self.run_cli(), EXIT_PARTIAL)
        self.assertIn(";fetch error;", self.report_lines()[1])

    def test_koji_error_for_package_marks_row(self):
        self.session.errors["vim"] = "boom"
        self.assertEqual(self.run_cli(), EXIT_PARTIAL)
        self.assertIn(";vim;ERROR;", self.report_lines()[1])


class FatalTest(CliCase):
    def assertFatal(self, code, needle):
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn(needle, self.log)
        self.assertNotIn("Traceback", self.log)

    def test_unknown_tag_is_fatal(self):
        self.session.tags = {"sl9-other"}
        self.assertFatal(self.run_cli(), "нет тега sl9")

    def test_empty_input_is_fatal(self):
        self.assertFatal(self.run_cli(text="\n \n"), "ни одного блока")

    def test_non_utf8_input_is_fatal(self):
        self.assertFatal(self.run_cli(data=BLOCK.encode("cp1251")), "UTF-8")

    def test_missing_input_is_fatal(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--rhel", "9", "--koji-url", "https://k", "--tag", "sl9",
                         self.path("нет-такого.txt"), "-o", self.path("r.csv")])
        self.log = err.getvalue()
        self.assertFatal(code, "вход")

    def test_unwritable_output_fails_before_network(self):
        code = self.run_cli("-o", self.path("нет-каталога/report.csv"))
        self.assertFatal(code, "выход")
        self.connect.assert_not_called()

    def test_bad_rhel_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--rhel", "nine", "--koji-url", "https://k", "--tag", "sl9"])
        self.assertEqual(caught.exception.code, 2)

    def test_failed_run_keeps_previous_report(self):
        with open(self.path("report.csv"), "w", encoding="utf-8") as handle:
            handle.write("прошлый отчёт\n")
        self.session.tags = {"sl9-other"}
        self.assertFatal(self.run_cli(), "нет тега sl9")
        with open(self.path("report.csv"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "прошлый отчёт\n")
        leftovers = [name for name in os.listdir(self.room) if name.startswith(".vulnsheet-")]
        self.assertEqual(leftovers, [])

    def test_unwritable_rejects_dir_fails_before_network(self):
        code = self.run_cli("--rejects", self.path("нет-каталога/bad.txt"))
        self.assertFatal(code, "отбраковки")
        self.connect.assert_not_called()


class BrokenPipeTest(CliCase):
    def test_broken_pipe_on_stdout_exits_quietly(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        err = io.StringIO()
        with mock.patch("vulnsheet.report.write", side_effect=BrokenPipeError()):
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = main(["--rhel", "9", "--koji-url", "https://k/kojihub",
                             "--tag", "sl9", src])
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertNotIn("фатальная ошибка", err.getvalue())


class StaleRejectsRemovalTest(CliCase):
    def test_removal_failure_is_a_warning_not_fatal(self):
        with open(self.path("report.rejected.txt"), "w") as handle:
            handle.write("старьё")
        with mock.patch("vulnsheet.cli.os.remove", side_effect=OSError("нет прав")):
            code = self.run_cli()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("WARNING", self.log)


class VersionFlagTest(unittest.TestCase):
    def test_prints_version_without_other_arguments(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "vulnsheet " + __version__)
