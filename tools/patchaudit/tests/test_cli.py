import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from patchaudit import __version__
from patchaudit.cli import main
from tests.fakes import FakeTransport, Response
from tests import test_audit as fixtures
from tests.test_audit import LATEST, PATCH

COMMON = ["--koji-url", "https://koji.example.org/kojihub", "--tag", "sl9",
          "--rhel", "9", "--gitlab-url", "https://git.example.org"]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AuditTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.room = Path(self.temp.name)
        self.transport = FakeTransport({
            "https://git.example.org/api/v4/projects/rpms%2Fvim/repository/tree":
                Response(200, [{"type": "blob", "path": PATCH}], {})})
        self.connect = mock.patch("patchaudit.kojiclient.connect", return_value=self.fixture.session).start()
        mock.patch("patchaudit.httpclient.UrllibTransport", return_value=self.transport).start()
        mock.patch.dict(os.environ, {"PATCHAUDIT_CONFIG": "", "XDG_CACHE_HOME": str(self.room / "cache")}).start()
        self.addCleanup(mock.patch.stopall)

    def invoke(self, args, common=True):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main((COMMON if common else []) + args)
        self.stderr = err.getvalue()
        self.stdout = out.getvalue()
        return code

    def test_package_and_target_modes_write_parseable_json_to_stdout(self):
        for flags, expected in [(["--package", "vim"], "fixed"),
                                (["--nvr", "vim-8.2-9.el9"], "remove"),
                                (["--nvr", "vim-8.2-8.el9"], "remove_on_upgrade")]:
            self.assertEqual(self.invoke(flags), 0)
            data = json.loads(self.stdout)
            self.assertEqual(data["format"], 1)
            self.assertEqual(data["patches"][0]["action"], expected)
            self.assertIn("patchaudit", self.stderr)

    def test_atomic_file_output_preserves_existing_mode_and_symlink(self):
        target = self.room / "report.json"
        target.write_text("old")
        target.chmod(0o640)
        link = self.room / "link.json"
        link.symlink_to(target)
        self.assertEqual(self.invoke(["--package", "vim", "-o", str(link)]), 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertTrue(json.loads(target.read_text())["complete"])
        self.assertEqual(self.stdout, "")

    def test_sl_target_decisions_preserve_original_nvr_in_json(self):
        for target, expected in (("vim-8.2-9.sl9^123", "remove"),
                                 ("vim-8.2-8.sl9^999", "remove_on_upgrade")):
            with self.subTest(target=target):
                self.assertEqual(self.invoke(["--nvr", target]), 0)
                data = json.loads(self.stdout)
                self.assertEqual(data["request"]["target_nvr"], target)
                self.assertEqual(data["patches"][0]["action"], expected)
                self.assertEqual(data["cves"][0]["fixes"][0]["nvr"], "vim-8.2-9.el9")

    def test_partial_report_is_written_with_exit_one(self):
        self.fixture.docs.clear()
        self.fixture.docs.update({"https://security.access.redhat.com/data/csaf/v2/vex/2026/cve-2026-1000.json": {}})
        with mock.patch("patchaudit.vex.time.sleep"):
            self.assertEqual(self.invoke(["--package", "vim"]), 1)
        data = json.loads(self.stdout)
        self.assertFalse(data["complete"])
        self.assertEqual(data["patches"][0]["action"], "review")

    def test_invalid_gitlab_body_is_reported_as_partial_json(self):
        for body in (None, {"message": "proxy error"}, [{"type": "blob"}]):
            self.transport.routes["https://git.example.org/api/v4/projects/rpms%2Fvim/repository/tree"] = Response(200, body, {})
            self.assertEqual(self.invoke(["--package", "vim"]), 1)
            self.assertFalse(json.loads(self.stdout)["complete"])

    def test_wrong_cached_cve_is_evicted_and_does_not_authorize_removal(self):
        path = self.room / "cache" / "patchaudit" / "cve-2026-1000.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(fixtures.doc(cve="CVE-2026-9999")))
        self.assertEqual(self.invoke(["--nvr", "vim-8.2-9.el9"]), 1)
        self.assertEqual(json.loads(self.stdout)["patches"][0]["action"], "review")
        self.assertFalse(path.exists())

    def test_bad_arguments_fail_before_network(self):
        for flags in ([], ["--package", "vim", "--nvr", "vim-1-2"],
                      ["--nvr", "not-an-nvr-"], ["--package", "bad/package"]):
            self.assertEqual(self.invoke(flags), 2)
        self.connect.assert_not_called()

    def test_missing_required_settings_and_wrong_rhel(self):
        for flags in (["--package", "vim"], COMMON[:4] + ["--package", "vim"],
                      COMMON + ["--package", "vim", "--rhel", "nonsense"]):
            self.assertEqual(self.invoke(flags, common=False), 2)
        self.connect.assert_not_called()

    def test_invalid_output_is_rejected_before_network(self):
        self.assertEqual(self.invoke(["--package", "vim", "-o", str(self.room / "absent" / "r.json")]), 2)
        self.connect.assert_not_called()

    def test_fatal_error_does_not_replace_previous_output(self):
        target = self.room / "report.json"
        target.write_text("old")
        self.fixture.session.hub_down = True
        self.assertEqual(self.invoke(["--package", "vim", "-o", str(target)]), 2)
        self.assertEqual(target.read_text(), "old")
        self.assertEqual(list(self.room.glob(".patchaudit-*.tmp")), [])

    def test_version_and_help_do_not_connect(self):
        self.assertEqual(self.invoke(["--version"], common=False), 0)
        self.assertEqual(self.stdout.strip(), "patchaudit " + __version__)
        self.assertEqual(self.invoke(["--help"], common=False), 0)
        self.assertIn("--nvr", self.stdout)
        self.connect.assert_not_called()

    def test_environment_config_and_cli_overrides(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        config = self.room / "config.yaml"
        config.write_text("koji:\n  hub: https://koji.example.org/kojihub\n  tag: wrong-tag\nrhel: '9'\n"
                          "gitlab:\n  hosts:\n    git.example.org:\n      api: https://git.example.org/api/v4\n")
        with mock.patch.dict(os.environ, {"PATCHAUDIT_CONFIG": str(config)}):
            self.assertEqual(self.invoke(["--package", "vim", "--tag", "sl9"], common=False), 0)
        self.assertEqual(json.loads(self.stdout)["latest_build"], LATEST)

    def test_token_trimmed_and_not_written_to_log_or_json(self):
        token = "secret-gitlab-token-123456"
        path = self.token_config(" " + token + "\n")
        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "wrong-env-token"}):
            self.assertEqual(self.invoke(["--package", "vim", "--config", str(path)]), 0)
        self.assertEqual(self.transport.requests[0][2]["PRIVATE-TOKEN"], token)
        self.assertNotIn(token, self.stdout + self.stderr)

    def token_config(self, token):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        path = self.room / "credentials.yaml"
        path.write_text("gitlab:\n  token: " + json.dumps(token) + "\n"
                        "  hosts:\n    git.example.org:\n      api: https://git.example.org/api/v4\n")
        return path

    def test_env_token_is_never_used_without_a_config_token(self):
        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "glpat-unused-env-secret"}):
            configs = [None, self.token_config(None), self.token_config("  ")]
            for config_path in configs:
                flags = ["--config", str(config_path)] if config_path else []
                self.transport.requests.clear()
                self.assertEqual(self.invoke(["--package", "vim"] + flags), 0)
                self.assertNotIn("PRIVATE-TOKEN", self.transport.requests[0][2])

    def test_secret_in_http_error_body_is_redacted_from_debug_log_and_json(self):
        secret = "glpat-config-response-secret"
        path = self.token_config(secret)
        url = "https://git.example.org/api/v4/projects/rpms%2Fvim/repository/tree"
        self.transport.routes[url] = Response(403, {"message": "rejected token " + secret}, {})
        self.assertEqual(self.invoke(["--package", "vim", "--config", str(path), "--log-level", "debug"]), 1)
        self.assertTrue(json.loads(self.stdout)["problems"])
        self.assertNotIn(secret, self.stdout + self.stderr)

    def test_yaml_error_does_not_expose_config_token_in_stderr(self):
        secret = "glpat-config-yaml-error-secret"
        path = self.token_config(None)
        path.write_text("gitlab:\n  token: [" + secret + "\n")
        self.assertEqual(self.invoke(["--package", "vim", "--config", str(path)]), 2)
        self.assertNotIn(secret, self.stdout + self.stderr)
