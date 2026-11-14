#!/usr/bin/env python3
"""Prepare and audit generic CLI snapshots; never publish or contact OBS.

Go-only notices cover the pinned module graph. Artifact SBOMs identify only
modules actually linked into each selected binary. Inventories/provenance are
deterministic, UNSIGNED and self-reported, not publisher attestations.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = "github.com/szmyty/obsgod"
GO = "go1.27.4"
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 96 * 1024 * 1024
TARGETS = {(system, arch, arm) for system in ("linux", "freebsd", "openbsd")
           for arch, arm in (("amd64", ""), ("arm64", ""), ("386", ""), ("arm", "6"), ("arm", "7"))}
TARGETS |= {("darwin", "amd64", ""), ("darwin", "arm64", ""),
            ("windows", "amd64", ""), ("windows", "arm64", ""), ("windows", "386", "")}
BASE_FILES = {"LICENSE", "README.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "GO-NOTICES.json", "GENERIC-CLI.md"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(*args, env=None):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=60, env=env).strip()


def git_file(revision, name):
    return subprocess.check_output(["git", "show", revision + ":" + name], cwd=ROOT)


def source(revision):
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)), "Full source revision required")
    require(command("git", "rev-parse", "HEAD") == revision, "Checkout differs from selected source")
    require(not command("git", "status", "--porcelain"), "Clean source required")
    stamp = int(command("git", "show", "-s", "--format=%ct", revision))
    return {"revision": revision, "tree": command("git", "rev-parse", revision + "^{tree}"),
            "created": datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "epoch": stamp}


def json_stream(text):
    decoder = json.JSONDecoder()
    while text.strip():
        value, end = decoder.raw_decode(text.lstrip())
        yield value
        text = text.lstrip()[end:]


def license_bytes(directory):
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        path = directory / name
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            require(0 < len(data) <= 1_000_000, "Missing or oversized dependency license")
            return name, data
    raise ValueError("Missing dependency license")


def prepare_documents(identity):
    require(command("go", "env", "GOVERSION") == GO, "Pinned Go toolchain required")
    command("go", "mod", "verify")
    goroot = Path(command("go", "env", "GOROOT"))
    _, standard = license_bytes(goroot)
    source_mod, source_sum = git_file(identity["revision"], "go.mod"), git_file(identity["revision"], "go.sum")
    catalog, sections = [], {}
    text = ("# Generic CLI third-party notices\n\nThe application retains its repository MIT license. "
            "This catalog covers Go packages selected for all20 compiled targets as a notice superset. "
            "Per-archive SBOMs identify actual linked dependencies; a catalog entry alone does not "
            "mean that module is redistributed. No Decky SDK, capture library, OBS or system runtime "
            "binary is included in these CLI archives.\n\n## Go standard library " + GO + "\n\n" + standard.decode() + "\n")
    selected = {}
    sums = {(name, version): checksum for name, version, checksum in (line.split() for line in source_sum.decode().splitlines())}
    for system, arch, arm in sorted(TARGETS):
        env = {**os.environ, "GOOS": system, "GOARCH": arch, "CGO_ENABLED": "0"}
        env.pop("GOARM", None)
        if arm:
            env["GOARM"] = arm
        for package in json_stream(command("go", "list", "-mod=readonly", "-deps", "-json", ".", env=env)):
            module = package.get("Module")
            if not module:
                continue
            require(not module.get("Replace"), "Unreviewed module replacement")
            if module.get("Main"):
                require(module["Path"] == MODULE, "Unexpected main module")
                continue
            key = module["Path"], module["Version"]
            if key in selected:
                require(selected[key]["Dir"] == module["Dir"], "Conflicting selected module directory")
            selected[key] = module
    # The module graph can contain unloaded test/doc modules lacking archive
    # sums or local directories. Only actual target-selected package modules
    # enter notices; their selected versions must have verified source sums.
    for (name, version), module in sorted(selected.items()):
        checksum = sums.get((name, version))
        require(checksum and (not module.get("Sum") or module["Sum"] == checksum), "Module differs from pinned go.sum")
        filename, license_ = license_bytes(Path(module["Dir"]))
        catalog.append({"name": name, "version": version, "go_sum": checksum,
                        "license_file": filename, "license_sha256": sha(license_)})
        sections[name] = "\n## " + name + " " + version + "\n\n" + license_.decode() + "\n"
    catalog.sort(key=lambda item: item["name"])
    require(catalog, "Missing dependency catalog")
    text += "".join(sections[name] for name in sorted(sections))
    metadata = {"schema_version": 1, "source": identity, "go": GO, "scope": "union-of-target-selected-Go-package-modules",
                "targets": [list(target) for target in sorted(TARGETS)],
                "standard_library_license_sha256": sha(standard), "modules": catalog,
                "source_sha256": {"go.mod": sha(source_mod), "go.sum": sha(source_sum)}}
    return {"THIRD_PARTY_NOTICES.md": text.encode(), "GO-NOTICES.json": canonical(metadata),
            "GENERIC-CLI.md": git_file(identity["revision"], "docs/generic-cli-distribution.md")}


def safe_directory(path):
    path = path.absolute()
    for ancestor in [path, *path.parents]:
        require(not ancestor.is_symlink(), "Refusing a symlink output path")
    if path.exists():
        require(path.is_dir() and path.stat().st_uid == os.getuid(), "Output directory must belong to current identity")
    else:
        path.mkdir(parents=True, mode=0o755)
    return path


def write_documents(path, documents, epoch=None):
    path = safe_directory(path)
    existing = {p.name for p in path.iterdir()}
    require(not existing - set(documents), "Unexpected existing output files")
    for name, data in documents.items():
        require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", name)), "Unsafe output name")
        target = path / name
        require(not target.is_symlink(), "Refusing a symlink output file")
        if target.exists():
            require(target.is_file() and target.stat().st_uid == os.getuid() and target.stat().st_nlink == 1, "Refusing foreign or hardlinked output file")
        with target.open("wb") as stream:
            stream.write(data)
        if epoch is not None:
            os.utime(target, (epoch, epoch))


def safe_member(name):
    require(isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z0-9_.-]+", name)) and name not in (".", ".."), "Unsafe archive member")
    return name


class BoundedGzip:
    def __init__(self, data):
        self.stream = gzip.GzipFile(fileobj=io.BytesIO(data))
        self.remaining = MAX_TOTAL + 1_000_000

    def read(self, size=-1):
        result = self.stream.read(self.remaining + 1 if size < 0 else min(size, self.remaining + 1))
        self.remaining -= len(result)
        require(self.remaining >= 0, "Archive expansion limit exceeded")
        return result


def archive_files(data, kind):
    require(len(data) <= MAX_TOTAL, "Oversized archive")
    files, total = {}, 0
    archive = tarfile.open(fileobj=BoundedGzip(data), mode="r|") if kind == "tar.gz" else zipfile.ZipFile(io.BytesIO(data))
    with archive:
        for number, member in enumerate(archive if kind == "tar.gz" else archive.infolist(), 1):
            require(number <= 20, "Too many archive members")
            name = safe_member(member.name if kind == "tar.gz" else member.filename)
            size = member.size if kind == "tar.gz" else member.file_size
            mode = member.mode if kind == "tar.gz" else member.external_attr >> 16
            regular = member.isfile() if kind == "tar.gz" else stat.S_ISREG(mode)
            require(regular and name not in files and not mode & 0o7000, "Nonregular, privileged or duplicate archive member")
            total += size
            require(0 <= size <= MAX_FILE and total <= MAX_TOTAL, "Archive expansion limit exceeded")
            content = archive.extractfile(member).read() if kind == "tar.gz" else archive.read(member)
            require(len(content) == size, "Truncated archive member")
            files[name] = {"data": content, "mode": stat.S_IMODE(mode)}
    require(files, "Empty archive")
    return files


def binary_metadata(data):
    # Parses cross-platform executable metadata; does not run the binary.
    with tempfile.TemporaryDirectory(prefix="obsgod-generic-metadata-") as directory:
        path = Path(directory) / "binary"
        path.write_bytes(data)
        output = command("go", "version", "-m", str(path))
    require(output.splitlines()[0].endswith(": " + GO), "Binary Go toolchain mismatch")
    deps, settings, main = [], {}, None
    for line in output.splitlines()[1:]:
        parts = line.strip().split("\t")
        require(parts[0] != "=>", "Unreviewed binary module replacement")
        if parts[0] == "mod":
            main = parts[1]
        elif parts[0] == "dep":
            require(len(parts) == 4, "Malformed binary dependency")
            deps.append(dict(zip(("name", "version", "go_sum"), parts[1:])))
        elif parts[0] == "build":
            require(len(parts) == 2 and "=" in parts[1], "Malformed binary build setting")
            key, value = parts[1].split("=", 1)
            require(key not in settings, "Duplicate binary build setting")
            settings[key] = value
    require(main == MODULE and deps, "Unexpected binary module inventory")
    return sorted(deps, key=lambda item: item["name"]), settings


def target_name(version, target):
    system, arch, arm = target
    return f"obsgod_{version}_{system}_{arch}{'v' + arm if arm else ''}." + ("zip" if system == "windows" else "tar.gz")


def audit_archive(name, data, target, version, identity, prepared):
    system, arch, arm = target
    files = archive_files(data, "zip" if system == "windows" else "tar.gz")
    binary = "obsgod.exe" if system == "windows" else "obsgod"
    require(set(files) == BASE_FILES | {binary}, "Generic archive exact inventory mismatch")
    for filename in ("LICENSE", "README.md", "CHANGELOG.md"):
        require(files[filename]["data"] == git_file(identity["revision"], filename), "Archive source file mismatch")
    for filename, expected in prepared.items():
        require(files[filename]["data"] == expected, "Archive notice/source catalog mismatch")
    require(system == "windows" or files[binary]["mode"] & 0o111, "Archive binary is not executable")
    dependencies, settings = binary_metadata(files[binary]["data"])
    require((settings.get("GOOS"), settings.get("GOARCH"), settings.get("GOARM", "").split(",")[0]) == target, "Binary platform mismatch")
    require(settings.get("CGO_ENABLED") == "0", "Generic snapshot must disable CGO")
    require(settings.get("vcs") == "git" and settings.get("vcs.revision") == identity["revision"] and settings.get("vcs.modified") == "false", "Binary clean VCS source mismatch")
    flags = settings.get("-ldflags", "")
    if flags.startswith('"'):
        flags = json.loads(flags)
    if flags:
        words = shlex.split(flags)
        required = {"main.version=" + version, "main.commitSHA=" + identity["revision"]}
        require(required <= {words[i + 1] for i, word in enumerate(words[:-1]) if word == "-X"}, "Binary version/source metadata mismatch")
        version_evidence = "Go build-record ldflags"
    else:
        # Go omits ldflags from trimmed build records. Do not fabricate fields:
        # source/version come from the clean snapshot metadata, with byte-presence
        # checks as a narrower static cross-build check. Linux smoke confirms the
        # actual CLI result; other native runtime checks remain outstanding.
        require(version.encode() in files[binary]["data"] and identity["revision"].encode() in files[binary]["data"], "Binary version/source bytes absent")
        version_evidence = "Snapshot version metadata plus embedded byte presence; native CLI values unrun-by-audit"
    catalog = json.loads(prepared["GO-NOTICES.json"])
    notice_modules = {m["name"]: m for m in catalog["modules"]}
    require(len(dependencies) == len({m["name"] for m in dependencies}), "Duplicate linked module")
    for module in dependencies:
        require(module["name"] in notice_modules and all(notice_modules[module["name"]][k] == module[k] for k in ("version", "go_sum")), "Linked module missing matching notices")
    return {"name": name, "sha256": sha(data), "platform": {"goos": system, "goarch": arch, "goarm": arm},
            "binary": binary, "binary_sha256": sha(files[binary]["data"]), "dependencies": dependencies,
            "version_source_evidence": version_evidence, "go_build_settings": settings,
            "source_evidence": "Go VCS metadata: exact selected revision and unmodified source",
            "files": {p: {"sha256": sha(v["data"]), "mode": v["mode"]} for p, v in sorted(files.items())}}


def sidecars(record, version, identity):
    identity_hash = record["sha256"]
    packages = [{"SPDXID": "SPDXRef-Application", "name": "obsgod", "versionInfo": version,
                 "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "MIT"},
                {"SPDXID": "SPDXRef-Go", "name": "Go standard library", "versionInfo": GO,
                 "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "BSD-3-Clause"}]
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Application"},
                     {"spdxElementId": "SPDXRef-Application", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": "SPDXRef-Go"}]
    for module in record["dependencies"]:
        identifier = "SPDXRef-Module-" + sha(module["name"].encode())[:20]
        packages.append({"SPDXID": identifier, "name": module["name"], "versionInfo": module["version"],
                         "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "NOASSERTION",
                         "comment": "Actual linked module; go.sum " + module["go_sum"] + "; full license text in THIRD_PARTY_NOTICES.md"})
        relationships.append({"spdxElementId": "SPDXRef-Application", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": identifier})
    files = []
    for filename, item in record["files"].items():
        identifier = "SPDXRef-File-" + sha(filename.encode())[:20]
        files.append({"SPDXID": identifier, "fileName": filename, "checksums": [{"algorithm": "SHA256", "checksumValue": item["sha256"]}],
                      "licenseConcluded": "NOASSERTION", "licenseInfoInFiles": ["NOASSERTION"], "copyrightText": "NOASSERTION"})
        relationships.append({"spdxElementId": "SPDXRef-Application", "relationshipType": "CONTAINS", "relatedSpdxElement": identifier})
    sbom = {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT", "name": record["name"],
            "documentNamespace": "https://github.com/szmyty/obsgod/sbom/" + identity["revision"] + "/" + identity_hash,
            "creationInfo": {"created": identity["created"], "creators": ["Tool: obsgod-generic-release-schema1"]},
            "packages": packages, "files": files, "relationships": relationships,
            "comment": "UNSIGNED local inventory. Notice catalog is a target-selected module superset; only actual linked modules are package dependencies. Platform compilation is not native runtime qualification."}
    materials = [{"uri": "git+https://github.com/szmyty/obsgod@" + identity["revision"], "digest": {"sha1": identity["revision"]}}]
    for name in ("go.mod", "go.sum", ".goreleaser.yml", ".github/workflows/goreleaser.yml", "scripts/generic-release.py", "docs/generic-cli-distribution.md"):
        materials.append({"uri": name, "digest": {"sha256": sha(git_file(identity["revision"], name))}})
    provenance = {"_type": "https://in-toto.io/Statement/v1", "subject": [{"name": record["name"], "digest": {"sha256": identity_hash}}],
                  "predicateType": "https://slsa.dev/provenance/v1", "predicate": {
                      "buildDefinition": {"buildType": "urn:obsgod:generic-cli-snapshot", "externalParameters": {"version": version, "platform": record["platform"]},
                                          "internalParameters": {"go": GO}, "resolvedDependencies": materials},
                      "runDetails": {"builder": {"id": "urn:obsgod:local-self-reported-unsigned"}, "metadata": {"invocationId": "urn:sha256:" + identity_hash},
                                     "byproducts": [{"name": "trust-boundary", "annotations": {"status": "UNSIGNED", "claim": "No authenticated publisher, trusted builder, signature, SLSA level or native-platform acceptance is established."}}]}}}
    return {record["name"] + ".spdx.json": canonical(sbom), record["name"] + ".provenance.unsigned.json": canonical(provenance)}


def audit(directory, revision):
    identity = source(revision)
    require(not directory.is_symlink() and directory.is_dir(), "Artifact directory must be a real directory")
    metadata = json.loads((directory / "metadata.json").read_bytes())
    require(metadata.get("commit") == revision and metadata.get("project_name") == "obsgod", "Snapshot metadata source/project mismatch")
    version = metadata.get("version", "")
    require(bool(re.fullmatch(r"0\.0\.0-dev\.g[0-9a-f]{7,40}", version)) and revision.startswith(version.split(".g", 1)[1]), "Revision-bound snapshot version required")
    expected = {target_name(version, target): target for target in TARGETS}
    actual = {p.name for p in directory.iterdir() if p.name.endswith((".tar.gz", ".zip"))}
    require(actual == set(expected), "Exactly the reviewed20 generic snapshot archives required")
    sums = {}
    for line in (directory / "checksums.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(re.fullmatch(r"[0-9a-f]{64}", digest) and name not in sums, "Invalid/duplicate snapshot checksum")
        sums[name] = digest
    require(set(expected) <= set(sums), "Missing archive checksums")
    prepared, documents, records = prepare_documents(identity), {}, []
    for name, target in sorted(expected.items()):
        path = directory / name
        require(not path.is_symlink() and path.is_file() and path.stat().st_size <= MAX_TOTAL, "Unsafe artifact file")
        data = path.read_bytes()
        require(sha(data) == sums[name], "Snapshot checksum mismatch")
        record = audit_archive(name, data, target, version, identity, prepared)
        documents.update(sidecars(record, version, identity))
        records.append(record)
    summary = {"schema_version": 1, "source": identity, "version": version, "archive_count": len(records), "archives": records,
               "integrity": "passed", "native_execution": "unrun-by-audit", "publication": "not-authorized-by-audit",
               "limits": ["Go-only tar/zip snapshot archives; nfpm packages are outside this audit.", "Native Windows/macOS/BSD/Linux-arm runtime and OBS integration remain unrun.", "Unsigned self-reported inventories are not authenticated publisher attestations.", "Release, deployment and stable support claims require their existing owner/qualification gates."]}
    documents["SUMMARY.json"] = canonical(summary)
    documents["AUDIT-SHA256SUMS"] = "".join(sha(data) + "  " + name + "\n" for name, data in sorted(documents.items())).encode()
    return documents, summary


def smoke(directory, summary):
    require(os.getuid() != 0, "Linux install smoke must run as an unprivileged user")
    require(platform.system() == "Linux" and platform.machine() in ("x86_64", "amd64"), "Linux amd64 runtime required")
    record = next(item for item in summary["archives"] if item["platform"] == {"goos": "linux", "goarch": "amd64", "goarm": ""})
    safe_member(record["name"])
    archive = directory / record["name"]
    require(not archive.is_symlink() and archive.stat().st_size <= MAX_TOTAL, "Unsafe smoke archive")
    data = archive.read_bytes()
    require(sha(data) == record["sha256"], "Smoke archive differs from audit")
    files = archive_files(data, "tar.gz")
    require(set(files) == BASE_FILES | {"obsgod"} and all(sha(item["data"]) == record["files"][name]["sha256"] for name, item in files.items()), "Smoke payload differs from audit")
    with tempfile.TemporaryDirectory(prefix="obsgod-generic-install-") as temporary:
        home = Path(temporary) / "home"
        unpacked = Path(temporary) / "unpacked"
        unpacked.mkdir(mode=0o700)
        for name, item in files.items():
            target = unpacked / name
            with target.open("xb") as stream:
                stream.write(item["data"])
            target.chmod(0o755 if name == "obsgod" else 0o644)
        binary = home / ".local/bin/obsgod"
        binary.parent.mkdir(parents=True, mode=0o700)
        binary.write_bytes((unpacked / "obsgod").read_bytes())
        binary.chmod(0o755)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "LANG": "C.UTF-8", "TMPDIR": temporary}
        outputs = []
        for arguments in (["version", "--json"], ["config", "path"], ["api", "capabilities"]):
            result = subprocess.run([str(binary), *arguments], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            require(result.returncode == 0 and not result.stderr and len(result.stdout) < 262144, "Installed CLI offline command failed")
            outputs.append(result.stdout.decode())
        version = json.loads(outputs[0])
        require(version == {"schema_version": 1, "name": "obsgod", "version": summary["version"] + " (" + summary["source"]["revision"] + ")"}, "Installed CLI version mismatch")
        require(outputs[1].strip() == str(home / ".config/obsgod/config.json") and not (home / ".config").exists(), "Config inspection wrote or selected unexpected data")
        require(isinstance(json.loads(outputs[2]), dict), "Capabilities command did not return JSON")
        return {"schema_version": 1, "source_revision": summary["source"]["revision"], "archive": record["name"], "archive_sha256": record["sha256"],
                "uid": os.getuid(), "gid": os.getgid(), "platform": "Linux/amd64", "outcome": "passed", "commands": [["obsgod", *a] for a in (["version", "--json"], ["config", "path"], ["api", "capabilities"])],
                "scope": "Private temporary user-prefix extraction/install/offline CLI only; no OBS connection or supported-platform claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--output", type=Path, default=ROOT / ".local-ci/generic-release")
    check = sub.add_parser("audit")
    check.add_argument("--revision", required=True)
    check.add_argument("--artifacts", type=Path, default=ROOT / "dist/snapshot")
    check.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("smoke")
    run.add_argument("--artifacts", type=Path, default=ROOT / "dist/snapshot")
    run.add_argument("--audit", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            identity = source(command("git", "rev-parse", "HEAD"))
            write_documents(args.output, prepare_documents(identity), identity["epoch"])
            print("Prepared pinned generic Go notices")
        elif args.action == "audit":
            documents, summary = audit(args.artifacts, args.revision)
            write_documents(args.output, documents)
            print(json.dumps({"archives": summary["archive_count"], "revision": args.revision, "integrity": "passed", "publication": "not-authorized"}))
        else:
            require(not args.audit.is_symlink() and args.audit.stat().st_size < 2_000_000, "Unsafe audit summary")
            summary = json.loads(args.audit.read_bytes())
            require(summary.get("integrity") == "passed" and summary.get("archive_count") == 20, "Complete generic audit required before smoke")
            result = smoke(args.artifacts, summary)
            write_documents(args.output, {"linux-install-smoke.json": canonical(result)})
            print(json.dumps(result))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError, StopIteration, tarfile.TarError, zipfile.BadZipFile) as error:
        print("Generic snapshot check failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
