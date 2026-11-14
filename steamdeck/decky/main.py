"""Unprivileged Decky adapter. OBS protocol and credentials stay in the CLI."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import uuid
from urllib.parse import urlsplit


def _bundled_module(name):
    """Load only our fixed packaged modules, including in source-only tests."""
    path = Path(__file__).resolve().parent / (name + ".py")
    spec = importlib.util.spec_from_file_location("obsgod_plugin_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


storage = _bundled_module("storage")
dependency_setup = _bundled_module("dependency_setup")

CONFIGURATION_ACTIONS = {"configure-fields", "change-obs-password", "test-connection", "restart"}
CONFIGURATION_READS = {"configuration", "connection-info", "test-connection"}
DESTINATION_FIELDS = {"server", "stream_key", "replace_key", "bitrate", "fps", "encoder",
                      "microphone", "capture_mode", "width", "height"}
PASSWORD_FIELDS = {"password", "confirm", "generate"}
PRIVATE_FIELDS = {"stream_key", "password"}
CONFIGURATION_UNAVAILABLE = "Configuration readiness is unavailable. Refresh settings before changing your destination or local OBS password. No stream was started."


def _private_values(value, depth=0):
    """Recognize private fields only to redact them, never to return/cache them."""
    values = []
    if isinstance(value, dict) and depth < 4:
        for name, item in value.items():
            normalized = str(name).lower().replace("-", "_")
            if isinstance(item, str) and item and (normalized == "key" or any(part in normalized for part in ("password", "stream_key", "streamkey", "token", "secret"))):
                values.append(item)
            elif isinstance(item, dict):
                values.extend(_private_values(item, depth + 1))
    return values


def _public_configuration_message(value, private=(), fallback=CONFIGURATION_UNAVAILABLE):
    if (not isinstance(value, str) or not value or len(value) > 500 or
            any(ord(char) < 32 or ord(char) == 127 for char in value) or
            any(secret and secret in value for secret in private) or
            re.search(r"(?:password|stream_key|token|secret)\s*[:=]|\b[A-Za-z][A-Za-z0-9+.-]*://|(?:^|\s)/\S+", value, re.I)):
        return fallback
    return value


def _public_connection(value, private=()):
    value = value if isinstance(value, dict) else {}
    private = tuple(private) + tuple(_private_values(value))
    result = {name: value.get(name) is True for name in
              ("ok", "authentication_required", "credentials_available", "connected", "managed", "output_known", "awaiting_verification")}
    result["host"] = value.get("host") if isinstance(value.get("host"), str) and value["host"] in {"127.0.0.1", "localhost", "::1"} else "127.0.0.1"
    result["port"] = value.get("port") if value.get("port") == "4457" else "4457"
    result["process"] = value.get("process") if isinstance(value.get("process"), str) and value["process"] in {"absent", "running", "unknown"} else "unknown"
    result["state"] = value.get("state") if isinstance(value.get("state"), str) and value["state"] in {"stopped", "streaming", "recording", "unknown", "setup"} else "unknown"
    result["message"] = _public_configuration_message(value.get("message"), private)
    return result


def _public_configuration(value, private=()):
    """Explicit projection: future Go fields cannot expose private readback."""
    value = value if isinstance(value, dict) else {}
    private = tuple(private) + tuple(_private_values(value))
    valid = (type(value.get("schema_version")) is int and value["schema_version"] == 1 and
             all(type(value.get(name)) is bool for name in
                 ("ok", "configured", "key_configured", "output_known", "can_configure", "can_close")) and
             isinstance(value.get("settings"), dict) and isinstance(value.get("connection"), dict))
    connection = value.get("connection") if isinstance(value.get("connection"), dict) else {}
    for name in ("ok", "authentication_required", "credentials_available", "connected", "managed", "output_known", "awaiting_verification"):
        if name in connection and type(connection[name]) is not bool:
            valid = False
    settings = {"server": "", "bitrate": 4500, "fps": 30, "encoder": "vaapi", "width": 1280,
                "height": 720, "capture_mode": "screen", "microphone": False}
    source = value.get("settings") if isinstance(value.get("settings"), dict) else {}
    for name in settings:
        if name not in source:
            continue
        item = source[name]
        if name == "server":
            safe = isinstance(item, str) and len(item.encode("utf-8", errors="replace")) <= 4096 and not any(ord(c) < 32 or ord(c) == 127 for c in item)
            try:
                url = urlsplit(item)
                safe = safe and (not item or (url.scheme in {"rtmp", "rtmps"} and bool(url.hostname) and
                        url.username is None and url.password is None and not url.query and not url.fragment))
            except (ValueError, TypeError):
                safe = False
            if isinstance(item, str) and any(secret and secret in item for secret in private):
                safe = False
        elif name in {"bitrate", "fps", "width", "height"}:
            safe = type(item) is int and 0 <= item <= 100000
        elif name == "microphone":
            safe = type(item) is bool
        elif name == "encoder":
            safe = item in {"vaapi", "x264"} if isinstance(item, str) else False
        else:
            safe = item in {"", "screen", "game"} if isinstance(item, str) else False
        if safe:
            settings[name] = item
        else:
            valid = False
    if not settings["width"] and not settings["height"]:
        settings["width"], settings["height"] = 1280, 720
    if not settings["capture_mode"]:
        settings["capture_mode"] = "screen"
    output_known = valid and value.get("output_known") is True
    ok = valid and value.get("ok") is True
    return {"schema_version": 1, "ok": ok, "configured": valid and value.get("configured") is True,
            "key_configured": valid and value.get("configured") is True and value.get("key_configured") is True,
            "settings": settings, "connection": _public_connection(value.get("connection"), private),
            "output_known": output_known, "can_configure": ok and output_known and value.get("can_configure") is True,
            "can_close": ok and output_known and value.get("can_close") is True,
            "message": _public_configuration_message(value.get("message"), private) if valid else CONFIGURATION_UNAVAILABLE}


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
        self._dependency_job = None
        self._setup_requested = False
        self._configuration_task = None
        self._configuration_tasks = set()
        self._configuration_epoch = 0

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
        """Retain one managed store; prepare only Decky-owned metadata/jobs."""
        return storage.child_environment(self._plugin_root(), self._provided)

    @property
    def _dependency_busy(self):
        return self._setup_requested or bool(self._dependency_job and self._dependency_job.running)

    @staticmethod
    def _setup_unavailable(code="context", message=None):
        message = message or "Decky's player storage context is unavailable. Reload or update Decky, then retry setup. Existing settings are preserved."
        return {"schema_version": 1, "ready": False, "state": "failed", "message": message,
                "reason": {"code": code, "message": message}, "dependencies": [],
                "remote": {"name": "flathub", "configured": False, "needs_add": False,
                           "valid": False, "reason": "Not observed."},
                "operation": None, "can_install": False, "can_cancel": False}

    async def _dependency_preflight(self):
        # The setup worker holds the SAME cross-process control.lock as the Go
        # commands before calling this fresh read. An old CLI cannot Start in
        # the gap between observing idle and installing dependencies.
        if self.busy or self._closing:
            return False
        current = await self._run("status")
        media = current.get("media")
        recording = media.get("recording") if isinstance(media, dict) else None
        media_idle = (isinstance(media, dict) and media.get("known") is True and
                      media.get("replay_active") is False and
                      (recording is None or isinstance(recording, dict) and recording.get("active") is False))
        absent_legacy = media is None and current.get("process") == "absent"
        return (current.get("output_known") is True and
                current.get("stream", {}).get("active") is False and
                not current.get("recording") and (media_idle or absent_legacy))

    def _dependency_controller(self):
        if self._dependency_job is None:
            context = storage.context(self._plugin_root(), self._provided)
            if context["mode"] != "decky":
                raise OSError("The loader did not provide complete plugin storage context")
            self._dependency_job = dependency_setup.DependencySetup(
                Path(context["jobs_dir"]), self._child_environment(),
                control_lock=Path(context["shared_state"]) / "control.lock",
                preflight=self._dependency_preflight)
        return self._dependency_job

    async def dependency_status(self):
        try:
            return await self._dependency_controller().status()
        except (OSError, ValueError):
            return self._setup_unavailable()

    async def install_dependencies(self, consent=False):
        if consent is not True:
            return await self.dependency_status()
        if self._closing or self.busy:
            return self._setup_unavailable("control_busy", "Wait for OBS control to finish before installing dependencies.")
        # Reserve before the first await, so a competing panel Start cannot
        # overtake the creation of the backend-owned setup job.
        self._setup_requested = True
        try:
            return await self._dependency_controller().start(consent=True)
        except (OSError, ValueError):
            return self._setup_unavailable()
        finally:
            self._setup_requested = False

    async def cancel_dependency_setup(self):
        try:
            return await self._dependency_controller().cancel()
        except (OSError, ValueError):
            return self._setup_unavailable()

    @staticmethod
    def _configuration_failure(action=None, message=CONFIGURATION_UNAVAILABLE):
        result = _public_configuration(None)
        result["message"] = message
        if action:
            result["action_result"] = {"action": action, "ok": False, "message": message}
        return result

    def _invalidate_configuration(self):
        self._configuration_epoch += 1
        self._configuration_task = None

    async def _read_configuration(self):
        try:
            raw = await self._run("configuration")
            return _public_configuration(raw, _private_values(self._control_payload))
        except (OSError, ValueError, TypeError, UnicodeError):
            return self._configuration_failure()

    async def _configuration_observed(self):
        # In-flight readers share work. A mutation invalidates its generation,
        # so a late pre-save response cannot overwrite the new destination.
        for _ in range(3):
            epoch = self._configuration_epoch
            if self._configuration_task is None or self._configuration_task.done():
                self._configuration_task = asyncio.create_task(self._read_configuration())
                self._configuration_tasks.add(self._configuration_task)
                self._configuration_task.add_done_callback(self._configuration_tasks.discard)
            result = await asyncio.shield(self._configuration_task)
            if epoch == self._configuration_epoch:
                return dict(result)
        return self._configuration_failure()

    def _configuration_gate(self, result, finishing=None):
        result = dict(result)
        control_busy = bool(self._control_task and not self._control_task.done() and self._control_task is not finishing)
        stop_busy = bool(self._stop_task and not self._stop_task.done())
        if self._closing or self._dependency_busy or control_busy or stop_busy:
            result["can_configure"], result["can_close"] = False, False
            result["message"] = ("Dependency setup is running. Wait or cancel setup before changing settings." if self._dependency_busy else
                                 "The plugin is closing. Wait for it to reload before changing settings." if self._closing else
                                 "Another OBS operation is running. Wait for confirmed status before changing settings.")
        return result

    async def configuration_status(self):
        return self._configuration_gate(await self._configuration_observed())

    async def _configuration_input(self, action, payload, allowed):
        if (not isinstance(payload, dict) or not payload or
                any(type(name) is not str or name not in allowed or type(value) not in (str, int, float, bool)
                    for name, value in payload.items())):
            return self._configuration_failure(action, "Send one supported settings object containing only scalar fields.")
        if action == "change-obs-password" and payload.get("confirm") is not True:
            return self._configuration_failure(action, "Explicitly confirm the local OBS password change before retrying.")
        owned = dict(payload)
        try:
            return await self._advanced(action, owned)
        finally:
            # The task receives its own separate copy below. A disconnected
            # caller cannot erase the key before the queued Go command reads it.
            for name in PRIVATE_FIELDS:
                if name in owned:
                    owned[name] = ""

    async def configure_destination(self, payload):
        return await self._configuration_input("configure-fields", payload, DESTINATION_FIELDS)

    async def change_control_password(self, payload):
        return await self._configuration_input("change-obs-password", payload, PASSWORD_FIELDS)

    async def test_control_connection(self):
        return await self._begin("test-connection")

    async def close_managed_obs(self):
        # Existing Go Restart positively verifies idle ownership and only closes
        # the managed instance. It does not reopen OBS or start an output.
        return await self._begin("restart")

    async def _configuration_rejection(self, action, message):
        result = await self.configuration_status()
        result["action_result"] = {"action": action, "ok": False, "message": message}
        return result

    def _clear_private_operation(self, task, payload):
        if isinstance(payload, dict):
            for name in PRIVATE_FIELDS:
                if name in payload:
                    payload[name] = ""
        if self._control_task is task and self._control_payload is payload:
            self._control_payload = None

    async def _perform_configuration(self, action, operation_id, payload):
        task = asyncio.current_task()
        try:
            try:
                command = await self._run(action, payload) if payload is not None else await self._run(action)
            except (OSError, ValueError, TypeError, UnicodeError):
                command = {"ok": False, "message": CONFIGURATION_UNAVAILABLE}
            private = _private_values(payload) + _private_values(command)
            outcome = {"id": operation_id, "action": action, "ok": isinstance(command, dict) and command.get("ok") is True,
                       "message": _public_configuration_message(command.get("message") if isinstance(command, dict) else None, private)}
            if self._last_action is None or operation_id >= self._last_action["id"]:
                self._last_action = dict(outcome)
            self._invalidate_configuration()
            observed = await self._configuration_observed()
            if action == "test-connection":
                observed["connection"] = _public_connection(command, private)
            observed = self._configuration_gate(observed, finishing=task)
            observed["action_result"] = outcome
            return observed
        finally:
            self._clear_private_operation(task, payload)

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
        private_configuration = action in CONFIGURATION_ACTIONS or action in CONFIGURATION_READS
        cleanup_budget = 1 if private_configuration else 8
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
                    await self._stop_child(child, cleanup_budget)
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
            if action in CONFIGURATION_READS or action == "change-obs-password":
                timeout = 7
            elif action in {"configure-fields", "restart"}:
                timeout = 11
            if action == "mixer" and isinstance(payload, dict) and payload.get("action") != "configure":
                timeout = 8
            output, _ = await asyncio.wait_for(communication, timeout)
            if private_configuration and len(output) > 131072:
                raise ValueError()
            result = json.loads(output)
            if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
                raise ValueError()
            return result
        except asyncio.CancelledError:
            await self._stop_child(process, cleanup_budget)
            raise
        except (asyncio.TimeoutError, ValueError, UnicodeError):
            await self._stop_child(process, cleanup_budget)
            return self._unknown("Output state is unconfirmed. Use Stop streaming and inspect OBS if the connection does not recover.")
        finally:
            if self.pending is process:
                self.pending = None

    @staticmethod
    async def _stop_child(process, budget=8):
        if process.returncode is None:
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.communicate(), budget)
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
            result = self._unknown("OBSGod's backend or player storage is unavailable. Reload or repair the Decky plugin; existing settings were not reset.")
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
        if action in CONFIGURATION_ACTIONS:
            return await self._perform_configuration(action, operation_id, payload)
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
                command = self._unknown("OBSGod's backend or player storage is unavailable. Reload or repair the Decky plugin; existing settings were not reset.")
        self._invalidate_configuration()
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
        if self._dependency_busy:
            if action in CONFIGURATION_ACTIONS:
                return await self._configuration_rejection(action, "Dependency setup is running. Wait or cancel setup before changing settings.")
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "Dependency setup is running. Wait or cancel setup before starting another operation."}
            return result
        if self._closing:
            if action in CONFIGURATION_ACTIONS:
                return await self._configuration_rejection(action, "The plugin is closing. Wait for it to reload before changing settings.")
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "OBSGod is shutting down. Wait for the plugin to reload."}
            return result
        if self._control_task and not self._control_task.done():
            if self._control_action == action and self._control_payload == payload and not self.cancel_requested:
                return await asyncio.shield(self._control_task)
            if action in CONFIGURATION_ACTIONS:
                return await self._configuration_rejection(action, "Another operation is running; wait or cancel it.")
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "Another operation is running; wait or cancel it."}
            return result
        if self._stop_task and not self._stop_task.done():
            if action in CONFIGURATION_ACTIONS:
                return await self._configuration_rejection(action, "Stop is still being confirmed. Wait before changing settings.")
            result = await self.status()
            result["action_result"] = {"ok": False, "action": action,
                                       "message": "Stop is still being confirmed. Wait before starting another operation."}
            return result
        self.cancel_requested = False
        self._control_action = action
        owned = dict(payload) if action in CONFIGURATION_ACTIONS and isinstance(payload, dict) else payload
        self._control_payload = owned
        self._operation_id += 1
        self._invalidate_configuration()
        self._control_task = asyncio.create_task(self._perform(action, self._operation_id, payload=owned))
        if action in CONFIGURATION_ACTIONS:
            self._control_task.add_done_callback(lambda task: self._clear_private_operation(task, owned))
        return await asyncio.shield(self._control_task)

    async def start(self):
        return await self._begin("start")

    async def test_recording(self):
        return await self._begin("test-recording")

    async def _advanced(self, action, payload):
        if not isinstance(payload, dict):
            if action in CONFIGURATION_ACTIONS:
                return self._configuration_failure(action, "Send one settings object.")
            return {"ok": False, "message": "Send one settings object."}
        try:
            encoded = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError):
            if action in CONFIGURATION_ACTIONS:
                return self._configuration_failure(action, "Settings must contain valid JSON values.")
            return {"ok": False, "message": "Settings must contain valid JSON values."}
        if len(encoded) > 16384:
            if action in CONFIGURATION_ACTIONS:
                return self._configuration_failure(action, "Settings are too large; choose a smaller profile.")
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
        self._invalidate_configuration()
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
            # Stop the owned installer before Stop needs the shared control
            # lock. Closing a panel never reaches this backend lifecycle hook.
            if self._dependency_job is not None:
                await self._dependency_job.close()
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
