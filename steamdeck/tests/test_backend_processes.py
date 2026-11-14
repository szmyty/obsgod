"""Real Linux process ownership regressions; no OBS, Flatpak or network calls."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


BACKEND = Path(__file__).resolve().parents[1] / "decky/main.py"

HELPER = r'''import fcntl, json, os, signal, sys, time
from pathlib import Path
root = Path(__file__).resolve().parents[1]
action = sys.argv[-1]
if (root / 'frozen-mode').exists():
    (root / 'helper-environment.json').write_text(json.dumps({
        name: os.environ.get(name) for name in
        ('PYTHONHOME', 'PYTHONPATH', 'LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG')}))
def event(name):
    with (root / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'event': name, 'pid': os.getpid()}) + '\n')
event(action)
if action == 'start':
    # Model a command stalled outside a cancellable Go request. Teardown must
    # retain ownership and eventually kill this command, never all OBS processes.
    signal.signal(signal.SIGINT, lambda *_: event('start-interrupted'))
    if (root / 'lease-mode').exists():
        lease = (root / 'control.lock').open('a')
        fcntl.flock(lease, fcntl.LOCK_EX)
        event('start-leased')
    time.sleep(6)
    (root / 'late-start').write_text('a Start command mutated after its owner left')
elif action == 'stop' and (root / 'lease-mode').exists():
    with (root / 'control.lock').open('a') as lease:
        event('stop-waiting')
        fcntl.flock(lease, fcntl.LOCK_EX)
        event('stop-applied')
elif action == 'mixer':
    time.sleep(8)
print(json.dumps({'ok': True, 'state': 'stopped', 'output_known': True,
    'process': 'absent', 'stream': {'active': False}, 'recording': False,
    'media': {'known': True, 'replay_active': False}}))
'''

OWNER = r'''import asyncio, importlib.util, json, os, signal, sys
from pathlib import Path
source, root, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
# This is the exact module name used by the pinned official Decky loader.
spec = importlib.util.spec_from_file_location('_', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
async def run():
    plugin = module.Plugin()
    plugin._plugin_root = lambda: root
    plugin._child_environment = lambda: dict(os.environ)
    if mode == 'frozen-loader':
        # PyInstaller points sys.executable at PluginLoader, which cannot run
        # Python source. Give it an executable trap instead of an interpreter.
        module.sys.frozen = True
        module.sys.executable = str(root / 'PluginLoader')
        os.environ['PYTHONHOME'] = '/fixture/poisoned-python-home'
        os.environ['PYTHONPATH'] = '/fixture/poisoned-python-path'
        os.environ['LD_LIBRARY_PATH'] = '/fixture/loader-bundled-libraries'
        os.environ['LD_LIBRARY_PATH_ORIG'] = '/usr/lib'
        actual_spawn = module.asyncio.create_subprocess_exec
        async def record_spawn(*args, **kwargs):
            with (root / 'guard-spawns.jsonl').open('a') as stream:
                stream.write(json.dumps(list(args)) + '\n')
            return await actual_spawn(*args, **kwargs)
        module.asyncio.create_subprocess_exec = record_spawn
    if mode == 'late-attachment':
        actual_spawn = module.asyncio.create_subprocess_exec
        async def delayed_spawn(*args, **kwargs):
            process = await actual_spawn(*args, **kwargs)
            if args[-1] == 'start':
                (root / 'spawning').write_text(str(process.pid))
                await asyncio.sleep(5.25)
            return process
        module.asyncio.create_subprocess_exec = delayed_spawn
    stopped = asyncio.Event()
    async def shutdown():
        result = await plugin._unload()
        (root / 'acknowledged').write_text(json.dumps(result))
        if mode == 'late-attachment':
            # Keep this backend alive after acknowledgement, so parent death
            # alone cannot hide a late permission-handshake regression.
            while not (root / 'release-owner').exists():
                await asyncio.sleep(.01)
        stopped.set()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM,
        lambda: asyncio.create_task(shutdown()))
    starting = asyncio.create_task(plugin.start())
    while (not (root / 'spawning').exists() if mode == 'late-attachment'
           else plugin.pending is None):
        await asyncio.sleep(.001)
    if mode == 'slow-observations':
        class Dependencies:
            running = False
            async def close(self):
                (root / 'dependency-close').touch()
                await asyncio.sleep(8)
        plugin._dependency_job = Dependencies()
    (root / 'ready').touch()
    await stopped.wait()
    # The loader stops its event loop after the hook; it does not grant these
    # RPCs another cancellation budget after acknowledgement.
    if not starting.done():
        starting.cancel()
    await asyncio.gather(starting, return_exceptions=True)
asyncio.run(run())
'''


@unittest.skipUnless(sys.platform == "linux", "Linux parent-death contract")
class BackendProcessOwnership(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="obsgod-backend-process-")
        self.root = Path(self.temporary.name)
        (self.root / "bin").mkdir()
        helper = self.root / "bin/obsgod"
        helper.write_text("#!" + sys.executable + "\n" + HELPER)
        helper.chmod(0o700)
        self.owner_source = self.root / "owner.py"
        self.owner_source.write_text(OWNER)
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3)
            process.communicate(timeout=3)
        for row in self.events():
            try:
                os.kill(row["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.temporary.cleanup()

    def launch(self, mode="normal"):
        process = subprocess.Popen(
            [sys.executable, str(self.owner_source), str(BACKEND), str(self.root), mode],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.processes.append(process)
        self.wait_for(lambda: (self.root / "ready").exists(), "backend Start attachment", process)
        if mode != "late-attachment":
            self.wait_for(lambda: any(row["event"] == "start" for row in self.events()),
                          "fake Start execution", process)
        return process

    def events(self):
        path = self.root / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def wait_for(self, predicate, description, process=None, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            if process is not None and process.poll() is not None:
                _, error = process.communicate()
                self.fail("backend exited before " + description + ": " + error.decode())
            time.sleep(.01)
        self.fail("timed out waiting for " + description)

    @staticmethod
    def living(pid):
        try:
            # Orphans may remain zombies until the host's init reaps them.
            return Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except FileNotFoundError:
            return False

    def assert_owned_start_dead(self):
        starts = [row["pid"] for row in self.events() if row["event"] == "start"]
        self.assertEqual(len(starts), 1)
        self.wait_for(lambda: not self.living(starts[0]), "owned Start termination")
        self.assertFalse((self.root / "late-start").exists())

    def test_official_five_second_stop_budget_cancels_start_before_slow_observations(self):
        process = self.launch("slow-observations")
        before = time.monotonic()
        process.send_signal(signal.SIGTERM)
        # Faithful loader deadline: SIGTERM triggers the lifecycle hook, then
        # SIGKILL follows at five seconds if the backend has not acknowledged.
        killed_at_deadline = False
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            killed_at_deadline = True
            process.kill()
            process.wait(timeout=2)
        self.assertFalse(killed_at_deadline, "unload exhausted Decky's five-second stop budget")
        self.assertLess(time.monotonic() - before, 5)
        self.assertTrue((self.root / "acknowledged").exists())
        self.assertTrue((self.root / "dependency-close").exists())
        self.assertIn("mixer", [row["event"] for row in self.events()])
        self.assert_owned_start_dead()

    def test_late_attachment_never_receives_exec_permission_after_unload_acknowledgement(self):
        process = self.launch("late-attachment")
        process.send_signal(signal.SIGTERM)
        self.wait_for(lambda: (self.root / "acknowledged").exists(), "bounded unload", process, timeout=5)
        self.assertIsNone(process.poll(), "fixture must keep the backend alive after unload")
        child = int((self.root / "spawning").read_text())
        self.wait_for(lambda: not self.living(child), "late guarded command termination", timeout=4)
        self.assertNotIn("start", [row["event"] for row in self.events()],
                         "closing adapter permitted a late Start to exec")
        self.assertFalse((self.root / "late-start").exists())
        (self.root / "release-owner").touch()
        process.wait(timeout=2)

    def test_final_stop_acquires_control_lease_after_stuck_start_is_killed(self):
        (self.root / "lease-mode").touch()
        process = self.launch()
        self.wait_for(lambda: any(row["event"] == "start-leased" for row in self.events()),
                      "fake Start control lease", process)
        before = time.monotonic()
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
            self.fail("unload exhausted Decky's five-second stop budget behind Start's lease")
        self.assertLess(time.monotonic() - before, 5)
        self.assertTrue((self.root / "acknowledged").exists())
        rows = self.events()
        stops = [row["pid"] for row in rows if row["event"] == "stop"]
        applied = [row["pid"] for row in rows if row["event"] == "stop-applied"]
        self.assertGreaterEqual(len(stops), 2, "a fresh Stop must follow the stuck Start's termination")
        self.assertIn(stops[0], [row["pid"] for row in rows if row["event"] == "stop-waiting"])
        self.assertIn(stops[-1], applied, "the final Stop never acquired the released control lease")
        observed = json.loads((self.root / "acknowledged").read_text())
        self.assertTrue(observed["output_known"])
        self.assertFalse(observed["stream"]["active"])
        self.assert_owned_start_dead()

    def test_abrupt_backend_death_kills_only_its_owned_command(self):
        # A separate process stands in for ordinary OBS, outside the adapter's
        # command ownership. Parent-death cleanup must leave it untouched.
        ordinary = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                    start_new_session=True)
        self.processes.append(ordinary)
        process = self.launch()
        process.kill()
        process.wait(timeout=2)
        self.assert_owned_start_dead()
        self.assertIsNone(ordinary.poll())

    def test_frozen_loader_uses_system_python_with_clean_helper_environment(self):
        (self.root / "frozen-mode").touch()
        stub = self.root / "PluginLoader"
        stub.write_text("#!/bin/sh\n: > '" + str(self.root / "frozen-loader-invoked") + "'\nexit 97\n")
        stub.chmod(0o700)
        process = self.launch("frozen-loader")
        before = time.monotonic()
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
            self.fail("frozen-loader unload exhausted Decky's five-second stop budget")
        self.assertLess(time.monotonic() - before, 5)
        self.assertTrue((self.root / "acknowledged").exists())
        self.assertFalse((self.root / "frozen-loader-invoked").exists())
        spawns = [json.loads(line) for line in (self.root / "guard-spawns.jsonl").read_text().splitlines()]
        self.assertTrue(spawns)
        for args in spawns:
            self.assertEqual(Path(args[0]).resolve(), Path("/usr/bin/python3").resolve())
            self.assertEqual(args[1:3], ["-I", "-B"])
        environment = json.loads((self.root / "helper-environment.json").read_text())
        self.assertEqual(environment, {"PYTHONHOME": None, "PYTHONPATH": None,
                                       "LD_LIBRARY_PATH": "/usr/lib", "LD_LIBRARY_PATH_ORIG": None})
        self.assert_owned_start_dead()

    def test_guard_refuses_exec_after_expected_parent_died_during_spawn(self):
        launcher = self.root / "late-launcher.py"
        launcher.write_text(r'''import json, os, subprocess, sys, time
from pathlib import Path
source, root = Path(sys.argv[1]), Path(sys.argv[2])
args = [sys.executable, str(source), '--owned-command', str(os.getpid()),
        str(root / 'bin/obsgod'), 'deck', 'start']
# Delay before the guard starts, modelling late subprocess attachment/exec.
code = 'import os,sys,time; time.sleep(.4); os.execv(sys.argv[1],sys.argv[1:])'
child = subprocess.Popen([sys.executable, '-c', code] + args, stdin=subprocess.PIPE)
child.stdin.write(b'\x01')
child.stdin.close()
(root / 'late-child').write_text(str(child.pid))
time.sleep(60)
''')
        process = subprocess.Popen([sys.executable, str(launcher), str(BACKEND), str(self.root)],
                                   start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(process)
        self.wait_for(lambda: (self.root / "late-child").exists(), "delayed guard spawn", process)
        child = int((self.root / "late-child").read_text())
        process.kill()
        process.wait(timeout=2)
        self.wait_for(lambda: not self.living(child), "late guard refusal")
        self.assertEqual(self.events(), [], "an orphaned guard executed the mutating helper")
        self.assertFalse((self.root / "late-start").exists())

    def test_guard_executes_authorized_command_for_living_owner(self):
        completed = subprocess.run([sys.executable, str(BACKEND), "--owned-command",
                                    str(os.getpid()), str(self.root / "bin/obsgod"), "deck", "status"],
                                   input=b"\x01", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertTrue(json.loads(completed.stdout)["ok"])
        self.assertEqual([row["event"] for row in self.events()], ["status"])


if __name__ == "__main__":
    unittest.main()
