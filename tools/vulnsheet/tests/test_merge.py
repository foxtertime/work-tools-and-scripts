import types
import unittest

from vulnsheet import report
from vulnsheet.kojiclient import ERROR, NOT_FOUND
from vulnsheet.merge import Fresh, Note, build, pairs, refresh, sync
from vulnsheet.ranges import CVEORG, NVD, Interval, RangeNote
from vulnsheet.table import Record
from vulnsheet.tasks import Task
from vulnsheet.vex import FETCH_ERROR, Verdict

LINK = "https://access.redhat.com/security/cve/"
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"

# Строки, которые люди уже вели: ручные колонки заполнены, koji и VEX старые.
OLD = ["Иванов", "В работе", "01.09.2026", "-", "обновить",
       "TASKID-1", "CVE-2026-0001", "В работу", "01.09.2026", "КМ", "vim", "+", "+",
       "vim-1-1.sl9", "-", "-", "Affected", "Low", "3.1", "-",
       LINK + "CVE-2026-0001", "ждём апстрим"]
BASH = ["Петров", "Готово", "02.09.2026", "03.09.2026", "обновлено",
        "TASKID-2", "CVE-2026-0002", "Выполнена", "02.09.2026", "КМ", "bash", "-", "-",
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
# (GitLab и диапазоны в FRESH не проверялись — P и D прежние)
MATCHED = (OLD[:5] + ["TASKID-1", "CVE-2026-0001", "Отменен", "22.09.2026", "ПП", "vim"]
           + OLD[report.MARKS] + UPDATED + OLD[20:])
# BASH, чьей задачи нет в блоках
BASH_MISSING = (BASH[:7] + [report.MISSING] + BASH[8:13]
                + ["bash-5-1.sl9", "-", "-", "Affected", "Moderate", "5.5", "-"] + BASH[20:])
# новая строка из OPENSSL
NEW = (["-"] * 5 + ["TASKID-3", "CVE-2026-0003", "В работу", "23.09.2026", "КМ", "openssl",
                    "-", "-", NOT_FOUND, "-", "-", "not listed", "-", "-", "-",
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
        self.assertEqual(out.rows, [OLD[:13] + UPDATED + OLD[20:]])
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
        self.assertEqual(out.rows[0], OLD[:13] + ["vim-2-1.sl9"] + OLD[14:])
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


VIM, BASH_PAIR, OPENSSL_PAIR = (("CVE-2026-0001", "vim"), ("CVE-2026-0002", "bash"),
                                ("CVE-2026-0003", "openssl"))
# vim закрыт патчем под CVE-2026-0001, bash — под чужую CVE
PATCHED = FRESH._replace(patched=types.MappingProxyType({
    "vim": frozenset({"CVE-2026-0001"}), "bash": frozenset({"CVE-2026-9999"})}))
INSIDE = RangeNote("2", True, NVD, (Interval(None, False, "3", False),))
OUTSIDE = RangeNote("5", False, CVEORG, (Interval(None, False, "3", False),))
UNKNOWN = RangeNote("1", None, None, ())


def marks(row):
    return row[report.PATCH], row[report.RANGE]


class PatchMarkTest(unittest.TestCase):
    def test_new_row_gets_plus_only_for_its_own_cve(self):
        fresh = PATCHED._replace(nvrs=dict(FRESH.nvrs, openssl="openssl-3-1.sl9"),
                                 patched=dict(PATCHED.patched, openssl=frozenset()))
        rows = build([task(), task("TASKID-2", "CVE-2026-0002", "bash"), OPENSSL], fresh).rows
        self.assertEqual([r[report.PATCH] for r in rows], ["+", "-", "-"])

    def test_refresh_overwrites_the_old_mark(self):
        rows = refresh([Record(2, BASH), Record(3, OLD)], PATCHED._replace(
            patched={"vim": frozenset(), "bash": frozenset({"CVE-2026-0002"})})).rows
        self.assertEqual([r[report.PATCH] for r in rows], ["+", "-"])

    def test_unchecked_component_keeps_the_old_mark_and_is_noted(self):
        out = refresh([Record(2, OLD)], PATCHED._replace(patched={}))
        self.assertEqual(out.rows[0][report.PATCH], "+")
        self.assertEqual(out.kept_patch, (Note(2, "CVE-2026-0001", "vim"),))

    def test_unchecked_component_of_a_new_row_is_minus(self):
        out = build([task()], PATCHED._replace(patched={}))
        self.assertEqual(out.rows[0][report.PATCH], "-")
        self.assertEqual((out.kept_patch, out.patch_unchecked), ((), 1))

    def test_kept_value_other_than_plus_or_minus_becomes_minus(self):
        # колонки вставили руками и оставили пустыми, а GitLab упал
        rows = [Record(2, changed(OLD, {report.PATCH: ""})),
                Record(3, changed(OLD, {report.PATCH: " + "})),
                Record(4, changed(OLD, {report.PATCH: "?"}))]
        out = refresh(rows, PATCHED._replace(patched={}))
        self.assertEqual([r[report.PATCH] for r in out.rows], ["-", "+", "-"])
        self.assertEqual(dict(out.patch_marks), {"+": 1, "-": 2})

    def test_package_not_in_koji_has_no_patch(self):
        cells = changed(OLD, {report.COMPONENT: "openssl", report.CVE_ID: "CVE-2026-0003"})
        out = refresh([Record(2, cells)], PATCHED)
        self.assertEqual(out.rows[0][report.PATCH], "-")
        self.assertEqual(out.kept_patch, ())

    def test_without_gitlab_old_marks_stay_and_nothing_is_counted(self):
        out = refresh([Record(2, OLD)], FRESH)
        self.assertEqual(out.rows[0][report.PATCH], "+")
        self.assertEqual((out.kept_patch, dict(out.patch_marks)), ((), {}))

    def test_marks_are_counted(self):
        out = sync([Record(2, OLD), Record(3, BASH)], [task(), OPENSSL],
                   PATCHED._replace(patched={"vim": frozenset({"CVE-2026-0001"})}))
        # vim «+», bash не проверен — прежний «-», openssl без билда — «-»
        self.assertEqual(dict(out.patch_marks), {"+": 1, "-": 2})
        self.assertEqual((len(out.kept_patch), out.patch_unchecked), (1, 0))


class RangeMarkTest(unittest.TestCase):
    def test_plus_only_outside_the_ranges(self):
        for note, mark in ((OUTSIDE, "+"), (INSIDE, "-"), (UNKNOWN, "-")):
            with self.subTest(note=note):
                row = build([task()], FRESH._replace(ranges={VIM: note})).rows[0]
                self.assertEqual(row[report.RANGE], mark)

    def test_failed_ranges_keep_the_old_mark(self):
        out = refresh([Record(2, OLD)], FRESH._replace(ranges={}))
        self.assertEqual(out.rows[0][report.RANGE], "+")
        self.assertEqual(out.kept_range, (Note(2, "CVE-2026-0001", "vim"),))

    def test_failed_ranges_of_a_new_row_are_minus(self):
        out = build([task()], FRESH._replace(ranges={}))
        self.assertEqual((out.rows[0][report.RANGE], out.range_unchecked), ("-", 1))

    def test_refresh_overwrites_the_old_mark(self):
        out = refresh([Record(2, OLD)], FRESH._replace(ranges={VIM: INSIDE}))
        self.assertEqual(out.rows[0][report.RANGE], "-")

    def test_without_ranges_old_marks_stay(self):
        self.assertEqual(refresh([Record(2, OLD)], FRESH).rows[0][report.RANGE], "+")

    def test_ranges_are_counted(self):
        fresh = FRESH._replace(ranges={VIM: INSIDE, BASH_PAIR: OUTSIDE})
        out = refresh([Record(2, OLD), Record(3, BASH)], fresh)
        self.assertEqual(dict(out.range_kinds), {True: 1, False: 1})
        self.assertEqual(dict(out.range_sources), {NVD: 1, CVEORG: 1})
        self.assertEqual(dict(out.range_marks), {"+": 1, "-": 1})

    def test_unknown_range_is_counted_apart(self):
        fresh = FRESH._replace(nvrs=dict(FRESH.nvrs, openssl="openssl-1-1.sl9"),
                               ranges={OPENSSL_PAIR: UNKNOWN})
        out = build([OPENSSL], fresh)
        self.assertEqual((dict(out.range_kinds), dict(out.range_marks)), ({None: 1}, {"-": 1}))


class CommentTest(unittest.TestCase):
    def test_comment_is_carried_over_untouched(self):
        fresh = PATCHED._replace(ranges={VIM: OUTSIDE})
        self.assertEqual(refresh([Record(2, OLD)], fresh).rows[0][report.COMMENT_INDEX],
                         "ждём апстрим")

    def test_new_row_has_an_empty_comment(self):
        fresh = PATCHED._replace(ranges={VIM: OUTSIDE})
        self.assertEqual(build([task()], fresh).rows[0][report.COMMENT_INDEX], "-")

    def test_row_with_nothing_to_ask_is_left_as_is(self):
        cells = changed(OLD, {report.CVE_ID: "-"})
        out = refresh([Record(2, cells)], PATCHED._replace(ranges={}))
        self.assertEqual(out.rows, [cells])
        self.assertEqual((dict(out.patch_marks), out.kept_range), ({}, ()))


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
