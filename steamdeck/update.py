#!/usr/bin/env python3
"""Install the pinned, qualified preview and replace its plugin through Decky."""
import fcntl
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0-deck.4"
PAYLOAD_URL = "https://raw.githubusercontent.com/szmyty/obsgod/64039036e0ef8d0fa0e9242cf6abf8cf2583a606/obsgod-deck_0.1.0-deck.4_linux_amd64.tar.gz"
PAYLOAD_SHA256 = "c584c04ed3c79a01f1b846adc4f8bbe86c8132a4bca2cf6ba60cc557eba39ce1"
ZIP_SHA256 = "3eec780691c0d9d62ba286bfe946ae64ceda2124339e1e2f9314fb89ac8cae54"
MAX_ARCHIVE = 32 * 1024 * 1024


class UpdateError(RuntimeError):
    pass


def private_directory(path, home):
    if not path.resolve().is_relative_to(home.resolve()):
        raise UpdateError("An install directory points outside your home. Existing files were preserved.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise UpdateError("An install directory is unsafe. Existing files were preserved.")


def verify_bundle():
    if not (ROOT / "manifest.json").is_file():
        raise UpdateError("Extract the entire updater ZIP first, then open Update OBSGod.desktop inside that folder.")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    expected = {"update.py", "decky-install", "Update OBSGod.desktop", "Update OBSGod.sh", "LICENSE", "THIRD_PARTY_NOTICES.md"}
    if set(manifest["files"]) != expected or manifest["target_version"] != VERSION:
        raise UpdateError("The updater package is incomplete. Extract the entire updater ZIP first.")
    for name, digest in manifest["files"].items():
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise UpdateError("Updater checksum verification failed. Download and extract a fresh updater ZIP.")
    (ROOT / "decky-install").chmod(0o700)


def check_decky():
    connection = http.client.HTTPConnection("127.0.0.1", 1337, timeout=3)
    try:
        connection.request("GET", "/auth/token")
        response = connection.getresponse()
        token = response.read(1024)
        if response.status != 200 or not 16 <= len(token) <= 128:
            raise UpdateError("Decky's local installer is unavailable. Keep Decky installed, return to Desktop Mode and rerun this updater.")
    except (OSError, http.client.HTTPException):
        raise UpdateError("Decky Loader is not running. Start Decky normally, return to Desktop Mode and rerun this updater.") from None
    finally:
        connection.close()


def download_payload(destination):
    deadline = time.monotonic() + 180
    total = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(PAYLOAD_URL, timeout=30) as source, destination.open("xb") as output:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE or time.monotonic() > deadline:
                    raise UpdateError("The download exceeded its size/time limit. Existing files were preserved; retry with a working connection.")
                output.write(chunk)
                digest.update(chunk)
    except OSError:
        raise UpdateError("The download failed. Check your connection and free disk space, then rerun the updater.") from None
    if digest.hexdigest() != PAYLOAD_SHA256:
        raise UpdateError("Download checksum mismatch. Existing files were preserved; download a fresh updater and retry.")


def unpack_payload(archive, destination):
    # SteamOS Python versions may predate tarfile's data filter. Validate every
    # member and copy only regular files into a new private directory instead.
    prefix = "OBSGod-" + VERSION
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        if len(members) > 64 or sum(item.size for item in members) > 64 * 1024 * 1024:
            raise UpdateError("Invalid release archive size")
        seen = set()
        for item in members:
            parts = PurePosixPath(item.name).parts
            if not parts or parts[0] != prefix or ".." in parts or "\\" in item.name or item.name in seen or not (item.isfile() or item.isdir()):
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
                target.chmod(0o700 if target.name == "obsgod" else 0o600)
    return destination / prefix


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_ok(result, instruction):
    if not result.get("ok"):
        # Only fixed bridge/CLI error messages are returned here, not settings,
        # stderr, subprocess exceptions, auth tokens or request payloads.
        raise UpdateError(instruction + "\n" + result.get("message", "Operation could not be confirmed"))


def close_managed_obs(bridge):
    state = bridge.run_cli("status", timeout=6)
    if state.get("stream", {}).get("active") or state.get("state") == "unknown":
        stopped = bridge.run_cli("stop", timeout=25)
        require_ok(stopped, "Could not confirm OBS stopped. Inspect the managed OBS window in Desktop Mode, stop its output, then rerun the updater.")
    else:
        require_ok(state, "Could not check existing OBS output. Inspect OBS in Desktop Mode before updating.")
    if state.get("configured"):
        require_ok(bridge.run_cli("restart", timeout=25), "Could not close idle managed OBS. Stop any recording/stream in OBS, then rerun the updater.")


def ensure_dependencies():
    if not shutil.which("flatpak"):
        raise UpdateError("Flatpak is unavailable. Run this updater on your Steam Deck in Desktop Mode.")
    installed = all(subprocess.run(["flatpak", "info", "--user", app], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15).returncode == 0 for app in ["com.obsproject.Studio", "com.obsproject.Studio.Plugin.Gstreamer"])
    if installed:
        return
    commands = [
        ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"],
        ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", "com.obsproject.Studio", "com.obsproject.Studio.Plugin.Gstreamer"],
    ]
    for command in commands:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200)
        if result.returncode:
            raise UpdateError("OBS/capture installation failed. Check Discover, disk space and your connection, then rerun the updater.")


def backup_settings(base, home):
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "obsgod"
    backup = base / "backups" / ("updater-" + str(time.time_ns()))
    for name in ["deck.json", "secrets.json"]:
        source = config / name
        if source.exists() or source.is_symlink():
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 64 * 1024:
                raise UpdateError("An existing settings file is unsafe. Existing files were preserved.")
            private_directory(backup, home)
            shutil.copyfile(source, backup / name)
            (backup / name).chmod(0o600)


def replace_plugin(current):
    payload = {"zip_path": str((current / "obsgod-decky.zip").resolve()), "sha256": ZIP_SHA256, "version": VERSION}
    try:
        process = subprocess.run([str(ROOT / "decky-install")], input=json.dumps(payload), capture_output=True, text=True, timeout=100)
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError()
    except (OSError, subprocess.SubprocessError, ValueError):
        raise UpdateError("The Desktop app was installed, but Decky's plugin update could not be confirmed. Close Steam's Big Picture window and rerun this updater in Desktop Mode.") from None
    require_ok(result, "The Desktop app was installed, but the Decky plugin update failed. Your saved settings remain.")
    if result.get("version") != VERSION:
        raise UpdateError("Decky did not confirm the expected plugin version. Rerun the updater after checking Decky.")


def run_update():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"} or os.getuid() == 0:
        raise UpdateError("Run this updater as your normal Steam Deck user in Desktop Mode, without sudo.")
    session = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" + os.environ.get("DESKTOP_SESSION", "")).lower()
    if "gamescope" in session or "steamos" in session:
        raise UpdateError("Switch to Desktop Mode before running this updater.")
    verify_bundle()
    home = Path.home()
    base = home / ".local/share/obsgod"
    private_directory(base, home)
    descriptor = os.open(base / "update.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError("Another OBSGod updater is running. Let it finish, then retry.") from None
        print("1/6 Checking the installed Decky service…", flush=True)
        check_decky()
        print("2/6 Downloading and verifying OBSGod " + VERSION + "…", flush=True)
        with tempfile.TemporaryDirectory(prefix=".update-", dir=base) as temporary:
            work = Path(temporary)
            archive = work / "payload.tar.gz"
            download_payload(archive)
            package = unpack_payload(archive, work)
            installer = load_module("obsgod_payload_installer", package / "install.py")
            installer.verify_payload()
            bridge = load_module("obsgod_payload_bridge", package / "bridge.py")
            print("3/6 Confirming output is stopped and closing idle managed OBS…", flush=True)
            close_managed_obs(bridge)
            print("4/6 Checking OBS and the capture plugin (downloads may take several minutes)…", flush=True)
            ensure_dependencies()
            backup_settings(base, home)
            print("5/6 Installing the Desktop app; preserving your settings and key…", flush=True)
            current = installer.install(launch=False)
            print("6/6 Replacing OBSGod through Decky's authenticated installer…", flush=True)
            replace_plugin(current)
            configured = bridge.run_cli("status", timeout=6).get("configured", False)
            if not configured:
                print("Opening local setup so you can enter your settings on this Deck…", flush=True)
                subprocess.run([sys.executable, str(current / "setup.py")], check=True)
    return "OBSGod " + VERSION + " is installed in the Desktop app and Decky.\n\nYour saved key, settings, recordings and diagnostic history are preserved.\n\nReturn to Gaming Mode, open a game, then make a local test clip. If startup still fails, choose Copy console log and send the log."


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
    os.umask(0o077)
    success = False
    try:
        message = run_update()
        success = True
    except UpdateError as error:
        message = str(error)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as error:
        message = "The updater stopped (" + type(error).__name__ + "). Your saved keys were not reset. Read the progress above, check your connection/free disk space and rerun the updater."
    except KeyboardInterrupt:
        message = "Update interrupted. Your settings were not reset. Rerun this updater to finish and verify both installations."
    print(("DONE: " if success else "UPDATE STOPPED: ") + message, flush=True)
    show_result(message, success)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
