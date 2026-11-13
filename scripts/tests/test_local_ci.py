"""Ensure local CI forwards needed proxy values without persisting credentials."""
import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("local_ci", Path(__file__).parents[1] / "local-ci.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)


class LocalCITests(unittest.TestCase):
    def assert_proxy_is_private(self, proxy, lines=None):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            act = state / "act"
            act.write_bytes(b"fixture act executable")
            child = SimpleNamespace(stdout=io.StringIO(lines or "connect " + proxy + "\n"), wait=lambda: 0)
            printed = io.StringIO()
            def output(command, **kwargs):
                return "act version 0.2.97\n" if command[-1] == "--version" else b""
            def git(*arguments):
                if arguments[0] == "status":
                    return ""
                return "b" * 40 if arguments[-1] == "HEAD^{tree}" else "a" * 40
            with patch.object(CI.sys, "argv", ["local-ci.py", "list", "--state", temporary, "--act", str(act)]), \
                    patch.dict(CI.os.environ, {"HTTP_PROXY": proxy}, clear=True), \
                    patch.object(CI, "prepare_actions", return_value=([], [])), \
                    patch.object(CI, "network_options", return_value="--mount trusted-ca"), \
                    patch.object(CI, "git", side_effect=git), \
                    patch.object(CI.subprocess, "check_output", side_effect=output), \
                    patch.object(CI.subprocess, "Popen", return_value=child) as run, \
                    redirect_stdout(printed), \
                    self.assertRaises(SystemExit) as stopped:
                CI.main()
            self.assertEqual(stopped.exception.code, 0)
            self.assertIn("HTTP_PROXY=" + proxy, run.call_args.args[0])
            receipt_file = next(state.glob("*.json"))
            receipt = json.loads(receipt_file.read_text())
            log = next(state.glob("*.log")).read_text()
            self.assertIn("HTTP_PROXY=[injected]", receipt["command"])
            self.assertNotIn("private-fixture-password", receipt_file.read_text())
            self.assertNotIn("private-fixture-password", log)
            self.assertNotIn("private-fixture-password", printed.getvalue())
            self.assertEqual(receipt["act_binary_sha256"], CI.sha(act.read_bytes()))
            self.assertEqual(receipt["launcher_sha256"], CI.sha(Path(CI.__file__).read_bytes()))
            self.assertEqual(receipt["actrc_sha256"], CI.sha((CI.ROOT / ".actrc").read_bytes()))
            self.assertEqual(receipt["source_tree"], "b" * 40)
            self.assertEqual(receipt["log_sha256"], CI.sha(log.encode()))
            self.assertEqual(receipt["log_format"], "jsonl-with-text-fallback")
            return receipt, log

    def test_proxy_password_is_not_kept_in_receipt_or_log(self):
        self.assert_proxy_is_private("http://user:private-fixture-password@proxy.example:8080")

    def test_proxy_token_only_userinfo_is_not_kept_in_receipt_or_log(self):
        self.assert_proxy_is_private("https://private-fixture-password@proxy.example:8080")

    def test_proxy_empty_password_userinfo_is_not_kept_in_receipt_or_log(self):
        self.assert_proxy_is_private("https://private-fixture-password:@proxy.example:8080")

    def test_json_log_escaped_userinfo_is_filtered_recursively(self):
        proxy = "https://user:private-fixture-password@proxy.example:8080"
        record = {"msg": "connect " + proxy, "fields": [
            {"proxy": "HTTPS://private-fixture-password@proxy.example"},
            {proxy: "https://private-fixture-password:@proxy.example"}],
            "time": "2026-11-13T12:00:00Z", "count": 2, "active": True, "missing": None}
        # Escaped slashes and @ mean a regex over raw JSON cannot recognize the
        # original URL. Filtering must operate after JSON decoding.
        encoded = json.dumps(record).replace("/", r"\/").replace("@", r"\u0040")
        receipt, log = self.assert_proxy_is_private(proxy, encoded + "\nlegacy warning\n")
        lines = log.splitlines()
        filtered = json.loads(lines[0])
        self.assertEqual(filtered["msg"], "connect https://[redacted]@proxy.example:8080")
        self.assertEqual(filtered["fields"], [{"proxy": "HTTPS://[redacted]@proxy.example"},
                         {"https://[redacted]@proxy.example:8080": "https://[redacted]@proxy.example"}])
        for field in ["time", "count", "active", "missing"]:
            self.assertEqual(filtered[field], record[field])
        self.assertEqual(lines[1], "legacy warning")
        self.assertEqual(receipt["log_record_counts"], {"json": 1, "text": 1})

    def test_legacy_prefixed_text_can_redact_json_escaped_slashes(self):
        line = r'legacy connect https:\/\/private-fixture-password:@proxy.example' + "\n"
        filtered, structured = CI.sanitize_log_line(line)
        self.assertFalse(structured)
        self.assertNotIn("private-fixture-password", filtered)
        self.assertEqual(filtered, r'legacy connect https:\/\/[redacted]@proxy.example' + "\n")

    def test_redacted_dictionary_key_collisions_retain_every_value(self):
        record = {"context": {
            "https://fixture-a@proxy.example": {"frames": 1},
            "https://fixture-b@proxy.example": ["second-output", False],
            "https://[redacted]@proxy.example [redacted key 2]": None}}
        line = json.dumps(record) + "\n"
        filtered, structured = CI.sanitize_log_line(line)
        self.assertTrue(structured)
        context = json.loads(filtered)["context"]
        self.assertEqual(len(context), 3)
        self.assertEqual(list(context.values()), list(record["context"].values()))
        self.assertNotIn("fixture-a", filtered)
        self.assertNotIn("fixture-b", filtered)
        self.assertEqual(CI.sanitize_log_line(line)[0], filtered)
        self.assertEqual(CI.sanitize_log_line(filtered)[0], filtered)

    def test_tampered_pinned_action_cache_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            repository, revision = "actions/setup-go", "4" * 40
            root = state / "action-sources" / (repository.replace("/", "-") + "-" + revision)
            root.mkdir(parents=True)
            (root / "action.yml").write_text("tampered action")
            root.with_suffix(".json").write_text(json.dumps({"files": {"action.yml": CI.sha(b"expected action")}}))
            fake_workflow = SimpleNamespace(read_text=lambda: "uses: " + repository + "@" + revision)
            fake_workflows = SimpleNamespace(glob=lambda pattern: [fake_workflow])
            # Path division uses the class method, so use a narrow fake class.
            class FakeRoot:
                def __truediv__(self, value):
                    return fake_workflows
            with patch.object(CI, "ROOT", FakeRoot()), self.assertRaisesRegex(SystemExit, "differs from verified receipt"):
                CI.prepare_actions(state)


if __name__ == "__main__":
    unittest.main()
