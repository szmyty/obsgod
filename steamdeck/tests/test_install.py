"""Installer boundary regressions for XDG, disk exhaustion and updater imports."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import install


class ProductInstallBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.package = Path(self.temp.name) / "package"
        self.package.mkdir()
        names = {"obsgod", "setup.py", "bridge.py", "setup.html", "setup.js", "setup.css", "uninstall.py", "obsgod-decky.zip", "LICENSE", "THIRD_PARTY_NOTICES.md", "STEAM-DECK.md"}
        for name in names:
            (self.package / name).write_text("fixture " + name)
        self.manifest = {"version": "0.1.0-test", "files": {name: hashlib.sha256((self.package / name).read_bytes()).hexdigest() for name in names}}
        (self.package / "manifest.json").write_text(json.dumps(self.manifest))
        self.env = patch.dict(os.environ, {"HOME": str(self.home), "XDG_DATA_HOME": "", "XDG_CONFIG_HOME": "", "XDG_STATE_HOME": "", "XDG_CACHE_HOME": ""})
        self.env.start()
        self.root = patch.object(install, "ROOT", self.package)
        self.root.start()

    def tearDown(self):
        self.root.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_fresh_custom_data_home_contains_application_and_shortcut(self):
        data = self.home / "custom data"
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}), contextlib.redirect_stdout(io.StringIO()):
            current = install.install(launch=False, with_decky=False)
        self.assertEqual(current, data / "obsgod/current")
        self.assertTrue((data / "applications/obsgod-setup.desktop").exists())
        self.assertFalse((self.home / ".local/share/obsgod").exists())

    def test_old_location_kept_when_xdg_data_changes_without_implicit_migration(self):
        with contextlib.redirect_stdout(io.StringIO()):
            original = install.install(launch=False, with_decky=False)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.home / "custom data")}), contextlib.redirect_stdout(io.StringIO()):
            current = install.install(launch=False, with_decky=False)
        self.assertEqual(current, original)
        self.assertFalse((self.home / "custom data/obsgod").exists())

    def test_insufficient_space_precedes_activation_or_plugin_replacement(self):
        with patch.object(install.shutil, "disk_usage", return_value=SimpleNamespace(free=0)), self.assertRaisesRegex(RuntimeError, "free space"):
            install.install(launch=False, with_decky=False)
        self.assertFalse((self.home / ".local/share/obsgod/current").exists())
        self.assertFalse((self.home / ".local/bin/obsgod").exists())

    def test_symlinked_parent_inside_home_is_also_refused(self):
        destination = self.home / "actual-local"
        destination.mkdir()
        (self.home / ".local").symlink_to(destination)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            install.install(launch=False, with_decky=False)
        self.assertEqual(list(destination.iterdir()), [])

    def test_xdg_symlink_back_to_home_is_refused_before_install(self):
        link = self.home / "data-link"
        link.symlink_to(self.home)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(link)}), self.assertRaisesRegex(RuntimeError, "symlinked"):
            install.install(launch=False, with_decky=False)
        self.assertFalse((self.home / "obsgod").exists())

    def test_malformed_output_status_never_allows_install(self):
        for state in [None, [], {"ok": True, "state": "stopped"}, {"ok": True, "state": "stopped", "stream": []}, {"ok": True, "state": "stopped", "recording": []}]:
            bridge = Mock()
            bridge.run_cli.return_value = state
            with self.assertRaises(RuntimeError):
                install.require_idle(bridge, close=True)
            self.assertEqual([x.args[0] for x in bridge.run_cli.call_args_list], ["status"])

    def test_replay_and_missing_legacy_replay_state_block_running_obs_update(self):
        idle = {"ok": True, "state": "stopped", "stream": {"active": False},
                "recording": False, "output_known": True, "process": "running"}
        for media in [None, [], {}, {"known": False, "replay_active": False}, {"known": True, "replay_active": True}]:
            bridge = Mock()
            bridge.run_cli.return_value = {**idle, **({"media": media} if media is not None else {})}
            with self.subTest(media=media), self.assertRaises(RuntimeError):
                install.require_idle(bridge, close=True)
            self.assertEqual([x.args[0] for x in bridge.run_cli.call_args_list], ["status"])
        bridge = Mock()
        bridge.run_cli.return_value = {**idle, "media": {"known": True, "replay_active": False}}
        install.require_idle(bridge)

    def test_old_updater_imports_new_modules_without_sys_path_or_stale_helpers(self):
        # Reproduce importlib loading from a published updater directory. The
        # downloaded installer must bind its OWN helper modules, not sys.path.
        code = """
import importlib.util, pathlib, sys, types
sys.modules['paths'] = types.SimpleNamespace(app_directories=lambda *a: (_ for _ in ()).throw(RuntimeError('stale helper')))
sys.modules['product'] = types.SimpleNamespace(DISPLAY_NAME='stale product')
for name in ['install', 'update', 'uninstall']:
    path = pathlib.Path(sys.argv[1]) / (name + '.py')
    spec = importlib.util.spec_from_file_location('downloaded_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app_directories(pathlib.Path(sys.argv[2]), {})[0] == pathlib.Path(sys.argv[2]) / '.local/share/obsgod'
    if hasattr(module, 'DISPLAY_NAME'): assert module.DISPLAY_NAME == 'Decky Stream'
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT), str(self.home)], cwd=self.home, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_official_decky_guide_requires_operator_consent(self):
        with patch.object(install.shutil, "which", return_value="kdialog"), patch.object(install.subprocess, "run") as dialog, patch.object(install.webbrowser, "open", return_value=True) as opened:
            dialog.return_value.returncode = 1
            self.assertFalse(install.offer_decky_guide("https://decky.xyz/"))
            opened.assert_not_called()
            dialog.return_value.returncode = 0
            self.assertTrue(install.offer_decky_guide("https://decky.xyz/"))
            opened.assert_called_once_with("https://decky.xyz/")


if __name__ == "__main__":
    unittest.main()
