#!/usr/bin/env python3
"""Install or repair OBSGod and its Decky plugin, preserving private user data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import time
import fcntl
import webbrowser
from contextlib import contextmanager
def _sibling(name):
    # Published older updaters load a downloaded installer with importlib while
    # sys.path still points at the old package. Never import its old helpers.
    spec = importlib.util.spec_from_file_location("obsgod_install_" + name, Path(__file__).resolve().parent / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_paths = _sibling("paths")
app_directories, xdg_root, validate_owned_root = _paths.app_directories, _paths.xdg_root, _paths.validate_owned_root
DISPLAY_NAME = _sibling("product").DISPLAY_NAME if (Path(__file__).resolve().parent / "product.py").is_file() else "OBSGod"

ROOT = Path(__file__).resolve().parent


def owned_directory(path, home):
    try:
        validate_owned_root(path, home)
    except ValueError as error:
        raise RuntimeError(str(error)) from None
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Refusing a symlinked install directory: " + str(path))


def quote_exec(value):
    if any(c in value for c in "\r\n\x00"):
        raise RuntimeError("Unsupported character in installation path")
    value = value.replace("%", "%%")
    return '"' + value.replace("\\", "\\\\\\\\").replace('"', '\\\\"').replace("$", "\\\\$").replace("`", "\\\\`") + '"'


def verify_payload():
    if not (ROOT / "manifest.json").is_file():
        raise RuntimeError("Extract the entire OBSGod archive to a folder first, then run Install OBSGod.desktop from that extracted folder")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    version = manifest["version"]
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in version):
        raise RuntimeError("Invalid package version")
    for name, expected in manifest["files"].items():
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("Unsafe or missing package file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Package checksum mismatch: " + name)
    required = {"obsgod", "setup.py", "bridge.py", "setup.html", "setup.js", "setup.css", "uninstall.py", "obsgod-decky.zip", "LICENSE", "THIRD_PARTY_NOTICES.md", "STEAM-DECK.md"}
    unified = {"decky-install", "decky.py", "install.py", "Install OBSGod.desktop", "update.py", "releases.py", "Update OBSGod.desktop", "Update OBSGod.sh"}
    capture = {"libgstobsgodcapture.so", "CAPTURE-SOURCE.tar.gz"}
    product = {"paths.py", "product.py", "Uninstall OBSGod.desktop"}
    # Historical archives remain repairable. New native-capture archives must
    # contain the complete unified payload and both binary and preferred source;
    # accepting a single arbitrary extra file would weaken the exact schema.
    if set(manifest["files"]) not in (required, required | unified, required | unified | capture, required | unified | capture | product):
        raise RuntimeError("Unexpected package manifest")
    return manifest


@contextmanager
def installation_lock(base):
    descriptor = os.open(base / "install.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another OBSGod installer is running. Let it finish, then retry")
        yield


def matching_release(release, manifest):
    saved = release / "manifest.json"
    return not saved.is_symlink() and saved.is_file() and saved.read_bytes() == (ROOT / "manifest.json").read_bytes() and all(
        not (release / name).is_symlink() and (release / name).is_file()
        and hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest["files"].items()
    )


def require_space(base, manifest):
    # Reserve room for staging and repair; Flatpak checks its own runtime space.
    needed = sum((ROOT / name).stat().st_size for name in manifest["files"]) * 2 + 16 * 1024 * 1024
    existing = base
    while not existing.exists():
        existing = existing.parent
    if shutil.disk_usage(existing).free < needed:
        raise RuntimeError("Not enough free space for a verified installation and repair copy. Free space in your home directory and retry; no application was replaced.")


def prepare_release(releases, manifest):
    current = releases.parent / "current"
    if current.is_symlink() and current.resolve().parent == releases:
        if matching_release(current.resolve(), manifest):
            for name in manifest["files"]:
                (current / name).chmod(0o700 if name in {"obsgod", "decky-install", "Install OBSGod.desktop", "Update OBSGod.desktop", "Update OBSGod.sh", "Uninstall OBSGod.desktop"} else 0o600)
            return current.resolve()
    release = releases / manifest["version"]
    if release.exists() or release.is_symlink():
        if release.is_symlink() or not release.is_dir():
            raise RuntimeError("Unsafe existing release path")
        if matching_release(release, manifest):
            # ZIP/filesystem tools can drop mode bits. Repair a verified copy.
            for name in manifest["files"]:
                (release / name).chmod(0o700 if name in {"obsgod", "decky-install", "Install OBSGod.desktop", "Update OBSGod.desktop", "Update OBSGod.sh", "Uninstall OBSGod.desktop"} else 0o600)
            return release
        # Preserve an older/damaged copy, including files mapped by a running
        # process. A fresh directory allows repair and same-version replacement.
        release = releases / (manifest["version"] + "-" + str(time.time_ns()))
    staging = Path(tempfile.mkdtemp(prefix=".install-", dir=releases))
    try:
        for name in manifest["files"]:
            shutil.copyfile(ROOT / name, staging / name)
            (staging / name).chmod(0o700 if name in {"obsgod", "decky-install", "Install OBSGod.desktop", "Update OBSGod.desktop", "Update OBSGod.sh", "Uninstall OBSGod.desktop"} else 0o600)
        shutil.copyfile(ROOT / "manifest.json", staging / "manifest.json")
        staging.rename(release)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return release


def validate_activation_paths(base, releases, bin_dir, apps, manifest):
    current = base / "current"
    if current.exists() or current.is_symlink():
        if not current.is_symlink() or not current.resolve().is_relative_to(releases):
            raise RuntimeError("OBSGod current path is not an owned release link")
    executable = bin_dir / "obsgod"
    desktop = apps / "obsgod-setup.desktop"
    updater_desktop = apps / "obsgod-update.desktop" if "update.py" in manifest["files"] else None
    uninstaller_desktop = apps / "obsgod-uninstall.desktop" if "Uninstall OBSGod.desktop" in manifest["files"] else None
    for path in [executable, desktop] + [item for item in [updater_desktop, uninstaller_desktop] if item]:
        if path.exists() and not (path.is_file() or path.is_symlink()):
            raise RuntimeError("Refusing to replace a non-file application entry")


def activate_release(base, releases, bin_dir, apps, home, manifest):
    validate_activation_paths(base, releases, bin_dir, apps, manifest)
    current = base / "current"
    executable = bin_dir / "obsgod"
    desktop = apps / "obsgod-setup.desktop"
    updater_desktop = apps / "obsgod-update.desktop" if "update.py" in manifest["files"] else None
    uninstaller_desktop = apps / "obsgod-uninstall.desktop" if "Uninstall OBSGod.desktop" in manifest["files"] else None
    release = prepare_release(releases, manifest)
    launch_code = "import subprocess,sys; result=subprocess.run([sys.executable,sys.argv[1]]); input('Press Enter to close this window.'); sys.exit(result.returncode)"
    content = "[Desktop Entry]\nType=Application\nName=" + DISPLAY_NAME + " Setup\nComment=Configure Steam Deck streaming locally\nExec=python3 -c " + quote_exec(launch_code) + " " + quote_exec(str(current / "setup.py")) + "\nIcon=video-display\nTerminal=true\nCategories=AudioVideo;\nX-OBSGod-Managed=true\n"
    backup = base / "backups" / str(time.time_ns())
    changes = []
    # Each entry is replaced atomically. Switch current last: any failure before
    # activation restores the old entry points and leaves the old release live.
    with tempfile.TemporaryDirectory(prefix=".activate-", dir=base) as temporary:
        staging = Path(temporary)
        (staging / "executable").symlink_to(current / "obsgod")
        (staging / "desktop").write_text(content)
        (staging / "desktop").chmod(0o600)
        (staging / "current").symlink_to(release)
        entries = [(staging / "executable", executable), (staging / "desktop", desktop)]
        if updater_desktop:
            updater_content = "[Desktop Entry]\nType=Application\nName=Update " + DISPLAY_NAME + "\nComment=Check and apply verified updates\nExec=python3 -c " + quote_exec(launch_code) + " " + quote_exec(str(current / "update.py")) + "\nIcon=system-software-update\nTerminal=true\nCategories=AudioVideo;\nX-OBSGod-Managed=true\n"
            (staging / "updater-desktop").write_text(updater_content)
            (staging / "updater-desktop").chmod(0o600)
            entries.append((staging / "updater-desktop", updater_desktop))
        if uninstaller_desktop:
            uninstall_content = "[Desktop Entry]\nType=Application\nName=Uninstall " + DISPLAY_NAME + "\nComment=Review removal, reset and owned-data wipe\nExec=python3 -c " + quote_exec(launch_code) + " " + quote_exec(str(current / "uninstall.py")) + "\nIcon=edit-delete\nTerminal=true\nCategories=AudioVideo;\nX-OBSGod-Managed=true\n"
            (staging / "uninstaller-desktop").write_text(uninstall_content)
            (staging / "uninstaller-desktop").chmod(0o600)
            entries.append((staging / "uninstaller-desktop", uninstaller_desktop))
        try:
            for source, destination in entries:
                if destination == executable and destination.is_symlink() and destination.readlink() == current / "obsgod":
                    continue
                if destination == desktop and not destination.is_symlink() and destination.is_file() and destination.read_text() == content:
                    continue
                saved = None
                if destination.exists() or destination.is_symlink():
                    owned_directory(backup, home)
                    saved = backup / destination.name
                    # Copy links themselves, including dangling links; never
                    # write through somebody else's application/menu symlink.
                    shutil.copy2(destination, saved, follow_symlinks=False)
                source.replace(destination)
                changes.append((destination, saved))
            (staging / "current").replace(current)
        except (OSError, RuntimeError):
            for destination, saved in reversed(changes):
                if saved is not None:
                    saved.replace(destination)
                else:
                    destination.unlink(missing_ok=True)
            raise
    return current


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_idle(bridge, close=False):
    state = bridge.run_cli("status", timeout=6)
    if not isinstance(state, dict):
        raise RuntimeError("OBS output state could not be read. Inspect OBS before changing the installation.")
    recording = state.get("recording")
    recording_active = recording.get("active") if isinstance(recording, dict) else recording
    stream = state.get("stream")
    if (state.get("ok") is not True or state.get("state") not in ("stopped", "setup")
            or not isinstance(stream, dict) or stream.get("active") is not False
            or not isinstance(recording_active, bool) or recording_active
            or state.get("output_known") is not True
            or state.get("process") not in ("absent", "running")
            or state.get("operation") not in (None, "", "idle")):
        raise RuntimeError("OBS output is active, busy or unconfirmed. Stop streaming/recording in OBSGod first, then retry. The installer will not stop a broadcast for you.")
    if close and state.get("configured"):
        result = bridge.run_cli("restart", timeout=20)
        if not isinstance(result, dict) or not result.get("ok"):
            raise RuntimeError("Idle managed OBS could not be closed safely. Inspect OBS in Desktop Mode and retry; nothing was force-killed.")


@contextmanager
def control_lock(home):
    state = xdg_root("XDG_STATE_HOME", home) / "obsgod"
    owned_directory(state, home)
    descriptor = os.open(state / "control.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another OBSGod control operation is busy. Let it finish before installing.") from None
        yield


def installed_obs_version():
    # `info --show-version` is not a Flatpak option. Resolve the same user
    # application/ref that `flatpak run --user` uses, then query machine-readable
    # installed AppStream metadata. Do not infer it from another branch or the
    # system installation that Discover may also display.
    reference = subprocess.run(["flatpak", "info", "--user", "--show-ref", "com.obsproject.Studio"], capture_output=True, text=True, timeout=15)
    obs_ref = reference.stdout.strip()
    if reference.returncode or not re.fullmatch(r"app/com\.obsproject\.Studio/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+", obs_ref):
        raise RuntimeError("Could not identify the user-installed OBS Studio ref. Check OBS Studio's user installation in Discover, then retry.")
    result = subprocess.run(["flatpak", "list", "--user", "--app", "--columns=ref,version"], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Flatpak could not report the installed OBS version. Check Flatpak/SteamOS updates and retry.")
    versions = []
    for line in result.stdout.splitlines():
        ref, separator, version = line.partition("\t")
        # `info --show-ref` includes app/; `list`'s ref column omits that
        # kind prefix. Preserve the exact application, architecture and branch.
        if ref.strip().removeprefix("app/") == obs_ref.removeprefix("app/"):
            versions.append(version.strip() if separator else "")
    if len(versions) != 1 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.-]+)?", versions[0]):
        raise RuntimeError("OBS Studio is installed, but Flatpak did not report one usable version for its active user ref. Check the OBS Studio entry in Discover and retry.")
    return versions[0]


def ensure_dependencies():
    if not shutil.which("flatpak"):
        raise RuntimeError("Flatpak is unavailable. Install on your Steam Deck in Desktop Mode.")
    apps = ["com.obsproject.Studio", "com.obsproject.Studio.Plugin.Gstreamer"]
    installed = all(subprocess.run(["flatpak", "info", "--user", app], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15).returncode == 0 for app in apps)
    if not installed:
        print("Installing OBS and its capture plugin through Flathub. This may take several minutes…", flush=True)
        commands = [
            ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"],
            ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub"] + apps,
        ]
        for command in commands:
            if subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200).returncode:
                raise RuntimeError("OBS/capture installation failed. Check Discover, disk space and your connection, then rerun this installer.")
    version = installed_obs_version()
    if int(re.match(r"[0-9]+", version).group()) < 28:
        raise RuntimeError("User-installed OBS " + version + " is older than OBS 28, which is required for bundled obs-websocket. Update that user installation in Discover, then retry; do not install a second WebSocket plugin.")
    print("OBS " + version + " includes obs-websocket; authenticated readiness will be checked on startup.", flush=True)


def recover_previous_plugin(decky, previous):
    if previous is None:
        return False
    try:
        manifest_path = previous / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            return False
        manifest = json.loads(manifest_path.read_text())
        decky.helper_request("install", previous, manifest)
        return True
    except (OSError, ValueError, KeyError, RuntimeError):
        return False


def offer_decky_guide(url):
    """Offer official instructions, never download or execute a privileged installer."""
    question = "Decky is not ready. Open its official installation and troubleshooting instructions? Finish that setup, then rerun this installer."
    accepted = False
    if shutil.which("kdialog"):
        accepted = subprocess.run(["kdialog", "--title", DISPLAY_NAME, "--yesno", question], check=False).returncode == 0
    elif shutil.which("zenity"):
        accepted = subprocess.run(["zenity", "--question", "--title=" + DISPLAY_NAME, "--text=" + question], check=False).returncode == 0
    elif sys.stdin.isatty():
        accepted = input(question + " [y/N] ").strip().lower() in {"y", "yes"}
    if accepted:
        return webbrowser.open(url)
    return False


def install(launch=True, with_decky=True):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise RuntimeError("This preview package requires Linux x86_64 (Steam Deck)")
    if os.getuid() == 0:
        raise RuntimeError("Run this installer as your normal Deck user, without sudo")
    os.umask(0o077)
    manifest = verify_payload()
    decky = bridge = None
    if with_decky:
        if not {"decky.py", "decky-install"} <= set(manifest["files"]):
            raise RuntimeError("This older package cannot install Decky automatically. Use its documented manual ZIP path or download the current unified package.")
        decky = load_module("obsgod_install_decky", ROOT / "decky.py")
        print("Checking Decky's authenticated service and existing Steam connection…", flush=True)
        report = decky.status()
        if not report["ok"]:
            if launch:
                offer_decky_guide("https://decky.xyz/")
            raise RuntimeError(report["message"] + " No app or plugin was replaced. Install/start Decky using its official instructions, keep normal Steam open in Desktop Mode, and rerun this installer.")
        print("Decky " + report["version"] + " is ready.", flush=True)
        ensure_dependencies()
        bridge = load_module("obsgod_install_bridge", ROOT / "bridge.py")
    home = Path.home()
    base, apps = app_directories(home)
    releases = base / "releases"
    bin_dir = home / ".local/bin"
    for path in [base, releases, bin_dir, apps]:
        owned_directory(path, home)
    require_space(base, manifest)
    with installation_lock(base):
        if with_decky:
            require_idle(bridge, close=True)
            with control_lock(home):
                # Close/recheck while holding the same lock as Start/configure.
                # A concurrent start cannot race plugin replacement or activation.
                require_idle(bridge)
                current_path = base / "current"
                previous = current_path.resolve() if current_path.is_symlink() and current_path.resolve().parent == releases else None
                validate_activation_paths(base, releases, bin_dir, apps, manifest)
                candidate = prepare_release(releases, manifest)
                plugin_verified = False
                try:
                    print("Installing the verified OBSGod plugin through Decky…", flush=True)
                    decky.helper_request("install", candidate, manifest)
                    plugin_verified = True
                    current = activate_release(base, releases, bin_dir, apps, home, manifest)
                except (OSError, RuntimeError):
                    # An interrupted/timeout request can still be running in
                    # Decky. Never race it with a second rollback request. Only
                    # restore after confirmed plugin completion + app failure.
                    recovered = recover_previous_plugin(decky, previous) if plugin_verified else False
                    record = {"version": manifest["version"], "previous_version": previous.name if previous else None, "app_activation_changed": current_path.is_symlink() and current_path.resolve() == candidate, "plugin_rollback_confirmed": recovered}
                    recovery_path = base / "installation-recovery.json"
                    if not recovery_path.is_symlink():
                        recovery_path.write_text(json.dumps(record, indent=2) + "\n")
                        recovery_path.chmod(0o600)
                    raise RuntimeError("Installation did not complete. The previous app activation was preserved. " + ("The previous plugin was restored and verified." if recovered else "The plugin version/rollback is unconfirmed; check Decky and rerun this same installer to repair both copies.") + " Your key, settings and recordings were not reset.") from None
                recovery_path = base / "installation-recovery.json"
                if recovery_path.is_file() and not recovery_path.is_symlink():
                    recovery_path.unlink()
        else:
            current = activate_release(base, releases, bin_dir, apps, home, manifest)
    print("Installed " + DISPLAY_NAME + " " + manifest["version"] + (" in the app and Decky." if with_decky else " app files only; Decky was not installed or verified."))
    print("Reopen setup from Applications → Multimedia → " + DISPLAY_NAME + " Setup.")
    if "update.py" in manifest["files"]:
        print("Check and apply updates from Applications → Multimedia → Update " + DISPLAY_NAME + ".")
    print("Settings, keys, recordings, diagnostic history and unrelated plugins are preserved.")
    if not with_decky:
        print("Manual Decky ZIP: " + str(current / "obsgod-decky.zip"))
    if launch:
        print("Keep this terminal open while configuring OBSGod. Finish setup in the browser when done.", flush=True)
        result = subprocess.run([sys.executable, str(current / "setup.py")])
        if result.returncode:
            raise RuntimeError("Files were installed, but the setup page failed to start. The error is shown above; rerun OBSGod Setup after correcting it")
    return current


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--app-only", action="store_true", help="Install only app files for manual repair/testing; does not install or verify Decky")
    args = parser.parse_args()
    try:
        install(launch=not args.no_launch, with_decky=not args.app_only)
    except subprocess.TimeoutExpired:
        raise SystemExit("Install timed out while checking or installing a dependency. Inspect Decky/Discover and rerun the same installer to verify or repair the app/plugin pair; settings and recordings are preserved.") from None
    except KeyboardInterrupt:
        raise SystemExit("Installation was interrupted. Rerun this same installer to verify or repair both copies; do not delete your settings or stream key.") from None
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise SystemExit("Install failed: " + str(error))
