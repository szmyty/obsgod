#!/usr/bin/env python3
"""Test the shipped configuration UI with simulated Decky APIs, not a Steam Deck."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile

from playwright.sync_api import expect, sync_playwright


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_zip", type=Path)
    parser.add_argument("--browser", default="/usr/bin/chromium")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    decky = Path(__file__).resolve().parents[1] / "decky"
    cases = []
    with tempfile.TemporaryDirectory(prefix="obsgod-native-configuration-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(args.plugin_zip) as archive:
            archive.extractall(root)
        subprocess.run(["node", "tests/build-fixture.mjs", str(root / "runtime.js")], cwd=decky, check=True)
        shutil.copyfile(decky / "tests/fixture.html", root / "index.html")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 800, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto("http://127.0.0.1:" + str(server.server_port))
                button = lambda name: page.get_by_role("button", name=name, exact=True)
                # Primary output controls stay before saved setup at the narrow
                # simulated panel size. This is geometry, not Deck controller proof.
                page.set_viewport_size({"width": 400, "height": 800})
                expect(button("Edit saved destination")).to_be_visible()
                expect(page.get_by_label("Stream key", exact=True)).to_have_count(0)
                for active in (False, True):
                    page.evaluate("active=>{fixture.active=active;fixture.bytes=2048}", active)
                    button("Refresh status").click()
                    if active:
                        expect(button("Start streaming")).to_be_disabled()
                    else:
                        expect(button("Start streaming")).to_be_enabled()
                    page.evaluate("window.scrollTo(0,0)")
                    stop = page.get_by_role("button", name=re.compile(r"^Stop streaming"))
                    stop_box = stop.bounding_box()
                    setup_box = page.get_by_role("heading", name="DEPENDENCY SETUP", exact=True).bounding_box()
                    assert stop_box and setup_box and stop_box["y"] + stop_box["height"] <= 800
                    assert stop_box["y"] < setup_box["y"]
                page.evaluate("fixture.active=false")
                button("Refresh status").click()
                expect(button("Start streaming")).to_be_enabled()
                page.set_viewport_size({"width": 800, "height": 900})
                button("Edit saved destination").click()
                cases.append("configured and streaming primary controls precede saved setup without narrow-panel scrolling")
                key = page.get_by_label("Stream key", exact=True)
                url = page.get_by_label("Stream server URL", exact=True)
                save = button("Save destination & settings")
                refresh = button("Refresh settings")
                expect(key).to_be_disabled()
                button("Close managed OBS to edit settings…").click()
                dialog = page.get_by_role("dialog", name="Close managed OBS to edit settings?")
                dialog.get_by_role("button", name="Cancel", exact=True).click()
                assert not page.evaluate("fixture.calls.close_managed_obs||0")
                button("Close managed OBS to edit settings…").click()
                dialog.get_by_role("button", name="Close managed OBS", exact=True).click()
                expect(key).to_be_enabled()
                assert page.evaluate("fixture.obsAbsent")
                assert not page.evaluate("fixture.active")
                cases.append("idle OBS close is explicit and confirmed; cancel has no side effect")

                # Missing dependencies must not prevent offline private configuration.
                page.evaluate("fixture.configured=false;fixture.dependencyReady=false;fixture.dependencyState='setup_required'")
                button("Check setup status").click()
                refresh.click()
                expect(save).to_be_enabled()
                url.fill("rtmps://fixture.global-contribute.live-video.net:443/app")
                key.fill("private-native-key-1")
                expect(key).to_have_attribute("type", "password")
                button("Show stream key").click()
                expect(key).to_have_attribute("type", "text")
                button("Hide stream key").click()
                reads = page.evaluate("fixture.calls.configuration_status")
                key.focus()
                page.wait_for_function("reads=>fixture.calls.configuration_status>reads", arg=reads)
                expect(key).to_be_focused()
                expect(key).to_have_value("private-native-key-1")
                save.evaluate("element=>{element.click();element.click();element.click();}")
                expect(key).to_have_value("")
                page.wait_for_function("fixture.configured")
                assert page.evaluate("fixture.calls.configure_destination") == 1
                assert page.evaluate("fixture.privateKey") == "private-native-key-1"
                assert not page.evaluate("fixture.calls.start||0")
                cases.append("first Kick destination saves offline, masks and clears keys, deduplicates Save and never broadcasts")

                # Blank retention sends no secret and does not reset unedited advanced state.
                button("Stream quality & capture settings").click()
                page.get_by_label("Frame rate", exact=True).select_option("60")
                save.click()
                page.wait_for_function("fixture.configurationSaved.fps===60")
                assert page.evaluate("fixture.configurationPatches.at(-1)") == {"fps": 60}
                assert page.evaluate("fixture.configurationSaved.idle_text") == "Preserve this idle message"
                assert page.evaluate("fixture.privateKey") == "private-native-key-1"
                cases.append("same-destination blank key retains privately; sparse quality edits preserve advanced preferences")

                calls = page.evaluate("fixture.calls.configure_destination")
                url.fill("rtmps://another-ingest.invalid/app")
                save.click()
                expect(page.get_by_text("Enter the key for this destination.", exact=False)).to_be_visible()
                assert page.evaluate("fixture.calls.configure_destination") == calls
                key.fill("discard-on-destination-change")
                page.get_by_label("Destination guide", exact=True).select_option("custom")
                expect(key).to_have_value("")
                page.context.grant_permissions(["clipboard-read", "clipboard-write"])
                page.evaluate("navigator.clipboard.writeText('private-native-key-2')")
                button("Paste stream key").click()
                expect(key).to_have_value("private-native-key-2")
                expect(key).to_have_attribute("type", "password")
                save.click()
                page.wait_for_function("fixture.configurationSaved.server==='rtmps://another-ingest.invalid/app'")
                expect(key).to_have_value("")
                page.get_by_label("Different account or event on the same server", exact=True).check()
                calls = page.evaluate("fixture.calls.configure_destination")
                save.click()
                assert page.evaluate("fixture.calls.configure_destination") == calls
                key.fill("private-native-key-3")
                save.click()
                page.wait_for_function("fixture.privateKey==='private-native-key-3'")
                assert page.evaluate("fixture.configurationPatches.at(-1).replace_key") is True
                cases.append("server/provider/account changes require a replacement key; clipboard paste stays masked")

                page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{readText:()=>Promise.reject(Error('denied'))}})")
                button("Paste stream key").click()
                expect(page.get_by_text("Clipboard access is unavailable.", exact=False)).to_be_visible()
                expect(key).to_have_value("")
                cases.append("clipboard denial gives manual keyboard/paste guidance without retaining a draft")

                page.evaluate("fixture.configurePending=true")
                page.get_by_label("Frame rate", exact=True).select_option("30")
                save.click()
                expect(button("Saving settings…")).to_be_disabled()
                calls = page.evaluate("fixture.calls.configure_destination")
                page.evaluate("fixture.finishConfiguration();fixture.configurePending=false")
                expect(save).to_be_enabled()
                assert page.evaluate("fixture.calls.configure_destination") == calls
                cases.append("pending save locks edits and repeated requests")

                for state in ("active", "recording", "replay", "unknown"):
                    page.evaluate("name=>{fixture[name]=true}", state)
                    refresh.click()
                    expect(save).to_be_disabled()
                    expect(key).to_be_disabled()
                    page.evaluate("name=>{fixture[name]=false}", state)
                    refresh.click()
                    expect(save).to_be_enabled()
                page.evaluate("fixture.dependencyState='running';fixture.dependencyReady=false")
                button("Check setup status").click()
                expect(save).to_be_disabled()
                page.evaluate("fixture.active=true;fixture.bytes=4096")
                button("Refresh status").click()
                stop = page.get_by_role("button", name=re.compile(r"^Stop streaming"))
                expect(stop).to_be_enabled()
                stop.click()
                page.wait_for_function("!fixture.active")
                page.evaluate("fixture.dependencyState='ready';fixture.dependencyReady=true")
                button("Check setup status").click()
                refresh.click()
                expect(save).to_be_enabled()
                cases.append("active, recording, replay, unknown and setup-busy states block edits while Stop stays available")

                button("Show local connection controls").click()
                button("Test local OBS connection").click()
                expect(page.get_by_text("Managed OBS is closed", exact=False).first).to_be_visible()
                assert page.evaluate("fixture.obsAbsent")
                button("Manage local OBS password").click()
                password = page.get_by_label("New local OBS password", exact=True)
                password.fill("discard-on-modal-dismiss")
                button("Change local OBS password…").click()
                page.evaluate("fixture.dismissModal()")
                expect(password).to_have_value("")
                password.fill("private-local-control-password")
                expect(password).to_have_attribute("type", "password")
                button("Change local OBS password…").click()
                password_dialog = page.get_by_role("dialog", name="Change the managed OBS password?")
                password_dialog.get_by_role("button", name="Save private password", exact=True).click()
                expect(password).to_have_value("")
                assert page.evaluate("fixture.controlPassword") == "private-local-control-password"
                button("Generate a new private OBS password…").click()
                password_dialog.get_by_role("button", name="Generate private password", exact=True).click()
                page.wait_for_function("fixture.controlPassword==='generated-private-password'")
                assert page.evaluate("fixture.privateKey") == "private-native-key-3"
                assert not page.evaluate("fixture.active")
                cases.append("read-only connection test never launches; confirmed password changes preserve the separate stream key")

                page.evaluate("fixture.linkFailure=true")
                page.get_by_role("button", name=re.compile(r"^Open .* setup guide$")).click()
                expect(page.get_by_text("Could not open the provider setup guide.", exact=False)).to_be_visible()
                page.evaluate("fixture.linkFailure=false")
                cases.append("failed provider guide navigation has accessible public feedback")

                key.fill("discard-on-hide-key")
                password.fill("discard-on-hide-password")
                page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{readText:()=>new Promise(resolve=>{fixture.finishClipboard=resolve})}})")
                button("Paste stream key").click()
                page.wait_for_function("typeof fixture.finishClipboard==='function'")
                button("Hide destination settings").click()
                expect(key).to_have_count(0)
                expect(password).to_have_count(0)
                page.evaluate("fixture.finishClipboard('late-private-clipboard-value')")
                edit = button("Edit saved destination")
                edit.focus()
                reads = page.evaluate("fixture.calls.configuration_status")
                page.wait_for_function("reads=>fixture.calls.configuration_status>reads", arg=reads)
                expect(edit).to_be_focused()
                edit.click()
                expect(key).to_have_value("")
                expect(key).to_have_attribute("type", "password")
                button("Show local connection controls").click()
                button("Manage local OBS password").click()
                expect(password).to_have_value("")
                expect(password).to_have_attribute("type", "password")
                for private in ("discard-on-hide-key", "discard-on-hide-password", "late-private-clipboard-value"):
                    assert private not in page.locator("body").inner_text()
                    assert private not in page.evaluate("JSON.stringify({...localStorage,...sessionStorage})")
                button("Show Desktop Setup instructions").click()
                expect(page.get_by_text("Advanced profiles, custom between-game media", exact=False)).to_be_visible()
                assert "127.0.0.1" not in page.evaluate("JSON.stringify(fixture.externalLinks)")
                cases.append("hiding settings clears both private drafts and late clipboard replies; stable focus and optional Desktop instructions")

                page.evaluate("fixture.configurationFailure=true")
                refresh.click()
                expect(save).to_be_disabled()
                expect(page.get_by_text("Could not confirm configuration readiness.", exact=False)).to_be_visible()
                for private in ("private-native-key-1", "private-native-key-2", "private-native-key-3", "private-local-control-password", "generated-private-password", "must-not-copy"):
                    assert private not in page.locator("body").inner_text()
                    assert private not in page.evaluate("JSON.stringify({...localStorage,...sessionStorage})")
                page.screenshot(path=str(args.output / "native-configuration.png"))
                page.evaluate("fixture.configurationFailure=false")
                refresh.click()
                expect(key).to_be_enabled()
                key.fill("unsaved-reload-private-draft")
                page.reload()
                button("Edit saved destination").click()
                expect(key).to_have_value("")
                assert "unsaved-reload-private-draft" not in page.evaluate("JSON.stringify({...localStorage,...sessionStorage})")
                assert not errors, errors
                cases.append("failed readiness disables writes; no saved secrets in readback, DOM, browser storage or reload")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    (args.output / "result.json").write_text(json.dumps({"passed": cases, "limitations": "Actual packaged frontend with simulated Decky/OBS APIs; controller, SteamOS, Flatpak and provider reception unrun."}, indent=2) + "\n")
    print("Passed", len(cases), "packaged native-configuration browser cases")


if __name__ == "__main__":
    main()
