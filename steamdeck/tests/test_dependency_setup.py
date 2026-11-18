"""Run real fake-Flatpak processes and a real owned Unix session socket.

These fixtures prove transaction/lifecycle behavior, not SteamOS, Flathub, OBS
launch, a real D-Bus session or provider streaming acceptance.
"""
import asyncio
import fcntl
import importlib.util
import json
import os
import pwd
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "decky/dependency_setup.py"
spec = importlib.util.spec_from_file_location("dependency_setup_under_test", MODULE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

OBS_REF = "app/com.obsproject.Studio/x86_64/stable"
GST_REF = "runtime/com.obsproject.Studio.Plugin.Gstreamer/x86_64/stable"

FAKE_FLATPAK = r'''import json, os, pathlib, signal, sys, time
root = pathlib.Path(os.environ["FIXTURE_ROOT"])
args = sys.argv[1:]
with (root / "commands.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\n")
state = json.loads((root / "flatpak.json").read_text())
def save():
    temporary = root / (".state-" + str(os.getpid()))
    temporary.write_text(json.dumps(state))
    temporary.replace(root / "flatpak.json")
if args[0] == "list":
    scope = "user" if "--user" in args else "system"
    for ref, version in state[scope].items():
        print(ref + "\t" + version)
elif args[0] == "remotes":
    if state["remote"] is not None:
        print("flathub\t" + state["remote"] + "\t" + state.get("remote_options", ""))
elif args[0] == "info":
    ref = args[-1]
    if "--show-ref" in args:
        print(state.get("active_obs", next((r for r in state["user"] if r.startswith("app/com.obsproject.Studio/")), "")))
    elif ref.startswith("app/"):
        print(state.get("obs_metadata", "[Application]\nname=com.obsproject.Studio\n[Extension com.obsproject.Studio.Plugin]\nversion=stable\n"))
    else:
        print(state.get("gst_metadata", "[ExtensionOf]\nref=" + state.get("active_obs", "app/com.obsproject.Studio/x86_64/stable") + "\n"))
elif args[0] == "remote-add":
    assert "--user" in args and "--if-not-exists" in args
    if state["remote"] is None:
        state["remote"] = "https://dl.flathub.org/repo/"
        save()
elif args[0] == "install":
    assert "--user" in args and "--system" not in args
    ref = args[-1]
    stage = "obs" if ref.startswith("app/") else "gstreamer"
    if state.get("failure_stage") == stage:
        print(state.get("failure", "failed"), file=sys.stderr)
        sys.exit(1)
    state["user"][ref] = "33.0.1" if stage == "obs" else "0.4.1"
    save()
    (root / (stage + ".started")).write_text(str(os.getpid()))
    if state.get("hold_stage") == stage:
        while not (root / (stage + ".release")).exists():
            time.sleep(0.01)
        (root / (stage + ".finished")).write_text(str(os.getpid()))
    if state.get("delay_stage") == stage:
        time.sleep(state.get("delay_seconds", 30))
    if state.get("noise"):
        print(state["noise"] * 20000)
else:
    print("Unexpected command", file=sys.stderr)
    sys.exit(90)
'''


@unittest.skipIf(os.geteuid() == 0, "Real unprivileged fixtures are run by RootRunner instead.")
class DependencySetupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dependency-setup-")
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.bus = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.bus.bind(str(self.runtime / "bus"))
        self.bus.listen(10)
        self.bus.settimeout(0.1)
        self.stop_bus = threading.Event()

        def drain():
            while not self.stop_bus.is_set():
                try:
                    connection, _ = self.bus.accept()
                    connection.close()
                except socket.timeout:
                    continue
                except OSError:
                    return

        self.thread = threading.Thread(target=drain, daemon=True)
        self.thread.start()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "flatpak"
        fake.write_text("#!" + sys.executable + "\n" + FAKE_FLATPAK)
        fake.chmod(0o700)
        self.state = {"user": {}, "system": {}, "remote": "https://dl.flathub.org/repo/"}
        self.save()
        self.env = dict(os.environ, HOME=str(self.home), DECKY_USER_HOME=str(self.home),
                        DECKY_USER=pwd.getpwuid(os.getuid()).pw_name, XDG_RUNTIME_DIR=str(self.runtime),
                        DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(self.runtime / "bus"),
                        PATH=str(self.bin), FIXTURE_ROOT=str(self.root))
        for key in ("XDG_DATA_HOME", "FLATPAK_USER_DIR", "FLATPAK_SYSTEM_DIR"):
            self.env.pop(key, None)
        # Only the passwd account's home is substituted. UID, file owners,
        # subprocesses, socket ownership and SO_PEERCRED are real.
        self.account = patch.object(setup.pwd, "getpwuid", return_value=SimpleNamespace(
            pw_dir=str(self.home), pw_name=self.env["DECKY_USER"]))
        self.account.start()
        self.jobs = []

    async def asyncTearDown(self):
        for job in self.jobs:
            await job.close()
        self.account.stop()
        self.stop_bus.set()
        self.bus.close()
        self.thread.join(1)
        self.temporary.cleanup()

    def save(self):
        (self.root / "flatpak.json").write_text(json.dumps(self.state))

    def commands(self):
        path = self.root / "commands.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def mutations(self):
        return [command for command in self.commands() if command[0] in {"install", "remote-add"}]

    def job(self, **options):
        value = setup.DependencySetup(self.root / "jobs", self.env, **options)
        self.jobs.append(value)
        return value

    async def finished(self, job, seconds=8):
        async def wait():
            while job.running:
                await asyncio.sleep(0.01)
            return await job.status()
        return await asyncio.wait_for(wait(), seconds)

    async def started(self, stage):
        async def wait():
            while not (self.root / (stage + ".started")).exists():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait(), 4)

    async def test_status_and_later_are_read_only_then_explicit_consent_installs(self):
        self.state["remote"] = None
        self.save()
        job = self.job()
        first = await job.status()
        self.assertEqual(first["state"], "setup_required")
        self.assertTrue(first["remote"]["needs_add"])
        self.assertTrue(first["can_install"])
        await job.start(consent=False)
        await job.start(consent="yes")
        self.assertEqual(self.mutations(), [])
        started = await job.start(consent=True)
        self.assertEqual(started["state"], "running")
        operation_id = started["operation"]["id"]
        result = await self.finished(job)
        self.assertTrue(result["ready"])
        self.assertEqual(result["operation"]["id"], operation_id)
        self.assertEqual([c[0] for c in self.mutations()], ["remote-add", "install", "install"])
        self.assertEqual([c[-1] for c in self.mutations()[1:]], [OBS_REF, GST_REF])
        self.assertFalse(any(c[0] in {"run", "uninstall", "repair", "update"} for c in self.commands()))
        receipt = self.root / "jobs/dependencies/receipt.json"
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    async def test_existing_compatible_refs_need_no_mutations_or_remote_changes(self):
        self.state.update(user={OBS_REF: "33.0.1", GST_REF: "0.4.1"}, remote="https://unrelated.invalid/repo")
        self.save()
        job = self.job()
        await job.start(True)
        result = await self.finished(job)
        self.assertTrue(result["ready"])
        self.assertFalse(result["remote"]["valid"])
        self.assertEqual(self.mutations(), [])

    async def test_reopen_and_repeated_install_share_job_then_cancel_preserves_partial_ref(self):
        self.state.update(delay_stage="obs")
        self.save()
        job = self.job()
        first = await job.start(True)
        await self.started("obs")
        again = await job.start(True)
        self.assertEqual(again["operation"]["id"], first["operation"]["id"])
        observer = self.job()
        reopened = await observer.status()
        self.assertEqual(reopened["operation"]["id"], first["operation"]["id"])
        self.assertEqual(reopened["state"], "running")
        self.assertFalse(reopened["can_install"])
        self.assertFalse(reopened["can_cancel"])
        self.assertTrue((await job.status())["can_cancel"])
        self.assertEqual(len(self.mutations()), 1)
        cancelled = await job.cancel()
        self.assertEqual(cancelled["state"], "cancelling")
        result = await self.finished(job)
        self.assertEqual(result["operation"]["state"], "cancelled")
        self.assertTrue(result["dependencies"][0]["compatible"])
        self.assertFalse(result["ready"])
        self.state = json.loads((self.root / "flatpak.json").read_text())
        self.state.pop("delay_stage")
        self.save()
        await observer.start(True)
        result = await self.finished(observer)
        self.assertTrue(result["ready"])
        self.assertEqual([c[-1] for c in self.mutations()], [OBS_REF, GST_REF])

    async def test_backend_close_marks_interrupted_and_reload_retries_only_missing(self):
        self.state.update(delay_stage="obs")
        self.save()
        job = self.job()
        await job.start(True)
        await self.started("obs")
        await job.close()
        replacement = self.job()
        result = await replacement.status()
        self.assertEqual(result["operation"]["state"], "interrupted")
        self.assertTrue(result["can_install"])
        self.state = json.loads((self.root / "flatpak.json").read_text())
        self.state.pop("delay_stage")
        self.save()
        await replacement.start(True)
        self.assertTrue((await self.finished(replacement))["ready"])
        self.assertEqual([c[-1] for c in self.mutations()], [OBS_REF, GST_REF])

    async def test_failures_are_actionable_and_raw_output_does_not_escape(self):
        for raw, expected in (("No space left on device", "disk_full"),
                              ("Could not resolve host", "network"),
                              ("Permission denied", "permission"),
                              ("GPG signature verification failed", "verification")):
            with self.subTest(code=expected):
                self.state.update(failure_stage="obs", failure=raw + " /home/private/person stream_key=never-show-this")
                self.save()
                job = self.job()
                await job.start(True)
                result = await self.finished(job)
                self.assertEqual(result["operation"]["error_code"], expected)
                self.assertTrue(result["can_install"])
                public = json.dumps(result)
                private_receipt = (self.root / "jobs/dependencies/receipt.json").read_text()
                for value in (public, private_receipt):
                    self.assertNotIn("never-show-this", value)
                    self.assertNotIn("/home/private", value)

    async def test_system_only_refs_remote_conflicts_and_old_obs_are_not_reinstalled(self):
        cases = [({"system": {OBS_REF: "33.0.1"}}, "system_scope"),
                 ({"remote": "https://unrelated.invalid/repo"}, "remote_conflict"),
                 ({"remote_options": "no-gpg-verify"}, "remote_conflict"),
                 ({"user": {OBS_REF: "27.2.0"}}, "obs_version"),
                 ({"user": {OBS_REF: "33.0.1"}, "obs_metadata": "[Application]\nname=com.obsproject.Studio\n"}, "compatibility")]
        for overrides, expected in cases:
            with self.subTest(code=expected):
                self.state = {"user": {}, "system": {}, "remote": "https://dl.flathub.org/repo/"}
                self.state.update(overrides)
                self.save()
                job = self.job()
                await job.start(True)
                result = await self.finished(job)
                self.assertEqual(result["reason"]["code"], expected)
                self.assertFalse(result["can_install"])
        self.assertEqual(self.mutations(), [])

    async def test_active_obs_branch_and_extension_owner_are_verified(self):
        beta_obs = OBS_REF.replace("stable", "beta")
        beta_gst = GST_REF.replace("stable", "beta")
        self.state.update(user={OBS_REF: "33.0.1", beta_obs: "35.0.0", GST_REF: "0.4.1", beta_gst: "0.5.0"},
                          active_obs=beta_obs, obs_metadata="[Extension com.obsproject.Studio.Plugin]\nversion=beta\n")
        self.save()
        result = await self.job().status()
        self.assertTrue(result["ready"])
        self.assertEqual(result["dependencies"][0]["ref"], beta_obs)
        self.assertEqual(result["dependencies"][1]["ref"], beta_gst)
        self.state["gst_metadata"] = "[ExtensionOf]\nref=" + OBS_REF + "\n"
        self.save()
        job = self.job()
        await job.start(True)
        result = await self.finished(job)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"]["code"], "compatibility")
        self.assertEqual(self.mutations(), [])

    async def test_shared_control_lock_and_preflight_prevent_output_races(self):
        shared = self.root / "state"
        shared.mkdir(mode=0o700)
        lock = shared / "control.lock"
        descriptor = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        calls = []

        async def preflight():
            with lock.open() as stream:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            calls.append("checked")
            return False

        job = self.job(control_lock=lock, preflight=preflight)
        result = await job.start(True)
        self.assertEqual(result["reason"]["code"], "control_busy")
        self.assertEqual(calls, [])
        os.close(descriptor)
        await job.start(True)
        result = await self.finished(job)
        self.assertEqual(result["reason"]["code"], "output_active")
        self.assertEqual(calls, ["checked"])
        self.assertEqual(self.mutations(), [])
        # Rejected preflight released the shared lease.
        with lock.open() as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    async def test_root_wrong_home_missing_bus_and_flatpak_override_are_rejected(self):
        job = self.job()
        with patch.object(setup.os, "geteuid", return_value=0):
            with self.assertRaises(setup.SetupError) as failure:
                job._context()
        self.assertEqual(failure.exception.code, "context")
        for change in ({"HOME": str(self.root)}, {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/not-a-user-bus"},
                       {"FLATPAK_USER_DIR": str(self.root / "other-flatpak")}):
            with self.subTest(change=change):
                value = self.job()
                value.environment.update(change)
                await value.start(True)
                result = await self.finished(value)
                self.assertEqual(result["reason"]["code"], "context")
        self.assertEqual(self.mutations(), [])

    async def test_missing_flatpak_and_unsafe_receipt_fail_closed(self):
        job = self.job()
        job.environment["PATH"] = str(self.root / "absent")
        await job.start(True)
        result = await self.finished(job)
        self.assertEqual(result["reason"]["code"], "flatpak_missing")
        receipt = self.root / "jobs/dependencies/receipt.json"
        target = self.root / "preserve.txt"
        target.write_text("unchanged")
        receipt.unlink()
        receipt.symlink_to(target)
        result = await self.job().status()
        self.assertEqual(result["reason"]["code"], "storage")
        self.assertEqual(target.read_text(), "unchanged")

    async def test_abrupt_parent_loss_keeps_child_lease_until_bounded_worker_finishes(self):
        # A separate parent holds the same kernel lease and runs the real worker.
        # Killing only that parent must not make the orphan's job look retryable.
        state_dir = self.root / "jobs/dependencies"
        state_dir.mkdir(mode=0o700, parents=True)
        operation = {"id": "a" * 32, "state": "running", "stage": "obs", "started_at": time.time(),
                     "finished_at": None, "error_code": None, "cancel_requested": False, "progress": []}
        receipt = state_dir / "receipt.json"
        receipt.write_text(json.dumps({"schema_version": 1, "operation": operation}))
        receipt.chmod(0o600)
        self.state.update(hold_stage="obs")
        self.save()
        release = self.root / "obs.release"

        async def worker_released():
            # A real inherited lease, rather than elapsed fixture sleep, proves
            # the orphan worker has reaped its child and finished.
            with (state_dir / "setup.lock").open() as stream:
                while True:
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return
                    except BlockingIOError:
                        await asyncio.sleep(0.01)

        parent_code = '''import fcntl,os,pathlib,subprocess,sys,time
root=pathlib.Path(sys.argv[1]);fd=os.open(str(root/"jobs/dependencies/setup.lock"),os.O_CREAT|os.O_RDWR,0o600)
fcntl.flock(fd,fcntl.LOCK_EX)
subprocess.Popen([sys.executable,sys.argv[2],"--worker","3",sys.argv[3],"install","--user","--noninteractive","-y","flathub",sys.argv[4]],pass_fds=(fd,),start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(30)
'''
        parent = await asyncio.create_subprocess_exec(sys.executable, "-c", parent_code, str(self.root),
                                                      str(MODULE), str(self.bin / "flatpak"), OBS_REF, env=self.env)
        try:
            await self.started("obs")
            job = self.job()
            result = await job.status()
            self.assertEqual(result["state"], "running")
            self.assertFalse(result["can_install"])
            parent.kill()
            await parent.wait()
            result = await job.status()
            self.assertEqual(result["state"], "running")
            self.assertFalse(result["can_install"])
            retried = await job.start(True)
            self.assertEqual(retried["operation"]["id"], operation["id"])
            self.assertEqual(retried["state"], "running")
            self.assertFalse(retried["can_install"])
            self.assertEqual(len(self.mutations()), 1)
            release.touch()
            await asyncio.wait_for(worker_released(), 4)
            self.assertEqual((self.root / "obs.finished").read_text(),
                             (self.root / "obs.started").read_text())
            result = await job.status()
            self.assertEqual(result["operation"]["state"], "interrupted")
            self.assertTrue(result["dependencies"][0]["compatible"])
            self.assertTrue(result["can_install"])
            self.assertEqual(len(self.mutations()), 1)
        finally:
            if parent.returncode is None:
                parent.kill()
                await parent.wait()
            release.touch()
            await asyncio.wait_for(worker_released(), 4)

    async def test_setup_budget_and_large_output_are_bounded(self):
        self.state.update(delay_stage="obs", delay_seconds=10, noise="secret-output-never-publish")
        self.save()
        job = self.job()
        with patch.object(setup, "SETUP_TIMEOUT", 0.6):
            await job.start(True)
            result = await self.finished(job)
        self.assertEqual(result["operation"]["error_code"], "timeout")
        self.assertTrue(result["dependencies"][0]["compatible"])
        self.assertNotIn("secret-output", json.dumps(result))
        self.assertLessEqual(len(result["operation"]["progress"]), setup.MAX_EVENTS)
        self.state = json.loads((self.root / "flatpak.json").read_text())
        self.state.pop("delay_stage")
        self.save()
        await job.start(True)
        result = await self.finished(job)
        self.assertTrue(result["ready"])
        self.assertNotIn("secret-output", json.dumps(result))
        self.assertLess((self.root / "jobs/dependencies/receipt.json").stat().st_size, 32768)

    async def test_immediate_cancel_before_worker_enters_releases_every_lease(self):
        job = self.job()
        await job.start(True)
        await job.cancel()
        result = await self.finished(job)
        self.assertEqual(result["operation"]["state"], "cancelled")
        self.assertEqual(self.mutations(), [])
        replacement = self.job()
        await replacement.start(True)
        self.assertTrue((await self.finished(replacement))["ready"])

    async def test_start_returns_promptly_before_a_slow_preflight(self):
        waiting = asyncio.Event()

        async def preflight():
            await waiting.wait()
            return True

        job = self.job(preflight=preflight)
        result = await asyncio.wait_for(job.start(True), 0.2)
        self.assertEqual(result["state"], "running")
        self.assertEqual(self.mutations(), [])
        await job.cancel()
        await self.finished(job)
        self.assertEqual(self.mutations(), [])

    async def test_first_install_initializes_missing_shared_control_namespace(self):
        lock = self.home / ".local/state/obsgod/control.lock"

        async def preflight():
            self.assertTrue(lock.exists())
            self.assertEqual(lock.parent.stat().st_mode & 0o777, 0o700)
            return True

        job = self.job(control_lock=lock, preflight=preflight)
        await job.start(True)
        result = await self.finished(job)
        self.assertTrue(result["ready"])

    async def test_saved_progress_cannot_inject_private_paths_into_public_status(self):
        private = self.root / "jobs/dependencies"
        private.mkdir(parents=True, mode=0o700)
        operation = {"id": "b" * 32, "state": "failed", "stage": "finished", "started_at": time.time(),
                     "finished_at": time.time(), "error_code": "flatpak_failed", "cancel_requested": False,
                     "progress": [{"time": time.time(), "level": "error", "message": "/home/private/secret-key"}]}
        receipt = private / "receipt.json"
        receipt.write_text(json.dumps({"schema_version": 1, "operation": operation}))
        receipt.chmod(0o600)
        result = await self.job().status()
        self.assertEqual(result["reason"]["code"], "storage")
        self.assertNotIn("secret-key", json.dumps(result))

    async def test_private_leaves_under_unsafe_writable_ancestors_refuse_before_children(self):
        public = self.root / "renameable"
        public.mkdir(mode=0o777)
        public.chmod(0o777)
        private = public / "private"
        private.mkdir(mode=0o700)
        for scope in ("jobs", "control"):
            with self.subTest(scope=scope):
                jobs = private / "jobs" if scope == "jobs" else self.root / "safe-jobs"
                control = private / "state/control.lock" if scope == "control" else None
                job = setup.DependencySetup(jobs, self.env, control_lock=control)
                self.jobs.append(job)
                result = await job.start(True)
                self.assertEqual(result["reason"]["code"], "storage")
                self.assertFalse(result["can_install"])
                self.assertEqual(self.commands(), [])
        self.assertEqual(private.stat().st_mode & 0o777, 0o700)
        self.assertFalse((private / "state").exists())

    async def test_trusted_sticky_ancestors_allow_private_job_and_control_namespaces(self):
        public = self.root / "sticky"
        public.mkdir(mode=0o1777)
        public.chmod(0o1777)
        private = public / "private"
        private.mkdir(mode=0o700)
        job = setup.DependencySetup(private / "jobs", self.env, control_lock=private / "state/control.lock")
        self.jobs.append(job)
        await job.start(True)
        result = await self.finished(job)
        self.assertTrue(result["ready"])
        self.assertEqual(public.stat().st_mode & 0o7777, 0o1777)


@unittest.skipUnless(os.geteuid() == 0, "Only needed when the outer test runner is root.")
class RootRunner(unittest.TestCase):
    def test_fixtures_execute_as_an_actual_unprivileged_user(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "DependencySetupTests", "-v"],
                                user=65534, group=65534, extra_groups=[], capture_output=True, text=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
