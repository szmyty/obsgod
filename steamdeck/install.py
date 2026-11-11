#!/usr/bin/env python3
"""Install the verified preview payload to user-owned paths; no sudo required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import fcntl
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent


def owned_directory(path, home):
    if not path.resolve().is_relative_to(home.resolve()):
        raise RuntimeError("Install paths must stay inside your home directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Refusing a symlinked install directory: " + str(path))


def quote_exec(value):
    if any(c in value for c in "\r\n\x00"):
        raise RuntimeError("Unsupported character in installation path")
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
    if set(manifest["files"]) != required:
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
    return all(
        not (release / name).is_symlink() and (release / name).is_file()
        and hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest["files"].items()
    )


def prepare_release(releases, manifest):
    current = releases.parent / "current"
    if current.is_symlink() and current.resolve().parent == releases:
        try:
            installed = json.loads((current / "manifest.json").read_text())
        except (OSError, ValueError):
            installed = {}
        if installed.get("version") == manifest["version"] and matching_release(current.resolve(), manifest):
            for name in manifest["files"]:
                (current / name).chmod(0o700 if name == "obsgod" else 0o600)
            return current.resolve()
    release = releases / manifest["version"]
    if release.exists() or release.is_symlink():
        if release.is_symlink() or not release.is_dir():
            raise RuntimeError("Unsafe existing release path")
        if matching_release(release, manifest):
            # ZIP/filesystem tools can drop mode bits. Repair a verified copy.
            for name in manifest["files"]:
                (release / name).chmod(0o700 if name == "obsgod" else 0o600)
            return release
        # Preserve an older/damaged copy, including files mapped by a running
        # process. A fresh directory allows repair and same-version replacement.
        release = releases / (manifest["version"] + "-" + str(time.time_ns()))
    staging = Path(tempfile.mkdtemp(prefix=".install-", dir=releases))
    try:
        for name in manifest["files"]:
            shutil.copyfile(ROOT / name, staging / name)
            (staging / name).chmod(0o700 if name == "obsgod" else 0o600)
        shutil.copyfile(ROOT / "manifest.json", staging / "manifest.json")
        staging.rename(release)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return release


def activate_release(base, releases, bin_dir, apps, home, manifest):
    current = base / "current"
    if current.exists() or current.is_symlink():
        if not current.is_symlink() or not current.resolve().is_relative_to(releases):
            raise RuntimeError("OBSGod current path is not an owned release link")
    executable = bin_dir / "obsgod"
    desktop = apps / "obsgod-setup.desktop"
    for path in [executable, desktop]:
        if path.exists() and not (path.is_file() or path.is_symlink()):
            raise RuntimeError("Refusing to replace a non-file application entry")
    release = prepare_release(releases, manifest)
    launch_code = "import subprocess,sys; result=subprocess.run([sys.executable,sys.argv[1]]); input('Press Enter to close this window.'); sys.exit(result.returncode)"
    content = "[Desktop Entry]\nType=Application\nName=OBSGod Setup\nComment=Configure Steam Deck streaming locally\nExec=python3 " + quote_exec(launch_code) + " " + quote_exec(str(current / "setup.py")) + "\nIcon=video-display\nTerminal=true\nCategories=AudioVideo;\nX-OBSGod-Managed=true\n"
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
        try:
            for source, destination in [(staging / "executable", executable), (staging / "desktop", desktop)]:
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


def install(launch=True):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise RuntimeError("This preview package requires Linux x86_64 (Steam Deck)")
    if os.getuid() == 0:
        raise RuntimeError("Run this installer as your normal Deck user, without sudo")
    os.umask(0o077)
    manifest = verify_payload()
    home = Path.home()
    base = home / ".local/share/obsgod"
    releases = base / "releases"
    bin_dir = home / ".local/bin"
    apps = home / ".local/share/applications"
    for path in [base, releases, bin_dir, apps]:
        owned_directory(path, home)
    with installation_lock(base):
        current = activate_release(base, releases, bin_dir, apps, home, manifest)
    print("Installed OBSGod " + manifest["version"])
    print("Decky plugin ZIP: " + str(current / "obsgod-decky.zip"))
    print("Reopen setup from Applications → Multimedia → OBSGod Setup.")
    print("Settings, keys and recordings are preserved. Replace OBSGod in Decky using the ZIP above as well.")
    if launch:
        print("Keep this terminal open while configuring OBSGod. Finish setup in the browser when done.", flush=True)
        result = subprocess.run([sys.executable, str(current / "setup.py")])
        if result.returncode:
            raise RuntimeError("Files were installed, but the setup page failed to start. The error is shown above; rerun OBSGod Setup after correcting it")
    return current


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args()
    try:
        install(launch=not args.no_launch)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise SystemExit("Install failed: " + str(error))
