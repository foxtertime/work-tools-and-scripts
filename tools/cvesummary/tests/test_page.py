import json
import os
import re
import unittest

from cvesummary import page

DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)
DATA = {"meta": {"version": "1.0.0", "as_of": "2026-10-19"},
        "rows": [{"cve": "CVE-1", "comment": "</script><script>alert(1)</script><!-- & >"}]}


class DataJsonTest(unittest.TestCase):
    def test_escapes_markup(self):
        text = page.data_json(DATA)
        for ch in "<>&":
            self.assertNotIn(ch, text)
        self.assertEqual(json.loads(text), DATA)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.html = page.render(DATA)

    def test_data_round_trips(self):
        self.assertEqual(json.loads(DATA_RE.search(self.html).group(1)), DATA)

    def test_cell_cannot_close_a_script(self):
        self.assertEqual(self.html.count("</script>"), 2)

    def test_markers_are_replaced(self):
        for marker in ("/*@css*/", "@data@", "/*@js*/"):
            self.assertNotIn(marker, self.html)

    def test_scripts_in_dependency_order(self):
        positions = [self.html.index("root.CS.%s =" % name[:-3]) for name in page.SCRIPTS
                     if name != "render.js"]
        self.assertEqual(positions, sorted(positions))
        self.assertGreater(self.html.index("JSON.parse(document.getElementById('data')"), positions[-1])

    def test_css_is_inlined(self):
        self.assertIn(".tl-scroll{", self.html)

    def test_section_bar_links_every_section(self):
        nav = re.search(r'<nav class="secnav".*?</nav>', self.html, re.S)
        self.assertIsNotNone(nav)
        links = re.findall(r'<a href="#([^"]+)"', nav.group(0))
        main = self.html[self.html.index("<main"):]
        sections = re.findall(r'<section\b[^>]*\bid="([^"]+)"', main)
        self.assertEqual(links, sections)
        self.assertEqual(len(re.findall(r'<section\b', main)), len(sections))


class AssetsTest(unittest.TestCase):
    def test_assets_cannot_break_out_of_their_tags(self):
        names = ["summary.css"] + ["js/" + n for n in page.SCRIPTS]
        for name in names:
            with open(os.path.join(page.ASSETS, name), encoding="utf-8") as handle:
                text = handle.read().lower()
            with self.subTest(name=name):
                self.assertNotIn("</script", text)
                self.assertNotIn("</style", text)
                self.assertNotIn("<!--", text)
