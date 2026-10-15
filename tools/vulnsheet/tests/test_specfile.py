import unittest

from vulnsheet.specfile import Mention, changelog_mentions, patch_mentions

SPEC = """\
Name:           nginx
Version:        1.26.3
Release:        2%{?dist}
Source0:        nginx-%{version}.tar.gz
Patch0:         nginx-1.26-distsuffix.patch
Patch12:        nginx-CVE-2026-12345.patch
patch13 :       %{name}-cve-2026-1111-2222.patch
Patch:          nginx-CVE-2026-12345-part2.patch
# Patch99: nginx-CVE-2026-9999.patch — закомментировано

%description
CVE-2026-7777 в описании не считается.

%changelog
* Mon Jan 05 2026 Иван Иванов <ivan@example.com> - 1.26.3-2
- Fix CVE-2026-12345 (rhbz#1)
- Fix CVE-2026-3333

* Fri Dec 12 2025 Пётр Петров <petr@example.com> - 1.26.3-1
- Earlier fix for CVE-2026-12345
- Fix cve-2025-4444-5555
* Thu Dec 11 2025 Без Версии <x@example.com>
- CVE-2025-6666
"""


class PatchMentionsTest(unittest.TestCase):
    def test_patch_lines_with_cve_in_the_value(self):
        got = patch_mentions(SPEC)
        self.assertEqual(got["CVE-2026-12345"], [
            Mention(6, "Patch12: nginx-CVE-2026-12345.patch"),
            Mention(8, "Patch: nginx-CVE-2026-12345-part2.patch")])
        self.assertEqual(got["CVE-2026-1111"], [Mention(7, "patch13: %{name}-cve-2026-1111-2222.patch")])
        self.assertEqual(got["CVE-2026-2222"], got["CVE-2026-1111"])

    def test_comments_description_and_patches_without_cve_are_ignored(self):
        got = patch_mentions(SPEC)
        self.assertEqual(set(got), {"CVE-2026-12345", "CVE-2026-1111", "CVE-2026-2222"})

    def test_separator_in_the_value_does_not_break_the_comment_cell(self):
        got = patch_mentions("Patch1: a-CVE-2026-1234.patch; b.patch\n")
        self.assertEqual(got["CVE-2026-1234"], [Mention(1, "Patch1: a-CVE-2026-1234.patch, b.patch")])


class ChangelogMentionsTest(unittest.TestCase):
    def test_newest_mention_with_the_version_of_its_entry(self):
        got = changelog_mentions(SPEC)
        self.assertEqual(got["CVE-2026-12345"], Mention(16, "1.26.3-2"))
        self.assertEqual(got["CVE-2026-3333"], Mention(17, "1.26.3-2"))
        self.assertEqual(got["CVE-2025-4444"], Mention(21, "1.26.3-1"))
        self.assertEqual(got["CVE-2025-5555"], Mention(21, "1.26.3-1"))

    def test_entry_without_a_version(self):
        self.assertEqual(changelog_mentions(SPEC)["CVE-2025-6666"], Mention(23, None))

    def test_only_the_changelog_section_counts(self):
        got = changelog_mentions(SPEC)
        self.assertNotIn("CVE-2026-7777", got)
        self.assertNotIn("CVE-2026-1111", got)

    def test_spec_without_changelog(self):
        self.assertEqual(changelog_mentions("Name: x\nPatch1: CVE-2026-1234.patch\n"), {})

    def test_version_with_epoch(self):
        got = changelog_mentions("%changelog\n* Mon Jan 05 2026 A <a@b> - 1:2.0-3\n- CVE-2026-1234\n")
        self.assertEqual(got["CVE-2026-1234"], Mention(3, "1:2.0-3"))


if __name__ == "__main__":
    unittest.main()
