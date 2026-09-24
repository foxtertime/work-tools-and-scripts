import unittest

from vulnsheet.tasks import Reject, Task, parse

BLOCK = "Состоит из\nTASKID-181229\nCVE-2026-73070 vim\nОтменен\n22.09.2026\nКМ"
VIM = Task("TASKID-181229", "CVE-2026-73070", "vim", "Отменен", "22.09.2026", "КМ")


class ParseTest(unittest.TestCase):
    def test_block_from_the_task(self):
        self.assertEqual(parse(BLOCK + "\n"), ([VIM], []))

    def test_blocks_split_by_blank_lines_keep_order(self):
        second = BLOCK.replace("181229", "181230").replace("vim", "openssl")
        tasks, rejects = parse(BLOCK + "\n\n\n" + second + "\n")
        self.assertEqual([t.task_id for t in tasks], ["TASKID-181229", "TASKID-181230"])
        self.assertEqual([t.component for t in tasks], ["vim", "openssl"])
        self.assertEqual(rejects, [])

    def test_whitespace_only_line_separates_blocks(self):
        tasks, rejects = parse(BLOCK + "\n   \t\n" + BLOCK)
        self.assertEqual(tasks, [VIM, VIM])
        self.assertEqual(rejects, [])

    def test_crlf_and_padding_are_tolerated(self):
        text = ("  Состоит из \r\n TASKID-181229\r\nCVE-2026-73070\t  vim  \r\n"
                "Отменен\r\n22.09.2026\r\nКМ \r\n")
        self.assertEqual(parse(text), ([VIM], []))

    def test_lowercase_cve_is_normalised(self):
        tasks, _ = parse(BLOCK.replace("CVE-2026-73070", "cve-2026-73070"))
        self.assertEqual(tasks[0].cve, "CVE-2026-73070")

    def test_leading_bom_is_ignored(self):
        # Файлы из Windows-редакторов начинаются с BOM.
        self.assertEqual(parse("﻿" + BLOCK), ([VIM], []))

    def test_empty_input(self):
        self.assertEqual(parse(""), ([], []))
        self.assertEqual(parse("\n  \n\n"), ([], []))


class RejectTest(unittest.TestCase):
    def _only_reject(self, text):
        tasks, rejects = parse(text)
        self.assertEqual(tasks, [])
        self.assertEqual(len(rejects), 1)
        return rejects[0]

    def test_five_lines(self):
        reject = self._only_reject(BLOCK.rsplit("\n", 1)[0])
        self.assertIn("5 строк", reject.reason)

    def test_seven_lines(self):
        self.assertIn("7 строк", self._only_reject(BLOCK + "\nлишнее").reason)

    def test_dashes_are_an_ordinary_line(self):
        # Разделитель блоков — только пустая строка.
        self.assertIn("7 строк", self._only_reject("---\n" + BLOCK).reason)

    def test_third_line_without_component(self):
        reject = self._only_reject(BLOCK.replace("CVE-2026-73070 vim", "CVE-2026-73070"))
        self.assertIn("нет компонента", reject.reason)

    def test_third_line_without_cve(self):
        reject = self._only_reject(BLOCK.replace("CVE-2026-73070 vim", "vim CVE-2026-73070"))
        self.assertIn("CVE-ID", reject.reason)

    def test_reject_keeps_number_and_block_verbatim(self):
        bad = "Состоит из\nTASKID-2\n  CVE-2026-73070\nВ работу\n23.09.2026\nКМ"
        tasks, rejects = parse(BLOCK + "\n\n" + bad + "\n\n" + BLOCK)
        self.assertEqual(tasks, [VIM, VIM])
        self.assertEqual([(r.number, r.text) for r in rejects], [(2, bad)])
        self.assertIsInstance(rejects[0], Reject)
