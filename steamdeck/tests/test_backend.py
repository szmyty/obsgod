import asyncio
import importlib.util
import json
from pathlib import Path
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

spec = importlib.util.spec_from_file_location("decky_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

IDLE = {"ok": True, "state": "stopped", "output_known": True,
        "stream": {"active": False}, "message": "fixture idle"}
LIVE = {"ok": True, "state": "streaming", "output_known": True,
        "stream": {"active": True, "bytes": 4096}, "message": "fixture live"}


class FakeProcess:
    def __init__(self, wait=False):
        self.returncode = None
        self.done = asyncio.Event()
        self.signals = []
        if not wait:
            self.done.set()

    async def communicate(self):
        await self.done.wait()
        self.returncode = self.returncode or 0
        return json.dumps({**IDLE, "ok": self.returncode == 0}).encode(), b""

    def send_signal(self, value):
        self.signals.append(value)
        self.returncode = 130
        self.done.set()

    def kill(self):
        self.send_signal(signal.SIGKILL)


class BackendState(unittest.IsolatedAsyncioTestCase):
    async def test_stop_cancels_start_even_before_process_is_attached(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        attach = asyncio.Event()
        start_process = FakeProcess(wait=True)

        async def spawn(*args, **_kwargs):
            if args[-1] == "start":
                entered.set()
                await attach.wait()
                return start_process
            return FakeProcess()

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(plugin.start())
            await entered.wait()
            duplicate = asyncio.create_task(plugin.start())
            await asyncio.sleep(0)
            self.assertIsNone(plugin.pending)
            stopped = await plugin.stop()
            self.assertTrue(stopped["action_result"]["ok"])
            self.assertEqual(stopped["operation"]["state"], "cancelling")
            attach.set()
            result, repeated = await asyncio.gather(task, duplicate)
        self.assertIn(signal.SIGINT, start_process.signals)
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["action_result"]["id"], repeated["action_result"]["id"])
        self.assertFalse(plugin.busy)
        self.assertIsNone(plugin.pending)

    async def test_unload_waits_for_late_start_and_rejects_new_start(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        stop_entered = asyncio.Event()
        attach = asyncio.Event()
        process = FakeProcess(wait=True)
        starts = []

        async def spawn(*args, **_kwargs):
            if args[-1] == "start":
                starts.append(1)
                entered.set()
                await attach.wait()
                return process
            if args[-1] == "stop":
                stop_entered.set()
            return FakeProcess()

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            start_task = asyncio.create_task(plugin.start())
            await entered.wait()
            unloading = asyncio.create_task(plugin._unload())
            await stop_entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(unloading.done())
            rejected = await plugin.start()
            self.assertFalse(rejected["action_result"]["ok"])
            attach.set()
            await start_task
            result = await unloading
        self.assertTrue(result["output_known"])
        self.assertFalse(result["stream"]["active"])
        self.assertEqual(starts, [1])
        self.assertIn(signal.SIGINT, process.signals)
        self.assertFalse(plugin.busy)
        self.assertIsNone(plugin.pending)

    async def test_cancelled_spawn_keeps_ownership_until_late_child_is_reaped(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        attach = asyncio.Event()
        process = FakeProcess(wait=True)

        async def spawn(*_args, **_kwargs):
            entered.set()
            await attach.wait()
            return process

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(plugin._run("start"))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(plugin._cleanup_tasks)
            attach.set()
            await asyncio.gather(*plugin._cleanup_tasks)
        self.assertIn(signal.SIGINT, process.signals)
        self.assertIsNotNone(process.returncode)

    async def test_concurrent_start_and_stop_requests_are_coalesced(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        finish = asyncio.Event()
        calls = []

        async def run(action):
            calls.append(action)
            if action == "start":
                entered.set()
                await finish.wait()
            return IDLE

        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.start())
            await entered.wait()
            second = asyncio.create_task(plugin.start())
            stopping = asyncio.create_task(plugin.stop())
            repeated_stop = asyncio.create_task(plugin.stop())
            await asyncio.sleep(0)
            finish.set()
            results = await asyncio.gather(first, second, stopping, repeated_stop)
        self.assertEqual(calls.count("start"), 1)
        self.assertEqual(calls.count("stop"), 1)
        self.assertEqual(results[0]["action_result"]["id"], results[1]["action_result"]["id"])
        self.assertEqual(results[2]["action_result"]["id"], results[3]["action_result"]["id"])

    async def test_failed_action_does_not_replace_observed_live_state(self):
        plugin = backend.Plugin()

        async def run(action):
            if action == "status":
                return LIVE
            return {"ok": False, "state": "error", "message": "fixture command failed"}

        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.start()
        self.assertTrue(result["stream"]["active"])
        self.assertTrue(result["output_known"])
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["action_result"]["message"], "fixture command failed")

    async def test_status_clients_share_query_and_pending_operation_metadata(self):
        plugin = backend.Plugin()
        finish = asyncio.Event()
        entered = asyncio.Event()
        calls = []

        async def run(action):
            calls.append(action)
            entered.set()
            await finish.wait()
            return IDLE

        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.status())
            await entered.wait()
            second = asyncio.create_task(plugin.status())
            await asyncio.sleep(0)
            finish.set()
            one, two = await asyncio.gather(first, second)
        self.assertEqual(calls, ["status"])
        self.assertEqual(one["snapshot_id"], two["snapshot_id"])
        self.assertEqual(one["backend_id"], two["backend_id"])
        self.assertIsNone(one["operation"])

    async def test_update_checks_coalesce_and_compare_the_app_not_only_the_plugin(self):
        plugin = backend.Plugin()
        calls = []

        def check(version, channel):
            calls.append((version, channel))
            return {"ok": True, "available": True, "state": "update-available", "message": "Update available"}

        module = SimpleNamespace(check_updates=check, current_versions=lambda _: {
            "app": "0.1.0-deck.1", "plugin": "0.1.0-deck.4", "updater": "not-bundled", "mismatch": True})
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(backend.importlib.util, "spec_from_file_location", return_value=fake_spec), patch.object(backend.importlib.util, "module_from_spec", return_value=module):
            one, two = await asyncio.gather(plugin.check_for_updates(), plugin.check_for_updates())
        self.assertEqual(calls, [("0.1.0-deck.1", "preview")])
        self.assertEqual(one, two)
        self.assertTrue(one["mismatch"])
        self.assertEqual(one["current_app_version"], "0.1.0-deck.1")
        self.assertEqual(one["current_plugin_version"], "0.1.0-deck.4")
        self.assertIn("Desktop installer", one["message"])

    async def test_idle_stop_does_not_issue_another_command(self):
        plugin = backend.Plugin()
        run = AsyncMock(return_value=IDLE)
        with patch.object(plugin, "_run", run):
            result = await plugin.stop()
            await plugin.stop()
        self.assertTrue(result["action_result"]["ok"])
        self.assertNotIn("stop", [call.args[0] for call in run.call_args_list])

    async def test_unknown_output_keeps_recovery_stop_available(self):
        plugin = backend.Plugin()
        unknown = {"ok": False, "state": "unknown", "output_known": False, "message": "fixture unknown"}
        run = AsyncMock(return_value=unknown)
        with patch.object(plugin, "_run", run):
            result = await plugin.stop()
        self.assertFalse(result["output_known"])
        self.assertIn("stop", [call.args[0] for call in run.call_args_list])


if __name__ == "__main__":
    unittest.main()
