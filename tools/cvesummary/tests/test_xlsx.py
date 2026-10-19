import datetime
import os
import tempfile
import unittest

from cvesummary import xlsx
from tests.xlsxmake import Bool, Error, Formula, Num, Rich, corrupt, replace, write

DAY = datetime.date(2026, 10, 19)
SERIAL = 46314            # DAY в системе 1900
SERIAL_1904 = 46314 - 1462


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def book(self, rows, **options):
        path = os.path.join(self.dir.name, "t.xlsx")
        write(path, rows, **options)
        return path

    def texts(self, path):
        return [[cell.text for cell in row.cells] for row in xlsx.read(path).rows]


class CellsTest(Base):
    def test_shared_and_inline_strings(self):
        for shared in (True, False):
            with self.subTest(shared=shared):
                self.assertEqual(self.texts(self.book([["a", "б"]], shared=shared)), [["a", "б"]])

    def test_rich_text_is_joined(self):
        self.assertEqual(self.texts(self.book([[Rich(["CVE-", "2026"])]])), [["CVE-2026"]])

    def test_formula_bool_error(self):
        row = [Formula("x"), Bool(True), Bool(False), Error("#N/A")]
        self.assertEqual(self.texts(self.book([row])), [["x", "TRUE", "FALSE", "#N/A"]])

    def test_numbers(self):
        cells = xlsx.read(self.book([[5, 7.5, Num(46000.0)]])).rows[0].cells
        self.assertEqual([c.text for c in cells], ["5", "7.5", "46000"])
        self.assertEqual(cells[1].number, 7.5)
        self.assertIsNone(cells[0].date)

    def test_missing_cells_are_empty(self):
        self.assertEqual(self.texts(self.book([["a", None, "c"]])), [["a", "", "c"]])

    def test_row_numbers_follow_the_sheet(self):
        sheet = xlsx.read(self.book([["a"], None, ["c"]]))
        self.assertEqual([row.number for row in sheet.rows], [1, 3])


class DatesTest(Base):
    def cell(self, value, **options):
        return xlsx.read(self.book([[value]], **options)).rows[0].cells[0]

    def test_builtin_date_style(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 14))
        self.assertEqual((cell.date, cell.text), (DAY, "19.10.2026"))

    def test_custom_date_format(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 164), numfmts={164: "dd.mm.yyyy"})
        self.assertEqual(cell.date, DAY)

    def test_time_is_dropped(self):
        self.assertEqual(self.cell(Num(SERIAL + 0.75, 1), xfs=(0, 22)).date, DAY)

    def test_date1904(self):
        self.assertEqual(self.cell(Num(SERIAL_1904, 1), xfs=(0, 14), date1904=True).date, DAY)

    def test_number_format_is_not_a_date(self):
        cell = self.cell(Num(SERIAL, 1), xfs=(0, 164), numfmts={164: '0" дней"'})
        self.assertEqual((cell.date, cell.text), (None, "46314"))

    def test_date_out_of_range_stays_a_number(self):
        cell = self.cell(Num(1e10, 1), xfs=(0, 14))
        self.assertEqual((cell.date, cell.text), (None, "10000000000"))

    def test_is_date_format(self):
        for code in ("dd.mm.yyyy", "yyyy-mm-dd", "d mmm", "DD/MM/YY", "[$-419]d mmmm yyyy"):
            self.assertTrue(xlsx.is_date_format(code), code)
        for code in ("0.00", '0" дней"', "[Red]#,##0", "General", "\\d0", "0_)"):
            self.assertFalse(xlsx.is_date_format(code), code)

    def test_serial_date(self):
        self.assertEqual(xlsx.serial_date(SERIAL), DAY)
        self.assertEqual(xlsx.serial_date(SERIAL_1904, True), DAY)
        with self.assertRaises(ValueError):
            xlsx.serial_date(1e10)


class SheetTest(Base):
    def test_first_sheet_by_workbook_order(self):
        sheet = xlsx.read(self.book([["first"]], second=[["second"]], swap=True))
        self.assertEqual(sheet.name, "Лист1")
        self.assertEqual([[c.text for c in r.cells] for r in sheet.rows], [["first"]])

    def test_absolute_target(self):
        self.assertEqual(self.texts(self.book([["a"]], absolute=True)), [["a"]])


class ErrorsTest(Base):
    def assertFails(self, path, fragment):
        with self.assertRaises(xlsx.XlsxError) as caught:
            xlsx.read(path)
        self.assertIn(fragment, str(caught.exception))

    def test_not_a_zip(self):
        path = os.path.join(self.dir.name, "t.xlsx")
        with open(path, "wb") as handle:
            handle.write(b"not a zip")
        self.assertFails(path, "zip")

    def test_missing_file(self):
        self.assertFails(os.path.join(self.dir.name, "none.xlsx"), "не открывается")

    def test_no_workbook(self):
        path = self.book([["a"]])
        replace(path, "xl/workbook.xml", None)
        self.assertFails(path, "xl/workbook.xml")

    def test_no_sheets(self):
        path = self.book([["a"]])
        replace(path, "xl/workbook.xml", '<workbook xmlns="%s"><sheets/></workbook>'
                % "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
        self.assertFails(path, "нет листов")

    def test_broken_xml(self):
        path = self.book([["a"]])
        replace(path, "xl/worksheets/sheet1.xml", "<worksheet")
        self.assertFails(path, "XML")

    def test_corrupt_deflate_member(self):
        path = self.book([["a", "б"]])
        corrupt(path, "xl/worksheets/sheet1.xml")
        self.assertFails(path, "сжат")

    def test_non_integer_attributes(self):
        sheet = ('<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>')
        main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        cases = {
            "numFmtId": ("xl/styles.xml", '<styleSheet xmlns="%s"><cellXfs count="1">'
                         '<xf numFmtId="abc"/></cellXfs></styleSheet>' % main, "numFmtId"),
            "s": ("xl/worksheets/sheet1.xml", sheet % (main, '<row r="1"><c r="A1" s="x"><v>1</v></c></row>'), "s"),
            "r": ("xl/worksheets/sheet1.xml", sheet % (main, '<row r="x"><c r="A1"><v>1</v></c></row>'), "r"),
        }
        for name, (part, text, fragment) in cases.items():
            with self.subTest(name=name):
                path = self.book([["a"]])
                replace(path, part, text)
                self.assertFails(path, fragment)
