import unittest

from vulnsheet import report
from vulnsheet.kojiclient import ERROR, NOT_FOUND
from vulnsheet.merge import Fresh, Note, build, pairs, refresh, sync
from vulnsheet.table import Record
from vulnsheet.tasks import Task
from vulnsheet.vex import FETCH_ERROR, Verdict

LINK = "https://access.redhat.com/security/cve/"
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"

# Строки, которые люди уже вели: ручные колонки заполнены, koji и VEX старые.
OLD = ["Иванов", "В работе", "01.09.2026", "-", "обновить",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       LINK + "CVE-2026-0001", "ждём апстрим"]
BASH = ["Петров", "Готово", "02.09.2026", "03.09.2026", "обновлено",
        "TASKID-2", "CVE-2026-0002", "Выполнена", "02.09.2026", "КМ", "bash",
        "bash-4-1.sl9", "-", "-", "Affected", "Moderate", "5.5", "-",
        LINK + "CVE-2026-0002", "-"]

FRESH = Fresh(
    nvrs={"vim": "vim-2-1.sl9", "bash": "bash-5-1.sl9", "openssl": NOT_FOUND},
    verdicts={
        ("CVE-2026-0001", "vim"): Verdict("Fixed", "Important", "7.8", "vim-2-1.el9",
                                          "2026-09-02", RHSA),
        ("CVE-2026-0002", "bash"): Verdict("Affected", "Moderate", "5.5"),
        ("CVE-2026-0003", "openssl"): Verdict("not listed"),
    })
# колонки SL NVR … Advisory строки OLD по FRESH
UPDATED = ["vim-2-1.sl9", "vim-2-1.el9", "02.09.2026", "Fixed", "Important", "7.8", RHSA]
DATA = slice(report.KOJI.start, report.VEX.stop)  # SL NVR … Advisory


def changed(cells, changes):
    """Копия строки с заменой ячеек: {индекс колонки: значение}."""
    cells = list(cells)
    for index, value in changes.items():
        cells[index] = value
    return cells


def task(task_id="TASKID-1", cve="CVE-2026-0001", component="vim",
         state="Отменен", date="22.09.2026", assignee="ПП"):
    return Task(task_id, cve, component, state, date, assignee)


OPENSSL = task("TASKID-3", "CVE-2026-0003", "openssl", "В работу", "23.09.2026", "КМ")
# OLD, совпавшая с task(): данные задачи из блока, ручные колонки прежние
MATCHED = (OLD[:5] + ["TASKID-1", "CVE-2026-0001", "Отменен", "22.09.2026", "ПП", "vim"]
           + UPDATED + OLD[18:])
# BASH, чьей задачи нет в блоках
BASH_MISSING = (BASH[:7] + [report.MISSING] + BASH[8:11]
                + ["bash-5-1.sl9", "-", "-", "Affected", "Moderate", "5.5", "-"] + BASH[18:])
# новая строка из OPENSSL
NEW = (["-"] * 5 + ["TASKID-3", "CVE-2026-0003", "В работу", "23.09.2026", "КМ", "openssl",
                    NOT_FOUND, "-", "-", "not listed", "-", "-", "-",
                    LINK + "CVE-2026-0003", "-"])


class PairsTest(unittest.TestCase):
    def test_mode1_keeps_every_block(self):
        tasks = [task(), task(), OPENSSL]
        self.assertEqual(pairs(None, tasks), [("CVE-2026-0001", "vim")] * 2
                         + [("CVE-2026-0003", "openssl")])

    def test_mode2_takes_rows_with_something_to_ask(self):
        records = [Record(2, changed(OLD, {report.CVE_ID: " cve-2026-0001 "})),
                   Record(3, changed(OLD, {report.CVE_ID: "-"})),
                   Record(4, changed(OLD, {report.COMPONENT: "-"})),
                   Record(5, BASH)]
        self.assertEqual(pairs(records, None),
                         [("CVE-2026-0001", "vim"), ("CVE-2026-0002", "bash")])

    def test_mode3_rows_then_new_triples_once(self):
        records = [Record(2, OLD), Record(3, BASH)]
        self.assertEqual(pairs(records, [task(), OPENSSL, OPENSSL]), [
            ("CVE-2026-0001", "vim"), ("CVE-2026-0002", "bash"),
            ("CVE-2026-0003", "openssl")])


class BuildTest(unittest.TestCase):
    def test_row_per_block_with_repeats(self):
        expected = report.row(task(), "vim-2-1.sl9", FRESH.verdicts[("CVE-2026-0001", "vim")])
        self.assertEqual(build([task(), task()], FRESH).rows, [expected, expected])


class RefreshTest(unittest.TestCase):
    def test_manual_and_task_columns_stay_koji_and_vex_update(self):
        before = list(OLD)
        out = refresh([Record(2, OLD)], FRESH)
        self.assertEqual(out.rows, [OLD[:11] + UPDATED + OLD[18:]])
        self.assertEqual((out.kept_koji, out.kept_vex, out.skipped), ((), (), ()))
        self.assertEqual(OLD, before)  # вход не изменён

    def test_koji_error_keeps_previous_nvr(self):
        out = refresh([Record(2, OLD)], FRESH._replace(nvrs={"vim": ERROR}))
        self.assertEqual(out.rows[0][DATA], [OLD[report.SL_NVR]] + UPDATED[1:])
        self.assertEqual(out.kept_koji, (Note(2, "CVE-2026-0001", "vim"),))
        self.assertEqual(out.kept_vex, ())

    def test_fetch_error_keeps_previous_vex_group(self):
        fresh = FRESH._replace(
            verdicts={("CVE-2026-0001", "vim"): Verdict(state=FETCH_ERROR)})
        out = refresh([Record(2, OLD)], fresh)
        self.assertEqual(out.rows[0], OLD[:11] + ["vim-2-1.sl9"] + OLD[12:])
        self.assertEqual(out.kept_vex, (Note(2, "CVE-2026-0001", "vim"),))

    def test_answers_overwrite_previous_values(self):
        fresh = Fresh(nvrs={"vim": NOT_FOUND},
                      verdicts={("CVE-2026-0001", "vim"): Verdict("not listed")})
        row = refresh([Record(2, OLD)], fresh).rows[0]
        self.assertEqual(row[DATA], [NOT_FOUND, "-", "-", "not listed", "-", "-", "-"])

    def test_row_without_cve_or_component_is_left_as_is(self):
        rows = [changed(OLD, {report.CVE_ID: "-"}), changed(OLD, {report.COMPONENT: " "})]
        out = refresh([Record(2, rows[0]), Record(3, rows[1])], Fresh({}, {}))
        self.assertEqual(out.rows, rows)
        self.assertEqual(out.skipped, (Note(2, "-", "vim"), Note(3, "CVE-2026-0001", " ")))

    def test_cve_cell_is_matched_loosely_but_kept_verbatim(self):
        cells = changed(OLD, {report.CVE_ID: " cve-2026-0001"})
        row = refresh([Record(2, cells)], FRESH).rows[0]
        self.assertEqual(row[report.CVE_ID], " cve-2026-0001")
        self.assertEqual(row[DATA], UPDATED)
        self.assertEqual(row[report.LINK], [LINK + "CVE-2026-0001"])


class SyncTest(unittest.TestCase):
    def test_match_missing_and_new(self):
        out = sync([Record(2, OLD), Record(3, BASH)], [OPENSSL, task()], FRESH)
        self.assertEqual(out.rows, [MATCHED, BASH_MISSING, NEW])
        self.assertEqual((out.matched, out.missing, out.added, out.repeated), (1, 1, 1, 0))

    def test_existing_order_kept_new_in_block_order(self):
        tasks = [task("TASKID-9", "CVE-2026-0003", "openssl"),
                 task("TASKID-2", "CVE-2026-0002", "bash"),
                 task("TASKID-8", "CVE-2026-0003", "openssl"), task()]
        out = sync([Record(2, BASH), Record(3, OLD)], tasks, FRESH)
        self.assertEqual([r[report.TASK_ID] for r in out.rows],
                         ["TASKID-2", "TASKID-1", "TASKID-9", "TASKID-8"])

    def test_missing_row_back_in_blocks_takes_block_state(self):
        cells = changed(OLD, {report.TASK_STATE: report.MISSING})
        self.assertEqual(sync([Record(2, cells)], [task()], FRESH).rows, [MATCHED])

    def test_key_is_trimmed_and_cve_case_insensitive(self):
        cells = changed(OLD, {report.TASK_ID: " TASKID-1 ", report.CVE_ID: "cve-2026-0001",
                              report.COMPONENT: "vim "})
        out = sync([Record(2, cells)], [task()], FRESH)
        self.assertEqual((out.matched, out.missing, out.added), (1, 0, 0))

    def test_same_cve_and_component_other_task_is_not_a_match(self):
        out = sync([Record(2, OLD)], [task(task_id="TASKID-7")], FRESH)
        self.assertEqual((out.matched, out.missing, out.added), (0, 1, 1))

    def test_repeated_block_triple_first_wins(self):
        out = sync([Record(2, OLD)], [task(), task(state="Выполнена")], FRESH)
        self.assertEqual(out.rows, [MATCHED])
        self.assertEqual(out.repeated, 1)

    def test_repeated_new_triple_is_added_once(self):
        out = sync([], [OPENSSL, OPENSSL], FRESH)
        self.assertEqual(out.rows, [NEW])
        self.assertEqual((out.added, out.repeated), (1, 1))

    def test_duplicate_table_rows_each_take_the_block(self):
        out = sync([Record(2, OLD), Record(3, OLD)], [task()], FRESH)
        self.assertEqual(out.rows, [MATCHED, MATCHED])
        self.assertEqual((out.matched, out.added), (2, 0))

    def test_failures_keep_old_values_but_new_row_gets_markers(self):
        fresh = Fresh(nvrs={"vim": ERROR, "openssl": ERROR}, verdicts={
            ("CVE-2026-0001", "vim"): Verdict(state=FETCH_ERROR),
            ("CVE-2026-0003", "openssl"): Verdict(state=FETCH_ERROR)})
        out = sync([Record(2, OLD)], [task(), OPENSSL], fresh)
        self.assertEqual(out.rows[0][DATA], OLD[DATA])
        self.assertEqual(out.rows[1][DATA], [ERROR, "-", "-", FETCH_ERROR, "-", "-", "-"])
        note = Note(2, "CVE-2026-0001", "vim")
        self.assertEqual((out.kept_koji, out.kept_vex), ((note,), (note,)))

    def test_row_with_nothing_to_ask_is_not_marked_missing(self):
        cells = changed(OLD, {report.CVE_ID: "-"})
        out = sync([Record(2, cells)], [OPENSSL], FRESH)
        self.assertEqual(out.rows, [cells, NEW])
        self.assertEqual((out.missing, out.skipped), (0, (Note(2, "-", "vim"),)))
