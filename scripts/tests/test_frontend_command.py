"""Exercise actual child identity/output ownership and unsafe-path refusal."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("frontend_command", ROOT / "scripts/frontend-command.py")
FRONTEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FRONTEND)


class FrontendCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontend-owner-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.frontend = self.root / "steamdeck" / "decky"
        self.frontend.mkdir(parents=True)
        self.uid, self.gid = (ROOT.stat().st_uid, ROOT.stat().st_gid) if os.getuid() == 0 else (os.getuid(), os.getgid())
        self.assertNotEqual(self.uid, 0, "Run fixtures from a user-owned checkout")
        if os.getuid() == 0:
            for path in (self.root, self.root / "steamdeck", self.frontend):
                os.chown(path, self.uid, self.gid)
        self.npm = self.root / "fake-npm"
        self.npm.write_text("#!" + sys.executable + "\n" + """
import json,os,pathlib,sys
if sys.argv[1:]==['run','build']:
    output=pathlib.Path('dist'); output.mkdir(exist_ok=True)
    (output/'index.js').write_text('reproducible frontend output\\n')
print(json.dumps({'arguments':sys.argv[1:],'uid':os.getuid(),'gid':os.getgid(),
  'groups':os.getgroups(),'home_mode':pathlib.Path.home().stat().st_mode&511,
  'temp_mode':pathlib.Path(os.environ['TMPDIR']).stat().st_mode&511,
  'sudo_present':any(k.startswith('SUDO_') for k in os.environ),
  'xdg_present':any(k in os.environ for k in ['XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR']),
  'registry':os.environ.get('npm_config_registry')}))
raise SystemExit(int(os.environ.get('FRONTEND_FIXTURE_EXIT','0')))
""")
        self.npm.chmod(0o755)

    def run_action(self, action):
        # A pipe sees output from the real exec'd command; Python redirect_stdout
        # alone would only capture the parent's identity announcement.
        read, write = os.pipe()
        saved = os.dup(1)
        try:
            sys.stdout.flush()
            os.dup2(write, 1)
            os.close(write)
            result = FRONTEND.run_frontend(action, root=self.root, npm=str(self.npm))
            sys.stdout.flush()
        finally:
            os.dup2(saved, 1)
            os.close(saved)
        with os.fdopen(read) as output:
            lines = output.read().splitlines()
        return result, json.loads(lines[-1])

    def test_absent_then_reused_output_stays_owned_by_real_child(self):
        preserved_env = {"SUDO_UID": "0", "SUDO_COMMAND": "fixture", "XDG_CACHE_HOME": "/root/fixture",
                         "XDG_RUNTIME_DIR": "/root/runtime-fixture",
                         "npm_config_registry": "https://registry.example.invalid"}
        hashes = []
        with patch.dict(os.environ, preserved_env):
            for _ in range(2):
                result, child = self.run_action("build")
                self.assertEqual(result, 0)
                self.assertEqual((child["uid"], child["gid"]), (self.uid, self.gid))
                if os.getuid() == 0:
                    self.assertEqual(child["groups"], [])
                self.assertEqual(child["home_mode"], 0o700)
                self.assertEqual(child["temp_mode"], 0o700)
                self.assertFalse(child["sudo_present"])
                self.assertFalse(child["xdg_present"])
                self.assertEqual(child["registry"], preserved_env["npm_config_registry"])
                for path in (self.frontend / "dist", self.frontend / "dist/index.js"):
                    self.assertEqual(path.stat().st_uid, self.uid)
                hashes.append((self.frontend / "dist/index.js").read_bytes())
        self.assertEqual(hashes[0], hashes[1])

    def test_fixed_commands_and_failure_exit_propagation(self):
        for action, arguments in FRONTEND.COMMANDS.items():
            with self.subTest(action=action), patch.dict(os.environ, {"FRONTEND_FIXTURE_EXIT": "37"}):
                result, child = self.run_action(action)
                self.assertEqual(result, 37)
                self.assertEqual(child["arguments"], arguments)

    def test_symlink_and_non_directory_outputs_are_preserved(self):
        output = self.frontend / "dist"
        target = self.root / "outside"
        target.mkdir()
        sentinel = target / "keep"
        sentinel.write_text("unchanged")
        output.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "symlink"), patch.object(FRONTEND.subprocess, "run") as child:
            FRONTEND.run_frontend("build", root=self.root, npm=str(self.npm))
        child.assert_not_called()
        self.assertTrue(output.is_symlink())
        self.assertEqual(sentinel.read_text(), "unchanged")
        output.unlink()
        output.write_text("not a directory")
        if os.getuid() == 0:
            os.chown(output, self.uid, self.gid)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "directory"):
            FRONTEND.validate_output(self.root, self.uid)
        self.assertEqual(output.read_text(), "not a directory")

    def test_linked_special_and_foreign_entries_are_not_repaired(self):
        output = self.frontend / "dist"
        output.mkdir()
        if os.getuid() == 0:
            os.chown(output, self.uid, self.gid)
        foreign = output / "foreign"
        foreign.write_text("keep")
        before = foreign.stat()
        # With root ACT this is an actual root-owned output versus checkout UID.
        # On a normal host, validate against another intended owner directly.
        wanted = self.uid if os.getuid() == 0 else self.uid + 1
        if os.getuid() == 0:
            with self.assertRaisesRegex(FRONTEND.FrontendError, "foreign"), patch.object(FRONTEND.subprocess, "run") as child:
                FRONTEND.run_frontend("build", root=self.root, npm=str(self.npm))
            child.assert_not_called()
        else:
            with self.assertRaisesRegex(FRONTEND.FrontendError, "foreign"):
                FRONTEND.validate_output(self.root, wanted)
        after = foreign.stat()
        self.assertEqual((before.st_uid, before.st_gid, before.st_mode), (after.st_uid, after.st_gid, after.st_mode))
        self.assertEqual(foreign.read_text(), "keep")
        foreign.unlink()
        target = self.root / "target"
        target.write_text("keep")
        if os.getuid() == 0:
            os.chown(target, self.uid, self.gid)
        os.link(target, output / "hardlink")
        with self.assertRaisesRegex(FRONTEND.FrontendError, "linked"):
            FRONTEND.validate_output(self.root, self.uid)
        self.assertEqual(target.read_text(), "keep")
        (output / "hardlink").unlink()
        os.mkfifo(output / "fifo")
        if os.getuid() == 0:
            os.chown(output / "fifo", self.uid, self.gid)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "non-regular"):
            FRONTEND.validate_output(self.root, self.uid)
        self.assertTrue(stat.S_ISFIFO((output / "fifo").stat().st_mode))

    def test_symlink_frontend_ancestor_is_refused(self):
        self.frontend.rmdir()
        target = self.root / "elsewhere"
        target.mkdir()
        self.frontend.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "unsafe"):
            FRONTEND.validate_output(self.root, self.uid)
        self.assertTrue(self.frontend.is_symlink())

    def test_root_owned_checkout_is_refused_without_identity_guess(self):
        with self.assertRaisesRegex(FRONTEND.FrontendError, "non-root-owned"):
            FRONTEND.checkout_identity(Path("/tmp"))


if __name__ == "__main__":
    unittest.main()
