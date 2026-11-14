#!/usr/bin/env python3
"""Exercise the actual packaged setup UI in a simulated Decky host, not a Deck."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_zip", type=Path)
    parser.add_argument("--browser", default="/usr/bin/chromium")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    decky = Path(__file__).resolve().parents[1] / "decky"
    with tempfile.TemporaryDirectory(prefix="obsgod-setup-panel-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(args.plugin_zip) as archive:
            archive.extractall(root)
        subprocess.run(["node", "tests/build-fixture.mjs", str(root / "runtime.js")], cwd=decky, check=True)
        shutil.copyfile(decky / "tests/fixture.html", root / "index.html")
        from http.server import SimpleHTTPRequestHandler

        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        cases = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 800, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto("http://127.0.0.1:" + str(server.server_port))
                start = page.get_by_role("button", name="Start streaming", exact=True)
                test = page.get_by_role("button", name="Make 10-second test clip", exact=True)
                check = page.get_by_role("button", name="Check setup status", exact=True)
                expect(start).to_be_enabled()
                page.evaluate("fixture.dependencyReady=false;fixture.dependencyState='setup_required';fixture.dependencyCanInstall=true;fixture.flathubNeeded=true")
                check.click()
                expect(start).to_be_disabled()
                expect(test).to_be_disabled()
                expect(page.get_by_role("button", name="Install dependencies…", exact=True)).to_be_enabled()
                page.screenshot(path=str(args.output / "setup-required.png"))
                cases.append("missing dependencies block new output without removing plugin")

                page.get_by_role("button", name="Install dependencies…", exact=True).click()
                dialog = page.get_by_role("dialog", name="Install streaming dependencies?")
                expect(dialog).to_be_visible()
                expect(dialog.locator("li")).to_have_count(3)
                dialog.get_by_role("button", name="Later", exact=True).click()
                expect(page.get_by_text("Setup postponed.", exact=False)).to_be_visible()
                assert page.evaluate("fixture.dependencyInstalls") == 0
                cases.append("Later records preference only; no installer call")

                page.get_by_role("button", name="Install dependencies…", exact=True).click()
                dialog.get_by_role("button", name="Install", exact=True).click()
                expect(page.get_by_text("Job: fixture-setup-job", exact=False)).to_be_visible()
                expect(start).to_be_disabled()
                assert page.evaluate("fixture.dependencyInstalls") == 1
                page.screenshot(path=str(args.output / "setup-running.png"))
                page.reload()
                expect(page.get_by_text("Job: fixture-setup-job", exact=False)).to_be_visible()
                expect(page.get_by_role("button", name="Cancel dependency setup", exact=True)).to_be_enabled()
                assert page.evaluate("fixture.dependencyInstalls") == 1
                assert not page.evaluate("fixture.calls.install_dependencies||0")
                cases.append("frontend reload recovers backend job without another Install")

                page.get_by_role("button", name="Cancel dependency setup", exact=True).click()
                expect(page.get_by_role("button", name="Review and retry setup", exact=True)).to_be_enabled()
                assert not page.evaluate("fixture.calls.stop||0")
                page.evaluate("fixture.obsInstalled=true;fixture.gstreamerInstalled=false;fixture.flathubNeeded=false")
                check.click()
                page.get_by_role("button", name="Review and retry setup", exact=True).click()
                expect(dialog.locator("li")).to_have_count(1)
                expect(dialog.locator("li")).to_contain_text("GStreamer")
                dialog.get_by_role("button", name="Later", exact=True).click()
                cases.append("cancel preserves partial install; retry consent lists only missing extension")

                page.evaluate("fixture.dependencyState='ready';fixture.dependencyReady=true;fixture.dependencyCanInstall=false;fixture.obsInstalled=true;fixture.gstreamerInstalled=true;fixture.dependencyOperation=null")
                check.click()
                expect(start).to_be_enabled()
                expect(test).to_be_enabled()
                assert not page.evaluate("fixture.active")
                cases.append("observed dependency readiness enables controls without broadcasting")

                page.evaluate("fixture.active=true;fixture.bytes=4096;fixture.dependencyFailure=true")
                page.get_by_role("button", name="Refresh status", exact=True).click()
                check.click()
                expect(start).to_be_disabled()
                stop = page.get_by_role("button", name=re.compile(r"^Stop streaming"))
                expect(stop).to_be_enabled()
                stop.click()
                page.wait_for_function("!fixture.active")
                expect(page.get_by_text("Setup status unavailable", exact=True)).to_be_visible()
                assert "must-not-copy" not in page.locator("body").inner_text()
                page.screenshot(path=str(args.output / "setup-observation-failed.png"))
                cases.append("failed dependency observation keeps explicit recovery Stop and excludes secrets")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
        (args.output / "result.json").write_text(json.dumps({"passed": cases, "limitations": "Simulated Decky/browser APIs; not Flatpak, actual controller, SteamOS or provider proof."}, indent=2) + "\n")
        print("Passed", len(cases), "packaged dependency-setup browser cases")


if __name__ == "__main__":
    main()
