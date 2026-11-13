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
        self._cancel_media_task = None

    @property
    def busy(self):
        return bool((self._control_task and not self._control_task.done()) or
                    (self._stop_task and not self._stop_task.done()))

    @staticmethod
    def _provided(name):
        """Read only the documented loader context, with old-loader fallback."""
        if name in os.environ:
            return os.environ[name] or None
        try:
            import decky
            return getattr(decky, name, None) or None
        except ImportError:
            return None

    @staticmethod
    def _directory(value, description):
        if (not isinstance(value, str) or not value or
                any(ord(char) < 32 for char in value) or not Path(value).is_absolute()):
            raise OSError("The loader supplied an invalid " + description + ". Reload or repair the plugin.")
        try:
            path = Path(value).resolve(strict=True)
            if not path.is_dir():
                raise OSError()
            return path
        except (OSError, ValueError, RuntimeError):
            raise OSError("The loader supplied an unavailable " + description + ". Reload or repair the plugin.") from None

    def _plugin_root(self):
        value = self._provided("DECKY_PLUGIN_DIR")
        if value is not None:
            return self._directory(value, "plugin directory")
        # Standalone use and older loaders may not inject the documented path.
        return Path(__file__).resolve().parent

    def _child_environment(self):
        """Use the player's context without changing the loader process HOME.

        Shared Desktop/CLI settings remain in the user's XDG store. Decky's
        plugin settings and persistent runtime-data directory are deliberately
        not substituted for those paths or the ephemeral XDG_RUNTIME_DIR.
        """
        child = os.environ.copy()
        home = self._provided("DECKY_USER_HOME")
        if home is not None:
            home = self._directory(home, "user home")
            old_home = child.get("HOME")
            child["HOME"] = str(home)
            # A service HOME can bring its own default XDG roots along. Do not
            # accidentally read root/service credentials as the real player.
            # Explicit absolute roots elsewhere remain valid shared overrides.
            for name in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                value = child.get(name)
                if not value:
                    continue
                if not Path(value).is_absolute() or any(ord(char) < 32 for char in value):
                    child.pop(name, None)
                elif (old_home and old_home != "/" and Path(old_home).is_absolute() and
                      Path(old_home) != home and Path(value).is_relative_to(old_home)):
                    child.pop(name, None)
        user = self._provided("DECKY_USER")
        if isinstance(user, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", user):
            child["USER"] = child["LOGNAME"] = user
        return child

    def _loader_metadata(self):
        result = {}
        for key, name in (("version", "DECKY_VERSION"), ("plugin_name", "DECKY_PLUGIN_NAME"),
                          ("plugin_author", "DECKY_PLUGIN_AUTHOR")):
            value = self._provided(name)
            if isinstance(value, str) and 0 < len(value) <= 80 and value.isprintable():
                result[key] = value
        return result

    def _version(self):
        value = self._provided("DECKY_PLUGIN_VERSION")
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.-]{1,80}", value):
            return value
        try:
            value = json.loads((self._plugin_root() / "package.json").read_text())["version"]
            return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.-]{1,80}", value) else "unknown"
        except (OSError, ValueError, KeyError, TypeError):
            return "unknown"

    def _decorate(self, result):
        result = dict(result)
        result["plugin_version"] = self._version()
        result["loader"] = self._loader_metadata()
        result["backend_id"] = self._backend_id
        if self.busy:
            stopping = self.cancel_requested or (self._stop_task and not self._stop_task.done())
            result["operation"] = {"id": self._operation_id,
                                   "action": "stop" if stopping else self._control_action,
                                   "state": "cancelling" if stopping else "running"}
            if self._control_action == "media" and isinstance(self._control_payload, dict):
                result["operation"]["media_action"] = self._control_payload.get("action")
        else:
            result["operation"] = None
        if self._last_action:
            result["last_action"] = dict(self._last_action)
        return result

    async def _main(self):
        os.umask(0o077)

    @staticmethod
    def _unknown(message):
        return {"ok": False, "state": "unknown", "output_known": False,
                "process": "unknown", "connection": "unavailable", "message": message}

    async def _run(self, action, payload=None):
        binary = self._plugin_root() / "bin/obsgod"
        if not os.access(binary, os.X_OK):
            binary.chmod(0o700)
        spawning = asyncio.create_task(asyncio.create_subprocess_exec(
            str(binary), "deck", action, stdin=asyncio.subprocess.PIPE if payload is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=self._child_environment(),
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
        if action in {"start", "test-recording"} or (action == "media" and isinstance(payload, dict) and payload.get("action") in {"record-start", "replay-start"}):
            self.pending = process
            if self.cancel_requested and process.returncode is None:
                self._signal_pending()
        try:
            communication = process.communicate(json.dumps(payload).encode()) if payload is not None else process.communicate()
            timeout = 6 if action in {"status", "clear-logs"} else 85
            if action == "mixer" and isinstance(payload, dict) and payload.get("action") != "configure":
                timeout = 8
            output, _ = await asyncio.wait_for(communication, timeout)
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
                    media = current.get("media")
                    media_idle = (isinstance(media, dict) and media.get("known") is True and
                                  media.get("replay_active") is False)
                    legacy_absent = media is None and current.get("process") == "absent"
                    if (current.get("output_known") is not True or
                            current.get("stream", {}).get("active") or current.get("recording") or
                            not (media_idle or legacy_absent)):
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
        if action in {"stream-profiles", "set-idle-media", "media", "retry-recovery", "mixer"}:
            # Rich action data is separate from the newly observed output.
            # A failed Save/Start can never replace the actual stream state.
            observed["data"] = command
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

    async def _advanced(self, action, payload):
        if not isinstance(payload, dict):
            return {"ok": False, "message": "Send one settings object."}
        try:
            encoded = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError):
            return {"ok": False, "message": "Settings must contain valid JSON values."}
        if len(encoded) > 16384:
            return {"ok": False, "message": "Settings are too large; choose a smaller profile."}
        # Serialize all mutations with normal stream control. CLI read actions
        # remain bounded and have no side effects, but use the same adapter so
        # the panel receives a fresh authoritative status after every action.
        return await self._begin(action, payload)

    async def stream_profiles(self, payload):
        return await self._advanced("stream-profiles", payload)

    async def set_idle_media(self, payload):
        return await self._advanced("set-idle-media", payload)

    async def media_action(self, payload):
        return await self._advanced("media", payload)

    async def mixer_action(self, payload):
        if not isinstance(payload, dict):
            return {"ok": False, "message": "Send one mixer settings object."}
        try:
            encoded = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError):
            return {"ok": False, "message": "Mixer settings must contain valid JSON values."}
        if len(encoded) > 16384:
            return {"ok": False, "message": "Mixer settings are too large."}
        action = payload.get("action")
        if action == "configure":
            return await self._begin("mixer", payload)
        if action not in {"status", "devices", "talk-start", "talk-release", "talk-cancel"}:
            return {"ok": False, "message": "Choose a supported mixer action."}
        # Lease renewal/release cannot wait for _perform's full output query.
        # A release/cancel remains available during Stop and loader teardown.
        if action == "talk-start" and (self._closing or self.cancel_requested or
                (self._stop_task and not self._stop_task.done()) or
                (not payload.get("token") and self.busy)):
            return {"ok": False, "message": "Wait for the current operation before holding to talk."}
        try:
            return await self._run("mixer", payload)
        except OSError:
            return {"ok": False, "message": "Microphone control is unavailable; its actual mute state is unknown."}

    async def stream_health(self):
        try:
            return await self._run("stream-health")
        except OSError:
            return {"ok": False, "state": "unknown", "message": "Stream health is unavailable. Inspect OBS and refresh status."}

    async def retry_recovery(self):
        return await self._begin("retry-recovery")

    async def cancel_media_operation(self):
        # Local startup cancellation must never invoke StopStream: the user may
        # be recording while an unrelated, explicitly started broadcast is live.
        if self._cancel_media_task and not self._cancel_media_task.done():
            return await asyncio.shield(self._cancel_media_task)

        async def cancel():
            task = self._control_task
            payload = self._control_payload
            kind = payload.get("action") if isinstance(payload, dict) else None
            if (not task or task.done() or self._control_action != "media" or
                    kind not in {"record-start", "replay-start"}):
                result = await self.status()
                result["action_result"] = {"ok": True, "action": "cancel-media", "message": "No local startup is pending; existing output was not changed."}
                return result
            self.cancel_requested = True
            self._signal_pending()
            # The CLI owns rollback/finalization of a newly started local output.
            # Draining it also covers cancellation before its child is attached.
            await asyncio.shield(task)
            self._status_task = None
            result = await self.status()
            media = result.get("media")
            media = media if isinstance(media, dict) else {}
            recording = media.get("recording")
            recording = recording if isinstance(recording, dict) else {}
            stopped = (media.get("known") is True and
                       (recording.get("active") is False if kind == "record-start" else
                        media.get("replay_active") is False))
            result["action_result"] = {"ok": stopped, "action": "cancel-media",
                                       "message": "Local startup cancelled; any partial recording was preserved. Streaming was not changed." if stopped else
                                       "Local startup cancellation could not confirm shutdown. Inspect recording/replay in managed OBS; streaming was not changed."}
            return result

        self._cancel_media_task = asyncio.create_task(cancel())
        return await asyncio.shield(self._cancel_media_task)

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
                path = self._plugin_root() / "releases.py"
                spec = importlib.util.spec_from_file_location("obsgod_releases", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                versions = module.current_versions(self._version(), environ=self._child_environment())
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
            await self.mixer_action({"action": "talk-cancel"})
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
