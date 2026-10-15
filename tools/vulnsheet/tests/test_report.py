import io
import unittest

from vulnsheet import report
from vulnsheet.patches import BRANCH_ONLY, FOUND, REMOVED, PatchNote
from vulnsheet.report import COLUMNS, format_date, row, write
from vulnsheet.tasks import Task
from vulnsheet.vex import Verdict

TASK = Task("TASKID-181229", "CVE-2026-73070", "vim", "Отменен", "22.09.2026", "КМ")
EXAMPLE = ("-;-;-;-;-;TASKID-181229;CVE-2026-73070;Отменен;22.09.2026;КМ;vim;"
           "vim-8.2.2637-26.sl9_8.6^4;-;-;Under investigation;Moderate;5.5;-;"
           "https://access.redhat.com/security/cve/CVE-2026-73070;-")
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"


class RowTest(unittest.TestCase):
    def cells(self, nvr, verdict):
        return dict(zip(COLUMNS, row(TASK, nvr, verdict)))

    def test_columns(self):
        self.assertEqual(COLUMNS, [
            "Разработчик", "Статус", "Start date", "End date", "Принятая мера",
            "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель",
            "Компонент", "SL NVR (latest build)", "RHEL NVR (if fixed)",
            "Fix date", "RHEL state", "RHEL severity", "RHEL CVSS",
            "Advisory (RHSA)", "CVE link", "Комментарий"])

    def test_example_from_the_task(self):
        verdict = Verdict(state="Under investigation", severity="Moderate", cvss="5.5")
        self.assertEqual(";".join(row(TASK, "vim-8.2.2637-26.sl9_8.6^4", verdict)), EXAMPLE)

    def test_fixed_fills_nvr_date_and_advisory(self):
        cells = self.cells("vim-8.2.2637-26.sl9_8.6^4", Verdict(
            "Fixed", "Important", "7.8", "vim-8.2.2637-22.el9_6", "2026-09-02", RHSA))
        self.assertEqual((cells["RHEL NVR (if fixed)"], cells["Fix date"],
                          cells["Advisory (RHSA)"]),
                         ("vim-8.2.2637-22.el9_6", "02.09.2026", RHSA))

    def test_fix_fields_only_when_fixed(self):
        cells = self.cells("x", Verdict("Affected", "Low", "3.1", "vim-1-1", "2026-09-02", RHSA))
        self.assertEqual((cells["RHEL NVR (if fixed)"], cells["Fix date"],
                          cells["Advisory (RHSA)"]), ("-", "-", "-"))

    def test_zero_cvss_survives(self):
        self.assertEqual(self.cells("x", Verdict("Affected", cvss="0.0"))["RHEL CVSS"], "0.0")

    def test_markers_pass_through(self):
        cells = self.cells("NOT_FOUND", Verdict(state="no VEX record"))
        self.assertEqual((cells["SL NVR (latest build)"], cells["RHEL state"],
                          cells["RHEL severity"], cells["CVE link"]),
                         ("NOT_FOUND", "no VEX record", "-",
                          "https://access.redhat.com/security/cve/CVE-2026-73070"))


L1 = "https://gitlab.example.com/g/vim/-/blob/sl9/PATCH/a.patch"
L2 = "https://gitlab.example.com/g/vim/-/blob/sl9/PATCH/b.patch"
FOUND_TEXT = "патч найден: " + L1


class PatchNoteTextTest(unittest.TestCase):
    def test_found(self):
        self.assertEqual(report.patch_note(PatchNote(FOUND, "sl9", (L1, L2))),
                         "патч найден: %s %s" % (L1, L2))

    def test_removed_from_the_branch(self):
        self.assertEqual(report.patch_note(PatchNote(REMOVED, "sl9", (L1,))),
                         "патч убран из ветки sl9, возможно, не нужен после обновления "
                         "пакета: " + L1)

    def test_only_in_the_branch(self):
        self.assertEqual(report.patch_note(PatchNote(BRANCH_ONLY, "sl9", (L1,))),
                         "патч есть в ветке sl9, но не в билде: " + L1)


class PatchNoteTest(unittest.TestCase):
    VERDICT = Verdict(state="Affected", severity="Low", cvss="3.1")

    def test_row_with_patch_carries_the_note(self):
        cells = row(TASK, "vim-1-1.sl9", self.VERDICT, note=FOUND_TEXT)
        self.assertEqual(cells[report.COMMENT_INDEX], FOUND_TEXT)

    def test_row_without_patch_has_an_empty_comment(self):
        cells = row(TASK, "vim-1-1.sl9", self.VERDICT)
        self.assertEqual(cells[report.COMMENT_INDEX], "-")

    def test_note_replaces_an_empty_cell(self):
        self.assertEqual(report.with_patch_note("-", FOUND_TEXT), FOUND_TEXT)
        self.assertEqual(report.with_patch_note(" ", FOUND_TEXT), FOUND_TEXT)

    def test_note_is_appended_to_human_text(self):
        self.assertEqual(report.with_patch_note("ждём апстрим", FOUND_TEXT),
                         "ждём апстрим; " + FOUND_TEXT)

    def test_own_note_is_replaced_and_human_text_kept(self):
        for own in ("патч присутствует", "патч найден: " + L2,
                    "патч убран из ветки sl9, возможно, не нужен после обновления пакета: " + L2,
                    "патч есть в ветке sl9, но не в билде: " + L2):
            with self.subTest(own=own):
                self.assertEqual(report.with_patch_note("ждём; %s; проверить" % own, FOUND_TEXT),
                                 "ждём; %s; проверить" % FOUND_TEXT)
                self.assertEqual(report.with_patch_note(own, FOUND_TEXT), FOUND_TEXT)

    def test_same_note_leaves_the_cell_as_is(self):
        cell = "ждём апстрим; " + FOUND_TEXT
        self.assertEqual(report.with_patch_note(cell, FOUND_TEXT), cell)

    def test_two_own_notes_collapse_into_one(self):
        cell = "патч присутствует; ждём; патч найден: " + L2
        self.assertEqual(report.with_patch_note(cell, FOUND_TEXT), FOUND_TEXT + "; ждём")

    def test_without_patch_the_cell_is_left_alone(self):
        # пометка прошлого прогона не снимается: патча могли и не увидеть
        for cell in ("-", "ждём апстрим", "патч присутствует", FOUND_TEXT):
            self.assertEqual(report.with_patch_note(cell, None), cell)

    def test_own_note_is_recognised(self):
        self.assertTrue(report.has_patch_note("ждём; патч присутствует"))
        self.assertTrue(report.has_patch_note(FOUND_TEXT))
        self.assertFalse(report.has_patch_note("патч пишем сами"))


class FormatDateTest(unittest.TestCase):
    def test_values(self):
        for value, want in [("2026-09-02", "02.09.2026"),
                            ("2026-09-02T10:00:00+00:00", "02.09.2026"),
                            ("когда-нибудь", "когда-нибудь"), ("", "")]:
            with self.subTest(value=value):
                self.assertEqual(format_date(value), want)


class WriteTest(unittest.TestCase):
    def test_header_then_rows_with_unix_newlines(self):
        out = io.StringIO()
        write([row(TASK, "vim-8.2.2637-26.sl9_8.6^4",
                   Verdict(state="Under investigation", severity="Moderate", cvss="5.5"))], out)
        self.assertEqual(out.getvalue(), ";".join(COLUMNS) + "\n" + EXAMPLE + "\n")


class GroupsTest(unittest.TestCase):
    GROUPS = [report.DEVELOPER, report.TASK, report.KOJI, report.VEX,
              report.LINK, report.COMMENT]

    def test_groups_cover_all_columns_in_order(self):
        self.assertEqual(sum((COLUMNS[group] for group in self.GROUPS), []), COLUMNS)

    def test_group_contents(self):
        self.assertEqual(COLUMNS[report.DEVELOPER], [
            "Разработчик", "Статус", "Start date", "End date", "Принятая мера"])
        self.assertEqual(COLUMNS[report.TASK], [
            "Task ID", "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент"])
        self.assertEqual(COLUMNS[report.KOJI], ["SL NVR (latest build)"])
        self.assertEqual(COLUMNS[report.VEX], [
            "RHEL NVR (if fixed)", "Fix date", "RHEL state", "RHEL severity",
            "RHEL CVSS", "Advisory (RHSA)"])
        self.assertEqual(COLUMNS[report.LINK], ["CVE link"])
        self.assertEqual(COLUMNS[report.COMMENT], ["Комментарий"])

    def test_row_fields_land_on_named_indices(self):
        cells = row(TASK, "vim-1", Verdict(state="Affected"))
        indices = [report.TASK_ID, report.CVE_ID, report.TASK_STATE, report.TASK_DATE,
                   report.ASSIGNEE, report.COMPONENT, report.SL_NVR, report.RHEL_STATE]
        self.assertEqual([cells[i] for i in indices], [
            "TASKID-181229", "CVE-2026-73070", "Отменен", "22.09.2026", "КМ", "vim",
            "vim-1", "Affected"])

    def test_missing_marker(self):
        self.assertEqual(report.MISSING, "Missing")
