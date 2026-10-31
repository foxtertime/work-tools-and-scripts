import unittest

from patchaudit.vex import build_index, fixed_releases
from tests.fakes import APPSTREAM96, EUS92, RHEL9, csaf, pid


class FixedReleasesTest(unittest.TestCase):
    def test_shared_nvr_keeps_all_products_and_unversioned_fixed_product_is_visible(self):
        doc = csaf("CVE-2026-1000", [
            ("fixed", APPSTREAM96, "vim-2:8.2-9.el9.x86_64"),
            ("fixed", APPSTREAM96, "vim-2:8.2-9.el9.aarch64"),
            ("fixed", RHEL9, "vim")])
        result = fixed_releases(build_index(doc), "vim", "9")
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]["products"]), 2)
        self.assertIsNone(result[1]["nvr"])

    def test_all_fixed_versions_with_their_own_date_and_errata(self):
        versions = ["vim-2:8.2-9.el9.x86_64", "vim-2:8.2-11.el9.x86_64"]
        statuses = [("fixed", APPSTREAM96, v) for v in versions]
        statuses.append(("fixed", EUS92, "vim-2:8.2-1.el9_2.x86_64"))
        remedies = [{"category": "vendor_fix", "product_ids": [pid(APPSTREAM96, v)],
                     "date": date, "url": url} for v, date, url in
                    zip(versions, ("2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"),
                        ("https://example.org/old", "https://example.org/new"))]
        result = fixed_releases(build_index(csaf("CVE-2026-1000", statuses, remediations=remedies)), "vim", "9")
        self.assertEqual([f["nvr"] for f in result], ["vim-8.2-9.el9", "vim-8.2-11.el9"])
        self.assertEqual([f["fix_date"] for f in result], ["2026-09-01", "2026-10-01"])
        self.assertEqual([f["advisory_url"] for f in result], ["https://example.org/old", "https://example.org/new"])

    def test_streams_aliases_and_absent_document(self):
        doc = csaf("CVE-2026-1000", [("fixed", RHEL9, "afterburn-0:5.1-2.el9.x86_64"),
                                    ("fixed", RHEL9, "afterburn-0:5.2-1.el9.x86_64::afterburn:5")])
        index = build_index(doc)
        self.assertEqual(fixed_releases(index, "rust-afterburn", "9"), [])
        self.assertEqual(len(fixed_releases(index, "rust-afterburn", "9", aliases=("afterburn",))), 1)
        self.assertEqual(fixed_releases(index, "afterburn", "9", "afterburn:5")[0]["nvr"], "afterburn-5.2-1.el9")
        self.assertEqual(fixed_releases(None, "afterburn", "9"), [])

    def test_multiple_advisories_for_one_product_keep_earliest_fix_date(self):
        version = "vim-0:8.2-9.el9.x86_64"
        remedies = [{"category": "vendor_fix", "product_ids": [pid(APPSTREAM96, version)],
                     "date": date, "url": "https://example.org/" + date}
                    for date in ("2026-10-01", "2026-09-01")]
        result = fixed_releases(build_index(csaf("CVE-2026-1000", [("fixed", APPSTREAM96, version)],
                                                 remediations=remedies)), "vim", "9")
        self.assertEqual(result[0]["fix_date"], "2026-09-01")
