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
    pass


def exists(path):
    return path.exists() or path.is_symlink()


def validate_path(path, home, *, current=False, tree=False):
    """Never traverse a symlink or remove a foreign-owned or shared root."""
    home = home.resolve()
    home_boundary = Path(os.environ.get("HOME", str(home)))
    if home_boundary.resolve() != home:
        home_boundary = home
    if not path.is_absolute() or path.resolve() == home or ".." in path.parts or not path.resolve().is_relative_to(home):
        raise RemovalError("Refusing an owned-data path outside your home directory")
    for parent in reversed(path.parents):
        if parent in (home, home_boundary) or not parent.resolve().is_relative_to(home):
            continue
        if parent.is_symlink():
            raise RemovalError("Refusing a symlinked parent directory: " + str(parent))
        if parent.exists() and (not parent.is_dir() or parent.stat().st_uid not in (0, os.getuid())):
            raise RemovalError("An owned-data parent has unexpected type or ownership: " + str(parent))
    if not exists(path):
        return
    info = path.lstat()
    if info.st_uid != os.getuid():
        raise RemovalError("Refusing data owned by another user: " + str(path))
    if path.is_symlink():
        if current and path.name == "current" and path.resolve().parent == (path.parent / "releases").resolve():
            return
        raise RemovalError("Refusing a symlinked removal path: " + str(path))
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise RemovalError("Refusing a special file: " + str(path))
    if tree and path.is_dir():
        for directory, names, files in os.walk(path, followlinks=False):
            for name in names + files:
                child = Path(directory) / name
                allowed_current = child == path / "current" and path.name == "obsgod"
                validate_path(child, home, current=allowed_current)


def build_plan(home, mode="uninstall", purge=False, delete_recordings=False, recordings=(), environ=None):
    home = home.resolve()
    base, apps = app_directories(home, environ)
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
        preserved.extend([str(base) + " (app and rollback backups; backups may contain saved credentials)", str(state / "control.lock") + " (operation lock)"])

    def add(path, label, kind="tree", include_missing=False):
        validate_path(path, home, current=kind == "current", tree=kind in {"tree", "state"})
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
            add(base, "Application, releases, rollback backups and updater records", include_missing=True)
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
        add(state, "Runtime state and diagnostic history", "state" if mode == "reset" else "tree", include_missing=True)
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
    return {"mode": mode, "remove_plugin": mode != "reset", "entries": entries,
            "preserved": preserved, "base": str(base), "state": str(state), "plugin_directory": str(decky["plugin"]),
            "decky_root": str(decky_root), "pending_gates": pending_gates}


def require_idle():
    result = run_cli("status", timeout=6)
    if not isinstance(result, dict):
        raise RemovalError("Output state could not be read; inspect OBS first")
    stream = result.get("stream")
    recording = result.get("recording")
    recording_active = recording.get("active") if isinstance(recording, dict) else recording
    recording_valid = isinstance(recording_active, bool)
    if (result.get("ok") is not True or result.get("state") not in ("stopped", "setup")
            or not isinstance(stream, dict) or stream.get("active") is not False
            or not recording_valid or recording_active or result.get("output_known") is not True
            or result.get("process") not in ("absent", "running")
            or result.get("operation") not in (None, "", "idle")):
        raise RemovalError("Removal blocked: OBS output is active, recording, busy or unconfirmed. Stop/cancel and confirm idle before retrying.")
    return result


@contextmanager
def removal_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        if os.fstat(handle.fileno()).st_uid != os.getuid():
            raise RemovalError("The operation lock belongs to another user")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RemovalError("Another installation or OBS control operation is busy. Let it finish before removal.") from None
        yield


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
    state = require_idle()
    if state.get("configured") or state.get("process") not in (None, "absent"):
        closed = run_cli("restart", timeout=20)
        if not isinstance(closed, dict) or closed.get("ok") is not True:
            raise RemovalError("Idle managed OBS could not be closed safely. Inspect Desktop OBS and retry.")
    require_idle()
    base, state_path = Path(plan["base"]), Path(plan["state"])
    validate_path(base, home)
    validate_path(state_path, home)
    new_locks = [(base, "install.lock", not exists(base)), (state_path, "control.lock", not exists(state_path))]
    completed = []
    try:
        with removal_lock(base / "install.lock"), removal_lock(state_path / "control.lock"):
            current = require_idle()
            if current.get("process") != "absent":
                raise RemovalError("Managed OBS restarted during removal. Close it and review the inventory before retrying.")
            for entry in plan["entries"]:
                path = Path(entry["path"])
                if entry["kind"] == "alias":
                    if not path.is_symlink() or path.readlink() != base / "current/obsgod":
                        raise RemovalError("The command alias changed; review the inventory again")
                else:
                    validate_path(path, home, current=entry["kind"] == "current", tree=entry["kind"] in {"tree", "state"})
            if plan["remove_plugin"]:
                remove_plugin(home, plan["plugin_directory"])
            for entry in plan["entries"]:
                path = Path(entry["path"])
                if not exists(path):
                    continue
                if entry["kind"] == "state":
                    # Keep the held lock inode until reset completes.
                    for child in path.iterdir():
                        if child.name != "control.lock":
                            shutil.rmtree(child) if child.is_dir() else child.unlink()
                elif path.is_symlink() or path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                completed.append(str(path))
            # A fresh/partial removal should not leave newly-created namespaces
            # containing only this operation's locks. All selected changes are
            # finished before these lock names are unlinked.
            for directory, name, created in new_locks:
                if created and directory.is_dir() and list(directory.iterdir()) == [directory / name]:
                    (directory / name).unlink()
                    directory.rmdir()
    except (OSError, RemovalError) as error:
        message = "Removal stopped after " + str(len(completed)) + " selected paths. Review remaining files and rerun --dry-run; a partial removal may have occurred."
        raise RemovalError(message) from error
    return completed


def describe(plan):
    lines = [DISPLAY_NAME + " — " + plan["mode"] + " inventory", ""]
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
                          args.purge_settings, args.delete_recordings, args.recording)
        if args.dry_run:
            print(json.dumps({"ok": True, "dry_run": True, **plan}) if args.json else describe(plan))
            return 0
        if not args.json:
            print(describe(plan), flush=True)
        if not args.yes and not confirm(plan):
            print(json.dumps({"ok": True, "cancelled": True}) if args.json else "Cancelled; no selected files were removed.")
            return 0
        completed = apply_plan(plan, home)
        message = DISPLAY_NAME + (" settings reset." if selected_mode == "reset" else " removal completed.") + " Shared dependencies and unselected recordings were preserved."
        print(json.dumps({"ok": True, "mode": plan["mode"], "removed": completed, "message": message}) if args.json else message)
        return 0
    except (OSError, ValueError, RemovalError, RuntimeError) as error:
        message = str(error)
        print(json.dumps({"ok": False, "message": message}) if args.json else "Removal failed: " + message)
        return 1
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"ok": False, "message": "Removal interrupted; rerun --dry-run to inspect remaining data."}) if args.json else "Removal interrupted; rerun --dry-run to inspect remaining data.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
