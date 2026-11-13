#!/usr/bin/env python3
"""Exercise M3 controls from the actual compiled plugin ZIP in a simulated Decky host."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import zipfile
from playwright.sync_api import expect, sync_playwright

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*_): pass

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_zip",type=Path)
    parser.add_argument("--browser",default="/usr/bin/chromium")
    parser.add_argument("--screenshots",type=Path,default=Path("/tmp/obsgod-m3-panel"))
    args=parser.parse_args();args.screenshots.mkdir(parents=True,exist_ok=True)
    decky=Path(__file__).resolve().parents[1]/"decky"
    with tempfile.TemporaryDirectory(prefix="obsgod-m3-panel-") as directory:
        root=Path(directory)
        with zipfile.ZipFile(args.plugin_zip) as archive: archive.extractall(root)
        subprocess.run(["node","tests/build-fixture.mjs",str(root/"runtime.js")],cwd=decky,check=True)
        shutil.copyfile(decky/"tests/fixture.html",root/"index.html")
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":800,"height":900});page.context.grant_permissions(["clipboard-read","clipboard-write"])
                errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.get_by_role("button",name="Start streaming",exact=True)).to_be_enabled()
                page.get_by_role("button",name="Open stream profiles",exact=True).click()
                expect(page.get_by_text("Current: 1280×720",exact=False)).to_be_visible()
                page.get_by_role("button",name="Preview selected preset",exact=True).click()
                expect(page.get_by_text("Starting point, not hardware qualified",exact=False)).to_be_visible()
                page.evaluate("fixture.obsAbsent=true")
                page.get_by_role("button",name="Apply selected preset",exact=True).click()
                expect(page.get_by_role("button",name="Apply selected preset",exact=True)).to_be_enabled()
                assert "apply" in page.evaluate("fixture.profileActions")
                assert not page.evaluate("fixture.active")
                page.evaluate("fixture.obsAbsent=false")
                page.get_by_role("button",name="Copy settings-only profile",exact=True).click()
                page.get_by_text("Copied a settings-only profile.",exact=False).wait_for()
                clipboard=page.evaluate("navigator.clipboard.readText()")
                assert 'width' in clipboard and 'stream_key' not in clipboard and 'server' not in clipboard
                page.get_by_role("button",name="Use black between-game screen",exact=True).click()
                expect(page.get_by_role("button",name="Use black between-game screen",exact=True)).to_be_enabled()
                assert page.evaluate("fixture.idleArgs.idle_style")=="black"
                assert not page.evaluate("fixture.active")
                page.evaluate("fixture.mediaStartPending=true;fixture.mediaCancelled=false")
                page.get_by_role("button",name="Start local recording",exact=True).click()
                page.get_by_role("button",name="Cancel local media startup",exact=True).click()
                expect(page.get_by_role("button",name="Start local recording",exact=True)).to_be_enabled()
                assert not page.evaluate("fixture.recording") and not page.evaluate("fixture.active")
                assert page.evaluate("fixture.calls.stop||0")==0
                page.evaluate("fixture.mediaStartPending=false;fixture.mediaCancelled=false")
                page.get_by_role("button",name="Start local recording",exact=True).click()
                expect(page.get_by_role("button",name="Stop & save recording",exact=True)).to_be_enabled()
                assert page.evaluate("fixture.recording") and not page.evaluate("fixture.active")
                expect(page.get_by_role("button",name="Apply selected preset",exact=True)).to_be_disabled()
                expect(page.get_by_role("button",name="Start streaming",exact=True)).to_be_disabled()
                page.get_by_role("button",name="Start replay buffer",exact=True).click()
                expect(page.get_by_role("button",name="Save replay clip",exact=True)).to_be_enabled()
                page.get_by_role("button",name="Stop & save recording",exact=True).click()
                expect(page.get_by_role("button",name="Start local recording",exact=True)).to_be_enabled()
                assert not page.evaluate("fixture.recording") and page.evaluate("fixture.replay")
                expect(page.get_by_role("button",name="Apply selected preset",exact=True)).to_be_disabled()
                page.get_by_role("button",name="Save replay clip",exact=True).click()
                page.get_by_text("Saved: /fixture/Videos/OBSGod/clip.mkv",exact=False).wait_for()
                page.get_by_role("button",name="Stop replay buffer",exact=True).click()
                expect(page.get_by_role("button",name="Start replay buffer",exact=True)).to_be_enabled()
                expect(page.get_by_role("button",name="Apply selected preset",exact=True)).to_be_enabled()
                page.get_by_role("button",name="Browse saved clips",exact=True).click()
                page.get_by_text("recording · clip.mkv",exact=False).wait_for()
                page.evaluate("fixture.unknown=true")
                page.get_by_role("button",name="Refresh status",exact=True).click()
                expect(page.get_by_role("button",name="Start local recording",exact=True)).to_be_disabled()
                expect(page.get_by_role("button",name="Save replay clip",exact=True)).to_be_disabled()
                expect(page.get_by_role("button",name="Stop recording / recover",exact=True)).to_be_enabled()
                expect(page.get_by_role("button",name="Stop replay / recover",exact=True)).to_be_enabled()
                expect(page.get_by_role("button",name="Use black between-game screen",exact=True)).to_be_disabled()
                page.evaluate("fixture.unknown=false")
                page.get_by_role("button",name="Refresh status",exact=True).click()
                page.get_by_role("button",name="Measure current stream health",exact=True).click()
                page.get_by_text("Network-dropped frames: 5.0%",exact=False).wait_for()
                page.get_by_text("GPU: Not measured",exact=False).wait_for()
                page.get_by_text("Check your connection; quality was not changed automatically.",exact=True).wait_for()
                calls=page.evaluate("fixture.calls.stream_health")
                page.wait_for_function("previous=>fixture.calls.stream_health>previous",arg=calls,timeout=9000)
                page.evaluate("fixture.healthFailure=true")
                page.get_by_text("Measurements expired or unavailable.",exact=False).wait_for(timeout=10000)
                assert not page.evaluate("fixture.active")
                assert page.evaluate("fixture.calls.start||0")==0
                assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
                page.screenshot(path=str(args.screenshots/"m3-controls.png"),full_page=True)
                assert not errors,errors
                page.evaluate("plugin.onDismount()")
                browser.close()
            print("PASS: compiled ZIP M3 profiles/presets/sanitized export, idle changes, cancellable local startup, confirmed recording+replay coexistence/save, owned clip list, unknown-state recovery gates, fresh/expired health and automatic health polls; no implicit broadcast. Simulated Decky, not actual Deck/controller proof.")
        finally: server.shutdown();server.server_close();thread.join()

if __name__=="__main__": main()
