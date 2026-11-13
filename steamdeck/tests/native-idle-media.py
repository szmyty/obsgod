#!/usr/bin/env python3
"""Actual OBS local idle media; only disposable native-game fixture data.

Run after native-game-obs-smoke.sh's game checks while its session is alive.
Fixture media is generated here, so no third-party creative rights are assumed.
This tests Linux OBS, not SteamOS/Flatpak/Gamescope/controller hardware.
"""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location("game_fixture", "/src/steamdeck/tests/native-game-obs.py")
game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game)
OUT = game.OUT
IMAGE = "OBSGod Idle Image"
VIDEO = "OBSGod Idle Video"


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", *args], check=True)


def validate_received(label, phases):
    source = OUT / (label + ".flv")
    proof = {}
    for name, phase in phases.items():
        at = (phase["at_ms"] + phase["end_ms"]) / 2000
        rgb = OUT / (name + "-media-viewer.rgb")
        ffmpeg("-ss", str(at), "-i", str(source), "-frames:v", "1", "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "rgb24", "-y", str(rgb))
        pixels = game.rgb_kind(rgb.read_bytes(), phase["expected"])
        audio = OUT / (name + "-media-audio.wav")
        ffmpeg("-ss", str(at), "-i", str(source), "-t", "1", "-vn", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", "-y", str(audio))
        measured = json.loads(subprocess.check_output(["python3", "/src/steamdeck/tests/native-audio.py", "measure", str(audio), "440"], text=True))
        # The video deliberately contains 880Hz audio. A passing 440Hz ratio
        # verifies this soundtrack is not mixed into selected system audio.
        entry = {"pixels": pixels, "audio": measured, "at_seconds": at}
        if name == "idle-video":
            hashes = OUT / "idle-video-moving.md5"
            ffmpeg("-ss", str(phase["at_ms"] / 1000 + .5), "-i", str(source), "-t", "2", "-an", "-vf", "fps=2", "-f", "framemd5", "-y", str(hashes))
            values = [line.split(",")[-1].strip() for line in hashes.read_text().splitlines() if line and not line.startswith("#")]
            assert len(values) >= 3 and len(set(values)) >= 3, "Idle video did not produce moving encoded frames"
            entry["distinct_encoded_frames"] = len(set(values))
        proof[name] = entry
    return proof


async def observe_phase(obs, expected, label, enabled_media, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = await obs.request("GetStreamStatus")
        assert output["outputActive"], "Idle media transition stopped explicit output"
        scene = (await obs.request("GetCurrentProgramScene"))["sceneName"]
        if scene == game.IDLE:
            try:
                await game.screenshot(obs, label + "-source", game.IDLE, expected)
                items = (await obs.request("GetSceneItemList", {"sceneName": game.IDLE}))["sceneItems"]
                actual = {item["sourceName"] for item in items if item["sceneItemEnabled"]}
                allowed = {game.AUDIO, enabled_media} if enabled_media else {game.AUDIO}
                assert actual <= allowed and game.AUDIO in actual, ("unsafe idle scene", sorted(actual))
                if enabled_media:
                    assert enabled_media in actual
                start_ms = output["outputDuration"]
                await asyncio.sleep(3)
                after = await obs.request("GetStreamStatus")
                assert after["outputActive"] and after["outputBytes"] > output["outputBytes"] and after["outputDuration"] > start_ms
                return {"at_ms": start_ms, "end_ms": after["outputDuration"], "expected": expected, "enabled_sources": sorted(actual)}
            except AssertionError:
                pass
        await asyncio.sleep(.2)
    raise AssertionError("Idle media scene/pixels failed to settle: " + label)


async def main():
    # Color PNG verifies actual imported image pixels; moving video has an
    # intentional decoy soundtrack that must remain muted in viewer output.
    image = OUT / "fixture-owned-image.png"
    video = OUT / "fixture-owned-video.mp4"
    ffmpeg("-f", "lavfi", "-i", "color=c=red:s=1280x720", "-frames:v", "1", "-threads", "1", "-y", str(image))
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(video))
    proof = {"scope": "Real OBS native local media and local RTMP viewer audio/picture; synthetic Linux session, not Steam Deck", "cases": {}, "state": "running"}
    sink = obs = None
    try:
        for style, source, expected, name in (("image", image, "red", IMAGE), ("video", video, "moving", VIDEO)):
            label = "idle-" + style
            result = await game.cli("set-idle-media", {"idle_style": style, "source": str(source), "rights_acknowledged": True, "attribution": "Generated native test fixture"})
            assert result["settings"]["idle_style"] == style
            stored = result["settings"]["idle_media"]
            status = await game.cli("status")
            assert status["output_known"] and not status["stream"]["active"] and not status["recording"], "Saving media started output"
            sink = await game.receiver(label)
            await game.cli("start")
            obs = await game.OBS.connect()
            phases = {label: await observe_phase(obs, expected, label, name)}
            if style == "video":
                assert (await obs.request("GetInputMute", {"inputName": VIDEO}))["inputMuted"], "Imported video soundtrack is not muted"
                settings = (await obs.request("GetInputSettings", {"inputName": VIDEO}))["inputSettings"]
                assert settings["is_local_file"] and settings["looping"], "Video did not use bounded local loop playback"
                owned = Path.home() / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/obsgod-media" / stored
                assert owned.is_file() and str(owned) == settings["local_file"]
                owned.unlink()
                phases["idle-missing-media-black"] = await observe_phase(obs, "black", "idle-missing-media-black", None)
                assert phases["idle-missing-media-black"]["at_ms"] > phases[label]["end_ms"], "Output clock restarted at missing-media fallback"
            await game.cli("stop")
            await asyncio.wait_for(sink.wait(), 10)
            sink = None
            await asyncio.sleep(1.2)
            assert not (await obs.request("GetStreamStatus"))["outputActive"]
            starts = [event for event in obs.events if event["event"] == "StreamStateChanged" and event["state"] == "OBS_WEBSOCKET_OUTPUT_STARTED"]
            # OBS event connection is attached after Start; stop evidence and
            # monotonic duration/bytes cover unchanged output during transitions.
            assert len(starts) == 0, "Media transition unexpectedly restarted output"
            proof["cases"][label] = {"phases": phases, "decoded_viewer": validate_received(label, phases)}
            await obs.close()
            obs = None
            await game.cli("restart")
        # Leave a portable safe style for the following native M3 tool checks.
        await game.cli("set-idle-media", {"idle_style": "black"})
        proof["state"] = "passed"
        proof["binary_sha256"] = hashlib.sha256(Path("/src/dist/obsgod").read_bytes()).hexdigest()
        (OUT / "idle-media-qualification.json").write_text(json.dumps(proof, indent=2) + "\n")
        print("PASS native idle PNG and moving muted MP4; decoded local RTMP picture/440Hz audio; missing asset→black without restarting output; explicit Stop preserved")
    finally:
        if obs:
            await obs.close()
        await game.stop_child(sink)


if __name__ == "__main__":
    asyncio.run(main())
