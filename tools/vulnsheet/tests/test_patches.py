import base64
import logging
import unittest

from tests.fakes import FakeTransport, Response
from vulnsheet.gitlabclient import GitlabClient, GitlabHost
from vulnsheet.patches import (BRANCH_ONLY, FAILED, FOUND, NO_DIR, NO_SOURCE, READ, REMOVED,
                               SPEC_MANY, SPEC_NONE, SPEC_READ, SRC_CHANGELOG, SRC_PATCH,
                               SRC_SPEC, SRPM, Item, PatchNote, cves_of, find)

HOSTS = {"gitlab.example.com": GitlabHost(api="https://gitlab.example.com/api/v4",
                                          web="https://gitlab.example.com")}
API = "https://gitlab.example.com/api/v4/projects/g%2Fvim/repository/"
TREE_URL = API + "tree"
COMMITS_URL = API + "commits/"
SPEC_URL = API + "files/SPECS%2Fvim.spec"
BRANCH_URL = "git+https://gitlab.example.com/g/vim.git#sl9"
SHA = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
KOJI_SOURCE = "git+ssh://git@gitlab.example.com/g/vim#" + SHA
CVE = "CVE-2024-1234"
FILE = "PATCH/vim-CVE-2024-1234.patch"
SPEC = """\
Name: vim
Patch1: vim-CVE-2024-1234.patch

%changelog
* Mon Jan 05 2026 A <a@example.com> - 9.0-2
- Fix CVE-2024-1234
"""


def tree(*paths):
    return Response(200, [{"type": "blob", "path": p} for p in paths], {})


NOT_FOUND = Response(404, {"message": "404 Tree Not Found"}, {})


def at(ref, path="PATCH"):
    """Ключ маршрута FakeTransport: дерево каталога path на ref."""
    return (TREE_URL, (("path", path), ("per_page", "100"),
                       ("recursive", "true"), ("ref", ref)))


def spec_file(text):
    return Response(200, {"encoding": "base64",
                          "content": base64.b64encode(text.encode()).decode()}, {})


def with_spec(ref, text=SPEC, name="vim.spec"):
    """Маршруты: в SPECS на ref лежит спек с таким текстом."""
    return {at(ref, "SPECS"): tree("SPECS/" + name),
            (API + "files/SPECS%2F" + name, (("ref", ref),)): spec_file(text)}


def blob(ref, path=FILE, line=None):
    url = "https://gitlab.example.com/g/vim/-/blob/%s/%s" % (ref, path)
    return url + "#L%d" % line if line else url


def note(kind, branch, *urls):
    """Пометка по каталогу PATCH: у файлов подписи нет."""
    return PatchNote(kind, branch, tuple(Item(None, url) for url in urls))


def info(original_url=BRANCH_URL, source=None):
    extra = {"source": {"original_url": original_url}} if original_url else {}
    return {"nvr": "vim-8.2-1.sl9", "extra": extra, "source": source}


def client(routes, **kwargs):
    # по умолчанию каталог SPECS пуст: спека нет, и тесты PATCH о нём не думают
    defaults = {at(ref, "SPECS"): tree() for ref in (SHA, "sl9")}
    transport = FakeTransport({**defaults, **routes})
    return GitlabClient(HOSTS, token=None, transport=transport,
                        sleeper=lambda _s: None, retries=1, **kwargs), transport


def patch_refs(transport):
    return [r[1]["ref"] for r in transport.requests if r[1].get("path") == "PATCH"]


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


class FindCase(unittest.TestCase):
    def find_vim(self, routes, build=None, **kwargs):
        cli, transport = client(routes, **kwargs)
        got = find({"vim": build or info(source=KOJI_SOURCE)}, cli)
        return got, transport

    @staticmethod
    def patch(got, cve=CVE):
        return got.notes["vim"][cve][SRC_PATCH]


class PatchDirTest(FindCase):
    def test_patch_in_build_and_branch_links_to_the_branch(self):
        got, transport = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(FILE)})
        self.assertEqual(got.notes, {"vim": {CVE: {SRC_PATCH: note(FOUND, "sl9", blob("sl9"))}}})
        self.assertEqual(got.failed, ())
        self.assertEqual(patch_refs(transport), [SHA, "sl9"])

    def test_patch_gone_from_the_branch_links_to_the_build_commit(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree("PATCH/other.patch")})
        self.assertEqual(self.patch(got), note(REMOVED, "sl9", blob(SHA)))

    def test_branch_without_patch_dir_means_the_patch_was_removed(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): NOT_FOUND,
                                COMMITS_URL + "sl9": Response(200, {"id": "f00"}, {})})
        self.assertEqual(self.patch(got).kind, REMOVED)

    def test_patch_only_in_the_branch_is_not_built_yet(self):
        got, _ = self.find_vim({at(SHA): tree(), at("sl9"): tree(FILE)})
        self.assertEqual(self.patch(got), note(BRANCH_ONLY, "sl9", blob("sl9")))

    def test_patch_only_in_the_branch_while_build_has_no_patch_dir(self):
        got, _ = self.find_vim({at(SHA): NOT_FOUND,
                                COMMITS_URL + SHA: Response(200, {"id": SHA}, {}),
                                at("sl9"): tree(FILE)})
        self.assertEqual(self.patch(got).kind, BRANCH_ONLY)
        self.assertEqual(dict(got.kinds), {NO_DIR: 1})

    def test_renamed_file_is_matched_by_cve_not_by_path(self):
        renamed = "PATCH/vim-9-CVE-2024-1234.patch"
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(renamed)})
        self.assertEqual(self.patch(got), note(FOUND, "sl9", blob("sl9", renamed)))

    def test_every_file_of_a_cve_is_linked(self):
        second = "PATCH/vim-CVE-2024-1234-part2.patch"
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(second, FILE)})
        self.assertEqual(self.patch(got), note(FOUND, "sl9", blob("sl9", second), blob("sl9")))

    def test_one_file_for_two_cves_links_both(self):
        both = "PATCH/vim-cve-2024-1234-5678.patch"
        got, _ = self.find_vim({at(SHA): tree(both), at("sl9"): tree(both)})
        self.assertEqual(set(got.notes["vim"]), {CVE, "CVE-2024-5678"})
        self.assertEqual(self.patch(got, "CVE-2024-5678"), note(FOUND, "sl9", blob("sl9", both)))

    def test_build_from_a_commit_has_no_branch_to_compare(self):
        got, transport = self.find_vim(
            {at(SHA): tree(FILE)}, info("git+https://gitlab.example.com/g/vim.git#" + SHA))
        self.assertEqual(self.patch(got), note(FOUND, None, blob(SHA)))
        self.assertEqual(patch_refs(transport), [SHA])

    def test_without_a_commit_only_the_branch_is_read(self):
        got, transport = self.find_vim({at("sl9"): tree(FILE)}, info())
        self.assertEqual(self.patch(got), note(FOUND, "sl9", blob("sl9")))
        self.assertEqual(patch_refs(transport), ["sl9"])

    def test_commit_of_another_project_is_not_taken(self):
        # верхний source указывает в другой репозиторий: чужой коммит хуже,
        # чем никакого, — читается только ветка
        got, transport = self.find_vim(
            {at("sl9"): tree()},
            info(source="git+ssh://git@gitlab.example.com/other/vim#" + SHA))
        self.assertEqual(patch_refs(transport), ["sl9"])

    def test_gone_commit_falls_back_to_the_branch_with_a_warning(self):
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim({
                at(SHA): NOT_FOUND,
                COMMITS_URL + SHA: Response(404, {"message": "404 Commit Not Found"}, {}),
                at("sl9"): tree(FILE)})
        self.assertEqual(self.patch(got), note(FOUND, "sl9", blob("sl9")))
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
        self.assertEqual(self.patch(got), note(FOUND, None, blob(SHA)))
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
        self.assertEqual(self.patch(got).items, (Item(None, blob("sl9")),))
        self.assertEqual(got.failed, ())
        self.assertIn("не описан в конфиге", "\n".join(caught.output))


class SpecTest(FindCase):
    def test_spec_mentions_in_build_and_branch(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec(SHA))
        routes.update(with_spec("sl9"))
        got, _ = self.find_vim(routes)
        spec = "SPECS/vim.spec"
        self.assertEqual(got.notes["vim"][CVE], {
            SRC_SPEC: PatchNote(FOUND, "sl9", (Item("Patch1: vim-CVE-2024-1234.patch",
                                                    blob("sl9", spec, 2)),)),
            SRC_CHANGELOG: PatchNote(FOUND, "sl9", (Item("9.0-2", blob("sl9", spec, 6)),)),
        })
        self.assertEqual(dict(got.spec_kinds), {SPEC_READ: 1})

    def test_patch_line_dropped_from_the_branch_spec(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec(SHA))
        routes.update(with_spec("sl9", SPEC.replace("Patch1: vim-CVE-2024-1234.patch\n", "")))
        got, _ = self.find_vim(routes)
        notes = got.notes["vim"][CVE]
        self.assertEqual(notes[SRC_SPEC], PatchNote(REMOVED, "sl9", (
            Item("Patch1: vim-CVE-2024-1234.patch", blob(SHA, "SPECS/vim.spec", 2)),)))
        self.assertEqual(notes[SRC_CHANGELOG].kind, FOUND)

    def test_changelog_entry_only_in_the_branch(self):
        newer = SPEC.replace("%changelog\n", "%changelog\n* Tue Jan 06 2026 A <a@b> - 9.0-3\n"
                                             "- Fix CVE-2024-9999\n\n")
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec(SHA))
        routes.update(with_spec("sl9", newer))
        got, _ = self.find_vim(routes)
        self.assertEqual(got.notes["vim"]["CVE-2024-9999"], {SRC_CHANGELOG: PatchNote(
            BRANCH_ONLY, "sl9", (Item("9.0-3", blob("sl9", "SPECS/vim.spec", 6)),))})

    def test_all_sources_together(self):
        routes = {at(SHA): tree(FILE), at("sl9"): tree(FILE)}
        routes.update(with_spec(SHA))
        routes.update(with_spec("sl9"))
        got, _ = self.find_vim(routes)
        self.assertEqual(list(got.notes["vim"][CVE]), [SRC_PATCH, SRC_SPEC, SRC_CHANGELOG])

    def test_spec_of_another_name_is_taken_when_it_is_the_only_one(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec(SHA, name="vim-enhanced.spec"))
        routes.update(with_spec("sl9", name="vim-enhanced.spec"))
        got, _ = self.find_vim(routes)
        self.assertEqual(got.notes["vim"][CVE][SRC_SPEC].items[0].url,
                         blob("sl9", "SPECS/vim-enhanced.spec", 2))

    def test_several_specs_take_the_package_one(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        for ref in (SHA, "sl9"):
            routes.update(with_spec(ref))
            routes[at(ref, "SPECS")] = tree("SPECS/other.spec", "SPECS/vim.spec")
        got, _ = self.find_vim(routes)
        self.assertIn(SRC_SPEC, got.notes["vim"][CVE])

    def test_several_specs_without_the_package_one_are_not_chosen(self):
        routes = {at(SHA): tree(FILE), at("sl9"): tree(FILE)}
        for ref in (SHA, "sl9"):
            routes[at(ref, "SPECS")] = tree("SPECS/a.spec", "SPECS/b.spec")
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim(routes)
        self.assertEqual(list(got.notes["vim"][CVE]), [SRC_PATCH])
        self.assertEqual((got.failed, dict(got.spec_kinds)), ((), {SPEC_MANY: 1}))
        self.assertIn("SPECS/a.spec, SPECS/b.spec", "\n".join(caught.output))

    def test_spec_appearing_only_in_the_branch_is_not_built_yet(self):
        # в билде спека не было — это известно, а не «неизвестно»: всё, что
        # есть в спеке ветки, в билд ещё не попало
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec("sl9"))
        got, _ = self.find_vim(routes)
        self.assertEqual({src: n.kind for src, n in got.notes["vim"][CVE].items()},
                         {SRC_SPEC: BRANCH_ONLY, SRC_CHANGELOG: BRANCH_ONLY})

    def test_specs_in_subdirectories_do_not_count(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        for ref in (SHA, "sl9"):
            routes.update(with_spec(ref, name="vim-enhanced.spec"))
            routes[at(ref, "SPECS")] = tree("SPECS/old/a.spec", "SPECS/vim-enhanced.spec")
        got, _ = self.find_vim(routes)
        self.assertEqual(dict(got.spec_kinds), {SPEC_READ: 1})

    def test_no_specs_dir_is_not_an_error(self):
        got, _ = self.find_vim({
            at(SHA): tree(FILE), at("sl9"): tree(FILE),
            at(SHA, "SPECS"): NOT_FOUND, COMMITS_URL + SHA: Response(200, {"id": SHA}, {}),
            at("sl9", "SPECS"): NOT_FOUND, COMMITS_URL + "sl9": Response(200, {"id": SHA}, {})})
        self.assertEqual((got.failed, dict(got.spec_kinds)), ((), {SPEC_NONE: 1}))
        self.assertEqual(dict(got.kinds), {READ: 1})

    def test_unreadable_spec_is_a_failure_but_patch_dir_is_kept(self):
        routes = {at(SHA): tree(FILE), at("sl9"): tree(FILE)}
        routes.update(with_spec(SHA))
        routes[(SPEC_URL, (("ref", SHA),))] = Response(500, {"message": "boom"}, {})
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got, _ = self.find_vim(routes)
        self.assertEqual(list(got.notes["vim"][CVE]), [SRC_PATCH])
        self.assertEqual(got.failed, ("vim",))
        self.assertIn("спек SPECS/vim.spec", "\n".join(caught.output))

    def test_unreadable_branch_spec_keeps_the_build_spec_unchecked(self):
        routes = {at(SHA): tree(), at("sl9"): tree()}
        routes.update(with_spec(SHA))
        routes.update(with_spec("sl9"))
        routes[(SPEC_URL, (("ref", "sl9"),))] = Response(500, {"message": "boom"}, {})
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got, _ = self.find_vim(routes)
        self.assertEqual(got.notes["vim"][CVE][SRC_SPEC].kind, FOUND)
        self.assertIsNone(got.notes["vim"][CVE][SRC_SPEC].branch)
        self.assertEqual(got.failed, ("vim",))


class OutcomeTest(FindCase):
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
        self.assertEqual(dict(got.spec_kinds), {})
        self.assertEqual(transport.requests, [])

    def test_read_components_are_counted(self):
        got, _ = self.find_vim({at(SHA): tree(FILE), at("sl9"): tree(FILE)})
        self.assertEqual(dict(got.kinds), {READ: 1})
        self.assertEqual(dict(got.spec_kinds), {SPEC_NONE: 1})

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
