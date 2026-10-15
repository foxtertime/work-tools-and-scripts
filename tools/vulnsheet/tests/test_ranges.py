import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from unittest import mock

from vulnsheet.ranges import (CVEORG, NVD, Docs, Interval, RangeNote, RangeSettings,
                              cveorg_intervals, cveorg_url, fetch_all, judge, nvd_intervals,
                              nvd_url, pick, ranges_for, upstream_version)


def cpe(product, version="*", vendor="f5", update="*", vulnerable=True, **bounds):
    match = {"vulnerable": vulnerable,
             "criteria": "cpe:2.3:a:%s:%s:%s:%s:*:*:*:*:*:*" % (vendor, product, version, update)}
    match.update(bounds)
    return match


def nvd(*matches):
    return {"vulnerabilities": [{"cve": {"configurations": [
        {"nodes": [{"operator": "OR", "cpeMatch": list(matches)}]}]}}]}


def affected(product=None, versions=(), package=None, vendor="x", default=None):
    entry = {"vendor": vendor, "product": product, "versions": list(versions)}
    if package:
        entry["packageName"] = package
    if default:
        entry["defaultStatus"] = default
    return entry


def cveorg(cna=(), adp=()):
    doc = {"containers": {"cna": {"affected": list(cna)}}}
    if adp:
        doc["containers"]["adp"] = [{"affected": list(adp)}]
    return doc


def ge_lt(start, end):
    return Interval(start, True, end, False)


class IntervalTest(unittest.TestCase):
    def test_contains_with_rpm_comparison(self):
        rng = ge_lt("1.11.4", "1.26.3")
        self.assertTrue(rng.contains("1.11.4"))
        self.assertTrue(rng.contains("1.26.2"))
        self.assertFalse(rng.contains("1.26.3"))
        self.assertFalse(rng.contains("1.9.15"))   # 1.9 < 1.11, а не строкой
        self.assertTrue(Interval("8.5p1", True, "9.7p1", True).contains("9.7p1"))
        self.assertTrue(Interval(None, False, "1.1.1x", False).contains("1.1.1w"))
        self.assertTrue(Interval(None, False, None, False).contains("0.1"))

    def test_text(self):
        self.assertEqual(ge_lt("1.11.4", "1.26.3").text(), ">=1.11.4 <1.26.3")
        self.assertEqual(Interval("1.0", False, "2.0", True).text(), ">1.0 <=2.0")
        self.assertEqual(Interval("1.27.0", True, "1.27.0", True).text(), "=1.27.0")
        self.assertEqual(Interval(None, False, "9.6", False).text(), "<9.6")
        self.assertEqual(Interval("1.5.13", True, None, False).text(),
                         ">=1.5.13, верхняя граница не указана")
        self.assertEqual(Interval(None, False, None, False).text(), "любая версия")


class NvdTest(unittest.TestCase):
    def test_ranges_and_exact_versions_of_matching_products(self):
        doc = nvd(cpe("nginx_open_source", versionStartIncluding="1.5.13",
                      versionEndExcluding="1.26.2"),
                  cpe("nginx_open_source", "1.27.0"),
                  cpe("nginx_plus", versionStartIncluding="r27", versionEndExcluding="r31"))
        self.assertEqual(nvd_intervals(doc, {"nginx", "nginx_open_source"}), [
            ge_lt("1.5.13", "1.26.2"), Interval("1.27.0", True, "1.27.0", True)])

    def test_end_including_and_start_excluding(self):
        doc = nvd(cpe("openssh", vendor="openbsd", versionStartExcluding="6.8",
                      versionEndIncluding="9.8"))
        self.assertEqual(nvd_intervals(doc, {"openssh"}), [Interval("6.8", False, "9.8", True)])

    def test_cpe_update_joins_the_version(self):
        doc = nvd(cpe("openssh", "8.5", vendor="openbsd", update="p1"))
        self.assertEqual(nvd_intervals(doc, {"openssh"}), [Interval("8.5p1", True, "8.5p1", True)])

    def test_wildcard_without_bounds_means_any_version(self):
        self.assertEqual(nvd_intervals(nvd(cpe("xz")), {"xz"}), [Interval(None, False, None, False)])

    def test_not_vulnerable_matches_are_platforms_not_the_product(self):
        self.assertEqual(nvd_intervals(nvd(cpe("xz", "5.6.0", vulnerable=False)), {"xz"}), [])

    def test_product_names_are_compared_loosely(self):
        doc = nvd(cpe("HTTP_Server", vendor="apache", versionEndExcluding="2.4.60"))
        self.assertEqual(len(nvd_intervals(doc, {"http server"})), 1)

    def test_missing_or_empty_document(self):
        self.assertEqual(nvd_intervals(None, {"vim"}), [])
        self.assertEqual(nvd_intervals({"vulnerabilities": []}, {"vim"}), [])
        self.assertEqual(nvd_intervals({"vulnerabilities": [{"cve": {}}]}, {"vim"}), [])


class CveOrgTest(unittest.TestCase):
    def test_less_than_and_less_than_or_equal(self):
        doc = cveorg([affected("OpenSSL", [
            {"version": "3.3.0", "lessThan": "3.3.2", "status": "affected", "versionType": "semver"},
            {"version": "1.1.1", "lessThan": "1.1.1za", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"openssl"}),
                         [ge_lt("3.3.0", "3.3.2"), ge_lt("1.1.1", "1.1.1za")])
        doc = cveorg([affected(package="OpenSSH", versions=[
            {"version": "8.5p1", "lessThanOrEqual": "9.7p1", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"openssh"}),
                         [Interval("8.5p1", True, "9.7p1", True)])

    def test_zero_start_means_no_lower_bound(self):
        doc = cveorg([affected("libexpat", [{"version": "0", "lessThan": "2.6.3",
                                             "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"libexpat"}), [Interval(None, False, "2.6.3", False)])

    def test_star_means_no_upper_bound(self):
        # F5 для nginx: «с 1.5.13», верхней границы нет
        doc = cveorg([affected("NGINX Open Source", [
            {"version": "1.5.13", "lessThan": "*", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"nginx open source"}),
                         [Interval("1.5.13", True, None, False)])

    def test_text_ranges_in_the_version_field(self):
        doc = cveorg([affected("git", [{"version": ">= 2.43.0, < 2.43.4", "status": "affected"},
                                       {"version": "= 2.45.0", "status": "affected"},
                                       {"version": "< 2.39.4", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"git"}), [
            ge_lt("2.43.0", "2.43.4"), Interval("2.45.0", True, "2.45.0", True),
            Interval(None, False, "2.39.4", False)])

    def test_plain_versions_are_points(self):
        doc = cveorg([affected(package="xz", versions=[{"version": "5.6.0", "status": "affected"},
                                                        {"version": "5.6.1", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"xz"}), [
            Interval("5.6.0", True, "5.6.0", True), Interval("5.6.1", True, "5.6.1", True)])

    def test_garbage_is_skipped(self):
        # curl в CVE-2023-38545: «8.4.0 < 8.4.0» — пустой диапазон
        doc = cveorg([affected("curl", [
            {"version": "8.4.0", "lessThan": "8.4.0", "status": "affected"},
            {"version": "7.69.0", "lessThan": "7.69.0", "status": "unaffected"},
            {"version": "n/a", "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"curl"}), [])

    def test_unaffected_and_rpm_entries_are_not_upstream_ranges(self):
        doc = cveorg([affected("Red Hat Enterprise Linux 9", package="openssh", default="affected",
                               versions=[{"version": "0:8.7p1-38.el9_4.1", "lessThan": "*",
                                          "status": "unaffected", "versionType": "rpm"}]),
                      affected(package="openssh", versions=[
                          {"version": "0:8.7p1-1.el9", "lessThan": "0:8.7p1-38.el9",
                           "status": "affected", "versionType": "rpm"}])])
        self.assertEqual(cveorg_intervals(doc, {"openssh"}), [])

    def test_cna_first_then_adp(self):
        adp = [affected("libexpat", [{"version": "0", "lessThan": "2.6.3", "status": "affected"}])]
        doc = cveorg([affected("n/a", [{"version": "n/a", "status": "affected"}])], adp)
        self.assertEqual(cveorg_intervals(doc, {"libexpat"}), [Interval(None, False, "2.6.3", False)])
        doc = cveorg([affected("libexpat", [{"version": "2.0", "lessThan": "2.6.2",
                                             "status": "affected"}])], adp)
        self.assertEqual(cveorg_intervals(doc, {"libexpat"}), [ge_lt("2.0", "2.6.2")])

    def test_other_products_do_not_count(self):
        doc = cveorg([affected("NGINX Plus", [{"version": "R4", "lessThan": "*",
                                               "status": "affected"}])])
        self.assertEqual(cveorg_intervals(doc, {"nginx"}), [])


class PickTest(unittest.TestCase):
    NVD_DOC = nvd(cpe("nginx", versionStartIncluding="1.11.4", versionEndExcluding="1.26.3"))
    ORG_DOC = cveorg([affected("nginx", [{"version": "1.11.4", "lessThan": "*",
                                          "status": "affected"}])])

    def test_nvd_wins_when_it_knows_the_product(self):
        got = pick(self.NVD_DOC, self.ORG_DOC, {"nginx"})
        self.assertEqual((got.source, got.intervals), (NVD, (ge_lt("1.11.4", "1.26.3"),)))

    def test_cve_org_fills_the_gap(self):
        got = pick(nvd(), self.ORG_DOC, {"nginx"})
        self.assertEqual(got.source, CVEORG)

    def test_nothing_anywhere(self):
        self.assertIsNone(pick(None, None, {"nginx"}))


class UpstreamVersionTest(unittest.TestCase):
    def test_version_of_the_nvr(self):
        self.assertEqual(upstream_version("nginx-1.26.3-2.sl9"), "1.26.3")
        self.assertEqual(upstream_version("vim-8.2.2637-26.sl9_8.6^4"), "8.2.2637")
        self.assertEqual(upstream_version("python3.11-3.11.9-7.el9"), "3.11.9")
        self.assertEqual(upstream_version("glibc-2:2.34-100.el9"), "2.34")

    def test_markers_and_garbage_have_no_version(self):
        for nvr in ("NOT_FOUND", "ERROR", "-", "", "nginx"):
            self.assertIsNone(upstream_version(nvr))


class JudgeTest(unittest.TestCase):
    RANGES = pick(nvd(cpe("nginx", versionStartIncluding="1.11.4", versionEndExcluding="1.26.3"),
                      cpe("nginx", "1.27.0")), None, {"nginx"})

    def test_inside(self):
        note = judge("1.26.2", self.RANGES)
        self.assertEqual(note, RangeNote("1.26.2", True, self.RANGES.source,
                                         (ge_lt("1.11.4", "1.26.3"),)))

    def test_outside_lists_every_range(self):
        note = judge("1.26.3", self.RANGES)
        self.assertEqual((note.inside, note.intervals), (False, self.RANGES.intervals))

    def test_unknown(self):
        self.assertEqual(judge("1.26.3", None), RangeNote("1.26.3", None, None, ()))


class FetchTest(unittest.TestCase):
    CVES = ["CVE-2024-7347", "CVE-2025-23419", "CVE-2023-44487"]

    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)
        self.answers = {}
        for cve in self.CVES:
            self.answers[nvd_url(cve)] = nvd(cpe("nginx", versionEndExcluding="1.26.3"))
            self.answers[cveorg_url(cve)] = cveorg([affected("nginx", [
                {"version": "1.0", "lessThan": "*", "status": "affected"}])])
        self.calls = []
        mock.patch("vulnsheet.ranges.download", side_effect=self._download).start()
        self.sleep = mock.patch("vulnsheet.ranges.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def _download(self, url, timeout=None, headers=None):
        self.calls.append((url, dict(headers or {})))
        answer = self.answers.get(url)
        if isinstance(answer, Exception):
            raise answer
        return None if answer is None else json.dumps(answer).encode()

    def settings(self, **kwargs):
        values = dict(cache_dir=self.room, cache_ttl=3600, jobs=4, retries=2, timeout=5)
        values.update(kwargs)
        return RangeSettings(**values)

    def test_both_sources_are_fetched(self):
        docs, failures = fetch_all(self.CVES[:1], self.settings())
        self.assertEqual(docs["CVE-2024-7347"], Docs(self.answers[nvd_url("CVE-2024-7347")],
                                                     self.answers[cveorg_url("CVE-2024-7347")], ()))
        self.assertEqual(failures, {})

    def test_nvd_is_paced_without_a_key(self):
        fetch_all(self.CVES, self.settings())
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [6.0, 6.0])

    def test_key_is_sent_to_nvd_only_and_shortens_the_pause(self):
        fetch_all(self.CVES, self.settings(nvd_key="secret-key"))
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [0.6, 0.6])
        for url, headers in self.calls:
            self.assertEqual(headers.get("apiKey"), "secret-key" if "nvd" in url else None)

    def test_cache_spares_the_network_and_the_pause(self):
        fetch_all(self.CVES, self.settings())
        self.calls.clear()
        self.sleep.reset_mock()
        docs, _ = fetch_all(self.CVES, self.settings())
        self.assertEqual(self.calls, [])
        self.sleep.assert_not_called()
        self.assertEqual(len(docs), 3)

    def test_unknown_cve_at_cve_org_is_not_a_failure(self):
        del self.answers[cveorg_url("CVE-2024-7347")]
        docs, failures = fetch_all(self.CVES[:1], self.settings())
        self.assertIsNone(docs["CVE-2024-7347"].cveorg)
        self.assertEqual((docs["CVE-2024-7347"].failed, failures), ((), {}))

    def test_one_source_failing_leaves_the_other(self):
        self.answers[nvd_url("CVE-2024-7347")] = urllib.error.URLError("сеть")
        with self.assertLogs("vulnsheet.ranges", "WARNING") as caught:
            docs, failures = fetch_all(self.CVES[:1], self.settings())
        self.assertEqual(docs["CVE-2024-7347"].failed, (NVD,))
        self.assertIsNotNone(docs["CVE-2024-7347"].cveorg)
        self.assertIn("CVE-2024-7347", "\n".join(caught.output))
        self.assertEqual(failures, {})

    def test_both_failing_is_a_failure(self):
        for url in (nvd_url("CVE-2024-7347"), cveorg_url("CVE-2024-7347")):
            self.answers[url] = urllib.error.URLError("сеть")
        with self.assertLogs("vulnsheet.ranges", "WARNING"):
            docs, failures = fetch_all(self.CVES[:1], self.settings())
        self.assertEqual(set(failures), {"CVE-2024-7347"})
        self.assertEqual(docs["CVE-2024-7347"].failed, (NVD, CVEORG))

    def test_failed_request_is_retried(self):
        url = nvd_url("CVE-2024-7347")
        good = self.answers[url]
        answers = [urllib.error.HTTPError(url, 503, "busy", {}, None), good]
        self.answers[url] = None
        original = self._download

        def flaky(u, timeout=None, headers=None):
            if u == url and answers:
                self.calls.append((u, dict(headers or {})))
                answer = answers.pop(0)
                if isinstance(answer, Exception):
                    raise answer
                return json.dumps(answer).encode()
            return original(u, timeout, headers)
        mock.patch("vulnsheet.ranges.download", side_effect=flaky).start()
        docs, failures = fetch_all(self.CVES[:1], self.settings())
        self.assertEqual(docs["CVE-2024-7347"].nvd, good)
        self.assertEqual(failures, {})


class RangesForTest(unittest.TestCase):
    NVD_DOC = nvd(cpe("nginx", versionEndExcluding="1.26.3"))

    def test_found(self):
        got, failed = ranges_for(Docs(self.NVD_DOC, None, ()), {"nginx"})
        self.assertEqual((got.source, failed), (NVD, False))

    def test_nothing_known_is_unknown_not_a_failure(self):
        self.assertEqual(ranges_for(Docs(nvd(), None, ()), {"nginx"}), (None, False))

    def test_nothing_known_after_a_failed_source_is_a_failure(self):
        # NVD мог знать диапазон: «неизвестен» было бы неправдой
        self.assertEqual(ranges_for(Docs(None, cveorg(), (NVD,)), {"nginx"}), (None, True))

    def test_found_despite_a_failed_source(self):
        got, failed = ranges_for(Docs(self.NVD_DOC, None, (CVEORG,)), {"nginx"})
        self.assertEqual((got.source, failed), (NVD, False))


if __name__ == "__main__":
    unittest.main()
