import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tests.fakes import APPSTREAM96, BASEOS96, EUS92, RHEL9, RHEL_AI, csaf, pid
from vulnsheet.vex import NO_RECORD, Verdict, VexError, build_index, fetch, fetch_all, lookup, parse_rhel, prepare_cache, vex_url

CVE = "CVE-2026-1000"
FIXED_VIM = "vim-2:8.2.2637-22.el9_6.x86_64"
RHSA = "https://access.redhat.com/errata/RHSA-2026:1234"


def vendor_fix(*pids, date="2026-09-02T00:00:00+00:00", url=RHSA):
    return {"category": "vendor_fix", "product_ids": list(pids), "url": url, "date": date}


def score(value, *pids):
    return {"cvss_v3": {"baseScore": value, "vectorString": "CVSS:3.1/AV:L"},
            "products": list(pids)}


class LookupTest(unittest.TestCase):
    def verdict(self, doc, component="vim", rhel="9"):
        return lookup(build_index(doc), component, rhel)

    def test_fixed_carries_nvr_date_and_advisory(self):
        fixed = pid(APPSTREAM96, FIXED_VIM)
        doc = csaf(CVE, [("fixed", APPSTREAM96, FIXED_VIM)],
                   scores=[score(7.8, fixed)], remediations=[vendor_fix(fixed)])
        self.assertEqual(self.verdict(doc), Verdict(
            state="Fixed", severity="Moderate", cvss="7.8",
            fixed_nvr="vim-8.2.2637-22.el9_6", fix_date="2026-09-02",
            advisory_url=RHSA))

    def test_will_not_fix_comes_from_remediation(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")], remediations=[
            {"category": "no_fix_planned", "details": "Will not fix",
             "product_ids": [pid(RHEL9, "vim")]}])
        verdict = self.verdict(doc)
        self.assertEqual(verdict.state, "Will not fix")
        self.assertEqual((verdict.fixed_nvr, verdict.advisory_url), ("", ""))

    def test_affected_without_remediation(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")])
        self.assertEqual(self.verdict(doc).state, "Affected")

    def test_under_investigation_takes_the_agreed_score(self):
        # Продукта нет ни в одном блоке оценок, но все блоки согласны.
        doc = csaf(CVE, [("under_investigation", RHEL9, "vim")],
                   scores=[score(5.5, "другой-продукт")])
        verdict = self.verdict(doc)
        self.assertEqual((verdict.state, verdict.cvss), ("Under investigation", "5.5"))

    def test_not_affected(self):
        doc = csaf(CVE, [("known_not_affected", RHEL9, "vim")])
        self.assertEqual(self.verdict(doc).state, "Not affected")

    def test_zero_cvss_is_kept(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim")],
                   scores=[score(0.0, pid(RHEL9, "vim"))])
        self.assertEqual(self.verdict(doc).cvss, "0.0")

    def test_flatpak_stream_is_not_the_package(self):
        fixed = pid(APPSTREAM96, "firefox-0:128.0-1.el9_6.x86_64")
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak"),
                         ("fixed", APPSTREAM96, "firefox-0:128.0-1.el9_6.x86_64")],
                   remediations=[vendor_fix(fixed)])
        verdict = self.verdict(doc, "firefox")
        self.assertEqual((verdict.state, verdict.fixed_nvr),
                         ("Fixed", "firefox-128.0-1.el9_6"))

    def test_stream_is_reported_when_nothing_else(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak")])
        self.assertEqual(self.verdict(doc, "firefox").state, "Affected")

    def test_minor_stream_only_is_not_listed_with_hint(self):
        doc = csaf(CVE, [("fixed", EUS92, "vim-2:8.2.2637-20.el9_2.x86_64")])
        verdict = self.verdict(doc)
        self.assertEqual(verdict.state, "not listed (present for 9.2)")
        self.assertEqual(verdict.severity, "Moderate")

    def test_absent_component_is_not_listed(self):
        doc = csaf(CVE, [("fixed", APPSTREAM96, FIXED_VIM)])
        self.assertEqual(self.verdict(doc, "emacs").state, "not listed")

    def test_component_match_is_exact(self):
        doc = csaf(CVE, [("known_affected", RHEL9, "vim-enhanced")])
        self.assertEqual(self.verdict(doc).state, "not listed")

    def test_other_red_hat_products_are_ignored(self):
        doc = csaf(CVE, [("known_affected", RHEL_AI, "vim")])
        self.assertEqual(self.verdict(doc).state, "not listed")

    def test_most_exposed_verdict_wins(self):
        fixed = pid(BASEOS96, FIXED_VIM)
        doc = csaf(CVE, [("fixed", BASEOS96, FIXED_VIM),
                         ("known_affected", APPSTREAM96, "vim")],
                   remediations=[vendor_fix(fixed)])
        verdict = self.verdict(doc)
        self.assertEqual((verdict.state, verdict.fixed_nvr, verdict.advisory_url),
                         ("Affected", "", ""))

    def test_no_document_means_no_record(self):
        self.assertEqual(lookup(None, "vim", "9"), Verdict(state=NO_RECORD))


class ParseRhelTest(unittest.TestCase):
    def test_accepted_spellings(self):
        for value, want in [("9", "9"), ("9.2", "9.2"), ("RHEL 9", "9"),
                            ("rhel-9", "9"), ("el9", "9"), ("RHEL9.4", "9.4")]:
            with self.subTest(value=value):
                self.assertEqual(parse_rhel(value), want)

    def test_rejected_values(self):
        for value in ["", "nine", "9.x", "rhel"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_rhel(value)


DOC = csaf(CVE, [("under_investigation", RHEL9, "vim")])
BODY = json.dumps(DOC).encode()


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)
        self.sleep = mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def cached(self):
        return os.path.join(self.cache, "cve-2026-1000.json")

    def test_url(self):
        self.assertEqual(vex_url(CVE), "https://security.access.redhat.com/"
                                       "data/csaf/v2/vex/2026/cve-2026-1000.json")

    def test_downloads_once_then_reads_cache(self):
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, self.cache), DOC)
            self.assertEqual(fetch(CVE, self.cache), DOC)
        download.assert_called_once_with(vex_url(CVE))

    def test_404_means_no_record(self):
        with mock.patch("vulnsheet.vex.download", return_value=None):
            self.assertIsNone(fetch(CVE, self.cache))

    def test_corrupt_cache_falls_back_to_network(self):
        with open(self.cached(), "w") as handle:
            handle.write("{оборвано")
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, self.cache), DOC)
        download.assert_called_once()

    def test_stale_cache_is_refetched(self):
        with open(self.cached(), "w") as handle:
            json.dump({"старый": True}, handle)
        os.utime(self.cached(), (0, 0))
        with mock.patch("vulnsheet.vex.download", return_value=BODY):
            self.assertEqual(fetch(CVE, self.cache), DOC)

    def test_retries_then_gives_up(self):
        with mock.patch("vulnsheet.vex.download", side_effect=OSError("сеть")) as download:
            with self.assertRaises(VexError):
                fetch(CVE)
        self.assertEqual(download.call_count, 3)
        self.assertEqual([c.args for c in self.sleep.call_args_list], [(1,), (2,)])

    def test_retry_recovers(self):
        with mock.patch("vulnsheet.vex.download", side_effect=[OSError("сеть"), BODY]):
            self.assertEqual(fetch(CVE), DOC)


class FetchAllTest(unittest.TestCase):
    def setUp(self):
        mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_indices_failures_and_missing_records(self):
        def download(url):
            if "1002" in url:
                raise OSError("сеть")
            return BODY if "1000" in url else None

        with mock.patch("vulnsheet.vex.download", side_effect=download) as fake:
            with self.assertLogs("vulnsheet", "WARNING") as caught:
                indices, failures = fetch_all(
                    [CVE, "CVE-2026-1001", "CVE-2026-1002", CVE], jobs=2)
        self.assertEqual(sorted(indices), [CVE, "CVE-2026-1001"])
        self.assertIsNone(indices["CVE-2026-1001"])
        self.assertEqual(lookup(indices[CVE], "vim", "9").state, "Under investigation")
        self.assertEqual(list(failures), ["CVE-2026-1002"])
        self.assertIn("CVE-2026-1002", "\n".join(caught.output))
        # 1000 и 1001 — по одному разу, 1002 — три попытки
        self.assertEqual(fake.call_count, 5)

    def test_malformed_document_is_a_failure(self):
        with mock.patch("vulnsheet.vex.download", return_value=b'{"document": {}}'):
            with self.assertLogs("vulnsheet", "WARNING"):
                indices, failures = fetch_all([CVE])
        self.assertEqual((indices, list(failures)), ({}, [CVE]))

    def test_malformed_document_is_not_cached(self):
        cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cache)
        with mock.patch("vulnsheet.vex.download", return_value=b'{"document": {}}'):
            with self.assertLogs("vulnsheet", "WARNING"):
                fetch_all([CVE], cache)
        self.assertFalse(os.path.exists(os.path.join(cache, "cve-2026-1000.json")))


class PrepareCacheTest(unittest.TestCase):
    def test_creates_directory(self):
        room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, room)
        path = os.path.join(room, "vulnsheet")
        self.assertEqual(prepare_cache(path), path)
        self.assertTrue(os.path.isdir(path))

    def test_unusable_path_disables_cache(self):
        with tempfile.NamedTemporaryFile() as blocker:
            with self.assertLogs("vulnsheet", "WARNING"):
                self.assertIsNone(prepare_cache(os.path.join(blocker.name, "sub")))
