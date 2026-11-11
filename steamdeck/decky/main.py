"""Unprivileged Decky adapter. OBS protocol and credentials stay in the CLI."""
import asyncio
import json
import os
from pathlib import Path
import signal
import re


class Plugin:
    def __init__(self):
        self.pending = None
        self.busy = False
        self.cancel_requested = False

    def _version(self):
        try:
            value = json.loads((Path(__file__).resolve().parent / "package.json").read_text())["version"]
            return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.-]{1,80}", value) else "unknown"
        except (OSError, ValueError, KeyError):
            return "unknown"

    async def _main(self):
        os.umask(0o077)
        # The loader supplies the real user's home even when its service has a
        # different environment. The plugin requests no _root flag.
        try:
            import decky
            os.environ["HOME"] = decky.DECKY_USER_HOME
        except ImportError:
            pass

    async def _run(self, action):
        binary = Path(__file__).resolve().parent / "bin/obsgod"
        if not os.access(binary, os.X_OK):
            binary.chmod(0o700)
        process = await asyncio.create_subprocess_exec(
            str(binary), "deck", action, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        if action in {"start", "test-recording"}:
            self.pending = process
            if self.cancel_requested and process.returncode is None:
                try:
                    process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 85 if action != "status" else 6)
            result = json.loads(output)
            if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
                raise ValueError()
            result["plugin_version"] = self._version()
            return result
        except (asyncio.TimeoutError, ValueError, UnicodeError):
            if process.returncode is None:
                process.send_signal(signal.SIGINT)
                try:
                    await asyncio.wait_for(process.communicate(), 8)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()
            return {"ok": False, "state": "unknown", "message": "Output state is unconfirmed. Use Stop streaming and inspect OBS if the connection does not recover."}
        finally:
            if self.pending is process:
                self.pending = None

    async def status(self):
        try:
            return await self._run("status")
        except OSError:
            return {"ok": False, "state": "unknown", "message": "OBSGod executable is unavailable. Reinstall the plugin ZIP."}

    async def clear_logs(self):
        return await self._run("clear-logs")

    async def start(self):
        if self.busy:
            return {"ok": False, "state": "starting", "message": "An operation is already running"}
        self.busy = True
        self.cancel_requested = False
        try:
            return await self._run("start")
        finally:
            self.busy = False

    async def stop(self):
        self.cancel_requested = True
        if self.pending is not None and self.pending.returncode is None:
            try:
                self.pending.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
        return await self._run("stop")

    async def test_recording(self):
        if self.busy:
            return {"ok": False, "state": "starting", "message": "An operation is already running"}
        self.busy = True
        self.cancel_requested = False
        try:
            return await self._run("test-recording")
        finally:
            self.busy = False

    async def _unload(self):
        # Do not leave a broadcast unattended when its control plugin unloads.
        try:
            await self.stop()
        except (OSError, asyncio.CancelledError):
            pass

    async def _uninstall(self):
        await self._unload()
