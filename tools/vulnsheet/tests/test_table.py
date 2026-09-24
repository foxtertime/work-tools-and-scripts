import csv
import io
import os
import shutil
import tempfile
import unittest

from vulnsheet.report import COLUMNS
from vulnsheet.table import Record, TableError, read

HEADER = ";".join(COLUMNS)
ROW = ["Иванов", "В работе", "01.09.2026", "-", "-",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       "https://access.redhat.com/security/cve/CVE-2026-0001", "-"]
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
            (HEADER + "\n" + ";".join(ROW[:19]) + "\n", "запись 2: ячеек 19"),
            (HEADER + "\n" + LINE + ";x\n", "запись 2: ячеек 21"),
        ]
        for text, needle in cases:
            with self.subTest(text=text):
                self.assertRejected(needle, text)

    def test_error_names_the_file(self):
        self.assertIn("old.csv", str(self.assertRejected("заголовок", "a;b\n")))

    def test_not_utf8(self):
        self.assertRejected("UTF-8", data=(HEADER + "\n").encode("cp1251"))

    def test_missing_file(self):
        with self.assertRaises(TableError) as caught:
            read(os.path.join(self.room, "нет.csv"))
        self.assertIn("не читается", str(caught.exception))
