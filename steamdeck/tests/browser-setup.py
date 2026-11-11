#!/usr/bin/env python3
"""Exercise the actual extracted installer and local setup in Chromium."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

from playwright.sync_api import sync_playwright
from test_bootstrap import desktop_command, read_until


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
        current = home / ".local/share/obsgod/current"
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
        process = subprocess.Popen(desktop_command(package / "Install OBSGod.desktop", as_uri=True), cwd=home,
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while not ready.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("Desktop installer exited before opening setup")
                time.sleep(0.05)
            assert ready.exists(), "The actual installer did not open a working setup server"
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(ready.read_text())
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
            output=read_until(process,b"Press Enter to close",timeout=10)
            assert b"browser-fixture-never-real" not in output
            assert process.poll() is None, "Desktop terminal did not stay open after setup"
            process.communicate(b"\n",timeout=10)
            assert process.returncode==0
            subprocess.run(["python3", str(current / "uninstall.py"), "--purge-settings"], env=env, check=True)
            assert not (home / ".local/bin/obsgod").exists()
            assert not secret.exists()
            print("PASS: actual desktop launcher, foreground startup, browser setup/reload, private credentials, terminal hold, clean uninstall; fixture credentials only")
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                process.communicate(timeout=10)


if __name__ == "__main__":
    main()
