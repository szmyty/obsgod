"""Check the installable plugin boundary, deterministic ZIP and private staging."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import decky_package as package

SPEC = importlib.util.spec_from_file_location("package_decky_entry", ROOT / "scripts/package-decky.py")
ENTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRY)
FRONTEND_SPEC = importlib.util.spec_from_file_location("private_frontend_entry", ROOT / "scripts/frontend-command.py")
FRONTEND = importlib.util.module_from_spec(FRONTEND_SPEC)
FRONTEND_SPEC.loader.exec_module(FRONTEND)


class DeckyPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="decky-package-test-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        frontend = self.work / "frontend"
        frontend.mkdir()
        for name in package.FRONTEND_FILES:
            (frontend / name).write_bytes(("fixture:" + name).encode())
        self.files = package.plugin_files(ROOT, version="0.1.0-test.1", binary=b"fixture executable",
            capture_library=b"fixture capture library", frontend=frontend, capture_source=b"fixture source",
            notices=b"fixture notices", revision="a" * 40, dirty=True)

    def test_complete_payload_and_license_module_boundary(self):
        self.assertIn("bin/obsgod", self.files)
        self.assertIn("bin/libgstobsgodcapture.so", self.files)
        self.assertIn("source/decky-api/SOURCE.tar.gz", self.files)
        self.assertNotIn("decky.py", self.files, "Do not shadow the loader's supplied module")
        self.assertNotIn("install.py", self.files, "The browser must not require a paired installer")
        for path in (ROOT / "steamdeck/decky").glob("*.py"):
            self.assertEqual(self.files[path.name], path.read_bytes())
            compile(self.files[path.name], path.name, "exec")
        manifest = json.loads(self.files["manifest.json"])
        for name, expected in manifest["files"].items():
            self.assertEqual(hashlib.sha256(self.files[name]).hexdigest(), expected)
        self.assertNotIn("manifest.json", manifest["files"])
        self.assertEqual(json.loads(self.files["plugin.json"])["flags"], [])

    def test_canonical_zip_is_repeatable_sorted_and_installable(self):
        first = package.zip_payload(self.files, 1700000001)
        second = package.zip_payload(dict(reversed(list(self.files.items()))), 1700000001)
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            for info in archive.infolist():
                self.assertTrue(info.filename.startswith("obsgod/"))
                self.assertEqual(info.external_attr >> 16 & 0o777, 0o755 if "/bin/" in info.filename else 0o644)
            archive.extractall(self.work / "unpacked")
        installed = self.work / "unpacked/obsgod"
        # No source checkout imports, loader module, installer, OBS process or
        # network is needed just to import the optional bundled setup server.
        probe = r'''
import sys,json,threading,http.client
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import setup,bridge,main
assert setup.PLUGIN_BUNDLE
assert "install" not in sys.modules and "decky" not in sys.modules
assert bridge.cli_path()==Path(sys.argv[1])/"bin/obsgod"
server=setup.SetupServer()
try:
    assert server.dependencies()["running"] is False
    assert server.install_plugin()["running"] is False
    assert server.job=={"running":False,"message":""}
    setup.run_cli=lambda action,*args,**kwargs:{"ok":True,"state":"stopped","message":"Fixture"}
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
    headers={"Authorization":"Bearer "+server.token,"Content-Type":"application/json"}
    connection.request("GET","/api/status",headers=headers)
    response=connection.getresponse();status=json.loads(response.read())
    assert response.status==200 and status["install_channel"]=="decky" and status["plugin_zip"] is None
    for action in ["dependencies","install-plugin"]:
        connection.request("POST","/api/action",body=json.dumps({"action":action}),headers=headers)
        response=connection.getresponse();reply=json.loads(response.read())
        assert response.status==200 and reply["ok"] is False and "Decky" in reply["message"]
    connection.request("POST","/api/action",body=json.dumps({"action":"configure","settings":{}}),headers=headers)
    response=connection.getresponse();assert response.status==200 and json.loads(response.read())["ok"]
    connection.close()
    server.shutdown();thread.join()
finally: server.server_close()
print(json.dumps({"plugin_bundle":True,"backend_imported":True,"legacy_installer_imported":False}))
'''
        result = subprocess.run([sys.executable, "-I", "-c", probe, str(installed)],
            capture_output=True, text=True, cwd=self.work, check=True)
        self.assertTrue(json.loads(result.stdout)["backend_imported"])

    def test_stage_matches_official_cli_defaults_contract_without_checkout_mutation(self):
        stage = self.work / "obsgod"
        package.stage_cli(self.files, stage)
        for name, data in self.files.items():
            direct = name in {"LICENSE", "main.py", "package.json", "plugin.json", "README.md"} or name.endswith(".py") and "/" not in name or name.startswith(("dist/", "bin/"))
            self.assertEqual((stage / (name if direct else "defaults/" + name)).read_bytes(), data)
        self.assertFalse((stage / "backend").exists(), "Do not rebuild Flatpak capture with a host builder")
        subprocess.run(["node", "build/verify.mjs"], cwd=stage, check=True, capture_output=True)
        (stage / "bin/obsgod").write_bytes(b"tampered")
        result = subprocess.run(["node", "build/verify.mjs"], cwd=stage, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Prepared payload changed: bin/obsgod", result.stderr)
        with self.assertRaises(FileExistsError):
            package.stage_cli(self.files, stage)

    def test_unsafe_payload_paths_privileges_and_inputs_are_rejected(self):
        for name in ("../outside", "/absolute", "a/../escape", "./relative", "a\\escape"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                package.zip_payload(dict(self.files, **{name: b"unsafe"}), 0)
        root_plugin = json.loads(self.files["plugin.json"])
        root_plugin["flags"] = ["root"]
        with self.assertRaisesRegex(ValueError, "privileges"):
            package.validate_files(dict(self.files, **{"plugin.json": json.dumps(root_plugin).encode()}))
        target = self.work / "target"
        target.write_bytes(b"preserved")
        link = self.work / "link"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            package.safe_read(link)
        os.link(target, self.work / "hardlink")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            package.safe_read(target)
        self.assertEqual(target.read_bytes(), b"preserved")

    def test_existing_or_symlink_output_is_preserved(self):
        output = self.work / "output"
        output.mkdir()
        sentinel = output / "keep"
        sentinel.write_text("preserved")
        with self.assertRaises(FileExistsError):
            ENTRY.output_directory(output)
        self.assertEqual(sentinel.read_text(), "preserved")
        link = self.work / "linked-parent"
        link.symlink_to(output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            ENTRY.output_directory(link / "new")
        self.assertFalse((output / "new").exists())

    def test_shared_writable_ancestors_cannot_redirect_reserved_output(self):
        shared = self.work / "shared"
        shared.mkdir()
        shared.chmod(0o777)
        private = shared / "private"
        private.mkdir(mode=0o700)
        for output in (shared / "candidate", private / "candidate"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "Unprotected"):
                ENTRY.output_directory(output)
            self.assertFalse(output.exists())
        uid = ROOT.stat().st_uid if os.getuid() == 0 else os.getuid()
        if os.getuid() == 0:
            for path in (self.work, shared, private):
                os.chown(path, uid, ROOT.stat().st_gid)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "unprotected"):
            FRONTEND.validate_output(ROOT, uid, private / "frontend")
        # A trusted sticky parent prevents other UIDs replacing our entry.
        # Primary output fixtures run under the current test UID.
        if os.getuid() == 0:
            os.chown(self.work, 0, 0)
            os.chown(shared, 0, 0)
        shared.chmod(0o1777)
        ENTRY.output_directory(shared / "protected-candidate")
        self.assertTrue((shared / "protected-candidate").is_dir())

    def test_bridge_keeps_legacy_layout_and_prefers_plugin_binary(self):
        root = self.work / "layout"
        root.mkdir()
        shutil.copyfile(ROOT / "steamdeck/bridge.py", root / "bridge.py")
        spec = importlib.util.spec_from_file_location("packaged_bridge", root / "bridge.py")
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        self.assertEqual(bridge.cli_path(), root / "obsgod")
        (root / "bin").mkdir()
        (root / "bin/obsgod").write_bytes(b"plugin")
        self.assertEqual(bridge.cli_path(), root / "bin/obsgod")

    def test_wrong_cli_binary_is_rejected_before_any_container_execution(self):
        fake = self.work / "fake-cli"
        fake.write_bytes(b"not the pinned release")
        with self.assertRaisesRegex(ValueError, "pinned official"):
            ENTRY.verify_cli(fake, self.files, self.work)

    def test_private_frontend_override_rejects_foreign_links_and_non_build_actions(self):
        output = self.work / "private-frontend"
        uid = ROOT.stat().st_uid if os.getuid() == 0 else os.getuid()
        if os.getuid() == 0:
            os.chown(self.work, uid, ROOT.stat().st_gid)
        FRONTEND.validate_output(ROOT, uid, output)
        output.symlink_to(self.work / "outside")
        with self.assertRaisesRegex(FRONTEND.FrontendError, "symlink"):
            FRONTEND.validate_output(ROOT, uid, output)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "only supported for build"):
            FRONTEND.run_frontend("test", output=output)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "absolute"):
            FRONTEND.validate_output(ROOT, uid, Path("relative"))
        output.unlink()
        self.work.chmod(0o755)
        with self.assertRaisesRegex(FRONTEND.FrontendError, "private"):
            FRONTEND.validate_output(ROOT, uid, output)


if __name__ == "__main__":
    unittest.main()
