import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tests.fakes import (APPSTREAM96, BASEOS96, EUS92, FASTDATAPATH9, RHEL9, RHEL_AI,
                         UNKNOWN_REPO9, csaf, pid)
from vulnsheet import vex
from vulnsheet.vex import (NO_RECORD, Verdict, VexError, VexSettings, build_index,
                           fetch, fetch_all, lookup, parse_rhel, prepare_cache, vex_url)

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

    def test_stream_is_never_taken_for_the_package(self):
        # Без маппинга firefox — только обычный пакет. Стрим — другой продукт,
        # и его вердикт в строку не попадает, даже если больше ничего нет.
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak")])
        self.assertEqual(self.verdict(doc, "firefox").state,
                         "not listed (streams: firefox:flatpak)")

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


class RhelRepositoryTest(unittest.TestCase):
    """Часть CPE после «::» — репозиторий; надстройки вроде Fast Datapath за
    RHEL не считаются, неизвестный репозиторий учитывается с предупреждением."""
    FDP_VIM = "vim-2:9.1.0-1.el9fdp.x86_64"
    FDP_RHSA = "https://access.redhat.com/errata/RHSA-2026:9999"

    def setUp(self):
        vex._warned_repos.clear()
        self.addCleanup(vex._warned_repos.clear)
        self.warning = mock.patch.object(vex.logger, "warning").start()
        self.addCleanup(mock.patch.stopall)

    def test_fast_datapath_is_not_rhel(self):
        # FDP первым в документе и errata той же даты — раньше побеждал он
        doc = csaf(CVE, [("fixed", FASTDATAPATH9, self.FDP_VIM),
                         ("fixed", APPSTREAM96, FIXED_VIM)],
                   remediations=[vendor_fix(pid(FASTDATAPATH9, self.FDP_VIM), url=self.FDP_RHSA),
                                 vendor_fix(pid(APPSTREAM96, FIXED_VIM))])
        verdict = lookup(build_index(doc), "vim", "9")
        self.assertEqual((verdict.advisory_url, verdict.fixed_nvr),
                         (RHSA, "vim-8.2.2637-22.el9_6"))
        self.warning.assert_not_called()

    def test_fast_datapath_only_is_not_listed(self):
        doc = csaf(CVE, [("fixed", FASTDATAPATH9, self.FDP_VIM)],
                   remediations=[vendor_fix(pid(FASTDATAPATH9, self.FDP_VIM))])
        self.assertEqual(lookup(build_index(doc), "vim", "9").state, "not listed")

    def test_unknown_repository_counts_as_rhel_and_warns_once(self):
        doc = csaf(CVE, [("fixed", UNKNOWN_REPO9, FIXED_VIM)],
                   remediations=[vendor_fix(pid(UNKNOWN_REPO9, FIXED_VIM))])
        index = build_index(doc)
        self.assertEqual(lookup(index, "vim", "9").state, "Fixed")
        lookup(index, "vim", "9")
        self.assertEqual(self.warning.call_count, 1)
        self.assertIn("something_new", self.warning.call_args.args[0] % self.warning.call_args.args[1:])

    def test_unknown_repository_of_other_package_is_silent(self):
        doc = csaf(CVE, [("fixed", UNKNOWN_REPO9, "bash-0:5.1-1.el9.x86_64"),
                         ("fixed", APPSTREAM96, FIXED_VIM)])
        lookup(build_index(doc), "vim", "9")
        self.warning.assert_not_called()

    def test_known_repositories_are_silent(self):
        doc = csaf(CVE, [("fixed", APPSTREAM96, FIXED_VIM), ("fixed", BASEOS96, FIXED_VIM),
                         ("known_affected", RHEL9, "vim")])
        lookup(build_index(doc), "vim", "9")
        self.warning.assert_not_called()


NGINX_FIXED = "nginx-2:1.20.1-22.el9_6.x86_64"


def nginx_doc():
    """Обычный nginx исправлен, стрим 1.26 уязвим, стрим 1.24 не будут чинить."""
    return csaf(CVE, [("fixed", APPSTREAM96, NGINX_FIXED),
                      ("known_affected", APPSTREAM96, "nginx::nginx:1.26"),
                      ("known_affected", APPSTREAM96, "nginx::nginx:1.24")],
                remediations=[vendor_fix(pid(APPSTREAM96, NGINX_FIXED)),
                              {"category": "no_fix_planned", "details": "Will not fix",
                               "product_ids": [pid(APPSTREAM96, "nginx::nginx:1.24")]}])


class StreamLookupTest(unittest.TestCase):
    def verdict(self, stream=None, component="nginx", doc=None):
        return lookup(build_index(doc or nginx_doc()), component, "9", stream)

    def test_plain_package_ignores_streams(self):
        verdict = self.verdict()
        self.assertEqual((verdict.state, verdict.fixed_nvr),
                         ("Fixed", "nginx-1.20.1-22.el9_6"))

    def test_mapped_stream_replaces_the_package(self):
        verdict = self.verdict("nginx:1.26")
        self.assertEqual((verdict.state, verdict.fixed_nvr, verdict.advisory_url),
                         ("Affected", "", ""))

    def test_each_stream_has_its_own_verdict(self):
        self.assertEqual(self.verdict("nginx:1.24").state, "Will not fix")

    def test_short_stream_form(self):
        self.assertEqual(self.verdict("1.26").state, "Affected")

    def test_package_inside_another_module(self):
        fixed_npm = "npm-1:10.8.2-1.el9_6.x86_64"
        doc = csaf(CVE, [("known_affected", APPSTREAM96, "npm::nodejs:20"),
                         ("fixed", APPSTREAM96, fixed_npm)],
                   remediations=[vendor_fix(pid(APPSTREAM96, fixed_npm))])
        self.assertEqual(self.verdict("nodejs:20", "npm", doc).state, "Affected")
        self.assertEqual(self.verdict(None, "npm", doc).state, "Fixed")

    def test_missing_stream_lists_what_exists(self):
        self.assertEqual(self.verdict("nginx:1.28").state,
                         "not listed (streams: (no stream), nginx:1.24, nginx:1.26)")

    def test_stream_only_in_minor_stream_hints_present_for(self):
        # Версия сравнивается точно: 9.2 в вердикт под 9 не попадает.
        doc = csaf(CVE, [("known_affected", EUS92, "nginx::nginx:1.26")])
        self.assertEqual(self.verdict("nginx:1.26", doc=doc).state,
                         "not listed (present for 9.2)")

    def test_real_module_product_id_shape(self):
        # Настоящий вид product_id модульного пакета у Red Hat: platform:
        # NVR-с-эпохой-и-архитектурой::модуль:стрим.
        platform = ("AppStream-9.5.0.Z.MAIN", "cpe:/a:redhat:enterprise_linux:9::appstream")
        component = ("nginx-1:1.24.0-4.module+el9.5.0+22371+ebc8e0cb.x86_64"
                     "::nginx:1.24")
        fixed = pid(platform, component)
        doc = csaf(CVE, [("fixed", platform, component)],
                   remediations=[vendor_fix(fixed)])
        verdict = self.verdict("nginx:1.24", doc=doc)
        self.assertEqual((verdict.state, verdict.fixed_nvr, verdict.advisory_url),
                         ("Fixed",
                          "nginx-1.24.0-4.module+el9.5.0+22371+ebc8e0cb", RHSA))
        self.assertEqual(self.verdict(doc=doc).state, "not listed (streams: nginx:1.24)")


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
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
        download.assert_called_once_with(vex_url(CVE), 30)

    def test_404_means_no_record(self):
        with mock.patch("vulnsheet.vex.download", return_value=None):
            self.assertIsNone(fetch(CVE, VexSettings(cache_dir=self.cache)))

    def test_corrupt_cache_falls_back_to_network(self):
        with open(self.cached(), "w") as handle:
            handle.write("{оборвано")
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
        download.assert_called_once()

    def test_stale_cache_is_refetched(self):
        with open(self.cached(), "w") as handle:
            json.dump({"старый": True}, handle)
        os.utime(self.cached(), (0, 0))
        with mock.patch("vulnsheet.vex.download", return_value=BODY):
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)

    def test_retries_then_gives_up(self):
        with mock.patch("vulnsheet.vex.download", side_effect=OSError("сеть")) as download:
            with self.assertRaises(VexError):
                fetch(CVE)
        self.assertEqual(download.call_count, 3)
        self.assertEqual([c.args for c in self.sleep.call_args_list], [(1,), (2,)])

    def test_retry_recovers(self):
        with mock.patch("vulnsheet.vex.download", side_effect=[OSError("сеть"), BODY]):
            self.assertEqual(fetch(CVE), DOC)

    def test_settings_reach_download_and_retries(self):
        with mock.patch("vulnsheet.vex.download", side_effect=OSError("сеть")) as download:
            with self.assertRaises(VexError):
                fetch(CVE, VexSettings(retries=2, timeout=5))
        self.assertEqual([c.args for c in download.call_args_list],
                         [(vex_url(CVE), 5), (vex_url(CVE), 5)])
        self.assertEqual([c.args for c in self.sleep.call_args_list], [(1,)])

    def test_zero_ttl_never_reads_cache(self):
        settings = VexSettings(cache_dir=self.cache, cache_ttl=0)
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            fetch(CVE, settings)
            fetch(CVE, settings)
        self.assertEqual(download.call_count, 2)


class FetchAllTest(unittest.TestCase):
    def setUp(self):
        mock.patch("vulnsheet.vex.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_indices_failures_and_missing_records(self):
        def download(url, timeout):
            if "1002" in url:
                raise OSError("сеть")
            return BODY if "1000" in url else None

        with mock.patch("vulnsheet.vex.download", side_effect=download) as fake:
            with self.assertLogs("vulnsheet", "WARNING") as caught:
                indices, failures = fetch_all(
                    [CVE, "CVE-2026-1001", "CVE-2026-1002", CVE], VexSettings(jobs=2))
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
                fetch_all([CVE], VexSettings(cache_dir=cache))
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
