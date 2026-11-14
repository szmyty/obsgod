#!/usr/bin/env python3
"""Run a fixed frontend check/build as the checkout owner, including under ACT.

Only private temporary HOME/TMPDIR paths are chowned. Existing frontend output
must already be safe and owned by that user; this helper never repairs, removes
or changes ownership/permissions of checkout files.
"""
import argparse
import os
from pathlib import Path
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {"typecheck": ["run", "typecheck"], "test": ["test"], "build": ["run", "build"]}


class FrontendError(RuntimeError):
    pass


def checkout_identity(root):
    owner = root.stat()
    if owner.st_uid == 0:
        raise FrontendError("Frontend commands require a non-root-owned checkout")
    if os.getuid() not in (0, owner.st_uid):
        raise FrontendError("Run frontend commands as the checkout owner")
    return (owner.st_uid, owner.st_gid) if os.getuid() == 0 else (os.getuid(), os.getgid())


def validate_output(root, uid):
    frontend = root / "steamdeck" / "decky"
    for path in (root / "steamdeck", frontend):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
            raise FrontendError(f"Refusing unsafe or foreign frontend directory: {path}")
    output = frontend / "dist"
    pending = [output]
    while pending:
        path = pending.pop()
        try:
            info = path.lstat()
        except FileNotFoundError:
            if path == output:
                return
            raise FrontendError(f"Frontend output changed during validation: {path}")
        if info.st_uid != uid or stat.S_ISLNK(info.st_mode):
            raise FrontendError(f"Refusing symlink or foreign frontend output: {path}; preserve it before recovery")
        if path == output and not stat.S_ISDIR(info.st_mode):
            raise FrontendError(f"Frontend output must be a directory: {path}")
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise FrontendError(f"Refusing non-regular or linked frontend output: {path}")


def run_frontend(action, *, root=ROOT, npm="npm"):
    uid, gid = checkout_identity(root)
    validate_output(root, uid)
    env = os.environ.copy()
    for key in ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND", "XDG_CONFIG_HOME",
                "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="ogf-", dir="/tmp") as temporary:
        work = Path(temporary)
        for path in (work, work / "home", work / "tmp"):
            path.mkdir(exist_ok=True, mode=0o700)
            if os.getuid() == 0:
                os.chown(path, uid, gid)
        env.update(HOME=str(work / "home"), TMPDIR=str(work / "tmp"))
        identity = {"user": uid, "group": gid, "extra_groups": []} if os.getuid() == 0 else {}
        print(f"Frontend {action} runs as UID {uid}, GID {gid}", flush=True)
        result = subprocess.run([npm, *COMMANDS[action]], cwd=root / "steamdeck" / "decky", env=env, **identity)
        validate_output(root, uid)
        return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=COMMANDS)
    args = parser.parse_args()
    try:
        return run_frontend(args.action)
    except (FrontendError, OSError) as error:
        parser.exit(1, f"Frontend command refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
