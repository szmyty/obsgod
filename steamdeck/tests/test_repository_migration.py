"""Publisher-transition rehearsal using real installers and temporary files.

The future publisher exists only in separately loaded fixture source. Production
trust remains unchanged. Decky/Flatpak/OBS observations and network responses are
explicit fixtures; this is not physical Deck or published-repository evidence.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OLD_REPOSITORY = "szmyty/obsgod"
FUTURE_REPOSITORY = "egohygiene/decky-stream"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryMigration(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="obsgod-migration-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.environment = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / "custom config"),
            "XDG_DATA_HOME": str(self.home / "custom data"),
            "XDG_STATE_HOME": str(self.home / "custom state"),
            "XDG_CACHE_HOME": str(self.home / "custom cache"),
            "XDG_CURRENT_DESKTOP": "KDE", "DESKTOP_SESSION": "plasma",
            "DECKY_HOME": str(self.home / "homebrew"),
        }
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, self.environment))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.base = self.home / "custom data/obsgod"
        self.config = self.home / "custom config/obsgod"
        self.plugin = self.home / "homebrew/plugins/obsgod"
        self.calls = []
        self.output_state = {
            "ok": True, "configured": True, "state": "stopped",
            "stream": {"active": False}, "recording": False,
            "output_known": True, "process": "absent",
            "media": {"known": True, "replay_active": False},
        }
        self.bridge = SimpleNamespace(run_cli=self.observe)
        self.decky = SimpleNamespace(
            status=lambda: {"ok": True, "version": "3.3.1"},
            helper_request=self.plugin_request,
        )
        self.sentinels = {}
        for relative, value in {
            "custom config/obsgod/deck.json": b'{"capture_mode":"game"}',
            "custom config/obsgod/secrets.json": b'{"fixture_key":"not-a-real-secret"}',
            "custom state/obsgod/diagnostics/history": b"prior diagnostics",
            "Videos/OBSGod/2026-11-14 00-00-00.mkv": b"preserved recording",
            ".var/app/com.obsproject.Studio/config/obs-studio/ordinary.json": b"ordinary OBS",
            "homebrew/plugins/OtherPlugin/keep": b"another plugin",
        }.items():
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
            self.sentinels[path] = value

    def observe(self, operation, **_kwargs):
        self.calls.append(("obs", operation))
        if operation == "status":
            return dict(self.output_state)
        if operation == "restart":
            # This fixture models closing only the already-confirmed idle app.
            self.output_state["process"] = "absent"
            return {"ok": True}
        self.fail("Migration must not broadcast or mutate OBS output: " + operation)

    def plugin_request(self, operation, package, manifest):
        self.assertEqual(operation, "install")
        package = Path(package)
        data = (package / "obsgod-decky.zip").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["files"]["obsgod-decky.zip"])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), ["OBSGod/plugin.json"])
            plugin = json.loads(archive.read("OBSGod/plugin.json"))
        self.assertEqual(plugin, {"name": "OBSGod", "version": manifest["version"]})
        self.calls.append(("plugin", manifest["version"]))
        self.plugin.mkdir(parents=True, exist_ok=True)
        (self.plugin / "plugin.json").write_text(json.dumps(plugin))
        return {"ok": True, "version": manifest["version"]}

    def package(self, version, repository):
        package = self.root / ("package-" + version)
        package.mkdir()
        names = {
            "obsgod", "setup.py", "bridge.py", "setup.html", "setup.js", "setup.css",
            "uninstall.py", "obsgod-decky.zip", "LICENSE", "THIRD_PARTY_NOTICES.md",
            "STEAM-DECK.md", "decky-install", "decky.py", "install.py",
            "Install OBSGod.desktop", "update.py", "releases.py",
            "Update OBSGod.desktop", "Update OBSGod.sh", "libgstobsgodcapture.so",
            "CAPTURE-SOURCE.tar.gz", "paths.py", "product.py", "Uninstall OBSGod.desktop",
        }
        for name in names:
            original = ROOT / name
            content = original.read_bytes() if original.is_file() else ("fixture " + name).encode()
            if name == "releases.py":
                before = b'REPOSITORY = "' + OLD_REPOSITORY.encode() + b'"'
                self.assertEqual(content.count(before), 1)
                content = content.replace(before, b'REPOSITORY = "' + repository.encode() + b'"')
            (package / name).write_bytes(content)
        with zipfile.ZipFile(package / "obsgod-decky.zip", "w") as archive:
            archive.writestr("OBSGod/plugin.json", json.dumps({"name": "OBSGod", "version": version}))
        manifest = {
            "version": version, "revision": "e" * 40, "platform": "linux/amd64",
            "dirty": False, "updater_version": version,
            "files": {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in sorted(names)},
        }
        (package / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        return package, manifest

    def installer(self, package):
        module = load(package / "install.py", "migration_installer")
        original = module.load_module

        def dependency(name, path):
            if Path(path).name == "decky.py":
                return self.decky
            if Path(path).name == "bridge.py":
                return self.bridge
            return original(name, path)

        self.stack.enter_context(patch.object(module, "load_module", side_effect=dependency))
        self.stack.enter_context(patch.object(module, "ensure_dependencies"))
        return module

    def assert_preserved(self):
        for path, value in self.sentinels.items():
            self.assertEqual(path.read_bytes(), value, str(path))
        self.assertFalse((self.home / "custom data/decky-stream").exists())
        self.assertFalse((self.home / "custom config/decky-stream").exists())
        self.assertFalse((self.home / "homebrew/plugins/decky-stream").exists())
        self.assertFalse((self.home / "homebrew/plugins/Decky Stream").exists())
        self.assertFalse(any(action in {"start", "stream-start", "stream", "configure"}
                             for kind, action in self.calls if kind == "obs"))

    def assert_pair(self, version):
        self.assertEqual(json.loads((self.base / "current/manifest.json").read_text())["version"], version)
        self.assertEqual(json.loads((self.plugin / "plugin.json").read_text())["version"], version)
        alias = self.home / ".local/bin/obsgod"
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.readlink(), self.base / "current/obsgod")
        self.assert_preserved()

    def published_fixture(self, publisher, package, manifest, corrupt=False):
        version = manifest["version"]
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for path in sorted(package.iterdir()):
                if not path.is_file():
                    continue
                data = path.read_bytes()
                if corrupt and path.name == "obsgod":
                    data += b"corruption"
                item = tarfile.TarInfo("OBSGod-" + version + "/" + path.name)
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
        archive_data = output.getvalue()
        archive_name = "obsgod-deck_" + version + "_linux_amd64.tar.gz"
        base = "https://github.com/" + publisher.REPOSITORY + "/releases/download/v" + version + "/"
        manifest_data = (package / "manifest.json").read_bytes()
        sums = (hashlib.sha256(manifest_data).hexdigest() + "  manifest.json\n" +
                hashlib.sha256(archive_data).hexdigest() + "  " + archive_name + "\n").encode()
        release = {"tag_name": "v" + version, "prerelease": True, "draft": False,
                   "assets": [{"name": name, "browser_download_url": base + name}
                              for name in (archive_name, "manifest.json", "SHA256SUMS")]}
        responses = {
            publisher.RELEASES_URL: json.dumps([release]).encode(),
            "https://api.github.com/repos/" + publisher.REPOSITORY + "/commits/v" + version:
                json.dumps({"sha": manifest["revision"]}).encode(),
            base + "manifest.json": manifest_data,
            base + "SHA256SUMS": sums,
            base + archive_name: archive_data,
        }

        def open_response(request, **_kwargs):
            self.assertTrue(publisher._safe_url(request.full_url))
            return io.BytesIO(responses[request.full_url])

        return open_response

    def update(self, installer_package, published_package, manifest, *, repair=False, corrupt=False):
        updater = load(installer_package / "update.py", "migration_updater")
        publisher = load(installer_package / "releases.py", "migration_publisher")
        original = updater.load_module

        def dependency(name, path):
            if Path(path).name == "bridge.py":
                return self.bridge
            if Path(path).name == "install.py":
                return self.installer(Path(path).parent)
            return original(name, path)

        with patch.object(updater, "release_module", return_value=publisher), \
                patch.object(updater, "load_module", side_effect=dependency), \
                patch.object(publisher, "_open_url", side_effect=self.published_fixture(
                    publisher, published_package, manifest, corrupt=corrupt)):
            return updater.run_update(repair=repair)

    def test_old_to_new_manual_installer_repair_update_rollback_and_uninstall(self):
        old, old_manifest = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        transition, transition_manifest = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        future, future_manifest = self.package("0.1.0-deck.12", FUTURE_REPOSITORY)
        self.installer(old).install(launch=False)
        self.assert_pair(old_manifest["version"])
        self.installer(transition).install(launch=False)
        self.assert_pair(transition_manifest["version"])
        self.update(transition, transition, transition_manifest, repair=True)
        self.assert_pair(transition_manifest["version"])
        self.assertEqual(len(list((self.base / "releases").iterdir())), 2)
        self.update(transition, future, future_manifest)
        self.assert_pair(future_manifest["version"])
        # Explicit rollback uses a verified previous installer; it is not a
        # version downgrade silently authorized by ordinary update discovery.
        self.installer(old).install(launch=False)
        self.assert_pair(old_manifest["version"])
        self.installer(future).install(launch=False)
        self.assert_pair(future_manifest["version"])
        uninstaller = load(future / "uninstall.py", "migration_uninstaller")

        def remove_plugin(home, plugin_path):
            self.assertEqual(home, self.home)
            self.assertEqual(Path(plugin_path), self.plugin)
            shutil.rmtree(self.plugin)

        with patch.object(uninstaller, "run_cli", side_effect=self.observe), \
                patch.object(uninstaller, "remove_plugin", side_effect=remove_plugin):
            plan = uninstaller.build_plan(self.home)
            uninstaller.apply_plan(plan, self.home)
        self.assertFalse((self.base / "current").is_symlink())
        self.assertFalse((self.base / "releases").exists())
        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.home / ".local/bin/obsgod").is_symlink())
        self.assert_preserved()

    def test_verified_plugin_then_activation_failure_restores_previous_pair(self):
        old, old_manifest = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        future, _ = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        self.installer(old).install(launch=False)
        installer = self.installer(future)
        with patch.object(installer, "activate_release", side_effect=OSError("fixture activation interruption")), \
                self.assertRaisesRegex(RuntimeError, "previous plugin was restored"):
            installer.install(launch=False)
        self.assert_pair(old_manifest["version"])
        recovery = json.loads((self.base / "installation-recovery.json").read_text())
        self.assertTrue(recovery["plugin_rollback_confirmed"])
        self.assertFalse(recovery["app_activation_changed"])

    def test_corrupted_future_payload_cannot_change_installed_pair(self):
        old, _ = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        transition, transition_manifest = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        future, future_manifest = self.package("0.1.0-deck.12", FUTURE_REPOSITORY)
        self.installer(old).install(launch=False)
        self.installer(transition).install(launch=False)
        before = len([x for x in self.calls if x[0] == "plugin"])
        with self.assertRaisesRegex(RuntimeError, "payload checksum"):
            self.update(transition, future, future_manifest, corrupt=True)
        self.assert_pair(transition_manifest["version"])
        self.assertEqual(before, len([x for x in self.calls if x[0] == "plugin"]))

    def test_active_or_unknown_output_blocks_manual_migration_without_plugin_change(self):
        old, old_manifest = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        future, _ = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        self.installer(old).install(launch=False)
        before = len([x for x in self.calls if x[0] == "plugin"])
        for changed in ({"stream": {"active": True}}, {"output_known": False},
                        {"media": {"known": False, "replay_active": False}},
                        {"media": {"known": True, "replay_active": True}}):
            with self.subTest(changed=changed), patch.dict(self.output_state, changed), \
                    self.assertRaisesRegex(RuntimeError, "active, busy or unconfirmed"):
                self.installer(future).install(launch=False)
            self.assert_pair(old_manifest["version"])
        self.assertEqual(before, len([x for x in self.calls if x[0] == "plugin"]))

    def test_two_existing_xdg_locations_require_explicit_repair(self):
        old, old_manifest = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        future, _ = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        self.installer(old).install(launch=False)
        legacy = self.home / ".local/share/obsgod"
        legacy.mkdir(parents=True)
        (legacy / "keep").write_text("second existing location")
        before = len(self.calls)
        with self.assertRaisesRegex(ValueError, "Two OBSGod installation locations"):
            self.installer(future).install(launch=False)
        self.assert_pair(old_manifest["version"])
        self.assertEqual((legacy / "keep").read_text(), "second existing location")
        self.assertEqual(before, len(self.calls))

    def test_repository_is_build_identity_not_environment_or_redirect_trust(self):
        old, _ = self.package("0.1.0-deck.10", OLD_REPOSITORY)
        future, _ = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        with patch.dict(os.environ, {"OBSGOD_REPOSITORY": FUTURE_REPOSITORY,
                                     "GITHUB_REPOSITORY": FUTURE_REPOSITORY}):
            old_publisher = load(old / "releases.py", "migration_old_source")
        new_publisher = load(future / "releases.py", "migration_future_source")
        self.assertEqual(old_publisher.REPOSITORY, OLD_REPOSITORY)
        self.assertEqual(new_publisher.REPOSITORY, FUTURE_REPOSITORY)
        for publisher, allowed, refused in ((old_publisher, OLD_REPOSITORY, FUTURE_REPOSITORY),
                                            (new_publisher, FUTURE_REPOSITORY, OLD_REPOSITORY)):
            for repository, expected in ((allowed, True), (refused, False), ("attacker/decky-stream", False)):
                urls = ["https://api.github.com/repos/" + repository + "/releases?per_page=100",
                        "https://api.github.com/repos/" + repository + "/commits/v1.0.0",
                        "https://raw.githubusercontent.com/" + repository + "/" + "a" * 40 + "/manifest.json",
                        "https://github.com/" + repository + "/releases/download/v1.0.0/archive.tar.gz"]
                for url in urls:
                    with self.subTest(publisher=allowed, url=url):
                        self.assertEqual(publisher._safe_url(url), expected)
                if not expected:
                    source = urllib.request.Request(publisher.RELEASES_URL)
                    with self.assertRaises(publisher.ReleaseError):
                        publisher._ProjectRedirects().redirect_request(source, None, 302, "Found", {}, urls[0])
            mutable = "https://raw.githubusercontent.com/" + allowed + "/main/manifest.json"
            self.assertFalse(publisher._safe_url(mutable))

    def test_future_immutable_artifact_metadata_stays_in_its_exact_repository(self):
        future, manifest = self.package("0.1.0-deck.11", FUTURE_REPOSITORY)
        publisher = load(future / "releases.py", "migration_future_artifacts")
        name = "obsgod-deck_" + manifest["version"] + "_linux_amd64.tar.gz"
        commit = "a" * 40
        expected = "https://raw.githubusercontent.com/" + FUTURE_REPOSITORY + "/" + commit + "/"
        for body_url in (expected + name,
                         "https://github.com/" + FUTURE_REPOSITORY + "/raw/" + commit + "/" + name):
            release = {"tag_name": "v" + manifest["version"], "assets": [], "body": "[Download](" + body_url + ")"}
            archive, locations = publisher._locations(release, manifest["version"])
            self.assertEqual(archive, name)
            self.assertEqual(locations, {n: expected + n for n in (name, "manifest.json", "SHA256SUMS")})
            for invalid in (body_url.replace(FUTURE_REPOSITORY, OLD_REPOSITORY),
                            body_url.replace(commit, "main"),
                            body_url.replace(FUTURE_REPOSITORY, "attacker/decky-stream")):
                with self.subTest(invalid=invalid), self.assertRaises(publisher.ReleaseError):
                    publisher._locations(dict(release, body="[Download](" + invalid + ")"), manifest["version"])


if __name__ == "__main__":
    unittest.main()
