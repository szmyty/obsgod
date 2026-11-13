#!/usr/bin/env python3
"""Offline artifact-integrity audit, SPDX inventory and UNSIGNED provenance.

Reads archives without extraction or executing their code. The revision must be
available in this Git object database. This is review evidence, not a signature,
trusted builder attestation, license opinion or a production release approval.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_name(name):
    require(isinstance(name, str) and name and not name.startswith("/") and "\\" not in name,
            "Unsafe archive path")
    require(all(part not in ("", ".", "..") for part in name.split("/")), "Unsafe archive path")
    return name


def archive_files(data, kind):
    """Accept regular, uniquely named files only, with bounded expansion."""
    files, total = {}, 0
    archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") if kind == "tar" else zipfile.ZipFile(io.BytesIO(data))
    with archive:
        entries = archive.getmembers() if kind == "tar" else archive.infolist()
        require(len(entries) <= 2000, "Too many archive members")
        for member in entries:
            name = safe_name(member.name if kind == "tar" else member.filename)
            size = member.size if kind == "tar" else member.file_size
            regular = member.isfile() if kind == "tar" else stat.S_ISREG(member.external_attr >> 16)
            require(regular and name not in files, "Non-regular or duplicate archive member: " + name)
            total += size
            require(0 <= size <= MAX_FILE and total <= MAX_TOTAL, "Archive expansion limit exceeded")
            content = archive.extractfile(member).read() if kind == "tar" else archive.read(member)
            require(len(content) == size, "Truncated member: " + name)
            files[name] = content
    require(files, "Empty archive")
    roots = {name.split("/")[0] for name in files}
    require(len(roots) == 1 and all("/" in name for name in files), "Archive must have one directory root")
    return roots.pop(), {name.split("/", 1)[1]: content for name, content in files.items()}


def verify_manifest(files, manifest):
    expected = manifest.get("files")
    require(isinstance(expected, dict) and expected, "Missing manifest file inventory")
    require(set(files) == set(expected) | {"manifest.json"}, "Manifest does not describe exact payload")
    for name, checksum in expected.items():
        safe_name(name)
        require(re.fullmatch(r"[0-9a-f]{64}", str(checksum)) and sha(files[name]) == checksum,
                "Manifest checksum mismatch: " + name)


def git(revision, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{path}"])


def verify_checksum_list(data, artifacts):
    values = {}
    for line in data.decode().splitlines():
        require(re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_.-]+", line), "Invalid checksum list")
        checksum, name = line.split("  ")
        require(name not in values, "Duplicate checksum entry")
        values[name] = checksum
    require(set(values) == set(artifacts), "Checksum list does not describe exact selected artifacts")
    require(all(sha(artifacts[name]) == checksum for name, checksum in values.items()), "Outer artifact checksum mismatch")


def go_inventory(binary, revision, allow_no_dependencies=False):
    # `go version -m` parses build metadata; it never executes the package.
    with tempfile.TemporaryDirectory(prefix="obsgod-audit-") as temporary:
        path = Path(temporary) / "obsgod"
        path.write_bytes(binary)
        output = subprocess.check_output(["go", "version", "-m", str(path)], text=True)
    require(output.splitlines()[0].endswith(": go1.27.4"), "Artifact Go toolchain mismatch")
    source_mod = git(revision, "go.mod").decode()
    source_sum = git(revision, "go.sum").decode().splitlines()
    require("\tbuild\tGOARCH=amd64" in output and "\tbuild\tGOOS=linux" in output, "Artifact Go platform mismatch")
    modules = []
    for line in output.splitlines():
        parts = line.strip().split("\t")
        require(not parts or parts[0] != "=>", "Unreviewed Go module replacement")
        if parts[0] == "dep":
            require(len(parts) == 4, "Malformed Go build dependency")
            _, name, version, checksum = parts
            require(re.search(r"(?m)^\s*(?:require\s+)?" + re.escape(name) + r"\s+" + re.escape(version) + r"(?:\s|$)", source_mod) and f"{name} {version} {checksum}" in source_sum,
                    "Binary dependency differs from pinned source: " + name)
            modules.append({"name": name, "version": version, "go_sum": checksum})
    require(modules or allow_no_dependencies, "No Go dependency inventory found")
    return sorted(modules, key=lambda item: item["name"])


def audit(directory, expected_revision):
    directory = directory.resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    revision, version = manifest.get("revision", ""), manifest.get("version", "")
    require(re.fullmatch(r"[0-9a-f]{40}", revision) and revision == expected_revision, "Exact source revision mismatch")
    require(re.fullmatch(r"[0-9][A-Za-z0-9.-]{0,79}", version), "Unsafe artifact version")
    require(manifest.get("dirty") is False and manifest.get("platform") == "linux/amd64", "Clean Linux amd64 candidate required")
    require((manifest.get("go"), manifest.get("node"), manifest.get("npm")) == ("go1.27.4", "24.19.0", "11.9.0"), "Pinned toolchain mismatch")
    names = [f"obsgod-deck_{version}_linux_amd64.tar.gz", "obsgod-decky.zip", "manifest.json"]
    artifacts = {name: (directory / name).read_bytes() for name in names}
    verify_checksum_list((directory / "SHA256SUMS").read_bytes(), artifacts)
    root, payload = archive_files(artifacts[names[0]], "tar")
    require(root == "OBSGod-" + version and payload["manifest.json"] == manifest_bytes, "Runtime manifest/root mismatch")
    verify_manifest(payload, manifest)
    require(payload["obsgod-decky.zip"] == artifacts["obsgod-decky.zip"], "Nested Decky ZIP mismatch")
    _, plugin = archive_files(artifacts["obsgod-decky.zip"], "zip")
    for name in ("obsgod", "libgstobsgodcapture.so"):
        require(plugin["bin/" + name] == payload[name], "Decky runtime differs: " + name)
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "CAPTURE-SOURCE.tar.gz"):
        require(plugin[name] == payload[name], "Decky notices/preferred source differ: " + name)
    require(json.loads(plugin["package.json"])["version"] == version, "Decky version mismatch")
    for name in ("LICENSE.LGPL-2.1", "LICENSE.qrcode-generator.txt"):
        require(plugin[name] == git(revision, "steamdeck/decky/" + name), "Third-party license differs from source")
    require(any(name.startswith("source/decky-api/src/") and name.endswith(".ts") for name in plugin), "Missing LGPL preferred TypeScript source")
    require(plugin.get("source/decky-api/BUILDING.md"), "Missing LGPL rebuild instructions")
    lock_bytes = git(revision, "steamdeck/decky/package-lock.json")
    lock = json.loads(lock_bytes)["packages"]
    require(json.loads(plugin["source/decky-api/package.json"])["version"] == lock["node_modules/@decky/api"]["version"], "LGPL source version mismatch")
    _, capture = archive_files(payload["CAPTURE-SOURCE.tar.gz"], "tar")
    require(set(capture) == {"gstobsgodcapture.c", "Makefile", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "build.Dockerfile"}, "Capture preferred-source inventory mismatch")
    for name, content in capture.items():
        require(content == git(revision, "steamdeck/capture/" + name), "Capture preferred source differs from revision: " + name)
    source_map = {name: "steamdeck/" + name for name in manifest["files"] if name.endswith((".py", ".desktop", ".sh", ".html", ".js", ".css"))}
    source_map.update({"LICENSE": "LICENSE", "STEAM-DECK.md": "docs/steam-deck.md"})
    for name, path in source_map.items():
        require(payload[name] == git(revision, path), "Runtime source differs from revision: " + path)
    for name in ("main.py", "releases.py", "paths.py", "product.py", "plugin.json"):
        source = "steamdeck/decky/" + name if name in ("main.py", "plugin.json") else "steamdeck/" + name
        require(plugin[name] == git(revision, source), "Decky source differs from revision: " + name)
    modules = go_inventory(payload["obsgod"], revision)
    helper_modules = go_inventory(payload["decky-install"], revision, allow_no_dependencies=True)
    modules = sorted({(module["name"], module["version"]): module for module in [*modules, *helper_modules]}.values(), key=lambda item: item["name"])
    notices = payload["THIRD_PARTY_NOTICES.md"].decode()
    require(all(module["name"] + " " + module["version"] in notices for module in modules), "Missing shipped Go dependency notices")
    updater_name = f"obsgod-one-click-update_{version}_linux_amd64.zip"
    updater_bytes = (directory / updater_name).read_bytes()
    verify_checksum_list((directory / "UPDATER-SHA256SUMS").read_bytes(), {updater_name: updater_bytes})
    updater_root, updater = archive_files(updater_bytes, "zip")
    updater_manifest = json.loads(updater["manifest.json"])
    require(updater_root == "OBSGod-Updater" and updater["manifest.json"] == (directory / "updater-manifest.json").read_bytes(), "Updater manifest/root mismatch")
    require(all(updater_manifest.get(key) == value for key, value in {"kind": "updater", "revision": revision, "runtime_revision": revision, "version": version, "updater_version": version, "platform": "linux/amd64"}.items()), "Updater identity mismatch")
    verify_manifest(updater, updater_manifest)
    for name in updater_manifest["files"]:
        require(updater[name] == payload[name], "Updater source differs from runtime: " + name)
    artifacts.update({updater_name: updater_bytes, "updater-manifest.json": updater["manifest.json"]})
    receipt = json.loads((directory / "capture-build.json").read_bytes())
    require(receipt["sha256"] == sha(payload["libgstobsgodcapture.so"]) and receipt["source_sha256"] == sha(capture["gstobsgodcapture.c"]) and receipt["dockerfile_sha256"] == sha(capture["build.Dockerfile"]) and receipt["network_during_compile"] is False, "Capture build receipt mismatch")
    artifacts["capture-build.json"] = (directory / "capture-build.json").read_bytes()
    materials = [{"uri": "git+https://github.com/szmyty/obsgod@" + revision, "digest": {"sha1": revision}}]
    for name in ("go.mod", "go.sum", "steamdeck/decky/package-lock.json", "steamdeck/decky/rollup.config.js", "scripts/package-deck.py", "scripts/package-updater.py", "steamdeck/capture/build.Dockerfile"):
        materials.append({"uri": name, "digest": {"sha256": sha(git(revision, name))}})
    timestamp = int(subprocess.check_output(["git", "-C", str(ROOT), "show", "-s", "--format=%ct", revision]))
    created = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return manifest, artifacts, payload, plugin, modules, lock, receipt, materials, created


def documents(result):
    manifest, artifacts, payload, plugin, modules, lock, capture, materials, created = result
    revision, version = manifest["revision"], manifest["version"]
    subjects = [{"name": name, "digest": {"sha256": sha(data)}} for name, data in sorted(artifacts.items())]
    identity = sha(canonical(subjects))
    packages = [{"SPDXID": "SPDXRef-Application", "name": "OBSGod", "versionInfo": version,
                 "downloadLocation": "https://github.com/szmyty/obsgod/tree/" + revision,
                 "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "MIT",
                 "copyrightText": "NOASSERTION", "sourceInfo": "Git revision " + revision}]
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Application"}]
    def add_package(name, version, license_id, relationship, comment):
        identifier = "SPDXRef-Package-" + sha((name + "@" + version).encode())[:20]
        packages.append({"SPDXID": identifier, "name": name, "versionInfo": version, "downloadLocation": "NOASSERTION", "filesAnalyzed": False,
                         "licenseConcluded": "NOASSERTION", "licenseDeclared": license_id, "copyrightText": "NOASSERTION", "comment": comment})
        relationships.append({"spdxElementId": identifier if relationship == "BUILD_DEPENDENCY_OF" else "SPDXRef-Application",
                              "relationshipType": relationship,
                              "relatedSpdxElement": "SPDXRef-Application" if relationship == "BUILD_DEPENDENCY_OF" else identifier})
    add_package("Go standard library", manifest["go"], "BSD-3-Clause", "DEPENDS_ON", "Linked standard library; license shipped in THIRD_PARTY_NOTICES.md")
    for module in modules:
        add_package(module["name"], module["version"], "NOASSERTION", "DEPENDS_ON", "Linked Go build metadata; go.sum " + module["go_sum"] + "; full license text shipped in THIRD_PARTY_NOTICES.md")
    for path, package in sorted(lock.items()):
        if not path:
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        bundled = path in ("node_modules/@decky/api", "node_modules/qrcode-generator")
        add_package("npm:" + name, package["version"], package.get("license", "NOASSERTION"), "DEPENDS_ON" if bundled else "BUILD_DEPENDENCY_OF",
                    ("Shipped separate module/preferred source" if name == "@decky/api" else "Bundled in plugin JavaScript") if bundled else "Pinned npm build environment input; inclusion here does not claim redistribution")
    files = []
    for name, data in sorted({**{"artifacts/" + name: data for name, data in artifacts.items()}, **{"runtime/" + name: data for name, data in payload.items()}, **{"decky/" + name: data for name, data in plugin.items()}}.items()):
        identifier = "SPDXRef-File-" + sha(name.encode())[:20]
        files.append({"SPDXID": identifier, "fileName": name, "checksums": [{"algorithm": "SHA256", "checksumValue": sha(data)}], "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"})
        relationships.append({"spdxElementId": "SPDXRef-Application", "relationshipType": "CONTAINS", "relatedSpdxElement": identifier})
    sbom = {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT", "name": "OBSGod-" + version,
            "documentNamespace": "https://github.com/szmyty/obsgod/sbom/" + revision + "/" + identity,
            "creationInfo": {"creators": ["Tool: obsgod-release-audit"], "created": created, "comment": "Deterministic inventory. Build inputs are distinguished from redistributed components; external OBS/Flatpak/GStreamer/Steam/Decky libraries are separately installed and outside this package inventory."},
            "packages": packages, "files": files, "relationships": relationships}
    provenance = {"_type": "https://in-toto.io/Statement/v1", "subject": subjects, "predicateType": "https://slsa.dev/provenance/v1",
                  "predicate": {"buildDefinition": {"buildType": "https://github.com/szmyty/obsgod/blob/" + revision + "/scripts/package-deck.py",
                    "externalParameters": {"version": version, "revision": revision, "platform": manifest["platform"]},
                    "internalParameters": {"go": manifest["go"], "node": manifest["node"], "npm": manifest["npm"], "capture_builder_image": capture["image_id"]},
                    "resolvedDependencies": materials},
                    "runDetails": {"builder": {"id": "urn:obsgod:local-self-reported-unsigned"}, "metadata": {"invocationId": "urn:sha256:" + identity},
                     "byproducts": [{"name": "trust-boundary", "content": {"status": "UNSIGNED", "claim": "Offline self-reported inventory only; no authenticated publisher or trusted builder identity; source and build receipts require independent review."}}]}}}
    report = {"schema_version": 1, "revision": revision, "version": version, "artifact_identity_sha256": identity,
              "integrity": "passed", "source_inventory": "passed", "preferred_source": "passed", "unsigned_provenance": "generated",
              "qualification": "unrun-by-this-audit", "publication": "not-authorized-by-this-audit",
              "remaining_gates": ["Final-revision automated qualification and review receipts", "Successful required hosted CI/review evidence; local act cannot prove GitHub services", "Actual Steam Deck/Flatpak/Gamescope/controller/audio and provider-viewer evidence", "Owner-controlled publisher/signing identity and signature verification policy", "Owner approval for release/publication/deployment and final consumer adoption proof"],
              "subjects": subjects}
    return {"sbom.spdx.json": canonical(sbom), "provenance.unsigned.json": canonical(provenance), "release-audit.json": canonical(report)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "dist")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        outputs = documents(audit(args.artifacts, args.revision))
        output = args.output.resolve()
        require(not args.output.is_symlink(), "Refusing a symlink output directory")
        output.mkdir(parents=True, exist_ok=True)
        for name in [*outputs, "AUDIT-SHA256SUMS"]:
            require(not (output / name).is_symlink(), "Refusing symlink output file")
        for name, content in outputs.items():
            (output / name).write_bytes(content)
        (output / "AUDIT-SHA256SUMS").write_text("".join(sha(content) + "  " + name + "\n" for name, content in sorted(outputs.items())))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise SystemExit("Release audit failed: " + str(error)) from error
    print(f"Offline integrity/source inventory passed for {args.revision}; unsigned evidence in {output}")


if __name__ == "__main__":
    main()
