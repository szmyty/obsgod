#!/usr/bin/env python3
"""Exercise the actual extracted installer and local setup in Chromium."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
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
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_STATE_HOME=str(home / ".local/state"))
        subprocess.run(["python3", str(package / "install.py"), "--no-launch"], env=env, check=True)
        current = home / ".local/share/obsgod/current"
        for key in ["HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME"]:
            os.environ[key] = env[key]
        sys.path.insert(0, str(current))
        spec = importlib.util.spec_from_file_location("installed_obsgod_setup", current / "setup.py")
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        server = setup.SetupServer()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(server.origin + "/#" + server.token)
                page.get_by_role("heading", name="Connect your stream").wait_for()
                assert not page.locator("#microphone").is_checked()
                page.locator("#server").fill("rtmps://example.invalid/app")
                page.locator("#key").fill("browser-fixture-never-real")
                page.get_by_role("button", name="Save on this Deck").click()
                page.get_by_text("Settings saved on this device", exact=True).wait_for()
                assert page.locator("#key").input_value() == ""
                page.screenshot(path=str(args.screenshots / "desktop-setup.png"), full_page=True)
                page.reload()
                page.wait_for_function("document.querySelector('#server').value === 'rtmps://example.invalid/app'")
                assert page.locator("#key").input_value() == ""
                assert page.locator("#zip-path").inner_text().endswith("obsgod-decky.zip")
                result = subprocess.run([str(current / "obsgod"), "deck", "status"], env=env, capture_output=True, text=True, check=True)
                assert json.loads(result.stdout)["configured"]
                assert "browser-fixture-never-real" not in result.stdout + result.stderr
                secret = home / ".config/obsgod/secrets.json"
                assert secret.stat().st_mode & 0o777 == 0o600
                assert json.loads(secret.read_text())["stream_key"] == "browser-fixture-never-real"
                page.set_viewport_size({"width": 800, "height": 1280})
                page.screenshot(path=str(args.screenshots / "desktop-setup-portrait.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                assert not errors, errors
                page.get_by_role("button", name="Finish and close setup").click()
                page.get_by_text("Setup closed. You can close this tab.", exact=True).wait_for()
                browser.close()
            subprocess.run(["python3", str(current / "uninstall.py"), "--purge-settings"], env=env, check=True)
            assert not (home / ".local/bin/obsgod").exists()
            assert not secret.exists()
            print("PASS: archive install, credential setup, refresh, responsive page, clean uninstall; no real credentials used")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
