"""Entrypoint orchestration with mocked Git and pinned Python helper processes.

These tests make no GitHub requests and perform no repository publication.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/migrate-fresh-repository.sh"
PIN = "a" * 40
DESTINATION = "egohygiene/deckystream"
PRIVATE = "fixture-private-token-never-echo"

HELPER = r'''
import json,os,subprocess,sys,time
from pathlib import Path
args=sys.argv[1:]
kind="export" if "export-project-history" in __file__ else "prepare"
with open(os.environ["FIXTURE_EVENTS"],"a") as events:
    events.write(json.dumps({"tool":kind,"arguments":args})+"\n")
if kind=="prepare" and os.environ.get("FIXTURE_GRANDCHILD"):
    subprocess.Popen([sys.executable,"-c", "import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(os.environ['FIXTURE_GRANDCHILD']+'.ready').write_text('ready');time.sleep(1);Path(os.environ['FIXTURE_GRANDCHILD']).write_text('must never finish after interruption')"])
    time.sleep(20)
if os.environ.get("FIXTURE_BLOCK")==kind:
    time.sleep(20)
if os.environ.get("FIXTURE_FAIL")==kind:
    print(os.environ["FIXTURE_PRIVATE"],file=sys.stderr)
    raise SystemExit(19)
def argument(flag): return args[args.index(flag)+1]
output=Path(argument("--output"))
pin=os.environ["FIXTURE_PIN"]
if kind=="export":
    if os.environ.get("FIXTURE_BAD_HISTORY"): pin="b"*40
    output.write_text(json.dumps({"schema":"obsgod.project-history/v1","purpose":"retirement-backup","retirement_performed":False,
      "repository":{"id":10,"full_name":"szmyty/obsgod","visibility":"public","default_branch_head":pin}}))
else:
    output.mkdir(mode=0o700)
    value={"schema":"obsgod.fresh-repository/v1","source_sha":pin,"destination":argument("--destination")}
    filename="plan.json"
    if "--apply" in args:
        filename="apply-receipt.json"
        value.update({"state":"snapshot-pushed-post-migration-tests-unrun","push_verified":True})
    (output/filename).write_text(json.dumps(value))
    print(os.environ["FIXTURE_PRIVATE"])
'''

GIT = r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
source=None
while args and (args[0].startswith("-") or args[0]=="-C"):
    flag=args.pop(0)
    if flag in ("-c","-C","--git-dir","--work-tree"):
        value=args.pop(0)
        if flag=="-C": source=Path(value)
with open(os.environ["FIXTURE_EVENTS"],"a") as events:
    events.write(json.dumps({"tool":"git","arguments":args,"raw_arguments":sys.argv[1:],
      "override_keys":[key for key in ("GIT_DIR","GIT_WORK_TREE","GIT_OBJECT_DIRECTORY","GIT_COMMON_DIR","GIT_ALTERNATE_OBJECT_DIRECTORIES") if key in os.environ],
      "index":os.environ.get("GIT_INDEX_FILE"),
      "replacement":os.environ.get("GIT_NO_REPLACE_OBJECTS"),"ca":os.environ.get("SSL_CERT_FILE"),"proxy":os.environ.get("HTTPS_PROXY")})+"\n")
if args[:2]==["remote","get-url"]:
    rewrite=os.environ.get("FIXTURE_REWRITE")
    if rewrite=="fetch" and "--push" not in args or rewrite=="push" and "--push" in args:
        print("https://unrelated.invalid/repository.git")
    else: print("https://github.com/szmyty/obsgod.git")
elif args[0]=="ls-remote":
    pin="b"*40 if os.environ.get("FIXTURE_BAD_REMOTE_PIN") else os.environ["FIXTURE_PIN"]
    print("ref: refs/heads/master\tHEAD\n"+pin+"\tHEAD")
elif args[0]=="fetch" and os.environ.get("FIXTURE_FAIL")=="fetch":
    print(os.environ["FIXTURE_PRIVATE"],file=sys.stderr)
    raise SystemExit(17)
elif args[0]=="checkout":
    helpers=source/"scripts"
    helpers.mkdir()
    for name in ("export-project-history.py","prepare-fresh-repository.py"):
        (helpers/name).write_text(os.environ["FIXTURE_HELPER"])
elif args[0]=="rev-parse":
    print(str(source) if "--show-toplevel" in args else os.environ["FIXTURE_PIN"])
elif args[0]=="status":
    if os.environ.get("FIXTURE_DIRTY") or os.environ.get("FIXTURE_DIRTY_AFTER_EXPORT") and (source.parent/"public-history.json").exists():
        print("?? unexpected-file")
'''


class Entrypoint(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="migration-entrypoint-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        git = self.bin / "git"
        git.write_text("#!" + sys.executable + "\n" + GIT)
        git.chmod(0o700)
        self.events = self.base / "events.jsonl"
        self.workspace = self.base / "retained workspace"
        self.environment = {**os.environ, "PATH": str(self.bin), "FIXTURE_EVENTS": str(self.events),
                            "FIXTURE_PIN": PIN, "FIXTURE_HELPER": HELPER, "FIXTURE_PRIVATE": PRIVATE,
                            "SSL_CERT_FILE": "preserved-ca-fixture", "HTTPS_PROXY": "preserved-proxy-fixture"}
        self.bash = shutil.which("bash")

    def commands(self):
        return [json.loads(row) for row in self.events.read_text().splitlines()] if self.events.exists() else []

    def run_entrypoint(self, *extra, environment=None, workspace=True):
        command = [self.bash, str(SCRIPT), "--source-sha", PIN, "--destination", DESTINATION]
        if workspace:
            command += ["--workspace", str(self.workspace)]
        result = subprocess.run(command + list(extra), env=environment or self.environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        self.assertNotIn(PRIVATE, result.stdout + result.stderr)
        return result

    def gh(self):
        (self.bin / "gh").write_text("#!/bin/sh\nexit 0\n")
        (self.bin / "gh").chmod(0o700)

    def test_default_preparation_needs_no_gh_and_forwards_no_apply_or_inspection(self):
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.commands()
        helpers = [row for row in calls if row["tool"] != "git"]
        self.assertEqual([row["tool"] for row in helpers], ["export", "prepare"])
        arguments = helpers[-1]["arguments"]
        self.assertNotIn("--apply", arguments)
        self.assertNotIn("--inspect-destination", arguments)
        self.assertIn("--stage-canonical-identity", arguments)
        self.assertEqual(arguments[arguments.index("--destination") + 1], DESTINATION)
        self.assertEqual(arguments[arguments.index("--source-sha") + 1], PIN)
        self.assertEqual(helpers[0]["arguments"], ["--repository", "szmyty/obsgod", "--purpose", "retirement-backup", "--output", str(self.workspace / "public-history.json")])
        for row in (row for row in calls if row["tool"] == "git"):
            self.assertNotIn(row["arguments"][0], ("push", "tag"))
            if row["arguments"][0] == "config":
                self.assertEqual(row["arguments"], ["config", "--local", "core.worktree", str(self.workspace / "source")])
        state = json.loads((self.workspace / "entrypoint-state.json").read_text())
        self.assertEqual(state["state"], "prepared-no-github-writes")
        self.assertEqual((self.workspace / "steps.log").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.workspace.stat().st_mode & 0o777, 0o700)
        self.assertIn(PRIVATE, (self.workspace / "steps.log").read_text())

    def test_explicit_apply_is_forwarded_only_after_export_and_clean_pin_checks(self):
        self.gh()
        result = self.run_entrypoint("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.commands()
        export_index = next(i for i, row in enumerate(calls) if row["tool"] == "export")
        prepare_index = next(i for i, row in enumerate(calls) if row["tool"] == "prepare")
        self.assertLess(export_index, prepare_index)
        self.assertTrue(any(row["tool"] == "git" and row["arguments"][0] == "status" for row in calls[export_index + 1:prepare_index]))
        self.assertIn("--apply", calls[prepare_index]["arguments"])
        self.assertNotIn("--inspect-destination", calls[prepare_index]["arguments"])
        self.assertEqual(json.loads((self.workspace / "entrypoint-state.json").read_text())["state"], "guarded-apply-finished-tests-unrun")

    def test_inspection_is_explicit_and_requires_gh_without_authorizing_apply(self):
        for flag in ("--inspect-destination", "--apply"):
            result = self.run_entrypoint(flag)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.events.exists())
        self.gh()
        result = self.run_entrypoint("--inspect-destination")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = next(row["arguments"] for row in self.commands() if row["tool"] == "prepare")
        self.assertIn("--inspect-destination", args)
        self.assertNotIn("--apply", args)

    def test_git_overrides_are_removed_while_ca_proxy_and_explicit_sha1_are_preserved(self):
        environment = {**self.environment, "GIT_DIR": "/caller/repo", "GIT_INDEX_FILE": "/caller/index", "GIT_WORK_TREE": "/caller/work", "GIT_COMMON_DIR": "/caller/common", "GIT_OBJECT_DIRECTORY": "/caller/objects", "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/caller/alternates", "GIT_DEFAULT_HASH": "sha256"}
        result = self.run_entrypoint(environment=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [row for row in self.commands() if row["tool"] == "git"]
        self.assertIn("--object-format=sha1", calls[0]["arguments"])
        for call in calls:
            self.assertEqual(call["override_keys"], [])
            self.assertEqual(call["replacement"], "1")
            self.assertEqual(call["index"], str(self.workspace / "source/.git/index"))
            self.assertIn("--git-dir", call["raw_arguments"])
            self.assertIn("--work-tree", call["raw_arguments"])
            self.assertIn("core.worktree=" + str(self.workspace / "source"), call["raw_arguments"])
            self.assertEqual(call["ca"], "preserved-ca-fixture")
            self.assertEqual(call["proxy"], "preserved-proxy-fixture")
            self.assertIn("core.hooksPath=/dev/null", call["raw_arguments"])
        fetch = next(row for row in calls if row["arguments"][0] == "fetch")
        self.assertEqual(fetch["arguments"], ["fetch", "--no-tags", "--depth=1", "origin", PIN])
        self.assertIn("http.https://github.com/szmyty/obsgod.git.followRedirects=false", fetch["raw_arguments"])

    def test_real_disposable_git_cannot_write_inherited_caller_worktree_or_index(self):
        real_git = shutil.which("git")
        fixture = self.base / "local-public-source-fixture"
        fixture.mkdir()
        creator_environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        creator_environment.update({"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
        def create_git(*args):
            return subprocess.run([real_git, "-c", "user.name=Fixture Owner", "-c", "user.email=fixture@example.invalid", "-C", str(fixture), *args],
                                  env=creator_environment, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        create_git("init", "--template=", "--object-format=sha1")
        (fixture / "scripts").mkdir()
        for name in ("export-project-history.py", "prepare-fresh-repository.py"):
            (fixture / "scripts" / name).write_text(HELPER)
        (fixture / "tracked.txt").write_text("remote source must stay inside its private clone")
        create_git("add", "--all")
        create_git("commit", "-m", "Local fixture only")
        pin = create_git("rev-parse", "HEAD").decode().strip()
        # Only replace public network reads with a local fixture. All repository
        # initialization, fetch/index writes and checkout use the real Git.
        (self.bin / "git").write_text("#!" + sys.executable + "\n" + r'''
import os,subprocess,sys
args=sys.argv[1:]
offset=0
while args[offset].startswith("-"):
    offset += 2 if args[offset] in ("-c","-C","--git-dir","--work-tree") else 1
if args[offset]=="ls-remote":
    print("ref: refs/heads/master\tHEAD\n"+os.environ["FIXTURE_PIN"]+"\tHEAD")
else:
    if args[offset]=="fetch": args[args.index("origin",offset)]=os.environ["FIXTURE_LOCAL_SOURCE"]
    raise SystemExit(subprocess.run([os.environ["FIXTURE_REAL_GIT"],*args]).returncode)
''')
        caller = self.base / "caller files"
        caller.mkdir()
        sentinel = caller / "tracked.txt"
        sentinel.write_text("caller must survive")
        index = caller / "caller-index"
        index.write_bytes(b"caller-index-must-survive")
        objects = caller / "objects"
        objects.mkdir()
        global_config = self.base / "caller-global-config"
        global_config.write_text("[core]\n\tworktree = " + str(caller) + "\n[init]\n\tdefaultObjectFormat = sha256\n")
        original_config = global_config.read_bytes()
        environment = {**self.environment, "FIXTURE_PIN": pin, "FIXTURE_REAL_GIT": real_git, "FIXTURE_LOCAL_SOURCE": str(fixture),
                       "GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(caller),
                       "GIT_DIR": str(fixture / ".git"), "GIT_WORK_TREE": str(caller), "GIT_INDEX_FILE": str(index),
                       "GIT_OBJECT_DIRECTORY": str(objects), "GIT_DEFAULT_HASH": "sha256"}
        result = self.run_entrypoint("--source-sha", pin, environment=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(), "caller must survive")
        self.assertEqual(index.read_bytes(), b"caller-index-must-survive")
        self.assertEqual(list(objects.iterdir()), [])
        self.assertEqual(global_config.read_bytes(), original_config)
        self.assertEqual((self.workspace / "source/tracked.txt").read_text(), "remote source must stay inside its private clone")
        self.assertTrue((self.workspace / "source/.git/index").is_file())

    def test_invalid_pin_destination_or_abbreviated_apply_fails_before_git(self):
        for extra in (("--source-sha", "HEAD"), ("--source-sha", "b" * 64), ("--destination", "other-owner/deckystream"), ("--destination", "egohygiene/decky-stream"), ("--app",)):
            with self.subTest(extra=extra):
                result = self.run_entrypoint(*extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.events.exists())
                self.assertFalse(self.workspace.exists())

    def test_unsafe_workspace_paths_are_preserved_without_git(self):
        self.workspace.mkdir()
        sentinel = self.workspace / "keep"
        sentinel.write_text("preserve")
        for path in (self.workspace, self.base / ".." / "escape", self.base / "linked/new"):
            (self.base / "linked").symlink_to(self.base) if not (self.base / "linked").exists() else None
            with self.subTest(path=path):
                result = self.run_entrypoint("--workspace", str(path))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.events.exists())
        self.assertEqual(sentinel.read_text(), "preserve")
        unsafe_parent = self.base / "unsafe-parent"
        unsafe_parent.mkdir(mode=0o777)
        unsafe_parent.chmod(0o777)
        result = self.run_entrypoint("--workspace", str(unsafe_parent / "new"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((unsafe_parent / "new").exists())

    def test_remote_rewrite_or_non_default_pin_prevents_fetch_and_helper_execution(self):
        for key, value in (("FIXTURE_REWRITE", "fetch"), ("FIXTURE_REWRITE", "push"), ("FIXTURE_BAD_REMOTE_PIN", "1")):
            self.workspace = self.base / (key + value)
            self.events = self.base / (key + value + ".jsonl")
            environment = {**self.environment, "FIXTURE_EVENTS": str(self.events), key: value}
            with self.subTest(key=key, value=value):
                result = self.run_entrypoint(environment=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(row["tool"] != "git" or row["arguments"][0] == "fetch" for row in self.commands()))
                self.assertTrue(self.workspace.exists())

    def test_fetch_export_bad_history_and_source_changes_never_forward_apply(self):
        self.gh()
        cases = (("FIXTURE_FAIL", "fetch"), ("FIXTURE_FAIL", "export"), ("FIXTURE_BAD_HISTORY", "1"), ("FIXTURE_DIRTY_AFTER_EXPORT", "1"), ("FIXTURE_DIRTY", "1"))
        for key, value in cases:
            self.workspace = self.base / (key + value)
            self.events = self.base / (key + value + ".jsonl")
            environment = {**self.environment, "FIXTURE_EVENTS": str(self.events), key: value}
            with self.subTest(key=key, value=value):
                result = self.run_entrypoint("--apply", environment=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(row["tool"] == "prepare" for row in self.commands()))
                self.assertEqual(json.loads((self.workspace / "entrypoint-state.json").read_text())["state"], "stopped-state-preserved")
                self.assertTrue((self.workspace / "steps.log").exists())

    def test_guarded_failure_keeps_public_history_and_pinned_checkout(self):
        self.gh()
        result = self.run_entrypoint("--apply", environment={**self.environment, "FIXTURE_FAIL": "prepare"})
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.workspace / "public-history.json").exists())
        self.assertTrue((self.workspace / "source/scripts/prepare-fresh-repository.py").exists())
        self.assertIn("Preserved workspace", result.stderr)

    def test_default_workspace_is_unique_private_and_retained(self):
        temporary_parent = self.base / "temporary-parent"
        temporary_parent.mkdir()
        result = self.run_entrypoint(workspace=False, environment={**self.environment, "TMPDIR": str(temporary_parent)})
        self.assertEqual(result.returncode, 0, result.stderr)
        children = list(temporary_parent.iterdir())
        self.assertEqual(len(children), 1)
        self.assertTrue((children[0] / "entrypoint-state.json").exists())
        self.assertEqual(children[0].stat().st_mode & 0o777, 0o700)

    def test_interruption_keeps_state_checkout_and_private_log(self):
        command = [self.bash, str(SCRIPT), "--source-sha", PIN, "--destination", DESTINATION, "--workspace", str(self.workspace)]
        process = subprocess.Popen(command, env={**self.environment, "FIXTURE_BLOCK": "export"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any(row["tool"] == "export" for row in self.commands()):
                break
            time.sleep(0.01)
        else:
            self.fail("Mock export never started")
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        self.assertNotIn(PRIVATE, stdout + stderr)
        self.assertTrue((self.workspace / "source/scripts/export-project-history.py").exists())
        state = json.loads((self.workspace / "entrypoint-state.json").read_text())
        self.assertEqual(state["state"], "stopped-state-preserved")
        self.assertEqual(state["stage"], "public-history-export")
        self.assertFalse(any(row["tool"] == "prepare" for row in self.commands()))

    def test_apply_interruption_stops_helper_descendants_before_reporting_stopped(self):
        self.gh()
        sentinel = self.base / "late-descendant-write"
        ready = self.base / "late-descendant-write.ready"
        command = [self.bash, str(SCRIPT), "--source-sha", PIN, "--destination", DESTINATION, "--workspace", str(self.workspace), "--apply"]
        process = subprocess.Popen(command, env={**self.environment, "FIXTURE_GRANDCHILD": str(sentinel)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if ready.exists():
                break
            time.sleep(0.01)
        else:
            self.fail("Mock guarded helper descendant never started")
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        self.assertNotIn(PRIVATE, stdout + stderr)
        time.sleep(1.2)
        self.assertFalse(sentinel.exists(), "A helper-owned descendant continued after interruption")
        state = json.loads((self.workspace / "entrypoint-state.json").read_text())
        self.assertEqual(state["state"], "stopped-state-preserved")
        self.assertEqual(state["stage"], "guarded-apply")
        self.assertTrue((self.workspace / "public-history.json").exists())


if __name__ == "__main__":
    unittest.main()
