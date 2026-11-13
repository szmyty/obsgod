#!/usr/bin/env python3
"""Run Python user-install/browser fixtures with a real unprivileged identity.

Hosted non-root runners keep their identity. act runs setup as root, then this
helper drops UID/GID and supplementary groups for user-owned install behavior.
Production root guards are never disabled. Only new, explicit test output and a
private temporary HOME/TMPDIR are owned; the checkout is never chowned/chmodded.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="Persistent browser evidence directory outside the checkout")
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help="Python script or -m/-c invocation, following --")
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    if not arguments:
        parser.error("Supply a Python test command after --")
    root_user = os.getuid() == 0
    owner = ROOT.stat()
    uid, gid = (owner.st_uid, owner.st_gid) if root_user and owner.st_uid else (65534, 65534)
    if not root_user:
        uid, gid = os.getuid(), os.getgid()
    if args.output_root:
        if args.output_root.is_symlink():
            parser.error("Refusing a symlink evidence directory")
        output = args.output_root.resolve()
        if output.is_relative_to(ROOT) or ROOT.is_relative_to(output):
            parser.error("Keep generated evidence outside the checkout")
        existed = output.exists()
        if existed and (not output.is_dir() or output.stat().st_uid != uid):
            parser.error("Existing evidence directory must already belong to the test user")
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root_user and not existed:
            os.chown(output, uid, gid)
    env = os.environ.copy()
    for key in ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        env.pop(key, None)
    # Browser Unix sockets have a short pathname limit. These private fixtures
    # do not use nested Docker mounts; persistent evidence/cache stay outside.
    with tempfile.TemporaryDirectory(prefix="ogt-", dir="/tmp") as temporary:
        work = Path(temporary)
        for path in (work, work / "home", work / "tmp"):
            path.mkdir(exist_ok=True, mode=0o700)
            if root_user:
                os.chown(path, uid, gid)
        # Let each fixture's HOME select its own XDG defaults. Binding explicit
        # XDG paths here would point outside a fixture that replaces HOME.
        env.update(HOME=str(work / "home"), TMPDIR=str(work / "tmp"), PYTHONDONTWRITEBYTECODE="1")
        identity = {"user": uid, "group": gid, "extra_groups": []} if root_user else {}
        print(f"User fixture Python runs as UID {uid}, GID {gid}; production root guards remain enabled", flush=True)
        result = subprocess.run([sys.executable, "-B", *arguments], env=env, **identity)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
