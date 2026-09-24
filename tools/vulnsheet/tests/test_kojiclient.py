import sys
import unittest
from unittest import mock

from tests.fakes import FakeKojiSession
from vulnsheet.kojiclient import ERROR, NOT_FOUND, KojiError, connect, latest_builds


class LatestBuildsTest(unittest.TestCase):
    def test_found_missing_and_failed_packages(self):
        session = FakeKojiSession(builds={"vim": "vim-8.2-1.sl9"}, errors={"bash": "boom"})
        with self.assertLogs("vulnsheet", "WARNING") as caught:
            got = latest_builds(session, "sl9", ["vim", "zsh", "bash"])
        self.assertEqual(got, {"vim": "vim-8.2-1.sl9", "zsh": NOT_FOUND, "bash": ERROR})
        joined = "\n".join(caught.output)
        self.assertIn("zsh", joined)
        self.assertIn("boom", joined)

    def test_each_package_is_asked_once(self):
        session = FakeKojiSession(builds={"vim": "vim-8.2-1.sl9"})
        latest_builds(session, "sl9", ["vim", "vim", "vim"])
        self.assertEqual(session.calls, [("sl9", "vim")])

    def test_no_packages_means_no_calls(self):
        session = FakeKojiSession(hub_down=True)
        self.assertEqual(latest_builds(session, "sl9", []), {})

    def test_unknown_tag_is_fatal(self):
        # Опечатка в теге — одна ошибка, а не таблица из одних ERROR.
        with self.assertRaises(KojiError) as caught:
            latest_builds(FakeKojiSession(tags=["sl9"]), "sl-9", ["vim"])
        self.assertIn("sl-9", str(caught.exception))

    def test_unreachable_hub_is_fatal(self):
        with self.assertRaises(KojiError):
            latest_builds(FakeKojiSession(hub_down=True), "sl9", ["vim"])

    def test_failed_multicall_is_fatal(self):
        with self.assertRaises(KojiError):
            latest_builds(FakeKojiSession(multicall_down=True), "sl9", ["vim"])


class ConnectTest(unittest.TestCase):
    def test_missing_koji_module_is_reported(self):
        with mock.patch.dict(sys.modules, {"koji": None}):
            with self.assertRaises(KojiError) as caught:
                connect("https://koji.example.com/kojihub")
        self.assertIn("koji", str(caught.exception))
