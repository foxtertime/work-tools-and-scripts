import io
import json
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from tests.fakes import APPSTREAM96, RHEL9, FakeKojiSession, csaf, pid
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
COMMON = ["--rhel", "9", "--koji-url", "https://koji.example.com/kojihub", "--tag", "sl9"]
VIM_DOC = csaf("CVE-2026-73070", [("under_investigation", RHEL9, "vim")],
               scores=[{"cvss_v3": {"baseScore": 5.5}, "products": [pid(RHEL9, "vim")]}])

try:
    import yaml  # noqa: F401 — только чтобы понять, есть ли PyYAML
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

NGINX_BLOCK = BLOCK.replace("vim", "nginx")
# под RHEL 9 обычный nginx исправлен, а стрим nginx:1.26 — уязвим
NGINX_DOC = csaf("CVE-2026-73070", [("fixed", APPSTREAM96, "nginx-2:1.20.1-22.el9_6.x86_64"),
                                    ("known_affected", APPSTREAM96, "nginx::nginx:1.26")])
CONFIG = """\
koji:
  hub: https://koji.example.com/kojihub
  tag: sl9
rhel: "9"
vex_streams:
  "9":
    nginx: nginx:1.26
"""


class CliCase(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)
        mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.path("cache")}).start()
        # настоящий конфиг из окружения того, кто гоняет тесты, сюда не ходит;
        # patch.dict вернёт переменную на место после теста
        os.environ.pop("VULNSHEET_CONFIG", None)
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

    def run_main(self, *argv):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(COMMON + list(argv))
        self.log = err.getvalue()
        return code

    def run_cli(self, *extra, text=BLOCK + "\n", data=None):
        src = self.path("tasks.txt")
        with open(src, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        return self.run_main("--blocks", src, "-o", self.path("report.csv"), *extra)

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
                         "--tag", "sl9", "--blocks", src])
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
                         "--blocks", self.path("нет-такого.txt"), "-o", self.path("r.csv")])
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

    def test_missing_required_value_is_fatal(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--rhel", "9", "--tag", "sl9", "--blocks", src, "-o", self.path("r.csv")])
        self.log = err.getvalue()
        self.assertFatal(code, "нужен --koji-url или koji.hub в конфиге")
        self.connect.assert_not_called()


@unittest.skipUnless(HAVE_YAML, "нужен PyYAML")
class ConfigTest(CliCase):
    def setUp(self):
        super().setUp()
        self.session.builds["nginx"] = "nginx-1.26.3-1.sl9"
        self.docs[vex_url("CVE-2026-73070")] = NGINX_DOC

    def write_config(self, text=CONFIG):
        path = self.path("vulnsheet.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_raw(self, *argv, text=NGINX_BLOCK + "\n"):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(text)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--blocks", src, "-o", self.path("report.csv")] + list(argv))
        self.log = err.getvalue()
        return code

    def test_stream_goes_to_vex_and_plain_name_to_koji(self):
        code = self.run_raw("--config", self.write_config())
        self.assertEqual(code, EXIT_OK)
        line = self.report_lines()[1]
        self.assertIn(";nginx;nginx-1.26.3-1.sl9;", line)
        self.assertIn(";Affected;", line)
        self.assertEqual(self.session.calls, [("sl9", "nginx")])
        self.assertIn("nginx → nginx:1.26 (1)", self.log)
        self.assertIn("хаб https://koji.example.com/kojihub, тег sl9, RHEL 9", self.log)

    def test_without_mapping_plain_package_is_used(self):
        text = CONFIG.split("vex_streams:")[0]
        self.assertEqual(self.run_raw("--config", self.write_config(text)), EXIT_OK)
        self.assertIn(";Fixed;", self.report_lines()[1])
        self.assertNotIn("стримы VEX", self.log)

    def test_mapping_for_another_version_is_not_used(self):
        code = self.run_raw("--config", self.write_config(), "--rhel", "9.2")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("стримы VEX", self.log)
        self.assertIn(";not listed", self.report_lines()[1])

    def test_flag_wins_over_config(self):
        path = self.write_config(CONFIG.replace("tag: sl9", "tag: sl9-old"))
        # если бы победил конфиг, тег sl9-old не нашёлся бы — код 2
        self.assertEqual(self.run_raw("--config", path, "--tag", "sl9"), EXIT_OK)
        self.assertEqual(self.session.calls, [("sl9", "nginx")])

    def test_config_from_environment(self):
        path = self.write_config()
        with mock.patch.dict(os.environ, {"VULNSHEET_CONFIG": path}):
            self.assertEqual(self.run_raw(), EXIT_OK)
        self.assertIn("конфиг: " + path, self.log)

    def test_vex_settings_from_config_are_used(self):
        path = self.write_config(CONFIG + "vex:\n  timeout: 7\n  cache_dir: %s\n"
                                 % self.path("mycache"))
        self.assertEqual(self.run_raw("--config", path), EXIT_OK)
        self.assertEqual(self.download.call_args.args,
                         (vex_url("CVE-2026-73070"), 7))
        self.assertTrue(os.path.exists(self.path("mycache/cve-2026-73070.json")))

    def test_broken_config_is_fatal(self):
        code = self.run_raw("--config", self.write_config("vex:\n  jobs: 0\n"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("vex.jobs", self.log)
        self.assertNotIn("Traceback", self.log)
        self.connect.assert_not_called()

    def test_missing_config_file_is_fatal(self):
        code = self.run_raw("--config", self.path("нет.yaml"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("не читается", self.log)
        self.assertNotIn("Traceback", self.log)


# строка прежней таблицы: ручные колонки заполнены, koji и VEX устарели
OLD_ROW = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
           "В работу;01.09.2026;КМ;vim;vim-8.2.2637-20.sl9;-;-;Affected;Low;3.1;-;"
           "https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# OLD_ROW после режима 2: обновлены только koji и VEX
REFRESHED = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
             "В работу;01.09.2026;КМ;vim;vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;"
             "Moderate;5.5;-;https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# OLD_ROW после режима 3 с BLOCK: данные задачи — из блока
SYNCED = ("Иванов;В работе;01.09.2026;-;обновить;TASKID-181229;CVE-2026-73070;"
          "Отменен;22.09.2026;КМ;vim;vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;"
          "Moderate;5.5;-;https://access.redhat.com/security/cve/CVE-2026-73070;ждём апстрим")
# задача, которой больше нет в блоках
GONE_ROW = ("Петров;Готово;-;-;-;TASKID-100000;CVE-2026-73071;Выполнена;01.08.2026;КМ;"
            "openssl;openssl-3-1.sl9;-;-;Fixed;Low;2.0;-;"
            "https://access.redhat.com/security/cve/CVE-2026-73071;-")
GONE_MISSING = ("Петров;Готово;-;-;-;TASKID-100000;CVE-2026-73071;Missing;01.08.2026;КМ;"
                "openssl;NOT_FOUND;-;-;no VEX record;-;-;-;"
                "https://access.redhat.com/security/cve/CVE-2026-73071;-")
NEW_BLOCK = BLOCK.replace("181229", "181230").replace("73070", "73071").replace("vim", "openssl")
NEW_ROW = ("-;-;-;-;-;TASKID-181230;CVE-2026-73071;Отменен;22.09.2026;КМ;openssl;NOT_FOUND;"
           "-;-;no VEX record;-;-;-;https://access.redhat.com/security/cve/CVE-2026-73071;-")


class UsageTest(CliCase):
    def assertUsageError(self, argv, needle):
        with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(needle, err.getvalue())

    def test_neither_blocks_nor_table(self):
        self.assertUsageError(COMMON, "нужен --blocks или --table")

    def test_table_from_stdin_is_refused(self):
        self.assertUsageError(COMMON + ["--table", "-"], "только файл")

    def test_blocks_from_stdin(self):
        with mock.patch("sys.stdin", io.StringIO(BLOCK)):
            code = self.run_main("--blocks", "-", "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, EXPECTED])
        self.assertIn("режим: новая таблица", self.log)


class UpdateModesTest(CliCase):
    def write_table(self, *rows, name="old.csv"):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join((HEADER,) + rows) + "\n")
        return path

    def write_blocks(self, text):
        path = self.path("tasks.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_refresh_updates_only_koji_and_vex(self):
        code = self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, REFRESHED])
        self.assertIn("режим: обновление koji и VEX", self.log)
        self.assertIn("old.csv: строк 1", self.log)

    def test_refresh_in_place(self):
        table = self.write_table(OLD_ROW, name="report.csv")
        self.assertEqual(self.run_main("--table", table, "-o", table), EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, REFRESHED])

    def test_refresh_keeps_previous_vex_on_fetch_error(self):
        self.docs[vex_url("CVE-2026-73070")] = OSError("сеть")
        code = self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines()[1],
                         OLD_ROW.replace("vim-8.2.2637-20.sl9", "vim-8.2.2637-26.sl9_8.6^4"))
        self.assertIn("оставлены прежние данные VEX", self.log)

    def test_refresh_row_without_cve_is_partial(self):
        row = OLD_ROW.replace("CVE-2026-73070;", "-;", 1)
        code = self.run_main("--table", self.write_table(row), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.report_lines(), [HEADER, row])
        self.assertIn("строка оставлена как есть", self.log)
        self.connect.assert_not_called()

    def test_refresh_does_not_touch_rejects_file(self):
        with open(self.path("report.rejected.txt"), "w") as handle:
            handle.write("старьё")
        self.run_main("--table", self.write_table(OLD_ROW), "-o", self.path("report.csv"))
        self.assertTrue(os.path.exists(self.path("report.rejected.txt")))

    def test_header_only_table_skips_network(self):
        code = self.run_main("--table", self.write_table(), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER])
        self.connect.assert_not_called()

    def test_sync_matches_marks_missing_and_appends(self):
        blocks = self.write_blocks(BLOCK + "\n\n" + NEW_BLOCK + "\n")
        code = self.run_main("--table", self.write_table(OLD_ROW, GONE_ROW),
                             "--blocks", blocks, "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.report_lines(), [HEADER, SYNCED, GONE_MISSING, NEW_ROW])
        self.assertIn("режим: синхронизация с блоками", self.log)
        self.assertIn("совпало 1, Missing 1, новых 1", self.log)

    def test_sync_with_empty_blocks_is_fatal(self):
        code = self.run_main("--table", self.write_table(OLD_ROW),
                             "--blocks", self.write_blocks("\n"), "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("ни одного блока", self.log)
        self.connect.assert_not_called()

    def test_sync_with_no_valid_blocks_is_fatal_and_keeps_table(self):
        table = self.write_table(OLD_ROW, name="report.csv")
        code = self.run_main("--table", table, "--blocks", self.write_blocks(BAD + "\n"),
                             "-o", table)
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("в блоках нет ни одного годного блока", self.log)
        self.assertNotIn("Traceback", self.log)
        self.connect.assert_not_called()
        with open(table, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), HEADER + "\n" + OLD_ROW + "\n")
        self.assertFalse(os.path.exists(self.path("report.rejected.txt")))

    def test_failed_in_place_run_keeps_table(self):
        table = self.write_table(OLD_ROW, name="report.csv")
        with open(table, encoding="utf-8") as handle:
            before = handle.read()
        self.session.tags = {"sl9-other"}
        code = self.run_main("--table", table, "-o", table)
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("нет тега sl9", self.log)
        self.assertNotIn("Traceback", self.log)
        with open(table, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before)
        leftovers = [name for name in os.listdir(self.room) if name.startswith(".vulnsheet-")]
        self.assertEqual(leftovers, [])

    def test_broken_table_is_fatal_and_keeps_output(self):
        with open(self.path("report.csv"), "w", encoding="utf-8") as handle:
            handle.write("прошлый отчёт\n")
        table = self.path("old.csv")
        with open(table, "w", encoding="utf-8") as handle:
            handle.write("не та таблица\n")
        code = self.run_main("--table", table, "-o", self.path("report.csv"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("old.csv", self.log)
        self.assertIn("заголовок", self.log)
        self.assertNotIn("Traceback", self.log)
        self.connect.assert_not_called()
        with open(self.path("report.csv"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "прошлый отчёт\n")


class OutputPermissionsTest(CliCase):
    def blocks_file(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        return src

    def test_existing_output_keeps_its_permissions(self):
        out = self.path("report.csv")
        with open(out, "w", encoding="utf-8") as handle:
            handle.write("прошлый отчёт\n")
        os.chmod(out, 0o640)
        self.assertEqual(self.run_main("--blocks", self.blocks_file(), "-o", out), EXIT_OK)
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o640)

    def test_symlink_output_keeps_the_link_and_updates_the_target(self):
        target = self.path("real.csv")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("прошлый отчёт\n")
        os.chmod(target, 0o640)
        link = self.path("report.csv")
        os.symlink(target, link)
        self.assertEqual(self.run_main("--blocks", self.blocks_file(), "-o", link), EXIT_OK)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), target)
        with open(target, encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), [HEADER, EXPECTED])
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o640)

    def test_new_output_gets_the_default_permissions(self):
        out = self.path("report.csv")
        old_umask = os.umask(0o022)
        os.umask(old_umask)
        self.assertEqual(self.run_main("--blocks", self.blocks_file(), "-o", out), EXIT_OK)
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o666 & ~old_umask)


class BrokenPipeTest(CliCase):
    def test_broken_pipe_on_stdout_exits_quietly(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        err = io.StringIO()
        with mock.patch("vulnsheet.report.write", side_effect=BrokenPipeError()):
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = main(["--rhel", "9", "--koji-url", "https://k/kojihub",
                             "--tag", "sl9", "--blocks", src])
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
