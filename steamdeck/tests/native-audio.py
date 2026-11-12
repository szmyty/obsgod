#!/usr/bin/env python3
"""Measure fixture PCM and inspect real OBS audio settings without exporting secrets."""
import argparse
import array
import asyncio
import base64
import hashlib
import json
import math
from pathlib import Path
import sys
import wave


INPUT = "OBSGod Game Audio"


def measurements(samples, rate, frequency):
    if not samples or rate <= 0:
        raise ValueError("Audio probe has no decoded samples")
    peak = max(abs(value) for value in samples) / 32768.0
    rms = math.sqrt(sum((value / 32768.0) ** 2 for value in samples) / len(samples))
    # Analyze one second to bound runtime while retaining an integral number of
    # cycles for the fixture's 440/880Hz tones. Both rates survive AAC encoding.
    values = samples[:rate]

    def power(hz):
        coefficient = 2 * math.cos(2 * math.pi * hz / rate)
        previous = before_previous = 0.0
        for value in values:
            current = value / 32768.0 + coefficient * previous - before_previous
            before_previous, previous = previous, current
        return max(0.0, previous ** 2 + before_previous ** 2 - coefficient * previous * before_previous) / len(values) ** 2

    expected = power(frequency)
    other_frequency = 880 if frequency == 440 else 440
    other = power(other_frequency)
    return {
        "samples": len(samples), "rate": rate,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "peak_dbfs": 20 * math.log10(peak) if peak else None,
        "expected_hz": frequency, "other_hz": other_frequency,
        "expected_power": expected, "other_power": other,
        "audible": rms > 0.01 and peak > 0.0178,  # RMS >-40dBFS, peak >-35dBFS.
        "expected_tone": expected > 0.00001 and expected > other * 16,
    }


def check_wave(path, frequency, silent=False):
    with wave.open(str(path)) as audio:
        if audio.getsampwidth() != 2 or audio.getnchannels() != 1:
            raise ValueError("Decode the fixture as mono signed16 PCM")
        values = array.array("h", audio.readframes(audio.getnframes()))
        if sys.byteorder != "little":
            values.byteswap()
        result = measurements(values, audio.getframerate(), frequency)
    if silent:
        assert not result["audible"] and not result["expected_tone"], "Digital-silence negative control was accepted as audible"
        result["status"] = "silence-rejected-as-expected"
    else:
        assert result["audible"], "Actual encoded output is silent or too quiet for the known fixture tone"
        assert result["expected_tone"], "Actual encoded output captured the wrong sink or mixed the decoy tone"
        result["status"] = "passed"
    return result


async def obs_snapshot(expected, seed=False):
    # This helper runs only in the disposable native fixture. The generated
    # password is read privately and never reaches argv, JSON output or logs.
    import websockets
    password = json.loads((Path.home() / ".config/obsgod/secrets.json").read_text())["obs_password"]
    async with websockets.connect("ws://127.0.0.1:4457", open_timeout=5, max_size=2 * 1024 * 1024) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
        identify = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = hello["d"].get("authentication")
        if auth:
            secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        await socket.send(json.dumps({"op": 1, "d": identify}))
        identified = json.loads(await asyncio.wait_for(socket.recv(), 5))
        assert identified["op"] == 2, "Fixture OBS authentication did not complete"
        counter = 0

        async def request(kind, data=None):
            nonlocal counter
            counter += 1
            identifier = str(counter)
            await socket.send(json.dumps({"op": 6, "d": {"requestType": kind, "requestId": identifier, "requestData": data or {"inputName": INPUT}}}))
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(), 5))
                if message.get("op") == 7 and message.get("d", {}).get("requestId") == identifier:
                    response = message["d"]
                    assert response["requestStatus"]["result"], kind + " failed in native OBS"
                    return response.get("responseData", {})

        if seed:
            await request("SetInputMute", {"inputName": INPUT, "inputMuted": True})
            await request("SetInputVolume", {"inputName": INPUT, "inputVolumeMul": 0.0})
            await request("SetInputAudioTracks", {"inputName": INPUT, "inputAudioTracks": {str(track): False for track in range(1, 7)}})
            await request("SetInputAudioMonitorType", {"inputName": INPUT, "monitorType": "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT"})
            return {"status": "seeded-stale-audio", "input": INPUT}

        settings = await request("GetInputSettings")
        mute = await request("GetInputMute")
        volume = await request("GetInputVolume")
        tracks = await request("GetInputAudioTracks")
        monitor = await request("GetInputAudioMonitorType")
        actual_device = settings["inputSettings"].get("device_id")
        assert actual_device == expected, "OBS did not select the expected real PulseAudio monitor"
        assert mute["inputMuted"] is False, "OBS audio source is still muted"
        assert abs(volume["inputVolumeMul"] - 1.0) < 0.0001, "OBS audio source did not restore normal volume"
        actual_tracks = tracks["inputAudioTracks"]
        assert actual_tracks.get("1") is True and not any(value for track, value in actual_tracks.items() if track != "1"), "OBS audio did not select only output track1"
        assert monitor["monitorType"] == "OBS_MONITORING_TYPE_NONE", "OBS source monitoring could create a feedback route"
        return {"status": "passed", "input": INPUT, "device_id": actual_device,
                "muted": mute["inputMuted"], "volume_mul": volume["inputVolumeMul"],
                "tracks": actual_tracks, "monitor_type": monitor["monitorType"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    measure = commands.add_parser("measure")
    measure.add_argument("wave", type=Path)
    measure.add_argument("frequency", type=int, choices=[440, 880])
    measure.add_argument("--silent", action="store_true")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("monitor")
    commands.add_parser("seed")
    args = parser.parse_args()
    if args.command == "measure":
        result = check_wave(args.wave, args.frequency, args.silent)
    else:
        result = asyncio.run(obs_snapshot(args.monitor if args.command == "snapshot" else None, args.command == "seed"))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
