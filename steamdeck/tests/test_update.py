import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
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

    def test_bundle_checksum_and_symlink_validation_before_helper_execution(self):
        package = self.home / "updater"
        package.mkdir()
        files = {name: b"fixture" for name in ["update.py", "decky-install", "Update OBSGod.desktop", "Update OBSGod.sh", "LICENSE", "THIRD_PARTY_NOTICES.md"]}
        for name, content in files.items():
            (package / name).write_bytes(content)
        (package / "manifest.json").write_text(json.dumps({"target_version": updater.VERSION, "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}))
        with patch.object(updater, "ROOT", package):
            updater.verify_bundle()
            self.assertTrue(os.access(package / "decky-install", os.X_OK))
            (package / "decky-install").write_bytes(b"changed")
            with self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.verify_bundle()
            (package / "decky-install").unlink()
            (package / "decky-install").symlink_to(package / "LICENSE")
            with self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.verify_bundle()

    def test_download_failure_keeps_existing_installation(self):
        self.base.mkdir(parents=True)
        sentinel = self.base / "keep"
        sentinel.write_bytes(b"old installation")
        with patch.object(updater, "verify_bundle"), patch.object(updater, "check_decky"), patch.object(updater, "download_payload", side_effect=updater.UpdateError("checksum mismatch")), patch.object(updater, "close_managed_obs") as close:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(updater.UpdateError, "checksum"):
                updater.run_update()
        close.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"old installation")
        self.assertFalse(list(self.base.glob(".update-*")))

    def test_download_rejects_bytes_that_do_not_match_pinned_digest(self):
        destination = self.home / "payload.tar.gz"
        with patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupted download")):
            with self.assertRaisesRegex(updater.UpdateError, "checksum mismatch"):
                updater.download_payload(destination)

    def test_unsafe_archive_paths_and_links_are_refused_before_extraction(self):
        for name, kind in [("../outside", tarfile.REGTYPE), ("OBSGod-" + updater.VERSION + "/../../outside", tarfile.REGTYPE), ("OBSGod-" + updater.VERSION + "/link", tarfile.SYMTYPE)]:
            archive = self.home / "payload.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = str(self.home / "outside")
                output.addfile(member)
            destination = self.home / "extract"
            destination.mkdir(exist_ok=True)
            with self.assertRaisesRegex(updater.UpdateError, "Unsafe"):
                updater.unpack_payload(archive, destination)
            self.assertEqual(list(destination.iterdir()), [])
            self.assertFalse((self.home / "outside").exists())

    def test_unknown_output_and_active_recording_are_never_force_killed(self):
        bridge = Mock()
        bridge.run_cli.side_effect = [{"ok": False, "state": "unknown", "configured": True}, {"ok": False, "message": "OBS output cannot be confirmed"}]
        with self.assertRaisesRegex(updater.UpdateError, "Could not confirm OBS stopped"):
            updater.close_managed_obs(bridge)
        self.assertEqual([call.args[0] for call in bridge.run_cli.call_args_list], ["status", "stop"])
        bridge.reset_mock()
        bridge.run_cli.side_effect = [{"ok": True, "state": "stopped", "configured": True}, {"ok": False, "message": "stop streaming and recording before restarting OBSGod"}]
        with self.assertRaisesRegex(updater.UpdateError, "Stop any recording"):
            updater.close_managed_obs(bridge)
        self.assertEqual([call.args[0] for call in bridge.run_cli.call_args_list], ["status", "restart"])

    def test_existing_dependencies_do_not_change_remotes_or_reinstall(self):
        with patch.object(updater.shutil, "which", return_value="/usr/bin/flatpak"), patch.object(updater.subprocess, "run", return_value=Mock(returncode=0)) as run:
            updater.ensure_dependencies()
        self.assertEqual(len(run.call_args_list), 2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][:3], ["flatpak", "info", "--user"])

    def test_settings_backup_is_private_and_originals_are_unchanged(self):
        config = self.home / ".config/obsgod"
        config.mkdir(parents=True)
        for name in ["deck.json", "secrets.json"]:
            (config / name).write_bytes(b"fixture-never-real")
        updater.backup_settings(self.base, self.home)
        for name in ["deck.json", "secrets.json"]:
            self.assertEqual((config / name).read_bytes(), b"fixture-never-real")
            copies = list((self.base / "backups").glob("*/" + name))
            self.assertEqual(len(copies), 1)
            self.assertEqual(copies[0].stat().st_mode & 0o777, 0o600)

    def test_helper_invalid_output_does_not_echo_stderr_or_secrets(self):
        with patch.object(updater.subprocess, "run", return_value=Mock(stdout="fixture-private-token", stderr="fixture-stream-key", returncode=1)):
            with self.assertRaises(updater.UpdateError) as caught:
                updater.replace_plugin(self.home)
        self.assertNotIn("fixture-private-token", str(caught.exception))
        self.assertNotIn("fixture-stream-key", str(caught.exception))

    def test_concurrent_updater_stops_before_network_and_writes(self):
        self.base.mkdir(parents=True)
        with (self.base / "update.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(updater, "verify_bundle"), patch.object(updater, "check_decky") as check:
                with self.assertRaisesRegex(updater.UpdateError, "Another OBSGod updater"):
                    updater.run_update()
                check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
