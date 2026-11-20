"""Private recovery bytes must be durable before any wipe/helper deletion."""
import contextlib
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import uninstall
import paths

IDLE = {"ok": True, "state": "stopped", "output_known": True, "process": "absent",
        "stream": {"active": False}, "recording": False,
        "media": {"known": True, "replay_active": False,
                  "recording": {"active": False, "paused": False}}}
SECRET = "synthetic-private-wipe-fixture-never-public"


class WipeExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "player"
        self.home.mkdir(mode=0o700)
        self.enterContext(patch.dict(os.environ, {"HOME": str(self.home), "DECKY_HOME": "",
                                                 **{name: "" for name in paths.DEFAULTS}}))
        self.cli = self.enterContext(patch.object(uninstall, "run_cli", return_value=IDLE))
        self.plugin = self.enterContext(patch.object(uninstall, "remove_plugin"))
        self.base = self.home / ".local/share/obsgod"
        self.settings = self.write(".config/obsgod/secrets.json", SECRET)
        self.write(".local/share/obsgod/releases/v1/obsgod", "reviewed executable")
        (self.base / "current").symlink_to(self.base / "releases/v1")
        self.write(".local/share/obsgod/backups/prior/secrets.json", "old private binding")
        self.write(".local/state/obsgod/history.json", "owned history")
        self.write(".var/app/com.obsproject.Studio/config/obsgod/profile.json", "managed settings")
        self.write(".var/app/com.obsproject.Studio/config/obs-studio/ordinary.json", "ordinary OBS")
        self.write("homebrew/settings/obsgod/owned.json", "owned adapter")
        self.write("homebrew/settings/OtherPlugin/keep", "unrelated")
        self.media = self.write("Videos/OBSGod/2026-11-20 00-00-00.mkv", "explicit media")

    def write(self, relative, value):
        path = self.home / relative
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_text(value)
        return path

    def intact(self):
        self.assertTrue(self.settings.exists())
        self.assertTrue((self.base / "current/obsgod").exists())
        self.assertTrue(self.media.exists())

    def archive(self, receipt):
        path = Path(receipt["path"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), receipt["sha256"])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(path.stat().st_nlink, 1)
        with tarfile.open(path) as archive:
            self.assertTrue(all(member.isfile() for member in archive))
            manifest = json.load(archive.extractfile("RECOVERY.json"))
            for entry in manifest["entries"]:
                if entry["kind"] == "file":
                    data = archive.extractfile("home/" + entry["path"]).read()
                    self.assertEqual(len(data), entry["bytes"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            return manifest, {m.name: archive.extractfile(m).read() for m in archive}

    def test_verified_private_export_precedes_plugin_removal_and_survives_wipe(self):
        plan = uninstall.build_plan(self.home, "wipe")
        observed = []
        def before_plugin(*_args):
            self.intact()
            observed.append(self.archive(plan["export_result"]))
        self.plugin.side_effect = before_plugin
        uninstall.apply_plan(plan, self.home)
        self.assertFalse(self.settings.exists())
        manifest, content = observed[0]
        receipt = plan["export_result"]
        self.assertTrue(Path(receipt["path"]).exists())
        self.assertTrue(manifest["contains_credentials"])
        self.assertTrue(manifest["preserved_after_wipe"])
        self.assertEqual(content["home/.config/obsgod/secrets.json"], SECRET.encode())
        self.assertTrue(any(x["kind"] == "alias" and x["path"].endswith("/current") for x in manifest["entries"]))
        self.assertFalse(any("Videos/" in name or "OtherPlugin" in name or "/obs-studio/" in name or
                             name.endswith(("control.lock", "update.lock", "install.lock")) for name in content))
        # Recovery uses an explicitly selected regular member into NEW private
        # staging, never extractall, HOME overwrite or recreated alias execution.
        restored = self.home / "private-recovery-staging"
        restored.mkdir(mode=0o700)
        (restored / "secrets.json").write_bytes(content["home/.config/obsgod/secrets.json"])
        self.assertEqual((restored / "secrets.json").read_text(), SECRET)
        self.assertEqual([call.args[0] for call in self.cli.call_args_list], ["status"] * 4)

    def test_dry_run_and_cli_result_disclose_retained_credentials_without_readback(self):
        destination = self.home / "private-exports/wipe.tar"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(uninstall.main(["--wipe", "--export", str(destination), "--dry-run", "--json"]), 0)
        preview = json.loads(output.getvalue())
        self.assertEqual(preview["export"]["path"], str(destination))
        self.assertTrue(preview["export"]["contains_credentials"])
        self.assertFalse(destination.parent.exists())
        self.cli.assert_not_called()
        self.plugin.assert_not_called()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(uninstall.main(["--wipe", "--export", str(destination), "--yes", "--json"]), 0)
        answer = json.loads(output.getvalue())
        self.assertTrue(answer["export"]["preserved_after_wipe"])
        self.assertIn("not all copies were erased", answer["message"])
        self.assertNotIn(SECRET, output.getvalue())
        self.assertEqual(set(answer["export"]), {"path", "sha256", "bytes", "entries", "contains_credentials", "preserved_after_wipe"})
        self.archive(answer["export"])

    def test_export_flag_does_not_change_normal_reset_or_retirement_scopes(self):
        for mode in ("uninstall", "reset"):
            with self.subTest(mode=mode), self.assertRaises(uninstall.RemovalError):
                uninstall.build_plan(self.home, mode, export_path=self.home / "new.tar")
        for options in ({}, {"mode": "reset"}, {"legacy_app_only": True}):
            self.assertNotIn("export", uninstall.build_plan(self.home, **options))
        self.cli.assert_not_called()

    def test_export_is_outside_selected_and_plugin_roots_in_both_directions(self):
        for destination in (self.settings.parent / "wipe.tar", self.base / "exports/wipe.tar",
                            self.home / ".local/state/obsgod/wipe.tar", self.home / "homebrew/plugins/obsgod/wipe.tar",
                            self.home / ".config"):
            with self.subTest(path=destination), self.assertRaisesRegex(uninstall.RemovalError, "outside"):
                uninstall.build_plan(self.home, "wipe", export_path=destination)
        self.intact()

    def test_existing_output_and_unsafe_or_symlinked_parent_are_never_overwritten(self):
        parent = self.home / "exports"
        parent.mkdir(mode=0o700)
        destination = parent / "existing.tar"
        destination.write_text("unrelated")
        for path in (destination,):
            with self.assertRaisesRegex(uninstall.RemovalError, "already exists"):
                uninstall.build_plan(self.home, "wipe", export_path=path)
        alias = self.home / "export-alias"
        alias.symlink_to(parent)
        with self.assertRaises(ValueError):
            uninstall.build_plan(self.home, "wipe", export_path=alias / "new.tar")
        parent.chmod(0o755)
        with self.assertRaisesRegex(uninstall.RemovalError, "0700"):
            uninstall.build_plan(self.home, "wipe", export_path=parent / "new.tar")
        self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(destination.read_text(), "unrelated")
        self.plugin.assert_not_called()

    def test_replaced_output_parent_after_preview_prevents_wipe(self):
        parent = self.home / "exports"
        parent.mkdir(mode=0o700)
        plan = uninstall.build_plan(self.home, "wipe", export_path=parent / "new.tar")
        parent.rename(self.home / "old-exports")
        parent.mkdir(mode=0o700)
        self.write("exports/keep", "unrelated replacement")
        with self.assertRaisesRegex(uninstall.RemovalError, "directory changed"):
            uninstall.apply_plan(plan, self.home)
        self.assertEqual((parent / "keep").read_text(), "unrelated replacement")
        self.plugin.assert_not_called()
        self.intact()

    def test_linked_and_foreign_export_sources_are_rejected_before_plugin_removal(self):
        alias = self.home / "shared-secret"
        os.link(self.settings, alias)
        with self.assertRaisesRegex(uninstall.RemovalError, "link count"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        alias.unlink()
        original = os.fstat
        inode = self.settings.stat().st_ino
        def foreign(fd):
            info = original(fd)
            if info.st_ino == inode:
                return SimpleNamespace(**{name: (info.st_uid + 1 if name == "st_uid" else getattr(info, name))
                                          for name in ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")})
            return info
        with patch.object(uninstall.os, "fstat", foreign), self.assertRaisesRegex(uninstall.RemovalError, "ownership"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.plugin.assert_not_called()
        self.intact()

    def test_source_change_during_copy_prevents_wipe(self):
        original = uninstall._ExportReader.read
        changed = False
        inode = self.settings.stat().st_ino
        def mutate(reader, size):
            nonlocal changed
            data = original(reader, size)
            if not changed and os.fstat(reader.source.fileno()).st_ino == inode:
                changed = True
                self.settings.write_text("changed by another writer")
            return data
        with patch.object(uninstall._ExportReader, "read", mutate), self.assertRaisesRegex(uninstall.RemovalError, "changed"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.plugin.assert_not_called()
        self.assertEqual(self.settings.read_text(), "changed by another writer")

    def test_export_failure_interruption_and_bounds_never_start_destructive_helper(self):
        failures = [("_verify_export", OSError("fixture short write")),
                    ("_verify_export", KeyboardInterrupt()),
                    ("_verify_export", tarfile.ReadError("fixture invalid archive")),
                    ("EXPORT_MAX_BYTES", 1), ("EXPORT_MAX_NODES", 1), ("EXPORT_SECONDS", -1)]
        for name, value in failures:
            options = {"side_effect": value} if isinstance(value, BaseException) else {"new": value}
            with self.subTest(failure=name), patch.object(uninstall, name, **options), self.assertRaises(uninstall.RemovalError) as caught:
                uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
            self.assertEqual(caught.exception.completed, [])
            self.plugin.assert_not_called()
            self.intact()
        self.assertEqual(list((self.home / ".local/share/obsgod-wipe-exports").iterdir()), [])

    def test_file_and_directory_fsync_failures_prevent_first_deletion(self):
        original_sync, original_link = os.fsync, os.link
        for phase in ("file", "published-directory"):
            published = False
            def link(*args, **kwargs):
                nonlocal published
                result = original_link(*args, **kwargs)
                published = True
                return result
            def sync(fd):
                directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                if phase == "file" and not directory or phase == "published-directory" and directory and published:
                    raise OSError("fixture durable flush denied")
                return original_sync(fd)
            with self.subTest(phase=phase), patch.object(uninstall.os, "fsync", sync), patch.object(uninstall.os, "link", link), self.assertRaises(uninstall.RemovalError):
                uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
            self.plugin.assert_not_called()
            self.intact()

    def test_exclusive_publication_preserves_racing_unrelated_destination(self):
        destination = self.home / "exports/wipe.tar"
        original = os.link
        def race(*args, **kwargs):
            destination.write_text("unrelated racing file")
            return original(*args, **kwargs)
        with patch.object(uninstall.os, "link", race), self.assertRaises(uninstall.RemovalError):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe", export_path=destination), self.home)
        self.assertEqual(destination.read_text(), "unrelated racing file")
        self.assertEqual(list(destination.parent.iterdir()), [destination])
        self.plugin.assert_not_called()
        self.intact()

    def test_cross_device_publication_error_is_not_a_copy_or_overwrite_fallback(self):
        with patch.object(uninstall.os, "link", side_effect=OSError(errno.EXDEV, "fixture different filesystem")), self.assertRaises(uninstall.RemovalError):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.plugin.assert_not_called()
        self.intact()

    def test_corrupted_archive_is_rejected_by_real_member_verification(self):
        original = uninstall._verify_export
        def corrupt(handle, expected, deadline):
            handle.seek(512)
            handle.write(b"!")
            handle.flush()
            return original(handle, expected, deadline)
        with patch.object(uninstall, "_verify_export", corrupt), self.assertRaisesRegex(uninstall.RemovalError, "digest"):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.plugin.assert_not_called()
        self.intact()

    def test_replaced_temp_name_is_not_followed_or_deleted_as_our_archive(self):
        original = os.link
        target = self.write("unrelated-target", "unrelated target")
        def replace(source, destination, **kwargs):
            os.unlink(source, dir_fd=kwargs["src_dir_fd"])
            os.symlink(target, source, dir_fd=kwargs["src_dir_fd"])
            return original(source, destination, **kwargs)
        with patch.object(uninstall.os, "link", replace), self.assertRaises(uninstall.RemovalError):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.assertEqual(target.read_text(), "unrelated target")
        self.plugin.assert_not_called()
        self.intact()

    def test_replaced_parent_during_publication_does_not_delete_replacement(self):
        parent = self.home / "exports"
        destination = parent / "wipe.tar"
        original = uninstall._export_digest
        reads = 0
        def replace(handle, deadline):
            nonlocal reads
            result = original(handle, deadline)
            reads += 1
            if reads == 2:
                parent.rename(self.home / "moved-private-export")
                parent.mkdir(mode=0o700)
                destination.write_text("unrelated replacement")
            return result
        with patch.object(uninstall, "_export_digest", replace), self.assertRaises(uninstall.RemovalError):
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe", export_path=destination), self.home)
        self.assertEqual(destination.read_text(), "unrelated replacement")
        self.plugin.assert_not_called()
        self.intact()

    def test_fresh_active_output_after_export_blocks_wipe_and_returns_recovery_receipt(self):
        self.cli.side_effect = [IDLE, IDLE, IDLE, {**IDLE, "stream": {"active": True}}]
        with self.assertRaises(uninstall.RemovalError) as caught:
            uninstall.apply_plan(uninstall.build_plan(self.home, "wipe"), self.home)
        self.assertEqual(caught.exception.completed, [])
        self.archive(caught.exception.export)
        self.plugin.assert_not_called()
        self.intact()

    def test_later_removal_failure_reports_private_export_without_secret_content(self):
        self.plugin.side_effect = uninstall.RemovalError("fixture loader unavailable")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(uninstall.main(["--wipe", "--yes", "--json"]), 1)
        answer = json.loads(output.getvalue())
        self.assertEqual(answer["removed"], [])
        self.assertTrue(answer["export"]["contains_credentials"])
        self.archive(answer["export"])
        self.assertNotIn(SECRET, output.getvalue())
        self.intact()

    def test_recordings_are_exported_only_with_separate_explicit_selection(self):
        plan = uninstall.build_plan(self.home, "wipe", recordings=[str(self.media)])
        uninstall.apply_plan(plan, self.home)
        _, content = self.archive(plan["export_result"])
        self.assertEqual(content["home/Videos/OBSGod/" + self.media.name], b"explicit media")
        self.assertFalse(self.media.exists())

    def test_backup_loss_after_helper_stops_remaining_deletions_without_false_retention_claim(self):
        destination = self.home / "exports/wipe.tar"
        self.plugin.side_effect = lambda *_: destination.unlink()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(uninstall.main(["--wipe", "--export", str(destination), "--yes", "--json"]), 1)
        answer = json.loads(output.getvalue())
        self.assertEqual(answer["removed"], [])
        self.assertIn("was created", answer["message"])
        self.assertIn("verify that archive", answer["message"])
        self.assertNotIn("retains credentials at", answer["message"])
        self.intact()

    def test_supplied_home_alias_retains_the_same_private_export_and_removal_roots(self):
        alias = Path(self.temp.name) / "home-alias"
        alias.symlink_to(self.home)
        plan = uninstall.build_plan(alias, "wipe")
        uninstall.apply_plan(plan, alias)
        self.archive(plan["export_result"])
        self.assertFalse(self.settings.exists())


if __name__ == "__main__":
    unittest.main()
