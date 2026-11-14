"""Package-reader, source/notice and install-fixture trust boundaries."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("nfpm_release", Path(__file__).parents[1] / "nfpm-release.py")
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)
REV, VERSION = "a" * 40, "0.0.0-dev.gaaaaaaa"
IDENTITY = {"revision": REV, "tree": "b" * 40, "created": "2026-11-14T00:00:00Z", "epoch": 1794614400}
DOCS = {name: (name + " pinned source").encode() for name in N.DOCS}


def tar(files, mutate=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in files.items():
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(data), 0o755 if name.endswith("/obsgod") else 0o644
            if mutate:
                mutate(item)
            archive.addfile(item, io.BytesIO(data))
    return buffer.getvalue()


def payload():
    return {"usr/bin/obsgod": b"a static executable", **{"usr/share/doc/obsgod/" + name: data for name, data in DOCS.items()}}


def ar(members):
    result = b"!<arch>\n"
    for name, data in members.items():
        header = f"{name:<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n".encode()
        assert len(header) == 60
        result += header + data + (b"\n" if len(data) % 2 else b"")
    return result


def deb(files=None, scripts=None):
    files = payload() if files is None else files
    control = {"./control": f"Package: obsgod\nVersion: {VERSION.replace('-', '~', 1)}\nArchitecture: amd64\n".encode(),
               "./md5sums": "".join(hashlib.md5(d).hexdigest() + "  " + n + "\n" for n, d in files.items()).encode()}
    control.update(scripts or {})
    return ar({"debian-binary": b"2.0\n", "control.tar.gz": gzip.compress(tar(control), mtime=0),
               "data.tar.gz": gzip.compress(tar(files), mtime=0)})


def apk(files=None, scripts=None, mutate=None):
    files = payload() if files is None else files
    compressed = gzip.compress(tar(files, mutate), mtime=0)
    control = {".PKGINFO": (f"pkgname = obsgod\npkgver = {VERSION.replace('-', '_', 1)}\narch = x86_64\n"
                            f"datahash = {hashlib.sha256(compressed).hexdigest()}\n").encode()}
    control.update(scripts or {})
    return gzip.compress(tar(control), mtime=0) + compressed


def header(values):
    entries, store = b"", b""
    for tag, (kind, value) in sorted(values.items()):
        if kind in (6, 8):
            parts = [value] if kind == 6 else value
            data, count = b"".join(p.encode() + b"\x00" for p in parts), len(parts)
        else:
            data, count = b"".join(int(v).to_bytes(4, "big") for v in value), len(value)
        entries += struct.pack(">IIII", tag, kind, len(store), count)
        store += data
    return b"\x8e\xad\xe8\x01\x00\x00\x00\x00" + struct.pack(">II", len(values), len(store)) + entries + store


def cpio(files):
    result = bytearray()
    for index, (name, data) in enumerate([*files.items(), ("TRAILER!!!", b"")]):
        fields = [index, stat.S_IFREG | (0o755 if name.endswith("/obsgod") else 0o644), 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name) + 1, 0]
        result += b"070701" + b"".join(f"{v:08x}".encode() for v in fields) + name.encode() + b"\x00"
        result += b"\x00" * (-len(result) % 4)
        result += data
        result += b"\x00" * (-len(result) % 4)
    return bytes(result)


def rpm(files=None, updates=None):
    files = payload() if files is None else files
    names = list(files)
    values = {1000: (6, "obsgod"), 1001: (6, VERSION.replace("-", "~", 1)), 1002: (6, "1"),
              1007: (6, "reproducible.obsgod.invalid"), 1022: (6, "x86_64"),
              1124: (6, "cpio"), 1125: (6, "gzip"), 1117: (8, names), 1118: (8, ["/"]), 1116: (4, [0] * len(names)),
              1030: (4, [stat.S_IFREG | (0o755 if n.endswith("/obsgod") else 0o644) for n in names]),
              1035: (8, [hashlib.sha256(data).hexdigest() for data in files.values()]), 1036: (8, [""] * len(names)),
              1037: (4, [0] * len(names)), 1039: (8, ["root"] * len(names)), 1040: (8, ["root"] * len(names)), 5011: (4, [8])}
    values.update(updates or {})
    lead = b"\xed\xab\xee\xdb\x03\x00" + b"\x00" * 90
    signature = header({})
    padding = b"\x00" * (-(len(lead) + len(signature)) % 8)
    return lead + signature + padding + header(values) + gzip.compress(cpio(files), mtime=0)


BUILD = {"deb": deb, "rpm": rpm, "apk": apk}


class NFPMTests(unittest.TestCase):
    def test_readers_accept_only_the_exact_root_owned_regular_payload(self):
        for kind in N.FORMATS:
            with self.subTest(kind=kind):
                files, metadata = N.package_files(BUILD[kind](), kind)
                self.assertEqual(set(files), N.PAYLOAD)
                self.assertEqual(metadata["Package"], "obsgod")
                for name, content in payload().items():
                    self.assertEqual(files[name]["data"], content)

    def test_source_notices_and_exact_inventory_are_verified_before_binary_audit(self):
        for kind in N.FORMATS:
            with self.subTest(kind=kind), patch.object(N.G, "audit_payload", return_value={"dependencies": []}) as audit:
                result = N.audit_package("pkg." + kind, BUILD[kind](), ("linux", "amd64", ""), kind, VERSION, IDENTITY, DOCS)
                self.assertEqual(result["format"], kind)
                self.assertEqual(set(result["files"]), N.PAYLOAD)
                self.assertEqual(set(audit.call_args.args[2]), N.G.BASE_FILES | {"obsgod"})
                changed = payload()
                changed["usr/share/doc/obsgod/LICENSE"] = b"wrong source"
                with self.assertRaisesRegex(ValueError, "notice/source"):
                    N.audit_package("pkg", BUILD[kind](changed), ("linux", "amd64", ""), kind, VERSION, IDENTITY, DOCS)
                changed = payload()
                changed["etc/obsgod.conf"] = b"unapproved"
                with self.assertRaisesRegex(ValueError, "inventory"):
                    N.audit_package("pkg", BUILD[kind](changed), ("linux", "amd64", ""), kind, VERSION, IDENTITY, DOCS)
                with self.assertRaisesRegex(ValueError, "name/version/architecture"):
                    N.audit_package("pkg", BUILD[kind](), ("linux", "arm64", ""), kind, VERSION, IDENTITY, DOCS)

    def test_scripts_triggers_and_capabilities_are_rejected(self):
        for package in (deb(scripts={"postinst": b"danger"}), apk(scripts={".post-install": b"danger"}),
                        rpm(updates={1024: (6, "danger")}), rpm(updates={1065: (8, ["danger"])}), rpm(updates={5010: (8, ["cap_setuid=ep"])})):
            kind = "deb" if package.startswith(b"!<arch>") else "rpm" if package.startswith(b"\xed\xab") else "apk"
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "scripts|control entries|install scripts"):
                N.package_files(package, kind)

    def test_rpm_verify_file_and_transaction_script_families_fail_closed(self):
        # An early ordinary pre/post-install blacklist missed these families.
        for tag in (1079, 1091, 1092, 5066, 5067, 5068, 5069, 5070, 5071, 5072, 5073,
                    5074, 5075, 5076, 5077, 5078, 5079, 5080, 5081, 5082, 5083,
                    5100, 5101, 5102, 5103, 5104, 5105, 5106, 5107, 65535):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, "unreviewed header"):
                N.package_files(rpm(updates={tag: (6, "unexpected-script-or-extension")}), "rpm")
        files, _ = N.package_files(rpm(updates={1005: (6, "ordinary package description")}), "rpm")
        self.assertEqual(set(files), N.PAYLOAD)

    def test_focused_configuration_uses_new_private_staging_without_mutating_defaults(self):
        config = (Path(__file__).parents[2] / ".goreleaser.yml").read_text()
        before = config
        focused, staging = N.focused_configuration(config, Path("/tmp/new focused/packages"))
        self.assertEqual(config, before)
        self.assertEqual(staging, Path("/tmp/new focused/packages-notices"))
        self.assertIn("    goos: [linux]\n    goarch: [amd64]\n", focused)
        self.assertNotIn(".local-ci/generic-release", focused)
        self.assertNotIn(".local-ci/nfpm-release", focused)
        self.assertIn("--output", focused)
        self.assertIn("mode: 0644", focused)

    def test_path_links_privileged_modes_duplicates_and_non_root_are_refused(self):
        for path in ("../escape", "/etc/escape", "a/../escape", "a\\escape", "a//escape"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Unsafe"):
                N.tar_entries(tar({path: b"x"}))
        for mutate in (lambda m: setattr(m, "type", tarfile.SYMTYPE), lambda m: setattr(m, "mode", 0o4755), lambda m: setattr(m, "uid", 1000)):
            with self.assertRaises(ValueError):
                N.tar_entries(tar({"usr/bin/obsgod": b""}, mutate))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            files = {}
            N.add_entry(files, "usr/bin/obsgod", stat.S_IFREG | 0o755, 0, 0, b"x")
            N.add_entry(files, "./usr/bin/obsgod", stat.S_IFREG | 0o755, 0, 0, b"x")

    def test_compression_truncation_expansion_and_apk_hash_are_checked(self):
        with self.assertRaisesRegex(ValueError, "Truncated"):
            N.gzip_member(gzip.compress(b"data")[:-4])
        with patch.object(N, "MAX_TOTAL", 8), self.assertRaisesRegex(ValueError, "oversized"):
            N.gzip_member(gzip.compress(b"x" * 100))
        valid = apk()
        control, payload_ = N.gzip_member(valid)
        damaged = gzip.compress(control.replace(hashlib.sha256(payload_).hexdigest().encode(), b"a" * 64), mtime=0) + payload_
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            N.package_files(damaged, "apk")
        with self.assertRaisesRegex(ValueError, "digest mismatch|compression streams"):
            N.package_files(valid + gzip.compress(b"extra"), "apk")

    def test_rpm_header_and_cpio_cannot_disagree(self):
        for updates in ({1117: (8, ["evil"] * len(payload()))}, {1035: (8, ["0" * 64] * len(payload()))},
                        {1039: (8, ["nobody"] * len(payload()))}, {1037: (4, [1] * len(payload()))}):
            with self.subTest(updates=list(updates)), self.assertRaisesRegex(ValueError, "paths differ|metadata|mismatch"):
                N.package_files(rpm(updates=updates), "rpm")

    def test_unsafe_smoke_image_and_tampered_package_never_start_a_container(self):
        package = deb()
        record = {"name": "package.deb", "format": "deb", "platform": {"goos": "linux", "goarch": "amd64", "goarm": ""},
                  "sha256": N.G.sha(package), "files": {n: {"sha256": N.G.sha(v)} for n, v in payload().items()}}
        summary = {"integrity": "passed", "packages": [record]}
        with tempfile.TemporaryDirectory() as temp, patch.object(N.subprocess, "run") as run:
            directory = Path(temp)
            (directory / record["name"]).write_bytes(package)
            with self.assertRaisesRegex(ValueError, "Digest-pinned"):
                N.smoke(directory, summary, ["deb"], {"deb": "debian:latest"})
            run.assert_not_called()
            (directory / record["name"]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "differs from audit"):
                N.smoke(directory, summary, ["deb"], N.IMAGES)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
