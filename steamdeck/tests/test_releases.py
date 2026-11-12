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


class ReleaseChecks(unittest.TestCase):
    def fixture(self, version="0.1.0-deck.10", raw=False):
        revision = "1" * 40
        archive = "obsgod-deck_" + version + "_linux_amd64.tar.gz"
        manifest = {"version": version, "revision": revision, "platform": "linux/amd64", "dirty": False, "updater_version": version, "files": {name: "a" * 64 for name in ["obsgod", "obsgod-decky.zip", "setup.py", "bridge.py"]}}
        data = json.dumps(manifest).encode()
        base = "https://raw.githubusercontent.com/szmyty/obsgod/" + "2" * 40 + "/" if raw else "https://github.com/szmyty/obsgod/releases/download/v" + version + "/"
        values = {
            "https://api.github.com/repos/szmyty/obsgod/commits/v" + version: json.dumps({"sha": revision}).encode(),
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
        for bad in [release["body"].replace("2" * 40, "master"), release["body"].replace("szmyty/obsgod", "attacker/obsgod")]:
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
        tag_url = "https://api.github.com/repos/szmyty/obsgod/commits/" + release["tag_name"]
        values[tag_url] = json.dumps({"sha": "9" * 40}).encode()
        result = self.run_check([release], values)
        self.assertFalse(result["ok"])
        self.assertIn("revision", result["message"])

    def test_offline_and_rate_limit_are_not_up_to_date(self):
        for failure, state in [(urllib.error.URLError("fixture-private-details"), "offline"), (urllib.error.HTTPError(releases.RELEASES_URL, 429, "fixture-private-details", {}, None), "error")]:
            with patch.object(releases.urllib.request, "urlopen", side_effect=failure):
                result = releases.check_updates("0.1.0-deck.9")
            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], state)
            self.assertNotIn("fixture-private-details", json.dumps(result))

    def test_download_checksum_and_source_url_fail_before_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive"
            candidate = {"archive_url": "https://github.com/szmyty/obsgod/releases/download/v1.0.0/obsgod-deck_1.0.0_linux_amd64.tar.gz", "archive_sha256": hashlib.sha256(b"expected").hexdigest()}
            with patch.object(releases.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupted")):
                with self.assertRaisesRegex(releases.ReleaseError, "checksum"):
                    releases.download_archive(candidate, path)
            with patch.object(releases.urllib.request, "urlopen") as opened:
                with self.assertRaisesRegex(releases.ReleaseError, "unsupported"):
                    releases.download_archive(dict(candidate, archive_url="https://example.invalid/installer"), Path(temporary) / "second")
                opened.assert_not_called()

    def test_url_policy_and_version_validation(self):
        for url in ["http://github.com/szmyty/obsgod/releases/download/v1.0.0/archive", "https://raw.githubusercontent.com/szmyty/obsgod/master/archive", "https://github.com:invalid/szmyty/obsgod/releases/download/v1.0.0/archive", "https://github.com/szmyty/obsgod/releases/download/v1.0.0/archive?secret=fixture", "https://github.com@evil.invalid/szmyty/obsgod/releases/download/v1.0.0/archive"]:
            self.assertFalse(releases._safe_url(url))
        for value in ["unknown", "01.0.0", "1.0.0-preview.01", "1.0.0/../../escape", None]:
            with self.assertRaises(releases.ReleaseError):
                releases.version_key(value)
        self.assertGreater(releases.version_key("1.0.0"), releases.version_key("1.0.0-rc.99"))

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
