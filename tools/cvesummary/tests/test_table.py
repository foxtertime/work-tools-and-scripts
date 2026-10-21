import datetime
import unittest

from cvesummary import table
from cvesummary.xlsx import Cell, Row, Sheet

HEADER = ["Разработчик", "Статус", "Start date", "End date", "Принятая мера", "Task ID",
          "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент", "P", "D",
          "SL NVR (latest build)", "RHEL NVR (if fixed)", "Fix date", "RHEL state",
          "RHEL severity", "RHEL CVSS", "Advisory (RHSA)", "CVE link",
          "ai_nvr", "ai_verdict", "ai_confidence", "ai_remediation", "ai_run", "Комментарий"]
ROW = ["Иванов И.И.", "Готов", "01.10.2026", "03.10.2026", "Патч из апстрима", "TASKID-1",
       "CVE-2026-1", "Выполнена", "28.09.2026", "КМ", "openssl", "+", "-",
       "openssl-3.2.2-6.sl9", "-", "-", "Affected", "Important", "7.5", "-",
       "https://access.redhat.com/security/cve/CVE-2026-1",
       "openssl-3.2.2-7.el9", "affected", "high", "backport prepared", "21.10.2026", "-"]
EXPECTED = {"row": 2, "dev": "Иванов И.И.", "status": "Готов", "start": "2026-10-01",
            "end": "2026-10-03", "measure": "Патч из апстрима", "task": "TASKID-1",
            "cve": "CVE-2026-1", "tdate": "2026-09-28", "exec": "КМ", "comp": "openssl",
            "p": "+", "d": "", "slnvr": "openssl-3.2.2-6.sl9", "rhnvr": "", "fixdate": "",
            "rstate": "Affected", "sev": "Important", "cvss": "7.5", "rhsa": "",
            "link": "https://access.redhat.com/security/cve/CVE-2026-1", "comment": "",
            "ai_verdict": "affected", "ai_run": "2026-10-21", "bad": []}
REQUIRED = ["CVE ID", "Компонент", "RHEL state", "RHEL severity"]


def sheet(*rows, date1904=False):
    """Лист из строк: ячейка — str или готовая Cell; номера строк с 1."""
    return Sheet("Лист1", [Row(n, [c if isinstance(c, Cell) else Cell(c) for c in row])
                           for n, row in enumerate(rows, 1)], date1904)


def one(*rows, **options):
    return table.build(sheet(*rows, **options)).rows[0]


class HeaderTest(unittest.TestCase):
    def test_full_row(self):
        self.assertEqual(one(HEADER, ROW), EXPECTED)

    def test_task_state_is_not_read(self):
        self.assertNotIn("Выполнена", one(HEADER, ROW).values())

    def test_group_row_above_header(self):
        result = table.build(sheet(["AG21", "", "SberLinux", "RedHat"], HEADER, ROW))
        self.assertEqual(result.header_row, 2)
        self.assertEqual(result.rows[0]["row"], 3)

    def test_columns_by_name_any_order_extra_ignored(self):
        got = one(["Заметки"] + HEADER[::-1], ["x"] + ROW[::-1])
        self.assertEqual(got, EXPECTED)

    def test_header_names_ignore_case_and_whitespace(self):
        header = [" cve id ", "КОМПОНЕНТ", "RHEL  state", "rhel\nseverity", "SL NVR\n(latest build)"]
        got = one(header, ["CVE-1", "bash", "Affected", "Low", "bash-5.1-1.sl9"])
        self.assertEqual((got["cve"], got["rstate"], got["sev"], got["slnvr"]),
                         ("CVE-1", "Affected", "Low", "bash-5.1-1.sl9"))

    def test_missing_required(self):
        with self.assertRaises(table.TableError) as caught:
            table.build(sheet(["CVE ID", "RHEL severity"], ["CVE-1", "Low"]))
        self.assertIn("Компонент, RHEL state", str(caught.exception))

    def test_no_header(self):
        with self.assertRaises(table.TableError) as caught:
            table.build(sheet(["a", "b"], ["c", "d"]))
        self.assertIn("CVE ID", str(caught.exception))

    def test_optional_missing_are_reported_and_empty(self):
        result = table.build(sheet(REQUIRED, ["CVE-1", "bash", "Affected", "Low"]))
        self.assertEqual(len(result.missing), len(table.FIELDS) - 4)
        self.assertIn("Разработчик", result.missing)
        self.assertEqual(result.rows[0]["dev"], "")

    def test_duplicate_column_first_wins(self):
        result = table.build(sheet(REQUIRED + ["Компонент"], ["CVE-1", "bash", "Affected", "Low", "zsh"]))
        self.assertEqual(result.rows[0]["comp"], "bash")
        self.assertEqual(result.duplicates, ["Компонент"])


class ValuesTest(unittest.TestCase):
    def test_dash_and_emdash_are_empty(self):
        got = one(REQUIRED + ["Разработчик", "Статус", "Комментарий"],
                  ["CVE-1", "bash", "Affected", "Low", "-", "—", "   "])
        self.assertEqual((got["dev"], got["status"], got["comment"]), ("", "", ""))

    def test_values_are_stripped(self):
        self.assertEqual(one(REQUIRED, [" CVE-1 ", "bash", "Affected", "Low"])["cve"], "CVE-1")

    def test_rows_without_cve_are_skipped_and_counted(self):
        result = table.build(sheet(REQUIRED, ["", "bash", "Affected", "Low"], ["", "", "", ""],
                                   ["CVE-2", "zsh", "Fixed", "Low"]))
        self.assertEqual(([r["cve"] for r in result.rows], result.skipped), (["CVE-2"], 1))

    def test_short_row_is_padded(self):
        self.assertEqual(one(REQUIRED + ["Комментарий"], ["CVE-1", "bash"])["sev"], "")


class DatesTest(unittest.TestCase):
    HEAD = REQUIRED + ["Start date"]

    def start(self, cell, **options):
        return one(self.HEAD, ["CVE-1", "bash", "Affected", "Low", cell], **options)

    def test_formats(self):
        cases = {"01.10.2026": "2026-10-01", "1.2.2026": "2026-02-01",
                 "2026-10-01": "2026-10-01", "2026-10-01T00:00:00": "2026-10-01",
                 "46314": "2026-10-19"}
        for text, iso in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.start(text)["start"], iso)

    def test_date_cells_and_numbers(self):
        day = datetime.date(2026, 10, 19)
        self.assertEqual(self.start(Cell("19.10.2026", 46314.0, day))["start"], "2026-10-19")
        self.assertEqual(self.start(Cell("46314", 46314.0))["start"], "2026-10-19")
        self.assertEqual(self.start(Cell("44852", 44852.0), date1904=True)["start"], "2026-10-19")

    def test_bad_date_stays_text_and_is_counted(self):
        for text in ("31.02.2026", "завтра"):
            with self.subTest(text=text):
                result = table.build(sheet(self.HEAD, ["CVE-1", "bash", "Affected", "Low", text]))
                self.assertEqual(result.rows[0]["start"], text)
                self.assertEqual(result.rows[0]["bad"], ["start"])
                self.assertEqual(result.bad_dates, 1)

    def test_ai_run_is_a_date(self):
        head = REQUIRED + ["ai_verdict", "ai_run"]
        for text in ("21.10.2026", "2026-10-21T12:04"):
            with self.subTest(text=text):
                got = one(head, ["CVE-1", "bash", "Affected", "Low", "affected", text])
                self.assertEqual((got["ai_verdict"], got["ai_run"]), ("affected", "2026-10-21"))

    def test_time_after_text_date_is_dropped(self):
        self.assertEqual(self.start("19.10.2026 14:30")["start"], "2026-10-19")

    def test_implausible_dates_are_bad(self):
        cells = [Cell("01.10.0206"), Cell("5"), Cell("5", 5.0),
                 Cell("30.12.1899", 0.0, datetime.date(1899, 12, 30))]
        for cell in cells:
            with self.subTest(text=cell.text, number=cell.number):
                result = table.build(sheet(self.HEAD, ["CVE-1", "bash", "Affected", "Low", cell]))
                self.assertEqual(result.rows[0]["bad"], ["start"])
                self.assertEqual(result.bad_dates, 1)

    def test_plausible_window_boundaries(self):
        ok = {"01.01.2000": "2000-01-01", "31.12.2099": "2099-12-31"}
        for text, iso in ok.items():
            with self.subTest(text=text):
                self.assertEqual(self.start(text)["start"], iso)
        for text in ("31.12.1999", "01.01.2100"):
            with self.subTest(text=text):
                self.assertIsNone(table.parse_date(Cell(text)))

    def test_parse_date(self):
        self.assertEqual(table.parse_date(Cell("05.10.2026")), datetime.date(2026, 10, 5))
        self.assertIsNone(table.parse_date(Cell("-")))


if __name__ == "__main__":
    unittest.main()
