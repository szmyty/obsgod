#!/usr/bin/env python3
"""Exercise Desktop mixer assets with a controlled authenticated transport fixture.

An optional runtime archive uses the exact packaged HTML/JS/CSS. This verifies
browser state and interaction, not OBS devices, native audio or Deck hardware.
"""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tarfile
import tempfile
import threading
import time
from playwright.sync_api import expect, sync_playwright

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path,nargs="?")
    parser.add_argument("--browser",default="/usr/bin/chromium")
    parser.add_argument("--screenshots",type=Path,default=Path("/tmp/obsgod-mixer-setup"))
    args=parser.parse_args();args.screenshots.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="obsgod-mixer-setup-") as temporary:
        root=Path(__file__).resolve().parents[1]
        if args.archive:
            with tarfile.open(args.archive) as archive:archive.extractall(temporary,filter="data")
            root=next(Path(temporary).glob("OBSGod-*"))
        fixture={"known":True,"obs_absent":False,"available":True,"system_muted":False,"talk_until":0,"notice":None,"calls":[],"active":True,"prefs":{"version":1,"microphone_enabled":False,"microphone_device":"default","microphone_muted":True,"microphone_gain_percent":100,"game_gain_percent":100,"push_to_talk":False},"profile":{"version":1,"width":1280,"height":720,"fps":30,"bitrate":4500,"encoder":"vaapi","microphone":False,"capture_mode":"game"}}
        def snapshot():
            now=time.time();prefs=dict(fixture["prefs"]);known=fixture["known"] and not fixture["obs_absent"]
            return {"schema_version":1,"known":known,"state":"ready" if known else "unknown","observed_at":time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(now))+"Z","expires_at":time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(now+8))+"Z","preferences":prefs,"microphone":{"known":known,"available":fixture["available"],"muted":prefs["microphone_muted"] or not prefs["microphone_enabled"] or not fixture["available"] or (prefs["push_to_talk"] and time.monotonic()>=fixture["talk_until"]),"system_muted":fixture["system_muted"],"signal":"signal","peak_dbfs":-16},"game":{"known":known,"available":True,"muted":False},"devices":[{"id":"deck-input","label":"Built-in microphone","default":True,"available":True},{"id":"headset-input","label":"Headset microphone","default":False,"available":True}],"hardware":{"model":"unknown","guidance":"Device routes are observed; no LCD jack state is assumed."},"notice":fixture["notice"]}
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":1280,"height":1000});errors=[]
                page.on("pageerror",lambda error:errors.append(str(error)))
                def api(route):
                    request=route.request
                    assert request.headers.get("authorization")=="Bearer mixer-browser-fixture"
                    path=request.url.split("/api/")[1]
                    data={"ok":True,"message":"Fixture connection ready"}
                    if path=="status":data.update(product_name="Decky Stream",configured=False,plugin_zip="fixture.zip",mixer=snapshot(),stream={"active":fixture["active"]},settings={**fixture["profile"],"server":"","idle_style":"black"})
                    elif path=="connection":data.update(process="absent" if fixture["obs_absent"] else "running",output_known=True)
                    elif path=="action":
                        body=request.post_data_json;fixture["calls"].append(body)
                        payload=body["settings"];action=payload["action"]
                        if body["action"]=="stream-profiles":
                            preset={**fixture["profile"],"capture_mode":"game","microphone":False}
                            if action=="list":data.update(current=dict(fixture["profile"]),profiles=[],presets=[{"name":"balanced-720p30","label":"Balanced 720p30","description":"Starting point","profile":preset}])
                            else:
                                assert action in ["apply","reset"],action
                                assert fixture["obs_absent"] and not fixture["active"],"Profile changes require closed OBS and idle output"
                                fixture["profile"]={**preset,"capture_mode":"screen" if action=="reset" else "game"}
                                data.update(profile=dict(fixture["profile"]),message="Profile defaults saved; existing live audio unchanged")
                        elif body["action"]!="mixer":raise AssertionError(body)
                        elif action=="configure":
                            patch=payload["preferences"];fixture["prefs"].update(patch)
                            if "microphone_device" in patch:fixture["prefs"]["microphone_muted"]=True
                            data["message"]="Audio preferences saved; stream unchanged"
                        elif action=="talk-start":
                            assert fixture["known"] and fixture["available"] and fixture["prefs"]["push_to_talk"] and not fixture["prefs"]["microphone_muted"]
                            fixture["talk_until"]=time.monotonic()+1.2;data.update(talk_token="fixture-hold",lease_ms=1200,talk_expires_at=datetime.fromtimestamp(time.time()+1.2,timezone.utc).isoformat())
                        elif action in ["talk-release","talk-cancel"]:fixture["talk_until"]=0
                        else:assert action in ["status","devices"],action
                        if body["action"]=="mixer":data["mixer"]=snapshot()
                    route.fulfill(status=200,content_type="application/json",body=json.dumps(data))
                page.route("**/api/**",api)
                page.goto(f"http://127.0.0.1:{server.server_port}/setup.html#mixer-browser-fixture")
                expect(page.locator("#mixer-observed")).to_have_text("Microphone disabled")
                expect(page.locator("#mixer-unmute")).to_be_disabled()
                page.locator("#mixer-enabled").check()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone muted on stream")
                page.locator("#mixer-unmute").click()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone live on stream")
                expect(page.locator("#mixer-level")).to_have_attribute("aria-valuetext","Voice level: -16.0 dBFS")
                page.locator("#mixer-device").select_option("headset-input")
                expect(page.locator("#mixer-observed")).to_have_text("Microphone muted on stream")
                assert fixture["prefs"]["microphone_device"]=="headset-input"
                page.locator("#mixer-game-gain").fill("0");page.locator("#mixer-mic-gain").fill("145")
                page.locator("#mixer-levels").click()
                expect(page.locator("#mixer-levels")).to_be_disabled()
                assert fixture["prefs"]["game_gain_percent"]==0 and fixture["prefs"]["microphone_gain_percent"]==145
                expect(page.get_by_label("Initial microphone default (before live audio is configured)",exact=True)).to_be_visible()
                expect(page.locator("#microphone-default-help")).to_contain_text("does not mute or disable")
                page.locator("#mixer-unmute").click()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone live on stream")
                saved_mixer=dict(fixture["prefs"])
                fixture["obs_absent"]=True;fixture["active"]=False
                page.locator("#mixer-refresh").click()
                expect(page.locator("#mixer-observed")).to_contain_text("unconfirmed")
                page.locator("#profiles-load").click()
                expect(page.locator("#profile-preset-help")).to_contain_text("initial microphone default off")
                page.locator("#profile-apply-preset").click()
                expect(page.locator("#profiles-status")).to_contain_text("existing live audio unchanged")
                assert fixture["prefs"]==saved_mixer and fixture["profile"]["microphone"] is False
                dialogs=[]
                def confirm(dialog):dialogs.append(dialog.message);dialog.accept()
                page.on("dialog",confirm);page.locator("#profile-reset").click()
                expect(page.locator("#capture_mode")).to_have_value("screen")
                assert dialogs and "initial microphone default off" in dialogs[-1] and "live microphone, mute and gain preferences remain unchanged" in dialogs[-1]
                assert fixture["prefs"]==saved_mixer
                expect(page.locator("#mixer-observed")).to_contain_text("unconfirmed")
                fixture["obs_absent"]=False;page.locator("#mixer-refresh").click()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone live on stream")
                fixture["active"]=True
                fixture["known"]=False;page.locator("#mixer-refresh").click()
                expect(page.locator("#mixer-observed")).to_contain_text("unconfirmed")
                expect(page.locator("#mixer-unmute")).to_be_disabled()
                expect(page.locator("#mixer-mute")).to_be_enabled()
                fixture["known"]=True;fixture["available"]=False;fixture["prefs"]["microphone_muted"]=True;fixture["notice"]={"code":"input-lost","revision":"observed-route-1","message":"Selected input disappeared; microphone kept muted."}
                page.locator("#mixer-refresh").click()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone unavailable · kept muted")
                expect(page.locator("#mixer-notice")).to_have_text(fixture["notice"]["message"])
                page.locator("#mixer-refresh").click()
                assert page.evaluate("mixerNotices.size")==1
                fixture["available"]=True;page.locator("#mixer-refresh").click()
                expect(page.locator("#mixer-observed")).to_have_text("Microphone muted on stream")
                page.locator("#mixer-ptt").check()
                expect(page.locator("#mixer-arm")).to_be_enabled();page.locator("#mixer-arm").click()
                hold=page.locator("#mixer-talk");expect(hold).to_be_enabled();hold.focus();page.keyboard.down("Space")
                expect(hold).to_have_attribute("aria-pressed","true")
                page.wait_for_function("mixerTalkToken==='fixture-hold'")
                page.keyboard.up("Space");expect(hold).to_have_attribute("aria-pressed","false")
                hold.focus();page.keyboard.down("Enter");expect(hold).to_have_attribute("aria-pressed","true")
                page.evaluate("window.dispatchEvent(new Event('blur'))");page.keyboard.up("Enter")
                expect(hold).to_have_attribute("aria-pressed","false")
                assert all(call["action"] in ["mixer","stream-profiles"] for call in fixture["calls"])
                assert fixture["active"] is True
                for width in [1280,800,390]:
                    page.set_viewport_size({"width":width,"height":1000})
                    assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
                    page.locator("#mixer-heading").scroll_into_view_if_needed()
                    page.screenshot(path=str(args.screenshots/f"mixer-setup-{width}.png"))
                assert not errors,errors
                browser.close()
            print("PASS: Desktop mixer assets with authenticated fixture transport; mute/unmute, initial-default/profile/reset privacy wording, preserved live audio preferences through closed-OBS profile apply/reset and fresh observation after reopen, explicit muted input selection, zero/custom gains, unknown/lost input gates, transition notice dedupe, keyboard hold/release/blur, responsive widths and no implicit broadcast. OBS/native Deck proof remains separate.")
        finally:server.shutdown();server.server_close();thread.join()

if __name__=="__main__":main()
