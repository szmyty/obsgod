#!/usr/bin/env python3
"""Exercise M3 authenticated Desktop setup from an installed runtime archive.

Real CLI/filesystem, temporary HOME, fixture credentials, OBS absent. Does not
qualify Deck hardware, OBS output or the full Decky transport installer.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
from playwright.sync_api import expect,sync_playwright
from test_bootstrap import read_until


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--browser",default="/usr/bin/chromium")
    parser.add_argument("--screenshots",type=Path,default=Path("/tmp/obsgod-m3-setup"))
    args=parser.parse_args();args.screenshots.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="obsgod-m3-setup-") as temporary:
        base=Path(temporary)
        with tarfile.open(args.archive) as archive:archive.extractall(base,filter="data")
        package=next(base.glob("OBSGod-*"));home=base/"home with spaces";home.mkdir()
        env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/".config"),XDG_DATA_HOME=str(home/".local/share"),XDG_STATE_HOME=str(home/".local/state"),XDG_CACHE_HOME=str(home/".cache"),BROWSER="/bin/true")
        subprocess.run([sys.executable,str(package/"install.py"),"--app-only","--no-launch"],env=env,check=True,capture_output=True)
        current=home/".local/share/obsgod/current"
        image=base/"owner image.png"
        image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
        process=subprocess.Popen([sys.executable,str(current/"setup.py")],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:
            output=read_until(process,b"http://127.0.0.1:")
            url=re.search(rb"http://127\.0\.0\.1:\d+/#[-\w]+",output).group().decode()
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":1280,"height":900});page.context.grant_permissions(["clipboard-read","clipboard-write"])
                errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
                page.goto(url)
                expect(page.locator("#server")).to_be_visible()
                page.locator("#server").fill("rtmps://fixture.invalid/app")
                page.locator("#key").fill("m3-browser-fixture-never-real")
                page.locator("#capture_mode").select_option("game")
                page.locator("#resolution").select_option("960x540")
                page.locator("#bitrate").fill("3200")
                page.locator("#save").click()
                page.get_by_text("Settings saved on this device",exact=True).wait_for()
                settings=json.loads((home/".config/obsgod/deck.json").read_text())
                assert settings["width"]==960 and settings["height"]==540 and settings["bitrate"]==3200
                page.locator("#profiles-load").click()
                expect(page.locator("#profile-preset")).not_to_have_value("")
                page.locator("#profile-preview").click()
                expect(page.locator("#profiles-status")).to_contain_text("not hardware",ignore_case=True)
                page.locator("#profile-name").fill("my-game")
                page.locator("#profile-save").click()
                expect(page.locator("#profile-saved")).to_have_value("my-game")
                page.locator("#profile-export").click()
                expect(page.locator("#profile-json")).not_to_have_value("")
                exported=json.loads(page.locator("#profile-json").input_value())
                assert exported["version"]==1 and exported["profile"]["width"]==960
                assert all(word not in json.dumps(exported) for word in ["stream_key","server","password","fixture.invalid","m3-browser-fixture","idle_media"])
                page.get_by_text("Settings-only import/export and game binding",exact=True).click()
                page.locator("#profile-copy").click()
                expect(page.locator("#profiles-status")).to_contain_text("Copied")
                assert json.loads(page.evaluate("navigator.clipboard.readText()"))==exported
                page.locator("#profile-game").fill("620")
                page.locator("#profile-bind").click()
                expect(page.locator("#profile-bindings")).to_contain_text("620 → my-game")
                page.locator("#profile-name").fill("imported-game")
                page.locator("#profile-import").click()
                expect(page.locator("#profiles-status")).to_contain_text("imported",ignore_case=True)
                rejected=page.evaluate("source=>api('/api/action',{action:'set-idle-media',settings:{idle_style:'image',source,rights_acknowledged:false}})",str(image))
                assert rejected["ok"] is False
                page.locator("#idle-media-source").fill(str(image))
                page.locator("#idle-media-attribution").fill("Original synthetic test pixel; test owner permission")
                page.locator("#idle-media-rights").check()
                page.locator("#idle-media-import").click()
                expect(page.locator("#idle-media-source")).to_have_value("")
                expect(page.locator("#idle_style")).to_have_value("image")
                settings=json.loads((home/".config/obsgod/deck.json").read_text())
                assert re.fullmatch(r"[0-9a-f]{64}\.png",settings["idle_media"])
                assert settings["idle_media_rights"]
                assert image.exists(),"Import must preserve original media"
                assert (home/".var/app/com.obsproject.Studio/config/obsgod/obs-studio/obsgod-media"/settings["idle_media"]).exists()
                page.locator("#media-refresh").click()
                expect(page.locator("#media-status")).to_contain_text("Recording: stopped")
                expect(page.locator("#record-start")).to_be_enabled()
                expect(page.locator("#replay-save")).to_be_disabled()
                page.get_by_text("Storage, replay limits and owned clips",exact=True).click()
                page.locator("#media-replay-seconds").fill("45")
                page.locator("#media-directory").fill(str(home/"Videos/Custom clips"))
                page.locator("#media-save-preferences").click()
                expect(page.locator("#media-status")).to_contain_text("saved",ignore_case=True)
                prefs=json.loads((home/".config/obsgod/recording.json").read_text())
                assert prefs["replay_seconds"]==45 and prefs["directory"].endswith("Custom clips")
                page.locator("#media-list").click()
                expect(page.locator("#media-library")).to_contain_text("No finalized owned clips")
                expect(page.locator("#media-prune-confirm")).to_be_disabled()
                page.locator("#stream-health").click()
                expect(page.locator("#stream-health-status")).to_contain_text("Provider/viewer reception: unknown")
                assert "m3-browser-fixture-never-real" not in page.locator("body").inner_text()
                assert "fixture.invalid" not in page.locator("#profile-json").input_value()
                status=page.evaluate("api('/api/status')")
                assert not status.get("stream",{}).get("active") and not status.get("recording")
                for width in [1280,800,390]:
                    page.set_viewport_size({"width":width,"height":900})
                    assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
                    page.screenshot(path=str(args.screenshots/f"m3-setup-{width}.png"),full_page=True)
                assert not errors,errors
                page.locator("#close").click();browser.close()
            process.wait(timeout=5)
            print("PASS: installed-archive authenticated M3 Desktop UI; resolution/custom bitrate roundtrip, profile preview/save/export/import/game binding with no secrets, acknowledged local image import/preservation, storage preferences, empty owned-clip library, unknown provider reception and responsive widths. Real CLI/filesystem; no OBS output or actual Deck proof.")
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=="__main__":main()
