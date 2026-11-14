#!/usr/bin/env python3
"""Build the primary, self-contained standard Decky plugin ZIP.

Use --verify-cli /absolute/path/to/decky-0.0.7 to additionally assemble the
prepared payload with the pinned official CLI and compare every packaged byte.
Nothing installs, publishes, starts OBS or starts a stream.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

from decky_package import (BUILDER_ALIAS, BUILDER_IMAGE, CLI_SHA256, CLI_VERSION,
                           TOOLS, json_bytes, plugin_files, read_zip, stage_cli, zip_payload)

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("legacy_deck_package", REPO / "scripts/package-deck.py")
LEGACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEGACY)


def command(*args, **kwargs):
    return subprocess.check_output(args, cwd=REPO, text=True, **kwargs).strip()


def source_snapshot():
    paths = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=REPO).split(b"\0")
    snapshot = {}
    for encoded in sorted(set(paths) - {b""}):
        name = os.fsdecode(encoded)
        path = REPO / name
        if not path.exists():
            snapshot[name] = None
        elif path.is_symlink() or not path.is_file():
            raise ValueError("Unsafe source input: " + name)
        else:
            snapshot[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def output_directory(path):
    """Only create a new output directory; never remove or overwrite user data."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("--output must be an absolute path without traversal")
    for ancestor in (path.parent, *path.parent.parents):
        info = ancestor.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ValueError("Unsafe output ancestor: " + str(ancestor))
        if (info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            raise ValueError("Unprotected or foreign output ancestor: " + str(ancestor))
    if path.parent.stat().st_uid != os.getuid():
        raise ValueError("Output parent must belong to the build user")
    path.mkdir(mode=0o700)


def verify_cli(cli, files, work):
    cli = cli.absolute()
    if cli.is_symlink() or hashlib.sha256(cli.read_bytes()).hexdigest() != CLI_SHA256:
        raise ValueError("Use the pinned official Decky CLI 0.0.7 asset and SHA256 from docs/decky-package.md")
    if command(str(cli), "--version") != "decky " + CLI_VERSION:
        raise ValueError("Unexpected Decky CLI version")
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("Docker is required for --verify-cli")
    # CLI 0.0.7 hardcodes builder:latest. A transparent, bounded engine adapter
    # pins only that exact invocation without retagging images or patching CLI.
    adapter = work / "engine"
    adapter.mkdir(mode=0o700)
    wrapper = adapter / "docker"
    wrapper.write_text("#!" + sys.executable + "\n" +
        "import os,sys\n" +
        "args=sys.argv[1:]\n" +
        "if args==['ps']: pass\n" +
        "elif args and args[0]=='run' and args[-1]==" + repr(BUILDER_ALIAS) + ":\n" +
        "    args=['run','--network=none','--env','HOME=/tmp','--env','CI=true',*args[1:-1]," + repr(BUILDER_IMAGE) + "]\n" +
        "else: raise SystemExit('Refusing unexpected CLI container-engine invocation')\n" +
        "os.execv(" + repr(docker) + ",[" + repr(docker) + ",'--host=unix:///var/run/docker.sock',*args])\n")
    wrapper.chmod(0o700)
    stage = work / "obsgod"
    stage_cli(files, stage)
    raw = work / "official"
    raw.mkdir(mode=0o700)
    env = dict(os.environ, PATH=str(adapter) + os.pathsep + os.environ["PATH"])
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)
    subprocess.run([str(cli), "plugin", "build", "--output-path", str(raw),
                    "--tmp-output-path", str(work / "cli-tmp"),
                    "--output-filename-source", "directory", str(stage)], check=True, env=env)
    archives = list(raw.glob("*.zip"))
    if len(archives) != 1:
        raise ValueError("Official CLI did not produce exactly one ZIP")
    actual = read_zip(archives[0])
    if actual != files:
        missing, extra = sorted(files.keys() - actual.keys()), sorted(actual.keys() - files.keys())
        changed = sorted(name for name in files.keys() & actual.keys() if files[name] != actual[name])
        raise ValueError(f"Official CLI payload differs: missing={missing}, extra={extra}, changed={changed}")
    return {"status": "passed", "version": CLI_VERSION, "sha256": CLI_SHA256,
            "builder_image": BUILDER_IMAGE, "builder_node": "26.12.1", "builder_pnpm": "12.14.0",
            "container_network": "none", "payload_files_compared": len(files),
            "raw_zip_sha256": hashlib.sha256(archives[0].read_bytes()).hexdigest(),
            "raw_zip_reproducible": False,
            "scope": "Unmodified official CLI and pinned default builder, assembling prepared bytes; not source compilation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="0.1.0-deck.9")
    parser.add_argument("--revision")
    parser.add_argument("--output", type=Path, required=True, help="New absolute output directory; existing paths are preserved")
    parser.add_argument("--allow-dirty", action="store_true", help="Unqualified local development build only")
    parser.add_argument("--verify-cli", type=Path, help="Pinned official 0.0.7 CLI binary; never downloaded automatically")
    args = parser.parse_args()
    if os.getuid() != REPO.stat().st_uid or os.getuid() == 0:
        raise ValueError("Run the primary package build as the non-root checkout owner (including inside act)")
    if not args.version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in args.version):
        raise ValueError("Invalid version")
    revision = command("git", "rev-parse", "HEAD")
    if args.revision and args.revision != revision:
        raise ValueError("Only the checked-out full source revision may label this build")
    source_status = command("git", "status", "--porcelain")
    source_files = source_snapshot()
    dirty = bool(source_status)
    if dirty and not args.allow_dirty:
        raise ValueError("Commit source changes first, or use --allow-dirty for an unqualified local build")
    epoch = int(command("git", "show", "-s", "--format=%ct", revision))
    if command("go", "version").split()[2] != TOOLS["go"]:
        raise ValueError("Use the pinned Go " + TOOLS["go"] + " toolchain")
    if command("node", "--version") != "v" + TOOLS["node"] or command("npm", "--version") != TOOLS["npm"]:
        raise ValueError("Use pinned Node " + TOOLS["node"] + " and npm " + TOOLS["npm"])
    # Validate and reserve the output before starting expensive work. It remains
    # empty on failure; no previous artifact is replaced or automatically removed.
    output_directory(args.output)
    subprocess.run([sys.executable, str(REPO / "scripts/generate-product.py"), "--check"], check=True)
    subprocess.run(["node", str(REPO / "scripts/generate-support.mjs"), "--check"], check=True)
    with tempfile.TemporaryDirectory(prefix="obsgod-decky-") as temporary:
        work = Path(temporary)
        frontend = work / "frontend"
        for action in ("typecheck", "build"):
            cmd = [sys.executable, str(REPO / "scripts/frontend-command.py"), action]
            if action == "build":
                cmd += ["--output", str(frontend)]
            subprocess.run(cmd, check=True)
        native, native_receipt = work / "libgstobsgodcapture.so", work / "capture-build.json"
        subprocess.run([sys.executable, str(REPO / "scripts/build-deck-capture.py"), "--output", str(native),
                        "--receipt", str(native_receipt)], check=True)
        binary = work / "obsgod-bin"
        env = dict(os.environ, CGO_ENABLED="0", GOOS="linux", GOARCH="amd64")
        subprocess.run(["go", "build", "-trimpath", "-buildvcs=false", "-ldflags",
                        "-s -w -buildid= -X main.version=" + args.version + " -X main.commitSHA=" + revision,
                        "-o", str(binary), "."], cwd=REPO, env=env, check=True)
        files = plugin_files(REPO, version=args.version, binary=binary.read_bytes(), capture_library=native.read_bytes(),
            frontend=frontend, capture_source=LEGACY.capture_source(epoch), notices=LEGACY.notices().encode(),
            revision=revision, dirty=dirty, capture_receipt=native_receipt.read_bytes())
        official = verify_cli(args.verify_cli, files, work) if args.verify_cli else {"status": "unrun"}
        # Concurrent edits cannot silently receive this build's source label.
        if (command("git", "rev-parse", "HEAD") != revision
                or command("git", "status", "--porcelain") != source_status or source_snapshot() != source_files):
            raise ValueError("Source changed during build; rerun from a stable revision")
        archive = args.output / "obsgod-decky.zip"
        archive.write_bytes(zip_payload(files, epoch))
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        receipt = {"revision": revision, "dirty": dirty, "version": args.version, "platform": "linux/amd64",
            "source_tools": TOOLS, "archive": archive.name, "sha256": checksum,
            "source_files_sha256": source_files,
            "payload_files": len(files), "official_cli": official,
            "device_installation": "unrun", "obs_startup_streaming": "unrun",
            "release_publication": "not performed"}
        (args.output / "build-receipt.json").write_bytes(json_bytes(receipt))
        (args.output / "SHA256SUMS").write_text(checksum + "  " + archive.name + "\n")
        print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("Decky package build failed: " + str(error))
