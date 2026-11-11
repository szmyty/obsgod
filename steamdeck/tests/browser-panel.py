#!/usr/bin/env python3
"""Render the actual release ZIP frontend in a simulated Decky/Steam UI host."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import zipfile
from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_zip", type=Path)
    parser.add_argument("--browser", default="/usr/bin/chromium")
    parser.add_argument("--screenshots", type=Path, default=Path("/tmp/obsgod-panel"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    decky = Path(__file__).resolve().parents[1] / "decky"
    with tempfile.TemporaryDirectory(prefix="obsgod-panel-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(args.plugin_zip) as archive:
            archive.extractall(root)
        subprocess.run(["node", "tests/build-fixture.mjs", str(root / "runtime.js")], cwd=decky, check=True)
        shutil.copyfile(decky / "tests/fixture.html", root / "index.html")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 800, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto("http://127.0.0.1:" + str(server.server_port))
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                page.screenshot(path=str(args.screenshots / "panel-stopped.png"))
                page.get_by_role("button", name="Start streaming", exact=True).click()
                page.get_by_role("status").filter(has_text="OBS streaming").wait_for()
                page.get_by_role("img", name="OBS streaming").wait_for()
                page.screenshot(path=str(args.screenshots / "panel-live.png"))
                page.evaluate("fixture.stalled=true")
                page.get_by_role("status").filter(has_text="Connecting / stalled").wait_for(timeout=15000)
                page.evaluate("fixture.failure=true")
                page.get_by_role("button", name="Refresh status").click()
                page.get_by_role("status").filter(has_text="Check OBS").wait_for()
                page.screenshot(path=str(args.screenshots / "panel-unconfirmed.png"))
                page.get_by_role("button", name="Stop streaming / cancel").click()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                page.get_by_role("button", name="Make 10-second test clip").click()
                page.get_by_text("Local fixture clip saved", exact=False).wait_for()
                page.evaluate("plugin.onDismount()")
                assert not errors, errors
                browser.close()
            print("PASS: release ZIP frontend renders; green/red/amber, stale-byte detection, failed polls, stop and test actions work in simulated loader. Real controller/Decky runtime untested.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
