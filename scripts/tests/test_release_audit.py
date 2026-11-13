"""Threat/consistency regressions for the offline release artifact auditor."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("release_audit", Path(__file__).parents[1] / "release-audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def tar_bytes(files, root="OBSGod-Capture"):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(root + "/" + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


def zip_bytes(files, root="obsgod"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(root + "/" + name)
            info.external_attr = stat.S_IFREG << 16
            archive.writestr(info, data)
    return out.getvalue()


class ReleaseAuditTests(unittest.TestCase):
    def test_rejects_unsafe_paths_and_links_without_extraction(self):
        for name in ("../outside", "/absolute", "a/../outside", "a//b", "a\\b"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unsafe"):
                AUDIT.safe_name(name)
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as archive:
            info = tarfile.TarInfo("root/link")
            info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
            archive.addfile(info)
        with self.assertRaisesRegex(ValueError, "Non-regular"):
            AUDIT.archive_files(out.getvalue(), "tar")

    def test_rejects_duplicate_and_expanding_archives(self):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as archive:
            for _ in range(2):
                info = tarfile.TarInfo("root/file")
                archive.addfile(info, io.BytesIO(b""))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            AUDIT.archive_files(out.getvalue(), "tar")
        with patch.object(AUDIT, "MAX_TOTAL", 2), self.assertRaisesRegex(ValueError, "expansion"):
            AUDIT.archive_files(tar_bytes({"file": b"123"}), "tar")

    def test_rejects_zip_symlink(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            info = zipfile.ZipInfo("root/link")
            info.external_attr = stat.S_IFLNK << 16
            archive.writestr(info, b"/etc/passwd")
        with self.assertRaisesRegex(ValueError, "Non-regular"):
            AUDIT.archive_files(out.getvalue(), "zip")

    def test_requires_exact_manifest_and_checksums(self):
        files = {"file": b"payload", "manifest.json": b"{}"}
        manifest = {"files": {"file": AUDIT.sha(b"payload")}}
        AUDIT.verify_manifest(files, manifest)
        with self.assertRaisesRegex(ValueError, "exact payload"):
            AUDIT.verify_manifest({**files, "extra": b"unexpected"}, manifest)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            AUDIT.verify_manifest({**files, "file": b"tampered"}, manifest)
        with self.assertRaisesRegex(ValueError, "Outer artifact"):
            AUDIT.verify_checksum_list(("0" * 64 + "  candidate.tar.gz\n").encode(), {"candidate.tar.gz": b"tampered"})

    def fixture(self, directory, mutate=None):
        revision, version = "a" * 40, "0.1.0-test"
        capture = {name: name.encode() for name in ("gstobsgodcapture.c", "Makefile", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "build.Dockerfile")}
        source = {"steamdeck/capture/" + name: data for name, data in capture.items()}
        source.update({"LICENSE": b"MIT license", "docs/steam-deck.md": b"guide"})
        lock = {"packages": {"node_modules/@decky/api": {"version": "1.1.3", "license": "LGPL-2.1"},
                             "node_modules/qrcode-generator": {"version": "2.0.4", "license": "MIT"}}}
        source["steamdeck/decky/package-lock.json"] = AUDIT.canonical(lock)
        plugin = {"bin/obsgod": b"go binary", "bin/libgstobsgodcapture.so": b"capture binary",
                  "LICENSE": b"MIT license", "THIRD_PARTY_NOTICES.md": b"example.test/module v1.0.0 license text",
                  "CAPTURE-SOURCE.tar.gz": tar_bytes(capture), "LICENSE.LGPL-2.1": b"LGPL license",
                  "LICENSE.qrcode-generator.txt": b"MIT QR license", "source/decky-api/src/index.ts": b"preferred source",
                  "source/decky-api/BUILDING.md": b"rebuild instructions", "source/decky-api/package.json": b'{"version":"1.1.3"}',
                  "package.json": AUDIT.canonical({"version": version})}
        source["steamdeck/decky/LICENSE.LGPL-2.1"] = plugin["LICENSE.LGPL-2.1"]
        source["steamdeck/decky/LICENSE.qrcode-generator.txt"] = plugin["LICENSE.qrcode-generator.txt"]
        for name in ("main.py", "releases.py", "paths.py", "product.py", "plugin.json"):
            plugin[name] = name.encode()
            source[("steamdeck/decky/" if name in ("main.py", "plugin.json") else "steamdeck/") + name] = plugin[name]
        runtime = {"obsgod": plugin["bin/obsgod"], "decky-install": b"helper binary", "libgstobsgodcapture.so": plugin["bin/libgstobsgodcapture.so"],
                   "CAPTURE-SOURCE.tar.gz": plugin["CAPTURE-SOURCE.tar.gz"], "LICENSE": plugin["LICENSE"],
                   "THIRD_PARTY_NOTICES.md": plugin["THIRD_PARTY_NOTICES.md"], "STEAM-DECK.md": b"guide", "update.py": b"updater"}
        source["steamdeck/update.py"] = b"updater"
        if mutate:
            mutate(runtime, plugin, source)
        runtime["obsgod-decky.zip"] = zip_bytes(plugin)
        manifest = {"version": version, "updater_version": version, "revision": revision, "dirty": False, "platform": "linux/amd64",
                    "go": "go1.27.4", "node": "24.19.0", "npm": "11.9.0", "files": {name: AUDIT.sha(data) for name, data in runtime.items()}}
        runtime["manifest.json"] = AUDIT.canonical(manifest)
        artifacts = {f"obsgod-deck_{version}_linux_amd64.tar.gz": tar_bytes(runtime, "OBSGod-" + version),
                     "obsgod-decky.zip": runtime["obsgod-decky.zip"], "manifest.json": runtime["manifest.json"]}
        updater = {"update.py": runtime["update.py"]}
        updater_manifest = {"kind": "updater", "version": version, "updater_version": version, "revision": revision, "runtime_revision": revision,
                            "platform": "linux/amd64", "files": {name: AUDIT.sha(data) for name, data in updater.items()}}
        updater["manifest.json"] = AUDIT.canonical(updater_manifest)
        updater_name = f"obsgod-one-click-update_{version}_linux_amd64.zip"
        updater_bytes = zip_bytes(updater, "OBSGod-Updater")
        receipt = {"sha256": AUDIT.sha(runtime["libgstobsgodcapture.so"]), "source_sha256": AUDIT.sha(capture["gstobsgodcapture.c"]),
                   "dockerfile_sha256": AUDIT.sha(capture["build.Dockerfile"]), "network_during_compile": False, "image_id": "sha256:" + "b" * 64}
        (directory / "SHA256SUMS").write_text("".join(AUDIT.sha(data) + "  " + name + "\n" for name, data in artifacts.items()))
        (directory / "UPDATER-SHA256SUMS").write_text(AUDIT.sha(updater_bytes) + "  " + updater_name + "\n")
        for name, data in {**artifacts, updater_name: updater_bytes, "updater-manifest.json": updater["manifest.json"], "capture-build.json": AUDIT.canonical(receipt)}.items():
            (directory / name).write_bytes(data)
        return source, revision

    def run_fixture(self, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source, revision = self.fixture(directory, mutate)
            with patch.object(AUDIT, "git", side_effect=lambda rev, path: source.get(path, b"build source")), \
                    patch.object(AUDIT, "go_inventory", return_value=[{"name": "example.test/module", "version": "v1.0.0", "go_sum": "h1:example"}]), \
                    patch.object(AUDIT.subprocess, "check_output", return_value=b"1700000000"):
                return AUDIT.documents(AUDIT.audit(directory, revision))

    def test_deterministic_documents_describe_real_selected_artifacts(self):
        first, second = self.run_fixture(), self.run_fixture()
        self.assertEqual(first, second)
        report = json.loads(first["release-audit.json"])
        self.assertEqual(report["integrity"], "passed")
        self.assertEqual(report["qualification"], "unrun-by-this-audit")
        provenance = json.loads(first["provenance.unsigned.json"])
        self.assertIn("unsigned", provenance["predicate"]["runDetails"]["builder"]["id"])
        self.assertEqual(report["subjects"], provenance["subject"])

    def test_detects_disagreement_between_plugin_and_runtime(self):
        with self.assertRaisesRegex(ValueError, "Decky runtime differs"):
            self.run_fixture(lambda runtime, plugin, source: plugin.update({"bin/obsgod": b"different build"}))

    def test_missing_preferred_source_is_not_release_ready(self):
        with self.assertRaisesRegex(ValueError, "preferred TypeScript"):
            self.run_fixture(lambda runtime, plugin, source: plugin.pop("source/decky-api/src/index.ts"))

    def test_runtime_source_cannot_be_relabelled_with_another_revision(self):
        with self.assertRaisesRegex(ValueError, "Runtime source differs"):
            self.run_fixture(lambda runtime, plugin, source: runtime.update({"update.py": b"unreviewed source"}))

    def test_capture_source_must_match_git_even_when_payload_hashes_are_valid(self):
        with self.assertRaisesRegex(ValueError, "Capture preferred source differs"):
            self.run_fixture(lambda runtime, plugin, source: source.update({"steamdeck/capture/gstobsgodcapture.c": b"different revision"}))


if __name__ == "__main__":
    unittest.main()
