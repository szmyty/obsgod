"""Real process locks, immutable cleanup previews, and explicit legacy retirement."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import uninstall
import paths

IDLE = {"ok": True, "configured": True, "state": "stopped", "output_known": True,
        "process": "absent", "stream": {"active": False, "reconnecting": False},
        "recording": False, "media": {"known": True, "replay_active": False,
                                      "recording": {"active": False, "paused": False}}}

PROBE = """import fcntl,json,os,sys
fd=os.open(sys.argv[1],os.O_RDWR)
print('opened',flush=True)
if sys.argv[2]=='wait':
 fcntl.flock(fd,fcntl.LOCK_EX)
 print(json.dumps({'acquired':True,'inode':os.fstat(fd).st_ino}),flush=True)
 sys.stdin.readline()
else:
 try:
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  acquired=True
 except BlockingIOError:acquired=False
 print(json.dumps({'acquired':acquired,'inode':os.fstat(fd).st_ino}),flush=True)
"""


class CleanupCoordination(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "player"
        self.home.mkdir(mode=0o700)
        self.base = self.home / ".local/share/obsgod"
        self.state = self.home / ".local/state/obsgod"
        self.config = self.home / ".config/obsgod"
        self.enterContext(patch.dict(os.environ, {"HOME": str(self.home), **{k: "" for k in paths.DEFAULTS}}))
        self.cli = self.enterContext(patch.object(uninstall, "run_cli", return_value=IDLE))
        self.plugin = self.enterContext(patch.object(uninstall, "remove_plugin"))
        self.waiters = []
        self.addCleanup(self.close_waiters)

    def close_waiters(self):
        for process in self.waiters:
            if process.poll() is None:
                process.communicate("release\n", timeout=5)
            else:
                process.communicate(timeout=5)

    def write(self, relative, content="fixture"):
        path = self.home / relative
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_text(content)
        return path

    def fixture(self):
        self.write(".local/share/obsgod/releases/v1/obsgod")
        (self.base / "current").symlink_to(self.base / "releases/v1")
        alias = self.home / ".local/bin/obsgod"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.base / "current/obsgod")
        for name in ("setup", "update", "uninstall"):
            self.write(".local/share/applications/obsgod-" + name + ".desktop", "X-OBSGod-Managed=true")
        self.write(".local/share/obsgod/backups/old/secrets.json", "private old fixture")
        self.write(".config/obsgod/secrets.json", "private current fixture")
        self.write(".local/state/obsgod/history.json")
        self.write(".cache/obsgod/keep")
        self.write("Videos/OBSGod/2026-11-14 00-00-00.mkv", "media sentinel")
        self.write(".var/app/com.obsproject.Studio/config/obs-studio/ordinary.json", "ordinary sentinel")
        self.write(".var/app/com.obsproject.Studio/config/obsgod/managed.json")
        for kind in ("plugins", "settings", "data", "logs"):
            self.write("homebrew/" + kind + "/obsgod/keep", "active plugin sentinel")
            self.write("homebrew/" + kind + "/OtherPlugin/keep", "unrelated sentinel")
        for lock in (self.base / "update.lock", self.base / "install.lock", self.state / "control.lock"):
            lock.touch(mode=0o600)
            lock.chmod(0o600)

    def probe(self, lock):
        result = subprocess.run([sys.executable, "-c", PROBE, str(lock), "probe"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def waiter(self, lock):
        process = subprocess.Popen([sys.executable, "-c", PROBE, str(lock), "wait"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.waiters.append(process)
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], "waiter did not open lock")
        self.assertEqual(process.stdout.readline().strip(), "opened")
        return process

    def test_wipe_preserves_all_generations_during_each_deletion_and_on_retry(self):
        self.fixture()
        locks = [self.base / "update.lock", self.base / "install.lock", self.state / "control.lock"]
        inodes = {str(lock): lock.stat().st_ino for lock in locks}
        real_unlink, real_rmtree = Path.unlink, shutil.rmtree
        started = False
        checks = []
        def boundary():
            nonlocal started
            if not started:
                started = True
                for lock in locks:
                    self.waiter(lock)
            for lock in locks:
                self.assertEqual(lock.stat().st_ino, inodes[str(lock)])
                self.assertFalse(self.probe(lock)["acquired"])
                checks.append(str(lock))
        def unlink(path, *args, **kwargs):
            real_unlink(path, *args, **kwargs)
            boundary()
        def rmtree(path, *args, **kwargs):
            real_rmtree(path, *args, **kwargs)
            boundary()
        plan = uninstall.build_plan(self.home, "wipe")
        preview = uninstall.describe(plan)
        self.assertIn("stable updater coordination", preview)
        self.assertIn("stable installation coordination", preview)
        self.assertIn("stable control coordination", preview)
        with patch.object(Path, "unlink", unlink), patch.object(uninstall.shutil, "rmtree", rmtree):
            uninstall.apply_plan(plan, self.home)
        self.assertGreater(len(checks), len(locks))
        for process, lock in zip(self.waiters, locks):
            self.assertTrue(select.select([process.stdout], [], [], 5)[0])
            acquired = json.loads(process.stdout.readline())
            self.assertEqual(acquired["inode"], inodes[str(lock)])
            self.assertFalse(self.probe(lock)["acquired"])
            process.communicate("release\n", timeout=5)
            self.assertTrue(self.probe(lock)["acquired"])
        uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.assertEqual({str(lock): lock.stat().st_ino for lock in locks}, inodes)
        self.assertTrue((self.home / "Videos/OBSGod/2026-11-14 00-00-00.mkv").exists())
        self.assertTrue((self.home / "homebrew/settings/OtherPlugin/keep").exists())
        self.assertTrue((self.home / ".var/app/com.obsproject.Studio/config/obs-studio/ordinary.json").exists())

    def test_busy_updater_fails_before_other_locks_or_deletion(self):
        self.fixture()
        (self.base / "install.lock").unlink()
        (self.state / "control.lock").unlink()
        lock = self.base / "update.lock"
        with lock.open("r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            with self.assertRaisesRegex(uninstall.RemovalError, "busy"):
                uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.assertFalse((self.base / "install.lock").exists())
        self.assertFalse((self.state / "control.lock").exists())
        self.plugin.assert_not_called()
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertTrue((self.base / "current/obsgod").exists())

    def test_changed_ancestor_or_tree_refuses_before_locks_and_helpers(self):
        for mutation in ("mode", "inode", "file", "symlink", "new-file"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "player"
                home.mkdir(mode=0o700)
                config = home / ".config/obsgod"
                config.mkdir(parents=True)
                (config / "secrets.json").write_text("preserve")
                (home / "homebrew").mkdir()
                with patch.dict(os.environ, {"HOME": str(home)}):
                    plan = uninstall.build_plan(home, "wipe")
                    if mutation == "mode":config.parent.chmod(0o770)
                    elif mutation == "inode":
                        config.parent.rename(home / "old-config")
                        config.mkdir(parents=True)
                        (config / "secrets.json").write_text("replacement")
                    elif mutation == "file":(config / "secrets.json").write_text("changed after preview")
                    elif mutation == "symlink":
                        config.rename(config.parent / "saved")
                        config.symlink_to(config.parent / "saved")
                    else:(config / "added-after-preview").write_text("unapproved")
                    with self.assertRaises(uninstall.RemovalError):uninstall.apply_plan(plan, home)
                    self.assertFalse((home / ".local/share/obsgod/update.lock").exists())
                    self.assertTrue((config / "secrets.json").exists())
        self.cli.assert_not_called()
        self.plugin.assert_not_called()

    def test_partial_failure_keeps_locks_and_lists_remaining_for_fresh_preview(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, "wipe")
        old_inodes = {str(lock): lock.stat().st_ino for lock in (self.base / "update.lock", self.base / "install.lock", self.state / "control.lock")}
        actual = shutil.rmtree
        def fail_config(path, *args, **kwargs):
            if Path(path) == self.config:raise OSError("fixture deletion denied")
            return actual(path, *args, **kwargs)
        with patch.object(uninstall.shutil, "rmtree", fail_config), self.assertRaises(uninstall.RemovalError) as caught:
            uninstall.apply_plan(plan, self.home)
        self.assertGreater(len(caught.exception.completed), 0)
        self.assertIn(str(self.config), caught.exception.remaining)
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertEqual({name: Path(name).stat().st_ino for name in old_inodes}, old_inodes)
        uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.assertFalse(self.config.exists())
        self.assertEqual({name: Path(name).stat().st_ino for name in old_inodes}, old_inodes)

    def test_helper_time_path_changes_are_rejected_before_selected_deletions(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, "wipe")
        def replace_selected(*_args):
            original = self.config / "secrets.json"
            original.rename(self.config / "original-preserved.json")
            original.write_text("replacement after helper")
        self.plugin.side_effect = replace_selected
        with self.assertRaisesRegex(uninstall.RemovalError, "changed"):
            uninstall.apply_plan(plan, self.home)
        self.assertTrue((self.config / "original-preserved.json").exists())
        self.assertTrue((self.base / "current/obsgod").exists())
        self.assertTrue((self.home / ".local/bin/obsgod").is_symlink())

    def test_created_and_preexisting_coordination_roots_and_locks_are_pinned(self):
        for mutation in ("fresh-root", "existing-root", "existing-lock"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "player"
                home.mkdir(mode=0o700)
                state = home / ".local/state/obsgod"
                if mutation != "fresh-root":
                    state.mkdir(parents=True)
                    (state / "sentinel").write_text("preserved")
                with patch.dict(os.environ, {"HOME": str(home)}):
                    plan = uninstall.build_plan(home)
                    def replace(*_args):
                        lock = state / "control.lock"
                        original = lock.stat().st_ino
                        if mutation == "existing-lock":lock.unlink()
                        else:
                            state.rename(home / "original-state")
                            state.mkdir(mode=0o700)
                        lock.touch(mode=0o600)
                        self.assertNotEqual(lock.stat().st_ino, original)
                        self.assertTrue(self.probe(lock)["acquired"])
                    self.plugin.side_effect = replace
                    with self.assertRaisesRegex(uninstall.RemovalError, "changed"):
                        uninstall.apply_plan(plan, home)
                    preserved = state if mutation == "existing-lock" else home / "original-state"
                    if mutation != "fresh-root":self.assertTrue((preserved / "sentinel").exists())

    def test_lock_replacement_at_selected_deletion_boundary_stops_remaining_deletions(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, "wipe")
        original_unlink = Path.unlink
        alias = self.home / ".local/bin/obsgod"
        def replace_after_alias(path, *args, **kwargs):
            original_unlink(path, *args, **kwargs)
            if path == alias:
                lock = self.state / "control.lock"
                original_unlink(lock)
                lock.touch(mode=0o600)
        with patch.object(Path, "unlink", replace_after_alias), self.assertRaisesRegex(uninstall.RemovalError, "changed"):
            uninstall.apply_plan(plan, self.home)
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertTrue((self.base / "current/obsgod").exists())

    def test_safe_alias_sticky_xdg_and_coincident_coordination_roots(self):
        root = self.home / "shared-data"
        root.mkdir(mode=0o1777)
        root.chmod(0o1777)
        base = root / "obsgod"
        base.mkdir(mode=0o700)
        (base / "owned.json").write_text("selected fixture")
        (self.home / "homebrew").mkdir()
        alias = Path(self.temp.name) / "player-alias"
        alias.symlink_to(self.home)
        values = {"HOME": str(alias), "XDG_DATA_HOME": str(alias / "shared-data"),
                  "XDG_STATE_HOME": str(alias / "shared-data")}
        with patch.dict(os.environ, values):
            plan = uninstall.build_plan(self.home, "wipe")
            self.assertEqual(sum(entry["path"] == str(base) for entry in plan["entries"]), 1)
            uninstall.apply_plan(plan, self.home)
        self.assertEqual({path.name for path in base.iterdir()}, {"update.lock", "install.lock", "control.lock"})

    def test_legacy_retirement_preserves_plugin_shared_data_backups_and_media(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, legacy_app_only=True)
        self.assertFalse(plan["remove_plugin"])
        selected = {entry["path"] for entry in plan["entries"]}
        self.assertEqual(selected, {str(self.home / ".local/bin/obsgod"), str(self.base / "current"), str(self.base / "releases"),
                                  *[str(self.home / (".local/share/applications/obsgod-" + name + ".desktop")) for name in ("setup", "update", "uninstall")]})
        uninstall.apply_plan(plan, self.home)
        self.assertFalse((self.base / "current").exists())
        self.assertFalse((self.base / "releases").exists())
        for sentinel in ("homebrew/plugins/obsgod/keep", ".config/obsgod/secrets.json", ".local/state/obsgod/history.json", ".cache/obsgod/keep",
                         ".local/share/obsgod/backups/old/secrets.json", "Videos/OBSGod/2026-11-14 00-00-00.mkv"):
            self.assertTrue((self.home / sentinel).exists(), sentinel)
        self.plugin.assert_not_called()
        self.assertEqual([call.args[0] for call in self.cli.call_args_list], ["status", "status", "status"])

    def test_legacy_retirement_never_closes_running_obs_or_accepts_active_unknown(self):
        self.fixture()
        for state in ({**IDLE, "process": "running"}, {**IDLE, "output_known": False},
                      {**IDLE, "stream": {"active": True}}, {**IDLE, "stream": {"active": False, "reconnecting": True}},
                      {**IDLE, "media": {"known": True, "replay_active": False, "recording": {"active": False, "paused": True}}}):
            self.cli.return_value = state
            with self.assertRaises(uninstall.RemovalError):
                uninstall.apply_plan(uninstall.build_plan(self.home, legacy_app_only=True), self.home)
            self.assertTrue((self.base / "current/obsgod").exists())
        self.assertTrue(all(call.args[0] == "status" for call in self.cli.call_args_list))
        self.plugin.assert_not_called()

    def test_legacy_retirement_rejects_destructive_flags_and_dry_run_is_offline(self):
        self.fixture()
        for options in ({"mode": "wipe"}, {"mode": "reset"}, {"purge": True}, {"delete_recordings": True}, {"recordings": ["anything"]}):
            with self.assertRaises(uninstall.RemovalError):uninstall.build_plan(self.home, legacy_app_only=True, **options)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(uninstall.main(["--legacy-app-only", "--dry-run", "--json"]), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result["legacy_app_only"])
        self.assertFalse(result["remove_plugin"])
        self.cli.assert_not_called()
        self.plugin.assert_not_called()

    def test_running_idle_close_that_changes_state_requires_a_new_preview(self):
        self.fixture()
        process = "running"
        def cli(action, **_kwargs):
            nonlocal process
            if action == "restart":
                self.write(".local/state/obsgod/diagnostics/close.json", "owned close observation")
                process = "absent"
                return {"ok": True}
            return {**IDLE, "process": process}
        self.cli.side_effect = cli
        with self.assertRaisesRegex(uninstall.RemovalError, "selected path changed"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "reset"), self.home)
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertTrue((self.state / "diagnostics/close.json").exists())
        self.plugin.assert_not_called()
        uninstall.apply_plan(uninstall.build_plan(self.home, "reset"), self.home)
        self.assertFalse(self.config.exists())
        self.assertEqual(sum(call.args[0] == "restart" for call in self.cli.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
