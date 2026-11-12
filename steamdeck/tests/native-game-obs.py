#!/usr/bin/env python3
"""Real OBS output/scene integration with synthetic app-scoped PipeWire media."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import websockets


LIVE = "OBSGod Live"
GAME = "OBSGod Game"
IDLE = "OBSGod Idle"
DISPLAY = "OBSGod Gamescope"
GAME_INPUT = "OBSGod Game Window"
AUDIO = "OBSGod Game Audio"
TEXT = "OBSGod Idle Message"
SENTINEL = "Legacy private display sentinel"
OUT = Path("/work/output")


class OBSNotReady(AssertionError):
    """OBS explicitly rejected a request before its frontend was ready."""


async def cli(action, settings=None, timeout=100):
    process = await asyncio.create_subprocess_exec(
        "/src/dist/obsgod", "deck", action,
        stdin=asyncio.subprocess.PIPE if settings is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        raw, _ = await asyncio.wait_for(process.communicate(
            json.dumps(settings).encode() if settings is not None else None), timeout)
    except BaseException:
        if process.returncode is None:
            process.send_signal(signal.SIGINT)
            try:
                await asyncio.wait_for(process.communicate(), 8)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
        raise
    result = json.loads(raw)
    assert process.returncode == 0 and result.get("ok"), (action, result)
    return result


class OBS:
    def __init__(self, socket):
        self.socket = socket
        self.serial = 0
        self.events = []

    @classmethod
    async def connect(cls):
        password = json.loads((Path.home() / ".config/obsgod/secrets.json").read_text())["obs_password"]
        last = None
        for _ in range(100):
            try:
                socket = await websockets.connect("ws://127.0.0.1:4457", open_timeout=.5, max_size=2*1024*1024)
                hello = json.loads(await asyncio.wait_for(socket.recv(), 3))
                identify = {"rpcVersion": 1, "eventSubscriptions": 64}
                auth = hello["d"].get("authentication")
                if auth:
                    secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
                    identify["authentication"] = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
                await socket.send(json.dumps({"op": 1, "d": identify}))
                assert json.loads(await asyncio.wait_for(socket.recv(), 3))["op"] == 2
                return cls(socket)
            except (OSError, TimeoutError, websockets.ConnectionClosed) as error:
                last = type(error).__name__
                await asyncio.sleep(.1)
        raise AssertionError("Native managed OBS control did not become ready: " + str(last))

    async def request(self, kind, data=None):
        self.serial += 1
        identifier = str(self.serial)
        await self.socket.send(json.dumps({"op": 6, "d": {"requestType": kind, "requestId": identifier, "requestData": data or {}}}))
        while True:
            message = json.loads(await asyncio.wait_for(self.socket.recv(), 8))
            if message.get("op") == 5:
                event = message["d"]
                if event.get("eventType") in ("StreamStateChanged", "RecordStateChanged"):
                    facts = event.get("eventData", {})
                    self.events.append({"event": event["eventType"], "state": facts.get("outputState"), "active": facts.get("outputActive")})
            elif message.get("op") == 7 and message["d"].get("requestId") == identifier:
                response = message["d"]
                if not response["requestStatus"]["result"]:
                    if response["requestStatus"].get("code") == 207:
                        raise OBSNotReady(kind, 207)
                    raise AssertionError((kind, response["requestStatus"].get("code")))
                return response.get("responseData", {})

    async def wait_frontend(self):
        # Authentication can precede initial scene creation. Retry only OBS's
        # explicit NotReady response, with one deadline for this bootstrap step;
        # authentication, transport and all other protocol failures remain hard.
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, "Native OBS frontend readiness exceeded 10 seconds"
            try:
                return await asyncio.wait_for(self.request("GetSceneCollectionList"), remaining)
            except OBSNotReady:
                remaining = deadline - time.monotonic()
                assert remaining > 0, "Native OBS frontend readiness exceeded 10 seconds"
                await asyncio.sleep(min(.1, remaining))

    async def close(self):
        await self.socket.close()


def rgb_kind(data, expected):
    assert len(data) == 160*90*3, len(data)
    means = [sum(data[c::3])/(160*90) for c in range(3)]
    if expected == "red":
        assert means[0] > 150 and means[2] < 55 and means[1] < 55, means
    elif expected == "green":
        assert means[1] > 150 and means[2] < 55 and means[0] < 55, means
    elif expected == "placeholder":
        assert max(means)-min(means) < 8 and max(data) > 100 and min(data) < 10, means
    elif expected == "black":
        assert max(data) < 12, (means, max(data))
    return {"channel_means": means, "expected": expected}


async def screenshot(obs, label, scene, expected):
    shot = await obs.request("GetSourceScreenshot", {"sourceName": scene, "imageFormat": "png", "imageWidth": 160, "imageHeight": 90})
    prefix = "data:image/png;base64,"
    assert shot["imageData"].startswith(prefix)
    png = OUT / (label + ".png")
    png.write_bytes(base64.b64decode(shot["imageData"][len(prefix):]))
    rgb = OUT / (label + ".rgb")
    process = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-i", str(png), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-y", str(rgb))
    assert await process.wait() == 0
    return rgb_kind(rgb.read_bytes(), expected)


async def seed_old_items(obs):
    collections = await obs.wait_frontend()
    if collections["currentSceneCollectionName"] != "OBSGod":
        if "OBSGod" in collections["sceneCollections"]:
            await obs.request("SetCurrentSceneCollection", {"sceneCollectionName": "OBSGod"})
        else:
            await obs.request("CreateSceneCollection", {"sceneCollectionName": "OBSGod"})
        await obs.wait_frontend()
    names = {x["sceneName"] for x in (await obs.request("GetSceneList"))["scenes"]}
    for scene in (IDLE, GAME, LIVE):
        if scene not in names:
            await obs.request("CreateScene", {"sceneName": scene})
    kinds = (await obs.request("GetInputKindList"))["inputKinds"]
    color = next(x for x in kinds if x.startswith("color_source"))
    await obs.request("CreateInput", {"sceneName": GAME, "inputName": SENTINEL, "inputKind": color,
        "inputSettings": {"color": 0xFFFF0000, "width": 1280, "height": 720}, "sceneItemEnabled": True})
    await obs.request("CreateSceneItem", {"sceneName": IDLE, "sourceName": SENTINEL, "sceneItemEnabled": True})
    await obs.request("CreateInput", {"sceneName": LIVE, "inputName": DISPLAY, "inputKind": "gstreamer-source",
        "inputSettings": {"pipeline": "pipewiresrc target-object=gamescope ! videoconvert ! video.", "stop_on_hide": True, "clear_on_end": True}, "sceneItemEnabled": False})
    for scene in (IDLE, GAME):
        await obs.request("CreateSceneItem", {"sceneName": scene, "sourceName": DISPLAY, "sceneItemEnabled": True})


async def verify_whitelist(obs, scene):
    items = (await obs.request("GetSceneItemList", {"sceneName": scene}))["sceneItems"]
    allowed = {AUDIO, TEXT} if scene == IDLE else {AUDIO, GAME_INPUT}
    for item in items:
        assert not item["sceneItemEnabled"] or item["sourceName"] in allowed, (scene, item["sourceName"])
        if item["sourceName"] in (DISPLAY, SENTINEL):
            assert not item["sceneItemEnabled"], (scene, "legacy display item remained visible")
    assert any(x["sourceName"] == AUDIO and x["sceneItemEnabled"] for x in items), (scene, "audio missing")
    return [{"source": x["sourceName"], "enabled": x["sceneItemEnabled"]} for x in items]


async def wait_scene(obs, wanted, expected, label, recording=False, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        current = await obs.request("GetCurrentProgramScene")
        output = await obs.request("GetRecordStatus" if recording else "GetStreamStatus")
        assert output["outputActive"], (label, "output stopped during a scene transition")
        if current["sceneName"] == wanted:
            try:
                pixels = await screenshot(obs, label, wanted, expected)
                return {"scene": wanted, "output_bytes": output["outputBytes"], "at_ms": output["outputDuration"], "pixels": pixels,
                        "items": await verify_whitelist(obs, wanted)}
            except AssertionError as error:
                last = str(error)
        await asyncio.sleep(.25)
    raise AssertionError((label, "scene/picture did not become ready", last))


async def tagged_game(appid):
    return await asyncio.create_subprocess_exec("sleep", "1000", env=dict(os.environ, SteamAppId=str(appid)))


async def stop_child(process):
    if process is not None and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


async def receiver(label):
    log = (OUT / (label+"-receiver.log")).open("wb")
    process = await asyncio.create_subprocess_exec("ffmpeg", "-hide_banner", "-listen", "1", "-i",
        "rtmp://127.0.0.1:1935/live/fixture-key", "-c", "copy", "-y", str(OUT/(label+".flv")), stdout=log, stderr=log)
    log.close()
    await asyncio.sleep(.3)
    assert process.returncode is None, "Local RTMP receiver exited early"
    return process


async def hold_phase(obs, wanted, expected, label):
    phase = await wait_scene(obs, wanted, expected, label)
    await asyncio.sleep(3)
    after = await obs.request("GetStreamStatus")
    assert after["outputActive"] and after["outputBytes"] > phase["output_bytes"]
    assert after["outputDuration"] > phase["at_ms"]
    phase["end_ms"] = after["outputDuration"]
    return phase


async def main():
    OUT.mkdir(exist_ok=True)
    settings = {"version": 1, "server": "rtmp://127.0.0.1:1935/live", "stream_key": "fixture-key", "bitrate": 3000,
        "fps": 30, "encoder": "x264", "microphone": False, "capture_mode": "game", "idle_style": "placeholder", "idle_text": "Between games fixture"}
    (OUT/"configure.json").write_text(json.dumps(await cli("configure", settings)))
    producer = game = sink = obs = None
    proof = {"scope": "Real OBS/GStreamer/PipeWire/PulseAudio/software encoding and local RTMP with synthetic app identities/producer; not actual Gamescope/SteamOS/Flatpak/Kick", "phases": {}}
    try:
        producer_log = (OUT/"game-producer.log").open("wb")
        producer = await asyncio.create_subprocess_exec("/work/capture-fixture", "gamescope", "good", stdout=producer_log, stderr=producer_log)
        producer_log.close()
        game = await tagged_game(4242)
        await asyncio.sleep(.4)
        await cli("open-obs")
        obs = await OBS.connect()
        await seed_old_items(obs)
        # The local-test parent holds its control lock. Its independent observer
        # must still select idle while that recording is active.
        clip_task = asyncio.create_task(cli("test-recording"))
        for _ in range(100):
            if (await obs.request("GetRecordStatus"))["outputActive"]:
                break
            if clip_task.done():
                await clip_task
                raise AssertionError("Local clip completed without an observed active recording")
            await asyncio.sleep(.1)
        proof["clip_game"] = await wait_scene(obs, GAME, "red", "clip-game", recording=True, timeout=5)
        status = await cli("status")
        assert status["recording"] and status["video"]["watching"], "Local-test watcher did not run while parent held control lock"
        await stop_child(game)
        game = None
        proof["clip_idle"] = await wait_scene(obs, IDLE, "placeholder", "clip-idle", recording=True, timeout=6)
        clip = await clip_task
        (OUT/"local-clip.json").write_text(json.dumps(clip))
        assert not clip["recording"]
        assert not (await obs.request("GetStreamStatus"))["outputActive"], "Local test broadcast unexpectedly"
        game = await tagged_game(4242)
        sink = await receiver("transitions")
        start = await cli("start")
        (OUT/"start.json").write_text(json.dumps(start))
        proof["phases"]["game-a"] = await hold_phase(obs, GAME, "red", "game-a")
        await stop_child(game)
        game = None
        proof["phases"]["between-games"] = await hold_phase(obs, IDLE, "placeholder", "between-games")
        game = await tagged_game(4243)
        proof["phases"]["game-b"] = await hold_phase(obs, GAME, "green", "game-b")
        # An unsupported producer must leave fallback live, never render its
        # blue compositor sentinel, and never restart or stop the output.
        await stop_child(producer)
        producer_log = (OUT/"unsupported-producer.log").open("wb")
        producer = await asyncio.create_subprocess_exec("/work/capture-fixture", "gamescope", "missing", stdout=producer_log, stderr=producer_log)
        producer_log.close()
        proof["phases"]["unsupported-source"] = await hold_phase(obs, IDLE, "placeholder", "unsupported-source")
        (OUT/"stop.json").write_text(json.dumps(await cli("stop")))
        await asyncio.wait_for(sink.wait(), 10)
        sink = None
        assert not (await obs.request("GetStreamStatus"))["outputActive"]
        starts = [x for x in obs.events if x["event"] == "StreamStateChanged" and x["state"] == "OBS_WEBSOCKET_OUTPUT_STARTED"]
        stops = [x for x in obs.events if x["event"] == "StreamStateChanged" and x["state"] == "OBS_WEBSOCKET_OUTPUT_STOPPED"]
        assert len(starts) == len(stops) == 1, obs.events
        proof["first_stream_events"] = obs.events
        await stop_child(game)
        game = await tagged_game(4242)
        await asyncio.sleep(2)
        assert not (await obs.request("GetStreamStatus"))["outputActive"], "A later game launch implicitly restarted output"
        await stop_child(game)
        game = None
        await obs.close()
        obs = None
        await cli("restart")
        settings["idle_style"] = "black"
        settings.pop("stream_key")
        await cli("configure", settings)
        sink = await receiver("black-fallback")
        (OUT/"black-start.json").write_text(json.dumps(await cli("start")))
        obs = await OBS.connect()
        proof["black_fallback"] = await hold_phase(obs, IDLE, "black", "black-fallback")
        status = await cli("status")
        assert status["stream"]["active"] and status["video"]["state"] == "idle" and status["video"]["idle_style"] == "black", status
        await cli("stop")
        await asyncio.wait_for(sink.wait(), 10)
        sink = None
        await asyncio.sleep(1.2)
        status = await cli("status")
        assert not status["stream"]["active"] and not status["recording"] and not status["video"]["watching"], status
        proof["final_status"] = {k: status[k] for k in ("state", "recording", "output_known", "video")}
        await obs.close()
        obs = None
        await cli("restart")
        proof["state"] = "passed"
        (OUT/"game-obs-qualification.json").write_text(json.dumps(proof, indent=2)+"\n")
        print("PASS native OBS game A / fallback / game B / unsupported source / black fallback; explicit local clip and stream lifecycle; observer runs during local control lock; continuous audio still requires decoded-media check")
    finally:
        if obs:
            await obs.close()
        for child in (game, producer, sink):
            await stop_child(child)


if __name__ == "__main__":
    asyncio.run(main())
