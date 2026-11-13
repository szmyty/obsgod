"""Ensure local CI forwards needed proxy values without persisting credentials."""
import importlib.util
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
    def test_child_gets_proxy_but_receipt_and_log_do_not_keep_its_password(self):
        proxy = "http://user:private-fixture-password@proxy.example:8080"
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            child = SimpleNamespace(stdout=io.StringIO("connect " + proxy + "\n"), wait=lambda: 0)
            def output(command, **kwargs):
                return "act version 0.2.97\n" if command[-1] == "--version" else b"source diff"
            with patch.object(CI.sys, "argv", ["local-ci.py", "list", "--state", temporary, "--act", "/fixture/act"]), \
                    patch.dict(CI.os.environ, {"HTTP_PROXY": proxy}, clear=True), \
                    patch.object(CI, "prepare_actions", return_value=([], [])), \
                    patch.object(CI, "network_options", return_value="--mount trusted-ca"), \
                    patch.object(CI, "git", return_value="a" * 40), \
                    patch.object(CI.subprocess, "check_output", side_effect=output), \
                    patch.object(CI.subprocess, "Popen", return_value=child) as run, \
                    self.assertRaises(SystemExit) as stopped:
                CI.main()
            self.assertEqual(stopped.exception.code, 0)
            self.assertIn("HTTP_PROXY=" + proxy, run.call_args.args[0])
            receipt_file = next(state.glob("*.json"))
            receipt = json.loads(receipt_file.read_text())
            self.assertIn("HTTP_PROXY=[injected]", receipt["command"])
            self.assertNotIn("private-fixture-password", receipt_file.read_text())
            self.assertNotIn("private-fixture-password", next(state.glob("*.log")).read_text())

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
