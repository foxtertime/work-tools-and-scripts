import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from vulnsheet.config import Config, ConfigError, load_config
from vulnsheet.vex import VexSettings

try:
    import yaml  # noqa: F401 — только чтобы понять, есть ли PyYAML
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

ROOT = os.path.join(os.path.dirname(__file__), "..")

FULL = """\
koji:
  hub: https://koji.example.com/kojihub
  tag: sl9-updates
rhel: "9"
vex:
  cache_dir: ~/vulnsheet-cache
  cache_ttl: 0
  jobs: 4
  retries: 2
  timeout: 12.5
vex_streams:
  "9":
    nginx: nginx:1.26
    npm: nodejs:20
  "10":
    nodejs: nodejs:22
vex_names:
  rust-afterburn: [afterburn, afterburn-dracut]
  rust-coreos-installer: coreos-installer
"""


class DefaultsTest(unittest.TestCase):
    def test_no_path_gives_builtin_values(self):
        cfg = load_config(None)
        self.assertEqual(cfg, Config())
        self.assertEqual(cfg.vex, VexSettings())
        self.assertIsNone(cfg.stream_for("nginx", "9"))

    def test_default_names_cannot_be_mutated(self):
        with self.assertRaises(TypeError):
            Config().vex_names["vim"] = ("x",)

    def test_default_streams_cannot_be_mutated(self):
        with self.assertRaises(TypeError):
            Config().vex_streams["9"] = {}


class NamesForTest(unittest.TestCase):
    def test_aliases_or_empty(self):
        cfg = Config(vex_names={"rust-afterburn": ("afterburn",)})
        self.assertEqual(cfg.names_for("rust-afterburn"), ("afterburn",))
        self.assertEqual(cfg.names_for("vim"), ())
        self.assertEqual(Config().names_for("vim"), ())


class StreamForTest(unittest.TestCase):
    CFG = Config(vex_streams={"9": {"nginx": "nginx:1.26"},
                              "9.2": {"nodejs": "nodejs:20"}})

    def test_exact_version(self):
        self.assertEqual(self.CFG.stream_for("nginx", "9"), "nginx:1.26")
        self.assertEqual(self.CFG.stream_for("nodejs", "9.2"), "nodejs:20")

    def test_minor_does_not_fall_back_to_major(self):
        self.assertIsNone(self.CFG.stream_for("nginx", "9.2"))

    def test_major_does_not_take_minor_set(self):
        self.assertIsNone(self.CFG.stream_for("nodejs", "9"))

    def test_unknown_package_or_version(self):
        self.assertIsNone(self.CFG.stream_for("vim", "9"))
        self.assertIsNone(self.CFG.stream_for("nginx", "10"))


class MissingYamlTest(unittest.TestCase):
    def test_config_without_pyyaml_is_reported(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaises(ConfigError) as caught:
                load_config("vulnsheet.yaml")
        self.assertIn("python3-pyyaml", str(caught.exception))


@unittest.skipUnless(HAVE_YAML, "нужен PyYAML")
class LoadTest(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)

    def write(self, text):
        path = os.path.join(self.room, "vulnsheet.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def assertRejected(self, text, needle):
        with self.assertRaises(ConfigError) as caught:
            load_config(self.write(text))
        self.assertIn(needle, str(caught.exception))
        return caught.exception

    def test_full_file(self):
        path = self.write(FULL)
        cfg = load_config(path)
        self.assertEqual(cfg.path, path)
        self.assertEqual((cfg.koji_hub, cfg.koji_tag, cfg.rhel),
                         ("https://koji.example.com/kojihub", "sl9-updates", "9"))
        self.assertEqual(cfg.vex, VexSettings(
            cache_dir=os.path.expanduser("~/vulnsheet-cache"), cache_ttl=0,
            jobs=4, retries=2, timeout=12.5))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26", "npm": "nodejs:20"},
                                           "10": {"nodejs": "nodejs:22"}})
        self.assertEqual(cfg.vex_names, {"rust-afterburn": ("afterburn", "afterburn-dracut"),
                                         "rust-coreos-installer": ("coreos-installer",)})

    def test_empty_file_is_empty_config(self):
        self.assertEqual(load_config(self.write(""))._replace(path=None), Config())

    def test_empty_sections_are_allowed(self):
        cfg = load_config(self.write("koji:\nvex:\nvex_streams:\n  \"9\":\n"))
        self.assertEqual(cfg.vex, VexSettings())
        self.assertEqual(cfg.vex_streams, {"9": {}})

    def test_unknown_nested_key_names_full_path(self):
        self.assertRejected("vex:\n  cache_tll: 10\n", "vex.cache_tll")

    def test_unknown_top_level_key(self):
        self.assertRejected("koj:\n  hub: x\n", "koj")

    def test_error_names_the_file(self):
        error = self.assertRejected("vex:\n  jobs: 0\n", "vex.jobs")
        self.assertIn("vulnsheet.yaml", str(error))

    def test_bad_values(self):
        cases = [
            ("vex:\n  jobs: 0\n", "vex.jobs"),
            ("vex:\n  jobs: true\n", "vex.jobs"),
            ("vex:\n  retries: 1.5\n", "vex.retries"),
            ("vex:\n  cache_ttl: -1\n", "vex.cache_ttl"),
            ("vex:\n  timeout: 0\n", "vex.timeout"),
            ("vex:\n  timeout: false\n", "vex.timeout"),
            ("vex:\n  timeout: .nan\n", "vex.timeout"),
            ("vex:\n  timeout: .inf\n", "vex.timeout"),
            ("vex:\n  cache_dir: ''\n", "vex.cache_dir"),
            ("koji:\n  tag: 9\n", "koji.tag"),
            ("koji:\n  hub: ''\n", "koji.hub"),
            ("rhel: nine\n", "rhel"),
            ("rhel: 9.2\n", "кавычк"),
            ("vex: [1]\n", "vex"),
            ("vex_streams: [nginx]\n", "vex_streams"),
            ("vex_streams:\n  \"9\": [nginx]\n", "vex_streams.9"),
            ("vex_streams:\n  \"9\":\n    nginx: ''\n", "vex_streams.9"),
            ("vex_streams:\n  \"9\":\n    nginx: 1.26\n", "кавычк"),
            ("- a\n", "словар"),
            ("vex_names: [a]\n", "vex_names"),
            ("vex_names:\n  rust-afterburn:\n", "vex_names.rust-afterburn"),
            ("vex_names:\n  rust-afterburn: []\n", "vex_names.rust-afterburn"),
            ("vex_names:\n  rust-afterburn: ['']\n", "vex_names.rust-afterburn"),
            ("vex_names:\n  rust-afterburn: [1]\n", "vex_names.rust-afterburn"),
            ("vex_names:\n  rust-afterburn: {a: b}\n", "vex_names.rust-afterburn"),
        ]
        for text, needle in cases:
            with self.subTest(text=text):
                self.assertRejected(text, needle)

    def test_unquoted_integer_version_key(self):
        cfg = load_config(self.write("vex_streams:\n  9:\n    nginx: nginx:1.26\n"))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26"}})

    def test_float_version_key_is_rejected(self):
        # 9.10 без кавычек YAML прочитал бы как 9.1 — молча не та версия.
        self.assertRejected("vex_streams:\n  9.10:\n    nginx: nginx:1.26\n", "кавычк")

    def test_version_keys_are_normalised(self):
        cfg = load_config(self.write("vex_streams:\n  RHEL 9:\n    nginx: nginx:1.26\n"))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26"}})

    def test_duplicate_version_after_normalisation(self):
        self.assertRejected("vex_streams:\n  9:\n    a: b\n  RHEL 9:\n    c: d\n", "дважды")

    def test_duplicate_yaml_key_in_vex_streams_block(self):
        self.assertRejected(
            "vex_streams:\n  \"9\":\n    nginx: nginx:1.26\n"
            "  \"9\":\n    npm: nodejs:20\n", "дважды")

    def test_duplicate_package_key_under_one_version(self):
        self.assertRejected(
            "vex_streams:\n  \"9\":\n    nginx: nginx:1.26\n"
            "    nginx: nginx:1.28\n", "дважды")

    def test_duplicate_top_level_key(self):
        self.assertRejected("koji:\n  hub: a\nkoji:\n  hub: b\n", "дважды")

    def test_merge_key_reuses_a_stream_set(self):
        # Наборы между 9 и 9.2 не наследуются — общий набор естественно
        # переиспользовать якорем.
        cfg = load_config(self.write(
            "vex_streams:\n  \"9\": &base\n    nginx: nginx:1.26\n"
            "  \"9.2\":\n    <<: *base\n    npm: nodejs:20\n"))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26"},
                                           "9.2": {"nginx": "nginx:1.26", "npm": "nodejs:20"}})

    def test_explicit_key_overrides_merged_one(self):
        # Переопределить ключ из якоря — обычный приём YAML, не дубль.
        cfg = load_config(self.write(
            "vex_streams:\n  \"9\": &base\n    nginx: nginx:1.26\n"
            "  \"9.2\":\n    <<: *base\n    nginx: nginx:1.24\n"))
        self.assertEqual(cfg.stream_for("nginx", "9.2"), "nginx:1.24")

    def test_duplicate_explicit_key_next_to_merge_is_rejected(self):
        self.assertRejected(
            "vex_streams:\n  \"9\": &base\n    nginx: nginx:1.26\n"
            "  \"9.2\":\n    <<: *base\n    npm: nodejs:20\n    npm: nodejs:22\n",
            "дважды")

    def test_loaded_streams_are_immutable(self):
        cfg = load_config(self.write(FULL))
        with self.assertRaises(TypeError):
            cfg.vex_streams["9"] = {}

    def test_missing_file(self):
        with self.assertRaises(ConfigError) as caught:
            load_config(os.path.join(self.room, "нет.yaml"))
        self.assertIn("не читается", str(caught.exception))

    def test_yaml_syntax_error(self):
        self.assertRejected("koji: [\n", "YAML")

    def test_example_file_is_valid(self):
        cfg = load_config(os.path.join(ROOT, "vulnsheet.example.yaml"))
        self.assertEqual(cfg.stream_for("nginx", "9"), "nginx:1.26")
