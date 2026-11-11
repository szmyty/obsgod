#!/usr/bin/env python3
"""Extract the maintained updater from an exact, clean runtime candidate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
FILES = ("update.py", "releases.py", "decky.py", "decky-install", "Update OBSGod.desktop", "Update OBSGod.sh", "LICENSE", "THIRD_PARTY_NOTICES.md")
EXECUTABLES = {"decky-install", "Update OBSGod.desktop", "Update OBSGod.sh"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Runtime archive built by package-deck.py from this clean revision")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise SystemExit("Commit source before packaging the updater")
    with tarfile.open(args.archive) as runtime:
        entries = runtime.getmembers()
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)) or any(not entry.isfile() for entry in entries):
            raise SystemExit("Use the unmodified runtime archive from package-deck.py")
        roots = {name.split("/")[0] for name in names}
        if len(roots) != 1:
            raise SystemExit("Invalid runtime archive root")
        root = roots.pop()
        manifest = json.load(runtime.extractfile(root + "/manifest.json"))
        version = manifest.get("version", "")
        if not re.fullmatch(r"[0-9][A-Za-z0-9.-]{0,79}", version) or root != "OBSGod-" + version:
            raise SystemExit("Invalid runtime version")
        if manifest.get("revision") != revision or manifest.get("dirty") is not False or manifest.get("platform") != "linux/amd64" or manifest.get("updater_version") != version:
            raise SystemExit("Use a clean runtime candidate built from the current source revision")
        files = {}
        for name in FILES:
            entry = runtime.getmember(root + "/" + name)
            if entry.size > 32 * 1024 * 1024:
                raise SystemExit("Oversized updater file")
            data = runtime.extractfile(entry).read()
            if hashlib.sha256(data).hexdigest() != manifest["files"].get(name):
                raise SystemExit("Runtime checksum mismatch: " + name)
            files[name] = data
    updater = {"kind": "updater", "version": version, "updater_version": version, "revision": revision, "runtime_revision": revision, "platform": "linux/amd64", "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["manifest.json"] = (json.dumps(updater, indent=2, sort_keys=True) + "\n").encode()
    epoch = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", revision], cwd=REPO, text=True))
    timestamp = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc).timetuple()[:6]
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    output_path = dist / ("obsgod-one-click-update_" + version + "_linux_amd64.zip")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("OBSGod-Updater/" + name, timestamp)
            info.create_system = 3
            info.external_attr = (0o100755 if name in EXECUTABLES else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    (dist / "updater-manifest.json").write_bytes(files["manifest.json"])
    checksum = hashlib.sha256(output_path.read_bytes()).hexdigest() + "  " + output_path.name + "\n"
    (dist / "UPDATER-SHA256SUMS").write_text(checksum)
    print(checksum, end="")


if __name__ == "__main__":
    main()
