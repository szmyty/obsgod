#!/usr/bin/env python3
"""Qualify live microphone/mixer safety against disposable real OBS/PulseAudio.

Run during the native fixture's existing explicitly started output. Synthetic
sources do not qualify Steam Deck hardware, jack/Bluetooth behavior or providers.
No key, password, device label or lease token reaches the summary.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

BIN = "/src/dist/obsgod"
MIC = "OBSGod Microphone"
GAME = "OBSGod Game Audio"


def pulse(*args, structured=False):
    result = subprocess.run(["pactl"] + (["--format=json"] if structured else []) + list(args), check=True, capture_output=True, timeout=3)
    return json.loads(result.stdout) if structured else result.stdout.decode().strip()


async def cli(payload):
    process = await asyncio.create_subprocess_exec(BIN, "deck", "mixer", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    output, _ = await asyncio.wait_for(process.communicate(json.dumps(payload).encode()), 8)
    result = json.loads(output)
    assert process.returncode == 0 and result.get("ok"), "The real mixer command failed; inspect its redacted diagnostics"
    return result


async def run():
    if not Path("/.dockerenv").exists() or os.environ.get("OBSGOD_DISPOSABLE_AUDIO_FIXTURE") != "1":
        raise ValueError("Use only the disposable OBS Docker fixture with its explicit audio-test flag")
    import websockets
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obsgod"
    mixer_path = config_root / "mixer.json"
    previous_mixer = mixer_path.read_bytes() if mixer_path.exists() else None
    previous_config = (config_root / "deck.json").read_bytes()
    previous_secret = (config_root / "secrets.json").read_bytes()
    password = json.loads(previous_secret)["obs_password"]
    original_default = pulse("info", structured=True).get("default_source_name")
    module = pulse("load-module", "module-null-source", "source_name=obsgod_fixture_mic")
    max_heartbeat_ms = 0
    try:
        async with websockets.connect("ws://127.0.0.1:4457", open_timeout=5, max_size=2 * 1024 * 1024) as socket:
            hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
            identify = {"rpcVersion": 1, "eventSubscriptions": 0}
            authentication = hello["d"].get("authentication")
            if authentication:
                secret = base64.b64encode(hashlib.sha256((password + authentication["salt"]).encode()).digest()).decode()
                identify["authentication"] = base64.b64encode(hashlib.sha256((secret + authentication["challenge"]).encode()).digest()).decode()
            await socket.send(json.dumps({"op": 1, "d": identify}))
            assert json.loads(await asyncio.wait_for(socket.recv(), 5))["op"] == 2, "Native mixer authentication failed"
            counter = 0

            async def request(kind, data=None):
                nonlocal counter
                counter += 1
                identifier = str(counter)
                await socket.send(json.dumps({"op": 6, "d": {"requestType": kind, "requestId": identifier, "requestData": data or {}}}))
                while True:
                    message = json.loads(await asyncio.wait_for(socket.recv(), 5))
                    if message.get("op") == 7 and message.get("d", {}).get("requestId") == identifier:
                        response = message["d"]
                        assert response["requestStatus"]["result"], "Native OBS mixer request failed"
                        return response.get("responseData", {})

            async def input_state(name):
                muted = await request("GetInputMute", {"inputName": name})
                gain = await request("GetInputVolume", {"inputName": name})
                return muted["inputMuted"], gain["inputVolumeMul"]

            async def output_state():
                return [(await request(kind))["outputActive"] for kind in ("GetStreamStatus", "GetRecordStatus", "GetReplayBufferStatus")]

            async def wait_muted(timeout=4):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if (await input_state(MIC))[0]:
                        return
                    await asyncio.sleep(.05)
                raise AssertionError("The microphone did not become physically muted in real OBS")

            initial_output = await output_state()
            assert any(initial_output), "An explicitly started fixture output is required"
            previous_game = await input_state(GAME)
            try:
                inventory = (await cli({"action": "devices"}))["mixer"]
                assert any(item["id"] == "obsgod_fixture_mic" and item["available"] for item in inventory["devices"]), "The real synthetic input was not discovered"
                await cli({"action": "configure", "preferences": {"microphone_enabled": True, "microphone_device": "obsgod_fixture_mic", "microphone_muted": True, "microphone_gain_percent": 65, "game_gain_percent": 75, "push_to_talk": False}})
                mic_state = await input_state(MIC)
                # Native OBS stores source gain as float32 (0.65 becomes
                # 0.6499999761581421). Keep mute strict; compare linear gain.
                assert mic_state[0] is True and abs(mic_state[1] - .65) <= 1e-6, "Explicit microphone gain/mute was not applied"
                game_state = await input_state(GAME)
                assert game_state[0] == previous_game[0] and abs(game_state[1] - .75) < .001, "Game gain changed game mute"
                await cli({"action": "configure", "preferences": {"microphone_muted": False}})
                mic_state = await input_state(MIC)
                assert mic_state[0] is False and abs(mic_state[1] - .65) <= 1e-6, "Explicit continuous microphone unmute failed"
                await cli({"action": "talk-cancel"})
                mic_state = await input_state(MIC)
                assert mic_state[0] is False and abs(mic_state[1] - .65) <= 1e-6, "Closing the panel muted a continuous microphone without a talk lease"
                await cli({"action": "configure", "preferences": {"push_to_talk": True, "microphone_muted": True}})
                await cli({"action": "configure", "preferences": {"microphone_muted": False}})
                mic_state = await input_state(MIC)
                assert mic_state[0] is True and abs(mic_state[1] - .65) <= 1e-6, "Arming hold-to-talk left the actual input hot"
                first = await cli({"action": "talk-start"})
                assert "talk_expires_at" in first, "Acquire omitted the backend's absolute deadline"
                token = first["talk_token"]
                assert (await input_state(MIC))[0] is False, "Hold-to-talk press did not unmute"
                for _ in range(3):
                    await asyncio.sleep(.25)
                    started = time.monotonic()
                    renewal = await cli({"action": "talk-start", "token": token})
                    latency = (time.monotonic() - started) * 1000
                    max_heartbeat_ms = max(max_heartbeat_ms, latency)
                    assert renewal["lease_ms"] == 1200 and "talk_expires_at" in renewal, "Heartbeat lost its absolute bounded deadline"
                    assert latency < 900, "Heartbeat performed unexpectedly slow work"
                    assert (await input_state(MIC))[0] is False, "Valid heartbeat did not preserve talking"
                await asyncio.sleep(1.4)
                await wait_muted()
                assert (await cli({"action": "status"}))["mixer"]["talking"] is False, "Expired lease still reported talking"
                second = await cli({"action": "talk-start"})
                await cli({"action": "talk-release", "token": second["talk_token"]})
                assert (await input_state(MIC))[0] is True, "Explicit release did not confirm mute"
                third = await cli({"action": "talk-start"})
                assert third["talk_token"] != second["talk_token"], "Replacement press reused its old capability"
                await cli({"action": "talk-cancel"})
                assert (await input_state(MIC))[0] is True, "Panel teardown cancellation did not mute its owned lease"
                # Run a normal unmuted microphone while its exact selected source
                # disappears. Recovery must mute/latch without choosing a default.
                await cli({"action": "configure", "preferences": {"push_to_talk": False, "microphone_muted": False}})
                pulse("unload-module", module)
                module = None
                await wait_muted(timeout=12)
                current = await cli({"action": "status"})
                snapshot = current["mixer"]
                assert snapshot["preferences"]["microphone_muted"] is True and snapshot["preferences"]["microphone_device"] == "obsgod_fixture_mic", "Missing input did not preserve selected source and saved mute"
                assert snapshot["microphone"]["available"] is False, "Missing input was presented available"
                assert await output_state() == initial_output, "Mixer/device loss changed broadcast, recording or replay state"
                assert (config_root / "deck.json").read_bytes() == previous_config, "Mixer changed legacy credential-bound settings"
                assert (config_root / "secrets.json").read_bytes() == previous_secret, "Mixer changed credentials"
            finally:
                # Leave the pre-existing output and source gain/mute intact for
                # the following audio-route/encoded-tone qualification.
                await cli({"action": "configure", "preferences": {"microphone_enabled": False, "microphone_muted": True, "push_to_talk": False, "game_gain_percent": previous_game[1] * 100}})
                await request("SetInputMute", {"inputName": GAME, "inputMuted": previous_game[0]})
                if previous_mixer is None:
                    mixer_path.unlink(missing_ok=True)
                else:
                    mixer_path.write_bytes(previous_mixer)
                    mixer_path.chmod(0o600)
    finally:
        if module is not None:
            pulse("unload-module", module)
        if original_default:
            available = pulse("list", "sources", structured=True)
            if any(item["name"] == original_default for item in available):
                pulse("set-default-source", original_default)
    return {"status": "passed", "platform": "synthetic Linux real OBS/PulseAudio", "actual_mute_gain_verified": True, "continuous_mic_preserved_on_panel_close": True,
            "hold_to_talk_acquire_renew_release_cancel_expiry": "passed", "max_heartbeat_ms": round(max_heartbeat_ms, 2), "selected_input_loss_fail_muted": True,
            "legacy_credentials_unchanged": True, "output_state_preserved": True, "steam_deck_lcd_oled_headset_hardware": "unrun", "control_loss_physical_mute": "cannot-confirm-without-control"}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(asyncio.run(run()), sort_keys=True))


if __name__ == "__main__":
    main()
