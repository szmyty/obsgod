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
    current = base / "current"
    if current.exists() or current.is_symlink():
        if not current.is_symlink() or not current.resolve().is_relative_to(releases):
            raise RuntimeError("OBSGod current path is not an owned release link")
    release = releases / manifest["version"]
    if release.exists() or release.is_symlink():
        if release.is_symlink() or not release.is_dir():
            raise RuntimeError("Unsafe existing release path")
        if any(not (release / name).is_file() or hashlib.sha256((release / name).read_bytes()).hexdigest() != digest for name, digest in manifest["files"].items()):
            raise RuntimeError("A different package already uses this version; remove that version explicitly before reinstalling")
    else:
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
    link = base / ".current-next"
    if link.exists() or link.is_symlink():
        raise RuntimeError("An incomplete install is present; inspect .current-next before retrying")
    link.symlink_to(release)
    link.replace(current)

    executable = bin_dir / "obsgod"
    backup = base / "backups" / str(time.time_ns())
    if executable.exists() or executable.is_symlink():
        if not (executable.is_symlink() and executable.readlink() == current / "obsgod"):
            owned_directory(backup, home)
            executable.rename(backup / "obsgod")
            print("Previous obsgod executable preserved at " + str(backup / "obsgod"))
        else:
            executable.unlink()
    executable.symlink_to(current / "obsgod")
    desktop = apps / "obsgod-setup.desktop"
    if desktop.exists():
        if desktop.is_symlink() or "X-OBSGod-Managed=true" not in desktop.read_text():
            owned_directory(backup, home)
            desktop.rename(backup / "obsgod-setup.desktop")
    launch_code = "import subprocess,sys; result=subprocess.run([sys.executable,sys.argv[1]]); input('Press Enter to close this window.'); sys.exit(result.returncode)"
    content = "[Desktop Entry]\nType=Application\nName=OBSGod Setup\nComment=Configure Steam Deck streaming locally\nExec=python3 " + quote_exec(launch_code) + " " + quote_exec(str(current / "setup.py")) + "\nIcon=video-display\nTerminal=true\nCategories=AudioVideo;\nX-OBSGod-Managed=true\n"
    desktop.write_text(content)
    desktop.chmod(0o600)
    print("Installed OBSGod " + manifest["version"])
    print("Decky plugin ZIP: " + str(current / "obsgod-decky.zip"))
    print("Reopen setup from Applications → Multimedia → OBSGod Setup.")
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
