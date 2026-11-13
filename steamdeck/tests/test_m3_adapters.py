"""M3 tools preserve actual output snapshots and share control serialization."""
import asyncio
import importlib.util
import json
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

spec = importlib.util.spec_from_file_location("m3_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)
IDLE = {"ok": True, "state": "stopped", "output_known": True, "recording": False,
        "stream": {"active": False}, "media": {"known": True, "replay_active": False}}


class AdvancedAdapter(IsolatedAsyncioTestCase):
    async def test_local_start_cancel_never_stops_live_stream_even_before_attach(self):
        plugin = backend.Plugin()
        entered, attached = asyncio.Event(), asyncio.Event()
        process = None
        calls = []
        live = {**IDLE, "state": "streaming", "stream": {"active": True, "bytes": 8192},
                "media": {"known": True, "replay_active": False, "recording": {"active": False}}}

        class Process:
            returncode = None
            def __init__(self): self.done = asyncio.Event()
            async def communicate(self, payload=None):
                await self.done.wait()
                return json.dumps({"ok": False, "message": "Startup cancelled"}).encode(), b""
            def send_signal(self, signal): self.returncode = 130; self.done.set()
        process = Process()
        async def spawn(*args, **kwargs):
            calls.append(args[-1])
            entered.set()
            await attached.wait()
            return process
        original = plugin._run
        async def run(action, payload=None):
            if action == "status": return live
            return await original(action, payload)
        with patch.object(plugin, "_run", side_effect=run), patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            start = asyncio.create_task(plugin.media_action({"action": "record-start"}))
            await entered.wait()
            cancelled = asyncio.create_task(plugin.cancel_media_operation())
            await asyncio.sleep(0)
            attached.set()
            await start
            result = await cancelled
        self.assertTrue(result["action_result"]["ok"])
        self.assertTrue(result["stream"]["active"])
        self.assertEqual(calls, ["media"])

    async def test_command_payload_never_replaces_actual_broadcast_snapshot(self):
        plugin = backend.Plugin()
        live = {**IDLE, "state": "streaming", "stream": {"active": True, "bytes": 4096}}
        command = {"ok": False, "state": "error", "message": "Stop output before applying a profile"}
        async def run(action, payload=None):
            return live if action == "status" else command
        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.stream_profiles({"action": "apply", "name": "Travel"})
        self.assertEqual(result["state"], "streaming")
        self.assertTrue(result["stream"]["active"])
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["data"], command)

    async def test_duplicate_media_actions_coalesce_and_different_actions_wait(self):
        plugin = backend.Plugin()
        entered, finish = asyncio.Event(), asyncio.Event()
        calls = []
        async def run(action, payload=None):
            calls.append((action, payload))
            if action == "media":
                entered.set()
                await finish.wait()
                return {"ok": True, "message": "Recording confirmed"}
            return IDLE
        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.media_action({"action": "record-start"}))
            await entered.wait()
            duplicate = asyncio.create_task(plugin.media_action({"action": "record-start"}))
            different = await plugin.media_action({"action": "replay-start"})
            self.assertFalse(different["action_result"]["ok"])
            finish.set()
            result, repeated = await asyncio.gather(first, duplicate)
        self.assertEqual(result["action_result"]["id"], repeated["action_result"]["id"])
        self.assertEqual(sum(action == "media" for action, _ in calls), 1)

    async def test_malformed_oversized_or_nonfinite_tool_data_never_starts_cli(self):
        plugin = backend.Plugin()
        with patch.object(plugin, "_run", AsyncMock()) as run:
            for payload in [None, [], {"name": "x" * 17000}, {"bitrate": float("nan")}]:
                result = await plugin.stream_profiles(payload)
                self.assertFalse(result["ok"])
        run.assert_not_called()

    async def test_replay_or_unknown_media_blocks_capture_edit(self):
        for media in [{"known": True, "replay_active": True}, {"known": False, "replay_active": False}]:
            plugin = backend.Plugin()
            with patch.object(plugin, "_run", AsyncMock(return_value={**IDLE, "media": media})) as run:
                result = await plugin.set_capture_mode("game")
            self.assertFalse(result["action_result"]["ok"])
            self.assertTrue(all(call.args == ("status",) for call in run.call_args_list))
