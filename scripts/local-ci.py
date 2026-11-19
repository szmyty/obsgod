#!/usr/bin/env python3
"""Install the checksum-pinned act client or run an explicit local CI job.

No tokens, .env, .input or .secrets files are implicitly passed to workflows.
Only the managed local Docker socket is used; existing Docker proxy/registry
configuration is retained. Logs remain local and must be reviewed before sharing.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.97"
IMAGE = "ghcr.io/catthehacker/ubuntu:act-24.04@sha256:19619a010b204f44c5340bff7d39b68551109fe6a56a53f75201ea91e05d4270"
APT_CA_CONFIG = b'Acquire::https::CaInfo "/run/obsgod-ca.pem";\n'
ACT_SHA256 = {"x86_64": ("x86_64", "67b4976a56f33ea7870b798912e738ec44eef38e7578ae7b532f2def1c73a5ad"),
              "aarch64": ("arm64", "44d48e3d4a6409053fdec6fc6518322467d79a2d5be8f72c021b0421e2ac113d")}
JOBS = {"build": ("build.yml", "build", "push"),
        "coverage": ("coverage.yml", "coverage", "push"),
        "lint": ("lint.yml", "golangci", "push"),
        "snapshot": ("goreleaser.yml", "goreleaser", "push"),
        "docs": ("docs-preview.yml", "build-preview", "workflow_dispatch"),
        "candidate": ("steam-deck.yml", "candidate", "workflow_dispatch")}
MATRIX_ORDER = ("lint", "build", "coverage", "snapshot", "docs", "candidate")
RESOURCE_SPEC = importlib.util.spec_from_file_location("local_ci_resources", ROOT / "scripts/local-ci-resources.py")
RESOURCES = importlib.util.module_from_spec(RESOURCE_SPEC)
RESOURCE_SPEC.loader.exec_module(RESOURCES)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def redact_log_value(value):
    """Filter decoded records, including URLs escaped by JSON log encoding."""
    if isinstance(value, str):
        return re.sub(r"(https?:(?:\\*/){2})[^\s/@]+@", r"\1[redacted]@", value, flags=re.IGNORECASE)
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    if isinstance(value, dict):
        filtered = {}
        for key, item in value.items():
            public_key = redact_log_value(key)
            unique_key = public_key
            duplicate = 2
            # Distinct private URLs can redact to the same public key. Retain
            # every value, including collisions with an existing suffix label.
            while unique_key in filtered:
                unique_key = f"{public_key} [redacted key {duplicate}]"
                duplicate += 1
            filtered[unique_key] = redact_log_value(item)
        return filtered
    return value


def sanitize_log_line(line):
    """Keep structured act records valid; retain legacy text as a fallback."""
    try:
        record = json.loads(line)
    except ValueError:
        return redact_log_value(line), False
    newline = "\n" if line.endswith("\n") else ""
    return json.dumps(redact_log_value(record), ensure_ascii=False, separators=(",", ":")) + newline, True


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def install(prefix):
    if platform.system() != "Linux" or platform.machine() not in ACT_SHA256:
        raise SystemExit("This installer supports Linux amd64/arm64; native macOS/Windows remain separate gates")
    arch, expected = ACT_SHA256[platform.machine()]
    url = f"https://github.com/nektos/act/releases/download/v{VERSION}/act_Linux_{arch}.tar.gz"
    data = urllib.request.urlopen(url, timeout=90).read()
    if sha(data) != expected:
        raise SystemExit("act archive checksum mismatch; nothing installed")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.getmember("act")
        if not member.isfile() or member.size > 100_000_000:
            raise SystemExit("Unexpected act archive member")
        binary = archive.extractfile(member).read()
    prefix.mkdir(parents=True, exist_ok=True)
    target = prefix / "act"
    if target.is_symlink():
        raise SystemExit("Refusing to replace a symlink")
    target.write_bytes(binary)
    target.chmod(0o755)
    print(f"Installed act {VERSION}; verified archive sha256 {expected}")
    subprocess.run([str(target), "--version"], check=True)


def network_options(state, temporary=None):
    # Bind the combined public CA bundle, never credentials or Docker config.
    ca = Path("/etc/ssl/certs/ca-certificates.crt")
    if not ca.is_file():
        raise SystemExit("A trusted combined CA bundle is required")
    temporary = temporary or state / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    apt_configuration = state / "apt-cloud-ca.conf"
    if apt_configuration.is_symlink():
        raise SystemExit("Refusing symlink APT trust configuration")
    apt_configuration.write_bytes(APT_CA_CONFIG)
    apt_configuration.chmod(0o644)
    options = ["--mount", f"type=bind,src={ca},dst=/run/obsgod-ca.pem,readonly",
               "--mount", f"type=bind,src={apt_configuration},dst=/etc/apt/apt.conf.d/99-obsgod-cloud-ca,readonly",
               "--mount", f"type=bind,src={temporary},dst={temporary}"]
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        host = urllib.parse.urlsplit(os.environ.get(key, "")).hostname
        if host:
            try:
                address = socket.gethostbyname(host)
            except OSError:
                raise SystemExit("Configured proxy host does not resolve; preserve configuration and repair runtime DNS")
            options += ["--add-host", f"{host}:{address}"]
    return shlex.join(options)


def prepare_actions(state):
    """Fetch the exact pinned action trees over HTTPS, avoiding go-git auth.

    Managed injected Git credentials are available to HTTPS/API calls here, but
    act's embedded go-git transport cannot necessarily consume that integration.
    This changes source acquisition only; it executes the original pinned action.
    """
    pins = set()
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text()
        for repository, revision in re.findall(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})", text):
            pins.add((repository, revision))
    mappings, receipts = [], []
    for repository, revision in sorted(pins):
        target = state / "action-sources" / (repository.replace("/", "-") + "-" + revision)
        receipt_path = target.with_suffix(".json")
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_bytes())
            actual = {p.relative_to(target).as_posix(): sha(p.read_bytes()) for p in sorted(target.rglob("*")) if p.is_file() and not p.is_symlink()}
            links = {p.relative_to(target).as_posix(): os.readlink(p) for p in sorted(target.rglob("*")) if p.is_symlink()}
            if links != receipt.get("symlinks", {}) or actual != receipt["files"]:
                raise SystemExit("Cached action source differs from verified receipt; inspect and repair " + str(target))
        else:
            url = f"https://api.github.com/repos/{repository}/commits/{revision}"
            commit = json.load(urllib.request.urlopen(url, timeout=90))
            if commit.get("sha") != revision:
                raise SystemExit("Action commit API identity mismatch")
            data = urllib.request.urlopen(f"https://codeload.github.com/{repository}/tar.gz/{revision}", timeout=90).read()
            files, links, modes = {}, {}, {}
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if member.isdir():
                        continue
                    parts = member.name.split("/")
                    if not (member.isfile() or member.issym()) or len(parts) < 2 or any(p in ("", ".", "..") for p in parts) or member.size > 64_000_000:
                        raise SystemExit("Unsafe pinned action archive")
                    name = "/".join(parts[1:])
                    if name in files or name in links:
                        raise SystemExit("Duplicate pinned action member")
                    if member.issym():
                        link = member.linkname
                        if Path(link).is_absolute() or not (target / name).parent.joinpath(link).resolve().is_relative_to(target.resolve()):
                            raise SystemExit("Unsafe pinned action symlink")
                        links[name] = link
                        continue
                    files[name] = archive.extractfile(member).read()
                    modes[name] = 0o755 if member.mode & 0o111 else 0o644
            target.mkdir(parents=True, exist_ok=False)
            for name, content in files.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                path.chmod(modes[name])
            for name, link in links.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(link)
            receipt = {"repository": repository, "revision": revision, "git_tree": commit["commit"]["tree"]["sha"],
                       "archive_sha256": sha(data), "acquisition": "GitHub API commit and exact codeload tree over authenticated HTTPS",
                       "files": {name: sha(content) for name, content in sorted(files.items())}, "symlinks": links}
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        mappings += ["--local-repository", f"{repository}@{revision}={target}"]
        receipts.append({key: receipt[key] for key in ("repository", "revision", "git_tree", "archive_sha256")})
    return mappings, receipts


def matrix(args, state):
    """A fresh, serial evidence session; interrupted attempts are never resumed."""
    scratch_base = RESOURCES.private_directory(args.scratch, ROOT)
    session = state / "sessions" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + os.urandom(6).hex())
    session.mkdir(mode=0o700, parents=True)
    scratch = scratch_base / session.name
    scratch.mkdir(mode=0o700)
    revision = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if git("status", "--porcelain"):
        raise SystemExit("Matrix requires a committed clean source revision")
    receipt = {"schema_version": 1, "revision": revision, "source_tree": tree,
               "profile": "constrained", "state": str(session), "scratch": str(scratch),
               "completed": False, "result": "running",
               "jobs": [{"action": action, "result": "unrun"} for action in MATRIX_ORDER]}
    path = session / "session.json"
    RESOURCES.write_json(path, receipt)
    print("New local matrix session: " + str(session), flush=True)
    probe = RESOURCES.allocate_attempt(scratch, "preflight", ROOT)
    measured = RESOURCES.preflight(ROOT, probe, IMAGE, revision)
    receipt["preflight"] = str(probe / "preflight.json")
    if measured["status"] != "passed":
        receipt.update(result="unavailable", reason="Resource preflight refused before any workflow")
        RESOURCES.write_json(path, receipt)
        print(json.dumps(measured, sort_keys=True), flush=True)
        return 3
    for job in receipt["jobs"]:
        if git("rev-parse", "HEAD") != revision or git("status", "--porcelain"):
            receipt.update(result="failed", reason="Frozen source changed; later jobs remain unrun")
            RESOURCES.write_json(path, receipt)
            return 1
        action = job["action"]
        command = [sys.executable, str(Path(__file__).resolve()), action, "--act", str(args.act),
                   "--state", str(session), "--profile", "constrained", "--scratch", str(scratch),
                   "--action-source-state", str(state)]
        job.update(result="running", command=command)
        RESOURCES.write_json(path, receipt)
        previous = set(session.glob("*-" + action + ".json"))
        prior_scratch = set(scratch.iterdir())
        result = subprocess.run(command, cwd=ROOT)
        job.update(exit_code=result.returncode, result="passed" if result.returncode == 0 else "failed")
        if result.returncode == 3:
            produced_scratch = set(scratch.iterdir()) - prior_scratch
            if len(produced_scratch) == 1:
                resource_path = produced_scratch.pop() / "preflight.json"
                try:
                    resource = json.loads(resource_path.read_text())
                    if resource.get("profile") == "constrained" and resource.get("status") in ("refused", "unavailable") and resource.get("revision") == revision:
                        job.update(result="unrun", availability="unavailable", preflight=str(resource_path))
                        receipt.update(result="unavailable", reason="Per-job resource preflight refused; this workflow and later jobs remain unrun")
                        RESOURCES.write_json(path, receipt)
                        return 3
                except (OSError, ValueError, TypeError):
                    pass
        if result.returncode == 0:
            produced = set(session.glob("*-" + action + ".json")) - previous
            verified = False
            if len(produced) == 1:
                actual_path = produced.pop()
                try:
                    if actual_path.is_symlink() or not stat.S_ISREG(actual_path.stat().st_mode) or actual_path.stat().st_size > 2_000_000:
                        raise ValueError("Unsafe child receipt")
                    actual = json.loads(actual_path.read_text())
                    log = actual_path.with_suffix(".log")
                    verified = (actual.get("action") == action and actual.get("revision") == revision and actual.get("source_tree") == tree
                                and actual.get("dirty") is False and actual.get("result") == "passed"
                                and actual.get("exit_code") == 0 and log.is_file() and not log.is_symlink()
                                and stat.S_ISREG(log.stat().st_mode) and log.stat().st_size <= 256_000_000
                                and actual.get("log_sha256") == sha(log.read_bytes()))
                    job["receipt"] = str(actual_path)
                except (OSError, ValueError, TypeError, AttributeError):
                    verified = False
            if not verified:
                job.update(result="failed", reason="Child exited0 without one verified clean-source completion receipt")
        RESOURCES.write_json(path, receipt)
        if result.returncode or job["result"] != "passed":
            receipt.update(result="failed", reason="Stopped after failed job; later jobs remain unrun")
            RESOURCES.write_json(path, receipt)
            return result.returncode or 1
    unchanged = git("rev-parse", "HEAD") == revision and not git("status", "--porcelain")
    receipt.update(completed=bool(unchanged), result="passed" if unchanged else "failed")
    RESOURCES.write_json(path, receipt)
    print("Matrix evidence: " + str(path), flush=True)
    return 0 if unchanged else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "prepare-actions", "list", "dry-run", "preflight", "matrix", *JOBS])
    parser.add_argument("--act", type=Path, default=Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "obsgod/tools/bin/act")
    parser.add_argument("--state", type=Path, default=ROOT / ".local-ci")
    parser.add_argument("--pull-request", action="store_true", help="Use the reviewed synthetic PR event (no provider review API is simulated)")
    parser.add_argument("--profile", choices=["constrained"], help="Opt into measured private scratch and post-consumer compiler-cache policy")
    parser.add_argument("--scratch", type=Path, help="Explicit private directory outside the checkout, visible to the local Docker daemon")
    parser.add_argument("--action-source-state", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action in ("preflight", "matrix"):
        args.profile = "constrained"
    if args.profile and (args.scratch is None or not args.scratch.is_absolute()):
        parser.error("The constrained profile requires an explicit absolute --scratch path")
    if args.scratch is not None and not args.profile:
        parser.error("--scratch requires --profile constrained")
    if args.pull_request and args.action in ("preflight", "matrix"):
        parser.error("Matrix/preflight do not simulate provider pull-request acceptance")
    if args.action == "install":
        install(args.act.parent)
        return
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    if args.action == "matrix":
        raise SystemExit(matrix(args, state))
    resource = None
    attempt = None
    if args.profile:
        attempt = RESOURCES.allocate_attempt(args.scratch, args.action, ROOT)
        resource = RESOURCES.preflight(ROOT, attempt, IMAGE, git("rev-parse", "HEAD"))
        if args.action == "preflight" or resource["status"] != "passed":
            print(json.dumps(resource, sort_keys=True))
            raise SystemExit(0 if resource["status"] == "passed" else 3)
    actual = subprocess.check_output([str(args.act), "--version"], text=True).strip()
    if actual != f"act version {VERSION}":
        raise SystemExit(f"Expected act {VERSION}, got {actual}")
    mappings, action_receipts = prepare_actions(args.action_source_state.resolve() if args.action_source_state else state)
    if args.action == "prepare-actions":
        print(json.dumps(action_receipts, indent=2, sort_keys=True))
        return
    env = {k: v for k, v in os.environ.items() if k not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    # act advertises this same address to its bridge containers. 0.0.0.0 would
    # point the client at itself. Only this local service host bypasses the proxy;
    # keep every pre-existing no-proxy entry and all internet proxy destinations.
    service_address = socket.gethostbyname(socket.gethostname())
    if service_address.startswith("127.") or service_address == "0.0.0.0":
        raise SystemExit("A bridge-reachable local interface address is required for act artifact/cache services")
    for key in ("NO_PROXY", "no_proxy"):
        entries = env.get(key, "").split(",")
        if service_address not in entries:
            entries.append(service_address)
        env[key] = ",".join(entry for entry in entries if entry)
    command = [str(args.act), "--directory", str(ROOT), "--bind", "--env-file", os.devnull,
               "--secret-file", os.devnull, "--input-file", os.devnull,
               "--container-daemon-socket", "/var/run/docker.sock", "--network", "bridge",
               "--concurrent-jobs", "1", "--container-options", network_options(state, attempt / "tmp") if attempt else network_options(state),
               "--action-cache-path", str(state / "actions"),
               "--artifact-server-path", str(state / "artifacts"),
               "--artifact-server-addr", service_address, "--artifact-server-port", "34567",
               "--env", "NODE_EXTRA_CA_CERTS=/run/obsgod-ca.pem",
               "--env", "NODE_USE_ENV_PROXY=1", "--env", "SSL_CERT_FILE=/run/obsgod-ca.pem",
               "--env", "GIT_SSL_CAINFO=/run/obsgod-ca.pem", "--env", "PIP_CERT=/run/obsgod-ca.pem",
               "--env", "CODEX_PROXY_CERT=/run/obsgod-ca.pem", "--env", "TMPDIR=" + str(state / "tmp"),
               "--env", "OBSGOD_ACT_TEMP=" + str(state / "tmp")]
    if attempt:
        for prefix in ("TMPDIR=", "OBSGOD_ACT_TEMP="):
            command[command.index(prefix + str(state / "tmp"))] = prefix + str(attempt / "tmp")
        # Bind the complete private attempt for compiler caches and nested builds;
        # network_options already binds the per-attempt daemon-visible temp.
        options = command.index("--container-options") + 1
        command[options] += " " + shlex.join(["--mount", f"type=bind,src={attempt},dst={attempt}"])
        for key, value in {"OBSGOD_LOCAL_PROFILE": "constrained", "OBSGOD_LOCAL_SCRATCH": str(attempt),
                           "OBSGOD_LOCAL_RESOURCE_RECEIPT": str(attempt / "resource-policy.json"),
                           "OBSGOD_LOCAL_OWNER_UID": str(os.getuid()), "GOCACHE": str(attempt / "go-build-root")}.items():
            command += ["--env", key + "=" + value]
    command += mappings
    # act uses the Engine API rather than `docker run`, so Docker client's proxy
    # defaults are not automatically copied. Values reach only the child argv;
    # receipts retain their names only. Never change the proxy destination.
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        if key in env:
            command += ["--env", key + "=" + env[key]]
    if args.action in ("list", "dry-run"):
        command += ["-W", ".github/workflows", "--list" if args.action == "list" else "--dryrun"]
    else:
        workflow, job, event = JOBS[args.action]
        command += ["pull_request" if args.pull_request else event, "-W", f".github/workflows/{workflow}", "-j", job]
        if args.action == "build":
            command += ["--matrix", "os:ubuntu-24.04"]
        if args.pull_request:
            command += ["--eventpath", ".github/act/pull-request.json"]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    prefix = state / f"{stamp}-{args.action}"
    actrc = ROOT / ".actrc"
    receipt = {"revision": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
               "source_tree": git("rev-parse", "HEAD^{tree}"),
               "tracked_diff_sha256": sha(subprocess.check_output(["git", "-C", str(ROOT), "diff", "HEAD", "--binary"])),
               "act": actual, "runner_image": IMAGE, "action": args.action,
               "act_binary_sha256": sha(args.act.read_bytes()),
               "launcher_sha256": sha(Path(__file__).read_bytes()),
               "actrc_sha256": sha(actrc.read_bytes()) if actrc.is_file() else None,
               "log_format": "jsonl-with-text-fallback", "log_record_counts": {"json": 0, "text": 0},
               "local_service_address": service_address,
               "apt_ca_configuration": {"content": APT_CA_CONFIG.decode(), "sha256": sha(APT_CA_CONFIG)},
               "action_sources": action_receipts,
               "pull_request_fixture": args.pull_request,
               "workflow_sha256": {p.name: sha(p.read_bytes()) for p in sorted((ROOT / ".github/workflows").glob("*.yml"))},
               "started_utc": stamp, "result": "running"}
    if resource:
        receipt["resource_profile"] = {"name": "constrained", "preflight": str(attempt / "preflight.json"),
                                       "preflight_sha256": sha((attempt / "preflight.json").read_bytes()),
                                       "scratch": str(attempt), "compiler_cache_policy": "explicit post-consumer workflow boundary"}
    # Commands contain session paths; they are local evidence, not release metadata.
    receipt["command"] = redact_log_value([re.sub(r"^((?:HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy))=.*$", r"\1=[injected]", value) for value in command])
    prefix.with_suffix(".json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    with prefix.with_suffix(".log").open("w") as log:
        for line in process.stdout:
            line, structured = sanitize_log_line(line)
            receipt["log_record_counts"]["json" if structured else "text"] += 1
            print(line, end="", flush=True)
            log.write(line)
    code = process.wait()
    receipt.update(exit_code=code, result="passed" if code == 0 else "failed", log_sha256=sha(prefix.with_suffix(".log").read_bytes()))
    if attempt:
        policy = attempt / "resource-policy.json"
        if policy.exists() and not policy.is_symlink() and policy.is_file() and policy.stat().st_size <= 2_000_000:
            receipt["resource_profile"].update(compiler_cache_receipt=str(policy), compiler_cache_receipt_sha256=sha(policy.read_bytes()))
    prefix.with_suffix(".json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"Local evidence: {prefix}.json (review log before sharing)")
    sys.exit(code)


if __name__ == "__main__":
    main()
