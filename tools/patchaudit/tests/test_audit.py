import unittest
from unittest import mock

from patchaudit import audit
from patchaudit.gitlabclient import TreeResult
from patchaudit.vex import VexSettings, vex_url
from tests.fakes import APPSTREAM96, RHEL9, FakeKojiSession, csaf, pid
import json

PACKAGE = "vim"
LATEST = "vim-8.2-7.sl9"
BRANCH = "updates/sl9"
SOURCE = "git+https://git.example.org/rpms/vim.git#" + BRANCH
CVE = "CVE-2026-1000"
OTHER = "CVE-2026-2000"
PATCH = "PATCH/vim-CVE-2026-1000.patch"


def doc(cve=CVE, version="vim-2:8.2-9.el9.x86_64", state="fixed"):
    return csaf(cve, [(state, APPSTREAM96, version)], remediations=[{
        "category": "vendor_fix", "product_ids": [pid(APPSTREAM96, version)],
        "date": "2026-10-01T00:00:00Z", "url": "https://example.org/errata"}])


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.info = {"nvr": LATEST, "extra": {"source": {"original_url": SOURCE}},
                     "source": "git+https://git.example.org/rpms/vim.git#" + "a" * 40}
        self.session = FakeKojiSession(builds={PACKAGE: LATEST}, infos={LATEST: self.info})
        self.client = mock.Mock()
        self.client.patch_dir = "PATCH"
        self.client.patch_files.return_value = TreeResult(True, [PATCH, "PATCH/build.patch"], None)
        self.docs = {vex_url(CVE): doc()}
        self.download = mock.patch("patchaudit.vex.download", side_effect=self._download).start()
        self.addCleanup(mock.patch.stopall)

    def _download(self, url, timeout=None):
        value = self.docs.get(url)
        if isinstance(value, Exception):
            raise value
        return json.dumps(value).encode() if value is not None else None

    def run_audit(self, target=None):
        return audit.run(PACKAGE, target, "sl9", "9", self.session, self.client,
                         VexSettings(retries=1))

    def test_package_mode_reads_branch_not_build_commit(self):
        result = self.run_audit()
        self.assertTrue(result["complete"])
        self.assertEqual(result["source"]["branch"], BRANCH)
        self.assertEqual(result["latest_build"], LATEST)
        self.assertEqual(result["patches"][0]["action"], "fixed")
        self.assertEqual(result["cves"][0]["fixes"][0]["fix_date"], "2026-10-01")
        self.client.patch_files.assert_called_once_with("git.example.org", "rpms/vim", BRANCH)
        self.assertEqual(self.session.build_calls, [LATEST])
        self.assertEqual(result["ignored_files"], ["PATCH/build.patch"])

    def test_target_does_not_have_to_exist_in_koji(self):
        result = self.run_audit("vim-8.2-9.el9")
        self.assertEqual(result["patches"][0]["action"], "remove")
        self.assertEqual(self.session.build_calls, [LATEST])
        self.assertEqual(self.run_audit("vim-8.2-8.el9")["patches"][0]["action"], "remove_on_upgrade")

    def test_multi_cve_file_and_one_fetch_per_cve(self):
        self.client.patch_files.return_value = TreeResult(True, [PATCH, "PATCH/CVE-2026-1000-2000.patch"], None)
        self.docs[vex_url(OTHER)] = csaf(OTHER, [("known_affected", RHEL9, "vim")])
        result = self.run_audit("vim-8.2-9.el9")
        decisions = {p["path"]: p["action"] for p in result["patches"]}
        self.assertEqual(decisions[PATCH], "remove")
        self.assertEqual(decisions["PATCH/CVE-2026-1000-2000.patch"], "keep")
        self.assertEqual(self.download.call_count, 2)

    def test_no_patch_directory_or_no_cves_skips_vex(self):
        for tree in (TreeResult(False, [], None), TreeResult(True, ["PATCH/build.patch"], None)):
            self.client.patch_files.return_value = tree
            result = self.run_audit()
            self.assertTrue(result["complete"])
            self.assertEqual(result["patches"], [])
        self.download.assert_not_called()

    def test_missing_ref_is_not_empty_directory(self):
        self.client.patch_files.return_value = TreeResult(None, [], "gitlab: ref not found")
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertIsNone(result["patch_directory"]["present"])
        self.assertTrue(result["problems"])

    def test_commit_only_srpm_or_missing_source_is_incomplete(self):
        for value in ("git+https://git.example.org/rpms/vim.git#" + "a" * 40,
                      "vim-8.2-7.sl9.src.rpm", None):
            self.info["extra"]["source"]["original_url"] = value
            self.assertFalse(self.run_audit()["complete"])
        self.client.patch_files.assert_not_called()

    def test_fetch_error_keeps_patch_for_review_and_report_partial(self):
        self.docs[vex_url(CVE)] = ConnectionError("VEX unavailable")
        result = self.run_audit("vim-8.2-9.el9")
        self.assertFalse(result["complete"])
        self.assertEqual(result["cves"][0]["status"], "fetch error")
        self.assertEqual(result["patches"][0]["action"], "review")
        self.assertEqual(result["problems"][0]["cve"], CVE)

    def test_no_vex_record_and_not_affected_do_not_recommend_delete(self):
        for value, state in ((None, "no VEX record"),
                             (csaf(CVE, [("known_not_affected", RHEL9, "vim")]), "Not affected")):
            self.docs[vex_url(CVE)] = value
            result = self.run_audit()
            self.assertTrue(result["complete"])
            self.assertEqual(result["cves"][0]["status"], state)
            self.assertEqual(result["patches"][0]["action"], "review")

    def test_no_build_or_no_build_info_is_incomplete(self):
        self.session.builds.clear()
        self.assertFalse(self.run_audit()["complete"])
        self.session.builds[PACKAGE] = LATEST
        self.session.infos.clear()
        self.assertFalse(self.run_audit()["complete"])

    def test_alias_and_stream_are_used_by_verdict_and_fix_listing(self):
        self.docs[vex_url(CVE)] = csaf(CVE, [("fixed", RHEL9, "vim-enhanced-2:8.2-9.el9.x86_64::vim:8")])
        result = audit.run(PACKAGE, "vim-8.2-9.el9", "sl9", "9", self.session, self.client,
                           VexSettings(retries=1), stream="vim:8", aliases=("vim-enhanced",))
        self.assertEqual(result["patches"][0]["action"], "remove")
        self.assertEqual(result["cves"][0]["fixes"][0]["nvr"], "vim-enhanced-8.2-9.el9")

    def test_cve_in_parent_directory_is_not_a_cve_patch(self):
        self.client.patch_files.return_value = TreeResult(True, ["PATCH/CVE-2026-1000/build.patch"], None)
        self.assertEqual(self.run_audit()["patches"], [])
        self.download.assert_not_called()

    def test_wrong_cve_document_and_malformed_status_produce_partial_json(self):
        for value in (doc(cve="CVE-2026-9999"),
                      {"document": {}, "vulnerabilities": [{"cve": CVE, "product_status": None}]}):
            self.docs[vex_url(CVE)] = value
            result = self.run_audit("vim-8.2-9.el9")
            self.assertFalse(result["complete"])
            self.assertEqual(result["patches"][0]["action"], "review")

    def test_different_alias_fixes_do_not_allow_premature_removal(self):
        self.docs[vex_url(CVE)] = csaf(CVE, [
            ("fixed", APPSTREAM96, "vim-enhanced-2:8.2-9.el9.x86_64"),
            ("fixed", RHEL9, "vim-minimal-2:8.2-11.el9.x86_64")])
        result = audit.run(PACKAGE, "vim-8.2-9.el9", "sl9", "9", self.session, self.client,
                           VexSettings(retries=1), aliases=("vim-enhanced", "vim-minimal"))
        self.assertEqual(result["patches"][0]["action"], "remove_on_upgrade")
