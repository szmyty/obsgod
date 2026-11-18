#!/usr/bin/env python3
"""Exercise bounded settings through unchanged packaged Python and Go.

Real unprivileged children, signals and file leases; synthetic private HOME and
Decky paths. No OBS, Flatpak or provider is launched. Receipts contain only
fixed check names, outcomes, counters, durations and source/artifact hashes.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import pwd
import re
import secrets
import shlex
import socket
import stat
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile


CHECKS = []
SPAWNS = []
PRIVATE = set()
STEP = "prepare"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(name, condition):
    global STEP
    STEP = name
    if not condition:
        raise AssertionError(name)


def public(value):
    require("public responses exclude synthetic credentials",
            not any(secret in json.dumps(value) for secret in PRIVATE))
    return value


@contextmanager
def held_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        require("fixture lease is a private owned regular file",
                stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def saved_pair(home):
    return tuple((home / ".config/obsgod" / name).read_bytes()
                 for name in ("deck.json", "secrets.json"))


def bound_credentials(home, key, password=None):
    settings, encoded = saved_pair(home)
    secret = json.loads(encoded)
    path = home / ".config/obsgod/secrets.json"
    require("credential store remains private", stat.S_IMODE(path.stat().st_mode) == 0o600)
    require("synthetic key binding is preserved", secret["stream_key"] == key)
    require("managed password remains distinct", isinstance(secret["obs_password"], str) and
            bool(secret["obs_password"]) and secret["obs_password"] != key)
    if password is not None:
        require("managed password is preserved", secret["obs_password"] == password)
    PRIVATE.add(secret["obs_password"])
    # These fixtures contain only ASCII scalar settings. Preserve file member
    # order to reproduce Go's compact struct JSON for its settings hash.
    compact = json.dumps(json.loads(settings), separators=(",", ":"), ensure_ascii=False).encode()
    require("settings and credentials remain bound", secret["settings_hash"] == digest(compact))
    return secret["obs_password"]


def outcome(value):
    public(value)
    result = value.get("action_result")
    require("capture reply includes a typed action result", isinstance(result, dict) and type(result.get("ok")) is bool)
    return result


async def setter_exec(after, binary):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        for row in SPAWNS[after:]:
            process = row["process"]
            if row["action"] != "set-capture-mode" or process.returncode is not None:
                continue
            try:
                command = Path("/proc/{}/cmdline".format(process.pid)).read_bytes().rstrip(b"\0").split(b"\0")
            except FileNotFoundError:
                continue
            require("observed child argv contains no credential", not any(secret.encode() in b"\0".join(command) for secret in PRIVATE))
            if command == [os.fsencode(binary), b"deck", b"set-capture-mode"]:
                return row
        await asyncio.sleep(0.005)
    require("actual packaged Go capture child was observed", False)


def all_reaped():
    return all(row["process"].returncode is not None for row in SPAWNS)


async def exercise(plugin_root, home, fixture):
    roots = {name: home / "homebrew" / directory / "obsgod"
             for name, directory in (("settings", "settings"), ("runtime", "data"), ("logs", "logs"))}
    for path in roots.values():
        path.mkdir(parents=True, mode=0o700)
    session = home / "session"
    session.mkdir(mode=0o700)
    barriers = fixture / "barriers"
    barriers.mkdir(mode=0o700)
    boundary_log = fixture / "forbidden-commands"
    for name in ("flatpak", "obs", "obs64", "obs-studio", "xdg-open", "dbus-send",
                 "busctl", "gdbus", "pkill", "killall", "pactl", "pw-dump"):
        command = barriers / name
        command.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(name) + " >> " +
                           shlex.quote(str(boundary_log)) + "\nexit 97\n")
        command.chmod(0o700)
    ordinary = home / ".var/app/com.obsproject.Studio/config/obs-studio/ordinary.ini"
    ordinary.parent.mkdir(parents=True, mode=0o700)
    ordinary.write_bytes(b"ordinary OBS fixture remains untouched\n")
    before_ordinary = ordinary.read_bytes()
    environment = dict(os.environ)
    for name in ("OBSGOD_DECKY_STORAGE_MAP", "OBSGOD_DECKY_RUNTIME_DIR", "OBSGOD_DECKY_LOG_DIR",
                 "FLATPAK_USER_DIR", "FLATPAK_SYSTEM_DIR", "PYTHONHOME", "PYTHONPATH"):
        environment.pop(name, None)
    environment.update(HOME=str(home), DECKY_HOME=str(home / "homebrew"),
        DECKY_USER_HOME=str(home), DECKY_USER=pwd.getpwuid(os.getuid()).pw_name,
        DECKY_PLUGIN_DIR=str(plugin_root), DECKY_PLUGIN_SETTINGS_DIR=str(roots["settings"]),
        DECKY_PLUGIN_RUNTIME_DIR=str(roots["runtime"]), DECKY_PLUGIN_LOG_DIR=str(roots["logs"]),
        XDG_CONFIG_HOME=str(home / ".config"), XDG_STATE_HOME=str(home / ".local/state"),
        XDG_DATA_HOME=str(home / ".local/share"), XDG_CACHE_HOME=str(home / ".cache"),
        XDG_RUNTIME_DIR=str(session), DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(session / "bus"),
        PATH=str(barriers) + os.pathsep + os.environ.get("PATH", ""))
    spec = importlib.util.spec_from_file_location("packaged_settings_boundary", plugin_root / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    real_spawn = asyncio.create_subprocess_exec
    binary = plugin_root / "bin/obsgod"
    allowed = {"configuration", "configure-fields", "status", "set-capture-mode", "stop"}

    async def observe_spawn(*args, **kwargs):
        require("adapter uses exact isolated guard and packaged Go",
                len(args) == 9 and args[:8] == (sys.executable, "-I", "-B", str((plugin_root / "main.py").resolve()),
                    "--owned-command", str(os.getpid()), str(binary), "deck") and args[8] in allowed)
        require("spawn arguments exclude credentials", not any(secret in json.dumps(args) for secret in PRIVATE))
        require("adapter preserves fixed subprocess pipe boundary", set(kwargs) == {"stdin", "stdout", "stderr", "env"} and
                kwargs["stdin"] == asyncio.subprocess.PIPE and kwargs["stdout"] == asyncio.subprocess.PIPE and
                kwargs["stderr"] == asyncio.subprocess.DEVNULL)
        process = await real_spawn(*args, **kwargs)
        row = {"action": args[8], "process": process, "permission": False}
        SPAWNS.append(row)
        communicate = process.communicate

        async def checked_communication(content=None):
            if content is None and not row["permission"]:
                # Cancellation before grant may close/reap the attached guard.
                # Sending no permission must never be mistaken for execution.
                return await communicate()
            if not row["permission"]:
                require("owned child receives a single permission byte", isinstance(content, bytes) and content[:1] == b"\x01")
                row["permission"] = True
            else:
                require("cleanup cannot resend command payload", content is None)
            return await communicate(content)

        process.communicate = checked_communication
        return process

    with ExitStack() as context:
        context.enter_context(patch.dict(os.environ, environment, clear=True))
        context.enter_context(patch.object(module.asyncio, "create_subprocess_exec", side_effect=observe_spawn))
        plugin = module.Plugin()
        await plugin._main()
        key = secrets.token_hex(24)
        PRIVATE.add(key)
        try:
            saved = await plugin.configure_destination({"server": "rtmps://example.invalid/app", "stream_key": key,
                                                        "capture_mode": "screen"})
            password = bound_credentials(home, key)
            require("actual packaged bootstrap saves privately", public(saved)["action_result"]["ok"])
            require("private bootstrap payload clears", plugin._control_payload is None)
            control = home / ".local/state/obsgod/control.lock"
            watcher = control.parent / "capture-watch/control.lock"

            async def prepare():
                answer = await asyncio.wait_for(plugin.set_capture_mode("screen"), 12)
                require("fresh explicit capture edit succeeds", outcome(answer)["ok"])
                bound_credentials(home, key, password)
                require("previous packaged children are reaped", all_reaped())

            before = saved_pair(home)
            with held_lock(control):
                started = time.monotonic()
                begin = len(SPAWNS)
                request = asyncio.create_task(plugin.set_capture_mode("game"))
                await setter_exec(begin, binary)
                answer = await asyncio.wait_for(asyncio.shield(request), 12)
                require("blocked edit fails before backend budget", not outcome(answer)["ok"] and time.monotonic() - started < 12)
                require("blocked edit children fully reaped", all_reaped())
                await asyncio.sleep(max(0, 16 - (time.monotonic() - started)))
                require("shared lease stayed held past UI deadline", time.monotonic() - started >= 16)
            await asyncio.sleep(0.5)
            require("lease release after UI deadline cannot cause a late write", saved_pair(home) == before and all_reaped())
            CHECKS.append({"name": "shared-lock-past-ui-deadline", "status": "passed", "seconds": round(time.monotonic() - started, 3)})

            await prepare()
            started = time.monotonic()
            with held_lock(control):
                begin = len(SPAWNS)
                request = asyncio.create_task(plugin.set_capture_mode("game"))
                await setter_exec(begin, binary)
                await asyncio.sleep(2)
            answer = await asyncio.wait_for(request, 12)
            require("near-deadline edit succeeds with actual readback", outcome(answer)["ok"] and
                    answer["settings"]["capture_mode"] == "game" and time.monotonic() - started < 12)
            bound_credentials(home, key, password)
            require("near-deadline success fully reaps children", all_reaped())
            CHECKS.append({"name": "near-deadline-lock-release-success", "status": "passed", "seconds": round(time.monotonic() - started, 3)})

            await prepare()
            before, started = saved_pair(home), time.monotonic()
            with held_lock(control):
                begin = len(SPAWNS)
                caller = asyncio.create_task(plugin.set_capture_mode("game"))
                await setter_exec(begin, binary)
                owned = plugin._control_task
                caller.cancel()
                try:
                    await caller
                except asyncio.CancelledError:
                    pass
                else:
                    require("caller disconnect cancels only its RPC waiter", False)
                require("bounded operation remains backend owned after disconnect", owned is not None and not owned.cancelled())
                answer = await asyncio.wait_for(asyncio.shield(owned), 12)
                require("disconnected operation settles within backend budget", not outcome(answer)["ok"] and time.monotonic() - started < 12)
                require("disconnected command is fully reaped", all_reaped())
            await asyncio.sleep(0.5)
            require("caller disconnect leaves no delayed write", saved_pair(home) == before)
            CHECKS.append({"name": "caller-disconnect-owned-deadline", "status": "passed", "seconds": round(time.monotonic() - started, 3)})

            await prepare()
            before, started = saved_pair(home), time.monotonic()
            with held_lock(control):
                begin = len(SPAWNS)
                request = asyncio.create_task(plugin.set_capture_mode("game"))
                setter = await setter_exec(begin, binary)
                stopping = asyncio.create_task(plugin.stop())
                answer = await asyncio.wait_for(request, 12)
                require("Stop cancels blocked settings child before lease release", not outcome(answer)["ok"] and setter["process"].returncode is not None)
                require("Stop waiting cannot authorize a settings write", saved_pair(home) == before)
            stopped = public(await asyncio.wait_for(stopping, 12))
            require("Stop confirms actual absent output", stopped.get("output_known") is True and stopped["stream"]["active"] is False)
            require("Stop and capture children fully reap", all_reaped() and saved_pair(home) == before)
            CHECKS.append({"name": "stop-during-blocked-edit", "status": "passed", "seconds": round(time.monotonic() - started, 3)})

            await prepare()
            started = time.monotonic()
            with held_lock(control):
                begin = len(SPAWNS)
                first = asyncio.create_task(plugin.set_capture_mode("game"))
                await setter_exec(begin, binary)
                repeated = asyncio.create_task(plugin.set_capture_mode("game"))
                different = public(await plugin.set_capture_mode("screen"))
                require("different edit is rejected while original is owned", not outcome(different)["ok"])
            first_value, repeat_value = await asyncio.wait_for(asyncio.gather(first, repeated), 12)
            require("matching edits share the original action result", outcome(first_value)["ok"] and
                    outcome(repeat_value)["id"] == first_value["action_result"]["id"])
            require("matching edits invoke only one actual Go setter", sum(row["action"] == "set-capture-mode" for row in SPAWNS[begin:]) == 1)
            require("coalesced edits fully reap children", all_reaped())
            CHECKS.append({"name": "repeated-identical-edit-coalescing", "status": "passed", "seconds": round(time.monotonic() - started, 3)})

            await prepare()
            before, started = saved_pair(home), time.monotonic()
            with held_lock(watcher):
                begin = len(SPAWNS)
                request = asyncio.create_task(plugin.set_capture_mode("game"))
                await setter_exec(begin, binary)
                answer = await asyncio.wait_for(request, 12)
                require("watcher contention fails and reaps within backend budget", not outcome(answer)["ok"] and
                        time.monotonic() - started < 12 and all_reaped())
            await asyncio.sleep(0.5)
            require("retired watcher lease cannot resume a stale edit", saved_pair(home) == before)
            CHECKS.append({"name": "watcher-lifetime-lease-contention", "status": "passed", "seconds": round(time.monotonic() - started, 3)})
            await prepare()
            observed = public(await plugin.status())
            require("all output remains positively absent", observed.get("output_known") is True and
                    observed.get("process") == "absent" and observed["stream"]["active"] is False)
            require("ordinary OBS is preserved", ordinary.read_bytes() == before_ordinary)
            require("no forbidden process boundary was attempted", not boundary_log.exists())
            require("every allowed adapter child was granted and reaped", all_reaped() and all(row["permission"] for row in SPAWNS))
            require("private fields remain absent from controller state", not any(secret in json.dumps(plugin._control_payload) for secret in PRIVATE))
            bound_credentials(home, key, password)
        finally:
            tasks = {task for task in (plugin._control_task, plugin._stop_task, plugin._status_task) if task is not None and not task.done()}
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for process in tuple(plugin._children):
                await plugin._stop_child(process, 0.4)
            if plugin._cleanup_tasks:
                await asyncio.gather(*tuple(plugin._cleanup_tasks), return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_zip", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path, help="New private evidence directory outside the checkout")
    args = parser.parse_args()
    os.umask(0o077)
    require("execution uses an actual normal user", os.getuid() == os.geteuid() != 0)
    require("qualification revision is explicit", re.fullmatch(r"[0-9a-f]{40}", args.revision) is not None)
    output = args.output.absolute()
    require("evidence directory is new", not output.exists() and not output.is_symlink() and ".." not in output.parts)
    checkout = Path(__file__).resolve().parents[2]
    require("evidence stays outside the checkout", not output.is_relative_to(checkout) and not checkout.is_relative_to(output))
    for parent in (output.parent, *output.parent.parents):
        info = parent.lstat()
        require("evidence ancestors are protected", stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                info.st_uid in (0, os.getuid()) and (not info.st_mode & 0o022 or bool(info.st_mode & stat.S_ISVTX)))
    require("evidence parent belongs to the test user", output.parent.stat().st_uid == os.getuid())
    output.mkdir(mode=0o700)
    receipt = {"schema": "obsgod.packaged-settings-boundary/v1", "revision": args.revision,
               "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "status": "failed",
               "platform": platform.platform(), "python": platform.python_version(), "uid": os.getuid(),
               "harness_sha256": digest(Path(__file__).read_bytes()), "checks": CHECKS,
               "limits": ["Actual packaged Python and Go with real locks/children; synthetic HOME/Decky paths.",
                          "No real loader RPC transport, SteamOS, OBS/Flatpak launch, controller, audio or provider qualification."]}
    started = time.monotonic()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.3)
            require("managed control port is unused", probe.connect_ex(("127.0.0.1", 4457)) != 0)
        archive_data = args.plugin_zip.read_bytes()
        receipt["zip_sha256"] = digest(archive_data)
        receipt["zip_bytes"] = len(archive_data)
        with tempfile.TemporaryDirectory(prefix="packaged-settings-", dir="/tmp") as temporary:
            fixture = Path(temporary)
            home = fixture / "home"
            home.mkdir(mode=0o700)
            plugins = home / "homebrew/plugins"
            plugins.mkdir(parents=True, mode=0o700)
            with zipfile.ZipFile(args.plugin_zip) as archive:
                names = archive.namelist()
                require("ZIP has unique safe plugin paths", len(names) == len(set(names)) and all(
                    name.startswith("obsgod/") and "\\" not in name and not PurePosixPath(name).is_absolute() and
                    ".." not in PurePosixPath(name).parts and str(PurePosixPath(name)) == name for name in names))
                require("ZIP extraction has a bounded total size", sum(member.file_size for member in archive.infolist()) <= 128 * 1024 * 1024)
                for member in archive.infolist():
                    require("ZIP entries are unencrypted regular files", not member.flag_bits & 1 and stat.S_ISREG(member.external_attr >> 16))
                    target = plugins / member.filename
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    target.write_bytes(archive.read(member))
                    target.chmod(0o700 if member.filename.startswith("obsgod/bin/") else 0o600)
            plugin_root = plugins / "obsgod"
            manifest = json.loads((plugin_root / "manifest.json").read_text())
            require("ZIP declares exact clean qualification source", manifest.get("revision") == args.revision and manifest.get("dirty") is False)
            files = manifest.get("files")
            require("manifest payload inventory is bounded and safe", isinstance(files, dict) and 0 < len(files) <= 100 and all(
                isinstance(name, str) and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and
                "\\" not in name and str(PurePosixPath(name)) == name and isinstance(value, str) and
                re.fullmatch(r"[0-9a-f]{64}", value) for name, value in files.items()))
            require("every manifest payload matches packaged bytes", all(digest((plugin_root / name).read_bytes()) == value for name, value in files.items()))
            receipt["payload_sha256"] = {name: digest((plugin_root / name).read_bytes()) for name in ("main.py", "storage.py", "dependency_setup.py", "bin/obsgod")}
            asyncio.run(exercise(plugin_root, home, fixture))
        receipt["status"] = "passed"
    except Exception as error:
        receipt["failure"] = {"check": STEP, "type": type(error).__name__}
    receipt["seconds"] = round(time.monotonic() - started, 3)
    receipt["guarded_child_count"] = len(SPAWNS)
    receipt["action_counts"] = dict(Counter(row["action"] for row in SPAWNS))
    encoded = json.dumps(receipt, indent=2, sort_keys=True)
    require("receipt contains no synthetic credential", not any(secret in encoded for secret in PRIVATE))
    (output / "receipt.json").write_text(encoded + "\n")
    print("Packaged settings boundary:", receipt["status"], "cases:", len(CHECKS))
    if receipt["status"] != "passed":
        print("Failed safe check:", receipt["failure"]["check"])
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
