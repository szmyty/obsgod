"""Privacy-lease controls stay responsive during long stream operations."""
import asyncio
import importlib.util
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

spec = importlib.util.spec_from_file_location("mixer_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class MixerAdapter(IsolatedAsyncioTestCase):
    async def test_renew_and_release_do_not_wait_for_busy_control_or_query_status(self):
        plugin = backend.Plugin()
        plugin._control_task = asyncio.create_task(asyncio.Event().wait())
        try:
            with patch.object(plugin, "_run", AsyncMock(return_value={"ok": True})) as run, patch.object(plugin, "status", AsyncMock()) as status:
                for payload in [{"action": "talk-start", "token": "private-lease"}, {"action": "talk-release", "token": "private-lease"}, {"action": "talk-cancel"}]:
                    result = await asyncio.wait_for(plugin.mixer_action(payload), .1)
                    self.assertTrue(result["ok"])
                self.assertEqual(run.await_count, 3)
                status.assert_not_called()
        finally:
            plugin._control_task.cancel()
            await asyncio.gather(plugin._control_task, return_exceptions=True)

    async def test_new_hold_refused_during_control_but_cancel_allowed_during_teardown(self):
        plugin = backend.Plugin()
        plugin._closing = True
        with patch.object(plugin, "_run", AsyncMock(return_value={"ok": True})) as run:
            result = await plugin.mixer_action({"action": "talk-start"})
            self.assertFalse(result["ok"])
            result = await plugin.mixer_action({"action": "talk-cancel"})
            self.assertTrue(result["ok"])
            run.assert_awaited_once_with("mixer", {"action": "talk-cancel"})

    async def test_configure_uses_serialized_path_and_preserves_observed_stream(self):
        plugin = backend.Plugin()
        live = {"ok": True, "state": "streaming", "output_known": True, "stream": {"active": True}}
        command = {"ok": False, "message": "Microphone source unavailable", "mixer": {"known": False}}
        async def run(action, payload=None):
            return live if action == "status" else command
        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.mixer_action({"action": "configure", "preferences": {"microphone_muted": False}})
        self.assertTrue(result["stream"]["active"])
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["data"], command)

    async def test_invalid_request_never_launches_control(self):
        plugin = backend.Plugin()
        with patch.object(plugin, "_run", AsyncMock()) as run:
            for payload in [None, [], {"action": "unexpected"}, {"action": "status", "x": float("nan")}, {"action": "status", "x": "x" * 17000}]:
                result = await plugin.mixer_action(payload)
                self.assertFalse(result["ok"])
            run.assert_not_called()
