#!/usr/bin/env python3
"""Run and inspect two complete primary builds as the non-root checkout owner.

The new output and its private HOME/TMPDIR must be on a daemon-visible path when
used inside ACT. Logs remain private. Nothing installs, publishes, starts OBS,
changes checkout ownership, deletes caches or accepts a dirty-source candidate.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

# ACT enters this wrapper as root. Imports must not create root-owned bytecode
# in the shared checkout before the fixed owner re-execution.
sys.dont_write_bytecode = True

from decky_package import (BUILDER_IMAGE, CLI_SHA256, CLI_VERSION, SHARED_FILES,
                           TOOLS, json_bytes, safe_read)

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


PRIMARY = module("qualified_primary_entry", "package-decky.py")
AUDIT = module("qualified_primary_audit", "release-audit.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def identity():
    owner = ROOT.stat()
    require(owner.st_uid != 0 and os.getuid() in (0, owner.st_uid),
            "Use a non-root-owned checkout and run as its owner")
    return owner.st_uid, owner.st_gid


def private_directory(path, uid, *, require_private=True):
    require(path.is_absolute() and ".." not in path.parts,
            "Use an absolute private path without traversal")
    for parent in (path, *path.parents):
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                "Refusing a linked or non-directory build path")
        require(info.st_uid in (0, uid) and
                (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX),
                "Refusing foreign or unprotected build ancestry")
    info = path.stat()
    require(info.st_uid == uid and
            (not require_private or not stat.S_IMODE(info.st_mode) & 0o077),
            "The build directory must belong to the checkout owner and be private when required")


def new_output(path, uid):
    # Hosted RUNNER_TEMP can be owner-protected 0755. The new child itself is
    # private; allowing that parent does not permit writable/foreign ancestry.
    private_directory(path.parent, uid, require_private=False)
    require(not path.is_relative_to(ROOT) and not ROOT.is_relative_to(path),
            "Keep qualification output outside the checkout")
    require(not path.exists() and not path.is_symlink(),
            "Qualification output must be new; preserve existing evidence")
    require(path.is_absolute() and ".." not in path.parts,
            "Use an absolute output path without traversal")


def docker_groups(gid):
    """Drop root groups; add only the existing local Docker socket's group."""
    try:
        info = Path("/var/run/docker.sock").lstat()
    except FileNotFoundError:
        return []
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == 0,
            "Refusing an unexpected local Docker socket identity")
    return [info.st_gid] if info.st_gid != gid else []


def cache_directory(path, uid):
    private_directory(path.parent, uid)
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=0o700)
    private_directory(path, uid)
    return str(path)


def build_environment(output, uid):
    context = output / "context"
    context.mkdir(mode=0o700)
    for name in ("home", "tmp"):
        (context / name).mkdir(mode=0o700)
    scratch = os.environ.get("OBSGOD_LOCAL_SCRATCH")
    if scratch:
        parent = Path(scratch)
        private_directory(parent, uid)
        require(not parent.is_relative_to(ROOT) and not ROOT.is_relative_to(parent),
                "Keep local build caches outside the checkout")
        declared = os.environ.get("OBSGOD_LOCAL_OWNER_UID", str(uid))
        require(declared == str(uid), "Local scratch owner does not match the checkout owner")
        compiler = parent / f"go-build-user-{uid}"
        modules = parent / f"go-mod-user-{uid}"
    else:
        compiler, modules = context / "go-build", context / "go-mod"
    env = os.environ.copy()
    for key in ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND", "XDG_CONFIG_HOME",
                "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        env.pop(key, None)
    env.update(HOME=str(context / "home"), TMPDIR=str(context / "tmp"),
               GOCACHE=cache_directory(compiler, uid),
               GOMODCACHE=cache_directory(modules, uid), PYTHONDONTWRITEBYTECODE="1")
    return env, {key: env[key] for key in ("HOME", "TMPDIR", "GOCACHE", "GOMODCACHE")}


def inspect_build(output, revision, version, source_files):
    """Read bounded artifacts, never execute archive members or extract them."""
    receipt_bytes = safe_read(output / "build-receipt.json", limit=4 * 1024 * 1024)
    receipt = json.loads(receipt_bytes)
    archive = output / "obsgod-decky.zip"
    archive_bytes = safe_read(archive)
    checksum = sha(archive_bytes)
    require(receipt.get("revision") == revision and receipt.get("version") == version
            and receipt.get("dirty") is False and receipt.get("platform") == "linux/amd64"
            and receipt.get("source_tools") == TOOLS and receipt.get("archive") == archive.name,
            "Primary receipt has inconsistent source, platform or tool identity")
    require(receipt.get("sha256") == checksum and
            receipt.get("source_files_sha256") == source_files,
            "Primary receipt does not match the actual archive and source snapshot")
    require(safe_read(output / "SHA256SUMS") ==
            (checksum + "  " + archive.name + "\n").encode(),
            "Primary checksum list does not match its canonical ZIP")
    root, files = AUDIT.archive_files(archive_bytes, "zip")
    require(root == "obsgod" and set(files) == AUDIT.STANDARD_PLUGIN_FILES,
            "Primary payload inventory differs; private state and extra files are forbidden")
    manifest = json.loads(files["manifest.json"])
    AUDIT.verify_manifest(files, manifest)
    require(all(manifest.get(key) == value for key, value in {
        "format": "decky-plugin", "revision": revision, "version": version,
        "dirty": False, "platform": "linux/amd64", "source_tools": TOOLS}.items()),
        "Primary manifest has inconsistent source, platform or tool identity")
    require(receipt.get("payload_files") == len(files), "Primary payload count differs")
    plugin = json.loads(files["plugin.json"])
    require(plugin.get("name") == "OBSGod" and plugin.get("flags") == []
            and plugin.get("api_version") == 1, "Primary plugin identity or privileges changed")
    expected_sources = {p.name: p for p in (ROOT / "steamdeck/decky").glob("*.py")}
    expected_sources.update({name: ROOT / "steamdeck" / name for name in SHARED_FILES})
    expected_sources.update({"README.md": ROOT / "docs/decky-package.md",
                             "LICENSE": ROOT / "LICENSE",
                             "LICENSE.LGPL-2.1": ROOT / "steamdeck/decky/LICENSE.LGPL-2.1",
                             "LICENSE.qrcode-generator.txt": ROOT / "steamdeck/decky/LICENSE.qrcode-generator.txt"})
    require(all(files.get(name) == safe_read(path) for name, path in expected_sources.items()),
            "Primary source, setup or notice bytes differ from the checked-out source")
    native = json.loads(files["build/capture-build.json"])
    require(native.get("sha256") == sha(files["bin/libgstobsgodcapture.so"])
            and native.get("source_sha256") == sha(safe_read(ROOT / "steamdeck/capture/gstobsgodcapture.c"))
            and native.get("dockerfile_sha256") == sha(safe_read(ROOT / "steamdeck/capture/build.Dockerfile"))
            and native.get("network_during_compile") is False,
            "Primary native build receipt differs from its source or library")
    official = receipt.get("official_cli")
    require(isinstance(official, dict) and official.get("status") in ("unrun", "passed"),
            "Primary official assembly result is invalid")
    if official["status"] == "passed":
        require(official.get("version") == CLI_VERSION and official.get("sha256") == CLI_SHA256
                and official.get("builder_image") == BUILDER_IMAGE
                and official.get("payload_files_compared") == len(files)
                and official.get("container_network") == "none"
                and official.get("raw_zip_reproducible") is False,
                "Official assembly metadata differs from its pinned scope")
    return {"archive": str(archive), "sha256": checksum, "receipt_sha256": sha(receipt_bytes),
            "manifest_sha256": sha(files["manifest.json"]), "payload_files": len(files),
            "source_files": len(source_files), "source_private_inventory": "passed",
            "official_cli": official}


def qualify(args):
    uid, gid = identity()
    new_output(args.output, uid)
    if os.getuid() == 0:
        command = [sys.executable, "-B", str(Path(__file__).resolve()), *sys.argv[1:]]
        return subprocess.run(command, cwd=ROOT, user=uid, group=gid,
                              extra_groups=docker_groups(gid)).returncode
    args.output.mkdir(mode=0o700)
    os.umask(0o077)
    record = {"schema": "obsgod.primary-build-qualification/v1", "revision": args.revision,
              "version": args.version, "observed_revision": git("rev-parse", "HEAD"),
              "source_tree": git("rev-parse", "HEAD^{tree}"),
              "dirty": bool(git("status", "--porcelain")), "uid": os.getuid(),
              "gid": os.getgid(), "groups": os.getgroups(), "status": "running", "builds": [],
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "limits": ["Local build only; actual Deck, OBS/provider, hosted acceptance and publication remain separate.",
                         "Canonical ZIP bytes are compared; optional official CLI assembly is not source compilation or reproducible raw ZIP proof.",
                         "Logs are private and require review before sharing. No cache is deleted by this helper."]}
    receipt_path = args.output / "qualification.json"

    def save():
        receipt_path.write_bytes(json_bytes(record))

    save()
    try:
        env, context = build_environment(args.output, uid)
        record["build_context"] = context
        before = PRIMARY.source_snapshot()
        for name in ("first", "second"):
            command = [sys.executable, "-B", str(ROOT / "scripts/package-decky.py"),
                       "--version", args.version, "--revision", args.revision,
                       "--output", str(args.output / name)]
            if args.verify_cli:
                command += ["--verify-cli", str(args.verify_cli)]
            log = args.output / (name + ".log")
            started = time.monotonic()
            with log.open("xb") as stream:
                result = subprocess.run(command, cwd=ROOT, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT)
            build = {"name": name, "command": command, "exit_code": result.returncode,
                     "seconds": round(time.monotonic() - started, 3), "log": log.name,
                     "log_sha256": sha(safe_read(log))}
            record["builds"].append(build)
            save()
            if result.returncode:
                record.update(status="failed", failure="Primary entry point failed; inspect the private build log")
                save()
                print(f"Primary entry point failed; private evidence: {receipt_path}", file=sys.stderr)
                return result.returncode if result.returncode > 0 else 1
            build["inspection"] = inspect_build(args.output / name, args.revision, args.version, before)
            save()
        require(safe_read(args.output / "first/obsgod-decky.zip") ==
                safe_read(args.output / "second/obsgod-decky.zip"),
                "Repeated primary canonical ZIP bytes differ")
        require(record["observed_revision"] == args.revision == git("rev-parse", "HEAD")
                and record["dirty"] is False and not git("status", "--porcelain")
                and PRIMARY.source_snapshot() == before, "Source changed during primary qualification")
        record.update(status="passed", archive=str(args.output / "second/obsgod-decky.zip"),
                      sha256=record["builds"][1]["inspection"]["sha256"],
                      finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save()
        print(json.dumps({"status": "passed", "archive": record["archive"], "sha256": record["sha256"],
                          "receipt": str(receipt_path)}))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        record.update(status="failed", failure_type=type(error).__name__,
                      failure="Primary qualification refused; no accepted archive. Inspect private inputs/logs.")
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--version", default="0.1.0-deck.9")
    parser.add_argument("--output", type=Path, required=True, help="New absolute directory under an existing protected checkout-owner parent")
    parser.add_argument("--verify-cli", type=Path, help="Optional pinned official CLI, never downloaded by this helper")
    args = parser.parse_args()
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.revision), "Use a full lowercase source revision")
        return qualify(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Primary qualification refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
