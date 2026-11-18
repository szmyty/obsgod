"""Exercise primary entry failure, immutable outputs and artifact refusals."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import decky_package as package

SPEC = importlib.util.spec_from_file_location("primary_qualification", ROOT / "scripts/qualify-decky-build.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class PrimaryQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="primary-qualification-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.uid, self.gid = ROOT.stat().st_uid, ROOT.stat().st_gid
        if os.getuid() == 0:
            os.chown(self.work, self.uid, self.gid)

    def invoke(self, output, revision="f" * 40, overrides=None):
        env = os.environ.copy()
        for key in ("OBSGOD_LOCAL_SCRATCH", "OBSGOD_LOCAL_OWNER_UID"):
            env.pop(key, None)
        env.update(overrides or {})
        return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/qualify-decky-build.py"),
                               "--revision", revision, "--output", str(output)],
                              cwd=ROOT, env=env, capture_output=True, text=True)

    def test_actual_primary_refusal_fails_command_and_cannot_accept_candidate(self):
        """No stub builder: wrong revision reaches real primary.main before Go/Docker."""
        output = self.work / "qualification"
        result = self.invoke(output)
        self.assertNotEqual(result.returncode, 0)
        record = json.loads((output / "qualification.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("archive", record)
        self.assertEqual(record["uid"], self.uid)
        self.assertNotEqual(record["uid"], 0, "Do not bypass the primary owner/root guard")
        self.assertEqual(len(record["builds"]), 1)
        first = record["builds"][0]
        self.assertNotEqual(first["exit_code"], 0)
        self.assertIn(str(ROOT / "scripts/package-decky.py"), first["command"])
        self.assertIn("Only the checked-out full source revision may label this build",
                      (output / "first.log").read_text())
        self.assertEqual(first["log_sha256"], hashlib.sha256((output / "first.log").read_bytes()).hexdigest())
        self.assertFalse((output / "second").exists())
        for key in ("HOME", "TMPDIR", "GOCACHE", "GOMODCACHE"):
            path = Path(record["build_context"][key])
            self.assertTrue(path.is_relative_to(output), "Build temporaries stay on the output's daemon-visible mount")
            self.assertEqual(path.stat().st_uid, self.uid)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)

    def test_profile_uses_separate_owner_caches_and_preserves_existing_modules(self):
        scratch = self.work / "scratch"
        scratch.mkdir(mode=0o700)
        modules = scratch / f"go-mod-user-{self.uid}"
        modules.mkdir(mode=0o700)
        sentinel = modules / "preserved"
        sentinel.write_text("existing module cache")
        if os.getuid() == 0:
            for path in (scratch, modules):
                os.chown(path, self.uid, self.gid)
        output = self.work / "profile"
        result = self.invoke(output, overrides={"OBSGOD_LOCAL_SCRATCH": str(scratch),
                                                "OBSGOD_LOCAL_OWNER_UID": str(self.uid)})
        self.assertNotEqual(result.returncode, 0, "The actual wrong-revision primary still fails")
        record = json.loads((output / "qualification.json").read_text())
        self.assertEqual(record["build_context"]["GOCACHE"], str(scratch / f"go-build-user-{self.uid}"))
        self.assertEqual(record["build_context"]["GOMODCACHE"], str(modules))
        self.assertEqual(sentinel.read_text(), "existing module cache")
        self.assertEqual(len(record["builds"]), 1)

    def test_profile_refuses_linked_compiler_cache_without_touching_target(self):
        scratch = self.work / "scratch"
        scratch.mkdir(mode=0o700)
        target = self.work / "keep-cache"
        target.mkdir(mode=0o700)
        sentinel = target / "keep"
        sentinel.write_text("preserved")
        (scratch / f"go-build-user-{self.uid}").symlink_to(target, target_is_directory=True)
        if os.getuid() == 0:
            os.chown(scratch, self.uid, self.gid)
        output = self.work / "refused"
        result = self.invoke(output, overrides={"OBSGOD_LOCAL_SCRATCH": str(scratch)})
        self.assertNotEqual(result.returncode, 0)
        record = json.loads((output / "qualification.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["builds"], [])
        self.assertEqual(sentinel.read_text(), "preserved")

    def test_existing_evidence_and_linked_output_are_preserved(self):
        output = self.work / "existing"
        output.mkdir()
        sentinel = output / "keep"
        sentinel.write_text("old evidence")
        result = self.invoke(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "old evidence")
        self.assertFalse((output / "qualification.json").exists())
        linked = self.work / "linked"
        linked.symlink_to(output, target_is_directory=True)
        result = self.invoke(linked)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "old evidence")

    def test_protected_0755_parent_accepts_context_but_writable_parent_is_refused(self):
        self.work.chmod(0o755)
        output = self.work / "hosted-parent"
        result = self.invoke(output)
        self.assertNotEqual(result.returncode, 0, "The real primary still refuses the wrong revision")
        record = json.loads((output / "qualification.json").read_text())
        self.assertEqual(len(record["builds"]), 1, "The wrapper must reach the actual primary entry")
        self.assertIn("Only the checked-out full source revision", (output / "first.log").read_text())
        for path in (output, output / "context", *map(Path, record["build_context"].values())):
            self.assertEqual(path.stat().st_uid, self.uid)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        self.work.chmod(0o777)
        refused = self.work / "unprotected-parent"
        result = self.invoke(refused)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(refused.exists(), "No evidence/cache/output is created through writable ancestry")

    def fixture(self):
        frontend = self.work / "frontend"
        frontend.mkdir()
        for name in package.FRONTEND_FILES:
            (frontend / name).write_bytes(("fixture:" + name).encode())
        capture = b"synthetic library, not native qualification"
        native = {"sha256": hashlib.sha256(capture).hexdigest(),
                  "source_sha256": hashlib.sha256((ROOT / "steamdeck/capture/gstobsgodcapture.c").read_bytes()).hexdigest(),
                  "dockerfile_sha256": hashlib.sha256((ROOT / "steamdeck/capture/build.Dockerfile").read_bytes()).hexdigest(),
                  "network_during_compile": False}
        files = package.plugin_files(ROOT, version="0.1.0-test.1", binary=b"synthetic executable",
            capture_library=capture, frontend=frontend, capture_source=b"synthetic preferred source",
            notices=b"synthetic notices", revision="a" * 40, dirty=False,
            capture_receipt=package.json_bytes(native))
        sources = {"synthetic source": "b" * 64}
        output = self.work / "fixture"
        output.mkdir()
        return output, files, sources

    def write_fixture(self, output, files, sources):
        archive = package.zip_payload(files, 1700000001)
        checksum = hashlib.sha256(archive).hexdigest()
        (output / "obsgod-decky.zip").write_bytes(archive)
        (output / "SHA256SUMS").write_text(checksum + "  obsgod-decky.zip\n")
        receipt = {"revision": "a" * 40, "version": "0.1.0-test.1", "dirty": False,
                   "platform": "linux/amd64", "source_tools": package.TOOLS,
                   "archive": "obsgod-decky.zip", "sha256": checksum,
                   "source_files_sha256": sources, "payload_files": len(files),
                   "official_cli": {"status": "unrun"}}
        (output / "build-receipt.json").write_bytes(package.json_bytes(receipt))

    def inspect(self, output, sources):
        return HELPER.inspect_build(output, "a" * 40, "0.1.0-test.1", sources)

    def test_valid_synthetic_inventory_is_read_without_extracting_or_executing(self):
        output, files, sources = self.fixture()
        self.write_fixture(output, files, sources)
        result = self.inspect(output, sources)
        self.assertEqual(result["payload_files"], len(files))
        self.assertEqual(result["source_private_inventory"], "passed")
        self.assertEqual(set(p.name for p in output.iterdir()),
                         {"obsgod-decky.zip", "SHA256SUMS", "build-receipt.json"})

    def test_extra_private_file_and_rehashed_source_tampering_are_refused(self):
        output, files, sources = self.fixture()
        files["secrets.json"] = b'{"stream_key":"synthetic-private-canary"}'
        manifest = json.loads(files["manifest.json"])
        manifest["files"]["secrets.json"] = hashlib.sha256(files["secrets.json"]).hexdigest()
        files["manifest.json"] = package.json_bytes(manifest)
        self.write_fixture(output, files, sources)
        with self.assertRaisesRegex(ValueError, "private state and extra files"):
            self.inspect(output, sources)
        del files["secrets.json"]
        del manifest["files"]["secrets.json"]
        files["bridge.py"] = b"# source changed after declared revision\n"
        manifest["files"]["bridge.py"] = hashlib.sha256(files["bridge.py"]).hexdigest()
        files["manifest.json"] = package.json_bytes(manifest)
        self.write_fixture(output, files, sources)
        with self.assertRaisesRegex(ValueError, "checked-out source"):
            self.inspect(output, sources)

    def test_outer_receipt_and_inner_readiness_identity_must_match_actual_bytes(self):
        output, files, sources = self.fixture()
        self.write_fixture(output, files, sources)
        with self.assertRaisesRegex(ValueError, "source snapshot"):
            self.inspect(output, {"different source": "c" * 64})
        manifest = json.loads(files["manifest.json"])
        manifest["dirty"] = True
        files["manifest.json"] = package.json_bytes(manifest)
        self.write_fixture(output, files, sources)
        with self.assertRaisesRegex(ValueError, "manifest has inconsistent"):
            self.inspect(output, sources)


if __name__ == "__main__":
    unittest.main()
