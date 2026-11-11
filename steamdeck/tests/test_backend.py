import asyncio
import importlib.util
import json
from pathlib import Path
import signal
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("decky_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


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
        return json.dumps({"ok": self.returncode == 0, "state": "stopped", "message": "fixture"}).encode(), b""

    def send_signal(self, value):
        self.signals.append(value)
        self.returncode = 130
        self.done.set()

    def kill(self):
        self.send_signal(signal.SIGKILL)


class BackendCancellation(unittest.IsolatedAsyncioTestCase):
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
            duplicate = await plugin.start()
            self.assertFalse(duplicate["ok"])
            self.assertIsNone(plugin.pending)
            stopped = await plugin.stop()
            self.assertTrue(stopped["ok"])
            attach.set()
            result = await task
        self.assertIn(signal.SIGINT, start_process.signals)
        self.assertFalse(result["ok"])
        self.assertFalse(plugin.busy)
        self.assertIsNone(plugin.pending)


if __name__ == "__main__":
    unittest.main()
