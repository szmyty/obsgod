#!/usr/bin/env python3
"""Render the actual release ZIP frontend in a simulated Decky/Steam UI host."""
import argparse
import json
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
        # Decky's real PluginWrapper selects ESMODULE_V1 only when the shipped
        # package.json declares type=module. Direct browser imports alone cannot
        # detect an archive that the real loader would incorrectly eval as IIFE.
        package=json.loads((root / "obsgod/package.json").read_text())
        assert package.get("type")=="module", "Decky would select its legacy eval loader"
        metadata=json.loads((root / "obsgod/plugin.json").read_text())
        assert metadata["name"]=="OBSGod" and metadata["api_version"]==1
        assert "root" not in metadata["flags"] and "_root" not in metadata["flags"]
        subprocess.run(["node", "tests/build-fixture.mjs", str(root / "runtime.js")], cwd=decky, check=True)
        shutil.copyfile(decky / "tests/fixture.html", root / "index.html")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 800, "height": 900})
                page.context.grant_permissions(["clipboard-read","clipboard-write"])
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto("http://127.0.0.1:" + str(server.server_port))
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                page.get_by_text("Decky Stream",exact=False).wait_for()
                assert page.evaluate("plugin.name") == "OBSGod", "display-name change must preserve loader identity"
                page.get_by_text("Status updates automatically",exact=True).wait_for()
                page.get_by_text("System audio: Not confirmed",exact=True).wait_for()
                page.get_by_text("Microphone: Off",exact=True).wait_for()
                page.evaluate("fixture.microphone=true;fixture.audio={state:'muted',message:'Fixture output muted',output_available:true,output_muted:true,microphone_available:true,microphone_muted:true,signal:'silent'}")
                page.get_by_role("button",name="Refresh status").click()
                page.get_by_text("System audio: Muted",exact=True).wait_for()
                page.get_by_text("Signal: No signal in last check",exact=True).wait_for()
                page.get_by_text("Microphone: Muted",exact=True).wait_for()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                page.evaluate("fixture.microphone=false;fixture.audio=null")
                page.get_by_role("button",name="Refresh status").click()
                page.get_by_text("Microphone: Off",exact=True).wait_for()
                page.evaluate("fixture.configured=false")
                page.get_by_role("button",name="Refresh status").click()
                page.get_by_role("status").filter(has_text="Setup required").wait_for()
                page.get_by_text("Finish Desktop Setup, then make a local test clip before your first stream.",exact=True).wait_for()
                assert page.get_by_role("button",name="Start streaming",exact=True).is_disabled()
                assert page.get_by_role("button",name="Make 10-second test clip",exact=True).is_disabled()
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(args.screenshots / "panel-setup.png"))
                page.evaluate("fixture.configured=true")
                page.get_by_role("button",name="Refresh status").click()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                assert page.get_by_text("system audio may include other apps",exact=False).count() == 0
                page.get_by_role("button",name="Capture help",exact=True).click()
                page.get_by_text("system audio may include other apps",exact=False).wait_for()
                page.get_by_role("button",name="Hide capture help",exact=True).click()
                assert page.get_by_text("system audio may include other apps",exact=False).count() == 0
                page.get_by_role("button",name="Setup and recording help",exact=True).click()
                page.get_by_text("Test clips save to Videos/OBSGod",exact=False).wait_for()
                page.get_by_role("button",name="Hide setup help",exact=True).click()
                console=page.get_by_role("log",name="OBSGod diagnostic console")
                console.get_by_text("No diagnostic events yet.",exact=False).wait_for()
                assert page.get_by_role("button",name="Copy console log").is_disabled()
                assert page.get_by_role("button",name="Refresh status").bounding_box()["y"] < console.bounding_box()["y"]
                assert page.get_by_role("button",name="Stop streaming",exact=True).is_disabled()
                mode_button=page.get_by_role("button",name="Switch to game only",exact=True)
                assert mode_button.is_enabled()
                mode_button.evaluate("button=>{button.click();button.click();button.click();}")
                page.get_by_text("Capture mode: Game only",exact=True).wait_for()
                assert page.evaluate("fixture.calls.set_capture_mode") == 1
                assert page.evaluate("fixture.modeArgs") == ["game"]
                assert not page.evaluate("fixture.active")
                assert page.evaluate("fixture.toasts.length") == 0
                page.get_by_role("button",name="Switch to entire screen",exact=True).click()
                page.get_by_text("Capture mode: Entire screen",exact=True).wait_for()
                # A recording or unconfirmed output must disable mode changes.
                page.evaluate("fixture.recording=true")
                page.get_by_role("button",name="Refresh status").click()
                assert page.get_by_role("button",name="Switch to game only",exact=True).is_disabled()
                page.evaluate("fixture.recording=false;fixture.unknown=true")
                page.get_by_role("button",name="Refresh status").click()
                assert page.get_by_role("button",name="Switch to game only",exact=True).is_disabled()
                page.evaluate("fixture.unknown=false")
                page.get_by_role("button",name="Refresh status").click()
                page.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Switch to game only'&&!button.disabled)")
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(args.screenshots / "panel-stopped.png"))
                # Rapid clicks must produce one request even before React paints
                # the disabled state. The success toast comes from a status poll.
                page.get_by_role("button",name="Start streaming",exact=True).evaluate("button=>{button.click();button.click();button.click();}")
                page.get_by_role("status").filter(has_text="OBS streaming").wait_for()
                page.get_by_role("img", name="OBS streaming").wait_for()
                console.get_by_text("Streaming fixture started",exact=False).wait_for()
                assert page.evaluate("fixture.calls.start") == 1
                assert page.get_by_role("button",name="Start streaming",exact=True).is_disabled()
                assert page.get_by_role("button",name="Switch to game only",exact=True).is_disabled()
                assert page.evaluate("fixture.toasts.filter(t=>t.body.includes('OBS is streaming.')).length") == 1
                page.get_by_role("button",name="Copy console log").click()
                page.get_by_text("Copied 1 diagnostic event.",exact=False).wait_for()
                assert "Streaming fixture started" in page.evaluate("navigator.clipboard.readText()")
                page.get_by_role("status").filter(has_text="OBS streaming").wait_for()
                page.get_by_role("button",name="Clear console").click()
                console.get_by_text("No diagnostic events yet.",exact=False).wait_for()
                page.get_by_role("status").filter(has_text="OBS streaming").wait_for()
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(args.screenshots / "panel-live.png"))
                page.evaluate("fixture.stalled=true")
                page.get_by_role("status").filter(has_text="Connecting / stalled").wait_for(timeout=15000)
                page.evaluate("fixture.failure=true")
                page.get_by_role("button", name="Refresh status").click()
                page.get_by_role("status").filter(has_text="Check OBS").wait_for()
                page.get_by_text("Capture mode: Not confirmed",exact=True).wait_for()
                assert page.get_by_role("button",name="Switch to game only",exact=True).is_disabled()
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(args.screenshots / "panel-unconfirmed.png"))
                page.get_by_role("button", name="Stop streaming / recover").click()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                assert page.get_by_role("button",name="Stop streaming",exact=True).is_disabled()
                assert page.evaluate("fixture.calls.stop") == 1
                assert page.evaluate("fixture.toasts.filter(t=>t.body.includes('streaming has stopped')).length") == 1
                page.get_by_role("button", name="Make 10-second test clip").click()
                console.get_by_text("Waiting for fixture OBS",exact=False).wait_for()
                assert page.get_by_role("button",name="Make 10-second test clip").is_disabled()
                assert page.get_by_role("button",name="Switch to game only",exact=True).is_disabled()
                assert page.get_by_role("button",name="Cancel operation").is_enabled()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                page.evaluate("fixture.finishTest()")
                console.get_by_text("Local fixture clip saved", exact=False).wait_for()
                page.evaluate("fixture.testFailure=true")
                page.get_by_role("button", name="Make 10-second test clip").click()
                page.wait_for_function("typeof fixture.finishTest === 'function'")
                page.evaluate("fixture.finishTest()")
                console.get_by_text("OBS startup timed out",exact=False).wait_for()
                page.evaluate("for(let i=0;i<15;i++)fixture.events.push({time:new Date().toISOString(),level:'info',message:'History event '+i})")
                page.get_by_role("button",name="Refresh status").click()
                console.get_by_text("History event 14",exact=False).wait_for()
                page.get_by_role("button",name="Older events").click()
                console.get_by_text("History event 6",exact=False).wait_for()
                page.get_by_role("button",name="Copy console log").click()
                page.get_by_text("Copied 20 diagnostic events.",exact=False).wait_for()
                copied=page.evaluate("navigator.clipboard.readText()")
                assert "OBSGod plugin 0.1.0-console-fixture" in copied
                assert "20 diagnostic events (newest first)" in copied
                assert "History event 14" in copied and "History event 0" in copied
                assert copied.index("History event 14") < copied.index("History event 0")
                assert "OBS startup timed out before its authenticated control connection became ready." in copied
                assert "must-not-copy" not in copied and "rtmps://" not in copied
                # Exercise the legacy clipboard path using the real browser
                # clipboard, then prove failures never claim a successful copy.
                page.evaluate("navigator.clipboard.writeText('fixture clipboard sentinel')")
                page.evaluate("""fixture.readClipboard=navigator.clipboard.readText.bind(navigator.clipboard);
                  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('fixture denied')}}});""")
                page.get_by_role("button",name="Copy console log").click()
                page.get_by_text("Copied 20 diagnostic events.",exact=False).wait_for()
                assert page.evaluate("fixture.readClipboard()") == copied
                assert page.get_by_role("button",name="Copy console log").evaluate("button=>document.activeElement===button")
                page.evaluate("document.execCommand=()=>false")
                page.get_by_role("button",name="Copy console log").click()
                page.get_by_text("Could not access the clipboard.",exact=False).wait_for()
                page.get_by_role("button",name="Latest events").click()
                console.get_by_text("History event 14",exact=False).wait_for()
                page.reload()
                page.get_by_role("log").get_by_text("History event 14",exact=False).wait_for()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(args.screenshots / "panel-console.png"),full_page=True)
                page.get_by_role("button",name="Check for updates",exact=True).click()
                page.get_by_text("A preview update is available.",exact=False).wait_for()
                assert page.evaluate("fixture.calls.check_for_updates") == 1
                assert not page.evaluate("fixture.active")
                assert page.get_by_role("button",name="Check for updates",exact=True).bounding_box()["y"] > console.bounding_box()["y"]
                support=page.get_by_role("heading",name="SUPPORT DEVELOPMENT",exact=True)
                assert support.bounding_box()["y"] > page.get_by_role("button",name="Check for updates",exact=True).bounding_box()["y"]
                destinations=[
                    ("GitHub Sponsors","https://github.com/sponsors/szmyty"),
                    ("Buy Me a Coffee","https://www.buymeacoffee.com/szmyty"),
                    ("Ko-fi","https://ko-fi.com/szmyty"),
                    ("Open Collective","https://opencollective.com/szmyty"),
                    ("thanks.dev","https://thanks.dev/u/gh/szmyty"),
                ]
                for label,url in destinations:
                    page.get_by_role("button",name=label,exact=True).click()
                    page.wait_for_function("url=>fixture.externalLinks.at(-1)===url",arg=url)
                assert page.evaluate("fixture.externalLinks") == [url for _,url in destinations]
                assert page.get_by_role("button",name="Patreon",exact=True).count()==0
                for coin in ["Bitcoin","Ethereum","Solana"]:
                    assert page.get_by_role("button",name="Support with "+coin,exact=True).count()==0
                # Support navigation and errors must not control OBS output or
                # steal the selected control when automatic status polls repaint.
                calls=page.evaluate("({...fixture.calls})")
                selected=page.get_by_role("button",name="GitHub Sponsors",exact=True)
                selected.focus()
                page.wait_for_timeout(1800)
                assert selected.evaluate("button=>document.activeElement===button")
                page.evaluate("fixture.linkFailure=true")
                selected.click()
                page.get_by_text("Could not open GitHub Sponsors.",exact=False).wait_for()
                page.get_by_role("status").filter(has_text="Stopped").wait_for()
                assert not page.evaluate("fixture.active")
                for method in ["start","stop","test_recording"]:
                    assert page.evaluate("fixture.calls").get(method,0)==calls.get(method,0)
                assert "must-not-copy" not in page.locator("body").inner_text()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(args.screenshots / "panel-support.png"),full_page=True)
                page.evaluate("plugin.onDismount()")
                assert not errors, errors
                browser.close()
            print("PASS: release ZIP frontend; metadata display name with stable loader identity, progressive capture/setup help, explicit system audio, partial setup with guarded actions, unknown capture label; automatic polls/confirmed transition toasts, duplicate Start coalescing, idle Stop disabled, pending Cancel, guarded capture-mode switch with JSON RPC args/no streaming toast/no duplicate action, check-only updates, colors/lifecycle, full timeout, history paging/clear/reload; actual clipboard copies all history and version, excludes settings, works during streaming, legacy fallback preserves focus and denial reports failure; five exact support destinations, hidden unconfigured wallets, navigation failure isolation and focus across polls. Real controller/Decky runtime untested.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
