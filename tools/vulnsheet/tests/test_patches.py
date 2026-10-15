import logging
import unittest

from tests.fakes import FakeTransport, Response
from vulnsheet.gitlabclient import GitlabClient, GitlabHost
from vulnsheet.patches import FAILED, NO_DIR, NO_SOURCE, READ, SRPM, cves_in, find

HOSTS = {"gitlab.example.com": GitlabHost(api="https://gitlab.example.com/api/v4",
                                          web="https://gitlab.example.com")}
TREE_URL = "https://gitlab.example.com/api/v4/projects/g%2Fvim/repository/tree"
COMMITS_URL = "https://gitlab.example.com/api/v4/projects/g%2Fvim/repository/commits/"
BRANCH_URL = "git+https://gitlab.example.com/g/vim.git#sl9"
SHA = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"


def tree(*paths):
    return Response(200, [{"type": "blob", "path": p} for p in paths], {})


def at(ref):
    """Ключ маршрута FakeTransport: дерево каталога PATCH на ref."""
    return (TREE_URL, (("path", "PATCH"), ("per_page", "100"),
                       ("recursive", "true"), ("ref", ref)))


def info(original_url=BRANCH_URL, source=None):
    extra = {"source": {"original_url": original_url}} if original_url else {}
    return {"nvr": "vim-8.2-1.sl9", "extra": extra, "source": source}


def client(routes, **kwargs):
    transport = FakeTransport(routes)
    return GitlabClient(HOSTS, token=None, transport=transport,
                        sleeper=lambda _s: None, retries=1, **kwargs), transport


class CvesInTest(unittest.TestCase):
    def test_ids_from_file_names_in_upper_case(self):
        got = cves_in(["PATCH/vim-cve-2024-1234.patch", "PATCH/CVE-2025-0001-a.patch"])
        self.assertEqual(got, {"CVE-2024-1234", "CVE-2025-0001"})

    def test_a_longer_id_is_not_a_shorter_one(self):
        # CVE-2024-12345 — другая уязвимость, а не CVE-2024-1234 с хвостом
        self.assertEqual(cves_in(["PATCH/CVE-2024-12345.patch"]), {"CVE-2024-12345"})

    def test_directory_names_count_too(self):
        self.assertEqual(cves_in(["PATCH/CVE-2024-1234/fix.patch"]), {"CVE-2024-1234"})

    def test_several_ids_in_one_name(self):
        self.assertEqual(cves_in(["PATCH/CVE-2024-1111_CVE-2024-2222.patch"]),
                         {"CVE-2024-1111", "CVE-2024-2222"})


class FindTest(unittest.TestCase):
    def test_tree_is_read_at_the_build_commit_from_koji_source(self):
        cli, transport = client({at(SHA): tree("PATCH/CVE-2024-1234.patch")})
        got = find({"vim": info(source="git+ssh://git@gitlab.example.com/g/vim#" + SHA)}, cli)
        self.assertEqual(got.cves, {"vim": {"CVE-2024-1234"}})
        self.assertEqual(got.failed, ())
        self.assertEqual(transport.requests[0][1]["ref"], SHA)

    def test_commit_in_original_url_is_used(self):
        cli, transport = client({at(SHA): tree("PATCH/CVE-2024-1234.patch")})
        got = find({"vim": info("git+https://gitlab.example.com/g/vim.git#" + SHA)}, cli)
        self.assertEqual(got.cves, {"vim": {"CVE-2024-1234"}})

    def test_without_a_commit_the_branch_is_read(self):
        cli, transport = client({at("sl9"): tree("PATCH/CVE-2024-1234.patch")})
        got = find({"vim": info()}, cli)
        self.assertEqual(got.cves, {"vim": {"CVE-2024-1234"}})
        self.assertEqual(transport.requests[0][1]["ref"], "sl9")

    def test_commit_of_another_project_is_not_taken(self):
        # верхний source указывает в другой репозиторий: чужой коммит хуже,
        # чем никакого, — читается ветка
        cli, transport = client({at("sl9"): tree()})
        find({"vim": info(source="git+ssh://git@gitlab.example.com/other/vim#" + SHA)}, cli)
        self.assertEqual(transport.requests[0][1]["ref"], "sl9")

    def test_gone_commit_falls_back_to_the_branch_with_a_warning(self):
        cli, _ = client({
            at(SHA): Response(404, {"message": "404 Tree Not Found"}, {}),
            COMMITS_URL + SHA: Response(404, {"message": "404 Commit Not Found"}, {}),
            at("sl9"): tree("PATCH/CVE-2024-1234.patch"),
        })
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got = find({"vim": info(source="git+ssh://git@gitlab.example.com/g/vim#" + SHA)},
                       cli)
        self.assertEqual(got.cves, {"vim": {"CVE-2024-1234"}})
        self.assertEqual(got.failed, ())
        line = "\n".join(caught.output)
        self.assertIn("vim", line)
        self.assertIn("с ветки", line)

    def test_gone_commit_without_a_branch_is_a_failure(self):
        cli, _ = client({
            at(SHA): Response(404, {"message": "404 Tree Not Found"}, {}),
            COMMITS_URL + SHA: Response(404, {"message": "404 Commit Not Found"}, {}),
        })
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got = find({"vim": info("git+https://gitlab.example.com/g/vim.git#" + SHA)}, cli)
        self.assertEqual(got.cves, {})
        self.assertEqual(got.failed, ("vim",))

    def test_missing_patch_dir_means_no_patches_not_a_failure(self):
        cli, _ = client({
            at("sl9"): Response(404, {"message": "404 Tree Not Found"}, {}),
            COMMITS_URL + "sl9": Response(200, {"id": SHA}, {}),
        })
        got = find({"vim": info()}, cli)
        self.assertEqual(got.cves, {"vim": frozenset()})
        self.assertEqual(got.failed, ())

    def test_failed_read_is_a_failure_named_in_the_log(self):
        cli, _ = client({at("sl9"): Response(500, {"message": "boom"}, {})})
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got = find({"vim": info()}, cli)
        self.assertEqual(got.cves, {})
        self.assertEqual(got.failed, ("vim",))
        line = "\n".join(caught.output)
        self.assertIn("vim", line)
        self.assertIn("500", line)

    def test_substituted_host_is_read_and_warned_about(self):
        cli, _ = client({at("sl9"): tree("PATCH/CVE-2024-1234.patch")},
                        default_host="gitlab.example.com")
        with self.assertLogs("vulnsheet.patches", "WARNING") as caught:
            got = find({"vim": info("git+https://mirror.example.com/g/vim.git#sl9")}, cli)
        self.assertEqual(got.cves, {"vim": {"CVE-2024-1234"}})
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
        self.assertEqual(got.cves, {})
        self.assertEqual(got.failed, ())
        self.assertEqual(transport.requests, [])

    def test_outcomes_are_counted_by_kind(self):
        cli, _ = client({
            at("sl9"): tree("PATCH/CVE-2024-1234.patch"),
            (TREE_URL.replace("vim", "zsh"), at("sl9")[1]): Response(
                404, {"message": "404 Tree Not Found"}, {}),
            COMMITS_URL.replace("vim", "zsh") + "sl9": Response(200, {"id": SHA}, {}),
        })
        with self.assertLogs("vulnsheet.patches", "WARNING"):
            got = find({"vim": info(), "zsh": info("git+https://gitlab.example.com/g/zsh#sl9"),
                        "bash": info(original_url=None),
                        "gcc": info("x/gcc-1-1.src.rpm"), "perl": None}, cli)
        self.assertEqual(dict(got.kinds), {READ: 1, NO_DIR: 1, NO_SOURCE: 1, SRPM: 1, FAILED: 1})

    def test_summary_is_left_to_the_caller(self):
        # итог по патчам пишет cli в конце прогона, не в его середине
        cli, _ = client({at("sl9"): tree("PATCH/CVE-2024-1234.patch")})
        # assertNoLogs — только с Python 3.10; маркер держит assertLogs довольным
        with self.assertLogs("vulnsheet.patches", "INFO") as caught:
            find({"vim": info()}, cli)
            logging.getLogger("vulnsheet.patches").info("маркер")
        self.assertEqual(caught.output, ["INFO:vulnsheet.patches:маркер"])

    def test_components_are_checked_in_parallel_and_all_come_back(self):
        routes = {}
        builds = {}
        for n in range(20):
            name = "pkg%d" % n
            url = "https://gitlab.example.com/api/v4/projects/g%%2F%s/repository/tree" % name
            routes[url] = tree("PATCH/CVE-2024-%04d.patch" % (1000 + n))
            builds[name] = info("git+https://gitlab.example.com/g/%s.git#sl9" % name)
        cli, _ = client(routes)
        got = find(builds, cli, jobs=4)
        self.assertEqual(got.cves, {"pkg%d" % n: {"CVE-2024-%04d" % (1000 + n)}
                                    for n in range(20)})


if __name__ == "__main__":
    unittest.main()
