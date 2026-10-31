from pathlib import Path
import unittest

from patchaudit import __version__


class VersionTest(unittest.TestCase):
    def test_version_and_changelog(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        root = Path(__file__).resolve().parent.parent
        self.assertIn("## " + __version__ + " ", (root / "CHANGELOG.md").read_text())
