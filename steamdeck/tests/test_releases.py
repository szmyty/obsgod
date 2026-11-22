import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("obsgod_releases", Path(__file__).resolve().parents[1] / "releases.py")
releases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(releases)
REPOSITORY_URL = "https://github.com/" + releases.REPOSITORY
RAW_URL = "https://raw.githubusercontent.com/" + releases.REPOSITORY
API_URL = "https://api.github.com/repos/" + releases.REPOSITORY


class ReleaseChecks(unittest.TestCase):
    def fixture(self, version="0.1.0-deck.10", raw=False):
        revision = "1" * 40
        archive = "obsgod-deck_" + version + "_linux_amd64.tar.gz"
        manifest = {"version": version, "revision": revision, "platform": "linux/amd64", "dirty": False, "updater_version": version, "files": {name: "a" * 64 for name in ["obsgod", "obsgod-decky.zip", "setup.py", "bridge.py"]}}
        data = json.dumps(manifest).encode()
        base = RAW_URL + "/" + "2" * 40 + "/" if raw else REPOSITORY_URL + "/releases/download/v" + version + "/"
        values = {
            API_URL + "/commits/v" + version: json.dumps({"sha": revision}).encode(),
            base + "manifest.json": data,
            base + "SHA256SUMS": (hashlib.sha256(data).hexdigest() + "  manifest.json\n" + hashlib.sha256(b"archive").hexdigest() + "  " + archive + "\n").encode(),
        }
        release = {"tag_name": "v" + version, "target_commitish": revision, "prerelease": "-" in version, "draft": False, "assets": [] if raw else [{"name": name, "browser_download_url": base + name} for name in [archive, "manifest.json", "SHA256SUMS"]], "body": "[Download](" + base + archive + ")" if raw else ""}
        return release, values, manifest

    def run_check(self, entries, values, installed="0.1.0-deck.9", channel="preview"):
        values = dict(values, **{releases.RELEASES_URL: json.dumps(entries).encode()})
        with patch.object(releases, "_read_url", side_effect=lambda url, *args, **kwargs: values[url]):
            return releases.check_updates(installed, channel)

    def test_numeric_preview_order_and_updater_only_release_are_distinct(self):
        runtime, values, _ = self.fixture()
        updater = {"tag_name": "v99.0.0-updater.1", "prerelease": True, "assets": [], "draft": False}
        result = self.run_check([updater, runtime], values)
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "0.1.0-deck.10")
        self.assertNotIn("archive_url", result)
        self.assertEqual(self.run_check([runtime], values, installed="0.1.0-deck.10")["state"], "up-to-date")
        self.assertEqual(self.run_check([runtime], values, installed="0.1.0-deck.11")["state"], "up-to-date")

    def test_stable_channel_does_not_select_preview_or_draft(self):
        preview, values, _ = self.fixture("9.0.0-preview.1")
        stable, stable_values, _ = self.fixture("1.0.0")
        values.update(stable_values)
        draft = dict(preview, tag_name="v10.0.0", prerelease=False, draft=True)
        result = self.run_check([preview, draft, stable], values, "0.1.0", "stable")
        self.assertEqual(result["latest_version"], "1.0.0")
        self.assertEqual(self.run_check([preview], {}, "0.1.0", "stable")["state"], "unavailable")

    def test_immutable_legacy_artifact_accepted_and_mutable_or_foreign_rejected(self):
        release, values, _ = self.fixture(raw=True)
        self.assertTrue(self.run_check([release], values)["available"])
        for bad in [release["body"].replace("2" * 40, "master"), release["body"].replace(releases.REPOSITORY, "attacker/obsgod")]:
            result = self.run_check([dict(release, body=bad)], {})
            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "unsupported")

    def test_incomplete_latest_release_is_not_misreported_as_up_to_date(self):
        release, _, _ = self.fixture()
        release["assets"] = []
        result = self.run_check([release], {})
        self.assertEqual(result["state"], "unsupported")
        self.assertFalse(result["ok"])

    def test_foreign_asset_or_duplicate_name_refused(self):
        release, values, _ = self.fixture()
        bad = dict(release, assets=[dict(a) for a in release["assets"]])
        bad["assets"][0]["browser_download_url"] = "https://example.invalid/installer"
        self.assertFalse(self.run_check([bad], values)["ok"])
        bad = dict(release, assets=release["assets"] + [release["assets"][0]])
        self.assertFalse(self.run_check([bad], values)["ok"])

    def test_manifest_hash_source_platform_and_dirty_must_match(self):
        release, values, manifest = self.fixture()
        manifest_url = next(url for url in values if url.endswith("manifest.json"))
        checksum_url = next(url for url in values if url.endswith("SHA256SUMS"))
        tampered = dict(values, **{manifest_url: b"tampered"})
        self.assertIn("checksum", self.run_check([release], tampered)["message"])
        for changed in [{"revision": "3" * 40}, {"platform": "windows/amd64"}, {"dirty": True}, {"version": "0.1.0-deck.11"}]:
            altered = dict(manifest, **changed)
            data = json.dumps(altered).encode()
            altered_values = dict(values)
            altered_values[manifest_url] = data
            altered_values[checksum_url] = values[checksum_url].replace(hashlib.sha256(values[manifest_url]).hexdigest().encode(), hashlib.sha256(data).hexdigest().encode())
            self.assertFalse(self.run_check([release], altered_values)["ok"])

    def test_checksums_reject_duplicate_missing_and_path_entries(self):
        release, values, _ = self.fixture()
        checksum_url = next(url for url in values if url.endswith("SHA256SUMS"))
        for data in [values[checksum_url] * 2, b"", b"a" * 64 + b"  ../escape\n"]:
            self.assertFalse(self.run_check([release], dict(values, **{checksum_url: data}))["ok"])

    def test_actual_tag_revision_is_checked_instead_of_creation_target(self):
        release, values, _ = self.fixture()
        tag_url = API_URL + "/commits/" + release["tag_name"]
        values[tag_url] = json.dumps({"sha": "9" * 40}).encode()
        result = self.run_check([release], values)
        self.assertFalse(result["ok"])
        self.assertIn("revision", result["message"])

    def test_offline_and_rate_limit_are_not_up_to_date(self):
        for failure, state in [(urllib.error.URLError("fixture-private-details"), "offline"), (urllib.error.HTTPError(releases.RELEASES_URL, 429, "fixture-private-details", {}, None), "error")]:
            with patch.object(releases, "_open_url", side_effect=failure):
                result = releases.check_updates("0.1.0-deck.9")
            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], state)
            self.assertNotIn("fixture-private-details", json.dumps(result))

    def test_download_checksum_and_source_url_fail_before_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive"
            candidate = {"archive_url": REPOSITORY_URL + "/releases/download/v1.0.0/obsgod-deck_1.0.0_linux_amd64.tar.gz", "archive_sha256": hashlib.sha256(b"expected").hexdigest()}
            with patch.object(releases, "_open_url", return_value=io.BytesIO(b"corrupted")):
                with self.assertRaisesRegex(releases.ReleaseError, "checksum"):
                    releases.download_archive(candidate, path)
            with patch.object(releases, "_open_url") as opened:
                with self.assertRaisesRegex(releases.ReleaseError, "unsupported"):
                    releases.download_archive(dict(candidate, archive_url="https://example.invalid/installer"), Path(temporary) / "second")
                opened.assert_not_called()

    def test_url_policy_and_version_validation(self):
        for url in ["http://github.com/" + releases.REPOSITORY + "/releases/download/v1.0.0/archive", RAW_URL + "/master/archive", "https://github.com:invalid/" + releases.REPOSITORY + "/releases/download/v1.0.0/archive", REPOSITORY_URL + "/releases/download/v1.0.0/archive?secret=fixture", "https://github.com@evil.invalid/" + releases.REPOSITORY + "/releases/download/v1.0.0/archive"]:
            self.assertFalse(releases._safe_url(url))
        for value in ["unknown", "01.0.0", "1.0.0-preview.01", "1.0.0/../../escape", None]:
            with self.assertRaises(releases.ReleaseError):
                releases.version_key(value)
        self.assertGreater(releases.version_key("1.0.0"), releases.version_key("1.0.0-rc.99"))

    def test_only_exact_build_selected_repository_is_trusted(self):
        def urls(repository):
            return ("https://api.github.com/repos/" + repository + "/releases?per_page=100",
                    "https://api.github.com/repos/" + repository + "/commits/v1.0.0",
                    "https://github.com/" + repository + "/releases/download/v1.0.0/archive.tar.gz",
                    "https://raw.githubusercontent.com/" + repository + "/" + "1" * 40 + "/manifest.json")
        for url in urls(releases.REPOSITORY):
            self.assertTrue(releases._safe_url(url), url)
        # The old source becomes an explicitly rejected publisher after staging.
        for repository in {"szmyty/obsgod", "unlisted-owner/deckystream"} - {releases.REPOSITORY}:
            for url in urls(repository):
                self.assertFalse(releases._safe_url(url), url)

    def test_installed_versions_detect_mismatch_without_reading_secrets(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"HOME": temporary}):
            home = Path(temporary)
            release = home / ".local/share/obsgod/releases/0.1.0-deck.10"
            release.mkdir(parents=True)
            (release.parent.parent / "current").symlink_to(release)
            (release / "manifest.json").write_text(json.dumps({"version": "0.1.0-deck.10", "revision": "1" * 40, "updater_version": "0.1.0-deck.10"}))
            values = releases.current_versions("0.1.0-deck.9")
            self.assertEqual(values["app"], "0.1.0-deck.10")
            self.assertTrue(values["mismatch"])
            self.assertEqual(values["updater"], "0.1.0-deck.10")
            (release / "manifest.json").unlink()
            (release / "manifest.json").symlink_to(home / "private-secrets")
            self.assertEqual(releases.current_versions("0.1.0-deck.9")["app"], "unknown")

    def test_decky_explicit_user_context_finds_xdg_install_without_global_home_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "deck"
            release = home / "data/obsgod/releases/0.1.0-deck.7"
            release.mkdir(parents=True)
            (release.parent.parent / "current").symlink_to(release)
            (release / "manifest.json").write_text(json.dumps({"version": "0.1.0-deck.7", "revision": "1" * 40}))
            previous_home = os.environ.get("HOME")
            context = {"HOME": str(home), "XDG_DATA_HOME": str(home / "data")}
            self.assertEqual(releases.current_versions("0.1.0-deck.7", environ=context)["app"], "0.1.0-deck.7")
            self.assertEqual(os.environ.get("HOME"), previous_home)
            for invalid in ["relative", "/tmp/invalid\npath"]:
                context["XDG_DATA_HOME"] = invalid
                self.assertEqual(releases.current_versions("0.1.0-deck.7", environ=context)["app"], "unknown")


if __name__ == "__main__":
    unittest.main()


class RedirectTrust(unittest.TestCase):
    def redirect(self, source, target):
        return releases._ProjectRedirects().redirect_request(
            releases.urllib.request.Request(source), None, 302, "Found", {}, target)

    def test_official_asset_redirect_is_allowed_once(self):
        source = REPOSITORY_URL + "/releases/download/v1.0.0/archive.tar.gz"
        target = "https://release-assets.githubusercontent.com/github-production-release-asset/1263344065/abcdef12-abcd-1234-abcd-123456abcdef?sig=fixture"
        self.assertEqual(self.redirect(source, target).full_url, target)
        with self.assertRaises(releases.ReleaseError):
            self.redirect(target, target + "&extra=1")

    def test_changed_owner_api_raw_or_untrusted_download_redirects_fail_closed(self):
        approved = [releases.RELEASES_URL,
                    RAW_URL + "/" + "1" * 40 + "/manifest.json",
                    REPOSITORY_URL + "/releases/download/v1.0.0/archive.tar.gz"]
        targets = ["https://api.github.com/repos/new-owner/decky-stream/releases?per_page=100",
                   "https://github.com/new-owner/decky-stream/releases/download/v1.0.0/archive.tar.gz",
                   "https://attacker.invalid/file", "http://release-assets.githubusercontent.com/file",
                   "https://[invalid", "https://release-assets.githubusercontent.com:bad/file",
                   "https://release-assets.githubusercontent.com.attacker.invalid/file",
                   "https://release-assets.githubusercontent.com/github-production-release-asset/1/id#fragment"]
        for source in approved:
            for target in targets:
                with self.subTest(source=source, target=target), self.assertRaises(releases.ReleaseError):
                    self.redirect(source, target)


class PluginReleaseChecks(unittest.TestCase):
    def fixture(self, version="0.1.0-deck.10"):
        revision = "1" * 40
        base = REPOSITORY_URL + "/releases/download/v" + version + "/"
        receipt = {"version": version, "revision": revision, "dirty": False,
                   "platform": "linux/amd64", "archive": "obsgod-decky.zip", "sha256": "a" * 64}
        entry = {"tag_name": "v" + version, "prerelease": "-" in version, "draft": False,
                 "assets": [{"name": name, "browser_download_url": base + name}
                            for name in ("obsgod-decky.zip", "build-receipt.json", "SHA256SUMS")]}
        values = {releases.RELEASES_URL: json.dumps([entry]).encode(),
                  API_URL + "/commits/v" + version: json.dumps({"sha": revision}).encode(),
                  base + "build-receipt.json": json.dumps(receipt).encode(),
                  base + "SHA256SUMS": ("a" * 64 + "  obsgod-decky.zip\n").encode()}
        return entry, receipt, values, base

    def test_standard_plugin_release_compares_loaded_version_and_never_downloads(self):
        _, _, values, _ = self.fixture("0.1.0-deck.5")
        for installed, expected, available in [("0.1.0-deck.4", "update-available", True),
                                                ("0.1.0-deck.5", "up-to-date", False),
                                                ("0.1.0-deck.9", "up-to-date", False)]:
            seen = []
            def read(url, *args, **kwargs):
                seen.append(url)
                return values[url]
            with self.subTest(installed=installed), patch.object(releases, "_read_url", side_effect=read):
                result = releases.check_plugin_updates(installed)
            self.assertEqual(result["state"], expected)
            self.assertEqual(result["available"], available)
            self.assertEqual(result["current_version"], installed)
            self.assertFalse(result["automatic_update_supported"])
            self.assertNotIn("Desktop updater", result["message"])
            self.assertFalse(any(url.endswith(".zip") for url in seen))

    def test_paired_runtime_alone_is_not_a_published_standard_plugin_release(self):
        paired, values, _ = ReleaseChecks().fixture("0.1.0-deck.5")
        values[releases.RELEASES_URL] = json.dumps([paired]).encode()
        with patch.object(releases, "_read_url", side_effect=lambda url, *a, **k: values[url]) as read:
            result = releases.check_plugin_updates("0.1.0-deck.9")
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "unavailable")
        self.assertFalse(result["available"])
        self.assertIsNone(result["latest_version"])
        self.assertEqual(read.call_count, 1)

    def test_incomplete_foreign_dirty_or_inconsistent_plugin_metadata_fails_closed(self):
        entry, receipt, values, base = self.fixture()
        cases = []
        for field, value in [("revision", "2" * 40), ("version", "0.1.0-deck.11"),
                             ("dirty", True), ("platform", "linux/arm64"),
                             ("sha256", "b" * 64), ("archive", "another.zip")]:
            changed = dict(values)
            changed[base + "build-receipt.json"] = json.dumps(dict(receipt, **{field: value})).encode()
            cases.append(changed)
        cases.append(dict(values, **{base + "SHA256SUMS": b""}))
        for assets in [entry["assets"][:1], entry["assets"] + [entry["assets"][0]],
                       [dict(asset, browser_download_url="https://attacker.invalid/zip") for asset in entry["assets"]]]:
            cases.append(dict(values, **{releases.RELEASES_URL: json.dumps([dict(entry, assets=assets)]).encode()}))
        for altered in cases:
            with self.subTest(metadata=altered), patch.object(releases, "_read_url", side_effect=lambda url, *a, **k: altered[url]):
                result = releases.check_plugin_updates("0.1.0-deck.9")
            self.assertFalse(result["ok"])
            self.assertFalse(result["available"])
            self.assertEqual(result["state"], "unsupported")

    def test_offline_does_not_claim_plugin_is_current(self):
        with patch.object(releases, "_open_url", side_effect=urllib.error.URLError("private fixture")):
            result = releases.check_plugin_updates("0.1.0-deck.9")
        self.assertEqual(result["state"], "offline")
        self.assertFalse(result["ok"])
        self.assertFalse(result["available"])
        self.assertNotIn("private fixture", str(result))

    def test_exact_recovery_target_is_selected_only_from_published_trusted_channel(self):
        old, values, _ = ReleaseChecks().fixture("0.1.0-deck.5")
        new, new_values, _ = ReleaseChecks().fixture("0.1.0-deck.10")
        values.update(new_values)
        values[releases.RELEASES_URL] = json.dumps([new, old]).encode()
        with patch.object(releases, "_read_url", side_effect=lambda url, *a, **k: values[url]):
            result, candidate = releases.inspect_updates("0.1.0-deck.9", target_version="0.1.0-deck.5")
            absent, no_candidate = releases.inspect_updates("0.1.0-deck.9", target_version="0.1.0-deck.6")
        self.assertEqual(candidate["version"], "0.1.0-deck.5")
        self.assertFalse(result["available"])
        self.assertEqual(absent["state"], "unavailable")
        self.assertIsNone(no_candidate)


class PluginReplacementGuard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {"HOME": str(self.home), "DECKY_HOME": "",
                                                  "DECKY_PLUGIN_DIR": "", "DECKY_PLUGIN_SETTINGS_DIR": "",
                                                  "DECKY_PLUGIN_RUNTIME_DIR": "", "DECKY_PLUGIN_LOG_DIR": ""})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def plugin(self, version):
        root = self.home / "homebrew/plugins/obsgod"
        root.mkdir(parents=True, exist_ok=True)
        (root / "package.json").write_text(json.dumps({"name": "obsgod", "version": version}))
        (root / "plugin.json").write_text(json.dumps({"name": "OBSGod"}))
        return root

    def test_absent_equal_older_newer_and_unknown_installed_plugin(self):
        self.assertIsNone(releases.require_plugin_replacement("0.1.0-deck.5", self.home))
        for installed in ("0.1.0-deck.4", "0.1.0-deck.5"):
            self.plugin(installed)
            self.assertEqual(releases.require_plugin_replacement("0.1.0-deck.5", self.home), installed)
        self.plugin("0.1.0-deck.9")
        with self.assertRaisesRegex(releases.ReleaseError, "newer"):
            releases.require_plugin_replacement("0.1.0-deck.5", self.home)
        self.plugin("unknown")
        with self.assertRaisesRegex(releases.ReleaseError, "could not be verified"):
            releases.require_plugin_replacement("0.1.0-deck.5", self.home)

    def test_recovery_binds_exact_target_and_observed_current_version_on_every_read(self):
        self.plugin("0.1.0-deck.9")
        for target, expected in [("0.1.0-deck.4", "0.1.0-deck.9"), ("0.1.0-deck.5", None),
                                 ("0.1.0-deck.5", "0.1.0-deck.8")]:
            with self.subTest(target=target, expected=expected), self.assertRaises(releases.ReleaseError):
                releases.require_plugin_replacement("0.1.0-deck.5", self.home, target, expected)
        self.assertEqual(releases.require_plugin_replacement("0.1.0-deck.5", self.home,
                                                            "0.1.0-deck.5", "0.1.0-deck.9"), "0.1.0-deck.9")
        self.plugin("0.1.0-deck.10")
        with self.assertRaisesRegex(releases.ReleaseError, "no longer matches"):
            releases.require_plugin_replacement("0.1.0-deck.5", self.home, "0.1.0-deck.5", "0.1.0-deck.9")

    def test_symlinked_incomplete_and_foreign_plugin_identities_fail_closed(self):
        root = self.plugin("0.1.0-deck.9")
        (root / "plugin.json").write_text('{"name":"Another plugin"}')
        with self.assertRaises(releases.ReleaseError):
            releases.installed_plugin_version(self.home)
        (root / "plugin.json").unlink()
        (root / "plugin.json").symlink_to(root / "package.json")
        with self.assertRaises(releases.ReleaseError):
            releases.installed_plugin_version(self.home)
        (root / "plugin.json").unlink()
        with self.assertRaises(releases.ReleaseError):
            releases.installed_plugin_version(self.home)
