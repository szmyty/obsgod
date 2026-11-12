#!/usr/bin/env python3
"""Exercise the actual extracted installer and local setup in Chromium."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

from playwright.sync_api import expect, sync_playwright
from test_bootstrap import desktop_command, previous_app_install_command, read_until


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--upgrade-from", type=Path, help="Install an earlier real archive and preserve its configured user data")
    parser.add_argument("--browser", default="/usr/bin/chromium")
    parser.add_argument("--screenshots", type=Path, default=Path("/tmp/obsgod-browser"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="obsgod-browser-") as directory:
        base = Path(directory)
        with tarfile.open(args.archive) as archive:
            archive.extractall(base, filter="data")
        package = next(base.glob("OBSGod-*"))
        home = base / "home with spaces"
        home.mkdir()
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"), XDG_STATE_HOME=str(home / ".local/state"), XDG_CACHE_HOME=str(home / ".cache"))
        current = home / ".local/share/obsgod/current"
        snapshots = {}
        if args.upgrade_from:
            older = base / "older"
            older.mkdir()
            with tarfile.open(args.upgrade_from) as archive:
                archive.extractall(older, filter="data")
            old_package = next(older.glob("OBSGod-*"))
            subprocess.run(previous_app_install_command(old_package), env=env, check=True)
            fixture = {"server":"rtmps://example.invalid/app","stream_key":"browser-fixture-never-real"}
            subprocess.run([str(current / "obsgod"), "deck", "configure"], input=json.dumps(fixture), env=env, capture_output=True, text=True, check=True)
            for path in [home / "Videos/OBSGod/keep.mkv", home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini"]:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b"preserved fixture data")
            snapshots = {path:path.read_bytes() for path in [home / ".config/obsgod/deck.json",home / ".config/obsgod/secrets.json",home / "Videos/OBSGod/keep.mkv",home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini"]}
        ready = base / "browser-url"
        probe = base / "browser-probe"
        probe.write_text("#!" + sys.executable + "\n" + """
import os,sys,urllib.request
from pathlib import Path
with urllib.request.urlopen(sys.argv[1].split('#')[0],timeout=3) as response:
 assert response.status==200
Path(os.environ['OBSGOD_TEST_BROWSER_URL']).write_text(sys.argv[1])
""")
        probe.chmod(0o700)
        env.update(BROWSER=str(probe), OBSGOD_TEST_BROWSER_URL=str(ready))
        # This suite qualifies the actual Desktop entry and browser/setup path.
        # The unmodified pinned Decky frontend/installer is exercised separately
        # by decky-transport-smoke.py against the same runtime archive.
        process = subprocess.Popen(desktop_command(package / "Install OBSGod.desktop", as_uri=True) + ["--app-only"], cwd=home,
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while not ready.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("Desktop installer exited before opening setup")
                time.sleep(0.05)
            assert ready.exists(), "The actual installer did not open a working setup server"
            assert all(path.read_bytes()==data for path,data in snapshots.items()), "Upgrade altered settings, secrets, recordings or managed OBS preferences"
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(ready.read_text())
                page.get_by_role("heading", name="Connect your stream").wait_for()
                expect(page.locator("#product-name")).to_contain_text("Decky Stream")
                assert "#" not in page.url, "Private setup token remained visible in URL"
                # Guides are explicit hints; selecting another provider cannot
                # silently change either a server or a key already being typed.
                page.locator("#server").fill("rtmps://example.invalid/app")
                page.locator("#key").fill("browser-fixture-never-real")
                for provider,docs in [
                    ("kick","https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com"),
                    ("youtube","https://support.google.com/youtube/answer/10364924?hl=en"),
                    ("custom","https://obsproject.com/kb/quick-start-guide"),
                ]:
                    page.locator("#provider").select_option(provider)
                    expect(page.locator("#provider-docs")).to_have_attribute("href",docs)
                    expect(page.locator("#server")).to_have_value("rtmps://example.invalid/app")
                    expect(page.locator("#key")).to_have_value("browser-fixture-never-real")
                    assert page.locator("#provider-preset").is_disabled()
                page.locator("#provider").select_option("twitch")
                assert page.locator("#provider-preset").is_enabled()
                page.once("dialog",lambda dialog:dialog.accept())
                page.locator("#provider-preset").click()
                expect(page.locator("#server")).to_have_value("rtmps://ingest.global-contribute.live-video.net/app")
                expect(page.locator("#key")).to_have_value("browser-fixture-never-real")
                page.locator("#provider").select_option("custom")
                page.locator("#server").fill("rtmps://example.invalid/app")
                assert not page.locator("#microphone").is_checked()
                expect(page.locator("#capture_mode")).to_have_value("screen")
                assert page.locator("#idle_style").is_disabled()
                assert page.locator("#idle_text").is_disabled()
                page.locator("#capture_mode").select_option("game")
                page.locator("#idle_style").select_option("placeholder")
                page.locator("#idle_text").fill("Back soon — <not HTML>")
                page.locator("#server").fill("rtmps://example.invalid/app")
                page.locator("#key").fill("browser-fixture-never-real")
                page.get_by_role("button", name="Save on this Deck").click()
                page.get_by_text("Settings saved on this device", exact=True).wait_for()
                assert page.locator("#key").input_value() == ""
                page.screenshot(path=str(args.screenshots / "desktop-setup.png"), full_page=True)
                page.reload()
                expect(page.locator("#server")).to_have_value("rtmps://example.invalid/app")
                assert page.locator("#key").input_value() == ""
                expect(page.locator("#capture_mode")).to_have_value("game")
                expect(page.locator("#idle_style")).to_have_value("placeholder")
                expect(page.locator("#idle_text")).to_have_value("Back soon — <not HTML>")
                page.get_by_text("Manual repair ZIP", exact=True).click()
                assert page.locator("#zip-path").inner_text().endswith("obsgod-decky.zip")
                result = subprocess.run([str(current / "obsgod"), "deck", "status"], env=env, capture_output=True, text=True, check=True)
                configured=json.loads(result.stdout)
                assert configured["configured"]
                assert configured["settings"]["capture_mode"] == "game"
                assert configured["settings"]["idle_style"] == "placeholder"
                assert configured["settings"]["idle_text"] == "Back soon — <not HTML>"
                assert "browser-fixture-never-real" not in result.stdout + result.stderr
                secret = home / ".config/obsgod/secrets.json"
                assert secret.stat().st_mode & 0o777 == 0o600
                assert json.loads(secret.read_text())["stream_key"] == "browser-fixture-never-real"
                # A changed destination requires its own explicit key; choosing
                # a guide alone still does not change the saved destination.
                page.locator("#server").fill("rtmps://different.invalid/app")
                assert page.locator("#key").evaluate("field=>field.required")
                page.get_by_text("Server changed: enter the key for this destination.",exact=False).wait_for()
                page.locator("#server").fill("rtmps://example.invalid/app")
                assert not page.locator("#key").evaluate("field=>field.required")
                # Exercise the actual private Go rotation through Desktop UI.
                # No OBS listener/process exists in this fixture, so this is
                # credential/configuration proof, not an authentication receipt.
                previous_secret=json.loads(secret.read_text())
                page.get_by_text("Change or recover the local control password",exact=True).click()
                assert page.locator("#reset-control-password").is_disabled()
                page.locator("#confirm-control-password").check()
                expect(page.locator("#reset-control-password")).to_be_enabled()
                page.locator("#reset-control-password").click()
                page.locator("#control-password-status").filter(has_text="Local control password saved privately for managed OBS.").wait_for()
                updated_secret=json.loads(secret.read_text())
                assert updated_secret["obs_password"] != previous_secret["obs_password"]
                assert updated_secret["stream_key"] == previous_secret["stream_key"]
                assert updated_secret["settings_hash"] == previous_secret["settings_hash"]
                assert page.locator("#control-password").input_value()==""
                assert not page.locator("#confirm-control-password").is_checked()
                assert page.locator("#reset-control-password").is_disabled()
                assert updated_secret["obs_password"] not in page.locator("body").inner_text()
                assert secret.stat().st_mode & 0o777 == 0o600
                # Explicitly saving new capture/fallback settings changes the
                # app settings/hash pair; repeat install must preserve that new
                # pair as well as the original OBS preferences and media.
                for path in list(snapshots):
                    if path in {home / ".config/obsgod/deck.json", secret}:
                        snapshots[path] = path.read_bytes()
                page.set_viewport_size({"width": 800, "height": 1280})
                page.screenshot(path=str(args.screenshots / "desktop-setup-portrait.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                assert not errors, errors
                page.get_by_role("button", name="Finish and close setup").click()
                page.get_by_text("Setup closed. You can close this tab.", exact=True).wait_for()
                browser.close()
            output=read_until(process,b"Press Enter to close",timeout=10)
            assert b"browser-fixture-never-real" not in output
            assert process.poll() is None, "Desktop terminal did not stay open after setup"
            process.communicate(b"\n",timeout=10)
            assert process.returncode==0
            subprocess.run([sys.executable, str(package / "install.py"), "--no-launch", "--app-only"], env=env, check=True)
            assert all(path.read_bytes()==data for path,data in snapshots.items()), "Repeat install altered user data"
            # App-only setup deliberately has no running Decky frontend. Review
            # inventory without effects, then prove actual removal refuses to
            # orphan its plugin. Successful removal is exercised through the
            # real pinned Decky uninstall route in decky-transport-smoke.py.
            uninstall=[sys.executable,str(current / "uninstall.py"),"--purge-settings"]
            inventory=subprocess.run(uninstall+["--dry-run","--json"],env=env,capture_output=True,text=True,check=True)
            plan=json.loads(inventory.stdout)
            assert plan["ok"] and plan["dry_run"] and plan["remove_plugin"]
            assert str(secret.parent) in [entry["path"] for entry in plan["entries"]]
            before_secret=secret.read_bytes()
            # Reserve the fixed port without listening. This both models an
            # unavailable service and prevents this negative test contacting a
            # real Decky installation on the host. An occupied port aborts the
            # fixture before any removal command rather than touching its user.
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as unavailable:
                unavailable.bind(("127.0.0.1",1337))
                removal=subprocess.run(uninstall+["--yes","--json"],env=env,capture_output=True,text=True,timeout=35)
            assert removal.returncode!=0, "App-only fixture unexpectedly removed files without a verified Decky frontend"
            failed=json.loads(removal.stdout)
            assert not failed["ok"] and "Decky" in failed["message"]
            assert current.is_dir() and (home / ".local/bin/obsgod").exists()
            assert secret.read_bytes()==before_secret
            assert "browser-fixture-never-real" not in inventory.stdout+inventory.stderr+removal.stdout+removal.stderr
            print("PASS: actual desktop launcher in explicit app-only test mode, foreground startup, browser provider guides with explicit server/key binding, private control-password rotation with no broadcast, setup/reload with preserved game-only/fallback settings, private credentials, terminal hold, repeat install, removal inventory and fail-closed preservation without Decky; actual Decky installation/removal qualified separately; fixture credentials only" + ("; actual earlier-preview upgrade preserves all user data" if snapshots else ""))
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                process.communicate(timeout=10)


if __name__ == "__main__":
    main()
