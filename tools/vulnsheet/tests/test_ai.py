import json
import os
import shutil
import tempfile
import unittest

from vulnsheet.ai import AiError, read

GLIBC = {"cve": "CVE-2026-6368", "package": "glibc", "nvr": "glibc-2.34-270.el9_8",
         "verdict": "affected", "confidence": "high",
         "remediation": "vendor update available", "run": "2026-10-21T12:04"}
POLKIT = {"cve": "CVE-2025-7519", "package": "polkit", "nvr": "polkit-0.117-14.el9",
          "verdict": "affected", "confidence": "high",
          "remediation": "backport prepared", "run": "2026-10-21T12:04"}


def doc(*results, **top):
    body = {"format": 1, "plugin": "4.0.0", "run": "2026-10-22T07:45",
            "results": list(results)}
    body.update(top)
    return body


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)

    def write(self, body=None, data=None):
        path = os.path.join(self.room, "ai.json")
        with open(path, "wb") as handle:
            handle.write(data if data is not None
                         else json.dumps(body, ensure_ascii=False).encode("utf-8"))
        return path

    def assertRejected(self, needle, body=None, data=None):
        with self.assertRaises(AiError) as caught:
            read(self.write(body, data))
        self.assertIn(needle, str(caught.exception))
        self.assertIn("ai.json", str(caught.exception))

    def test_results_by_cve_and_package(self):
        found = read(self.write(doc(GLIBC, POLKIT)))
        self.assertEqual(found.cells, {
            ("CVE-2026-6368", "glibc"): ("glibc-2.34-270.el9_8", "affected", "high",
                                         "vendor update available", "21.10.2026"),
            ("CVE-2025-7519", "polkit"): ("polkit-0.117-14.el9", "affected", "high",
                                          "backport prepared", "21.10.2026"),
        })
        self.assertEqual((found.plugin, found.run, found.total),
                         ("4.0.0", "2026-10-22T07:45", 2))
        self.assertEqual((found.skipped, found.repeated), ((), 0))

    def test_file_time_falls_back_to_generated(self):
        body = doc(GLIBC)
        del body["run"]
        body["generated"] = "2026-10-21T12:31:00+03:00"
        self.assertEqual(read(self.write(body)).run, "2026-10-21T12:31:00+03:00")
        del body["generated"]
        self.assertIsNone(read(self.write(body)).run)

    def test_em_dash_is_an_empty_value(self):
        entry = dict(GLIBC, remediation="—", confidence=" — ")
        cells = read(self.write(doc(entry))).cells[("CVE-2026-6368", "glibc")]
        self.assertEqual((cells[2], cells[3]), ("-", "-"))

    def test_cve_and_package_are_matched_like_table_rows(self):
        entry = dict(GLIBC, cve=" cve-2026-6368 ", package=" glibc ")
        self.assertIn(("CVE-2026-6368", "glibc"), read(self.write(doc(entry))).cells)

    def test_missing_empty_and_null_fields_are_dashes(self):
        entry = {"cve": "CVE-2026-6368", "package": "glibc", "nvr": "", "verdict": None,
                 "confidence": "  "}
        self.assertEqual(read(self.write(doc(entry))).cells[("CVE-2026-6368", "glibc")],
                         ("-",) * 5)

    def test_run_is_written_as_a_date(self):
        for run, cell in (("2026-10-21T12:04", "21.10.2026"), ("2026-10-21", "21.10.2026"),
                          ("вчера", "вчера"), ("21.10.2026", "21.10.2026")):
            with self.subTest(run=run):
                cells = read(self.write(doc(dict(GLIBC, run=run)))).cells
                self.assertEqual(cells[("CVE-2026-6368", "glibc")][4], cell)

    def test_non_string_values_are_written_as_text(self):
        entry = dict(GLIBC, confidence=0.9, verdict=True, remediation=["a", "b"])
        cells = read(self.write(doc(entry))).cells[("CVE-2026-6368", "glibc")]
        self.assertEqual(cells[1:4], ("true", "0.9", '["a", "b"]'))

    def verdict_of(self, *results):
        return read(self.write(doc(*results))).cells[("CVE-2026-6368", "glibc")][1]

    def test_the_freshest_result_of_a_pair_wins(self):
        newer = dict(GLIBC, verdict="not affected", run="2026-10-22T09:00")
        found = read(self.write(doc(newer, GLIBC)))
        self.assertEqual(found.cells[("CVE-2026-6368", "glibc")][1:5:3],
                         ("not affected", "22.10.2026"))
        self.assertEqual((found.total, found.repeated), (2, 1))
        self.assertEqual(self.verdict_of(GLIBC, newer), "not affected")

    def test_freshness_counts_the_time_and_the_offset(self):
        later_today = dict(GLIBC, verdict="later", run="2026-10-21T15:00")
        self.assertEqual(self.verdict_of(later_today, GLIBC), "later")
        # время с поясом сравнивается в UTC: 12:30 по Москве — 09:30 UTC,
        # раньше 10:00 UTC
        utc = dict(GLIBC, verdict="utc", run="2026-10-21T10:00:00+00:00")
        msk = dict(GLIBC, verdict="msk", run="2026-10-21T12:30:00+03:00")
        self.assertEqual(self.verdict_of(msk, utc), "utc")

    def test_result_with_a_run_beats_one_without(self):
        undated = dict(GLIBC, verdict="undated", run="вчера")
        self.assertEqual(self.verdict_of(undated, GLIBC), "affected")
        self.assertEqual(self.verdict_of(GLIBC, dict(undated, run=None)), "affected")

    def test_same_or_unknown_run_first_wins(self):
        twin = dict(GLIBC, verdict="twin")
        self.assertEqual(self.verdict_of(GLIBC, twin), "affected")
        self.assertEqual(self.verdict_of(dict(GLIBC, run=""), dict(twin, run="?")), "affected")

    def test_results_without_cve_or_package_are_skipped_with_a_reason(self):
        found = read(self.write(doc(dict(GLIBC, cve="glibc"), dict(GLIBC, package=" "),
                                    {"nvr": "x"}, "строка", POLKIT)))
        self.assertEqual(list(found.cells), [("CVE-2025-7519", "polkit")])
        self.assertEqual([(s.number, s.reason) for s in found.skipped], [
            (1, "не CVE-ID: 'glibc'"), (2, "нет package"), (3, "нет cve"),
            (4, "не объект")])

    def test_empty_results(self):
        found = read(self.write(doc()))
        self.assertEqual((found.cells, found.total), ({}, 0))

    def test_bad_files(self):
        cases = [
            ("не JSON", None, b"{format: 1"),
            ("UTF-8", None, json.dumps(doc(GLIBC), ensure_ascii=False)
             .replace("glibc", "глибц").encode("cp1251")),
            ("не объект", [GLIBC], None),
            ("format", doc(GLIBC, format=2), None),
            ("format", {"results": [GLIBC]}, None),
            ("format", doc(GLIBC, format=True), None),
            ("results", doc(results={"a": 1}), None),
            ("results", {"format": 1}, None),
        ]
        for needle, body, data in cases:
            with self.subTest(needle=needle, body=body):
                self.assertRejected(needle, body, data)

    def test_bom_is_allowed(self):
        data = b"\xef\xbb\xbf" + json.dumps(doc(GLIBC)).encode("utf-8")
        self.assertIn(("CVE-2026-6368", "glibc"), read(self.write(data=data)).cells)

    def test_missing_file(self):
        with self.assertRaises(AiError) as caught:
            read(os.path.join(self.room, "нет.json"))
        self.assertIn("не читается", str(caught.exception))
