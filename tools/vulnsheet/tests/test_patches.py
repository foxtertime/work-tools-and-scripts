import logging
import unittest

from tests.fakes import FakeTransport, Response
from vulnsheet.gitlabclient import GitlabClient, GitlabHost
from vulnsheet.patches import (BRANCH_ONLY, FAILED, FOUND, NO_DIR, NO_SOURCE, READ, REMOVED,
                               SRPM, PatchNote, cves_of, find)

HOSTS = {"gitlab.example.com": GitlabHost(api="https://gitlab.example.com/api/v4",
                                          web="https://gitlab.example.com")}
TREE_URL = "https://gitlab.example.com/api/v4/projects/g%2Fvim/repository/tree"
COMMITS_URL = "https://gitlab.example.com/api/v4/projects/g%2Fvim/repository/commits/"
BRANCH_URL = "git+https://gitlab.example.com/g/vim.git#sl9"
SHA = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
KOJI_SOURCE = "git+ssh://git@gitlab.example.com/g/vim#" + SHA
CVE = "CVE-2024-1234"
FILE = "PATCH/vim-CVE-2024-1234.patch"


def tree(*paths):
    return Response(200, [{"type": "blob", "path": p} for p in paths], {})


NOT_FOUND = Response(404, {"message": "404 Tree Not Found"}, {})


def at(ref, url=TREE_URL):
    """Ключ маршрута FakeTransport: дерево каталога PATCH на ref."""
    return (url, (("path", "PATCH"), ("per_page", "100"),
                  ("recursive", "true"), ("ref", ref)))


def blob(ref, path=FILE, project="g/vim"):
    return "https://gitlab.example.com/%s/-/blob/%s/%s" % (project, ref, path)


def info(original_url=BRANCH_URL, source=None):
    extra = {"source": {"original_url": original_url}} if original_url else {}
    return {"nvr": "vim-8.2-1.sl9", "extra": extra, "source": source}


def client(routes, **kwargs):
    transport = FakeTransport(routes)
    return GitlabClient(HOSTS, token=None, transport=transport,
                        sleeper=lambda _s: None, retries=1, **kwargs), transport


class CvesOfTest(unittest.TestCase):
    def test_ids_from_file_names_in_upper_case(self):
        self.assertEqual(cves_of("PATCH/vim-cve-2024-1234.patch"), ["CVE-2024-1234"])

    def test_a_longer_id_is_not_a_shorter_one(self):
        # CVE-2024-12345 — другая уязвимость, а не CVE-2024-1234 с хвостом
        self.assertEqual(cves_of("PATCH/CVE-2024-12345.patch"), ["CVE-2024-12345"])

    def test_directory_names_count_too(self):
        self.assertEqual(cves_of("PATCH/CVE-2024-1234/fix.patch"), ["CVE-2024-1234"])

    def test_each_id_with_its_own_prefix(self):
        self.assertEqual(cves_of("PATCH/cve-2025-1111-cve-2026-2222.patch"),
                         ["CVE-2025-1111", "CVE-2026-2222"])

    def test_following_numbers_are_ids_of_the_same_year(self):
        self.assertEqual(cves_of("PATCH/nginx-1.26-cve-2026-12345-67890.patch.new"),
                         ["CVE-2026-12345", "CVE-2026-67890"])
        self.assertEqual(cves_of("PATCH/cve-2026-12345-67890-11111.patch"),
                         ["CVE-2026-12345", "CVE-2026-67890", "CVE-2026-11111"])

    def test_short_tail_is_not_an_id(self):
        self.assertEqual(cves_of("PATCH/nginx-1.26-cve-2026-12345-1.patch"),
                         ["CVE-2026-12345"])

    def test_eight_digits_look_like_a_date_not_an_id(self):
        self.assertEqual(cves_of("PATCH/cve-2026-12345-20260115.patch"), ["CVE-2026-12345"])

    def test_repeats_are_dropped(self):
        self.assertEqual(cves_of("PATCH/CVE-2024-1234/CVE-2024-1234.patch"), ["CVE-2024-1234"])


class FindTest(unittest.TestCase):
    def find_vim(self, routes, build=None, **kwargs):
        cli, transport = client(routes, **kwargs)
        got = find({"vim": build or info(source=KOJI_SOURCE)}, cli)
        return got, transport

    def test_patch_in_build_and_branch_links_to_the_branch(self):
        got, transport = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(FILE)})
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(FOUND, "sl9", (blob("sl9"),))}})
        self.assertEqual(got.failed, ())
        self.assertEqual([r[1]["ref"] for r in transport.requests], [SHA, "sl9"])

    def test_patch_gone_from_the_branch_links_to_the_build_commit(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree("PATCH/other.patch")})
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(REMOVED, "sl9", (blob(SHA),))}})

    def test_branch_without_patch_dir_means_the_patch_was_removed(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): NOT_FOUND,
                                COMMITS_URL + "sl9": Response(200, {"id": "f00"}, {})})
        self.assertEqual(got.notes["vim"][CVE].kind, REMOVED)

    def test_patch_only_in_the_branch_is_not_built_yet(self):
        got, _ = self.find_vim({at(SHA): tree(), at("sl9"): tree(FILE)})
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(BRANCH_ONLY, "sl9",
                                                            (blob("sl9"),))}})

    def test_patch_only_in_the_branch_while_build_has_no_patch_dir(self):
        got, _ = self.find_vim({at(SHA): NOT_FOUND,
                                COMMITS_URL + SHA: Response(200, {"id": SHA}, {}),
                                at("sl9"): tree(FILE)})
        self.assertEqual(got.notes["vim"][CVE].kind, BRANCH_ONLY)
        self.assertEqual(dict(got.kinds), {NO_DIR: 1})

    def test_renamed_file_is_matched_by_cve_not_by_path(self):
        renamed = "PATCH/vim-9-CVE-2024-1234.patch"
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(renamed)})
        self.assertEqual(got.notes["vim"][CVE],
                         PatchNote(FOUND, "sl9", (blob("sl9", renamed),)))

    def test_every_file_of_a_cve_is_linked(self):
        second = "PATCH/vim-CVE-2024-1234-part2.patch"
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(second, FILE)})
        self.assertEqual(got.notes["vim"][CVE].urls, (blob("sl9", second), blob("sl9")))

    def test_one_file_for_two_cves_links_both(self):
        both = "PATCH/vim-cve-2024-1234-5678.patch"
        got, _ = self.find_vim({at(SHA): tree(both), at("sl9"): tree(both)})
        self.assertEqual(set(got.notes["vim"]), {CVE, "CVE-2024-5678"})
        self.assertEqual(got.notes["vim"]["CVE-2024-5678"].urls, (blob("sl9", both),))

    def test_build_from_a_commit_has_no_branch_to_compare(self):
        got, transport = self.find_vim(
            {at(SHA): tree(FILE)}, info("git+https://gitlab.example.com/g/vim.git#" + SHA))
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(FOUND, None, (blob(SHA),))}})
        self.assertEqual(len(transport.requests), 1)

    def test_without_a_commit_only_the_branch_is_read(self):
        got, transport = self.find_vim({at("sl9"): tree(FILE)}, info())
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(FOUND, "sl9", (blob("sl9"),))}})
        self.assertEqual([r[1]["ref"] for r in transport.requests], ["sl9"])

    def test_commit_of_another_project_is_not_taken(self):
        # верхний source указывает в другой репозиторий: чужой коммит хуже,
        # чем никакого, — читается только ветка
        got, transport = self.find_vim(
            {at("sl9"): tree()},
            info(source="git+ssh://git@gitlab.example.com/other/vim#" + SHA))
        self.assertEqual([r[1]["ref"] for r in transport.requests], ["sl9"])

    def test_gone_commit_falls_back_to_the_branch_with_a_warning(self):
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim({
                at(SHA): NOT_FOUND,
                COMMITS_URL + SHA: Response(404, {"message": "404 Commit Not Found"}, {}),
                at("sl9"): tree(FILE)})
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(FOUND, "sl9", (blob("sl9"),))}})
        self.assertEqual(got.failed, ())
        self.assertIn("с ветки", "\n".join(caught.output))

    def test_gone_commit_without_a_branch_is_a_failure(self):
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got, _ = self.find_vim(
                {at(SHA): NOT_FOUND,
                 COMMITS_URL + SHA: Response(404, {"message": "404 Commit Not Found"}, {})},
                info("git+https://gitlab.example.com/g/vim.git#" + SHA))
        self.assertEqual((got.notes, got.failed), ({}, ("vim",)))

    def test_failed_branch_read_keeps_the_build_patch_and_is_a_failure(self):
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim({at(SHA): tree(FILE),
                                    at("sl9"): Response(500, {"message": "boom"}, {})})
        self.assertEqual(got.notes, {"vim": {CVE: PatchNote(FOUND, None, (blob(SHA),))}})
        self.assertEqual(got.failed, ("vim",))
        self.assertEqual(dict(got.kinds), {FAILED: 1})
        line = "\n".join(caught.output)
        self.assertIn("vim", line)
        self.assertIn("ветк", line)

    def test_failed_build_read_is_a_failure_named_in_the_log(self):
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, transport = self.find_vim({at(SHA): Response(500, {"message": "boom"}, {})})
        self.assertEqual((got.notes, got.failed), ({}, ("vim",)))
        self.assertIn("500", "\n".join(caught.output))
        self.assertEqual(len(transport.requests), 1)

    def test_substituted_host_is_read_warned_about_and_linked_to_the_answering_server(self):
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim({at("sl9"): tree(FILE)},
                                   info("git+https://mirror.example.com/g/vim.git#sl9"),
                                   default_host="gitlab.example.com")
        self.assertEqual(got.notes["vim"][CVE].urls, (blob("sl9"),))
        self.assertEqual(got.failed, ())
        self.assertIn("не описан в конфиге", "\n".join(caught.output))

    def test_build_without_details_is_a_failure(self):
        cli, transport = client({})
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got = find({"vim": None}, cli)
        self.assertEqual(got.failed, ("vim",))
        self.assertEqual(transport.requests, [])

    def test_unparsable_source_url_is_a_failure(self):
        cli, transport = client({})
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got = find({"vim": info("gitlab.example.com/g/vim")}, cli)
        self.assertEqual(got.failed, ("vim",))
        self.assertEqual(transport.requests, [])

    def test_no_source_and_srpm_are_skipped_not_failed(self):
        cli, transport = client({})
        got = find({"vim": info(original_url=None),
                    "bash": info("cli-build/1699999999.9/bash-5.1-1.sl9.src.rpm")}, cli)
        self.assertEqual((got.notes, got.failed), ({}, ()))
        self.assertEqual(dict(got.kinds), {NO_SOURCE: 1, SRPM: 1})
        self.assertEqual(transport.requests, [])

    def test_read_components_are_counted(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(FILE)})
        self.assertEqual(dict(got.kinds), {READ: 1})

    def test_summary_is_left_to_the_caller(self):
        # итог по патчам пишет cli в конце прогона, не в его середине;
        # assertNoLogs — только с Python 3.10, маркер держит assertLogs довольным
        cli, _ = client({at("sl9"): tree(FILE)})
        with self.assertLogs("vulnsheet.patches", "INFO") as caught:
            find({"vim": info()}, cli)
            logging.getLogger("vulnsheet.patches").info("маркер")
        self.assertEqual(caught.output, ["INFO:vulnsheet.patches:маркер"])

    def test_components_are_checked_in_parallel_and_all_come_back(self):
        routes, builds = {}, {}
        for n in range(20):
            name = "pkg%d" % n
            url = "https://gitlab.example.com/api/v4/projects/g%%2F%s/repository/tree" % name
            routes[url] = tree("PATCH/CVE-2024-%04d.patch" % (1000 + n))
            builds[name] = info("git+https://gitlab.example.com/g/%s.git#sl9" % name)
        cli, _ = client(routes)
        got = find(builds, cli, jobs=4)
        self.assertEqual({name: set(notes) for name, notes in got.notes.items()},
                         {"pkg%d" % n: {"CVE-2024-%04d" % (1000 + n)} for n in range(20)})


if __name__ == "__main__":
    unittest.main()
