import os
import tempfile
import unittest

from cvesummary import csvfile, table
from cvesummary.xlsx import Cell


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "t.csv")

    def put(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)

    def texts(self, found):
        return [[c.text for c in row.cells] for row in found.sheet.rows]


class ReadTest(Base):
    def test_vulnsheet_semicolon(self):
        self.put("CVE ID;Компонент\nCVE-1;bash\n".encode("utf-8"))
        found = csvfile.read(self.path)
        self.assertEqual(found.delimiter, ";")
        self.assertEqual(found.encoding, "utf-8")
        self.assertEqual(self.texts(found), [["CVE ID", "Компонент"], ["CVE-1", "bash"]])
        self.assertEqual([r.number for r in found.sheet.rows], [1, 2])
        self.assertEqual(found.sheet.rows[1].cells[0], Cell("CVE-1"))

    def test_comma_and_tab(self):
        for sep in (",", "\t"):
            with self.subTest(sep=repr(sep)):
                self.put(sep.join(["CVE ID", "Компонент"]).encode() + b"\nCVE-1" + sep.encode() + b"bash\n")
                found = csvfile.read(self.path)
                self.assertEqual(found.delimiter, sep)
                self.assertEqual(self.texts(found)[1], ["CVE-1", "bash"])

    def test_delimiter_is_taken_from_header_line(self):
        # строка группировки выше шапки — с другим числом разделителей
        self.put(b"AG21,,\n\"x;y\";CVE ID;Comp\n1;CVE-1;bash\n")
        found = csvfile.read(self.path)
        self.assertEqual(found.delimiter, ";")
        self.assertEqual(self.texts(found)[2], ["1", "CVE-1", "bash"])

    def test_no_delimiter_defaults_to_semicolon(self):
        self.put(b"CVE ID\nCVE-1\n")
        self.assertEqual(csvfile.read(self.path).delimiter, ";")

    def test_bom_and_crlf(self):
        self.put("CVE ID;Компонент\r\nCVE-1;bash\r\n".encode("utf-8-sig"))
        found = csvfile.read(self.path)
        self.assertEqual(found.encoding, "utf-8")
        self.assertEqual(self.texts(found)[0], ["CVE ID", "Компонент"])

    def test_cp1251(self):
        self.put("CVE ID;Компонент;Статус\nCVE-1;bash;Готов\n".encode("cp1251"))
        found = csvfile.read(self.path)
        self.assertEqual(found.encoding, "cp1251")
        self.assertEqual(self.texts(found)[1], ["CVE-1", "bash", "Готов"])

    def test_quoted_field_with_newline_keeps_record_numbers(self):
        self.put('CVE ID;Комментарий\nCVE-1;"две\nстроки; и ;"\nCVE-2;-\n'.encode("utf-8"))
        found = csvfile.read(self.path)
        self.assertEqual(self.texts(found)[1], ["CVE-1", "две\nстроки; и ;"])
        self.assertEqual([r.number for r in found.sheet.rows], [1, 2, 3])

    def test_dates_stay_text_and_parse_in_table(self):
        self.put("CVE ID;Компонент;RHEL state;RHEL severity;Start date\n"
                 "CVE-1;bash;Affected;Low;05.10.2026\n".encode("utf-8"))
        built = table.build(csvfile.read(self.path).sheet)
        self.assertEqual(built.rows[0]["start"], "2026-10-05")
        self.assertEqual(built.bad_dates, 0)


class FailTest(Base):
    def test_missing_file(self):
        with self.assertRaises(csvfile.CsvError) as caught:
            csvfile.read(self.path)
        self.assertNotIn(self.path, str(caught.exception))

    def test_nul_byte(self):
        self.put(b"CVE ID;x\nCVE-1;\x00\n")
        with self.assertRaises(csvfile.CsvError):
            csvfile.read(self.path)

    def test_empty_file_has_no_header(self):
        self.put(b"")
        with self.assertRaises(table.TableError) as caught:
            table.build(csvfile.read(self.path).sheet)
        self.assertNotIn("листа", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
