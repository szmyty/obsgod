#!/usr/bin/env python3
"""Exercise real audio hotplug recovery in the disposable native OBS fixture.

Run while an explicitly started native-fixture output and its resilience observer
are active. This moves the fixture's tagged game's PulseAudio stream between its
two existing null sinks. It deliberately changes OBS source gain/mute, verifies
recovery preserves them, and restores the route and mixer in finally. No provider
or system-hardware capability is claimed by this synthetic Linux check.
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


def pulse(*args, structured=False):
    command = ["pactl"] + (["--format=json"] if structured else []) + list(args)
    result = subprocess.run(command, check=True, capture_output=True, timeout=3)
    return json.loads(result.stdout) if structured else None


async def run(game_pid):
    if not Path("/.dockerenv").exists() or os.environ.get("OBSGOD_DISPOSABLE_AUDIO_FIXTURE") != "1":
        raise ValueError("Use only the disposable OBS Docker fixture with its explicit audio-test flag")
    import websockets

    streams = pulse("list", "sink-inputs", structured=True)
    game_inputs = [item for item in streams if str(item.get("properties", {}).get("application.process.id")) == str(game_pid)]
    assert len(game_inputs) == 1, "Fixture game audio is ambiguous or absent"
    game_input = game_inputs[0]
    sinks = pulse("list", "sinks", structured=True)
    original = next(item for item in sinks if item["index"] == game_input["sink"])
    alternate = next(item for item in sinks if item["name"] == "obsgod_decoy")
    assert original["name"] == "obsgod_game", "The fixture must begin on its known game sink"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    password = json.loads((root / "obsgod/secrets.json").read_text())["obs_password"]
    async with websockets.connect("ws://127.0.0.1:4457", open_timeout=5, max_size=2 * 1024 * 1024) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
        identify = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = hello["d"].get("authentication")
        if auth:
            secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        await socket.send(json.dumps({"op": 1, "d": identify}))
        identified = json.loads(await asyncio.wait_for(socket.recv(), 5))
        assert identified["op"] == 2, "Fixture OBS authentication failed"
        counter = 0

        async def request(kind, data=None):
            nonlocal counter
            counter += 1
            identifier = str(counter)
            await socket.send(json.dumps({"op": 6, "d": {"requestType": kind, "requestId": identifier, "requestData": data if data is not None else {"inputName": "OBSGod Game Audio"}}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), 5))
                if message.get("op") == 7 and message.get("d", {}).get("requestId") == identifier:
                    response = message["d"]
                    assert response["requestStatus"]["result"], "Native OBS audio test request failed"
                    return response.get("responseData", {})

        async def mixer():
            mute = await request("GetInputMute")
            volume = await request("GetInputVolume")
            tracks = await request("GetInputAudioTracks")
            monitor = await request("GetInputAudioMonitorType")
            return {"mute": mute["inputMuted"], "volume": volume["inputVolumeMul"],
                    "tracks": tracks["inputAudioTracks"], "monitor": monitor["monitorType"]}

        async def wait_route(sink):
            deadline = time.monotonic() + 14
            while time.monotonic() < deadline:
                settings = await request("GetInputSettings")
                if settings["inputSettings"].get("device_id") == sink["monitor_source"]:
                    return
                await asyncio.sleep(0.2)
            raise AssertionError("The real observer did not follow the changed audio route within its bound")

        initial_stream = await request("GetStreamStatus", {})
        initial_record = await request("GetRecordStatus", {})
        initial_replay = await request("GetReplayBufferStatus", {})
        assert initial_stream["outputActive"] or initial_record["outputActive"] or initial_replay["outputActive"], "An explicitly started fixture output is required"
        previous = await mixer()
        try:
            await request("SetInputVolume", {"inputName": "OBSGod Game Audio", "inputVolumeMul": 0.65})
            await request("SetInputMute", {"inputName": "OBSGod Game Audio", "inputMuted": True})
            selected = await mixer()
            pulse("move-sink-input", str(game_input["index"]), alternate["name"])
            await wait_route(alternate)
            actual = await mixer()
            assert actual == selected, "Automatic recovery changed the user's gain/mute/tracks/monitoring policy"
            pulse("move-sink-input", str(game_input["index"]), original["name"])
            await wait_route(original)
            assert await mixer() == selected, "Returning the original device changed mixer policy"
        finally:
            pulse("move-sink-input", str(game_input["index"]), original["name"])
            await request("SetInputVolume", {"inputName": "OBSGod Game Audio", "inputVolumeMul": previous["volume"]})
            await request("SetInputMute", {"inputName": "OBSGod Game Audio", "inputMuted": previous["mute"]})
        final_stream = await request("GetStreamStatus", {})
        final_record = await request("GetRecordStatus", {})
        final_replay = await request("GetReplayBufferStatus", {})
        assert final_stream["outputActive"] == initial_stream["outputActive"], "Audio recovery changed broadcast state"
        assert final_record["outputActive"] == initial_record["outputActive"], "Audio recovery changed recording state"
        assert final_replay["outputActive"] == initial_replay["outputActive"], "Audio recovery changed replay state"
        if initial_stream["outputActive"]:
            assert final_stream["outputBytes"] > initial_stream["outputBytes"], "Streaming output did not advance during route recovery"
        return {"status": "passed", "platform": "synthetic Linux OBS", "route_transitions": 2,
                "mixer_policy_preserved": True, "output_state_preserved": True,
                "real_steam_deck": "unrun"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-pid", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.game_pid)), sort_keys=True))


if __name__ == "__main__":
    main()
