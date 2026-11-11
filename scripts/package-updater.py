#!/usr/bin/env python3
"""Package a one-click installer for the already-qualified preview-4 runtime."""
import hashlib
import json
from pathlib import Path
import os
import subprocess
import zipfile
from datetime import datetime, timezone

from importlib.util import spec_from_file_location, module_from_spec

REPO = Path(__file__).resolve().parents[1]
VERSION = "0.1.0-deck.4-updater.1"


def main():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise SystemExit("Commit source before packaging the updater")
    if "go1.27.4" not in subprocess.check_output(["go", "version"], text=True):
        raise SystemExit("Use the pinned Go 1.27.4 toolchain")
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    binary = dist / "decky-install"
    subprocess.run(["go", "build", "-trimpath", "-buildvcs=false", "-ldflags", "-s -w -buildid=", "-o", str(binary), "./cmd/obsgod-decky-install"], cwd=REPO, env=dict(os.environ, CGO_ENABLED="0", GOOS="linux", GOARCH="amd64"), check=True)
    spec = spec_from_file_location("deck_packager", REPO / "scripts/package-deck.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    files = {name: (REPO / "steamdeck" / name).read_bytes() for name in ["update.py", "Update OBSGod.desktop", "Update OBSGod.sh"]}
    files.update({"decky-install": binary.read_bytes(), "LICENSE": (REPO / "LICENSE").read_bytes(), "THIRD_PARTY_NOTICES.md": module.notices().encode()})
    manifest = {"version": VERSION, "revision": revision, "target_version": "0.1.0-deck.4", "platform": "linux/amd64", "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    epoch = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", revision], cwd=REPO, text=True))
    timestamp = datetime.fromtimestamp(epoch, timezone.utc).timetuple()[:6]
    archive = dist / ("obsgod-one-click-update_" + VERSION + "_linux_amd64.zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("OBSGod-Updater/" + name, timestamp)
            info.create_system = 3
            info.external_attr = (0o100755 if name in {"decky-install", "Update OBSGod.desktop", "Update OBSGod.sh"} else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    (dist / "updater-manifest.json").write_bytes(files["manifest.json"])
    print(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name)


if __name__ == "__main__":
    main()
