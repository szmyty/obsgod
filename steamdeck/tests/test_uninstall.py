"""Real temporary-file removal fixtures: output, ownership and data boundaries."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import uninstall
import paths


class RemovalSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {"HOME": str(self.home), **{k: "" for k in paths.DEFAULTS}})
        self.env.start()
        self.base = self.home / ".local/share/obsgod"
        self.config = self.home / ".config/obsgod"
        self.state = self.home / ".local/state/obsgod"
        self.cache = self.home / ".cache/obsgod"
        self.obs = self.home / ".var/app/com.obsproject.Studio/config/obsgod"
        self.videos = self.home / "Videos/OBSGod"
        self.idle = {"ok": True, "configured": True, "state": "stopped", "stream": {"active": False}, "recording": False, "output_known": True, "process": "absent"}
        self.cli = patch.object(uninstall, "run_cli", return_value=self.idle)
        self.run_cli = self.cli.start()
        self.real_remove_plugin = uninstall.remove_plugin
        self.plugin = patch.object(uninstall, "remove_plugin")
        self.remove_plugin = self.plugin.start()

    def tearDown(self):
        self.plugin.stop()
        self.cli.stop()
        self.env.stop()
        self.temp.cleanup()

    def write(self, relative, content="fixture"):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def fixture(self):
        self.write(".local/share/obsgod/releases/v1/obsgod")
        (self.base / "current").symlink_to(self.base / "releases/v1")
        alias = self.home / ".local/bin/obsgod"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.base / "current/obsgod")
        self.write(".local/share/applications/obsgod-setup.desktop", "X-OBSGod-Managed=true")
        self.write(".local/share/applications/obsgod-uninstall.desktop", "X-OBSGod-Managed=true")
        self.write(".config/obsgod/secrets.json", "private fixture")
        self.write(".var/app/com.obsproject.Studio/config/obsgod/obs-studio/config.json")
        self.write(".var/app/com.obsproject.Studio/config/obs-studio/ordinary.json", "ordinary OBS")
        self.write(".local/state/obsgod/diagnostics/events.json")
        self.write(".cache/obsgod/cache")
        self.write(".local/share/obsgod/backups/old/secrets.json", "old private fixture")
        self.write("Videos/OBSGod/2026-11-12 11-30-00.mkv", "recorded clip")
        self.write("Videos/OBSGod/other.mkv", "owner-added media")
        self.write("Videos/OBSGod/notes.txt", "unrelated text")
        for kind in ["settings", "data", "logs"]:
            self.write("homebrew/" + kind + "/obsgod/owned", "adapter data")
            self.write("homebrew/" + kind + "/OtherPlugin/keep", "unrelated plugin")

    def test_default_removes_app_and_plugin_but_preserves_private_data_and_media(self):
        self.fixture()
        plan = uninstall.build_plan(self.home)
        uninstall.apply_plan(plan, self.home)
        self.remove_plugin.assert_called_once_with(self.home, str(self.home / "homebrew/plugins/obsgod"))
        self.assertFalse((self.base / "current").is_symlink())
        self.assertFalse((self.base / "releases").exists())
        self.assertFalse((self.home / ".local/bin/obsgod").is_symlink())
        for path in [self.config, self.obs, self.state, self.cache, self.base / "backups", self.videos]:
            self.assertTrue(path.exists(), path)
        for kind in ["settings", "data", "logs"]:
            self.assertTrue((self.home / "homebrew" / kind / "obsgod/owned").exists())
        self.assertTrue((self.obs.parent / "obs-studio/ordinary.json").exists())
        self.assertEqual([x.args[0] for x in self.run_cli.call_args_list], ["status", "restart", "status", "status"])

    def test_wipe_removes_owned_credentials_backups_data_but_not_recordings_or_ordinary_obs(self):
        self.fixture()
        uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        for path in [self.base, self.config, self.obs, self.state, self.cache]:
            self.assertFalse(path.exists(), path)
        for kind in ["settings", "data", "logs"]:
            self.assertFalse((self.home / "homebrew" / kind / "obsgod").exists())
            self.assertTrue((self.home / "homebrew" / kind / "OtherPlugin/keep").exists())
        self.assertTrue((self.videos / "other.mkv").exists())
        self.assertTrue((self.obs.parent / "obs-studio/ordinary.json").exists())

    def test_reset_retains_app_plugin_and_same_control_lock_inode(self):
        self.fixture()
        lock = self.write(".local/state/obsgod/control.lock")
        inode = lock.stat().st_ino
        uninstall.apply_plan(uninstall.build_plan(self.home, "reset"), self.home)
        self.remove_plugin.assert_not_called()
        self.assertTrue((self.base / "current/obsgod").exists())
        self.assertTrue((self.base / "backups/old/secrets.json").exists())
        self.assertEqual(lock.stat().st_ino, inode)
        self.assertEqual(list(self.state.iterdir()), [lock])
        for path in [self.config, self.obs, self.cache]:
            self.assertFalse(path.exists())

    def test_media_requires_separate_selection_and_automatic_selection_excludes_other_files(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, "wipe", delete_recordings=True)
        chosen = [x["path"] for x in plan["entries"] if x["label"] == "Explicitly selected recording"]
        self.assertEqual(chosen, [str(self.videos / "2026-11-12 11-30-00.mkv")])
        uninstall.apply_plan(plan, self.home)
        self.assertFalse((self.videos / "2026-11-12 11-30-00.mkv").exists())
        self.assertTrue((self.videos / "other.mkv").exists())
        self.assertTrue((self.videos / "notes.txt").exists())
        explicit = uninstall.build_plan(self.home, recordings=[str(self.videos / "other.mkv")])
        self.assertTrue(any(x["path"] == str(self.videos / "other.mkv") for x in explicit["entries"]))
        for value in [str(self.home / "Videos/other.mkv"), "other.mkv", str(self.videos / "notes.txt")]:
            with self.assertRaises(uninstall.RemovalError):
                uninstall.build_plan(self.home, recordings=[value])

    def test_unknown_recording_busy_or_malformed_output_stops_before_plugin_or_file_changes(self):
        self.fixture()
        cases = [{"ok": False, "state": "unknown"}, {**self.idle, "stream": {"active": True}},
                 {**self.idle, "recording": True}, {**self.idle, "recording": {"active": True}},
                 {**self.idle, "recording": []}, {**self.idle, "stream": []},
                 {**self.idle, "operation": "start"}, {**self.idle, "output_known": False},
                 {"ok": True, "state": "stopped"},
                 {k:v for k,v in self.idle.items() if k != "output_known"},
                 {**self.idle, "stream": {}}, {**self.idle, "process": "unknown"}]
        for state in cases:
            self.run_cli.return_value = state
            with self.assertRaises(uninstall.RemovalError):
                uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
            self.assertTrue((self.config / "secrets.json").exists())
        self.remove_plugin.assert_not_called()

    def test_dry_run_is_offline_nonmutating_machine_readable_and_includes_selection(self):
        self.fixture()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = uninstall.main(["--wipe", "--delete-recordings", "--dry-run", "--json"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(result["dry_run"])
        self.assertTrue(any("secrets" in x["label"].lower() or "Settings" in x["label"] for x in result["entries"]))
        self.run_cli.assert_not_called()
        self.remove_plugin.assert_not_called()
        self.assertFalse((self.base / "install.lock").exists())

    def test_confirmation_cancel_never_contacts_obs_or_decky(self):
        self.fixture()
        with patch.object(uninstall, "confirm", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            code = uninstall.main(["--wipe", "--json"])
        self.assertEqual(code, 0)
        self.run_cli.assert_not_called()
        self.remove_plugin.assert_not_called()

    def test_symlink_escape_nested_link_special_file_or_foreign_owner_refused(self):
        self.fixture()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        linked = self.config / "escape"
        linked.symlink_to(outside)
        with self.assertRaises(uninstall.RemovalError):
            uninstall.build_plan(self.home, "wipe")
        linked.unlink()
        fifo = self.config / "special"
        os.mkfifo(fifo)
        with self.assertRaises(uninstall.RemovalError):
            uninstall.build_plan(self.home, "wipe")
        fifo.unlink()
        with patch.object(uninstall.os, "getuid", return_value=os.getuid() + 1), self.assertRaises(uninstall.RemovalError):
            uninstall.build_plan(self.home, "wipe")
        self.remove_plugin.assert_not_called()

    def test_custom_xdg_roots_and_legacy_conflict(self):
        env = {"XDG_DATA_HOME": str(self.home / "data"), "XDG_CONFIG_HOME": str(self.home / "cfg"), "XDG_STATE_HOME": str(self.home / "state"), "XDG_CACHE_HOME": str(self.home / "cache")}
        base, apps = paths.app_directories(self.home, env)
        self.assertEqual(base, self.home / "data/obsgod")
        self.assertEqual(apps, self.home / "data/applications")
        for value in ["relative", "bad\npath"]:
            with self.assertRaises(ValueError):
                paths.app_directories(self.home, {"XDG_DATA_HOME": value})
        self.fixture()
        self.assertEqual(paths.app_directories(self.home, env)[0], self.base)
        base.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Two OBSGod"):
            paths.app_directories(self.home, env)

    def test_changed_alias_or_removal_failure_is_reported_as_partial(self):
        self.fixture()
        plan = uninstall.build_plan(self.home, "wipe")
        alias = self.home / ".local/bin/obsgod"
        alias.unlink()
        alias.symlink_to(self.home / "unrelated")
        with self.assertRaisesRegex(uninstall.RemovalError, "partial"):
            uninstall.apply_plan(plan, self.home)
        self.assertTrue((self.config / "secrets.json").exists())

    def test_control_lock_blocks_reset_without_deleting_config(self):
        self.fixture()
        lock = self.write(".local/state/obsgod/control.lock")
        with lock.open("w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(uninstall.RemovalError, "partial"):
                uninstall.apply_plan(uninstall.build_plan(self.home, "reset"), self.home)
        self.assertTrue((self.config / "secrets.json").exists())

    def test_busy_control_lock_never_removes_plugin_or_selected_files(self):
        self.fixture()
        lock = self.write(".local/state/obsgod/control.lock")
        with lock.open("w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(uninstall.RemovalError, "partial"):
                uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.remove_plugin.assert_not_called()
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertTrue((self.base / "current/obsgod").exists())

    def test_reappearing_idle_obs_is_not_removed_under_the_control_lock(self):
        self.fixture()
        self.run_cli.side_effect = [self.idle, {"ok": True}, self.idle,
                                    {**self.idle, "process": "running"}]
        with self.assertRaisesRegex(uninstall.RemovalError, "partial"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.remove_plugin.assert_not_called()
        self.assertTrue((self.config / "secrets.json").exists())

    def test_mid_plan_interrupt_reports_failure_and_preserves_remaining_data(self):
        self.fixture()
        alias = self.home / ".local/bin/obsgod"
        original = Path.unlink
        def interrupt_after_first_delete(path, *args, **kwargs):
            if path == alias:
                original(path, *args, **kwargs)
                raise KeyboardInterrupt()
            return original(path, *args, **kwargs)
        output = io.StringIO()
        with patch.object(Path, "unlink", interrupt_after_first_delete), contextlib.redirect_stdout(output):
            result = uninstall.main(["--wipe", "--yes", "--json"])
        answer = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertFalse(answer["ok"])
        self.assertIn("interrupted", answer["message"])
        self.assertFalse(alias.is_symlink())
        self.assertTrue((self.config / "secrets.json").exists())
        self.assertTrue((self.base / "current/obsgod").exists())
        retry = uninstall.build_plan(self.home, "wipe")
        self.assertFalse(any(entry["path"] == str(alias) for entry in retry["entries"]))

    def test_unloaded_orphan_directory_is_retried_and_absence_must_be_verified(self):
        folder = self.home / "homebrew/plugins/obsgod"
        folder.mkdir(parents=True)
        (folder / "plugin.json").write_text('{"name":"OBSGod"}')
        helper = Mock(return_value={"ok": True, "removed": True})
        with patch.object(uninstall, "_sibling", return_value=SimpleNamespace(helper_request=helper)):
            with self.assertRaisesRegex(uninstall.RemovalError, "files remain"):
                self.real_remove_plugin(self.home)
            helper.assert_called_with("uninstall", uninstall_existing=True)
            def finish(*args, **kwargs):
                import shutil
                shutil.rmtree(folder)
                return {"ok": True, "removed": True}
            helper.side_effect = finish
            self.real_remove_plugin(self.home)
            self.assertFalse(folder.exists())
            self.assertEqual(helper.call_count, 2)

    def test_fresh_removal_leaves_no_new_owned_lock_namespaces(self):
        self.run_cli.return_value = {**self.idle, "configured": False}
        uninstall.apply_plan(uninstall.build_plan(self.home), self.home)
        self.assertFalse(self.base.exists())
        self.assertFalse(self.state.exists())

    def test_wipe_unknown_decky_root_has_visible_gate_and_never_mutates(self):
        self.write(".config/obsgod/secrets.json", "preserved private fixture")
        plan = uninstall.build_plan(self.home, "wipe")
        self.assertEqual(plan["decky_root"], str(self.home / "homebrew"))
        self.assertTrue(plan["pending_gates"])
        self.assertIn("DECKY_HOME", uninstall.describe(plan))
        with self.assertRaisesRegex(uninstall.RemovalError, "DECKY_HOME"):
            uninstall.apply_plan(plan, self.home)
        self.run_cli.assert_not_called()
        self.remove_plugin.assert_not_called()
        self.assertTrue((self.config / "secrets.json").exists())

    def test_custom_decky_roots_and_inconsistent_plugin_paths(self):
        root = self.home / "custom Decky"
        for kind in ["settings", "data", "logs"]:
            path = root / kind / "obsgod"
            path.mkdir(parents=True)
            (path / "owned").write_text("adapter fixture")
        env = {"DECKY_HOME": str(root)}
        plan = uninstall.build_plan(self.home, "wipe", environ=env)
        chosen = {x["path"] for x in plan["entries"]}
        self.assertTrue(all(str(root / kind / "obsgod") in chosen for kind in ["settings", "data", "logs"]))
        self.assertEqual(plan["plugin_directory"], str(root / "plugins/obsgod"))
        with self.assertRaises(ValueError):
            uninstall.build_plan(self.home, "wipe", environ={**env, "DECKY_PLUGIN_SETTINGS_DIR": str(root / "settings/OtherPlugin")})


if __name__ == "__main__":
    unittest.main()
