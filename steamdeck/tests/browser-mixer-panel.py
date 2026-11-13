#!/usr/bin/env python3
"""Exercise compiled live mixer UI in the simulated Decky host (no hardware proof)."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import re
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
    parser.add_argument("--screenshots",type=Path,default=Path("/tmp/obsgod-mixer-panel"))
    args=parser.parse_args();args.screenshots.mkdir(parents=True,exist_ok=True)
    decky=Path(__file__).resolve().parents[1]/"decky"
    with tempfile.TemporaryDirectory(prefix="obsgod-mixer-panel-") as directory:
        root=Path(directory)
        with zipfile.ZipFile(args.plugin_zip) as archive:archive.extractall(root)
        subprocess.run(["node","tests/build-fixture.mjs",str(root/"runtime.js")],cwd=decky,check=True)
        shutil.copyfile(decky/"tests/fixture.html",root/"index.html")
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":800,"height":900});errors=[]
                page.on("pageerror",lambda error:errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                button=lambda name:page.get_by_role("button",name=name,exact=True)
                expect(button("Enable microphone capture · starts muted")).to_be_enabled()
                expect(button("Unmute microphone on stream")).to_be_disabled()
                button("Enable microphone capture · starts muted").click()
                expect(page.get_by_text("Microphone muted on stream",exact=True)).to_be_visible()
                assert page.evaluate("fixture.mixerPreferences.microphone_muted") is True
                button("Unmute microphone on stream").click()
                expect(page.get_by_text("Microphone live on stream",exact=True)).to_be_visible()
                expect(page.get_by_role("meter",name="Microphone input level")).to_have_attribute("aria-valuenow","-18")
                page.get_by_label("Microphone input",exact=True).select_option("headset-mic")
                expect(page.get_by_text("Microphone muted on stream",exact=True)).to_be_visible()
                assert page.evaluate("fixture.mixerPreferences.microphone_device")=="headset-mic"
                page.get_by_label("Game / system audio gain",exact=True).fill("0")
                page.get_by_label("Microphone gain",exact=True).fill("150")
                button("Apply audio levels").click()
                expect(button("Apply audio levels")).to_be_disabled()
                assert page.evaluate("fixture.mixerPreferences.game_gain_percent")==0
                assert page.evaluate("fixture.mixerPreferences.microphone_gain_percent")==150
                assert page.evaluate("fixture.calls.start||0")==0
                # Initial profile defaults do not override saved live audio.
                # OBS must be closed for profile writes: actual mic is unknown
                # until a new managed-OBS observation after reopening.
                button("Unmute microphone on stream").click()
                expect(page.get_by_text("Microphone live on stream",exact=True)).to_be_visible()
                mixer_preferences=page.evaluate("({...fixture.mixerPreferences})")
                page.evaluate("fixture.obsAbsent=true")
                button("Refresh status").click()
                expect(page.get_by_text("Microphone state unconfirmed",exact=True)).to_be_visible()
                button("Open stream profiles").click()
                expect(page.get_by_text("Existing live microphone, mute and gain preferences stay unchanged",exact=False)).to_be_visible()
                expect(page.get_by_text("initial microphone default off",exact=False).first).to_be_visible()
                button("Apply selected preset").click()
                expect(button("Apply selected preset")).to_be_enabled()
                assert page.evaluate("fixture.mixerPreferences")==mixer_preferences
                assert page.evaluate("fixture.microphone") is False
                button("Reset stream settings to defaults").click()
                confirm=button("Confirm reset: entire screen; live audio unchanged")
                expect(confirm).to_be_visible()
                expect(page.get_by_text("Existing live microphone, mute and gain preferences remain unchanged.",exact=False)).to_be_visible()
                confirm.click()
                expect(button("Reset stream settings to defaults")).to_be_enabled()
                assert page.evaluate("fixture.mixerPreferences")==mixer_preferences
                assert page.evaluate("fixture.mode")=="screen"
                expect(page.get_by_text("Microphone state unconfirmed",exact=True)).to_be_visible()
                page.evaluate("fixture.obsAbsent=false")
                button("Refresh status").click()
                expect(page.get_by_text("Microphone live on stream",exact=True)).to_be_visible()
                assert page.evaluate("fixture.calls.start||0")==0
                page.evaluate("fixture.active=true;fixture.bytes=2048")
                button("Refresh status").click()
                expect(page.get_by_role("button",name=re.compile(r"^Stop streaming"))).to_be_enabled()
                button("Unmute microphone on stream").click()
                expect(page.get_by_text("Microphone live on stream",exact=True)).to_be_visible()
                assert page.evaluate("fixture.active") is True
                # A pending audio write cannot disable priority Stop, and its
                # late reply cannot restore the old streaming state.
                page.evaluate("fixture.mixerConfigurePending=true")
                button("Mute microphone on stream").click()
                expect(button("Unmute microphone on stream")).to_be_disabled()
                page.get_by_role("button",name=re.compile(r"^Stop streaming")).click()
                page.wait_for_function("fixture.active===false")
                page.evaluate("fixture.mixerConfigurePending=false;fixture.finishMixer();delete fixture.finishMixer")
                expect(button("Mute microphone on stream")).to_be_enabled()
                assert page.evaluate("fixture.active") is False
                expect(button("Start streaming")).to_be_enabled()
                page.evaluate("fixture.active=true")
                button("Refresh status").click()
                page.evaluate("fixture.mixerUnknown=true")
                button("Refresh status").click()
                expect(button("Unmute microphone on stream")).to_be_disabled()
                expect(page.get_by_text("Microphone state unconfirmed",exact=True)).to_be_visible()
                expect(button("Mute microphone on stream")).to_be_enabled()
                expect(page.get_by_role("button",name=re.compile(r"^Stop streaming"))).to_be_enabled()
                page.evaluate("fixture.mixerUnknown=false;fixture.mixerUnavailable=true;fixture.mixerPreferences.microphone_muted=true;fixture.mixerNotice={code:'input-lost',revision:'observed-route-1',message:'Selected input disappeared; microphone kept muted.'}")
                button("Refresh status").click()
                expect(page.get_by_text("Microphone unavailable · kept muted",exact=True)).to_be_visible()
                toast_count=page.evaluate("fixture.toasts.filter(value=>value.body==='Selected input disappeared; microphone kept muted.').length")
                assert toast_count==1
                button("Refresh status").click()
                assert page.evaluate("fixture.toasts.filter(value=>value.body==='Selected input disappeared; microphone kept muted.').length")==1
                page.evaluate("fixture.mixerUnavailable=false")
                button("Refresh status").click()
                expect(page.get_by_text("Microphone muted on stream",exact=True)).to_be_visible()
                button("Enable hold-to-talk · starts muted").click()
                expect(button("Arm hold-to-talk")).to_be_enabled()
                button("Arm hold-to-talk").click()
                hold=button("Hold here to talk")
                expect(hold).to_have_attribute("aria-disabled","false")
                hold.focus();page.keyboard.down("Space")
                expect(button("Talking lease active · release to mute")).to_have_attribute("aria-pressed","true")
                page.wait_for_function("fixture.mixerActions.filter(action=>action.action==='talk-start').length>=2")
                page.keyboard.up("Space")
                expect(button("Hold here to talk")).to_have_attribute("aria-pressed","false")
                page.wait_for_function("fixture.mixerTalking===false")
                hold.focus();page.keyboard.down("Enter")
                expect(button("Talking lease active · release to mute")).to_have_attribute("aria-pressed","true")
                page.evaluate("window.dispatchEvent(new Event('blur'))")
                page.keyboard.up("Enter")
                page.wait_for_function("fixture.mixerTalking===false")
                expect(button("Hold here to talk")).to_have_attribute("aria-pressed","false")
                assert page.evaluate("fixture.active") is True
                assert page.evaluate("fixture.calls.start||0")==0
                assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
                page.screenshot(path=str(args.screenshots/"mixer-live-controls.png"),full_page=True)
                assert not errors,errors
                page.evaluate("plugin.onDismount()")
                browser.close()
            print("PASS: compiled mixer UI mute/unmute, truthful initial-default/reset wording, live audio preferences preserved through closed-OBS profile apply/reset and fresh observation after reopen, input changes start muted, zero/custom gains, live output preserved, unknown/lost input gates, notice dedupe, hold-to-talk keyboard renewal/release/blur, and no implicit broadcast. Simulated Decky; native devices/controller proof remains separate.")
        finally:server.shutdown();server.server_close();thread.join()

if __name__=="__main__":main()
