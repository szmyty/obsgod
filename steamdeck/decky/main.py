"""Unprivileged Decky adapter. OBS protocol and credentials stay in the CLI."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import uuid


class Plugin:
    def __init__(self):
        self.pending = None
        self.cancel_requested = False
        self._control_task = None
        self._control_action = None
        self._control_payload = None
        self._stop_task = None
        self._status_task = None
        self._operation_id = 0
        self._snapshot_id = 0
        self._backend_id = uuid.uuid4().hex
        self._last_action = None
        self._update_task = None
        self._closing = False
        self._cleanup_tasks = set()

    @property
    def busy(self):
        return bool((self._control_task and not self._control_task.done()) or
                    (self._stop_task and not self._stop_task.done()))

    def _version(self):
        try:
            value = json.loads((Path(__file__).resolve().parent / "package.json").read_text())["version"]
            return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.-]{1,80}", value) else "unknown"
        except (OSError, ValueError, KeyError, TypeError):
            return "unknown"

    def _decorate(self, result):
        result = dict(result)
        result["plugin_version"] = self._version()
        result["backend_id"] = self._backend_id
        if self.busy:
            stopping = self.cancel_requested or (self._stop_task and not self._stop_task.done())
            result["operation"] = {"id": self._operation_id,
                                   "action": "stop" if stopping else self._control_action,
                                   "state": "cancelling" if stopping else "running"}
        else:
            result["operation"] = None
        if self._last_action:
            result["last_action"] = dict(self._last_action)
        return result

    async def _main(self):
        os.umask(0o077)
        # The loader supplies the real user's home even when its service has a
        # different environment. The plugin requests no _root flag.
        try:
            import decky
            os.environ["HOME"] = decky.DECKY_USER_HOME
        except ImportError:
            pass

    @staticmethod
    def _unknown(message):
        return {"ok": False, "state": "unknown", "output_known": False,
                "process": "unknown", "connection": "unavailable", "message": message}

    async def _run(self, action, payload=None):
        binary = Path(__file__).resolve().parent / "bin/obsgod"
        if not os.access(binary, os.X_OK):
            binary.chmod(0o700)
        spawning = asyncio.create_task(asyncio.create_subprocess_exec(
            str(binary), "deck", action, stdin=asyncio.subprocess.PIPE if payload is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        ))
        try:
            process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            # Cancellation can arrive while asyncio is attaching the child.
            # Keep ownership of that spawn until its eventual child is reaped.
            async def reap_late_child():
                try:
                    child = await spawning
                    await self._stop_child(child)
                except OSError:
                    pass
            cleanup = asyncio.create_task(reap_late_child())
            self._cleanup_tasks.add(cleanup)
            cleanup.add_done_callback(self._cleanup_tasks.discard)
            raise
        if action in {"start", "test-recording"}:
            self.pending = process
            if self.cancel_requested and process.returncode is None:
                self._signal_pending()
        try:
            communication = process.communicate(json.dumps(payload).encode()) if payload is not None else process.communicate()
            output, _ = await asyncio.wait_for(communication, 85 if action not in {"status", "clear-logs"} else 6)
            result = json.loads(output)
            if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
                raise ValueError()
            return result
        except asyncio.CancelledError:
            await self._stop_child(process)
            raise
        except (asyncio.TimeoutError, ValueError, UnicodeError):
            await self._stop_child(process)
            return self._unknown("Output state is unconfirmed. Use Stop streaming and inspect OBS if the connection does not recover.")
        finally:
            if self.pending is process:
                self.pending = None

    @staticmethod
    async def _stop_child(process):
        if process.returncode is None:
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.communicate(), 8)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()

    def _signal_pending(self):
        if self.pending is not None and self.pending.returncode is None:
            try:
                self.pending.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass

    async def _read_status(self):
        self._snapshot_id += 1
        snapshot_id = self._snapshot_id
        try:
            result = await self._run("status")
        except OSError:
            result = self._unknown("OBSGod executable is unavailable. Reinstall OBSGod from its Desktop installer.")
        result["snapshot_id"] = snapshot_id
        return result

    async def status(self):
        # Multiple panel/icon/manual clients share one bounded real OBS query.
        # Operation metadata is attached at return time, not when that query
        # began, so a slow status response cannot resurrect a completed action.
        if self._status_task is None or self._status_task.done():
            self._status_task = asyncio.create_task(self._read_status())
        return self._decorate(await asyncio.shield(self._status_task))

    async def clear_logs(self):
        try:
            await self._run("clear-logs")
        except OSError:
            pass
        return await self.status()

    async def _perform(self, action, operation_id, command=None, payload=None):
        if command is None:
            try:
                if action == "set-capture-mode":
                    # This read occurs after the control operation is reserved.
                    # Never use a pre-click cached panel snapshot to authorize
                    # changing capture, and keep the CLI's own lock/state gate.
                    current = await self._run("status")
                    if (current.get("output_known") is not True or
                            current.get("stream", {}).get("active") or current.get("recording")):
                        command = {"ok": False, "message": "Stop streaming and recording, then wait for confirmed status before changing capture mode."}
                if command is None:
                    command = await self._run(action, payload) if payload is not None else await self._run(action)
            except OSError:
                command = self._unknown("OBSGod executable is unavailable. Reinstall OBSGod from its Desktop installer.")
        # Command success/error is not an output snapshot. Re-query actual OBS
        # rather than allowing a failed Start to replace an active stream with
        # an error/stopped state, or a click to declare a stream live.
        outcome = {"id": operation_id, "action": action, "ok": command["ok"],
                   "message": command.get("message", "Operation could not be confirmed")}
        if command.get("recording_path"):
            outcome["recording_path"] = command["recording_path"]
        if self._last_action is None or operation_id >= self._last_action["id"]:
            self._last_action = outcome
        # Discard a pre-action in-flight status result before the final query.
        previous = self._status_task
        if previous and not previous.done():
            await asyncio.shield(previous)
        self._status_task = None
        observed = await self.status()
        observed["action_result"] = outcome
        return observed

    async def _begin(self, action, payload=None):
        if self._closing:
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "OBSGod is shutting down. Wait for the plugin to reload."}
            return result
        if self._control_task and not self._control_task.done():
            if self._control_action == action and self._control_payload == payload and not self.cancel_requested:
                return await asyncio.shield(self._control_task)
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "Another operation is running; wait or cancel it."}
            return result
        if self._stop_task and not self._stop_task.done():
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "Stop is still being confirmed. Wait before starting another operation."}
            return result
        self.cancel_requested = False
        self._control_action = action
        self._control_payload = payload
        self._operation_id += 1
        self._control_task = asyncio.create_task(self._perform(action, self._operation_id, payload=payload))
        return await asyncio.shield(self._control_task)

    async def start(self):
        return await self._begin("start")

    async def test_recording(self):
        return await self._begin("test-recording")

    async def set_capture_mode(self, mode):
        if not isinstance(mode, str) or mode not in {"screen", "game"}:
            result = await self.status()
            result["action_result"] = {"ok": False, "action": "set-capture-mode",
                                       "message": "Choose entire screen or game only."}
            return result
        return await self._begin("set-capture-mode", {"capture_mode": mode})

    async def _stop(self, operation_id):
        if not (self._control_task and not self._control_task.done()):
            current = await self.status()
            if current.get("output_known") is True and not current.get("stream", {}).get("active"):
                return await self._perform("stop", operation_id, {"ok": True, "message": "OBS confirms streaming is already stopped."})
        return await self._perform("stop", operation_id)

    async def stop(self):
        # Coalesce Stop requests too. Cancellation is latched before spawning
        # Stop, including the race before Start's child process is attached.
        if self._stop_task and not self._stop_task.done():
            return await asyncio.shield(self._stop_task)
        self.cancel_requested = True
        self._signal_pending()
        self._operation_id += 1
        self._stop_task = asyncio.create_task(self._stop(self._operation_id))
        return await asyncio.shield(self._stop_task)

    async def check_for_updates(self):
        if self._update_task and not self._update_task.done():
            return await asyncio.shield(self._update_task)

        async def check():
            try:
                path = Path(__file__).resolve().parent / "releases.py"
                spec = importlib.util.spec_from_file_location("obsgod_releases", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                versions = module.current_versions(self._version())
                current = versions["app"] if versions["app"] != "unknown" else versions["plugin"]
                result = await asyncio.to_thread(module.check_updates, current, channel="preview")
                result.update(current_app_version=versions["app"], current_plugin_version=versions["plugin"],
                              current_updater_version=versions["updater"], mismatch=versions["mismatch"])
                if versions["mismatch"]:
                    result["message"] += " App and plugin versions differ; use the Desktop installer to repair the pair."
                return result
            except (OSError, ValueError, ImportError, AttributeError):
                return {"ok": False, "state": "error", "current_version": self._version(),
                        "available": False, "message": "Could not check updates. Retry or use the bundled Desktop updater."}

        self._update_task = asyncio.create_task(check())
        return await asyncio.shield(self._update_task)

    async def _unload(self):
        # Refuse new Starts first, latch cancellation, drain the original start
        # even when its child has not attached, then confirm Stop once more.
        # A loader teardown acknowledgement must not precede a late Start.
        self._closing = True
        try:
            await asyncio.wait_for(asyncio.shield(self.stop()), 18)
            if self._control_task and not self._control_task.done():
                await asyncio.wait_for(asyncio.shield(self._control_task), 12)
            return await asyncio.wait_for(asyncio.shield(self.stop()), 12)
        except (OSError, asyncio.TimeoutError, asyncio.CancelledError):
            self.cancel_requested = True
            self._signal_pending()
            tasks = [task for task in (self._control_task, self._stop_task, self._status_task)
                     if task is not None and not task.done()]
            for task in tasks:
                task.cancel()
            if tasks:
                try:
                    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
                except asyncio.TimeoutError:
                    pass
            if self._cleanup_tasks:
                try:
                    await asyncio.wait_for(asyncio.shield(asyncio.gather(*self._cleanup_tasks, return_exceptions=True)), 5)
                except asyncio.TimeoutError:
                    pass
            message = "Shutdown could not confirm all output stopped. Inspect OBS before leaving it unattended."
            self._last_action = {"id": self._operation_id, "action": "stop", "ok": False, "message": message}
            return self._unknown(message)

    async def _uninstall(self):
        await self._unload()
