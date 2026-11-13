"""Exercise real child identity/status and retain production root refusal."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/run-user-tests.py"


class UserTestIdentity(unittest.TestCase):
    def test_child_has_real_nonroot_identity_private_home_and_no_root_groups(self):
        result = subprocess.run([sys.executable, str(HELPER), "--", "-c", "import json,os,pathlib; print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'home_mode':pathlib.Path.home().stat().st_mode&511,'temp_mode':pathlib.Path(os.environ['TMPDIR']).stat().st_mode&511}))"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout.splitlines()[-1])
        self.assertNotEqual(data["uid"], 0)
        self.assertEqual(data["home_mode"], 0o700)
        self.assertEqual(data["temp_mode"], 0o700)
        if os.getuid() == 0:
            self.assertEqual(data["groups"], [])
            self.assertEqual(data["uid"], ROOT.stat().st_uid or 65534)
        else:
            self.assertEqual(data["uid"], os.getuid())

    def test_child_failure_is_propagated(self):
        result = subprocess.run([sys.executable, str(HELPER), "--", "-c", "raise SystemExit(37)"], capture_output=True)
        self.assertEqual(result.returncode, 37)

    def test_long_parent_tmpdir_does_not_break_actual_browser_style_unix_socket(self):
        with tempfile.TemporaryDirectory(prefix="long-cloud-workspace-" + "x" * 50) as inherited:
            code = "import os,pathlib,socket; directory=pathlib.Path(os.environ['TMPDIR'])/'org.chromium.Chromium.abcdef'; directory.mkdir(); stream=socket.socket(socket.AF_UNIX); stream.bind(str(directory/'SingletonSocket')); stream.close(); print('actual Unix socket bound')"
            result = subprocess.run([sys.executable, str(HELPER), "--", "-c", code], env={**os.environ, "TMPDIR": inherited}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("actual Unix socket bound", result.stdout)

    def test_source_tree_cannot_become_output_and_ownership_is_preserved(self):
        before = (ROOT.stat().st_uid, ROOT.stat().st_gid, ROOT.stat().st_mode)
        result = subprocess.run([sys.executable, str(HELPER), "--output-root", str(ROOT), "--", "-c", "raise SystemExit(0)"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((ROOT.stat().st_uid, ROOT.stat().st_gid, ROOT.stat().st_mode), before)

    def test_existing_foreign_owned_output_is_not_chowned(self):
        temporary_root = Path("/tmp")
        before = (temporary_root.stat().st_uid, temporary_root.stat().st_gid, temporary_root.stat().st_mode)
        result = subprocess.run([sys.executable, str(HELPER), "--output-root", str(temporary_root), "--", "-c", "raise SystemExit(0)"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((temporary_root.stat().st_uid, temporary_root.stat().st_gid, temporary_root.stat().st_mode), before)

    def test_production_install_update_uninstall_still_refuse_root(self):
        # In act these assertions use the actual UID0. On ordinary hosted/local
        # user runners only this negative boundary test simulates UID0.
        for name in ("install", "update", "uninstall"):
            with self.subTest(operation=name):
                spec = importlib.util.spec_from_file_location("root_guard_" + name, ROOT / "steamdeck" / (name + ".py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                root_identity = contextlib.nullcontext() if os.getuid() == 0 else patch.object(module.os, "getuid", return_value=0)
                with root_identity:
                    if name == "install":
                        with self.assertRaisesRegex(RuntimeError, "without sudo"):
                            module.install(launch=False, with_decky=False)
                    elif name == "update":
                        with self.assertRaisesRegex(module.UpdateError, "without sudo"):
                            module.run_update()
                    else:
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            self.assertEqual(module.main(["--dry-run", "--json"]), 1)
                        self.assertIn("without sudo", output.getvalue())


if __name__ == "__main__":
    unittest.main()
