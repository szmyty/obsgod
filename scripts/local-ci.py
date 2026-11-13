#!/usr/bin/env python3
"""Install the checksum-pinned act client or run an explicit local CI job.

No tokens, .env, .input or .secrets files are implicitly passed to workflows.
Only the managed local Docker socket is used; existing Docker proxy/registry
configuration is retained. Logs remain local and must be reviewed before sharing.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.97"
IMAGE = "ghcr.io/catthehacker/ubuntu:act-24.04@sha256:19619a010b204f44c5340bff7d39b68551109fe6a56a53f75201ea91e05d4270"
ACT_SHA256 = {"x86_64": ("x86_64", "67b4976a56f33ea7870b798912e738ec44eef38e7578ae7b532f2def1c73a5ad"),
              "aarch64": ("arm64", "44d48e3d4a6409053fdec6fc6518322467d79a2d5be8f72c021b0421e2ac113d")}
JOBS = {"build": ("build.yml", "build", "push"),
        "coverage": ("coverage.yml", "coverage", "push"),
        "lint": ("lint.yml", "golangci", "push"),
        "snapshot": ("goreleaser.yml", "goreleaser", "push"),
        "docs": ("docs-preview.yml", "build-preview", "workflow_dispatch"),
        "candidate": ("steam-deck.yml", "candidate", "workflow_dispatch")}


def sha(data):
    return hashlib.sha256(data).hexdigest()


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


def network_options(state):
    # Bind the combined public CA bundle, never credentials or Docker config.
    ca = Path("/etc/ssl/certs/ca-certificates.crt")
    if not ca.is_file():
        raise SystemExit("A trusted combined CA bundle is required")
    temporary = state / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    options = ["--mount", f"type=bind,src={ca},dst=/run/obsgod-ca.pem,readonly",
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "prepare-actions", "list", "dry-run", *JOBS])
    parser.add_argument("--act", type=Path, default=Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "obsgod/tools/bin/act")
    parser.add_argument("--state", type=Path, default=ROOT / ".local-ci")
    parser.add_argument("--pull-request", action="store_true", help="Use the reviewed synthetic PR event (no provider review API is simulated)")
    args = parser.parse_args()
    if args.action == "install":
        install(args.act.parent)
        return
    actual = subprocess.check_output([str(args.act), "--version"], text=True).strip()
    if actual != f"act version {VERSION}":
        raise SystemExit(f"Expected act {VERSION}, got {actual}")
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    mappings, action_receipts = prepare_actions(state)
    if args.action == "prepare-actions":
        print(json.dumps(action_receipts, indent=2, sort_keys=True))
        return
    env = {k: v for k, v in os.environ.items() if k not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    command = [str(args.act), "--directory", str(ROOT), "--bind", "--env-file", os.devnull,
               "--secret-file", os.devnull, "--input-file", os.devnull,
               "--container-daemon-socket", "/var/run/docker.sock", "--network", "bridge",
               "--concurrent-jobs", "1", "--container-options", network_options(state),
               "--action-cache-path", str(state / "actions"),
               "--artifact-server-path", str(state / "artifacts"),
               "--artifact-server-addr", "0.0.0.0", "--artifact-server-port", "34567",
               "--env", "NODE_EXTRA_CA_CERTS=/run/obsgod-ca.pem",
               "--env", "NODE_USE_ENV_PROXY=1", "--env", "SSL_CERT_FILE=/run/obsgod-ca.pem",
               "--env", "GIT_SSL_CAINFO=/run/obsgod-ca.pem", "--env", "PIP_CERT=/run/obsgod-ca.pem",
               "--env", "CODEX_PROXY_CERT=/run/obsgod-ca.pem", "--env", "TMPDIR=" + str(state / "tmp"),
               "--env", "OBSGOD_ACT_TEMP=" + str(state / "tmp")]
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
    receipt = {"revision": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
               "tracked_diff_sha256": sha(subprocess.check_output(["git", "-C", str(ROOT), "diff", "HEAD", "--binary"])),
               "act": actual, "runner_image": IMAGE, "action": args.action,
               "action_sources": action_receipts,
               "pull_request_fixture": args.pull_request,
               "workflow_sha256": {p.name: sha(p.read_bytes()) for p in sorted((ROOT / ".github/workflows").glob("*.yml"))},
               "started_utc": stamp, "result": "running"}
    # Commands contain session paths; they are local evidence, not release metadata.
    receipt["command"] = [re.sub(r"^((?:HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy))=.*$", r"\1=[injected]", value) for value in command]
    prefix.with_suffix(".json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    with prefix.with_suffix(".log").open("w") as log:
        for line in process.stdout:
            line = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", line)
            print(line, end="", flush=True)
            log.write(line)
    code = process.wait()
    receipt.update(exit_code=code, result="passed" if code == 0 else "failed", log_sha256=sha(prefix.with_suffix(".log").read_bytes()))
    prefix.with_suffix(".json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"Local evidence: {prefix}.json (review log before sharing)")
    sys.exit(code)


if __name__ == "__main__":
    main()
