#!/usr/bin/env python3
"""Review and remove Decky Stream, reset settings, or wipe its owned data."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

def _sibling(name):
    spec = importlib.util.spec_from_file_location("obsgod_remove_" + name, Path(__file__).resolve().parent / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_cli = _sibling("bridge").run_cli
_paths = _sibling("paths")
app_directories, xdg_root, decky_locations = _paths.app_directories, _paths.xdg_root, _paths.decky_locations
DISPLAY_NAME = _sibling("product").DISPLAY_NAME if (Path(__file__).resolve().parent / "product.py").is_file() else "OBSGod"

RECORDING = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}(?:_\d+)?\.mkv\Z")


class RemovalError(RuntimeError):
    def __init__(self, message, completed=(), remaining=()):
        super().__init__(message)
        self.completed = list(completed)
        self.remaining = list(remaining)


def exists(path):
    return path.exists() or path.is_symlink()


def validate_path(path, home, *, current=False, tree=False):
    """Never traverse a symlink or remove a foreign-owned or shared root."""
    try:
        path = _paths.normalize_home_path(path, home)
        _paths.validate_directory_ancestry(path.parent, home)
    except ValueError as error:
        raise RemovalError(str(error)) from None
    if not exists(path):
        return path
    info = path.lstat()
    if info.st_uid != os.getuid():
        raise RemovalError("Refusing data owned by another user: " + str(path))
    if path.is_symlink():
        if current and path.name == "current" and path.resolve().parent == (path.parent / "releases").resolve():
            return path
        raise RemovalError("Refusing a symlinked removal path: " + str(path))
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise RemovalError("Refusing a special file: " + str(path))
    if stat.S_ISDIR(info.st_mode):
        try:
            _paths.validate_directory_ancestry(path, home)
        except ValueError as error:
            raise RemovalError(str(error)) from None
    if tree and path.is_dir():
        for directory, names, files in os.walk(path, followlinks=False):
            for name in names + files:
                child = Path(directory) / name
                allowed_current = child == path / "current" and path.name == "obsgod"
                validate_path(child, home, current=allowed_current)
    return path


def _identity(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    value = [info.st_dev, info.st_ino, info.st_mode, info.st_uid]
    if not stat.S_ISDIR(info.st_mode):
        value.extend([info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns])
    if stat.S_ISLNK(info.st_mode):
        value.append(str(path.readlink()))
    return value


def _retained_names(path, plan):
    names = set()
    if path == Path(plan["base"]):
        names.update(("install.lock", "update.lock"))
    if path == Path(plan["state"]):
        names.add("control.lock")
    return names


def _entry_identity(entry, plan):
    path = Path(entry["path"])
    nodes = [[".", _identity(path)]]
    if path.is_dir() and not path.is_symlink() and entry["kind"] in {"tree", "state", "application"}:
        retained = _retained_names(path, plan)
        for directory, names, files in os.walk(path, followlinks=False):
            if Path(directory) == path:
                names[:] = [name for name in names if name not in retained]
                files = [name for name in files if name not in retained]
            for name in sorted(names + files):
                child = Path(directory) / name
                nodes.append([str(child.relative_to(path)), _identity(child)])
    return sorted(nodes, key=lambda value: value[0])


def _check_preview(plan, home, entries=None, *, coordination_created=False):
    for name, identity in plan["ancestors"].items():
        path = Path(name)
        if path.is_relative_to(home.resolve()):
            _paths.validate_directory_ancestry(path, home)
        if _identity(path) != identity:
            raise RemovalError("A removal parent changed; review the inventory again: " + name)
    for name, identity in plan.get("locks", {}).items():
        info = Path(name).lstat()
        actual = [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink]
        if actual != identity:
            raise RemovalError("An operation lock changed; review the inventory again: " + name)
    for entry in plan["entries"] if entries is None else entries:
        path = Path(entry["path"])
        if entry["kind"] == "alias":
            _paths.validate_directory_ancestry(path.parent, home)
        else:
            validate_path(path, home, current=entry["kind"] == "current",
                          tree=entry["kind"] in {"tree", "state", "application"})
        actual = _entry_identity(entry, plan)
        expected = entry["identity"]
        # Creating only coordination files in a previously absent namespace is
        # our own lock acquisition, never permission to delete newly found data.
        created = (coordination_created and _retained_names(path, plan) and
                   expected == [[".", None]] and len(actual) == 1 and
                   actual[0][1] is not None)
        if actual != expected and not created:
            raise RemovalError("A selected path changed; review the inventory again: " + str(path))


def _pin_coordination(plan, locks):
    """Own-created namespaces get exact identities before any external helper."""
    pinned = {**plan, "ancestors": dict(plan["ancestors"]),
              "entries": [dict(entry) for entry in plan["entries"]], "locks": locks}
    for root in (Path(plan["base"]), Path(plan["state"])):
        for parent in (*reversed(root.parents), root):
            pinned["ancestors"].setdefault(str(parent), _identity(parent))
    for entry in pinned["entries"]:
        path = Path(entry["path"])
        if _retained_names(path, plan) and entry["identity"] == [[".", None]]:
            entry["identity"] = [[".", _identity(path)]]
    return pinned


def _selected_child(entry, child):
    prefix = child.name + "/"
    nodes = [["." if name == child.name else name[len(prefix):], identity]
             for name, identity in entry["identity"]
             if name == child.name or name.startswith(prefix)]
    return {"path": str(child), "kind": "current" if child.name == "current" else "tree",
            "identity": nodes}


def build_plan(home, mode="uninstall", purge=False, delete_recordings=False, recordings=(), environ=None,
               legacy_app_only=False):
    if legacy_app_only and (mode != "uninstall" or purge or delete_recordings or recordings):
        raise RemovalError("Legacy app retirement cannot be combined with reset, wipe, settings or recording deletion.")
    home = home.resolve()
    base, apps = app_directories(home, environ)
    base = validate_path(base, home)
    apps = validate_path(apps, home)
    config = xdg_root("XDG_CONFIG_HOME", home, environ) / "obsgod"
    state = xdg_root("XDG_STATE_HOME", home, environ) / "obsgod"
    cache = xdg_root("XDG_CACHE_HOME", home, environ) / "obsgod"
    managed_obs = home / ".var/app/com.obsproject.Studio/config/obsgod"
    # Match the runtime's compatibility media path; never infer ownership of an
    # unrelated XDG Videos location during a product rename.
    videos = home / "Videos/OBSGod"
    decky = decky_locations(home, environ)
    decky_root = decky["plugin"].parent.parent
    pending_gates = []
    if mode == "wipe" and not decky_root.is_dir():
        pending_gates.append("Decky's root is unconfirmed. Set DECKY_HOME to the actual Decky directory, then review this inventory again before wiping adapter data.")
    entries = []
    preserved = [str(videos) + " (unselected files)", "Decky Loader", "ordinary OBS profiles", "OBS/GStreamer shared Flatpaks"]
    if mode == "reset":
        preserved.append(str(base) + " (app and rollback backups; backups may contain saved credentials)")

    def add(path, label, kind="tree", include_missing=False):
        path = validate_path(path, home, current=kind == "current", tree=kind in {"tree", "state", "application"})
        if exists(path) or include_missing:
            entries.append({"path": str(path), "label": label, "kind": kind})

    if mode != "reset":
        executable = home / ".local/bin/obsgod"
        if executable.is_symlink() and executable.readlink() == base / "current/obsgod":
            for parent in [executable.parent, executable.parent.parent]:
                validate_path(parent, home)
            if executable.lstat().st_uid != os.getuid():
                raise RemovalError("The installed command alias belongs to another user")
            entries.append({"path": str(executable), "label": "Managed command alias", "kind": "alias"})
        elif exists(executable):
            preserved.append(str(executable) + " (unrelated command)")
        for name in ["obsgod-setup.desktop", "obsgod-update.desktop", "obsgod-uninstall.desktop"]:
            shortcut = apps / name
            validate_path(shortcut, home)
            if shortcut.is_file():
                if shortcut.stat().st_size > 64 * 1024:
                    raise RemovalError("An application shortcut is unexpectedly large")
                if "X-OBSGod-Managed=true" in shortcut.read_text():
                    add(shortcut, "Managed Desktop shortcut", "file")
                else:
                    preserved.append(str(shortcut) + " (unrelated shortcut)")
        if mode == "wipe":
            add(base, "Application, releases, rollback backups and updater records (coordination locks retained)", "application", include_missing=True)
        else:
            add(base / "current", "Active release link", "current")
            add(base / "releases", "Installed releases")
            preserved.append(str(base / "backups") + " (may contain saved credentials)")
    if mode in {"reset", "wipe"} or purge:
        add(config, "Settings, stream key and control password")
        add(managed_obs, "Isolated managed OBS profiles")
    else:
        preserved.extend([str(config), str(managed_obs)])
    if mode in {"reset", "wipe"}:
        add(state, "Runtime state and diagnostic history (control lock retained)", "state", include_missing=True)
        add(cache, "Owned cache")
        if mode == "wipe":
            for name in ["settings", "data", "logs"]:
                add(decky[name], "Decky adapter " + name)
    else:
        preserved.extend([str(state), str(cache)])
    if mode != "wipe":
        preserved.extend(str(decky[name]) + " (Decky adapter " + name + ")" for name in ["settings", "data", "logs"])
    # Every filename is listed before confirmation. Automatic selection recognizes
    # OBS-generated names only; unusual files need an explicit --recording.
    selected = set()
    if delete_recordings and exists(videos):
        validate_path(videos, home)
        selected.update(path for path in videos.iterdir() if RECORDING.fullmatch(path.name))
    for value in recordings:
        path = Path(value)
        if not path.is_absolute() or path.parent != videos or path.suffix.lower() != ".mkv":
            raise RemovalError("Select an absolute MKV path inside " + str(videos))
        selected.add(path)
    for path in sorted(selected):
        validate_path(path, home)
        if exists(path) and not path.is_file():
            raise RemovalError("A selected recording is not a regular file")
        add(path, "Explicitly selected recording", "file")
    state = validate_path(state, home)
    preserved.extend([str(base / "update.lock") + " (stable updater coordination lock)",
                      str(base / "install.lock") + " (stable installation coordination lock)",
                      str(state / "control.lock") + " (stable control coordination lock)"])
    if legacy_app_only:
        preserved.append(str(decky["plugin"]) + " (active Decky plugin)")
    plan = {"mode": mode, "legacy_app_only": legacy_app_only,
            "remove_plugin": mode != "reset" and not legacy_app_only, "entries": entries,
            "preserved": preserved, "base": str(base), "state": str(state), "plugin_directory": str(decky["plugin"]),
            "decky_root": str(decky_root), "pending_gates": pending_gates}
    unique = {}
    for entry in entries:
        if entry["path"] in unique:
            unique[entry["path"]]["label"] += "; " + entry["label"]
        else:
            unique[entry["path"]] = entry
    entries[:] = unique.values()
    # Coordination roots may coincide for custom XDG layouts, but a selected
    # parent must never recursively erase another retained lock namespace.
    for entry in entries:
        path = Path(entry["path"])
        for root in (base, state):
            if root != path and root.is_relative_to(path):
                raise RemovalError("A selected path contains a coordination namespace; choose separate XDG roots.")
        entry["identity"] = _entry_identity(entry, plan)
    ancestors = {}
    for path in [base, state] + [Path(entry["path"]).parent for entry in entries]:
        _paths.validate_directory_ancestry(path, home)
        for parent in (*reversed(path.parents), path):
            if exists(parent):
                ancestors[str(parent)] = _identity(parent)
    # Selected roots are checked by their entry identity; their contents change
    # as the approved plan proceeds, while their directory inode stays fixed.
    plan["ancestors"] = ancestors
    return plan


def require_idle():
    result = run_cli("status", timeout=6)
    if not isinstance(result, dict):
        raise RemovalError("Output state could not be read; inspect OBS first")
    stream = result.get("stream")
    recording = result.get("recording")
    recording_active = recording.get("active") if isinstance(recording, dict) else recording
    recording_paused = recording.get("paused", False) if isinstance(recording, dict) else False
    recording_valid = isinstance(recording_active, bool)
    media = result.get("media")
    media_recording = media.get("recording") if isinstance(media, dict) else None
    nested_idle = (isinstance(media_recording, dict) and media_recording.get("active") is False
                   and media_recording.get("paused") is False)
    media_idle = (isinstance(media, dict) and media.get("known") is True
                  and media.get("replay_active") is False and nested_idle)
    legacy_absent = media is None and result.get("process") == "absent"
    if (result.get("ok") is not True or result.get("state") not in ("stopped", "setup")
            or not isinstance(stream, dict) or stream.get("active") is not False
            or stream.get("reconnecting", False) is not False
            or not recording_valid or recording_active or recording_paused is not False
            or result.get("output_known") is not True
            or not (media_idle or legacy_absent)
            or result.get("process") not in ("absent", "running")
            or result.get("operation") not in (None, "", "idle")):
        raise RemovalError("Removal blocked: OBS output is active, recording, replaying, busy or unconfirmed. Stop/cancel and confirm idle before retrying; close managed OBS when upgrading from an older app.")
    return result


@contextmanager
def removal_lock(path, home=None):
    home = Path.home() if home is None else home
    _paths.validate_owned_root(path.parent, home)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _paths.validate_owned_root(path.parent, home)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_nlink != 1 or info.st_mode & 0o077):
            raise RemovalError("The operation lock has unsafe type, ownership or permissions")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RemovalError("Another installation or OBS control operation is busy. Let it finish before removal.") from None
        named = path.lstat()
        if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
            raise RemovalError("The operation lock changed; review the inventory again")
        yield [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink]


def remove_plugin(home, directory=None):
    # Use Decky's existing authenticated frontend, never raw-delete root-owned
    # plugin files or restart the shared Decky service.
    decky = _sibling("decky")
    known = Path(directory) if directory is not None else decky_locations(home)["plugin"]
    if exists(known):
        metadata = known / "plugin.json"
        if known.is_symlink() or metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 64 * 1024:
            raise RemovalError("The remaining plugin directory could not be identified safely; inspect Decky before retrying.")
        saved = json.loads(metadata.read_text())
        if not isinstance(saved, dict) or saved.get("name") != "OBSGod":
            raise RemovalError("The remaining plugin directory has an unexpected identity; inspect Decky before retrying.")
    result = decky.helper_request("uninstall", uninstall_existing=exists(known))
    if result.get("removed") is not True:
        raise RemovalError("Decky plugin removal is unconfirmed; application files were preserved")
    # Decky3.3.1 can swallow a filesystem-removal exception after unloading.
    if exists(known):
        raise RemovalError("Decky unloaded the plugin but its files remain. Inspect Decky and retry; application files were preserved.")


def apply_plan(plan, home):
    if plan.get("pending_gates"):
        raise RemovalError(" ".join(plan["pending_gates"]))
    base, state_path = Path(plan["base"]), Path(plan["state"])
    completed = []
    try:
        _check_preview(plan, home)
        state = require_idle()
        if plan.get("legacy_app_only"):
            if state.get("process") != "absent":
                raise RemovalError("Close managed OBS explicitly through Decky before retiring the legacy app.")
        elif state.get("configured") or state.get("process") not in (None, "absent"):
            closed = run_cli("restart", timeout=20)
            if not isinstance(closed, dict) or closed.get("ok") is not True:
                raise RemovalError("Idle managed OBS could not be closed safely. Inspect Desktop OBS and retry.")
        require_idle()
        # Match the updater's update -> install -> control acquisition order.
        # These names remain after every removal so already-open waiters and
        # later controllers always use the same kernel lock generation.
        with removal_lock(base / "update.lock", home) as updater, removal_lock(base / "install.lock", home) as installer, removal_lock(state_path / "control.lock", home) as controller:
            _check_preview(plan, home, coordination_created=True)
            pinned = _pin_coordination(plan, {str(base / "update.lock"): updater,
                                             str(base / "install.lock"): installer,
                                             str(state_path / "control.lock"): controller})
            _check_preview(pinned, home)
            current = require_idle()
            if current.get("process") != "absent":
                raise RemovalError("Managed OBS restarted during removal. Close it and review the inventory before retrying.")
            if plan["remove_plugin"]:
                remove_plugin(home, plan["plugin_directory"])
            _check_preview(pinned, home)
            for entry in pinned["entries"]:
                _check_preview(pinned, home, [entry])
                path = Path(entry["path"])
                if not exists(path):
                    continue
                retained = _retained_names(path, plan)
                if retained:
                    for child in sorted(path.iterdir()):
                        if child.name not in retained:
                            _check_preview(pinned, home, [_selected_child(entry, child)])
                            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
                            _check_preview(pinned, home, [])
                elif path.is_symlink() or path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                completed.append(str(path))
            _check_preview(pinned, home, [])
    except (OSError, ValueError, RemovalError, KeyboardInterrupt, EOFError) as error:
        remaining = [entry["path"] for entry in plan["entries"] if entry["path"] not in completed and exists(Path(entry["path"]))]
        interrupted = isinstance(error, (KeyboardInterrupt, EOFError))
        message = ("Removal interrupted" if interrupted else "Removal stopped") + " after " + str(len(completed)) + " selected paths. Review remaining files and rerun --dry-run; a partial removal may have occurred."
        if not interrupted:
            message += " " + str(error)
        raise RemovalError(message, completed, remaining) from None
    return completed


def describe(plan):
    scope = "legacy app retirement" if plan.get("legacy_app_only") else plan["mode"]
    lines = [DISPLAY_NAME + " — " + scope + " inventory", ""]
    if plan["remove_plugin"]:
        lines.append("Remove the OBSGod compatibility plugin through Decky at " + plan["plugin_directory"] + ".")
    lines.append("Decky adapter inventory root: " + plan["decky_root"] + ". For a nonstandard installation, set DECKY_HOME before reviewing this plan.")
    lines.extend(entry["label"] + ": " + entry["path"] for entry in plan["entries"])
    if not plan["entries"]:
        lines.append("No selected application/data paths currently exist.")
    lines.extend(["", "Preserve:"] + plan["preserved"])
    if plan.get("pending_gates"):
        lines.extend(["", "Resolve before removal:"] + plan["pending_gates"])
    lines.append("\nSelected deletions cannot be undone. OBS / GStreamer and Decky remain installed.")
    return "\n".join(lines)


def confirm(plan):
    message = describe(plan)
    if shutil.which("kdialog"):
        return subprocess.run(["kdialog", "--title", DISPLAY_NAME, "--warningyesno", message], check=False).returncode == 0
    if shutil.which("zenity"):
        return subprocess.run(["zenity", "--question", "--title=" + DISPLAY_NAME, "--text=" + message], check=False).returncode == 0
    if sys.stdin.isatty():
        return input("\nType REMOVE to apply this inventory, or press Enter to cancel: ") == "REMOVE"
    raise RemovalError("Confirmation is required. Use the Desktop launcher, an interactive terminal, or --yes after reviewing --dry-run.")


def choose_mode():
    """The no-argument Desktop launcher offers the three removal scopes first."""
    if shutil.which("kdialog"):
        result = subprocess.run(["kdialog", "--title", DISPLAY_NAME, "--radiolist", "Choose an action. Recordings are retained unless separately selected using the command-line options.",
                                 "uninstall", "Uninstall app and plugin; keep settings and recordings", "on",
                                 "reset", "Reset settings, private keys and history; keep app/plugin", "off",
                                 "wipe", "Uninstall and wipe owned data/backups; keep recordings", "off"],
                                capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() in {"uninstall", "reset", "wipe"} else None
    if sys.stdin.isatty():
        print("1. Uninstall app/plugin; keep settings and recordings\n2. Reset settings/history; keep app/plugin\n3. Uninstall and wipe owned data/backups; keep recordings")
        return {"1": "uninstall", "2": "reset", "3": "wipe"}.get(input("Choose 1–3, or press Enter to cancel: "))
    return "uninstall"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reset", action="store_true", help="Reset settings/credentials/isolated OBS/state/cache; retain installed app/plugin")
    mode.add_argument("--wipe", action="store_true", help="Uninstall and wipe owned app/settings/state/cache/rollback backups; media is separately selected")
    mode.add_argument("--purge-settings", action="store_true", help="Legacy uninstall plus settings/isolated OBS removal; history/backups remain")
    parser.add_argument("--dry-run", action="store_true", help="Print inventory without changing files or contacting OBS/Decky")
    parser.add_argument("--json", action="store_true", help="Machine-readable inventory/result")
    parser.add_argument("--yes", action="store_true", help="Apply the reviewed inventory without prompting")
    parser.add_argument("--legacy-app-only", action="store_true", help="Retire only the old Desktop app and launchers; preserve the Decky plugin and shared user data")
    parser.add_argument("--delete-recordings", action="store_true", help="Also delete standard date-named OBS MKVs in Videos/OBSGod; preview with --dry-run")
    parser.add_argument("--recording", action="append", default=[], metavar="PATH", help="Also delete this explicitly selected MKV in Videos/OBSGod (repeatable)")
    args = parser.parse_args(argv)
    try:
        if os.getuid() == 0:
            raise RemovalError("Run without sudo as your normal Deck user")
        home = Path.home().resolve()
        selected_mode = "reset" if args.reset else "wipe" if args.wipe else "uninstall"
        if argv is None and len(sys.argv) == 1:
            selected_mode = choose_mode()
            if selected_mode is None:
                print("Cancelled; no selected files were removed.")
                return 0
        plan = build_plan(home, selected_mode,
                          args.purge_settings, args.delete_recordings, args.recording,
                          legacy_app_only=args.legacy_app_only)
        if args.dry_run:
            print(json.dumps({"ok": True, "dry_run": True, **plan}) if args.json else describe(plan))
            return 0
        if not args.json:
            print(describe(plan), flush=True)
        if not args.yes and not confirm(plan):
            print(json.dumps({"ok": True, "cancelled": True}) if args.json else "Cancelled; no selected files were removed.")
            return 0
        completed = apply_plan(plan, home)
        message = DISPLAY_NAME + (" legacy app retired; Decky plugin and shared user data preserved." if args.legacy_app_only else
                                  " settings reset." if selected_mode == "reset" else " removal completed.") + " Shared dependencies and unselected recordings were preserved. Stable coordination locks were retained."
        print(json.dumps({"ok": True, "mode": plan["mode"], "removed": completed, "message": message}) if args.json else message)
        return 0
    except (OSError, ValueError, RemovalError, RuntimeError) as error:
        message = str(error)
        print(json.dumps({"ok": False, "message": message,
                          "removed": getattr(error, "completed", []),
                          "remaining": getattr(error, "remaining", [])}) if args.json else "Removal failed: " + message)
        return 1
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"ok": False, "message": "Removal interrupted; rerun --dry-run to inspect remaining data."}) if args.json else "Removal interrupted; rerun --dry-run to inspect remaining data.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
