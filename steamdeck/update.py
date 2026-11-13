#!/usr/bin/env python3
"""Check official OBSGod releases and explicitly apply an idle Desktop update."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
def _sibling(name):
    spec = importlib.util.spec_from_file_location("obsgod_update_" + name, Path(__file__).resolve().parent / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_paths = _sibling("paths")
app_directories, xdg_root, validate_owned_root = _paths.app_directories, _paths.xdg_root, _paths.validate_owned_root

ROOT = Path(__file__).resolve().parent
MAX_ARCHIVE = 64 * 1024 * 1024


class UpdateError(RuntimeError):
    pass


def private_directory(path, home):
    try:
        validate_owned_root(path, home)
    except ValueError as error:
        raise UpdateError(str(error) + ". Existing files were preserved.") from None
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise UpdateError("An install directory is unsafe. Existing files were preserved.")


def verify_bundle():
    saved = ROOT / "manifest.json"
    if saved.is_symlink() or not saved.is_file() or saved.stat().st_size > 64 * 1024:
        raise UpdateError("Extract the entire OBSGod archive first, then open Update OBSGod.desktop inside that folder.")
    manifest = json.loads(saved.read_text())
    if not isinstance(manifest, dict):
        raise UpdateError("The updater manifest is invalid. Extract a fresh complete archive.")
    files = manifest.get("files")
    required = {"update.py", "releases.py", "Update OBSGod.desktop", "Update OBSGod.sh"}
    if not isinstance(files, dict) or not required.issubset(files) or len(files) > 64 or manifest.get("platform") != "linux/amd64":
        raise UpdateError("The updater package is incomplete. Extract a fresh complete archive.")
    for name, digest in files.items():
        if not isinstance(name, str) or name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,180}", name) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise UpdateError("The updater manifest contains an unsafe filename or checksum.")
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise UpdateError("Updater checksum verification failed. Extract a fresh complete archive.")
    return manifest


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release_module():
    return load_module("obsgod_release_metadata", ROOT / "releases.py")


def installed_release(home):
    base, _ = app_directories(home)
    current = base / "current"
    if not current.exists() and not current.is_symlink():
        return None, {"version": "0.0.0", "updater_version": "not-installed"}
    if not current.is_symlink() or current.resolve().parent != (base / "releases").resolve() or not current.resolve().is_relative_to(home.resolve()):
        raise UpdateError("The installed release path is unsafe. Existing files were preserved.")
    saved = current / "manifest.json"
    if saved.is_symlink() or not saved.is_file() or saved.stat().st_size > 64 * 1024:
        raise UpdateError("The installed manifest is unavailable. Use the complete installer to repair the current version.")
    manifest = json.loads(saved.read_text())
    if not isinstance(manifest, dict) or not isinstance(manifest.get("version"), str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", manifest["version"]):
        raise UpdateError("The installed manifest is invalid. Use the complete installer to repair the current version.")
    return current, manifest


def check(channel="preview"):
    verify_bundle()
    _, installed = installed_release(Path.home())
    result = release_module().check_updates(installed.get("version", "unknown"), channel)
    result["current_updater_version"] = installed.get("updater_version", "not-bundled")
    return result


def unpack_payload(archive, destination, version):
    # Older SteamOS Python lacks tarfile's data filter. Validate all members
    # before copying only regular files into a new private directory.
    prefix = "OBSGod-" + version
    with tarfile.open(archive) as bundle:
        members = []
        total = 0
        for item in bundle:
            members.append(item)
            total += item.size
            if len(members) > 96 or total > 96 * 1024 * 1024:
                raise UpdateError("Invalid release archive size")
        seen = set()
        for item in members:
            parts = PurePosixPath(item.name).parts
            if not parts or parts[0] != prefix or ".." in parts or "\\" in item.name or item.name in seen or not (item.isfile() or item.isdir()) or item.name != str(PurePosixPath(item.name)):
                raise UpdateError("Unsafe release archive path")
            seen.add(item.name)
        for item in members:
            target = destination.joinpath(*PurePosixPath(item.name).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if item.isdir():
                target.mkdir(exist_ok=True, mode=0o700)
            else:
                with bundle.extractfile(item) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o700 if target.name in {"obsgod", "decky-install"} else 0o600)
    return destination / prefix


def require_idle(bridge, allow_legacy=False):
    """Modern evidence authorizes apply; legacy evidence only gates a download.

    Published previews1–4 lack output_known/recording/process. Their old check
    cannot establish recording safety. A verified new payload performs this
    strict check again before settings backup, plugin replacement or activation.
    """
    state = bridge.run_cli("status", timeout=6)
    if not isinstance(state, dict):
        raise UpdateError("Update blocked: OBS output state could not be read.")
    recording = state.get("recording", False if allow_legacy else None)
    recording_active = recording.get("active") if isinstance(recording, dict) else recording
    stream = state.get("stream")
    known = state.get("output_known", True if allow_legacy else None)
    media = state.get("media")
    media_idle = (isinstance(media, dict) and media.get("known") is True
                  and media.get("replay_active") is False)
    # A historical status can gate a download, but the verified new payload
    # repeats the strict check before any backup or installation mutation.
    legacy_download_or_absent = media is None and (allow_legacy or state.get("process") == "absent")
    if (state.get("ok") is not True or state.get("state") not in ("stopped", "setup")
            or not isinstance(stream, dict) or stream.get("active") is not False
            or not isinstance(recording_active, bool) or recording_active
            or known is not True
            or not (media_idle or legacy_download_or_absent)
            or (not allow_legacy or "process" in state) and state.get("process") not in ("absent", "running")
            or state.get("operation") not in (None, "", "idle")):
        raise UpdateError("Update blocked: OBS output is active, starting, recording or unconfirmed. Use Stop/cancel, wait for confirmed idle, then run Update OBSGod in Desktop Mode.")
    # No implicit Stop: the installer rechecks and closes only verified idle OBS.


def backup_settings(base, home):
    config = xdg_root("XDG_CONFIG_HOME", home) / "obsgod"
    if not config.resolve().is_relative_to(home.resolve()):
        raise UpdateError("The settings directory points outside your home. Existing files were preserved.")
    backup = base / "backups" / ("updater-" + str(time.time_ns()))
    for name in ["deck.json", "secrets.json"]:
        source = config / name
        if source.exists() or source.is_symlink():
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 64 * 1024:
                raise UpdateError("An existing settings file is unsafe. Existing files were preserved.")
            private_directory(backup, home)
            shutil.copyfile(source, backup / name)
            (backup / name).chmod(0o600)


def save_progress(base, values):
    path = base / "update-status.json"
    if path.is_symlink():
        raise UpdateError("The update recovery record is unsafe. Existing files were preserved.")
    descriptor, temporary = tempfile.mkstemp(prefix=".update-status-", dir=base)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(values, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def run_update(channel="preview", repair=False):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"} or os.getuid() == 0:
        raise UpdateError("Run this updater as your normal Steam Deck user in Desktop Mode, without sudo.")
    session = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" + os.environ.get("DESKTOP_SESSION", "")).lower()
    if "gamescope" in session or "steamos" in session:
        raise UpdateError("Switch to Desktop Mode before running this updater.")
    verify_bundle()
    releases = release_module()
    home = Path.home()
    base, _ = app_directories(home)
    private_directory(base, home)
    descriptor = os.open(base / "update.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError("Another OBSGod updater is running. Let it finish, then retry.") from None
        current, installed = installed_release(home)
        if current and (current / "bridge.py").is_file():
            legacy = installed.get("version") in {"0.1.0-deck.1", "0.1.0-deck.2", "0.1.0-deck.3", "0.1.0-deck.4"}
            require_idle(load_module("obsgod_installed_bridge", current / "bridge.py"), allow_legacy=legacy)
        print("1/4 Checking the official " + channel + " runtime releases…", flush=True)
        result, candidate = releases.inspect_updates(installed.get("version", "unknown"), channel)
        if not result.get("ok") or candidate is None:
            raise UpdateError(result.get("message", "No verified runtime release is available."))
        if not result["available"] and (not repair or candidate["version"] != installed.get("version")):
            return result["message"] + " Nothing was replaced."
        required = {"install.py", "decky.py", "decky-install", "update.py", "releases.py"}
        if not required.issubset(candidate["manifest"]["files"]):
            raise UpdateError("This historical runtime predates the unified installer. Open its official release page for installation instructions; your current app and plugin were not replaced.")
        progress = {"state": "downloading", "from_version": installed.get("version"), "version": candidate["version"], "revision": candidate["revision"], "channel": channel}
        save_progress(base, progress)
        try:
            with tempfile.TemporaryDirectory(prefix=".update-", dir=base) as temporary:
                work = Path(temporary)
                archive = work / "payload.tar.gz"
                print("2/4 Downloading and verifying OBSGod " + candidate["version"] + "…", flush=True)
                releases.download_archive(candidate, archive)
                package = unpack_payload(archive, work, candidate["version"])
                manifest = package / "manifest.json"
                if manifest.is_symlink() or not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != candidate["manifest_sha256"]:
                    raise UpdateError("The downloaded archive contains a different manifest. Existing files were preserved.")
                for name, digest in candidate["manifest"]["files"].items():
                    path = package / name
                    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                        raise UpdateError("The release payload checksum does not match. Existing files were preserved.")
                installer = load_module("obsgod_payload_installer", package / "install.py")
                installer.verify_payload()
                require_idle(load_module("obsgod_payload_bridge", package / "bridge.py"))
                backup_settings(base, home)
                progress["state"] = "installing"
                save_progress(base, progress)
                print("3/4 Installing the app and Decky plugin; preserving settings and key…", flush=True)
                current = installer.install(launch=False)
                if hashlib.sha256((current / "manifest.json").read_bytes()).hexdigest() != candidate["manifest_sha256"]:
                    raise UpdateError("The final app version could not be verified. Keep the recovery record and rerun the updater.")
                progress["state"] = "complete"
                save_progress(base, progress)
                print("4/4 Verified the app; unified installer confirmed the Decky plugin…", flush=True)
        except BaseException:
            progress["state"] = "interrupted-or-failed"
            save_progress(base, progress)
            raise
    return "OBSGod " + candidate["version"] + " is installed in the Desktop app and Decky. Your settings, key and media are preserved. Return to Gaming Mode and make a local test clip before broadcasting."


def show_result(message, success):
    if shutil.which("kdialog"):
        subprocess.run(["kdialog", "--title", "OBSGod updater", "--msgbox" if success else "--error", message], check=False)
    elif shutil.which("zenity"):
        subprocess.run(["zenity", "--info" if success else "--error", "--title=OBSGod updater", "--text=" + message], check=False)
    elif sys.stdin.isatty():
        print("You can close this window, or press Enter.", flush=True)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check only; never install")
    parser.add_argument("--json", action="store_true", help="machine-readable check result")
    parser.add_argument("--channel", choices=["stable", "preview"], default="preview")
    parser.add_argument("--repair", action="store_true", help="explicitly reinstall the same verified runtime")
    args = parser.parse_args()
    os.umask(0o077)
    if args.json and not args.check:
        parser.error("--json requires --check; installation is an explicit Desktop action")
    if args.check:
        try:
            result = check(args.channel)
        except (UpdateError, OSError, ValueError, KeyError):
            result = {"ok": False, "state": "error", "available": False, "message": "The updater or installed manifest could not be verified. Extract a complete installer to repair it."}
        print(json.dumps(result, sort_keys=True) if args.json else result["message"])
        return 0 if result.get("ok") else 1
    success = False
    try:
        message = run_update(args.channel, args.repair)
        success = True
    except UpdateError as error:
        message = str(error)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as error:
        message = "The updater stopped (" + type(error).__name__ + "). Your keys were not reset. Keep the recovery record and rerun the updater; the installer preserves the previous release on failure."
    except KeyboardInterrupt:
        message = "Update interrupted. Your settings were not reset. Rerun this updater to finish and verify both installations."
    except Exception as error:
        # A separately loaded release module has a distinct exception class.
        # Only its fixed, credential-free errors are safe to show directly.
        message = str(error) if type(error).__name__ == "ReleaseError" else "The update could not be confirmed. Your saved settings were not reset; keep the recovery record and rerun the updater."
    print(("DONE: " if success else "UPDATE STOPPED: ") + message, flush=True)
    show_result(message, success)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
