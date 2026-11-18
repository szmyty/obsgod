"""Legacy recovery uses the candidate's native leased dependency transaction.

Real fake-Flatpak children, file leases and an owned Unix session socket prove
the local boundary; they are not actual SteamOS/Flathub acceptance.
"""
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install
import test_dependency_setup as native


IDLE = {"ok": True, "state": "stopped", "configured": False, "output_known": True,
        "process": "absent", "recording": False, "stream": {"active": False, "reconnecting": False},
        "media": {"known": True, "recording": {"active": False, "paused": False}, "replay_active": False}}


@unittest.skipIf(os.geteuid() == 0, "Real user/session fixtures run through RootRunner.")
class InstallerDependencyTests(unittest.IsolatedAsyncioTestCase):
    # Reuse fixture infrastructure, without inheriting its separate test cases.
    save = native.DependencySetupTests.save
    commands = native.DependencySetupTests.commands
    mutations = native.DependencySetupTests.mutations
    started = native.DependencySetupTests.started

    async def asyncSetUp(self):
        await native.DependencySetupTests.asyncSetUp(self)
        self.env["XDG_STATE_HOME"] = str(self.home / ".local/state")
        self.env["DECKY_HOME"] = str(self.home / "homebrew")
        for name in ("DECKY_PLUGIN_DIR", "DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR",
                     "DECKY_PLUGIN_LOG_DIR", "OBSGOD_DECKY_STORAGE_MAP"):
            self.env.pop(name, None)
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.package = self.root / "package"
        self.package.mkdir()
        self.archive = self.package / "obsgod-decky.zip"
        self.write_policy(native.MODULE.read_bytes())
        self.root_patch = patch.object(install, "ROOT", self.package)
        self.root_patch.start()
        self.loaded_policy = install.dependency_policy(self.manifest)
        self.policy = self.loaded_policy.__enter__()
        self.bridge = Mock()
        self.bridge.run_cli.return_value = IDLE
        self.base = self.home / ".local/share/obsgod"
        install.owned_directory(self.base, self.home)

    async def asyncTearDown(self):
        self.loaded_policy.__exit__(None, None, None)
        self.root_patch.stop()
        self.environment.stop()
        await native.DependencySetupTests.asyncTearDown(self)

    def write_policy(self, source, name="obsgod/dependency_setup.py"):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr(name, source)
        self.manifest = {"files": {self.archive.name: hashlib.sha256(self.archive.read_bytes()).hexdigest()}}

    async def recover(self):
        with install.installation_lock(self.base):
            return await install.run_dependency_setup(self.policy, self.bridge, self.home)

    def assert_lease_held(self, path):
        with path.open("r+") as lock:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    async def test_fresh_install_checks_idle_under_both_leases_before_trusted_mutations(self):
        self.state["remote"] = None
        self.save()

        def observe(action, timeout):
            self.assertEqual((action, timeout), ("status", 6))
            self.assertEqual(self.mutations(), [])
            self.assert_lease_held(self.base / "install.lock")
            self.assert_lease_held(self.home / ".local/state/obsgod/control.lock")
            self.assert_lease_held(self.home / "homebrew/data/obsgod/jobs/dependencies/setup.lock")
            return IDLE

        self.bridge.run_cli.side_effect = observe
        result = await self.recover()
        self.assertTrue(result["ready"])
        self.assertEqual(self.mutations(), [
            ["remote-add", "--user", "--if-not-exists", "flathub", self.policy.FLATHUB],
            ["install", "--user", "--noninteractive", "-y", "flathub", native.OBS_REF],
            ["install", "--user", "--noninteractive", "-y", "flathub", native.GST_REF],
        ])
        self.bridge.run_cli.assert_called_once()
        with install.control_lock(self.home):
            pass

    async def test_installed_compatible_refs_are_reused_without_mutation(self):
        self.state["user"] = {native.OBS_REF: "33.0.1", native.GST_REF: "0.4.1"}
        self.save()
        result = await self.recover()
        self.assertTrue(result["ready"])
        self.assertEqual(self.mutations(), [])

    async def test_active_unknown_recording_paused_replay_and_busy_snapshots_never_mutate(self):
        snapshots = [
            {**IDLE, "stream": {"active": True}},
            {**IDLE, "stream": {"active": False, "reconnecting": True}},
            {**IDLE, "ok": False, "state": "unknown", "output_known": False},
            {**IDLE, "recording": True},
            {**IDLE, "media": {"known": True, "replay_active": False,
                               "recording": {"active": False, "paused": True}}},
            {**IDLE, "media": {"known": True, "replay_active": True,
                               "recording": {"active": False, "paused": False}}},
            {**IDLE, "operation": {"action": "start", "state": "running"}},
            {**IDLE, "media": {"known": True, "replay_active": False}},
        ]
        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot):
                self.bridge.run_cli.return_value = snapshot
                with self.assertRaises(RuntimeError):
                    await self.recover()
                self.assertEqual(self.mutations(), [])
        self.assertTrue(all(call.args[0] == "status" for call in self.bridge.run_cli.call_args_list))

    async def test_busy_shared_control_prevents_flatpak_queries_and_mutators(self):
        with install.control_lock(self.home):
            with self.assertRaisesRegex(RuntimeError, "operation is busy"):
                await self.recover()
        self.assertEqual(self.commands(), [])
        self.bridge.run_cli.assert_not_called()

    async def test_busy_native_setup_does_not_start_a_second_transaction(self):
        job = self.policy.DependencySetup(self.home / "homebrew/data/obsgod/jobs", self.env)
        job._initialize()
        self.assertTrue(job._acquire())
        try:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                await self.recover()
        finally:
            job._release()
        self.assertEqual(self.commands(), [])
        self.bridge.run_cli.assert_not_called()

    async def test_wrong_disabled_and_unverified_flathub_remotes_never_mutate(self):
        for url, options in [("https://unrelated.invalid/repo", ""),
                             ("https://dl.flathub.org/repo/", "disabled"),
                             ("https://dl.flathub.org/repo/", "no-gpg-verify")]:
            with self.subTest(url=url, options=options):
                self.state.update(remote=url, remote_options=options)
                self.save()
                with self.assertRaisesRegex(RuntimeError, "Flathub"):
                    await self.recover()
                self.assertEqual(self.mutations(), [])

    async def test_only_missing_extension_branch_from_obs_metadata_is_installed(self):
        self.state["user"] = {native.OBS_REF: "33.0.1"}
        self.state["obs_metadata"] = "[Extension com.obsproject.Studio.Plugin]\nversion=33\n"
        self.save()
        await self.recover()
        self.assertEqual(self.mutations(), [["install", "--user", "--noninteractive", "-y", "flathub",
            "runtime/com.obsproject.Studio.Plugin.Gstreamer/x86_64/33"]])

    async def test_system_only_old_obs_and_wrong_extension_owner_never_mutate(self):
        cases = [
            {"user": {}, "system": {native.OBS_REF: "33.0.1"}},
            {"user": {native.OBS_REF: "27.2.0"}, "system": {}},
            {"user": {native.OBS_REF: "33.0.1", native.GST_REF: "0.4.1"}, "system": {},
             "gst_metadata": "[ExtensionOf]\nref=app/com.unrelated.OBS/x86_64/stable\n"},
        ]
        for values in cases:
            with self.subTest(values=values):
                self.state.update(values)
                self.save()
                with self.assertRaises(RuntimeError):
                    await self.recover()
                self.assertEqual(self.mutations(), [])

    async def test_invalid_actual_session_fails_before_flatpak(self):
        with patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/missing/bus"}):
            with self.assertRaisesRegex(RuntimeError, "session"):
                await self.recover()
        self.assertEqual(self.commands(), [])

    async def test_cancellation_preserves_partial_install_and_retry_only_installs_missing_ref(self):
        sentinel = self.home / "ordinary-obs-settings"
        sentinel.write_text("preserve ordinary OBS and shared dependencies")
        self.state.update(delay_stage="obs", delay_seconds=30)
        self.save()
        task = asyncio.create_task(self.recover())
        try:
            await self.started("obs")
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.state = json.loads((self.root / "flatpak.json").read_text())
        self.assertIn(native.OBS_REF, self.state["user"])
        self.assertNotIn(native.GST_REF, self.state["user"])
        self.state.pop("delay_stage")
        self.save()
        await self.recover()
        self.assertEqual([command[-1] for command in self.mutations()], [native.OBS_REF, native.GST_REF])
        self.assertEqual(sentinel.read_text(), "preserve ordinary OBS and shared dependencies")
        self.assertTrue(all(command[0] not in {"remove", "uninstall", "run"} for command in self.commands()))

    async def test_synchronous_browser_entry_verifies_package_and_install_lease(self):
        with patch.object(install, "verify_payload", return_value=self.manifest), \
                patch.object(install, "load_module", wraps=install.load_module) as loader:
            # Only the bridge is synthetic. The ZIP policy and workers are real.
            original = loader._mock_wraps
            loader.side_effect = lambda name, path: self.bridge if name == "obsgod_install_bridge" else original(name, path)

            def observe(action, timeout):
                self.assert_lease_held(self.base / "install.lock")
                return IDLE

            self.bridge.run_cli.side_effect = observe
            await asyncio.to_thread(install.ensure_dependencies)
        self.assertEqual([command[-1] for command in self.mutations()], [native.OBS_REF, native.GST_REF])

    async def test_policy_comes_from_candidate_zip_and_hash_mismatch_has_no_side_effects(self):
        marker = self.policy.__file__
        self.assertFalse(Path(marker).is_relative_to(install.ROOT))
        self.assertEqual(Path(marker).read_bytes(), native.MODULE.read_bytes())
        self.archive.write_bytes(b"changed after payload verification")
        with self.assertRaisesRegex(RuntimeError, "verified native dependency setup"):
            with install.dependency_policy(self.manifest):
                self.fail("changed archive was executed")
        self.assertEqual(self.commands(), [])

    async def test_legacy_zip_without_native_policy_is_not_an_automatic_fallback(self):
        self.write_policy(b"not a native setup worker", "obsgod/main.py")
        with self.assertRaisesRegex(RuntimeError, "current Decky plugin"):
            with install.dependency_policy(self.manifest):
                self.fail("legacy unguarded dependency path was reached")
        self.assertEqual(self.commands(), [])

    async def test_final_observation_cannot_join_a_different_native_job_receipt(self):
        release = self.policy.DependencySetup._release
        replaced = False

        def other_job_after_release(job):
            nonlocal replaced
            release(job)
            if not replaced and job._operation and job._operation.get("state") == "ready":
                receipt = job.directory / "receipt.json"
                value = json.loads(receipt.read_text())
                value["operation"]["id"] = "e" * 32
                receipt.write_text(json.dumps(value))
                replaced = True

        with patch.object(self.policy.DependencySetup, "_release", other_job_after_release):
            with self.assertRaisesRegex(RuntimeError, "setup changed"):
                await self.recover()
        self.assertEqual([command[-1] for command in self.mutations()], [native.OBS_REF, native.GST_REF])


@unittest.skipUnless(os.geteuid() == 0, "Only needed when the outer runner is root.")
class RootRunner(unittest.TestCase):
    def test_real_user_fixtures(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "InstallerDependencyTests", "-v"],
                                user=65534, group=65534, extra_groups=[], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
