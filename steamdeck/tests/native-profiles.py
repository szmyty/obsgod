#!/usr/bin/env python3
"""Actual output-profile proof in native-obs-smoke's disposable Linux fixture.

This tests synthetic moving/audible capture and software encoding. It supplies
no Steam Deck, Flatpak, controller, VAAPI, provider or battery qualification.
"""
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


BINARY = Path("/src/dist/obsgod")
OUTPUT = Path("/work/output")
SENSITIVE = set()


def command(name, payload=None, flags=(), allow_unknown=False):
    process = subprocess.run([str(BINARY), "deck", name, *flags],
                             input=None if payload is None else json.dumps(payload).encode(),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=70)
    try:
        result = json.loads(process.stdout)
    except (ValueError, UnicodeError):
        raise AssertionError("Native profile command returned invalid JSON") from None
    encoded = json.dumps(result)
    assert not any(secret and secret in encoded for secret in SENSITIVE), "Credential reached profile result"
    if not allow_unknown:
        assert process.returncode == 0 and result.get("ok") is True, "Native profile action failed: " + name + ": " + result.get("message", "unknown")
    assert not result.get("stream", {}).get("active", False), "A profile/local output action started broadcasting"
    return result


def profiles(action, **payload):
    return command("stream-profiles", {"action": action, **payload})


def confirmed_idle():
    status = command("status")
    assert status.get("output_known") is True, "Profile fixture requires confirmed output state"
    assert not status.get("recording") and not status["media"]["replay_active"], "Profile fixture requires idle local output"
    return status


def wait_ready():
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        snapshot = command("status", allow_unknown=True)
        if snapshot.get("connected") and snapshot.get("output_known"):
            return snapshot
        time.sleep(0.2)
    raise AssertionError("Restored profile OBS did not become ready")


async def video_settings(password):
    import websockets
    async with websockets.connect("ws://127.0.0.1:4457", open_timeout=5, max_size=2 * 1024 * 1024) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
        identify = {"rpcVersion": 1, "eventSubscriptions": 0}
        authentication = hello["d"].get("authentication")
        if authentication:
            secret = base64.b64encode(hashlib.sha256((password + authentication["salt"]).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(hashlib.sha256((secret + authentication["challenge"]).encode()).digest()).decode()
        await socket.send(json.dumps({"op": 1, "d": identify}))
        identified = json.loads(await asyncio.wait_for(socket.recv(), 5))
        assert identified.get("op") == 2, "Profile fixture control authentication failed"
        request = {"op": 6, "d": {"requestType": "GetVideoSettings", "requestId": "native-profile-video"}}
        await socket.send(json.dumps(request))
        while True:
            response = json.loads(await asyncio.wait_for(socket.recv(), 5))
            if response.get("op") == 7 and response.get("d", {}).get("requestId") == "native-profile-video":
                value = response["d"]
                assert value["requestStatus"]["result"], "Actual OBS GetVideoSettings failed"
                return value["responseData"]


def run():
    assert Path("/.dockerenv").exists() and Path.home() == Path("/work/home"), "Run only inside the disposable native fixture"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obsgod"
    original = json.loads((root / "deck.json").read_text())
    initial_secrets = json.loads((root / "secrets.json").read_text())
    SENSITIVE.update(initial_secrets.get(key, "") for key in ["stream_key", "obs_password"])
    library_path = root / "stream-profiles.json"
    library = library_path.read_bytes() if library_path.exists() else None
    spec = importlib.util.spec_from_file_location("native_media_fixture", Path(__file__).with_name("native-media.py"))
    media = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(media)
    proof = {"platform": "synthetic Linux OBS with x264", "real_steam_deck": "unrun", "checks": []}
    confirmed_idle()
    try:
        for name, preset, width, height, fps, bound in [
            ("native-small", "small-540p30", 960, 540, 30, False),
            ("native-smooth", "smooth-720p60", 1280, 720, 60, True),
        ]:
            command("restart")
            saved = profiles("save", name=name, preset=preset, overrides={"encoder": "x264"})
            document = profiles("export", name=name)["document"]
            portable = json.dumps(document, sort_keys=True)
            assert document["version"] == 1 and document["profile"]["fps"] == fps, "Portable profile schema mismatched"
            assert not any(secret and secret in portable for secret in SENSITIVE), "Portable export leaked a credential"
            assert not any(key in portable for key in ["server", "stream_key", "obs_password", "idle_media", "/work/"]), "Portable export included private/local values"
            profiles("import", name=name + "-copy", document=document)
            profiles("validate", name=name + "-copy")
            if bound:
                profiles("bind-game", name=name, game_id="424242")
                # Explicit local output must select the verified fixture game's
                # profile before launching cold OBS, never from a watcher.
            else:
                profiles("apply", name=name + "-copy")
            command("media", {"action": "record-start"})
            observed = asyncio.run(video_settings(initial_secrets["obs_password"]))
            assert observed["baseWidth"] == 1280 and observed["baseHeight"] == 720, "Output preferences changed the scene canvas"
            assert observed["outputWidth"] == width and observed["outputHeight"] == height, "Actual OBS output dimensions did not follow the profile"
            assert observed["fpsNumerator"] / observed["fpsDenominator"] == fps, "Actual OBS frame rate did not follow the profile"
            time.sleep(4)
            stopped = command("media", {"action": "record-stop"})
            clip_path = stopped["recording_path"]
            probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", clip_path],
                                              check=True, capture_output=True, timeout=10).stdout)
            video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
            assert video["width"] == width and video["height"] == height, "Encoded file dimensions did not follow the profile"
            measurement = media.check_output(clip_path, name)
            confirmed_idle()
            after_secrets = json.loads((root / "secrets.json").read_text())
            assert all(after_secrets[key] == initial_secrets[key] for key in ["stream_key", "obs_password"]), "Profile operation changed credentials"
            proof["checks"].append({"preset": preset, "selection": "verified-game-before-explicit-cold-recording" if bound else "explicit-saved-profile-apply",
                                     "obs_video": observed, "encoded_width": width, "encoded_height": height, "fps": fps,
                                     "portable_export_private": True, "picture_audio": measurement, "implicit_broadcast": False})
            if bound:
                profiles("unbind-game", game_id="424242")
        proof["status"] = "passed"
    finally:
        # Preserve all finalized files. Only explicit owned local outputs are
        # cleaned up; these actions never start or stop a network broadcast.
        for action in ["record-stop", "replay-stop"]:
            try:
                command("media", {"action": action})
            except (AssertionError, subprocess.SubprocessError):
                pass
        confirmed_idle()
        command("restart")
        if library is None:
            library_path.unlink(missing_ok=True)
        else:
            library_path.write_bytes(library)
        command("configure", original)
        command("open-obs")
        wait_ready()
        confirmed_idle()
    proof["original_settings_restored"] = True
    proof["credentials_unchanged"] = True
    encoded = json.dumps(proof, sort_keys=True)
    assert not any(secret and secret in encoded for secret in SENSITIVE), "Credential reached native profile proof"
    (OUTPUT / "profile-qualification.json").write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    run()
