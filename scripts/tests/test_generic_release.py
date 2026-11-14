"""Generic CLI archive trust boundaries, identity and deterministic inventories."""
import gzip
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("generic_release", Path(__file__).parents[1] / "generic-release.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)
REV = "a" * 40
IDENTITY = {"revision": REV, "tree": "b" * 40, "created": "2026-11-13T00:00:00Z", "epoch": 1794528000}
VERSION = "0.0.0-dev.gaaaaaaa"
DEP = {"name": "example.test/library", "version": "v1.2.3", "go_sum": "h1:pinned"}
PREPARED = {"THIRD_PARTY_NOTICES.md": b"Complete pinned license", "GENERIC-CLI.md": b"Generic guide",
            "GO-NOTICES.json": G.canonical({"modules": [DEP]})}


def archived(files, kind="tar.gz", mutate=None):
    out = io.BytesIO()
    if kind == "zip":
        with zipfile.ZipFile(out, "w") as archive:
            for name, data in files.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFREG | 0o755) << 16
                archive.writestr(info, data)
    else:
        with gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in files.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o755
                    if mutate:
                        mutate(info)
                    archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


def payload(target):
    system, arch, arm = target
    settings = {"GOOS": system, "GOARCH": arch, "CGO_ENABLED": "0", "vcs": "git", "vcs.revision": REV, "vcs.modified": "false",
                "-ldflags": f'"-s -w -buildid= -X main.version={VERSION} -X main.commitSHA={REV}"'}
    if arm:
        settings["GOARM"] = arm
    binary = G.canonical({"dependencies": [DEP], "settings": settings})
    return {**PREPARED, "LICENSE": b"LICENSE", "README.md": b"README.md", "CHANGELOG.md": b"CHANGELOG.md",
            "obsgod.exe" if system == "windows" else "obsgod": binary}


def binary_metadata(data):
    value = json.loads(data)
    return value["dependencies"], value["settings"]


def source_file(revision, name):
    assert revision == REV
    return name.encode()


class GenericReleaseTests(unittest.TestCase):
    def test_archive_rejects_paths_links_privileged_and_duplicate_files(self):
        for name in ("../escape", "/escape", "a/b", "a\\b", ".", ".."):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unsafe"):
                G.archive_files(archived({name: b"data"}), "tar.gz")
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE):
            def mutate(info):
                info.type, info.linkname = kind, "/outside"
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "Nonregular"):
                G.archive_files(archived({"file": b""}, mutate=mutate), "tar.gz")
        def privileged(info):
            info.mode = 0o4755
        with self.assertRaisesRegex(ValueError, "privileged"):
            G.archive_files(archived({"file": b"x"}, mutate=privileged), "tar.gz")
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as archive:
            for _ in range(2):
                archive.addfile(tarfile.TarInfo("file"), io.BytesIO(b""))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            G.archive_files(out.getvalue(), "tar.gz")

    def test_zip_symlink_and_oversized_first_tar_member_are_rejected(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"/outside")
        with self.assertRaisesRegex(ValueError, "Nonregular"):
            G.archive_files(out.getvalue(), "zip")
        info = tarfile.TarInfo("oversized")
        info.size = G.MAX_FILE + 1
        with self.assertRaisesRegex(ValueError, "expansion"):
            G.archive_files(gzip.compress(info.tobuf() + b"truncated"), "tar.gz")
        with patch.object(G, "MAX_TOTAL", 2), self.assertRaisesRegex(ValueError, "Oversized|expansion"):
            G.archive_files(archived({"file": b"123"}), "tar.gz")

    def test_exact_inventory_notices_platform_version_and_dependency_binding(self):
        target = ("linux", "amd64", "")
        with patch.object(G, "git_file", side_effect=source_file), patch.object(G, "binary_metadata", side_effect=binary_metadata):
            valid = payload(target)
            result = G.audit_archive("archive", archived(valid), target, VERSION, IDENTITY, PREPARED)
            self.assertEqual(result["dependencies"], [DEP])
            for update, message in [({"extra": b"unreviewed"}, "inventory"), ({"THIRD_PARTY_NOTICES.md": b"missing license"}, "notice"), ({"README.md": b"wrong source"}, "source file")]:
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    G.audit_archive("archive", archived({**valid, **update}), target, VERSION, IDENTITY, PREPARED)
            with self.assertRaisesRegex(ValueError, "platform"):
                G.audit_archive("archive", archived(payload(("linux", "arm64", ""))), target, VERSION, IDENTITY, PREPARED)
            with self.assertRaisesRegex(ValueError, "version/source"):
                G.audit_archive("archive", archived(valid), target, VERSION + "wrong", IDENTITY, PREPARED)
            changed = json.loads(valid["obsgod"])
            changed["dependencies"][0]["go_sum"] = "h1:wrong"
            with self.assertRaisesRegex(ValueError, "matching notices"):
                G.audit_archive("archive", archived({**valid, "obsgod": G.canonical(changed)}), target, VERSION, IDENTITY, PREPARED)

    def test_trimmed_build_has_explicit_narrower_version_evidence_and_cgo_guard(self):
        target = ("linux", "amd64", "")
        files = payload(target)
        changed = json.loads(files["obsgod"])
        changed["settings"].pop("-ldflags")
        changed["embedded_strings"] = VERSION + " " + REV
        with patch.object(G, "git_file", side_effect=source_file), patch.object(G, "binary_metadata", side_effect=binary_metadata):
            result = G.audit_archive("archive", archived({**files, "obsgod": G.canonical(changed)}), target, VERSION, IDENTITY, PREPARED)
            self.assertIn("native CLI values unrun", result["version_source_evidence"])
            changed["embedded_strings"] = "wrong version/source"
            with self.assertRaisesRegex(ValueError, "bytes absent"):
                G.audit_archive("archive", archived({**files, "obsgod": G.canonical(changed)}), target, VERSION, IDENTITY, PREPARED)
            changed["settings"]["CGO_ENABLED"] = "1"
            with self.assertRaisesRegex(ValueError, "CGO"):
                G.audit_archive("archive", archived({**files, "obsgod": G.canonical(changed)}), target, VERSION, IDENTITY, PREPARED)

    def test_vcs_requires_exact_unmodified_selected_source(self):
        target = ("linux", "amd64", "")
        files = payload(target)
        for key, value in [("vcs.revision", "b" * 40), ("vcs.modified", "true"), ("vcs", "hg")]:
            changed = json.loads(files["obsgod"])
            changed["settings"][key] = value
            with self.subTest(key=key), patch.object(G, "git_file", side_effect=source_file), patch.object(G, "binary_metadata", side_effect=binary_metadata), self.assertRaisesRegex(ValueError, "VCS source"):
                G.audit_archive("archive", archived({**files, "obsgod": G.canonical(changed)}), target, VERSION, IDENTITY, PREPARED)

    def test_all_twenty_archives_have_reproducible_artifact_specific_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sums = []
            for target in G.TARGETS:
                name = G.target_name(VERSION, target)
                data = archived(payload(target), "zip" if target[0] == "windows" else "tar.gz")
                (root / name).write_bytes(data)
                sums.append(G.sha(data) + "  " + name + "\n")
            (root / "checksums.txt").write_text("".join(sums))
            (root / "metadata.json").write_bytes(G.canonical({"commit": REV, "project_name": "obsgod", "version": VERSION}))
            with patch.object(G, "source", return_value=IDENTITY), patch.object(G, "prepare_documents", return_value=PREPARED), patch.object(G, "git_file", side_effect=source_file), patch.object(G, "binary_metadata", side_effect=binary_metadata):
                documents, summary = G.audit(root, REV)
                self.assertEqual(documents, G.audit(root, REV)[0])
                self.assertEqual(summary["archive_count"], 20)
                self.assertEqual(len(documents), 42)
                sbom = json.loads(next(data for name, data in documents.items() if name.endswith(".spdx.json")))
                self.assertEqual({p["name"] for p in sbom["packages"]}, {"obsgod", "Go standard library", DEP["name"]})
                self.assertIn("UNSIGNED", sbom["comment"])
                archive = root / summary["archives"][0]["name"]
                archive.write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    G.audit(root, REV)
                archive.unlink()
                with self.assertRaisesRegex(ValueError, "reviewed20"):
                    G.audit(root, REV)

    def test_notice_preparation_verifies_pins_licenses_and_stays_go_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            goroot, module = root / "go", root / "module"
            goroot.mkdir(); module.mkdir()
            (goroot / "LICENSE").write_bytes(b"Go standard license")
            (module / "LICENSE").write_bytes(b"Upstream full module license")
            dep = {"Path": DEP["name"], "Version": DEP["version"], "Sum": DEP["go_sum"], "Dir": str(module)}
            def command(*args, **kwargs):
                if args == ("go", "list", "-mod=readonly", "-deps", "-json", "."):
                    self.assertEqual(kwargs["env"]["CGO_ENABLED"], "0")
                    return json.dumps({"Module": dep})
                return {("go", "env", "GOVERSION"): G.GO, ("go", "mod", "verify"): "all modules verified",
                        ("go", "env", "GOROOT"): str(goroot)}[args]
            def source(revision, name):
                return {"go.mod": b"require example.test/library v1.2.3\n", "go.sum": b"example.test/library v1.2.3 h1:pinned\n", "docs/generic-cli-distribution.md": b"guide"}[name]
            with patch.object(G, "command", side_effect=command), patch.object(G, "git_file", side_effect=source):
                result = G.prepare_documents(IDENTITY)
                self.assertIn(b"Upstream full module license", result["THIRD_PARTY_NOTICES.md"])
                self.assertNotIn(b"LGPL", result["THIRD_PARTY_NOTICES.md"])
                self.assertEqual(json.loads(result["GO-NOTICES.json"])["modules"][0]["license_sha256"], G.sha(b"Upstream full module license"))
                dep["Sum"] = "h1:wrong"
                with self.assertRaisesRegex(ValueError, "go.sum"):
                    G.prepare_documents(IDENTITY)
                dep["Sum"] = DEP["go_sum"]
                dep["Replace"] = {"Dir": "/unreviewed"}
                with self.assertRaisesRegex(ValueError, "replacement"):
                    G.prepare_documents(IDENTITY)
                dep.pop("Replace")
                (module / "LICENSE").unlink()
                with self.assertRaisesRegex(ValueError, "Missing dependency license"):
                    G.prepare_documents(IDENTITY)

    def test_transitive_selected_module_uses_go_sum_without_requiring_literal_go_mod_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "LICENSE").write_text("Full upstream license")
            module = {"Path": DEP["name"], "Version": DEP["version"], "Dir": str(root)}
            def command(*args, **kwargs):
                if args == ("go", "env", "GOVERSION"):
                    return G.GO
                if args == ("go", "env", "GOROOT"):
                    return str(root)
                if args == ("go", "mod", "verify"):
                    return "all modules verified"
                return json.dumps({"Module": module})
            def source(revision, name):
                return {"go.mod": b"module root.test/main\n", "go.sum": b"example.test/library v1.2.3 h1:pinned\n", "docs/generic-cli-distribution.md": b"guide"}[name]
            with patch.object(G, "command", side_effect=command), patch.object(G, "git_file", side_effect=source):
                self.assertEqual(json.loads(G.prepare_documents(IDENTITY)["GO-NOTICES.json"])["modules"][0]["name"], DEP["name"])

    def test_binary_parser_retains_platform_and_refuses_replacements(self):
        text = "binary: go1.27.4\n\tmod\tgithub.com/szmyty/obsgod\t(devel)\n\tdep\texample.test/library\tv1.2.3\th1:pinned\n\tbuild\tGOOS=windows\n\tbuild\tGOARCH=arm64\n"
        with patch.object(G, "command", return_value=text):
            deps, settings = G.binary_metadata(b"binary")
            self.assertEqual(deps, [DEP])
            self.assertEqual(settings["GOOS"], "windows")
        with patch.object(G, "command", return_value=text + "\t=>\t/unreviewed\n"), self.assertRaisesRegex(ValueError, "replacement"):
            G.binary_metadata(b"binary")

    def test_output_refuses_symlink_parent_foreign_files_and_unexpected_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                G.write_documents(root / "link/out", {"file": b"x"})
            output = root / "out"
            G.write_documents(output, {"file": b"x"})
            (output / "extra").write_bytes(b"preserve me")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                G.write_documents(output, {"file": b"changed"})
            self.assertEqual((output / "file").read_bytes(), b"x")

    def test_output_preserves_hardlinked_symlinked_and_foreign_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_bytes(b"preserve source")
            output = root / "out"
            output.mkdir()
            (output / "file").hardlink_to(source)
            with self.assertRaisesRegex(ValueError, "hardlinked"):
                G.write_documents(output, {"file": b"changed"})
            self.assertEqual(source.read_bytes(), b"preserve source")
            (output / "file").unlink()
            (output / "file").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "symlink"):
                G.write_documents(output, {"file": b"changed"})
            (output / "file").unlink()
            (output / "file").write_bytes(b"foreign")
            real_uid = G.os.getuid()
            with patch.object(G.os, "getuid", return_value=real_uid + 1), self.assertRaisesRegex(ValueError, "current identity"):
                G.write_documents(output, {"file": b"changed"})
            self.assertEqual((output / "file").read_bytes(), b"foreign")

    def test_smoke_is_unprivileged_private_and_binds_installed_version(self):
        target = ("linux", "amd64", "")
        data = archived(payload(target))
        with patch.object(G, "git_file", side_effect=source_file), patch.object(G, "binary_metadata", side_effect=binary_metadata):
            record = G.audit_archive(G.target_name(VERSION, target), data, target, VERSION, IDENTITY, PREPARED)
        summary = {"source": IDENTITY, "version": VERSION, "archives": [record]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / record["name"]).write_bytes(data)
            with patch.object(G.os, "getuid", return_value=0), self.assertRaisesRegex(ValueError, "unprivileged"):
                G.smoke(root, summary)
            def run(args, **kwargs):
                self.assertNotIn("OBS_PASSWORD", kwargs["env"])
                self.assertIn("/.local/bin/obsgod", args[0])
                home = Path(kwargs["env"]["HOME"])
                output = {"version": G.canonical({"schema_version": 1, "name": "obsgod", "version": VERSION + " (" + REV + ")"}),
                          "config": (str(home / ".config/obsgod/config.json") + "\n").encode(), "api": b'{}\n'}[args[1]]
                return subprocess.CompletedProcess(args, 0, output, b"")
            with patch.object(G.os, "getuid", return_value=1000), patch.object(G.platform, "system", return_value="Linux"), patch.object(G.platform, "machine", return_value="x86_64"), patch.object(G.subprocess, "run", side_effect=run), patch.dict(G.os.environ, {"OBS_PASSWORD": "private-fixture"}):
                self.assertEqual(G.smoke(root, summary)["outcome"], "passed")
                (root / record["name"]).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "differs from audit"):
                    G.smoke(root, summary)


if __name__ == "__main__":
    unittest.main()
