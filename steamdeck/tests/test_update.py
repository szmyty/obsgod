import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("obsgod_updater", Path(__file__).resolve().parents[1] / "update.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.base = self.home / ".local/share/obsgod"
        self.env = patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_CURRENT_DESKTOP": "KDE", "DESKTOP_SESSION": "plasma"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def fixture(self):
        version = "0.1.0-deck.5"
        files = {name: b"verified fixture" for name in ["obsgod", "install.py", "bridge.py", "decky.py", "decky-install", "update.py", "releases.py", "obsgod-decky.zip"]}
        manifest = {"version": version, "revision": "1" * 40, "platform": "linux/amd64", "dirty": False, "updater_version": version, "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        files["manifest.json"] = json.dumps(manifest).encode()
        candidate = {"version": version, "revision": manifest["revision"], "manifest": manifest, "manifest_sha256": hashlib.sha256(files["manifest.json"]).hexdigest()}
        release = Mock()
        release.inspect_updates.return_value = ({"ok": True, "available": True}, candidate)

        def download(_candidate, destination):
            with tarfile.open(destination, "w:gz") as archive:
                for name, data in files.items():
                    member = tarfile.TarInfo("OBSGod-" + version + "/" + name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        release.download_archive.side_effect = download
        return release, candidate, files

    def test_bundle_checksum_and_symlink_validation_before_download(self):
        package = self.home / "updater"
        package.mkdir()
        files = {name: b"fixture" for name in ["update.py", "releases.py", "Update OBSGod.desktop", "Update OBSGod.sh", "decky-install"]}
        for name, content in files.items():
            (package / name).write_bytes(content)
        (package / "manifest.json").write_text(json.dumps({"platform": "linux/amd64", "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}))
        with patch.object(updater, "ROOT", package):
            updater.verify_bundle()
            (package / "decky-install").write_bytes(b"changed")
            with self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.verify_bundle()
            (package / "decky-install").unlink()
            (package / "decky-install").symlink_to(package / "update.py")
            with self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.verify_bundle()

    def test_download_failure_preserves_current_install_and_has_recovery_record(self):
        release, _, _ = self.fixture()
        release.download_archive.side_effect = RuntimeError("download failed")
        self.base.mkdir(parents=True)
        sentinel = self.base / "keep"
        sentinel.write_bytes(b"old installation")
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release), patch.object(updater, "load_module") as load:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "download failed"):
                updater.run_update()
        load.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"old installation")
        self.assertFalse(list(self.base.glob(".update-*")))
        self.assertEqual(json.loads((self.base / "update-status.json").read_text())["state"], "interrupted-or-failed")

    def test_unsafe_archive_paths_and_links_refused_before_extraction(self):
        for name, kind in [("../outside", tarfile.REGTYPE), ("OBSGod-0.1.0-deck.5/../../outside", tarfile.REGTYPE), ("OBSGod-0.1.0-deck.5/link", tarfile.SYMTYPE)]:
            archive = self.home / "payload.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = str(self.home / "outside")
                output.addfile(member)
            destination = self.home / "extract"
            destination.mkdir(exist_ok=True)
            with self.assertRaisesRegex(updater.UpdateError, "Unsafe"):
                updater.unpack_payload(archive, destination, "0.1.0-deck.5")
            self.assertEqual(list(destination.iterdir()), [])
            self.assertFalse((self.home / "outside").exists())

    def test_unknown_starting_active_and_recording_output_never_stopped_by_updater(self):
        for state in [{"ok": False, "state": "unknown"}, {"ok": True, "state": "starting"}, {"ok": True, "state": "streaming", "stream": {"active": True}}, {"ok": True, "state": "stopped", "recording": True}, {"ok": True, "state": "stopped", "output_known": False}, {"ok": True, "state": "stopped", "operation": "start"}]:
            bridge = Mock()
            bridge.run_cli.return_value = state
            with self.assertRaisesRegex(updater.UpdateError, "Update blocked"):
                updater.require_idle(bridge)
            self.assertEqual([call.args[0] for call in bridge.run_cli.call_args_list], ["status"])

    def test_no_update_does_not_download_install_or_downgrade(self):
        release, candidate, _ = self.fixture()
        release.inspect_updates.return_value = ({"ok": True, "available": False, "message": "No newer runtime"}, candidate)
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release), patch.object(updater, "load_module") as load:
            with contextlib.redirect_stdout(io.StringIO()):
                message = updater.run_update()
        release.download_archive.assert_not_called()
        load.assert_not_called()
        self.assertIn("Nothing was replaced", message)
        self.assertFalse((self.base / "update-status.json").exists())

    def test_historical_app_only_installer_is_not_misreported_as_unified_success(self):
        release, candidate, _ = self.fixture()
        del candidate["manifest"]["files"]["decky.py"]
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(updater.UpdateError, "historical runtime"):
                updater.run_update()
        release.download_archive.assert_not_called()

    def test_tampered_payload_stops_before_any_downloaded_code_is_imported(self):
        release, candidate, files = self.fixture()
        files["install.py"] = b"tampered installer"
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release), patch.object(updater, "load_module") as load:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.run_update()
        load.assert_not_called()

    def test_unified_install_invoked_once_with_key_preservation_and_final_revision_check(self):
        release, candidate, files = self.fixture()
        config = self.home / ".config/obsgod"
        config.mkdir(parents=True)
        for name in ["deck.json", "secrets.json"]:
            (config / name).write_bytes(b"fixture-never-real")
        media = self.home / "Videos/OBSGod/keep.mkv"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"existing recording")
        installer = Mock()
        bridge = Mock()
        bridge.run_cli.return_value = {"ok": True, "state": "stopped", "output_known": True, "recording": False}

        def install(launch):
            self.assertFalse(launch)
            target = self.base / "releases" / candidate["version"]
            target.mkdir(parents=True)
            for name, data in files.items():
                (target / name).write_bytes(data)
            (self.base / "current").symlink_to(target)
            return self.base / "current"
        installer.install.side_effect = install
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release), patch.object(updater, "load_module", side_effect=lambda name, path: installer if name == "obsgod_payload_installer" else bridge):
            with contextlib.redirect_stdout(io.StringIO()):
                message = updater.run_update()
        installer.verify_payload.assert_called_once()
        installer.install.assert_called_once_with(launch=False)
        self.assertIn(candidate["version"], message)
        self.assertEqual(media.read_bytes(), b"existing recording")
        self.assertEqual((config / "secrets.json").read_bytes(), b"fixture-never-real")
        backup = list((self.base / "backups").glob("updater-*/secrets.json"))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((self.base / "update-status.json").read_text())["state"], "complete")

    def test_interruption_preserves_previous_activation_and_records_retry(self):
        release, _, _ = self.fixture()
        old = self.base / "releases/old"
        old.mkdir(parents=True)
        (old / "manifest.json").write_text(json.dumps({"version": "0.1.0-deck.4"}))
        (self.base / "current").symlink_to(old)
        installer = Mock()
        installer.install.side_effect = KeyboardInterrupt()
        bridge = Mock()
        bridge.run_cli.return_value = {"ok": True, "state": "stopped", "output_known": True}
        with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module", return_value=release), patch.object(updater, "load_module", side_effect=lambda name, path: installer if name == "obsgod_payload_installer" else bridge):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                updater.run_update()
        self.assertEqual((self.base / "current").resolve(), old)
        self.assertEqual(json.loads((self.base / "update-status.json").read_text())["state"], "interrupted-or-failed")
        self.assertFalse(list(self.base.glob(".update-*")))

    def test_concurrent_updater_stops_before_network_and_writes(self):
        self.base.mkdir(parents=True)
        with (self.base / "update.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(updater, "verify_bundle"), patch.object(updater, "release_module") as release:
                with self.assertRaisesRegex(updater.UpdateError, "Another OBSGod updater"):
                    updater.run_update()
                release.return_value.inspect_updates.assert_not_called()

    def test_settings_backup_private_and_symlinked_recovery_record_refused(self):
        config = self.home / ".config/obsgod"
        config.mkdir(parents=True)
        (config / "secrets.json").write_bytes(b"fixture-never-real")
        updater.backup_settings(self.base, self.home)
        saved = next((self.base / "backups").glob("*/secrets.json"))
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        protected = self.home / "preserved"
        protected.write_bytes(b"unchanged")
        (self.base / "update-status.json").symlink_to(protected)
        with self.assertRaisesRegex(updater.UpdateError, "unsafe"):
            updater.save_progress(self.base, {"state": "downloading"})
        self.assertEqual(protected.read_bytes(), b"unchanged")


if __name__ == "__main__":
    unittest.main()
