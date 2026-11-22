#!/usr/bin/env bash
# Run with Bash; Python supplies exact argv, process, and path handling.
set -euo pipefail
exec python3 - "$@" <<'PY'
"""Fetch one pinned public source, export history, then prepare or explicitly apply.

All workspaces and private logs survive success, failure and interruption.
No packages, global configuration, issues, releases or automatic cleanup.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile

SOURCE = "https://github.com/szmyty/obsgod.git"
DESTINATION = "egohygiene/deckystream"
SHA = re.compile(r"[0-9a-f]{40}\Z")
GIT_OVERRIDES = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_NAMESPACE", "GIT_QUARANTINE_PATH", "GIT_PREFIX")


class Stopped(RuntimeError):
    def __init__(self, message, status=1):
        super().__init__(message)
        self.status = status


def interrupted(number, frame):
    raise Stopped("Interrupted; inspect the retained state before another action.", 128 + number)


def safe_path(value):
    path = Path(value).absolute()
    if (".." in path.parts or any(ord(c) < 32 or ord(c) == 127 for c in str(path))
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise Stopped("Workspace paths cannot traverse symlinks, parent segments or control characters.")
    return path


def workspace_path(value):
    if value is None:
        # Resolve a platform's temporary-directory alias before making a unique
        # private child; subsequent guarded-tool paths then contain no symlinks.
        parent = Path(tempfile.gettempdir()).resolve(strict=True)
        return safe_path(tempfile.mkdtemp(prefix="deckystream-migration-", dir=parent))
    path = safe_path(value)
    parent = path.parent
    if (os.path.lexists(path) or not parent.is_dir() or parent.stat().st_uid != os.getuid()
            or parent.stat().st_mode & 0o022):
        raise Stopped("Use a new workspace inside an existing private, owned parent; existing paths are preserved.")
    path.mkdir(mode=0o700)
    return path


def save_state(workspace, state):
    temporary = workspace / ".entrypoint-state.json"
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(state, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, workspace / "entrypoint-state.json")
    descriptor = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def stop_process_group(process):
    """Stop helper-owned Git/gh descendants before reporting interruption.

    A server may already have accepted a request; retained receipts still carry
    that uncertainty. Never leave local descendants continuing after our exit.
    """
    previous = {number: signal.signal(number, signal.SIG_IGN) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # The leader can exit before a descendant that ignored SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main():
    parser = argparse.ArgumentParser(prog="migrate-fresh-repository.sh", description=__doc__, allow_abbrev=False)
    parser.add_argument("--source-sha", required=True, help="exact full lowercase source default-branch commit")
    parser.add_argument("--destination", required=True, help="selected egohygiene/deckystream only")
    parser.add_argument("--workspace", help="new retained private directory; default is a unique temporary directory")
    parser.add_argument("--inspect-destination", action="store_true", help="optional authenticated read-only destination inspection")
    parser.add_argument("--apply", action="store_true", help="explicitly allow the existing guarded tool to create/push the fresh destination")
    args = parser.parse_args()
    workspace = None
    state = {}
    try:
        if not SHA.fullmatch(args.source_sha):
            raise Stopped("--source-sha must be one full lowercase 40-character SHA1.")
        if args.destination != DESTINATION:
            raise Stopped("This entrypoint supports only the selected egohygiene/deckystream destination.")
        if not shutil.which("git"):
            raise Stopped("Git is required; no installation was attempted.")
        if (args.apply or args.inspect_destination) and not shutil.which("gh"):
            raise Stopped("Existing gh authentication/tools are required for apply or explicit inspection; no installation was attempted.")
        os.umask(0o077)
        workspace = workspace_path(args.workspace)
        state = {"schema": "obsgod.migration-entrypoint/v1", "state": "workspace-created",
                 "stage": "initialization", "source_sha": args.source_sha, "destination": DESTINATION,
                 "mode": "apply" if args.apply else "preparation", "workspace": str(workspace),
                 "recovery": "Keep this workspace. Inspect entrypoint-state.json and result/apply-receipt.json before another action; a failed network response can follow a successful remote mutation. Private steps.log may contain credentials: do not publish it."}
        save_state(workspace, state)
        print("Retained private workspace: " + str(workspace), flush=True)
        environment = os.environ.copy()
        for key in GIT_OVERRIDES:
            environment.pop(key, None)
        environment["GIT_NO_REPLACE_OBJECTS"] = "1"
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        environment["GIT_TERMINAL_PROMPT"] = "0"
        source = workspace / "source"
        history = workspace / "public-history.json"
        output = workspace / "result"
        with (workspace / "steps.log").open("xb") as log:
            def execute(command, stage, timeout=180, child_environment=None):
                state["stage"] = stage
                save_state(workspace, state)
                process = subprocess.Popen(command, env=child_environment or environment, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=log, start_new_session=True)
                try:
                    captured_stdout, _ = process.communicate(timeout=timeout)
                except BaseException as error:
                    stop_process_group(process)
                    if isinstance(error, subprocess.TimeoutExpired):
                        if error.stdout:
                            log.write(error.stdout)
                        raise Stopped("A step timed out; inspect the retained private logs and receipts.") from None
                    raise
                finally:
                    process.stdout.close()
                log.write(captured_stdout)
                log.flush()
                if process.returncode:
                    stop_process_group(process)
                    status = process.returncode if process.returncode > 0 else 128 - process.returncode
                    raise Stopped("A step stopped; inspect the retained private logs and receipts.", status)
                return captured_stdout

            def git(*arguments):
                git_environment = {**environment, "GIT_INDEX_FILE": str(source / ".git/index")}
                return execute(["git", "--no-pager", "--git-dir", str(source / ".git"), "--work-tree", str(source),
                                "-c", "core.worktree=" + str(source), "-c", "core.bare=false",
                                "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                                "-c", "http.followRedirects=false", "-c", "http." + SOURCE + ".followRedirects=false",
                                "-C", str(source), *arguments], "source-preflight", child_environment=git_environment)

            print("Fetching the exact public source pin.", flush=True)
            source.mkdir(mode=0o700)
            git("init", "--template=", "--object-format=sha1")
            # This is the newly created private clone's own configuration. It
            # also keeps the existing guard's independent root check meaningful.
            git("config", "--local", "core.worktree", str(source))
            git("remote", "add", "origin", SOURCE)
            for options in (("--all",), ("--all", "--push")):
                if git("remote", "get-url", *options, "origin").decode().splitlines() != [SOURCE]:
                    raise Stopped("Git URL rewriting or multiple source URLs were detected; no source was fetched.")
            advertised = git("ls-remote", "--symref", "--exit-code", "origin", "HEAD").decode().splitlines()
            heads = [row for row in advertised if re.fullmatch(r"[0-9a-f]{40}\tHEAD", row)]
            symbolic = [row for row in advertised if re.fullmatch(r"ref: refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,254}\tHEAD", row)]
            if len(heads) != 1 or heads[0] != args.source_sha + "\tHEAD" or len(symbolic) != 1:
                raise Stopped("The requested source pin must equal the exact public repository's current default-branch HEAD.")
            git("fetch", "--no-tags", "--depth=1", "origin", args.source_sha)
            git("checkout", "--detach", args.source_sha)
            if (git("rev-parse", "HEAD").decode().strip() != args.source_sha
                    or git("rev-parse", "--show-toplevel").decode().strip() != str(source)
                    or git("status", "--porcelain=v1", "--untracked-files=all")):
                raise Stopped("Pinned checkout identity or cleanliness is unconfirmed.")
            helpers = [source / "scripts/export-project-history.py", source / "scripts/prepare-fresh-repository.py"]
            if any(not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)) for path in helpers):
                raise Stopped("The exact source pin lacks regular migration helper files.")
            print("Capturing public tracker history; private chat and credentials are excluded.", flush=True)
            execute([sys.executable, str(helpers[0]), "--repository", "szmyty/obsgod", "--purpose", "retirement-backup",
                     "--output", str(history)], "public-history-export", timeout=900)
            if not history.is_file() or history.is_symlink() or history.stat().st_size > 32 * 1024 * 1024:
                raise Stopped("The public history export is missing or unsafe; guarded execution was not started.")
            captured = json.loads(history.read_bytes())
            if not isinstance(captured, dict) or not isinstance(captured.get("repository"), dict):
                raise Stopped("The public history export shape is unsupported; guarded execution was not started.")
            repository = captured.get("repository", {})
            if (captured.get("schema") != "obsgod.project-history/v1" or captured.get("purpose") != "retirement-backup"
                    or captured.get("retirement_performed") is not False or repository.get("full_name") != "szmyty/obsgod"
                    or repository.get("visibility") != "public" or repository.get("default_branch_head") != args.source_sha
                    or type(repository.get("id")) is not int or repository["id"] <= 0):
                raise Stopped("The public history export does not match the exact source pin; guarded execution was not started.")
            # Recheck the copied source after export, before even forwarding an
            # explicit --apply. Outputs live outside this checkout.
            if git("rev-parse", "HEAD").decode().strip() != args.source_sha or git("status", "--porcelain=v1", "--untracked-files=all"):
                raise Stopped("Source changed during public history capture; guarded execution was not started.")
            for options in (("--all",), ("--all", "--push")):
                if git("remote", "get-url", *options, "origin").decode().splitlines() != [SOURCE]:
                    raise Stopped("Source origin changed during public history capture; guarded execution was not started.")
            print("Running guarded " + ("apply" if args.apply else "preparation") + "; final product/device tests remain unrun.", flush=True)
            command = [sys.executable, str(helpers[1]), "--source", str(source), "--source-sha", args.source_sha,
                       "--destination", DESTINATION, "--history-backup", str(history), "--output", str(output),
                       "--stage-canonical-identity"]
            if args.inspect_destination:
                command.append("--inspect-destination")
            if args.apply:
                command.append("--apply")
            execute(command, "guarded-apply" if args.apply else "guarded-preparation", timeout=900)
        result_path = output / ("apply-receipt.json" if args.apply else "plan.json")
        result = json.loads(result_path.read_bytes())
        if (not isinstance(result, dict) or result.get("schema") != "obsgod.fresh-repository/v1" or result.get("source_sha") != args.source_sha
                or result.get("destination") != DESTINATION
                or (args.apply and (result.get("push_verified") is not True or result.get("state") != "snapshot-pushed-post-migration-tests-unrun"))):
            raise Stopped("Guarded result identity/outcome is unconfirmed; inspect the retained receipts.")
        state.update({"state": "guarded-apply-finished-tests-unrun" if args.apply else "prepared-no-github-writes", "stage": "finished", "result": str(result_path)})
        save_state(workspace, state)
        print("Result: " + str(result_path), flush=True)
        print("Source, snapshots and private logs are retained. Device, CI, rights and release decisions remain separate.", flush=True)
        return 0
    except (Stopped, OSError, ValueError, KeyError, TypeError) as error:
        status = error.status if isinstance(error, Stopped) else 1
        if workspace is not None:
            state.update({"state": "stopped-state-preserved", "exit_status": status})
            try:
                save_state(workspace, state)
            except OSError:
                pass
        print("Migration entrypoint stopped: " + (str(error) if isinstance(error, Stopped) else "Inspect local tools, paths and retained receipts; raw tool output is withheld."), file=sys.stderr)
        if workspace is not None:
            print("Preserved workspace: " + str(workspace), file=sys.stderr)
        return status


signal.signal(signal.SIGINT, interrupted)
signal.signal(signal.SIGTERM, interrupted)
raise SystemExit(main())
PY
