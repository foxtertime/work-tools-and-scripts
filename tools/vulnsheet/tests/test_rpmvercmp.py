import unittest

from vulnsheet.rpmvercmp import rpmvercmp


class RpmVerCmpTest(unittest.TestCase):
    CASES = [
        # (a, b, a ? b) — как rpmdev-vercmp
        ("1.0", "1.0", 0),
        ("1.0", "2.0", -1),
        ("2.0.1", "2.0", 1),
        ("2.4.62", "2.4.60", 1),
        ("1.010", "1.9", 1),
        ("1.05", "1.5", 0),
        ("1.1.1za", "1.1.1x", 1),      # openssl
        ("1.0.2zk", "1.0.2zj", 1),
        ("8.7p1", "8.5p1", 1),         # openssh
        ("9.7p1", "9.8", -1),
        ("9.0.2106", "8.2.2637", 1),   # vim
        ("1.9.17p1", "1.9.17", 1),     # sudo
        ("1.0a", "1.0", 1),
        ("1.0a", "1.0.1", -1),
        ("1.0~rc1", "1.0", -1),
        ("1.0~rc1", "1.0~rc2", -1),
        ("1.0^git1", "1.0", 1),
        ("1.0^git1", "1.0.1", -1),
        ("r31", "r27", 1),
        ("1_2", "1.2", 0),             # разделители не различаются
    ]

    def test_table(self):
        for a, b, want in self.CASES:
            with self.subTest(a=a, b=b):
                self.assertEqual(rpmvercmp(a, b), want)
                self.assertEqual(rpmvercmp(b, a), -want)


if __name__ == "__main__":
    unittest.main()
