#!/usr/bin/env python3
"""Explicit resource checks and compiler-cache policy for local ACT attempts.

This helper never moves host caches, prunes Docker, or removes toolchains,
modules, artifacts or evidence. The constrained profile trades compiler-cache
reuse for space only at an explicit workflow boundary after its consumers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import time

GIB = 1024 ** 3
ROOT_REQUIRED = 4 * GIB
SCRATCH_REQUIRED = 6 * GIB
PROFILE = "constrained"


def write_json(path, value):
    temporary = path.with_name(path.name + ".new")
    if temporary.exists() or temporary.is_symlink() or path.is_symlink():
        raise ValueError("Unsafe resource receipt path")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def safe_ancestry(path, owner):
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Use an absolute private path without traversal")
    for parent in [path, *path.parents]:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError("Scratch paths cannot contain symlinks or non-directories")
        if info.st_uid not in (0, owner) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            raise ValueError("Scratch ancestry is foreign or unprotected")


def private_directory(path, root=None):
    """Reject symlinks and foreign/private-output ancestry before mutation."""
    path = Path(path)
    safe_ancestry(path, os.getuid())
    if root is not None:
        checkout = Path(root).resolve()
        if path.is_relative_to(checkout) or checkout.is_relative_to(path):
            raise ValueError("Keep scratch outside the checkout")
    if not path.exists():
        path.mkdir(mode=0o700, parents=True)
    safe_ancestry(path, os.getuid())
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Scratch must be an owned private directory (mode0700)")
    return path


def allocate_attempt(base, action, root):
    base = private_directory(base, root)
    name = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + action + "-" + secrets.token_hex(6)
    attempt = base / name
    attempt.mkdir(mode=0o700)
    for directory in ("tmp", "go-build-root"):
        (attempt / directory).mkdir(mode=0o700)
    return attempt


def disk(path):
    info = os.statvfs(path)
    return {"available_bytes": info.f_bavail * info.f_frsize,
            "total_bytes": info.f_blocks * info.f_frsize,
            "filesystem_id": info.f_fsid, "device": os.stat(path).st_dev}


def docker_metadata(image, env):
    """Read cached metadata without creating a potentially expensive VFS copy."""
    commands = [["docker", "--host", "unix:///var/run/docker.sock", "info", "--format", "{{json .Driver}}"],
                ["docker", "--host", "unix:///var/run/docker.sock", "image", "inspect", "--format", "{{json .Size}}", image]]
    values = []
    for command in commands:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError("Managed Docker metadata unavailable; verify the local daemon and cached pinned runner image")
        values.append(json.loads(result.stdout))
    driver, size = values
    if not isinstance(driver, str) or not driver or not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("Invalid managed Docker driver/image metadata")
    return {"driver": driver, "image_size_bytes": size, "image": image, "commands": commands}


def preflight(root, attempt, image, revision):
    """Measure both host paths and what the local Docker daemon actually sees."""
    root, attempt = Path(root), Path(attempt)
    marker = attempt / ".daemon-volume-probe"
    written = attempt / ".daemon-volume-probe-output"
    if marker.exists() or marker.is_symlink() or written.exists() or written.is_symlink():
        raise ValueError("Expected unused private probe paths")
    env = {key: value for key, value in os.environ.items() if key not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    receipt = {"schema_version": 1, "profile": PROFILE, "revision": revision,
               "scope": "Preflight only; no workflow check was executed", "scratch": str(attempt),
               "host_root": disk(root), "host_scratch": disk(attempt),
               "probe": {"status": "unrun", "exit_code": None},
               "status": "unavailable", "shortfalls": []}
    same = receipt["host_root"]["device"] == receipt["host_scratch"]["device"]
    receipt["same_host_filesystem"] = same
    try:
        metadata = docker_metadata(image, env)
        # VFS deep-copies an image when a container is created. The observed
        # cached ACT image exhausted ~3GiB merely probing a 1.625GB logical
        # image, so reserve 2x its reported size before any docker run. Other
        # drivers retain the operational floor and the actual allocation probe.
        allowance = 2 * metadata["image_size_bytes"] if metadata["driver"] == "vfs" else 0
        receipt["docker_metadata"] = metadata
        receipt["allocation_policy"] = {"runner_copy_allowance_bytes": allowance,
            "formula": "2 * cached image Size for vfs; 0 for other drivers",
            "scope": "Conservative pre-allocation allowance, not a peak-space guarantee"}
        root_required = ROOT_REQUIRED + allowance
        combined = root_required + SCRATCH_REQUIRED
        receipt["requirements"] = {"root_bytes": root_required, "scratch_bytes": SCRATCH_REQUIRED,
                                   "same_filesystem_bytes": combined, "daemon_root_after_allocation_bytes": ROOT_REQUIRED}
        for name, required in (("host_root", combined if same else root_required),
                               ("host_scratch", combined if same else SCRATCH_REQUIRED)):
            available = receipt[name]["available_bytes"]
            if available < required:
                receipt["shortfalls"].append({"location": name, "required_bytes": required,
                                              "available_bytes": available, "missing_bytes": required - available})
        if receipt["shortfalls"]:
            receipt.update(status="refused", reason="Host capacity is insufficient before allocating the cached runner probe")
            write_json(attempt / "preflight.json", receipt)
            return receipt
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        receipt["reason"] = str(error)
        write_json(attempt / "preflight.json", receipt)
        return receipt
    marker.write_text(secrets.token_hex(24))
    marker.chmod(0o600)
    # The host allocation gate passed. Verify actual daemon capacity and owner
    # access using only the cached pinned image, without pulling anything.
    command = ["docker", "--host", "unix:///var/run/docker.sock", "run", "--rm", "--network", "none", "--pull=never",
               "--user", f"{os.getuid()}:{os.getgid()}",
               "--mount", f"type=bind,src={attempt},dst=/probe",
               "--entrypoint", "python3", image, "-c",
               "import json,os; from pathlib import Path; "
               "disk=lambda p:dict(available_bytes=os.statvfs(p).f_bavail*os.statvfs(p).f_frsize,"
               "total_bytes=os.statvfs(p).f_blocks*os.statvfs(p).f_frsize,filesystem_id=os.statvfs(p).f_fsid); "
               "marker=Path('/probe/.daemon-volume-probe').read_text(); "
               "Path('/probe/.daemon-volume-probe-output').write_text(marker); "
               "print(json.dumps(dict(marker=marker,"
               "docker_root=disk('/'),scratch=disk('/probe'))))"]
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    receipt["probe"] = {"command": command, "status": "passed" if result and result.returncode == 0 else "failed",
                        "exit_code": result.returncode if result else None}
    try:
        if result is None or result.returncode:
            raise ValueError("Pinned Docker probe failed; verify the local daemon and cached runner image")
        observed = json.loads(result.stdout)
        if observed.pop("marker", None) != marker.read_text():
            raise ValueError("Docker daemon cannot observe the selected scratch directory")
        if (written.is_symlink() or not written.is_file() or not stat.S_ISREG(written.stat().st_mode)
                or written.stat().st_uid != os.getuid() or written.read_text() != marker.read_text()):
            raise ValueError("Docker daemon cannot write scratch as the actual local owner")
        receipt["owner_write_verified"] = True
        receipt["daemon"] = observed
        requirements = (("daemon_root", ROOT_REQUIRED), ("daemon_scratch", SCRATCH_REQUIRED))
        observations = {"daemon_root": observed["docker_root"], "daemon_scratch": observed["scratch"]}
        for name, required in requirements:
            available = observations[name]["available_bytes"]
            if available < required:
                receipt["shortfalls"].append({"location": name, "required_bytes": required,
                                              "available_bytes": available, "missing_bytes": required - available})
        receipt["status"] = "refused" if receipt["shortfalls"] else "passed"
    except (ValueError, KeyError, TypeError) as error:
        receipt["probe"]["status"] = "failed"
        receipt["reason"] = str(error)
    finally:
        marker.unlink()
        if written.exists() or written.is_symlink():
            written.unlink()
    write_json(attempt / "preflight.json", receipt)
    return receipt


def cache_inventory(path):
    digest = hashlib.sha256()
    files = bytes_ = 0
    for parent, directories, names in os.walk(path, followlinks=False):
        directories.sort()
        for name in sorted(directories + names):
            entry = Path(parent) / name
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError("Private compiler cache contains a symlink or special file")
            digest.update(str(entry.relative_to(path)).encode() + b"\0")
            if stat.S_ISREG(info.st_mode):
                digest.update(hashlib.sha256(entry.read_bytes()).digest())
                files += 1
                bytes_ += info.st_size
    return {"sha256": digest.hexdigest(), "files": files, "bytes": bytes_}


def active_compilers():
    active = []
    for process in Path("/proc").iterdir():
        if not process.name.isdecimal():
            continue
        try:
            name = (process / "comm").read_text().strip()
            status = (process / "status").read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if name in ("go", "compile", "link", "asm", "cgo") and "State:\tZ" not in status:
            active.append({"pid": int(process.name), "name": name})
    return active


def trim_compiler_cache():
    if os.environ.get("OBSGOD_LOCAL_PROFILE") != PROFILE:
        print("Compiler-cache policy inactive outside the explicit local constrained profile")
        return 0
    attempt = Path(os.environ["OBSGOD_LOCAL_SCRATCH"])
    owner = os.environ["OBSGOD_LOCAL_OWNER_UID"]
    if not owner.isdecimal():
        raise ValueError("Expected the numeric local attempt owner")
    safe_ancestry(attempt, int(owner))
    if (not attempt.is_dir() or attempt.stat().st_uid != int(owner)
            or stat.S_IMODE(attempt.stat().st_mode) & 0o077):
        raise ValueError("Expected an owned private attempt directory")
    record = Path(os.environ["OBSGOD_LOCAL_RESOURCE_RECEIPT"])
    if record != attempt / "resource-policy.json" or record.is_symlink() or record.exists():
        raise ValueError("Expected a new attempt-local resource-policy receipt")
    cache = Path(os.environ["GOCACHE"])
    if cache != attempt / "go-build-root" or cache.is_symlink() or not cache.is_dir():
        raise ValueError("Refusing to trim a cache outside the exact private attempt path")
    caches = [cache]
    # The unprivileged official builder has a separate cache because ACT runs
    # Go as root. Never grant it ownership of another identity's cache tree.
    for entry in sorted(attempt.glob("go-build-user-*")):
        if entry.name != "go-build-user-" + owner or entry.is_symlink() or not entry.is_dir():
            raise ValueError("Unexpected private compiler cache")
        caches.append(entry)
    for target in caches:
        for parent, directories, names in os.walk(target, followlinks=False):
            for name in directories + names:
                if (Path(parent) / name).is_symlink():
                    raise ValueError("Private compiler cache contains a symlink")
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            # Linux mountinfo escapes spaces/backslashes using octal notation.
            mount = re_mount_path(line.split()[4])
            if mount == target or mount.is_relative_to(target):
                raise ValueError("Compiler cache contains a separate mount")
    if active_compilers():
        raise ValueError("A Go compiler is still active; cache consumers must finish first")
    phases = []
    for target in caches:
        before = cache_inventory(target)
        env = dict(os.environ, GOCACHE=str(target))
        observed = subprocess.check_output(["go", "env", "GOCACHE"], env=env, text=True).strip()
        if observed != str(target):
            raise ValueError("Go resolved another compiler cache")
        command = ["go", "clean", "-cache"]
        row = {"cache": str(target), "before": before, "disk_before": disk(attempt), "command": command}
        write_json(record, {"schema_version": 1, "profile": PROFILE,
                           "scope": "Only attempt-local compiler caches, after all Go consumers; no host caches, module caches, toolchains, artifacts or evidence removed",
                           "phases": phases + [dict(row, result="running")], "completed": False})
        run = subprocess.run(command, env=env, capture_output=True, text=True)
        row.update(exit_code=run.returncode, after=cache_inventory(target), disk_after=disk(attempt))
        phases.append(row)
        write_json(record, {"schema_version": 1, "profile": PROFILE, "scope": "Only attempt-local compiler caches, after all Go consumers; no host caches, module caches, toolchains, artifacts or evidence removed", "phases": phases, "completed": False})
        if run.returncode:
            return run.returncode
    write_json(record, {"schema_version": 1, "profile": PROFILE, "scope": "Only attempt-local compiler caches, after all Go consumers; no host caches, module caches, toolchains, artifacts or evidence removed", "phases": phases, "completed": True})
    print(json.dumps({"compiler_cache_policy": "passed", "receipt": str(record)}))
    return 0


def re_mount_path(value):
    import re
    return Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["trim-compiler-cache"])
    parser.parse_args()
    raise SystemExit(trim_compiler_cache())
