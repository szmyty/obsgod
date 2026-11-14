"""Adapter task and output boundaries during a bounded Decky shutdown."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


spec = importlib.util.spec_from_file_location("teardown_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

IDLE = {"ok": True, "state": "stopped", "output_known": True,
        "process": "absent", "stream": {"active": False},
        "recording": False, "media": {"known": True, "replay_active": False}}


class BackendTeardown(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_and_owned_signal_precede_dependency_or_microphone_await(self):
        plugin = backend.Plugin()
        signals = []
        child = SimpleNamespace(returncode=None, send_signal=signals.append)
        plugin.pending = child
        entered, release = asyncio.Event(), asyncio.Event()

        async def close():
            self.assertTrue(plugin._closing)
            self.assertTrue(plugin.cancel_requested)
            self.assertIn(signal.SIGINT, signals)
            entered.set()
            await release.wait()

        plugin._dependency_job = SimpleNamespace(close=close, running=False)
        with patch.object(plugin, "_run", AsyncMock(return_value=IDLE)):
            unloading = asyncio.create_task(plugin._unload())
            await entered.wait()
            rejected = await plugin.start()
            self.assertFalse(rejected["action_result"]["ok"])
            self.assertFalse(rejected["output_known"])
            release.set()
            await unloading

    async def test_shutdown_drains_invalidated_readers_direct_rpcs_and_update_bookkeeping(self):
        plugin = backend.Plugin()
        waiting = asyncio.Event()
        entered = []

        async def read(action, payload=None, _teardown=False):
            if _teardown:
                return IDLE
            entered.append(action)
            await waiting.wait()
            return IDLE

        with patch.object(plugin, "_run", side_effect=read):
            configuration = asyncio.create_task(plugin.configuration_status())
            status = asyncio.create_task(plugin.status())
            health = asyncio.create_task(plugin.stream_health())
            mixer = asyncio.create_task(plugin.mixer_action({"action": "devices"}))
            while len(entered) != 4:
                await asyncio.sleep(0)
            first_reader = plugin._configuration_task
            plugin._invalidate_configuration()
            newer_configuration = asyncio.create_task(plugin.configuration_status())
            while len(entered) != 5:
                await asyncio.sleep(0)
            plugin._update_task = asyncio.create_task(waiting.wait())
            plugin._cancel_media_task = asyncio.create_task(waiting.wait())
            callers = [configuration, newer_configuration, status, health, mixer]
            result = await plugin._unload()
            await asyncio.gather(*callers, return_exceptions=True)
        self.assertTrue(result["output_known"])
        self.assertTrue(first_reader.cancelled())
        self.assertTrue(plugin._configuration_task.cancelled())
        self.assertTrue(plugin._status_task.cancelled())
        self.assertTrue(plugin._update_task.cancelled())
        self.assertTrue(plugin._cancel_media_task.cancelled())
        self.assertFalse(plugin._rpc_tasks)
        self.assertFalse(plugin._command_tasks)
        self.assertFalse(plugin._configuration_tasks)
        self.assertFalse(plugin._owned_tasks())
        self.assertTrue(all(task.done() for task in callers))

    async def test_active_and_unknown_outputs_are_reported_without_obs_or_media_kills(self):
        observations = [
            {**IDLE, "state": "streaming", "stream": {"active": True}},
            {**IDLE, "state": "recording", "recording": True},
            {**IDLE, "media": {"known": True, "replay_active": True}},
            {**IDLE, "state": "recording", "recording": True,
             "media": {"known": True, "replay_active": True}},
            {**IDLE, "state": "unknown", "output_known": False},
        ]
        for observed in observations:
            with self.subTest(observed=observed):
                plugin = backend.Plugin()
                calls = []

                async def run(action, payload=None, _teardown=False):
                    calls.append((action, payload, _teardown))
                    return observed

                with patch.object(plugin, "_run", side_effect=run), patch.object(backend.os, "kill") as kill:
                    result = await plugin._unload()
                    await plugin._uninstall()  # Decky calls both hooks on uninstall.
                self.assertEqual([action for action, _, _ in calls].count("stop"), 1)
                self.assertTrue(all(internal for _, _, internal in calls))
                self.assertEqual({action for action, _, _ in calls}, {"mixer", "stop", "status"})
                self.assertFalse(kill.called)
                if observed["output_known"]:
                    self.assertEqual(result["stream"], observed["stream"])
                    self.assertEqual(result["recording"], observed["recording"])
                    self.assertEqual(result["media"], observed["media"])
                else:
                    self.assertFalse(result["output_known"])
                    self.assertEqual(result["state"], "unknown")

    async def test_closing_reads_and_mutations_cannot_spawn_or_query_dependencies(self):
        plugin = backend.Plugin()
        plugin._closing = True
        plugin._dependency_job = SimpleNamespace(running=False, status=AsyncMock(), cancel=AsyncMock())
        with patch.object(backend.asyncio, "create_subprocess_exec") as spawn:
            results = await asyncio.gather(plugin.status(), plugin.configuration_status(), plugin.stream_health(),
                                           plugin.mixer_action({"action": "talk-start"}), plugin.start(),
                                           plugin.stop(), plugin.dependency_status(), plugin.install_dependencies(True),
                                           plugin.cancel_dependency_setup(), plugin.check_for_updates())
        spawn.assert_not_called()
        plugin._dependency_job.status.assert_not_called()
        plugin._dependency_job.cancel.assert_not_called()
        self.assertTrue(all(isinstance(result, dict) for result in results))
        self.assertFalse(results[1]["can_configure"])
        self.assertFalse(results[1]["can_close"])

    async def test_cancelled_update_thread_has_no_late_result_or_exit_join(self):
        started, release = threading.Event(), threading.Event()
        workers = []

        def check():
            workers.append(threading.current_thread())
            started.set()
            release.wait(3)
            return {"ok": True}

        task = asyncio.create_task(backend._readonly_thread(check))
        try:
            while not started.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(workers[0].daemon)
        finally:
            release.set()
            while workers and workers[0].is_alive():
                await asyncio.sleep(.001)
        await asyncio.sleep(0)  # The cancelled Future ignores its late callback.

    async def test_frozen_dependency_worker_uses_system_python_and_original_libraries(self):
        with tempfile.TemporaryDirectory(prefix="obsgod-frozen-worker-") as temporary:
            root = Path(temporary)
            fake = root / "flatpak"
            fake.write_text("#!" + sys.executable + "\n" +
                            "import json,os\nprint(json.dumps({key:os.environ.get(key) for key in "
                            "['LD_LIBRARY_PATH','LD_LIBRARY_PATH_ORIG','PYTHONHOME','PYTHONPATH']}))\n")
            fake.chmod(0o700)
            stub = root / "PluginLoader"
            stub.write_text("#!/bin/sh\ntouch '" + str(root / "wrong-interpreter") + "'\nexit 72\n")
            stub.chmod(0o700)
            environment = dict(os.environ, LD_LIBRARY_PATH="/frozen/private", LD_LIBRARY_PATH_ORIG="/original/libraries",
                               PYTHONHOME="/poison/home", PYTHONPATH="/poison/path")
            controller = backend.dependency_setup.DependencySetup(root, environment)
            controller._flatpak, controller._child_env = str(fake), environment
            with patch.object(backend.sys, "frozen", True, create=True), patch.object(backend.sys, "executable", str(stub)):
                code, output, _ = await controller._command(["--version"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output), {"LD_LIBRARY_PATH": "/original/libraries", "LD_LIBRARY_PATH_ORIG": None,
                                                 "PYTHONHOME": None, "PYTHONPATH": None})
            self.assertFalse((root / "wrong-interpreter").exists())
            self.assertEqual(environment["PYTHONHOME"], "/poison/home", "parent environment must remain unchanged")

    async def test_frozen_interpreter_is_fixed_and_refuses_unsafe_or_missing_system_python(self):
        setup = backend.dependency_setup
        with patch.object(backend.sys, "frozen", True, create=True):
            command, environment = setup.python_process({"PATH": "/untrusted", "LD_LIBRARY_PATH": "/frozen/private"})
            self.assertEqual(command, [str(Path("/usr/bin/python3").resolve()), "-I", "-B"])
            self.assertNotIn("LD_LIBRARY_PATH", environment)
            with patch.object(setup.Path, "resolve", side_effect=FileNotFoundError):
                with self.assertRaises(OSError):
                    setup.python_process({})
            with tempfile.TemporaryDirectory(prefix="obsgod-unsafe-python-") as temporary:
                target = Path(temporary) / "python3"
                target.write_text("untrusted")
                with patch.object(setup.Path, "resolve", return_value=target):
                    with self.assertRaises(OSError):
                        setup.python_process({})


if __name__ == "__main__":
    unittest.main()
