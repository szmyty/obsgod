"""Consented, unprivileged Flatpak setup; deliberately never launches OBS.

Only allowlisted status is persisted/exposed. Flatpak output is bounded and used
to classify failures, never forwarded to the panel. A process lock and receipt
survive panel lifetimes and identify interrupted backend jobs on the next load.
Compatible with SteamOS Python 3.9 (stdlib only).
"""

import asyncio
import configparser
import copy
import fcntl
import json
import os
import platform
import pwd
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path


OBS = "com.obsproject.Studio"
GSTREAMER = OBS + ".Plugin.Gstreamer"
FLATHUB = "https://flathub.org/repo/flathub.flatpakrepo"
REMOTE_URLS = {"https://dl.flathub.org/repo", "https://flathub.org/repo"}
QUERY_TIMEOUT = 6
SETUP_TIMEOUT = 1200
MAX_OUTPUT = 256 * 1024
MAX_EVENTS = 32
ACTIVE = {"running", "cancelling"}
STATES = ACTIVE | {"ready", "failed", "cancelled", "interrupted", "setup_required"}


def python_process(environ):
    """Run our stdlib helpers with Python, including inside frozen Decky.

    PyInstaller's sys.executable is PluginLoader, not a Python interpreter.
    SteamOS supplies /usr/bin/python3; never resolve an interpreter via PATH or
    download another runtime. Isolate helpers from loader Python configuration.
    """
    env = dict(environ)
    executable = sys.executable
    if getattr(sys, "frozen", False):
        executable = Path("/usr/bin/python3").resolve(strict=True)
        for path in (*reversed(executable.parents), executable):
            info = path.stat()
            expected_type = stat.S_ISREG(info.st_mode) if path == executable else stat.S_ISDIR(info.st_mode)
            if info.st_uid != 0 or info.st_mode & 0o022 or not expected_type:
                raise OSError("The system Python interpreter is unavailable or unsafe")
        if not os.access(executable, os.X_OK):
            raise OSError("The system Python interpreter is unavailable or unsafe")
        # PyInstaller prepends its private libraries for itself. System Python
        # must use the original library search environment, not bundled ABIs.
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return [str(executable), "-I", "-B"], env


MESSAGES = {
    "context": "Setup needs the actual player's user session. Restart Decky in Gaming Mode or sign in to Desktop Mode, then retry.",
    "flatpak_missing": "Flatpak is unavailable. Repair or update SteamOS in Desktop Mode, then retry; do not unlock the system.",
    "system_scope": "A required dependency exists only in the system installation. Resolve its scope in Desktop Mode before retrying; setup will not create a duplicate user installation.",
    "observation": "Flatpak could not confirm installed dependencies. Check Discover and any pending Flatpak operation in Desktop Mode, then retry.",
    "obs_version": "OBS 28 or newer is required for its bundled WebSocket server. Update the existing user installation in Discover, then retry; do not add another WebSocket plugin.",
    "compatibility": "The installed OBS/add-on branches could not be verified as compatible. Check the OBS and GStreamer entries in Discover, then retry.",
    "remote_conflict": "The user remote named flathub is not the expected verified Flathub remote. Inspect it in Desktop Mode; setup will not replace it.",
    "network": "The dependency download could not reach Flathub. Check the connection in Desktop Mode, then retry; installed components are preserved.",
    "disk_full": "Dependency setup ran out of disk space. Free space in Desktop Mode, then retry; installed components and Flatpak's cache are preserved.",
    "permission": "Flatpak denied the operation in this user session. Check Discover and Decky's user permissions in Desktop Mode, then retry; no administrator changes were attempted.",
    "verification": "Flatpak could not verify the download. Check Flathub and the system clock in Desktop Mode, then retry; verification was not disabled.",
    "flatpak_busy": "Another Flatpak operation is busy. Let Discover or that operation finish, then retry.",
    "timeout": "Dependency setup reached its time limit. Check the connection and Discover, then retry; setup will recheck installed components first.",
    "flatpak_failed": "Flatpak could not finish dependency setup. Check Discover, disk space and the connection in Desktop Mode, then retry.",
    "storage": "The private setup receipt is unavailable or unsafe. Repair the plugin's Decky runtime directory before retrying.",
    "external_job": "A dependency setup job is already owned by another backend. Wait for it to finish or restart Decky before retrying.",
    "control_busy": "Another OBS control operation is busy. Let it finish before installing dependencies.",
    "output_active": "OBS output could not be confirmed idle. Stop streaming, recording and replay, then check status before installing dependencies.",
    "cancelled": "Dependency setup was cancelled. Installed components are preserved; choose Install to retry the missing work.",
    "interrupted": "The previous setup was interrupted. Installed components have been checked again; choose Install to retry missing work.",
    "consent": "OBS Studio and its compatible GStreamer extension require your approval. Choose Install, or Later to keep setup pending.",
}

EVENTS = set(MESSAGES.values()) | {
    "Flatpak is still working. You may close this panel; setup will continue.",
    "Dependency setup was approved. Checking installed components before each step.",
    "Adding the verified Flathub user remote.",
    "Installing OBS Studio.",
    "Installing the compatible GStreamer capture extension.",
    "Checking what Flatpak actually installed.",
    "Dependency setup finished; broadcasting has not been started.",
    "Cancellation requested. Flatpak will stop; installed components will be preserved.",
}


class SetupError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def _error_code(output):
    text = output.lower()
    for code, patterns in (
        ("disk_full", ("no space left", "disk full", "not enough space", "insufficient space")),
        ("permission", ("permission denied", "not authorized", "not permitted", "polkit", "access denied")),
        ("verification", ("gpg", "signature", "checksum", "certificate", "tls")),
        ("flatpak_busy", ("another transaction", "lock was not acquired", "already running", "resource busy")),
        ("network", ("resolve host", "network", "could not connect", "couldn't connect", "connection", "download", "timed out", "offline")),
    ):
        if any(pattern in text for pattern in patterns):
            return code
    return "flatpak_failed"


def _safe_directories(path, missing=False):
    """A private leaf is unsafe when someone else can rename its ancestors."""
    if not path.is_absolute() or ".." in path.parts:
        raise OSError()
    for component in tuple(reversed(path.parents)) + (path,):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if missing:
                return
            raise
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.geteuid()) or
                (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
            raise OSError()


class DependencySetup:
    def __init__(self, storage_dir, environment, control_lock=None, preflight=None):
        self.directory = Path(storage_dir) / "dependencies"
        self.environment = dict(environment)
        self._guard = asyncio.Lock()
        self._task = None
        self._lock_fd = None
        self._control_fd = None
        self.control_lock = Path(control_lock) if control_lock is not None else None
        self.preflight = preflight
        self._operation = None
        self._external_running = False
        self._closing = False
        self._entered = False
        self._initialized = False
        self._problem = None
        self._dependencies = [self._dependency("obs", OBS, "OBS Studio"),
                              self._dependency("gstreamer", GSTREAMER, "GStreamer capture extension")]
        self._remote = {"name": "flathub", "configured": False, "needs_add": False,
                        "valid": False, "reason": "Not observed yet."}
        self._ready = False
        self._can_install = False
        self._plan = []
        self._flatpak = None
        self._child_env = None

    @staticmethod
    def _dependency(identifier, app_id, name):
        return {"id": identifier, "app_id": app_id, "name": name, "installed": False,
                "compatible": False, "scope": None, "ref": None, "version": None}

    @property
    def running(self):
        return bool(self._task and not self._task.done()) or self._external_running

    @property
    def busy(self):
        return self.running

    def _initialize(self):
        try:
            _safe_directories(self.directory, missing=not self._initialized)
            if not self._initialized:
                self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                _safe_directories(self.directory)
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise OSError()
            if not self._initialized:
                self._read_receipt()
            self._initialized = True
        except (OSError, ValueError, TypeError):
            raise SetupError("storage") from None

    def _read_receipt(self):
        path = self.directory / "receipt.json"
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > 32768:
                raise OSError()
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                fd = None
                data = json.load(stream)
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError()
            value = data["operation"]
            if value is None:
                self._operation = None
                return
            # Receipts are private but still untrusted input after interruption.
            if (not isinstance(value, dict) or not re.fullmatch(r"[a-f0-9]{32}", value.get("id", "")) or
                    value.get("state") not in STATES or value.get("stage") not in
                    {"checking", "remote", "obs", "gstreamer", "verifying", "finished"}):
                raise ValueError()
            events = value.get("progress", [])
            if not isinstance(events, list) or len(events) > MAX_EVENTS:
                raise ValueError()
            for event in events:
                if (not isinstance(event, dict) or event.get("level") not in {"info", "error"} or
                        not isinstance(event.get("message"), str) or event["message"] not in EVENTS or
                        any(ord(c) < 32 for c in event["message"]) or
                        not isinstance(event.get("time"), (int, float))):
                    raise ValueError()
            for key in ("started_at", "finished_at"):
                if value.get(key) is not None and not isinstance(value[key], (int, float)):
                    raise ValueError()
            code = value.get("error_code")
            if code is not None and code not in MESSAGES:
                raise ValueError()
            # Only schema-owned fields survive, rather than arbitrary receipt data.
            self._operation = {key: value.get(key) for key in
                               ("id", "state", "stage", "started_at", "finished_at", "error_code")}
            self._operation["progress"] = events
            self._operation["cancel_requested"] = value.get("cancel_requested") is True
        except (KeyError, ValueError, TypeError, UnicodeError):
            raise SetupError("storage") from None
        finally:
            if fd is not None:
                os.close(fd)

    def _save(self):
        path = self.directory / "receipt.json"
        temporary = self.directory / (".receipt-" + uuid.uuid4().hex)
        try:
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    raise OSError()
            fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"schema_version": 1, "operation": self._operation}, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(temporary), str(path))
        except (OSError, ValueError, TypeError):
            raise SetupError("storage") from None
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _acquire(self):
        fd = os.open(str(self.directory / "setup.lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise SetupError("storage")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            self._lock_fd = fd
            fd = None
            return True
        finally:
            if fd is not None:
                os.close(fd)

    def _release(self):
        if self._control_fd is not None:
            fcntl.flock(self._control_fd, fcntl.LOCK_UN)
            os.close(self._control_fd)
            self._control_fd = None
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None

    def _acquire_control(self):
        if self.control_lock is None:
            return
        path = self.control_lock
        try:
            if not path.is_absolute():
                raise OSError()
            _safe_directories(path.parent, missing=True)
            # A new user has no managed state yet. Initialize only its private
            # namespace; never change permissions on existing shared state.
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _safe_directories(path.parent)
            parent = path.parent.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode) or
                    parent.st_uid != os.geteuid() or parent.st_mode & 0o077):
                raise OSError()
            fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    raise OSError()
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise SetupError("control_busy") from None
                self._control_fd, fd = fd, None
            finally:
                if fd is not None:
                    os.close(fd)
        except OSError:
            raise SetupError("storage") from None

    def _event(self, message, level="info", stage=None):
        if not self._operation:
            return
        if message not in EVENTS:
            raise ValueError("Only fixed public progress messages may be recorded.")
        if stage:
            self._operation["stage"] = stage
        self._operation["progress"].append({"time": time.time(), "level": level, "message": message})
        self._operation["progress"] = self._operation["progress"][-MAX_EVENTS:]
        self._save()

    def _context(self):
        try:
            uid = os.geteuid()
            account = pwd.getpwuid(uid)
            env = dict(self.environment)
            home = Path(env.get("HOME", ""))
            if (uid == 0 or os.getuid() != uid or not home.is_absolute() or home.is_symlink() or
                    home.resolve(strict=True) != Path(account.pw_dir).resolve(strict=True) or
                    home.stat().st_uid != uid):
                raise OSError()
            if env.get("DECKY_USER_HOME") and Path(env["DECKY_USER_HOME"]).resolve(strict=True) != home.resolve():
                raise OSError()
            if env.get("DECKY_USER") and env["DECKY_USER"] != account.pw_name:
                raise OSError()
            runtime = Path(env.get("XDG_RUNTIME_DIR") or "/run/user/{}".format(uid))
            info = runtime.lstat()
            if not runtime.is_absolute() or not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077:
                raise OSError()
            address = env.get("DBUS_SESSION_BUS_ADDRESS") or "unix:path=" + str(runtime / "bus")
            matched = re.fullmatch(r"unix:path=([^,;]+)(?:,guid=[a-fA-F0-9]+)?", address)
            if not matched:
                raise OSError()
            bus = Path(matched.group(1))
            if bus.parent.resolve(strict=True) != runtime.resolve(strict=True) or bus.is_symlink():
                raise OSError()
            info = bus.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid:
                raise OSError()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(0.5)
                connection.connect(str(bus))
                credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                if struct.unpack("3i", credentials)[1] != uid:
                    raise OSError()
            # Do not accidentally redirect Flatpak to a plugin-owned or service store.
            if env.get("FLATPAK_USER_DIR") or env.get("FLATPAK_SYSTEM_DIR"):
                raise OSError()
            data_home = Path(env.get("XDG_DATA_HOME") or str(home / ".local/share"))
            if not data_home.is_absolute() or self.directory == data_home or self.directory in data_home.parents:
                raise OSError()
            env["HOME"], env["USER"], env["LOGNAME"] = str(home), account.pw_name, account.pw_name
            env["XDG_RUNTIME_DIR"], env["DBUS_SESSION_BUS_ADDRESS"] = str(runtime), address
            env["LC_ALL"] = "C"
            self._flatpak = shutil.which("flatpak", path=env.get("PATH"))
            self._child_env = env
            if not self._flatpak:
                raise SetupError("flatpak_missing")
        except (OSError, ValueError, KeyError, TypeError):
            raise SetupError("context") from None

    @staticmethod
    async def _stop(process):
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), 3)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def _command(self, arguments, timeout=QUERY_TIMEOUT, progress=False):
        # No shell and no user-provided argv. Children never receive credentials in argv.
        leases = tuple(fd for fd in (self._lock_fd, self._control_fd) if fd is not None)
        # The bounded worker retains kernel leases if the loader is killed. A
        # replacement backend cannot mistake its still-running child for a dead
        # transaction and start duplicate work. No process is killed by saved PID.
        interpreter, environment = python_process(self._child_env)
        spawning = asyncio.create_task(asyncio.create_subprocess_exec(
            *interpreter, str(Path(__file__).resolve()), "--worker", str(timeout), self._flatpak,
            *arguments, env=environment, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True, pass_fds=leases))
        try:
            process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            try:
                process = await spawning
                await self._stop(process)
            except OSError:
                pass
            raise
        except (OSError, ValueError):
            raise SetupError("flatpak_missing") from None

        async def read(stream):
            parts, size = [], 0
            while True:
                part = await stream.read(8192)
                if not part:
                    break
                if size < MAX_OUTPUT:
                    parts.append(part[:MAX_OUTPUT - size])
                    size += len(parts[-1])
            return b"".join(parts).decode("utf-8", errors="replace")

        stdout = asyncio.create_task(read(process.stdout))
        stderr = asyncio.create_task(read(process.stderr))
        waiting = asyncio.create_task(process.wait())
        started, heartbeat = time.monotonic(), time.monotonic()
        try:
            while process.returncode is None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise SetupError("timeout")
                try:
                    await asyncio.wait_for(asyncio.shield(waiting), min(remaining, 1))
                except asyncio.TimeoutError:
                    pass
                if progress and time.monotonic() - heartbeat >= 5:
                    self._event("Flatpak is still working. You may close this panel; setup will continue.")
                    heartbeat = time.monotonic()
            output, error = await asyncio.gather(stdout, stderr)
            return process.returncode, output, error
        finally:
            if process.returncode is None:
                await self._stop(process)
            await asyncio.gather(stdout, stderr, return_exceptions=True)
            await waiting

    async def _query(self, arguments):
        try:
            code, output, error = await self._command(arguments)
        except SetupError as error:
            if error.code == "timeout":
                raise SetupError("observation") from None
            raise
        if code:
            mapped = _error_code(error + output)
            raise SetupError(mapped if mapped != "flatpak_failed" else "observation")
        return output

    @staticmethod
    def _refs(output, app_id, kind):
        values = {}
        pattern = r"(?:" + kind + r"/)?" + re.escape(app_id) + r"/([A-Za-z0-9_-]{1,24})/([A-Za-z0-9._-]{1,64})"
        for line in output.splitlines():
            reference, separator, version = line.partition("\t")
            match = re.fullmatch(pattern, reference.strip())
            if match:
                reference = kind + "/" + app_id + "/" + match.group(1) + "/" + match.group(2)
                if reference in values:
                    raise SetupError("observation")
                values[reference] = version.strip() if separator else ""
        return values

    @staticmethod
    def _metadata(output):
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        try:
            parser.read_string(output)
        except configparser.Error:
            raise SetupError("compatibility") from None
        return parser

    async def _observe(self):
        try:
            await asyncio.wait_for(self._observe_dependencies(), 8)
        except asyncio.TimeoutError:
            self._ready, self._can_install = False, False
            self._problem = "observation"

    async def _observe_dependencies(self):
        self._ready, self._can_install, self._plan = False, False, []
        self._problem = None
        try:
            self._context()
            user = await self._query(["list", "--user", "--columns=ref,version"])
            system = await self._query(["list", "--system", "--columns=ref,version"])
            obs = self._refs(user, OBS, "app")
            gst = self._refs(user, GSTREAMER, "runtime")
            system_obs = self._refs(system, OBS, "app")
            system_gst = self._refs(system, GSTREAMER, "runtime")
            self._dependencies = [self._dependency("obs", OBS, "OBS Studio"),
                                  self._dependency("gstreamer", GSTREAMER, "GStreamer capture extension")]
            for dependency, refs, system_refs in ((self._dependencies[0], obs, system_obs),
                                                   (self._dependencies[1], gst, system_gst)):
                dependency["installed"] = bool(refs or system_refs)
                dependency["scope"] = "user" if refs else "system" if system_refs else None
            remote_output = await self._query(["remotes", "--user", "--columns=name,url,options"])
            remotes = [line.split("\t") for line in remote_output.splitlines() if line.split("\t")[0] == "flathub"]
            valid = (len(remotes) == 1 and len(remotes[0]) == 3 and
                     remotes[0][1].rstrip("/") in REMOTE_URLS and
                     not any(flag in remotes[0][2].lower() for flag in ("no-gpg-verify", "disabled")))
            self._remote = {"name": "flathub", "configured": bool(remotes), "valid": valid,
                            "needs_add": not remotes, "reason": "Verified Flathub user remote." if valid else
                            "Flathub will be added to the user's installation with approval." if not remotes else MESSAGES["remote_conflict"]}
            if (not obs and system_obs) or (not gst and system_gst):
                raise SetupError("system_scope")
            architecture = platform.machine()
            if architecture not in {"x86_64", "aarch64"}:
                raise SetupError("compatibility")
            extension_branch = "stable"
            if obs:
                reference = (await self._query(["info", "--user", "--show-ref", OBS])).strip()
                if reference not in obs:
                    raise SetupError("observation")
                _, _, architecture, branch = reference.split("/")
                version = obs[reference]
                if len(version) > 80 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.-]+)?", version):
                    raise SetupError("observation")
                self._dependencies[0].update(ref=reference, version=version)
                if int(re.match(r"[0-9]+", version).group()) < 28:
                    raise SetupError("obs_version")
                metadata = self._metadata(await self._query(["info", "--user", "--show-metadata", reference]))
                section = "Extension " + OBS + ".Plugin"
                if not metadata.has_section(section):
                    raise SetupError("compatibility")
                extension_branch = metadata.get(section, "version", fallback=branch)
                branches = metadata.get(section, "versions", fallback=extension_branch).strip(";").split(";")
                if len(branches) > 8 or not all(re.fullmatch(r"[A-Za-z0-9._-]{1,64}", value) for value in branches + [extension_branch]):
                    raise SetupError("compatibility")
                self._dependencies[0]["compatible"] = True
                candidates = ["runtime/{}/{}/{}".format(GSTREAMER, architecture, value) for value in branches]
                matching = [value for value in candidates if value in gst]
                if matching:
                    gst_ref = matching[0]
                    metadata = self._metadata(await self._query(["info", "--user", "--show-metadata", gst_ref]))
                    owner = metadata.get("ExtensionOf", "ref", fallback="")
                    if owner != reference:
                        raise SetupError("compatibility")
                    gst_version = gst[gst_ref]
                    safe_version = gst_version if len(gst_version) <= 80 and re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.-]+)?", gst_version) else None
                    self._dependencies[1].update(ref=gst_ref, version=safe_version, compatible=True)
                else:
                    self._plan.append(("gstreamer", "runtime/{}/{}/{}".format(GSTREAMER, architecture, extension_branch)))
            else:
                self._plan.append(("obs", "app/{}/{}/stable".format(OBS, architecture)))
            self._ready = all(item["compatible"] for item in self._dependencies)
            if self._ready:
                self._remote["needs_add"] = False
            elif remotes and not valid:
                raise SetupError("remote_conflict")
            self._can_install = not self._ready and bool(self._plan)
        except SetupError as error:
            self._problem = error.code
            self._can_install = False

    def _snapshot(self):
        operation = copy.deepcopy(self._operation)
        if self.running:
            state = "cancelling" if operation and operation.get("cancel_requested") else "running"
            if self._external_running:
                message = "A previous backend still owns dependency setup. Wait for its bounded worker to finish; status will then check installed components again."
            else:
                message = "Cancelling dependency setup; installed components will be checked again." if state == "cancelling" else "Installing dependencies. You may close this panel and return later."
        elif self._ready:
            state, message = "ready", "OBS and its compatible GStreamer extension are installed. OBS has not been launched by setup."
        elif self._problem:
            state, message = "setup_required", MESSAGES[self._problem]
        elif operation and operation.get("state") in {"failed", "cancelled", "interrupted"}:
            state = operation["state"]
            message = MESSAGES.get(operation.get("error_code"), MESSAGES.get(state, MESSAGES["flatpak_failed"]))
        else:
            state, message = "setup_required", MESSAGES["consent"]
        return {"schema_version": 1, "ready": self._ready, "state": state, "message": message,
                "reason": None if self._ready else {"code": self._problem or (operation or {}).get("error_code") or "consent", "message": message},
                "dependencies": copy.deepcopy(self._dependencies), "remote": dict(self._remote),
                "operation": operation, "can_install": self._can_install and not self.running,
                "can_cancel": bool(self._task and not self._task.done() and operation and not operation["cancel_requested"])}

    async def status(self):
        async with self._guard:
            try:
                self._initialize()
                if not self._task or self._task.done():
                    if not self._acquire():
                        self._external_running = True
                        self._read_receipt()
                    else:
                        self._external_running = False
                        try:
                            self._read_receipt()
                            if self._operation and self._operation["state"] in ACTIVE:
                                self._operation.update(state="interrupted", stage="finished", finished_at=time.time(), error_code="interrupted")
                                self._event(MESSAGES["interrupted"])
                            await self._observe()
                        finally:
                            self._release()
            except (SetupError, OSError) as error:
                self._problem = error.code if isinstance(error, SetupError) else "storage"
                self._ready, self._can_install = False, False
            return self._snapshot()

    async def start(self, consent=False):
        if consent is not True:
            return await self.status()
        async with self._guard:
            try:
                self._initialize()
                if self._task and not self._task.done():
                    return self._snapshot()
                if not self._acquire():
                    self._external_running = True
                    self._read_receipt()
                    return self._snapshot()
                self._external_running = False
                self._acquire_control()
                self._closing = False
                self._entered = False
                self._ready = False
                self._problem = None
                self._operation = {"id": uuid.uuid4().hex, "state": "running", "stage": "checking",
                                   "started_at": time.time(), "finished_at": None, "progress": [],
                                   "cancel_requested": False, "error_code": None}
                self._event("Dependency setup was approved. Checking installed components before each step.")
                self._task = asyncio.create_task(self._work())
            except (SetupError, OSError) as error:
                self._release()
                self._problem = error.code if isinstance(error, SetupError) else "storage"
            except asyncio.CancelledError:
                self._release()
                raise
            return self._snapshot()

    async def _work(self):
        terminal, error_code = "failed", None
        deadline = time.monotonic() + SETUP_TIMEOUT
        self._entered = True
        try:
            if self._operation["cancel_requested"]:
                raise asyncio.CancelledError()
            if self.preflight is not None:
                try:
                    safe = await asyncio.wait_for(self.preflight(), 8)
                except (asyncio.TimeoutError, OSError, RuntimeError, ValueError):
                    safe = False
                if safe is not True:
                    raise SetupError("output_active")
            # Each iteration re-observes actual refs. In particular, OBS metadata
            # determines its extension branch after a fresh OBS installation.
            for _ in range(4):
                await self._observe()
                if self._ready:
                    terminal = "ready"
                    break
                if not self._can_install:
                    raise SetupError(self._problem or "compatibility")
                if self._remote["needs_add"]:
                    self._event("Adding the verified Flathub user remote.", stage="remote")
                    arguments = ["remote-add", "--user", "--if-not-exists", "flathub", FLATHUB]
                else:
                    stage, reference = self._plan[0]
                    self._event("Installing OBS Studio." if stage == "obs" else "Installing the compatible GStreamer capture extension.", stage=stage)
                    arguments = ["install", "--user", "--noninteractive", "-y", "flathub", reference]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SetupError("timeout")
                code, output, error = await self._command(arguments, remaining, progress=True)
                if code:
                    raise SetupError(_error_code(error + output))
            else:
                raise SetupError("compatibility")
            if terminal != "ready":
                raise SetupError("compatibility")
        except asyncio.CancelledError:
            terminal = "interrupted" if self._closing else "cancelled"
            error_code = terminal
        except SetupError as error:
            error_code = error.code
        except (OSError, ValueError):
            error_code = "flatpak_failed"
        finally:
            try:
                self._event("Checking what Flatpak actually installed.", stage="verifying")
                await self._observe()
                self._operation.update(state=terminal, error_code=error_code, stage="finished", finished_at=time.time())
                self._event("Dependency setup finished; broadcasting has not been started." if terminal == "ready" else MESSAGES[error_code or "flatpak_failed"],
                            "error" if terminal == "failed" else "info")
            except (SetupError, OSError):
                self._problem = "storage"
                self._ready, self._can_install = False, False
            finally:
                self._release()

    async def cancel(self):
        async with self._guard:
            if self._task and not self._task.done() and not self._operation["cancel_requested"]:
                self._operation["cancel_requested"] = True
                self._operation["state"] = "cancelling"
                self._event("Cancellation requested. Flatpak will stop; installed components will be preserved.")
                if self._entered:
                    self._task.cancel()
            return self._snapshot()

    async def close(self):
        # Closing a panel does not call this; this is backend unload/shutdown.
        self._closing = True
        if self._task and not self._task.done():
            if not self._operation["cancel_requested"]:
                self._operation["cancel_requested"] = True
                if self._entered:
                    self._task.cancel()
            await self._task


def _worker():
    """A time-bounded lease holder, including after abrupt parent termination."""
    if len(sys.argv) < 5 or sys.argv[1] != "--worker":
        return 2
    try:
        budget = float(sys.argv[2])
        if not 0 < budget <= SETUP_TIMEOUT:
            return 2
        # The worker and Flatpak share the isolated group. The owner sends TERM
        # to both, waits, then KILLs this exact owned group if necessary.
        signal.signal(signal.SIGTERM, lambda *_: None)
        signal.signal(signal.SIGINT, lambda *_: None)
        child = subprocess.Popen(sys.argv[3:], stdin=subprocess.DEVNULL)
        try:
            return child.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgrp(), signal.SIGKILL)
            return 124
    except (OSError, ValueError):
        return 127


if __name__ == "__main__":
    sys.exit(_worker())
