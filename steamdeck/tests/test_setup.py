import contextlib
import hashlib
import http.client
import importlib.util
import json
import os
import shlex
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import setup
import install


class LocalSetupSecurity(unittest.TestCase):
    def setUp(self):
        self.server = setup.SetupServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cli = patch.object(setup, "run_cli", return_value={"ok": True, "state": "stopped", "configured": True, "message": "Saved"})
        self.mock = self.cli.start()

    def tearDown(self):
        self.cli.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, auth=True, origin=None, host=None):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.server.token
        if origin:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_requests_require_token_origin_and_loopback_host(self):
        for method, path, body in [("GET", "/api/status", None), ("POST", "/api/action", {"action": "configure", "settings": {"stream_key": "private-fixture"}})]:
            self.assertEqual(self.request(method, path, body, auth=False)[0], 403)
            self.assertEqual(self.request(method, path, body, origin="https://attacker.invalid")[0], 403)
            self.assertEqual(self.request(method, path, body, host="attacker.invalid")[0], 403)
        self.mock.assert_not_called()

    def test_secret_only_goes_to_stdin_bridge_not_response(self):
        settings = {"stream_key": "private-fixture"}
        status, headers, body = self.request("POST", "/api/action", {"action": "configure", "settings": settings})
        self.assertEqual(status, 200)
        self.mock.assert_called_once_with("configure", settings)
        self.assertNotIn(b"private-fixture", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_static_page_does_not_embed_authorization_or_execute_inline(self):
        status, _, body = self.request("GET", "/", auth=False)
        self.assertEqual(status, 200)
        self.assertNotIn(self.server.token.encode(), body)
        self.assertIn(b'src="/setup.js"', body)
        self.assertEqual(self.request("GET", "/api/action")[0], 404)
        self.assertEqual(self.request("POST", "/api/action", {"action": "start"})[0], 400)


class InstallerSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.source = Path(self.temp.name) / "package"
        self.source.mkdir()
        self.files = {"obsgod", "setup.py", "bridge.py", "setup.html", "setup.js", "setup.css", "uninstall.py", "obsgod-decky.zip", "LICENSE", "THIRD_PARTY_NOTICES.md", "STEAM-DECK.md"}
        for name in self.files:
            (self.source / name).write_text("fixture " + name)
        self.manifest()
        self.env = patch.dict(os.environ, {"HOME": str(self.home)})
        self.env.start()
        self.root = patch.object(install, "ROOT", self.source)
        self.root.start()

    def manifest(self, version="0.1.0-test"):
        (self.source / "manifest.json").write_text(json.dumps({"version": version, "files": {name: hashlib.sha256((self.source / name).read_bytes()).hexdigest() for name in self.files}}))

    def tearDown(self):
        self.root.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_install_repeat_backup_and_existing_obs_preservation(self):
        binary = self.home / ".local/bin/obsgod"
        binary.parent.mkdir(parents=True)
        binary.write_text("previous program")
        obs = self.home / ".var/app/com.obsproject.Studio/config/obs-studio/global.ini"
        obs.parent.mkdir(parents=True)
        obs.write_text("my scenes")
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False, with_decky=False)
            install.install(launch=False, with_decky=False)
        self.assertEqual(binary.resolve(), current.resolve() / "obsgod")
        self.assertEqual(obs.read_text(), "my scenes")
        backups = list((self.home / ".local/share/obsgod/backups").glob("*/obsgod"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "previous program")
        self.assertEqual((current / "obsgod").stat().st_mode & 0o777, 0o700)
        desktop = (self.home / ".local/share/applications/obsgod-setup.desktop").read_text()
        self.assertIn('Exec=python3 -c "', desktop)
        self.assertIn("home with spaces", desktop)

    def test_installed_application_launcher_executes_code_and_preserves_error(self):
        special_home = self.home.with_name("home with spaces %20")
        self.home.rename(special_home)
        self.home = special_home
        (self.source / "setup.py").write_text("print('managed setup launched', flush=True)\nraise SystemExit(7)\n")
        self.manifest()
        with patch.dict(os.environ, {"HOME": str(self.home)}), contextlib.redirect_stdout(__import__("io").StringIO()):
            install.install(launch=False, with_decky=False)
        desktop = self.home / ".local/share/applications/obsgod-setup.desktop"
        line = next(line[5:] for line in desktop.read_text().splitlines() if line.startswith("Exec="))
        # %% is the Desktop Entry specification's literal-percent field escape.
        self.assertIn("spaces %%20", line)
        command = [value.replace("%%", "%") for value in shlex.split(line)]
        result = subprocess.run(command, input="\n", capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 7)
        self.assertIn("managed setup launched", result.stdout)
        self.assertIn("Press Enter to close", result.stdout)

    def test_tamper_and_symlink_refused(self):
        (self.source / "obsgod").write_text("tampered")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            install.install(launch=False, with_decky=False)
        self.manifest()
        (self.source / "obsgod").unlink()
        (self.source / "obsgod").symlink_to(self.source / "setup.py")
        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            install.install(launch=False, with_decky=False)

    def test_install_cannot_follow_home_directory_escape(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "inside your home"):
            install.install(launch=False, with_decky=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_update_same_version_replacement_and_repair_preserve_user_data(self):
        protected = [
            self.home / ".config/obsgod/deck.json",
            self.home / ".config/obsgod/secrets.json",
            self.home / "Videos/OBSGod/keep.mkv",
            self.home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini",
            self.home / ".local/state/obsgod/diagnostics/events.json",
        ]
        for path in protected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("keep " + path.name)
        snapshots = {path: path.read_bytes() for path in protected}
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False, with_decky=False)
            original = current.resolve()
            (self.source / "obsgod").write_text("new executable")
            self.manifest("0.2.0-test")
            install.install(launch=False, with_decky=False)
            updated = current.resolve()
            self.assertNotEqual(original, updated)
            self.assertEqual((original / "obsgod").read_text(), "fixture obsgod")
            (self.source / "obsgod").write_text("replacement with same version")
            self.manifest("0.2.0-test")
            install.install(launch=False, with_decky=False)
            replacement = current.resolve()
            self.assertNotEqual(replacement, updated)
            self.assertEqual((updated / "obsgod").read_text(), "new executable")
            # Simulate a damaged canonical install, then rerun the same package.
            (self.source / "obsgod").write_text("new executable")
            self.manifest("0.2.0-test")
            (updated / "obsgod").write_text("damaged")
            install.install(launch=False, with_decky=False)
            self.assertEqual((current / "obsgod").read_text(), "new executable")
            repaired = current.resolve()
            (current / "obsgod").chmod(0o600)
            install.install(launch=False, with_decky=False)
            self.assertEqual(current.resolve(), repaired)
            self.assertTrue(os.access(current / "obsgod", os.X_OK))
            (current / "manifest.json").unlink()
            install.install(launch=False, with_decky=False)
            self.assertTrue((current / "manifest.json").is_file())
        self.assertEqual({path: path.read_bytes() for path in protected}, snapshots)

    def test_activation_failure_keeps_old_version_and_restores_entry_points(self):
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False, with_decky=False)
        previous = current.resolve()
        desktop = self.home / ".local/share/applications/obsgod-setup.desktop"
        desktop.write_text("my existing desktop entry")
        self.manifest("0.2.0-test")
        replace = Path.replace

        def fail_current(path, target):
            if target == current:
                raise OSError("simulated activation failure")
            return replace(path, target)

        with patch.object(Path, "replace", fail_current), self.assertRaisesRegex(OSError, "activation failure"):
            install.install(launch=False, with_decky=False)
        self.assertEqual(current.resolve(), previous)
        self.assertEqual(desktop.read_text(), "my existing desktop entry")
        self.assertEqual((self.home / ".local/bin/obsgod").resolve(), previous / "obsgod")

    def test_dangling_desktop_link_is_backed_up_without_writing_its_target(self):
        desktop = self.home / ".local/share/applications/obsgod-setup.desktop"
        desktop.parent.mkdir(parents=True)
        target = self.home / "unrelated-file"
        desktop.symlink_to(target)
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            install.install(launch=False, with_decky=False)
        self.assertFalse(target.exists())
        self.assertFalse(desktop.is_symlink())
        copies = list((self.home / ".local/share/obsgod/backups").glob("*/obsgod-setup.desktop"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].readlink(), target)

    def test_concurrent_installer_is_refused_without_changing_current(self):
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False, with_decky=False)
        previous = current.resolve()
        with install.installation_lock(current.parent):
            with self.assertRaisesRegex(RuntimeError, "Another OBSGod installer"):
                install.install(launch=False, with_decky=False)
        self.assertEqual(current.resolve(), previous)


class UnifiedInstallerSafety(unittest.TestCase):
    manifest = InstallerSafety.manifest

    def setUp(self):
        InstallerSafety.setUp(self)
        self.files |= {"decky-install", "decky.py", "install.py", "Install OBSGod.desktop", "update.py", "releases.py", "Update OBSGod.desktop", "Update OBSGod.sh"}
        for name in self.files:
            if not (self.source / name).exists():
                (self.source / name).write_text("fixture " + name)
        self.manifest()
        self.decky = Mock()
        self.decky.status.return_value = {"ok": True, "version": "v3.3.1"}
        self.bridge = Mock()
        self.bridge.run_cli.return_value = {"ok": True, "state": "stopped", "configured": False}
        self.loader = patch.object(install, "load_module", side_effect=lambda name, path: self.decky if name == "obsgod_install_decky" else self.bridge)
        self.loader.start()
        self.dependencies = patch.object(install, "ensure_dependencies")
        self.dependencies.start()

    def tearDown(self):
        self.dependencies.stop()
        self.loader.stop()
        InstallerSafety.tearDown(self)

    def test_default_installs_verified_plugin_before_activating_app(self):
        current = self.home / ".local/share/obsgod/current"
        def verify_first(operation, candidate, manifest):
            self.assertFalse(current.exists())
            self.assertEqual(operation, "install")
            self.assertTrue((candidate / "obsgod-decky.zip").is_file())
        self.decky.helper_request.side_effect = verify_first
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            installed = install.install(launch=False)
        self.assertEqual(installed.resolve().name, "0.1.0-test")
        self.assertIn("Update OBSGod", (self.home / ".local/share/applications/obsgod-update.desktop").read_text())
        self.decky.status.assert_called_once()
        self.decky.helper_request.assert_called_once()
        self.assertEqual([call.args[0] for call in self.bridge.run_cli.call_args_list], ["status", "status"])

    def test_missing_decky_stops_before_app_or_dependencies_change(self):
        self.decky.status.return_value = {"ok": False, "message": "Decky service unavailable. Official setup: https://decky.xyz/"}
        with self.assertRaisesRegex(RuntimeError, "No app or plugin was replaced"):
            install.install(launch=False)
        self.assertFalse((self.home / ".local/share/obsgod/current").exists())
        self.decky.helper_request.assert_not_called()
        install.ensure_dependencies.assert_not_called()

    def test_active_unknown_or_pending_output_is_never_stopped(self):
        for state in [
            {"ok": True, "state": "streaming", "stream": {"active": True}},
            {"ok": False, "state": "unknown"},
            {"ok": True, "state": "stopped", "recording": {"active": True}},
            {"ok": True, "state": "starting"},
            {"ok": True, "state": "stopped", "output_known": False},
            {"ok": True, "state": "stopped", "operation": "start"},
        ]:
            self.bridge.run_cli.reset_mock()
            self.bridge.run_cli.return_value = state
            with self.subTest(state=state), self.assertRaisesRegex(RuntimeError, "will not stop a broadcast"):
                install.install(launch=False)
            self.assertEqual([call.args[0] for call in self.bridge.run_cli.call_args_list], ["status"])
            self.decky.helper_request.assert_not_called()

    def test_activation_failure_keeps_old_app_and_verifies_old_plugin_recovery(self):
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False, with_decky=False)
        previous = current.resolve()
        self.manifest("0.2.0-test")
        with patch.object(install, "activate_release", side_effect=OSError("activation failed")), self.assertRaisesRegex(RuntimeError, "previous plugin was restored and verified"):
            install.install(launch=False)
        self.assertEqual(current.resolve(), previous)
        self.assertEqual(self.decky.helper_request.call_args_list[-1].args[1], previous)
        record = current.parent / "installation-recovery.json"
        self.assertEqual(record.stat().st_mode & 0o777, 0o600)
        self.assertTrue(json.loads(record.read_text())["plugin_rollback_confirmed"])

    def test_unconfirmed_rollback_is_reported_without_false_success(self):
        self.decky.helper_request.side_effect = RuntimeError("unconfirmed install")
        with self.assertRaisesRegex(RuntimeError, "plugin version/rollback is unconfirmed"):
            install.install(launch=False)
        current = self.home / ".local/share/obsgod/current"
        self.assertFalse(current.exists())
        record = json.loads((current.parent / "installation-recovery.json").read_text())
        self.assertFalse(record["plugin_rollback_confirmed"])
        self.decky.helper_request.assert_called_once()

    def test_pending_control_operation_blocks_plugin_replacement(self):
        with install.control_lock(self.home):
            with self.assertRaisesRegex(RuntimeError, "control operation is busy"):
                install.install(launch=False)
        self.decky.helper_request.assert_not_called()


class DependencyCompatibility(unittest.TestCase):
    OBS_REF = "app/com.obsproject.Studio/x86_64/stable"

    @staticmethod
    def result(stdout="", code=0):
        return Mock(returncode=code, stdout=stdout)

    def responses(self, version="33.0.1"):
        return [self.result(), self.result(), self.result(self.OBS_REF + "\n"),
                self.result(self.OBS_REF + "\t" + version + "\n")]

    def test_installed_modern_obs_does_not_reinstall_or_change_remotes(self):
        with patch.object(install.shutil, "which", return_value="/usr/bin/flatpak"), patch.object(install.subprocess, "run", side_effect=self.responses()) as run:
            install.ensure_dependencies()
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ["flatpak", "info", "--user", "com.obsproject.Studio"],
            ["flatpak", "info", "--user", "com.obsproject.Studio.Plugin.Gstreamer"],
            ["flatpak", "info", "--user", "--show-ref", "com.obsproject.Studio"],
            ["flatpak", "list", "--user", "--app", "--columns=ref,version"],
        ])

    def test_obs_before_bundled_websocket_is_rejected(self):
        with patch.object(install.shutil, "which", return_value="/usr/bin/flatpak"), patch.object(install.subprocess, "run", side_effect=self.responses("27.2.0")):
            with self.assertRaisesRegex(RuntimeError, "User-installed OBS 27.2.0.*older than OBS 28"):
                install.ensure_dependencies()

    def test_boundary_and_current_versions_are_supported(self):
        for version in ["28.0.0", "33.0.1", "33.0.1-rc1"]:
            with self.subTest(version=version), patch.object(install.subprocess, "run", side_effect=self.responses(version)[2:]):
                self.assertEqual(install.installed_obs_version(), version)

    def test_query_failures_are_not_reported_as_old_obs(self):
        cases = [
            [self.result("", 1)],
            [self.result("not-an-app-ref")],
            [self.result(self.OBS_REF), self.result("", 1)],
            [self.result(self.OBS_REF), self.result("")],
            [self.result(self.OBS_REF), self.result(self.OBS_REF + "\t\n")],
            [self.result(self.OBS_REF), self.result(self.OBS_REF + "\t33.invalid\n")],
            [self.result(self.OBS_REF), self.result((self.OBS_REF + "\t33.0.1\n") * 2)],
        ]
        for responses in cases:
            with self.subTest(responses=responses), patch.object(install.subprocess, "run", side_effect=responses):
                with self.assertRaises(RuntimeError) as error:
                    install.installed_obs_version()
                self.assertNotIn("older than OBS 28", str(error.exception))
                self.assertNotIn("second WebSocket", str(error.exception))

    def test_resolved_ref_selects_launched_branch_not_unrelated_app_or_highest_version(self):
        rows = "app/com.other.App/x86_64/stable\t99.0.0\n" + \
               "app/com.obsproject.Studio/x86_64/beta\t35.0.0\n" + \
               self.OBS_REF + "\t27.2.0\n"
        with patch.object(install.subprocess, "run", side_effect=[self.result(self.OBS_REF), self.result(rows)]):
            self.assertEqual(install.installed_obs_version(), "27.2.0")

    def test_missing_dependencies_use_user_flatpak_then_verify_version(self):
        responses = [self.result(code=1), self.result(), self.result(),
                     self.result(self.OBS_REF), self.result(self.OBS_REF + "\t33.0.1\n")]
        with patch.object(install.shutil, "which", return_value="/usr/bin/flatpak"), patch.object(install.subprocess, "run", side_effect=responses) as run:
            install.ensure_dependencies()
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[0], "flatpak")
            self.assertIn("--user", command)
        self.assertEqual(run.call_args_list[-1].args[0], ["flatpak", "list", "--user", "--app", "--columns=ref,version"])


if __name__ == "__main__":
    unittest.main()
