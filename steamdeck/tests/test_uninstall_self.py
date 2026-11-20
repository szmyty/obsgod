"""Execute the copied installed uninstaller with its real lazy helper boundary."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IDLE = {"ok": True, "configured": True, "state": "stopped", "output_known": True,
        "process": "absent", "stream": {"active": False, "reconnecting": False},
        "recording": False, "media": {"known": True, "replay_active": False,
                                      "recording": {"active": False, "paused": False}}}


class InstalledSelfRemoval(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "player"
        self.home.mkdir(mode=0o700)
        self.base = self.home / ".local/share/obsgod"
        self.release = self.base / "releases/v1"
        self.release.mkdir(parents=True, mode=0o700)
        (self.base / "current").symlink_to(self.release)
        for name in ("uninstall.py", "bridge.py", "paths.py", "product.py", "decky.py"):
            shutil.copyfile(ROOT / name, self.release / name)
        for relative in (".config/obsgod/secrets.json", ".local/state/obsgod/diagnostics/keep.json",
                         "homebrew/settings/obsgod/keep", "Videos/OBSGod/keep.mkv"):
            path = self.home / relative
            path.parent.mkdir(parents=True)
            path.write_text("owned fixture sentinel")
        cli = self.release / "obsgod"
        cli.write_text("#!" + sys.executable + "\n" +
                       "import json,os,sys\nfrom pathlib import Path\n" +
                       "home=Path(os.environ['HOME']);action=sys.argv[-1]\n" +
                       "with (home/'calls.jsonl').open('a') as stream:stream.write(json.dumps(action)+'\\n')\n" +
                       "if action=='restart':\n (home/'.local/state/obsgod/diagnostics/unexpected-restart').write_text('mutation')\n" +
                       "print(" + repr(json.dumps(IDLE)) + ")\n")
        cli.chmod(0o700)
        self.helper = self.release / "decky-install"
        self.helper.write_text("#!" + sys.executable + "\n" +
                               "import json,os,stat\nfrom pathlib import Path\n" +
                               "path=Path(__file__);info=path.stat();root=path.parent\n" +
                               "value={'inode':info.st_ino,'ctime_ns':info.st_ctime_ns,'mode':stat.S_IMODE(info.st_mode),'caches':sorted(str(p.relative_to(root)) for p in root.rglob('__pycache__'))}\n" +
                               "(Path(os.environ['HOME'])/'helper-observation.json').write_text(json.dumps(value))\n" +
                               "print(json.dumps({'ok':True,'removed':True}))\n")
        self.helper.chmod(0o700)

    def command(self, flag, *scope):
        env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": "", "XDG_STATE_HOME": "",
               "XDG_DATA_HOME": "", "XDG_CACHE_HOME": "", "DECKY_HOME": ""}
        return subprocess.run([sys.executable, flag, str(self.release / "uninstall.py"), *scope, "--yes", "--json"],
                              env=env, text=True, capture_output=True, timeout=15)

    def assert_only_read_observations(self, count=3):
        calls = [json.loads(line) for line in (self.home / "calls.jsonl").read_text().splitlines()]
        self.assertEqual(calls, ["status"] * count)
        self.assertFalse((self.home / ".local/state/obsgod/diagnostics/unexpected-restart").exists())

    def test_isolated_python_self_uninstall_keeps_helper_identity_and_imports_read_only(self):
        before = self.helper.stat()
        result = self.command("-I", "--purge-settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        observed = json.loads((self.home / "helper-observation.json").read_text())
        self.assertEqual(observed["inode"], before.st_ino)
        self.assertEqual(observed["ctime_ns"], before.st_ctime_ns)
        self.assertEqual(observed["mode"], 0o700)
        self.assertEqual(observed["caches"], [])
        self.assertFalse(self.release.exists())
        self.assert_only_read_observations()

    def test_bytecode_disabled_python_self_wipe_preserves_coordination_and_media(self):
        before = self.helper.stat()
        result = self.command("-B", "--wipe")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads((self.home / "helper-observation.json").read_text())
        self.assertEqual((observed["inode"], observed["ctime_ns"]), (before.st_ino, before.st_ctime_ns))
        self.assertEqual(observed["caches"], [])
        self.assertEqual({path.name for path in self.base.iterdir()}, {"update.lock", "install.lock"})
        self.assertEqual({path.name for path in (self.home / ".local/state/obsgod").iterdir()}, {"control.lock"})
        self.assertTrue((self.home / "Videos/OBSGod/keep.mkv").exists())
        self.assertTrue(json.loads(result.stdout)["export"]["preserved_after_wipe"])
        self.assert_only_read_observations(4)

    def test_configured_but_absent_reset_does_not_record_an_unnecessary_restart(self):
        result = self.command("-I", "--reset")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.release.exists())
        self.assertFalse((self.home / "helper-observation.json").exists())
        self.assertFalse((self.release / "__pycache__").exists())
        self.assert_only_read_observations()

    def test_helper_mode_normalization_still_invalidates_the_reviewed_release(self):
        self.helper.chmod(0o755)
        before = self.helper.stat()
        result = self.command("-I", "--purge-settings")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        answer = json.loads(result.stdout)
        self.assertIn("selected path changed", answer["message"])
        self.assertEqual(answer["removed"], [])
        after = self.helper.stat()
        self.assertEqual(after.st_ino, before.st_ino)
        self.assertNotEqual(after.st_ctime_ns, before.st_ctime_ns)
        self.assertEqual(after.st_mode & 0o7777, 0o700)
        self.assertFalse((self.release / "__pycache__").exists())
        self.assertTrue((self.home / ".config/obsgod/secrets.json").exists())
        # Only a fresh, explicit inventory can authorize removing this changed
        # release; a second execution has no normalization left to perform.
        retried = self.command("-I", "--purge-settings")
        self.assertEqual(retried.returncode, 0, retried.stdout + retried.stderr)


if __name__ == "__main__":
    unittest.main()
