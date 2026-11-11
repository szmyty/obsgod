#!/usr/bin/env python3
"""Build a reproducible Steam Deck archive and Decky ZIP from a source revision."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[1]


def command(*args, **kwargs):
    return subprocess.check_output(args, cwd=REPO, text=True, **kwargs).strip()


def modules_json(data):
    decoder = json.JSONDecoder()
    while data.strip():
        value, end = decoder.raw_decode(data.lstrip())
        yield value
        data = data.lstrip()[end:]


def notices():
    text = "# Third-party notices\n\nOBSGod's CLI and application code retain the repository MIT license.\n\n"
    text += "OBS Studio and obs-gstreamer are separately installed GPL software from Flathub; their binaries are not included in this package.\n\n"
    text += "The Decky plugin imports @decky/api 1.1.3 as a separate, replaceable LGPL-2.1 module in dist/decky-api.js, with its license included. Modifications change the manifest import to ./manifest.js and add the .js suffix to the types import for native browser modules. The original source is at https://github.com/SteamDeckHomebrew/loader-api. React and @decky/ui are supplied by Steam/Decky and are not bundled. Build inputs are pinned in steamdeck/decky/package-lock.json.\n\n"
    text += "## Go standard library\n\n" + (Path(command("go", "env", "GOROOT")) / "LICENSE").read_text() + "\n"
    linked = {}
    for package in modules_json(command("go", "list", "-deps", "-json", ".")):
        module = package.get("Module")
        if module and not module.get("Main"):
            linked[module["Path"]] = module
    for _, module in sorted(linked.items()):
        directory = Path(module["Dir"])
        candidates = [directory / name for name in ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"]]
        license_file = next((p for p in candidates if p.is_file()), None)
        if license_file is None:
            raise RuntimeError("Missing dependency license: " + module["Path"])
        text += "\n## " + module["Path"] + " " + module["Version"] + "\n\n" + license_file.read_text() + "\n"
    return text


def zip_payload(files, epoch):
    output = io.BytesIO()
    timestamp = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("obsgod/" + name, timestamp)
            info.create_system = 3
            info.external_attr = (0o100755 if name == "bin/obsgod" else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="0.1.0-deck.3")
    parser.add_argument("--revision", default=None)
    parser.add_argument("--allow-dirty", action="store_true", help="Local test packages only; manifest is marked dirty")
    args = parser.parse_args()
    if not args.version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in args.version):
        raise SystemExit("Invalid version")
    revision = args.revision or command("git", "rev-parse", "HEAD")
    dirty = bool(command("git", "status", "--porcelain"))
    if dirty and not args.allow_dirty:
        raise SystemExit("Commit source changes first, or use --allow-dirty for a local test package")
    if revision != command("git", "rev-parse", "HEAD"):
        raise SystemExit("Package the checked-out revision; do not label different source with another SHA")
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise SystemExit("Use a full source commit SHA")
    epoch = int(command("git", "show", "-s", "--format=%ct", revision))
    if "go1.27.4" not in command("go", "version"):
        raise SystemExit("Use the pinned Go 1.27.4 toolchain")
    subprocess.run(["npm", "run", "typecheck"], cwd=REPO / "steamdeck/decky", check=True)
    subprocess.run(["npm", "run", "build"], cwd=REPO / "steamdeck/decky", check=True)
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    binary = dist / "obsgod"
    env = dict(os.environ, CGO_ENABLED="0", GOOS="linux", GOARCH="amd64")
    subprocess.run(["go", "build", "-trimpath", "-buildvcs=false", "-ldflags", "-s -w -buildid= -X main.version=" + args.version + " -X main.commitSHA=" + revision, "-o", str(binary), "."], cwd=REPO, env=env, check=True)
    third_party = notices().encode()
    plugin = {
        "main.py": (REPO / "steamdeck/decky/main.py").read_bytes(),
        "plugin.json": (REPO / "steamdeck/decky/plugin.json").read_bytes(),
        "package.json": json.dumps({"name": "obsgod", "version": args.version, "license": "MIT", "type":"module"}, sort_keys=True).encode(),
        "bin/obsgod": binary.read_bytes(),
        "LICENSE": (REPO / "LICENSE").read_bytes(),
        "LICENSE.LGPL-2.1": (REPO / "steamdeck/decky/LICENSE.LGPL-2.1").read_bytes(),
        "THIRD_PARTY_NOTICES.md": third_party,
    }
    for name in ["index.js", "decky-api.js", "manifest.js", "types.js"]:
        plugin["dist/" + name] = (REPO / "steamdeck/decky/dist" / name).read_bytes()
    # Include the SDK's preferred source form as well as its replaceable runtime
    # module, so the LGPL dependency can be rebuilt and modified independently.
    sdk = REPO / "steamdeck/decky/node_modules/@decky/api"
    for path in sorted((sdk / "src").rglob("*")):
        if path.is_file():
            plugin["source/decky-api/" + path.relative_to(sdk).as_posix()] = path.read_bytes()
    plugin["source/decky-api/package.json"] = (sdk / "package.json").read_bytes()
    plugin["source/decky-api/BUILDING.md"] = b"The unmodified preferred TypeScript source of @decky/api 1.1.3 is included here. OBSGod's pinned TypeScript build and rollup.config.js are in the release's corresponding GitHub source archive. The runtime dist/decky-api.js is a separate replaceable module. Its build changes only the manifest import to ./manifest.js and the types export to ./types.js; dist/manifest.js supplies the OBSGod name. The complete LGPL-2.1 license is at the plugin root.\n"
    plugin_zip = zip_payload(plugin, epoch)
    (dist / "obsgod-decky.zip").write_bytes(plugin_zip)
    files = {name: (REPO / "steamdeck" / name).read_bytes() for name in ["setup.py", "bridge.py", "setup.html", "setup.js", "setup.css", "uninstall.py"]}
    files.update({"obsgod": binary.read_bytes(), "LICENSE": (REPO / "LICENSE").read_bytes(), "THIRD_PARTY_NOTICES.md": third_party, "STEAM-DECK.md": (REPO / "docs/steam-deck.md").read_bytes(), "obsgod-decky.zip": plugin_zip})
    manifest = {"version": args.version, "revision": revision, "dirty": dirty, "go": "go1.27.4", "platform": "linux/amd64", "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    files["install.py"] = (REPO / "steamdeck/install.py").read_bytes()
    files["Install OBSGod.desktop"] = (REPO / "steamdeck/Install OBSGod.desktop").read_bytes()
    archive_path = dist / ("obsgod-deck_" + args.version + "_linux_amd64.tar.gz")
    with archive_path.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo("OBSGod-" + args.version + "/" + name)
                    info.size = len(data)
                    info.mtime = epoch
                    info.mode = 0o755 if name in {"obsgod", "install.py", "Install OBSGod.desktop"} else 0o644
                    archive.addfile(info, io.BytesIO(data))
    (dist / "manifest.json").write_bytes(files["manifest.json"])
    artifacts = [archive_path, dist / "obsgod-decky.zip", dist / "manifest.json"]
    checksums = "".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n" for path in artifacts)
    (dist / "SHA256SUMS").write_text(checksums)
    print(checksums)


if __name__ == "__main__":
    main()
