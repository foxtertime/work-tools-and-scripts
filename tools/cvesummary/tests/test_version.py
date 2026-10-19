import unittest

from cvesummary import __version__


class VersionTest(unittest.TestCase):
    def test_semver(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
