import csv
import io
import os
import shutil
import tempfile
import unittest

from vulnsheet.report import COLUMNS
from vulnsheet.table import Record, TableError, read

HEADER = ";".join(COLUMNS)
HEADER_2 = ";".join(c for c in COLUMNS if not c.startswith("ai_"))  # vulnsheet 2.x
ROW = ["Иванов", "В работе", "01.09.2026", "-", "-",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim", "+", "-",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       "https://access.redhat.com/security/cve/CVE-2026-0001",
       "vim-1-1.el9", "affected", "high", "-", "21.10.2026", "ждём апстрим"]
ROW_2 = ROW[:21] + ROW[26:]  # та же строка в таблице vulnsheet 2.x
LINE = ";".join(ROW)


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)

    def write(self, text="", data=None):
        path = os.path.join(self.room, "old.csv")
        with open(path, "wb") as handle:
            handle.write(data if data is not None else text.encode("utf-8"))
        return path

    def assertRejected(self, needle, text="", data=None):
        with self.assertRaises(TableError) as caught:
            read(self.write(text, data))
        self.assertIn(needle, str(caught.exception))
        return caught.exception

    def test_rows_come_back_verbatim_with_record_numbers(self):
        self.assertEqual(read(self.write(HEADER + "\n" + LINE + "\n")), [Record(2, ROW)])

    def test_bom_and_crlf(self):
        data = ("﻿" + HEADER + "\r\n" + LINE + "\r\n").encode("utf-8")
        self.assertEqual(read(self.write(data=data)), [Record(2, ROW)])

    def test_quoted_cell_with_separator_and_newline_is_kept(self):
        cells = list(ROW)
        cells[-1] = "ждём; апстрим\nи RHSA"
        buffer = io.StringIO()
        csv.writer(buffer, delimiter=";", lineterminator="\n").writerow(cells)
        rows = read(self.write(HEADER + "\n" + buffer.getvalue()))
        self.assertEqual(rows, [Record(2, cells)])

    def test_blank_records_are_skipped_but_counted(self):
        self.assertEqual(read(self.write(HEADER + "\n\n" + LINE + "\n")), [Record(3, ROW)])

    def test_header_only_is_an_empty_table(self):
        self.assertEqual(read(self.write(HEADER + "\n")), [])

    def test_bad_tables(self):
        cases = [
            ("", "нет заголовка"),
            ("\n \n", "нет заголовка"),
            (HEADER.replace("Task ID", "Task") + "\n", "заголовок"),
            (HEADER + "\n" + ";".join(ROW[:26]) + "\n", "запись 2: ячеек 26, ожидается 27"),
            (HEADER + "\n" + LINE + ";x\n", "запись 2: ячеек 28"),
            (HEADER_2 + "\n" + LINE + "\n", "запись 2: ячеек 27, ожидается 22"),
        ]
        for text, needle in cases:
            with self.subTest(text=text):
                self.assertRejected(needle, text)

    def test_table_of_vulnsheet_2_gets_empty_ai_columns(self):
        rows = read(self.write(HEADER_2 + "\n" + ";".join(ROW_2) + "\n"))
        self.assertEqual(rows, [Record(2, ROW_2[:21] + ["-"] * 5 + ROW_2[21:])])

    def test_table_of_vulnsheet_1_is_rejected_with_a_hint(self):
        old = [c for c in HEADER_2.split(";") if c not in ("P", "D")]
        line = ";".join(ROW_2[:11] + ROW_2[13:])
        error = self.assertRejected("vulnsheet 1.x", ";".join(old) + "\n" + line + "\n")
        self.assertIn("P и D", str(error))

    def test_error_names_the_file(self):
        self.assertIn("old.csv", str(self.assertRejected("заголовок", "a;b\n")))

    def test_not_utf8(self):
        self.assertRejected("UTF-8", data=(HEADER + "\n").encode("cp1251"))

    def test_unclosed_quote_swallows_following_rows(self):
        second = ";".join(ROW).replace("TASKID-1", "TASKID-2")
        broken = LINE.rsplit(";", 1)[0] + ';"неполная кавычка'
        self.assertRejected("ошибка CSV", HEADER + "\n" + broken + "\n" + second + "\n")

    def test_missing_file(self):
        with self.assertRaises(TableError) as caught:
            read(os.path.join(self.room, "нет.csv"))
        self.assertIn("не читается", str(caught.exception))
