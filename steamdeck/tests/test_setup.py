import contextlib
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

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
            current = install.install(launch=False)
            install.install(launch=False)
        self.assertEqual(binary.resolve(), current.resolve() / "obsgod")
        self.assertEqual(obs.read_text(), "my scenes")
        backups = list((self.home / ".local/share/obsgod/backups").glob("*/obsgod"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "previous program")
        self.assertEqual((current / "obsgod").stat().st_mode & 0o777, 0o700)
        desktop = (self.home / ".local/share/applications/obsgod-setup.desktop").read_text()
        self.assertIn('Exec=python3 "', desktop)
        self.assertIn("home with spaces", desktop)

    def test_tamper_and_symlink_refused(self):
        (self.source / "obsgod").write_text("tampered")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            install.install(launch=False)
        self.manifest()
        (self.source / "obsgod").unlink()
        (self.source / "obsgod").symlink_to(self.source / "setup.py")
        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            install.install(launch=False)

    def test_install_cannot_follow_home_directory_escape(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "inside your home"):
            install.install(launch=False)
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
            current = install.install(launch=False)
            original = current.resolve()
            (self.source / "obsgod").write_text("new executable")
            self.manifest("0.2.0-test")
            install.install(launch=False)
            updated = current.resolve()
            self.assertNotEqual(original, updated)
            self.assertEqual((original / "obsgod").read_text(), "fixture obsgod")
            (self.source / "obsgod").write_text("replacement with same version")
            self.manifest("0.2.0-test")
            install.install(launch=False)
            replacement = current.resolve()
            self.assertNotEqual(replacement, updated)
            self.assertEqual((updated / "obsgod").read_text(), "new executable")
            # Simulate a damaged canonical install, then rerun the same package.
            (self.source / "obsgod").write_text("new executable")
            self.manifest("0.2.0-test")
            (updated / "obsgod").write_text("damaged")
            install.install(launch=False)
            self.assertEqual((current / "obsgod").read_text(), "new executable")
            repaired = current.resolve()
            (current / "obsgod").chmod(0o600)
            install.install(launch=False)
            self.assertEqual(current.resolve(), repaired)
            self.assertTrue(os.access(current / "obsgod", os.X_OK))
        self.assertEqual({path: path.read_bytes() for path in protected}, snapshots)

    def test_activation_failure_keeps_old_version_and_restores_entry_points(self):
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False)
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
            install.install(launch=False)
        self.assertEqual(current.resolve(), previous)
        self.assertEqual(desktop.read_text(), "my existing desktop entry")
        self.assertEqual((self.home / ".local/bin/obsgod").resolve(), previous / "obsgod")

    def test_dangling_desktop_link_is_backed_up_without_writing_its_target(self):
        desktop = self.home / ".local/share/applications/obsgod-setup.desktop"
        desktop.parent.mkdir(parents=True)
        target = self.home / "unrelated-file"
        desktop.symlink_to(target)
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            install.install(launch=False)
        self.assertFalse(target.exists())
        self.assertFalse(desktop.is_symlink())
        copies = list((self.home / ".local/share/obsgod/backups").glob("*/obsgod-setup.desktop"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].readlink(), target)

    def test_concurrent_installer_is_refused_without_changing_current(self):
        with contextlib.redirect_stdout(__import__("io").StringIO()):
            current = install.install(launch=False)
        previous = current.resolve()
        with install.installation_lock(current.parent):
            with self.assertRaisesRegex(RuntimeError, "Another OBSGod installer"):
                install.install(launch=False)
        self.assertEqual(current.resolve(), previous)


if __name__ == "__main__":
    unittest.main()
