"""Shared standard Decky payload and official CLI staging contract.

The source build is performed by package-decky.py with the repository's pinned
tools. Decky's CLI assembles that prepared plugin; it never rebuilds the native
capture library against the host SteamOS ABI.
"""
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile

CLI_VERSION = "0.0.7"
CLI_SHA256 = "0d0f8c127cd3dba12b75f771c786194ca9f4f771b4787ae24de8b1af45af4294"
CLI_URL = "https://github.com/SteamDeckHomebrew/cli/releases/download/0.0.7/decky-linux-x86_64"
BUILDER_IMAGE = "ghcr.io/steamdeckhomebrew/builder@sha256:e2616e391f3ae9a46c4cf906b1091220c2506e7fb1301e16a2a72409efbce7c5"
BUILDER_ALIAS = "ghcr.io/steamdeckhomebrew/builder:latest"
TOOLS = {"go": "go1.27.4", "node": "24.19.0", "npm": "11.9.0"}
FRONTEND_FILES = ("index.js", "decky-api.js", "manifest.js", "types.js", "LICENSE.qrcode-generator.txt")
SHARED_FILES = ("releases.py", "paths.py", "product.py", "bridge.py", "setup.py", "setup.html", "setup.js", "setup.css")
# This build script validates prepared bytes, not source compilation. It works
# both in the CLI's defaults/ staging tree and in the flattened installed ZIP.
STAGE_BUILD = b'''import {readFileSync,existsSync} from "node:fs";
import {createHash} from "node:crypto";
const locate=name=>existsSync(name)?name:"defaults/"+name;
const manifest=JSON.parse(readFileSync(locate("manifest.json"),"utf8"));
for(const [name,expected] of Object.entries(manifest.files)){
  const actual=createHash("sha256").update(readFileSync(locate(name))).digest("hex");
  if(actual!==expected)throw new Error("Prepared payload changed: "+name);
}
console.log("Verified prepared Decky payload; source compilation used pinned repository tools.");
'''
STAGE_LOCK = b"lockfileVersion: '9.0'\nsettings:\n  autoInstallPeers: true\n  excludeLinksFromLockfile: false\nimporters:\n  .: {}\n"


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sdk_source_archive(sdk):
    """Keep original source paths inside a deterministic preferred-source TAR.

    Decky's default builder excludes nested src/ directories during rsync; an
    archive retains the untouched source tree without customizing that builder.
    """
    files = {"package.json": safe_read(sdk / "package.json")}
    for path in sorted((sdk / "src").rglob("*")):
        if path.is_symlink():
            raise ValueError("Refusing linked SDK source: " + str(path))
        if path.is_file():
            files[path.relative_to(sdk).as_posix()] = safe_read(path)
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, data in sorted(files.items()):
                entry = tarfile.TarInfo("decky-api/" + name)
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
                archive.addfile(entry, io.BytesIO(data))
    return output.getvalue()


def safe_read(path, *, limit=64 * 1024 * 1024):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise ValueError(f"Refusing unsafe or oversized package input: {path}")
    return path.read_bytes()


def validate_files(files):
    if not files or len(files) > 2048:
        raise ValueError("Invalid package file count")
    for name, data in files.items():
        path = PurePosixPath(name)
        if (not isinstance(name, str) or path.is_absolute() or ".." in path.parts
                or str(path) != name or "\\" in name or not isinstance(data, bytes)):
            raise ValueError("Invalid package payload path or content")
    required = {"main.py", "storage.py", "dependency_setup.py", "plugin.json", "package.json", "dist/index.js", "bin/obsgod",
                "bin/libgstobsgodcapture.so", "LICENSE", "LICENSE.LGPL-2.1",
                "THIRD_PARTY_NOTICES.md", "CAPTURE-SOURCE.tar.gz", "dist/decky-api.js",
                "source/decky-api/package.json", "source/decky-api/SOURCE.tar.gz", *SHARED_FILES}
    if required - files.keys():
        raise ValueError("Missing package payload: " + ", ".join(sorted(required - files.keys())))
    plugin = json.loads(files["plugin.json"])
    package = json.loads(files["package.json"])
    if plugin.get("name") != "OBSGod" or plugin.get("flags") != [] or plugin.get("api_version") != 1:
        raise ValueError("Unexpected Decky identity, privileges or API contract")
    if package.get("name") != "obsgod":
        raise ValueError("Unexpected compatible package identity")


def plugin_files(repo, *, version, binary, capture_library, frontend, capture_source, notices,
                 revision, dirty, capture_receipt=None):
    """One complete plugin, including our optional Desktop configuration UI."""
    plugin = {}

    def add(name, data):
        if name in plugin:
            raise ValueError("Duplicate package path: " + name)
        plugin[name] = data

    backend = repo / "steamdeck/decky"
    modules = sorted(backend.glob("*.py"))
    if len(modules) > 128:
        raise ValueError("Too many top-level backend modules")
    for path in modules:
        add(path.name, safe_read(path, limit=2 * 1024 * 1024))
    for name in SHARED_FILES:
        add(name, safe_read(repo / "steamdeck" / name, limit=2 * 1024 * 1024))
    add("plugin.json", safe_read(backend / "plugin.json"))
    add("package.json", json_bytes({"name": "obsgod", "version": version, "license": "MIT",
        "type": "module", "scripts": {"build": "node build/verify.mjs"}}))
    add("build/verify.mjs", STAGE_BUILD)
    add("pnpm-lock.yaml", STAGE_LOCK)
    add("README.md", safe_read(repo / "docs/decky-package.md"))
    add("bin/obsgod", binary)
    add("bin/libgstobsgodcapture.so", capture_library)
    add("CAPTURE-SOURCE.tar.gz", capture_source)
    for name, source in (("LICENSE", repo / "LICENSE"),
                         ("LICENSE.LGPL-2.1", backend / "LICENSE.LGPL-2.1"),
                         ("LICENSE.qrcode-generator.txt", backend / "LICENSE.qrcode-generator.txt")):
        add(name, safe_read(source))
    add("THIRD_PARTY_NOTICES.md", notices)
    for name in FRONTEND_FILES:
        add("dist/" + name, safe_read(frontend / name))
    # Keep the LGPL SDK separate and replaceable, with its preferred source.
    sdk = backend / "node_modules/@decky/api"
    add("source/decky-api/SOURCE.tar.gz", sdk_source_archive(sdk))
    add("source/decky-api/package.json", safe_read(sdk / "package.json"))
    add("source/decky-api/BUILDING.md", b"SOURCE.tar.gz contains the unmodified preferred TypeScript source of @decky/api 1.1.3, including its original package.json and src/ tree under decky-api/. Extract with tar -xzf SOURCE.tar.gz, then use the corresponding repository revision's pinned frontend toolchain and rollup.config.js. The outer package.json is an identical convenience copy. dist/decky-api.js is separate and replaceable; build changes are the manifest import to ./manifest.js and the types export to ./types.js. dist/manifest.js supplies the OBSGod name. LICENSE.LGPL-2.1 is at the plugin root.\n")
    if capture_receipt is not None:
        add("build/capture-build.json", capture_receipt)
    manifest = {"format": "decky-plugin", "version": version, "revision": revision,
                "dirty": dirty, "platform": "linux/amd64", "source_tools": TOOLS,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(plugin.items())}}
    add("manifest.json", json_bytes(manifest))
    validate_files(plugin)
    return plugin


def zip_payload(files, epoch):
    validate_files(files)
    output = io.BytesIO()
    timestamp = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("obsgod/" + name, timestamp)
            info.create_system = 3
            info.external_attr = (0o100755 if name.startswith("bin/") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return output.getvalue()


def stage_cli(files, directory):
    """Materialize CLI-supported root files plus defaults/ flattened extras.

    Never run CLI on the real checkout: CLI 0.0.7 chmods bind roots to 0777.
    """
    validate_files(files)
    directory.mkdir(mode=0o700)  # must be new, not an existing checkout
    expected = {"LICENSE", "main.py", "package.json", "plugin.json", "README.md"}
    for name, data in files.items():
        direct = name in expected or name.endswith(".py") and "/" not in name or name.startswith(("bin/", "dist/"))
        target = directory / (name if direct else "defaults/" + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if name.startswith("bin/") else 0o644)
    # The builder executes these root inputs; defaults/ carries the same bytes
    # into the flattened final archive. No package download is needed.
    (directory / "pnpm-lock.yaml").write_bytes(files["pnpm-lock.yaml"])
    (directory / "build").mkdir()
    (directory / "build/verify.mjs").write_bytes(files["build/verify.mjs"])


def read_zip(path):
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != len(set(names)) or any(not name.startswith("obsgod/") for name in names):
            raise ValueError("Duplicate or unexpected official CLI archive paths")
        files = {name.removeprefix("obsgod/"): archive.read(name) for name in names}
    validate_files(files)
    return files
