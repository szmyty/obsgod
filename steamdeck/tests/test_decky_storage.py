"""Retained shared-store migration, native Decky paths and path safety."""
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import pwd
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("decky_storage", Path(__file__).parents[1] / "decky/storage.py")
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


class LegacyStorage(unittest.TestCase):
    def test_missing_and_partial_loader_context_preserves_environment_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = list(root.iterdir())
            env = {"HOME": str(root), "XDG_CONFIG_HOME": str(root / "config"),
                   "XDG_RUNTIME_DIR": "/run/user/fixture", "XDG_DATA_HOME": str(root / "data")}
            for supplied in ({}, {"DECKY_PLUGIN_SETTINGS_DIR": str(root / "missing")}):
                child = S.child_environment(root, supplied, env)
                self.assertEqual(child, env)
                self.assertEqual(S.context(root, supplied, env)["mode"], "legacy")
                self.assertEqual(list(root.iterdir()), before)
            self.assertEqual(S.child_environment(root, {}, {}), {})


@unittest.skipIf(os.getuid() == 0, "native Decky metadata requires an actual unprivileged player")
class NativeStorage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plugin = self.root / "bundle"
        self.plugin.mkdir()
        self.home = self.root / "player"
        self.home.mkdir(mode=0o700)
        self.settings = self.root / "decky-settings"
        self.runtime = self.root / "decky-data"
        self.logs = self.root / "decky-logs"
        for directory in (self.settings, self.runtime, self.logs):
            directory.mkdir(mode=0o700)
        self.provided = {"DECKY_USER_HOME": str(self.home), "DECKY_USER": pwd.getpwuid(os.getuid()).pw_name,
                         "DECKY_PLUGIN_SETTINGS_DIR": str(self.settings), "DECKY_PLUGIN_RUNTIME_DIR": str(self.runtime),
                         "DECKY_PLUGIN_LOG_DIR": str(self.logs)}
        self.env = {"HOME": str(self.home), "XDG_STATE_HOME": str(self.root / "shared-state"),
                    "XDG_CONFIG_HOME": str(self.root / "shared-config"), "XDG_DATA_HOME": str(self.root / "data"),
                    "XDG_CACHE_HOME": str(self.root / "cache"), "XDG_RUNTIME_DIR": str(self.root / "run/user"),
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=fixture-bus"}
        self.config_dir = Path(self.env["XDG_CONFIG_HOME"]) / "obsgod"
        self.config_dir.mkdir(parents=True, mode=0o700)
        self.config = self.config_dir / "deck.json"
        self.secrets = self.config_dir / "secrets.json"
        self.config.write_bytes(b'{"version":1,"server":"rtmps://fixture.invalid/live"}\n')
        self.secrets.write_bytes(b'{"stream_key":"synthetic-private-key","obs_password":"synthetic-obs-password","settings_hash":"retained-binding"}\n')
        self.secrets.chmod(0o600)
        self.state = Path(self.env["XDG_STATE_HOME"]) / "obsgod"
        self.state.mkdir(parents=True, mode=0o700)
        (self.state / "control.lock").write_bytes(b"same-controller-inode")
        self.video = self.home / "Videos/OBSGod/keep.mkv"
        self.video.parent.mkdir(parents=True)
        self.video.write_bytes(b"retained-media")

    def test_native_paths_are_metadata_only_and_keep_ephemeral_runtime_unchanged(self):
        original = dict(self.env)
        child = S.child_environment(self.plugin, self.provided, self.env)
        paths = S.context(self.plugin, self.provided, self.env)
        self.assertEqual(self.env, original)
        self.assertEqual(child["XDG_RUNTIME_DIR"], original["XDG_RUNTIME_DIR"])
        self.assertEqual(child["DBUS_SESSION_BUS_ADDRESS"], original["DBUS_SESSION_BUS_ADDRESS"])
        for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            self.assertEqual(child[key], original[key])
        self.assertEqual(paths["jobs_dir"], str(self.runtime / "jobs"))
        self.assertEqual(paths["log_dir"], str(self.logs))
        mapping = json.loads(Path(child[S.MAP_ENV]).read_text())
        self.assertEqual(mapping["shared"], {"config": str(self.config), "secrets": str(self.secrets), "state": str(self.state)})
        self.assertEqual(mapping["uid"], os.getuid())
        for path in (Path(child[S.MAP_ENV]), Path(child[S.MAP_ENV]).with_name("migration.json")):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotIn("synthetic-private-key", path.read_text())
            self.assertNotIn("synthetic-obs-password", path.read_text())
        self.assertEqual(stat.S_IMODE(Path(child[S.MAP_ENV]).parent.stat().st_mode), 0o700)

    def test_repeat_repair_and_rollback_keep_credentials_settings_media_and_lock(self):
        originals = {p: (p.read_bytes(), p.stat().st_ino) for p in (self.config, self.secrets, self.video, self.state / "control.lock")}
        first = S.context(self.plugin, self.provided, self.env)
        mapping = Path(first["map_path"])
        receipt = mapping.with_name("migration.json")
        original_map, original_receipt = mapping.read_bytes(), receipt.read_bytes()
        self.assertEqual(S.context(self.plugin, self.provided, self.env), first)
        self.assertEqual(mapping.read_bytes(), original_map)
        self.assertEqual(receipt.read_bytes(), original_receipt)
        receipt.unlink()
        S.context(self.plugin, self.provided, self.env)
        self.assertEqual(mapping.read_bytes(), original_map)
        self.assertEqual(json.loads(receipt.read_text())["observation"], "receipt-repair")
        self.assertTrue(S.rollback(self.plugin, self.provided, self.env)["removed"])
        self.assertFalse(S.rollback(self.plugin, self.provided, self.env)["removed"])
        self.assertFalse(mapping.exists())
        self.assertFalse(receipt.exists())
        self.assertEqual(S.context(self.plugin, self.provided, self.env), first)
        for path, (data, inode) in originals.items():
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_ino, inode)

    def test_changed_xdg_context_never_silently_selects_a_second_store(self):
        first = S.context(self.plugin, self.provided, self.env)
        for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
            with self.subTest(key=key), self.assertRaisesRegex(OSError, "does not match"):
                S.child_environment(self.plugin, self.provided, {**self.env, key: str(self.root / (key + "-other"))})
        self.assertEqual(S.context(self.plugin, self.provided, self.env), first)

    def test_service_home_xdg_is_removed_only_for_the_child(self):
        service = self.root / "service"
        service.mkdir()
        env = {**self.env, "HOME": str(service), "XDG_CONFIG_HOME": str(service / ".config"),
               "XDG_DATA_HOME": str(service / ".local/share")}
        child = S.child_environment(self.plugin, self.provided, env)
        self.assertEqual(child["HOME"], str(self.home))
        self.assertNotIn("XDG_CONFIG_HOME", child)
        self.assertNotIn("XDG_DATA_HOME", child)
        self.assertEqual(child["XDG_STATE_HOME"], env["XDG_STATE_HOME"])
        self.assertEqual(env["HOME"], str(service))

    def test_system_home_alias_does_not_erase_same_players_explicit_xdg_roots(self):
        alias = self.root / "home-alias"
        alias.symlink_to(self.home, target_is_directory=True)
        config = str(self.home / ".config")
        child = S.child_environment(self.plugin, {"DECKY_USER_HOME": str(alias)},
                                    {"HOME": str(self.home), "XDG_CONFIG_HOME": config})
        self.assertEqual(child["HOME"], str(self.home))
        self.assertEqual(child["XDG_CONFIG_HOME"], config)

    def test_map_uid_schema_and_path_mutation_fail_without_overwrite(self):
        info = S.context(self.plugin, self.provided, self.env)
        path = Path(info["map_path"])
        expected = json.loads(path.read_text())
        for change in ({"uid": os.getuid() + 1}, {"version": 2}, {"version": True}, {"shared": {**expected["shared"], "state": str(self.runtime)}}):
            with self.subTest(change=change):
                changed = json.dumps({**expected, **change})
                path.write_text(changed)
                with self.assertRaises(OSError):
                    S.context(self.plugin, self.provided, self.env)
                self.assertEqual(path.read_text(), changed)
        path.write_text(json.dumps(expected))

    def test_symlink_hardlink_foreign_owner_and_public_secret_fail_closed(self):
        info = S.context(self.plugin, self.provided, self.env)
        path = Path(info["map_path"])
        data = path.read_bytes()
        path.unlink()
        path.symlink_to(self.secrets)
        with self.assertRaises(OSError):
            S.context(self.plugin, self.provided, self.env)
        self.assertTrue(path.is_symlink())
        path.unlink()
        path.write_bytes(data)
        path.chmod(0o600)
        link = path.with_name("unrelated-hardlink")
        link.hardlink_to(path)
        with self.assertRaises(OSError):
            S.context(self.plugin, self.provided, self.env)
        link.unlink()
        self.secrets.chmod(0o644)
        with self.assertRaises(OSError):
            S.context(self.plugin, self.provided, self.env)
        self.secrets.chmod(0o600)
        original_lstat = Path.lstat
        def foreign(p):
            value = original_lstat(p)
            if p == path:
                values = list(value)
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return value
        with patch.object(Path, "lstat", foreign), self.assertRaises(OSError):
            S.context(self.plugin, self.provided, self.env)

    def test_symlinked_loader_root_and_invalid_player_context_do_not_leak_values(self):
        actual = self.root / "actual"
        actual.mkdir()
        self.logs.rmdir()
        self.logs.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(OSError) as caught:
            S.context(self.plugin, self.provided, self.env)
        self.assertNotIn(str(actual), str(caught.exception))
        self.logs.unlink()
        self.logs.mkdir()
        with self.assertRaises(OSError):
            S.context(self.plugin, {**self.provided, "DECKY_USER": "no-such-private-player"}, self.env)
        with self.assertRaises(OSError):
            S.context(self.plugin, {**self.provided, "DECKY_PLUGIN_LOG_DIR": "relative-private-fixture"}, self.env)

    def test_bundle_storage_is_rejected_before_creating_replacement_state(self):
        candidate = self.plugin / "persistent-state"
        with self.assertRaises(OSError):
            S.context(self.plugin, {**self.provided, "DECKY_PLUGIN_RUNTIME_DIR": str(candidate)}, self.env)
        self.assertFalse(candidate.exists())

    def test_private_state_below_nonsticky_writable_ancestor_cannot_fork_controller(self):
        ancestor = self.root / "shared-ancestor"
        private = ancestor / "private-grandchild"
        private.mkdir(parents=True, mode=0o700)
        ancestor.chmod(0o700)
        state = private / "obsgod"
        state.mkdir(mode=0o700)
        lock = state / "control.lock"
        lock.write_bytes(b"held-original-controller")
        env = {**self.env, "XDG_STATE_HOME": str(private)}
        S.context(self.plugin, self.provided, env)
        with lock.open("r+b") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            original_inode = os.fstat(held.fileno()).st_ino
            ancestor.chmod(0o777)
            with self.assertRaises(OSError):
                S.context(self.plugin, self.provided, env)
            moved = private / "previous-obsgod"
            state.rename(moved)
            state.mkdir(mode=0o700)
            with self.assertRaises(OSError):
                S.child_environment(self.plugin, self.provided, env)
            self.assertFalse((state / "control.lock").exists())
            self.assertEqual((moved / "control.lock").stat().st_ino, original_inode)
            self.assertEqual(os.fstat(held.fileno()).st_ino, original_inode)

    def test_sticky_owned_ancestor_supports_legitimate_external_xdg_state(self):
        ancestor = self.root / "sticky-shared"
        private = ancestor / "private-grandchild"
        private.mkdir(parents=True, mode=0o700)
        ancestor.chmod(0o1777)
        env = {**self.env, "XDG_STATE_HOME": str(private)}
        native = S.context(self.plugin, self.provided, env)
        self.assertEqual(native["shared_state"], str(private / "obsgod"))
        self.assertEqual(stat.S_IMODE(ancestor.stat().st_mode), 0o1777)
        self.assertEqual(S.context(self.plugin, self.provided, env), native)


if __name__ == "__main__":
    unittest.main()
