import unittest

from patchaudit.decisions import classify, compare_target, parse_nvr, patch_action


def fix(nvr):
    return {"nvr": nvr, "fix_date": "2026-10-01", "advisory_url": "https://example.org/errata"}


class DecisionsTest(unittest.TestCase):
    def test_name_with_hyphens_and_rpm_release(self):
        nvr = parse_nvr("python-requests-2.31.0-5.el9_6.2")
        self.assertEqual((nvr.name, nvr.version, nvr.release),
                         ("python-requests", "2.31.0", "5.el9_6.2"))

    def test_bad_nvr_is_rejected(self):
        for value in ("vim", "vim--1", "-1-2", "vim-1-", "vim-1:2-3", "vim-1-2.src.rpm", "vim-1-2 x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_nvr(value)

    def test_backport_and_numeric_release(self):
        self.assertEqual(compare_target("vim-8.2-10.el9", "vim-8.2-9.el9"), 1)
        self.assertEqual(compare_target("vim-8.2-9.el9", "vim-8.2-9.el9"), 0)
        self.assertEqual(compare_target("vim-8.2-8.el9", "vim-8.2-9.el9"), -1)
        self.assertEqual(compare_target("vim-8.2~rc1-10.el9", "vim-8.2-9.el9"), -1)

    def test_disttag_does_not_make_foreign_release_newer(self):
        self.assertIsNone(compare_target("vim-8.2-9.el10", "vim-8.2-9.el9"))
        self.assertIsNone(compare_target("vim-8.2-9.custom", "vim-8.2-9.el9"))
        self.assertIsNone(compare_target("vim-8.2-9.el9fdp", "vim-8.2-9.el9"))
        self.assertIsNone(compare_target("vim-8.2-9.el9.custom", "vim-8.2-9.el9"))

    def test_sl_release_and_numeric_rebuild_suffix_compare_as_redhat_release(self):
        for target, fixed, expected in (
                ("vim-8.2-9.sl9", "vim-8.2-9.el9", 0),
                ("vim-8.2-9.sl9_6.2^1", "vim-8.2-9.el9_6.2", 0),
                ("vim-8.2-9.sl9_6.2^123456", "vim-8.2-9.el9_6.2", 0),
                ("vim-8.2-9.el9_6.2^42", "vim-8.2-9.el9_6.2", 0),
                ("vim-8.2-8.sl9^999", "vim-8.2-9.el9", -1),
                ("vim-8.2-10.sl9^0", "vim-8.2-9.el9", 1)):
            with self.subTest(target=target):
                self.assertEqual(compare_target(target, fixed), expected)

    def test_sl_normalization_keeps_version_and_does_not_hide_unknown_release(self):
        self.assertEqual(compare_target("sl-tools-8.2^1-9.sl9^2", "sl-tools-8.2-9.el9"), 1)
        for release in ("9.sl10^1", "9.sl9.custom^1", "9.sl9fdp^1", "9.sl9^beta", "9.sl9^1.extra"):
            with self.subTest(release=release):
                self.assertIsNone(compare_target("vim-8.2-" + release, "vim-8.2-9.el9"))

    def test_sl_module_release_with_rebuild_suffix(self):
        fixed = "nginx-1.24.0-4.module+el9.5.0+22371+ebc8e0cb"
        self.assertEqual(compare_target("nginx-1.24.0-4.module+sl9.5.0+22371+ebc8e0cb^12", fixed), 0)
        self.assertEqual(compare_target("nginx-1.24.0-4.module_sl9.5.0+22371+ebc8e0cb^12",
                                        "nginx-1.24.0-4.module_el9.5.0+22371+ebc8e0cb"), 0)

    def test_module_release_is_comparable_only_to_same_family(self):
        fixed = "nginx-1.24.0-4.module+el9.5.0+22371+ebc8e0cb"
        self.assertEqual(compare_target(fixed, fixed), 0)
        self.assertEqual(compare_target("nginx-1.24.0-5.module+el9.6.0+23371+abc123ef", fixed), 1)
        self.assertIsNone(compare_target("nginx-1.24.0-5.el9", fixed))

    def test_newer_upstream_version(self):
        self.assertEqual(compare_target("vim-9.0-1.el9", "vim-8.2-9.el9"), 1)

    def test_package_mode_records_fixed_without_target(self):
        result = classify("Fixed", [fix("vim-8.2-9.el9")], None)
        self.assertEqual(result["action"], "fixed")

    def test_nvr_mode_separates_fixed_now_and_after_upgrade(self):
        fixes = [fix("vim-8.2-9.el9"), fix("vim-8.2-11.el9")]
        result = classify("Fixed", fixes, "vim-8.2-9.el9")
        self.assertEqual(result["action"], "remove")
        self.assertEqual(result["fixed_in_target"], fixes[:1])
        self.assertEqual(result["fixed_after_target"], fixes[1:])
        self.assertEqual(classify("Fixed", fixes, "vim-8.2-8.el9")["action"], "remove_on_upgrade")

    def test_uncertain_data_never_suggests_removal(self):
        for state in ("Not affected", "not listed", "not listed (streams: nginx:1.24)",
                      "no VEX record", "fetch error"):
            self.assertEqual(classify(state, [], None)["action"], "review")
        self.assertEqual(classify("Fixed", [], "vim-8.2-9.el9")["action"], "review")
        self.assertEqual(classify("Fixed", [fix("vim-8.2-9.el9")], "vim-8.2-9.custom")["action"], "review")

    def test_unfixed_states_keep_patch(self):
        for state in ("Affected", "Will not fix", "Fix deferred", "Under investigation", "Out of support scope"):
            self.assertEqual(classify(state, [], None)["action"], "keep")

    def test_all_product_groups_must_be_covered_but_historical_fixes_are_alternatives(self):
        fixes = [dict(fix("vim-enhanced-8.2-9.el9"), products=["appstream-enhanced"]),
                 dict(fix("vim-enhanced-8.2-12.el9"), products=["appstream-enhanced"]),
                 dict(fix("vim-minimal-8.2-11.el9"), products=["baseos-minimal"])]
        self.assertEqual(classify("Fixed", fixes, "vim-8.2-9.el9")["action"], "remove_on_upgrade")
        self.assertEqual(classify("Fixed", fixes, "vim-8.2-11.el9")["action"], "remove")
        fixes.append({"nvr": None, "products": ["unknown-fixed-version"]})
        self.assertEqual(classify("Fixed", fixes, "vim-8.2-11.el9")["action"], "review")
        self.assertEqual(classify("Fixed", fixes, None)["action"], "review")

    def test_multicve_patch_requires_every_cve_fixed(self):
        for actions, expected in [(["remove", "remove"], "remove"),
                                  (["fixed", "fixed"], "fixed"),
                                  (["remove", "remove_on_upgrade"], "remove_on_upgrade"),
                                  (["remove", "review"], "review"),
                                  (["remove", "keep"], "keep"),
                                  (["review", "keep"], "keep")]:
            self.assertEqual(patch_action(actions), expected)
