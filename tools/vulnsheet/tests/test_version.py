"""Номер версии живёт в vulnsheet/__init__.py; тесты сторожат его форму и
запись в CHANGELOG тулзы. Флаг --version проверяет test_cli."""
import os
import unittest

from vulnsheet import __version__

CHANGELOG = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")


class VersionTest(unittest.TestCase):
    def test_version_is_three_numbers(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_changelog_names_the_current_version(self):
        # Покрасневший тест значит забытую запись в CHANGELOG, а не
        # сломанный код.
        with open(CHANGELOG, encoding="utf-8") as handle:
            self.assertIn("## %s " % __version__, handle.read())
