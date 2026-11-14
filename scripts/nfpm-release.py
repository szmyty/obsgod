#!/usr/bin/env python3
"""Inspect unsigned Linux packages and test package managers in disposable containers.

No package is installed on the host. Publication, OBS integration and other
native platforms are outside this source-bound package check.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import zlib

SPEC = importlib.util.spec_from_file_location("generic_release", Path(__file__).with_name("generic-release.py"))
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)
ROOT, MAX_TOTAL, MAX_FILE = G.ROOT, G.MAX_TOTAL, G.MAX_FILE
FORMATS = ("deb", "rpm", "apk")
DOCS = G.BASE_FILES | {"SOURCE.json"}
PAYLOAD = {"usr/bin/obsgod"} | {"usr/share/doc/obsgod/" + name for name in DOCS}
DIRECTORIES = {"usr", "usr/bin", "usr/share", "usr/share/doc", "usr/share/doc/obsgod"}
ARCH = {
    "amd64": {"deb": "amd64", "rpm": "x86_64", "apk": "x86_64"},
    "arm64": {"deb": "arm64", "rpm": "aarch64", "apk": "aarch64"},
    "386": {"deb": "i386", "rpm": "i386", "apk": "x86"},
    "armv6": {"deb": "armel", "rpm": "armv6hl", "apk": "armhf"},
    "armv7": {"deb": "armhf", "rpm": "armv7hl", "apk": "armv7"},
}
# Explicitly resolved image digests, not mutable runner labels. The native smoke
# supports Linux amd64 only; the package audit still covers all selected targets.
IMAGES = {
    "deb": "debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc",
    "rpm": "fedora:43@sha256:f01112b9a1f1d0504ad962d9adfa401425033f8ab067e0a821904ebdde5b8ca5",
    "apk": "alpine:3.23@sha256:469c9ea410b9215eaee7976ba6c0639039b444be8e5d638f7abbada189971eb2",
}
# The reviewed NFPM version emits only these metadata/payload fields. A list of
# known-dangerous scripts is insufficient: RPM also has verify, file-trigger,
# transaction-trigger and pre/post-untransaction script families. Unknown header
# fields fail closed until the pinned package writer's output is reviewed.
RPM_SIGNATURE_TAGS = {62, 269, 273, 1000, 1004, 1007}
RPM_HEADER_TAGS = {63, 100, 1000, 1001, 1002, 1004, 1005, 1006, 1007, 1009, 1014, 1015,
                   1020, 1021, 1022, 1028, 1030, 1033, 1034, 1035, 1036, 1037, 1039, 1040,
                   1044, 1045, 1047, 1048, 1049, 1050, 1064, 1095, 1096, 1097, 1112, 1113,
                   1116, 1117, 1118, 1124, 1125, 1126, 1140, 5011, 5092, 5093}


def require(condition, message):
    G.require(condition, message)


def member_name(name):
    require(isinstance(name, str) and "\\" not in name and not name.startswith("/"), "Unsafe package path")
    name = name.removeprefix("./").removesuffix("/")
    require(name and all(p not in ("", ".", "..") for p in name.split("/"))
            and bool(re.fullmatch(r"[A-Za-z0-9_.+/-]+", name)), "Unsafe package path")
    return name


def add_entry(files, name, mode, uid, gid, data):
    name = member_name(name)
    require(name not in files and uid == gid == 0 and not mode & 0o7000,
            "Duplicate, non-root or privileged package entry")
    directory = stat.S_ISDIR(mode)
    require(directory or stat.S_ISREG(mode), "Package links/devices are not permitted")
    require(0 <= len(data) <= MAX_FILE and (not directory or not data), "Invalid package member size")
    if directory:
        require(name in DIRECTORIES and stat.S_IMODE(mode) == 0o755, "Unexpected package directory")
    files[name] = {"data": data, "mode": stat.S_IMODE(mode), "directory": directory}


def tar_entries(data):
    require(len(data) <= MAX_TOTAL, "Package expansion limit exceeded")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for index, member in enumerate(archive, 1):
            require(index <= 40 and (member.isfile() or member.isdir()), "Too many or nonregular package members")
            require(not set(member.pax_headers) - {"mtime", "APK-TOOLS.checksum.SHA1"}, "Unexpected package extended attributes")
            require(0 <= member.size <= MAX_FILE, "Package member expansion limit exceeded")
            content = archive.extractfile(member).read() if member.isfile() else b""
            require(len(content) == member.size, "Truncated package member")
            if "APK-TOOLS.checksum.SHA1" in member.pax_headers:
                require(hashlib.sha1(content).hexdigest() == member.pax_headers["APK-TOOLS.checksum.SHA1"], "APK member digest mismatch")
            mode = (stat.S_IFDIR if member.isdir() else stat.S_IFREG) | member.mode
            add_entry(files, member.name, mode, member.uid, member.gid, content)
    return files


def gzip_member(data):
    decoder = zlib.decompressobj(31)
    expanded = decoder.decompress(data, MAX_TOTAL + 1)
    require(decoder.eof and len(expanded) <= MAX_TOTAL, "Truncated or oversized package compression")
    return expanded, decoder.unused_data


def fields(data, separator):
    result = {}
    for line in data.decode("utf-8").splitlines():
        if not line or line.startswith(("#", " ")):
            continue
        require(separator in line, "Malformed package metadata")
        key, value = line.split(separator, 1)
        require(key not in result, "Duplicate package metadata")
        result[key] = value
    return result


def deb_files(data):
    require(data.startswith(b"!<arch>\n"), "Invalid Debian archive")
    members, offset = {}, 8
    while offset < len(data):
        require(len(data) - offset >= 60, "Truncated Debian member")
        header = data[offset:offset + 60]
        require(header[58:] == b"`\n", "Invalid Debian member header")
        name, size = header[:16].decode().strip().removesuffix("/"), int(header[48:58])
        require(name not in members and 0 <= size <= MAX_TOTAL and offset + 60 + size <= len(data), "Invalid Debian member size")
        members[name] = data[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
    require(set(members) == {"debian-binary", "control.tar.gz", "data.tar.gz"}
            and members["debian-binary"] == b"2.0\n", "Unexpected Debian archive inventory")
    control_data, unused = gzip_member(members["control.tar.gz"])
    require(not unused, "Unexpected Debian control stream")
    # Control entries are inspected separately: no maintainer scripts, conffiles,
    # hooks or triggers can be smuggled into an apparently harmless CLI package.
    require(len(control_data) <= 1000000, "Oversized Debian control archive")
    with tarfile.open(fileobj=io.BytesIO(control_data), mode="r:") as archive:
        entries = list(archive)
        require({m.name.removeprefix("./") for m in entries} == {"control", "md5sums"}
                and len(entries) == 2 and all(m.isfile() and m.uid == m.gid == 0 and m.mode == 0o644 and m.size <= 100000 for m in entries),
                "Unexpected Debian control entries or scripts")
        control = {m.name.removeprefix("./"): archive.extractfile(m).read() for m in entries}
    payload, unused = gzip_member(members["data.tar.gz"])
    require(not unused, "Unexpected Debian payload stream")
    files = tar_entries(payload)
    checksums = {}
    for line in control["md5sums"].decode().splitlines():
        digest, name = line.split("  ", 1)
        name = member_name(name)
        require(name not in checksums and re.fullmatch(r"[0-9a-f]{32}", digest), "Invalid Debian payload digest")
        checksums[name] = digest
    regular = {name: item for name, item in files.items() if not item["directory"]}
    require(set(checksums) == set(regular) and all(hashlib.md5(v["data"]).hexdigest() == checksums[n] for n, v in regular.items()),
            "Debian metadata/payload digest mismatch")
    return files, fields(control["control"], ": ")


def rpm_header(data, offset):
    require(data[offset:offset + 8] == b"\x8e\xad\xe8\x01\x00\x00\x00\x00" and len(data) >= offset + 16, "Invalid RPM header")
    count, size = struct.unpack(">II", data[offset + 8:offset + 16])
    require(count <= 300 and size <= 1000000 and offset + 16 + count * 16 + size <= len(data), "Oversized or truncated RPM header")
    start = offset + 16 + count * 16
    store, values = data[start:start + size], {}
    for index in range(count):
        tag, kind, at, length = struct.unpack(">IIII", data[offset + 16 + index * 16:offset + 32 + index * 16])
        require(tag not in values and at < len(store) and length <= 1000000, "Invalid RPM header field")
        if kind in (6, 8, 9):
            require(0 < length <= 10000 and (kind != 6 or length == 1), "Invalid RPM string count")
            strings, current = [], at
            for _ in range(length):
                end = store.find(b"\x00", current)
                require(end >= 0, "Unterminated RPM string")
                strings.append(store[current:end].decode("utf-8"))
                current = end + 1
            values[tag] = strings[0] if kind == 6 else strings
        else:
            widths = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}
            require(kind in widths and at + length * widths[kind] <= len(store), "Invalid RPM typed value")
            raw = store[at:at + length * widths[kind]]
            values[tag] = ([int.from_bytes(raw[i:i + widths[kind]], "big") for i in range(0, len(raw), widths[kind])]
                           if kind in (3, 4, 5) else raw.hex())
    return values, start + size


def cpio_entries(data):
    files, offset = {}, 0
    while True:
        require(offset + 110 <= len(data) and data[offset:offset + 6] == b"070701", "Invalid RPM cpio payload")
        values = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        _, mode, uid, gid, links, _, size, _, _, rmajor, rminor, namesize, checksum = values
        require(0 < namesize <= 256 and 0 <= size <= MAX_FILE and rmajor == rminor == checksum == 0, "Invalid RPM cpio entry")
        offset += 110
        require(offset + namesize <= len(data) and data[offset + namesize - 1] == 0, "Truncated RPM cpio name")
        name = data[offset:offset + namesize - 1].decode("utf-8")
        offset = (offset + namesize + 3) // 4 * 4
        require(offset + size <= len(data), "Truncated RPM cpio data")
        content = data[offset:offset + size]
        offset = (offset + size + 3) // 4 * 4
        if name == "TRAILER!!!":
            require(size == 0 and not any(data[offset:]), "Trailing RPM cpio data")
            return files
        require(len(files) < 40 and (stat.S_ISDIR(mode) or links == 1), "Too many or hardlinked RPM files")
        add_entry(files, name, mode, uid, gid, content)


def rpm_files(data):
    require(data[:6] == b"\xed\xab\xee\xdb\x03\x00" and len(data) > 112, "Invalid RPM lead")
    signatures, offset = rpm_header(data, 96)
    require(set(signatures) <= RPM_SIGNATURE_TAGS, "Unexpected RPM signature: unsigned snapshot expected")
    header, offset = rpm_header(data, (offset + 7) // 8 * 8)
    require(set(header) <= RPM_HEADER_TAGS and header.get(1124) == "cpio" and header.get(1125) == "gzip", "Unexpected RPM scripts, unreviewed header fields or payload encoding")
    payload, unused = gzip_member(data[offset:])
    require(not unused, "Trailing RPM payload")
    files = cpio_entries(payload)
    basenames, directory_names, indexes = header.get(1117, []), header.get(1118, []), header.get(1116, [])
    require(len(basenames) == len(indexes) == len(files), "RPM header/payload inventory mismatch")
    names = []
    for name, index in zip(basenames, indexes):
        require(0 <= index < len(directory_names), "Invalid RPM directory index")
        names.append(member_name((directory_names[index] + name).removeprefix("/")))
    require(len(set(names)) == len(names) and set(names) == set(files), "RPM header/payload paths differ")
    for tag in (1030, 1035, 1036, 1037, 1039, 1040):
        require(len(header.get(tag, [])) == len(names), "Incomplete RPM file metadata")
    algorithm = header.get(5011, [1])
    require(algorithm in ([1], [8]), "Unsupported RPM file digest")
    digest = hashlib.sha256 if algorithm == [8] else hashlib.md5
    for index, name in enumerate(names):
        entry = files[name]
        require(header[1036][index] == "" and header[1037][index] == 0 and header[1039][index] == header[1040][index] == "root"
                and stat.S_IMODE(header[1030][index]) == entry["mode"] and digest(entry["data"]).hexdigest() == header[1035][index],
                "RPM file ownership/flags/digest mismatch")
    return files, {"Package": header.get(1000), "Version": header.get(1001), "Architecture": header.get(1022),
                                  "Release": header.get(1002), "BuildHost": header.get(1007)}


def apk_files(data):
    control, payload = gzip_member(data)
    require(len(control) <= 1000000, "Oversized APK control archive")
    with tarfile.open(fileobj=io.BytesIO(control), mode="r:") as archive:
        entries = list(archive)
        require(len(entries) == 1 and entries[0].name == ".PKGINFO" and entries[0].isfile()
                and entries[0].size < 100000, "Unexpected APK metadata or install scripts")
        metadata = fields(archive.extractfile(entries[0]).read(), " = ")
    require(metadata.get("datahash") == G.sha(payload), "APK payload digest mismatch")
    expanded, unused = gzip_member(payload)
    require(not unused, "Unexpected APK compression streams")
    return tar_entries(expanded), {"Package": metadata.get("pkgname"), "Version": metadata.get("pkgver"), "Architecture": metadata.get("arch")}


def package_files(data, kind):
    require(0 < len(data) <= MAX_TOTAL and kind in FORMATS, "Invalid package format or size")
    return {"deb": deb_files, "rpm": rpm_files, "apk": apk_files}[kind](data)


def prepared(identity):
    documents = {**G.prepare_documents(identity), **{name: G.git_file(identity["revision"], name) for name in ("LICENSE", "README.md", "CHANGELOG.md")}}
    documents["SOURCE.json"] = G.canonical({"schema_version": 1, "source": identity,
        "preferred_application_source": "https://github.com/szmyty/obsgod/tree/" + identity["revision"],
        "go_module_sources": "GO-NOTICES.json records exact linked-module source checksums; full notices in THIRD_PARTY_NOTICES.md",
        "scope": "Generic statically linked Go CLI only; no separate Decky/native/OBS payload is redistributed",
        "source_sha256": {name: G.sha(G.git_file(identity["revision"], name)) for name in ("go.mod", "go.sum", ".goreleaser.yml", "scripts/nfpm-release.py")}})
    return documents


def package_name(version, target, kind):
    return G.target_name(version, target).removesuffix(".tar.gz") + "." + kind


def audit_package(name, data, target, kind, version, identity, documents):
    files, metadata = package_files(data, kind)
    regular = {n: item for n, item in files.items() if not item["directory"]}
    require(set(regular) == PAYLOAD, "Package exact inventory mismatch")
    for name_, expected in documents.items():
        item = regular["usr/share/doc/obsgod/" + name_]
        require(item["data"] == expected and item["mode"] == 0o644, "Package notice/source content or mode mismatch")
    require(regular["usr/bin/obsgod"]["mode"] == 0o755, "Package executable mode mismatch")
    arch = target[1] + ("v" + target[2] if target[2] else "")
    expected_version = version.replace("-", "_" if kind == "apk" else "~", 1)
    require(metadata.get("Package") == "obsgod" and metadata.get("Architecture") == ARCH[arch][kind]
            and metadata.get("Version") == expected_version, "Package name/version/architecture mismatch")
    if kind == "rpm":
        require(metadata.get("BuildHost") == "reproducible.obsgod.invalid", "RPM build host is not deterministic")
    flattened = {doc: regular["usr/share/doc/obsgod/" + doc] for doc in G.BASE_FILES}
    flattened["obsgod"] = regular["usr/bin/obsgod"]
    result = G.audit_payload(name, data, flattened, target, version, identity, {k: v for k, v in documents.items() if k in ("THIRD_PARTY_NOTICES.md", "GO-NOTICES.json", "GENERIC-CLI.md")})
    result.update({"format": kind, "package_metadata": metadata,
                   "files": {n: {"sha256": G.sha(v["data"]), "mode": v["mode"]} for n, v in sorted(regular.items())}})
    return result


def audit(directory, revision, target=None):
    identity = G.source(revision)
    require(directory.is_dir() and not directory.is_symlink(), "Unsafe package artifact directory")
    metadata = json.loads((directory / "metadata.json").read_bytes())
    version = metadata.get("version", "")
    require(metadata.get("commit") == revision and metadata.get("project_name") == "obsgod"
            and re.fullmatch(r"0\.0\.0-dev\.g[0-9a-f]{7,40}", version)
            and revision.startswith(version.split(".g", 1)[1]), "Snapshot source/version mismatch")
    targets = {t for t in G.TARGETS if t[0] == "linux"}
    if target:
        require(target == "linux-amd64", "Only the explicit Linux amd64 focused subset is supported")
        targets = {("linux", "amd64", "")}
    expected = {package_name(version, t, f): (t, f) for t in targets for f in FORMATS}
    require({p.name for p in directory.iterdir() if p.suffix.removeprefix(".") in FORMATS} == set(expected), "Package matrix differs from selected targets")
    sums = {}
    for line in (directory / "checksums.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(name not in sums and re.fullmatch(r"[0-9a-f]{64}", digest), "Invalid snapshot checksum")
        sums[name] = digest
    documents, output, records = prepared(identity), {}, []
    for name, (platform_, kind) in sorted(expected.items()):
        path = directory / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_TOTAL, "Unsafe package artifact")
        data = path.read_bytes()
        require(G.sha(data) == sums.get(name), "Package checksum mismatch")
        record = audit_package(name, data, platform_, kind, version, identity, documents)
        sidecars = G.sidecars(record, version, identity)
        provenance_name = name + ".provenance.unsigned.json"
        provenance = json.loads(sidecars[provenance_name])
        build = provenance["predicate"]["buildDefinition"]
        build["buildType"] = "urn:obsgod:nfpm-cli-snapshot"
        build["externalParameters"]["format"] = kind
        build["resolvedDependencies"].append({"uri": "scripts/nfpm-release.py", "digest": {"sha256": G.sha(G.git_file(revision, "scripts/nfpm-release.py"))}})
        sidecars[provenance_name] = G.canonical(provenance)
        output.update(sidecars)
        records.append(record)
    summary = {"schema_version": 1, "source": identity, "version": version, "packages": records,
        "package_count": len(records), "matrix": "focused-linux-amd64" if target else "all-five-linux-targets",
        "integrity": "passed", "native_execution": "unrun-by-audit", "publication": "not-authorized-by-audit",
        "limits": ["Bounded static package inspection is not package-manager execution or OBS integration.",
                   "Sidecars are UNSIGNED self-reported inventories, not authenticated publisher attestations.",
                   "Native ARM/386 runtime, other platforms, actual Deck and release acceptance remain separate."]}
    output["SUMMARY.json"] = G.canonical(summary)
    output["AUDIT-SHA256SUMS"] = "".join(G.sha(data) + "  " + name + "\n" for name, data in sorted(output.items())).encode()
    return output, summary


def focused_configuration(config, output):
    """Derive only target/output/private staging paths from the source config."""
    require(config.count("dist: dist/snapshot\n") == 1 and config.count("    goos:\n") == 1, "Review changed snapshot configuration before focusing")
    config = config.replace("dist: dist/snapshot\n", "dist: " + json.dumps(str(output)) + "\n", 1)
    start, end = config.index("    goos:\n"), config.index("\narchives:\n")
    config = config[:start] + "    goos: [linux]\n    goarch: [amd64]\n" + config[end:]
    staging = output.parent / (output.name + "-notices")
    for kind in ("generic", "nfpm"):
        location = staging / kind
        # Previous ACT runs can leave root-owned ignored catalogs. Keep those
        # bytes/modes untouched; the focused build owns its new private staging.
        hook = "python3 scripts/" + kind + "-release.py prepare"
        require(config.count("    - " + hook + "\n") == 1, "Review changed notice-preparation hook")
        config = config.replace("    - " + hook + "\n", "    - " + json.dumps(hook + " --output " + shlex.quote(str(location))) + "\n", 1)
        config = config.replace(".local-ci/" + kind + "-release", str(location))
    return config, staging


def focused(output, goreleaser):
    """Derive a one-target config without modifying/cleaning the existing dist."""
    identity = G.source(G.command("git", "rev-parse", "HEAD"))
    output = output.absolute()
    require(not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)), "Focused output must be a new safe directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    config, staging = focused_configuration(G.git_file(identity["revision"], ".goreleaser.yml").decode(), output)
    require(not staging.exists() and not any(p.is_symlink() for p in (staging, *staging.parents)), "Focused notice staging must be new and safe")
    with tempfile.TemporaryDirectory(prefix="obsgod-focused-config-") as temporary:
        path = Path(temporary) / "goreleaser.yml"
        path.write_text(config)
        subprocess.run([str(goreleaser), "release", "--snapshot", "--skip=publish,sign", "--parallelism", "2", "--config", str(path)], cwd=ROOT, check=True)
    return {"source_revision": identity["revision"], "scope": "focused-linux-amd64; not full matrix", "derived_config_sha256": G.sha(config.encode()), "artifacts": str(output), "notice_staging": str(staging)}


def smoke(directory, summary, formats, images, previous=None):
    require(sys.platform.startswith("linux") and os.uname().machine in ("x86_64", "amd64"), "Native Linux amd64 Docker host required")
    require(summary.get("integrity") == "passed", "Successful selected-source audit required")
    require("," not in str(directory.absolute()) and not directory.is_symlink(), "Unsafe Docker package mount path")
    selected = {r["format"]: r for r in summary["packages"] if r["platform"] == {"goos": "linux", "goarch": "amd64", "goarm": ""}}
    require(set(formats) <= selected.keys(), "Selected Linux amd64 package absent")
    results = []
    for kind in formats:
        record, image = selected[kind], images[kind]
        require(re.fullmatch(r"[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}", image), "Digest-pinned smoke image required")
        package = directory / G.safe_member(record["name"])
        require(package.is_file() and not package.is_symlink() and package.stat().st_size <= MAX_TOTAL and G.sha(package.read_bytes()) == record["sha256"], "Smoke package differs from audit")
        payload, _ = package_files(package.read_bytes(), kind)
        require(set(n for n, v in payload.items() if not v["directory"]) == set(record["files"])
                and all(G.sha(payload[n]["data"]) == v["sha256"] for n, v in record["files"].items()), "Smoke package payload differs from audit")
        subprocess.run(["docker", "image", "inspect", image], stdout=subprocess.DEVNULL, check=True)
        container = subprocess.check_output(["docker", "run", "--detach", "--rm", "--pull=never", "--network=none",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--mount", "type=bind,src=" + str(directory.absolute()) + ",dst=/packages,readonly",
            "--entrypoint=/bin/sh", image, "-c", "sleep 300"], text=True).strip()
        require(re.fullmatch(r"[0-9a-f]{64}", container), "Unexpected disposable container identity")
        calls = []
        def execute(args, user=None):
            cmd = ["docker", "exec"]
            if user:
                cmd += ["--user", user, "--env", "HOME=/home/package-user", "--env", "XDG_CONFIG_HOME=/home/package-user/.config"]
            cmd += [container, *args]
            p = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
            calls.append({"arguments": args, "uid": user or "0", "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr})
            require(p.returncode == 0, "Disposable " + kind + " command failed: " + p.stderr[-1500:])
            return p.stdout
        try:
            execute(["/bin/sh", "-eu", "-c", "mkdir -p /home/package-user/.config/obsgod /home/package-user/Videos; printf preserve > /home/package-user/.config/obsgod/fixture; printf media > /home/package-user/Videos/fixture; chmod 777 /home/package-user; chmod -R a+rX /home/package-user"])
            install = {"deb": ["dpkg", "--install"], "rpm": ["rpm", "-U", "--replacepkgs", "--oldpackage"], "apk": ["apk", "add", "--allow-untrusted", "--no-network"]}[kind]
            # An optional separately audited older source can exercise a genuine
            # cross-revision package replacement/upgrade; never fabricate one.
            if previous:
                old = next(r for r in previous["packages"] if r["format"] == kind and r["platform"] == record["platform"])
                require(old["name"] != record["name"] and old["name"] in {p.name for p in directory.iterdir()}, "Previous audited package must be copied into the read-only fixture directory")
                require(G.sha((directory / old["name"]).read_bytes()) == old["sha256"], "Previous package differs from its audit")
                previous_payload, _ = package_files((directory / old["name"]).read_bytes(), kind)
                require(previous["source"]["revision"] != summary["source"]["revision"]
                        and set(n for n, v in previous_payload.items() if not v["directory"]) == set(old["files"])
                        and all(G.sha(previous_payload[n]["data"]) == v["sha256"] for n, v in old["files"].items()),
                        "Previous package source/payload failed current parser preflight")
                execute([*install, "/packages/" + G.safe_member(old["name"])])
            execute([*install, "/packages/" + record["name"]])
            for filename, expected in record["files"].items():
                digest = execute(["sha256sum", "/" + filename]).split()[0]
                require(digest == expected["sha256"], "Installed package file differs from audit")
            value = json.loads(execute(["/usr/bin/obsgod", "version", "--json"], "65534:65534"))
            require(value["version"] == summary["version"] + " (" + summary["source"]["revision"] + ")", "Installed package version/source mismatch")
            execute(["/usr/bin/obsgod", "--help"], "65534:65534")
            execute(["/usr/bin/obsgod", "api", "capabilities"], "65534:65534")
            require(execute(["/usr/bin/obsgod", "config", "path"], "65534:65534").strip() == "/home/package-user/.config/obsgod/config.json", "Installed config path mismatch")
            execute([*install, "/packages/" + record["name"]])
            remove = {"deb": ["dpkg", "--purge", "obsgod"], "rpm": ["rpm", "-e", "obsgod"], "apk": ["apk", "del", "--no-network", "obsgod"]}[kind]
            execute(remove)
            execute(["/bin/sh", "-eu", "-c", "test ! -e /usr/bin/obsgod; test ! -e /usr/share/doc/obsgod/SOURCE.json; test \"$(cat /home/package-user/.config/obsgod/fixture)\" = preserve; test \"$(cat /home/package-user/Videos/fixture)\" = media; test ! -e /home/package-user/.config/obsgod/config.json"])
            results.append({"format": kind, "package": record["name"], "sha256": record["sha256"], "image": image,
                "outcome": "passed", "commands": calls, "package_replacement": "previous audited source to current" if previous else "unrun; no previous audited source supplied",
                "limits": "Disposable Linux amd64 package lifecycle and unprivileged offline CLI only; no OBS, actual Deck, host installation or native ARM proof."})
        finally:
            subprocess.run(["docker", "rm", "--force", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return {"schema_version": 1, "source_revision": summary["source"]["revision"], "outcome": "passed", "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--output", type=Path, default=ROOT / ".local-ci/nfpm-release")
    a = commands.add_parser("audit")
    a.add_argument("--revision", required=True)
    a.add_argument("--artifacts", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    a.add_argument("--target", choices=["linux-amd64"])
    f = commands.add_parser("focused")
    f.add_argument("--output", type=Path, required=True)
    f.add_argument("--goreleaser", type=Path, required=True)
    s = commands.add_parser("smoke")
    s.add_argument("--artifacts", type=Path, required=True)
    s.add_argument("--audit", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--formats", nargs="+", choices=FORMATS, default=list(FORMATS))
    s.add_argument("--image", action="append", default=[], help="format=repository@sha256:digest; pre-pull explicitly")
    s.add_argument("--previous-audit", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            identity = G.source(G.command("git", "rev-parse", "HEAD"))
            G.write_documents(args.output, prepared(identity), identity["epoch"])
            print("Prepared source-bound NFPM documentation")
        elif args.action == "focused":
            print(json.dumps(focused(args.output, args.goreleaser)))
        elif args.action == "audit":
            documents, summary = audit(args.artifacts, args.revision, args.target)
            G.write_documents(args.output, documents)
            print(json.dumps({"packages": summary["package_count"], "matrix": summary["matrix"], "integrity": "passed"}))
        else:
            require(not args.audit.is_symlink() and args.audit.stat().st_size <= 2_000_000, "Unsafe package audit")
            images = dict(IMAGES)
            for definition in args.image:
                kind, image = definition.split("=", 1)
                require(kind in FORMATS, "Unknown package image")
                images[kind] = image
            require(set(args.formats) <= images.keys(), "Supply digest-pinned --image for every selected format")
            previous = json.loads(args.previous_audit.read_bytes()) if args.previous_audit else None
            if previous:
                require(previous.get("integrity") == "passed", "Previous successful audit required")
            report = smoke(args.artifacts, json.loads(args.audit.read_bytes()), args.formats, images, previous)
            G.write_documents(args.output, {"linux-package-smoke.json": G.canonical(report)})
            print(json.dumps({"outcome": "passed", "formats": args.formats, "source_revision": report["source_revision"]}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration, subprocess.SubprocessError, tarfile.TarError, zlib.error, struct.error) as error:
        print("NFPM check failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
