#!/usr/bin/env python3
"""Qualify local recording/replay against actual disposable Linux OBS.

Requires native-obs-smoke.sh's synthetic moving capture and audible fixture.
No real broadcast, Steam Deck, Flatpak, Gamescope, hardware-encoder or controller
claim is supplied by this test. Writes only under the disposable /work tree.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


BINARY = Path("/src/dist/obsgod")
OUTPUT = Path("/work/output")
SENSITIVE = set()


def command(action, **payload):
    result = subprocess.run([str(BINARY), "deck", "media"],
                            input=json.dumps({"action": action, **payload}).encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=70)
    try:
        data = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise AssertionError("Native media command did not return valid JSON") from None
    encoded = json.dumps(data)
    assert not any(secret and secret in encoded for secret in SENSITIVE), "A credential reached media proof"
    assert result.returncode == 0 and data.get("ok") is True, "Native media operation failed: " + action + ": " + data.get("message", "unknown")
    return data


def main_status():
    result = subprocess.run([str(BINARY), "deck", "status"], capture_output=True, timeout=8)
    value = json.loads(result.stdout)
    assert result.returncode == 0 and value.get("output_known") is True, "Native media output became unknown"
    return value


def check_output(path, label):
    path = Path(path)
    assert path.is_file() and path.stat().st_size > 0, "Native media was not finalized"
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            check=True, capture_output=True, timeout=10)
    probe = json.loads(result.stdout)
    assert float(probe["format"]["duration"]) >= 2, "Native media is too short to qualify"
    assert {"video", "audio"}.issubset({stream["codec_type"] for stream in probe["streams"]}), "Native media lacks picture/audio streams"
    hashes = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(path), "-an", "-vf", "fps=2", "-frames:v", "4", "-f", "framemd5", "-"],
                            check=True, capture_output=True, timeout=15).stdout.decode()
    frames = [line.rsplit(",", 1)[-1].strip() for line in hashes.splitlines() if line and not line.startswith("#")]
    assert len(set(frames)) > 1, "Native media video did not move"
    wave = OUTPUT / (label + ".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(path), "-t", "2", "-vn", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", "-y", str(wave)],
                   check=True, capture_output=True, timeout=15)
    spec = importlib.util.spec_from_file_location("native_audio", Path(__file__).with_name("native-audio.py"))
    audio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audio)
    measured = audio.check_wave(wave, 440)
    return {"file": path.name, "bytes": path.stat().st_size,
            "duration_seconds": float(probe["format"]["duration"]),
            "distinct_frames": len(set(frames)), "audio": measured}


def run():
    assert Path("/.dockerenv").exists() and Path.home() == Path("/work/home"), "Run only inside the disposable native fixture"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    secret = json.loads((root / "obsgod/secrets.json").read_text())
    SENSITIVE.update(secret.get(key, "") for key in ["obs_password", "stream_key"])
    initial = main_status()
    assert not initial["stream"]["active"] and not initial["media"]["recording"]["active"] and not initial["media"]["replay_active"], "Media qualification needs confirmed idle OBS"
    original = command("status")["preferences"]
    preferences = dict(original, replay_seconds=15, replay_memory_mb=64)
    proof = {"platform": "synthetic Linux OBS", "real_steam_deck": "unrun", "checks": {}}
    try:
        command("configure", preferences=preferences)
        command("replay-start")
        command("replay-start")  # Idempotent: no duplicate output.
        replay = main_status()
        assert replay["media"]["replay_active"] and not replay["stream"]["active"], "Local replay started a broadcast or did not start"
        command("record-start")
        command("record-start")
        time.sleep(4)
        concurrent = main_status()
        assert concurrent["media"]["recording"]["active"] and concurrent["media"]["replay_active"] and not concurrent["stream"]["active"], "Recording/replay coexistence failed"
        saved = command("replay-save")
        stopped = command("record-stop")
        assert main_status()["media"]["replay_active"], "Stopping recording disabled replay capture"
        proof["checks"]["recording"] = check_output(stopped["recording_path"], "media-recording")
        proof["checks"]["replay"] = check_output(saved["recording_path"], "media-replay")
        command("replay-stop")
        command("replay-stop")
        library = command("list")
        paths = {Path(stopped["recording_path"]).name, Path(saved["recording_path"]).name}
        selected = [clip for clip in library["clips"] if clip["name"] in paths]
        assert len(selected) == 2 and all(clip["finalized"] for clip in selected), "Finalized files missing from managed library"
        exported = command("export", id=selected[0]["id"], directory=str(OUTPUT / "media-export"))
        assert Path(exported["path"]).read_bytes() == (Path(selected[0]["directory"]) / selected[0]["name"]).read_bytes(), "Export changed media"
        command("record-start")
        time.sleep(2)
        cancelled = command("record-cancel")
        assert Path(cancelled["recording_path"]).is_file(), "Cancel destroyed the partial recording"
        proof["checks"]["coexistence"] = {"recording_and_replay": True, "stop_recording_preserved_replay": True,
                                              "cancel_preserved_partial": True, "export_preserved_source": True,
                                              "implicit_broadcast": False}
        # Cross the explicit configured reserve with a small disposable filler,
        # without exhausting disk. The owned observer must finalize local media.
        directory = Path(command("status")["media"]["storage"]["directory"])
        free = os.statvfs(directory).f_bavail * os.statvfs(directory).f_frsize
        reserve = free // (1024 * 1024) - 8
        if 256 <= reserve <= 65536:
            filler = directory / ".media-reserve-fixture"
            try:
                command("configure", preferences=dict(preferences, reserve_mib=reserve))
                command("record-start")
                with filler.open("wb") as output:
                    output.write(b"\0" * (16 * 1024 * 1024))
                    output.flush()
                    os.fsync(output.fileno())
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    snapshot = main_status()
                    if not snapshot["media"]["recording"]["active"]:
                        break
                    time.sleep(0.5)
                assert not snapshot["media"]["recording"]["active"] and not snapshot["stream"]["active"], "Low-space guard did not finalize local recording"
                proof["checks"]["reserve"] = {"status": "passed", "reserve_mib": reserve, "local_output_finalized": True,
                                                  "media_preserved": True, "actual_disk_exhaustion": False}
            finally:
                filler.unlink(missing_ok=True)
        else:
            proof["checks"]["reserve"] = {"status": "unavailable", "reason": "fixture free space is outside supported reserve range; unit/path tests remain separate"}
        command("configure", preferences=original)
        final = main_status()
        assert not final["stream"]["active"] and not final["media"]["recording"]["active"] and not final["media"]["replay_active"], "Local qualification left output active"
        proof["status"] = "passed"
        encoded = json.dumps(proof, sort_keys=True)
        assert not any(secret and secret in encoded for secret in SENSITIVE), "A credential reached native media proof"
        (OUTPUT / "media-qualification.json").write_text(encoded + "\n")
        print(encoded)
    finally:
        # Explicit local-output cleanup only; never start/stop streaming here.
        for action in ["record-stop", "replay-stop"]:
            try:
                command(action)
            except (AssertionError, subprocess.SubprocessError):
                pass
        try:
            command("configure", preferences=original)
        except (AssertionError, subprocess.SubprocessError):
            pass



def run_live():
    assert Path("/.dockerenv").exists() and Path.home() == Path("/work/home"), "Run only inside the disposable native fixture"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    secret = json.loads((root / "obsgod/secrets.json").read_text())
    SENSITIVE.update(secret.get(key, "") for key in ["obs_password", "stream_key"])
    initial = main_status()
    assert initial["stream"]["active"] and not initial["media"]["recording"]["active"] and not initial["media"]["replay_active"], "Live coexistence needs an explicitly started fixture stream and idle local outputs"
    try:
        command("record-start")
        command("replay-start")
        time.sleep(4)
        during = main_status()
        assert during["stream"]["active"] and during["media"]["recording"]["active"] and during["media"]["replay_active"], "Real stream/record/replay coexistence failed"
        health_result = subprocess.run([str(BINARY), "deck", "stream-health"],
                                       capture_output=True, timeout=10)
        health = json.loads(health_result.stdout)
        health_encoded = json.dumps(health)
        assert not any(secret and secret in health_encoded for secret in SENSITIVE), "A credential reached native health proof"
        assert health_result.returncode == 0 and health.get("ok") is True and health.get("output_known") is True and health.get("streaming") is True, "Native health failed to confirm the active local OBS output"
        metrics = health.get("metrics", {})
        assert isinstance(metrics.get("bitrate_kbps"), (int, float)) and metrics["bitrate_kbps"] > 0, "Native health did not measure positive advancing bitrate"
        assert isinstance(metrics.get("fps"), (int, float)) and metrics["fps"] > 0, "Native health did not measure positive FPS"
        assert health.get("provider_reception") == "unknown", "Local metrics incorrectly claimed provider/viewer reception"
        health_projection = {key: health[key] for key in ["schema_version", "state", "observed_at", "expires_at", "sample_ms", "output_known", "streaming", "metrics", "audio", "capture", "provider_reception"]}
        replay = command("replay-save")
        recording = command("record-stop")
        command("replay-stop")
        final = main_status()
        assert final["stream"]["active"] and final["stream"]["bytes"] > initial["stream"]["bytes"], "Local media operations stopped or stalled streaming"
        assert not final["media"]["recording"]["active"] and not final["media"]["replay_active"], "Local output stop was not confirmed"
        proof = {"status": "passed", "platform": "synthetic Linux OBS", "real_steam_deck": "unrun",
                 "stream_advanced_while_recording_and_replay": True, "local_stop_preserved_stream": True,
                 "health": health_projection,
                 "recording": check_output(recording["recording_path"], "media-live-recording"),
                 "replay": check_output(replay["recording_path"], "media-live-replay")}
        encoded = json.dumps(proof, sort_keys=True)
        assert not any(secret and secret in encoded for secret in SENSITIVE), "A credential reached native media proof"
        (OUTPUT / "media-live-qualification.json").write_text(encoded + "\n")
        print(encoded)
    finally:
        for action in ["record-stop", "replay-stop"]:
            try:
                command(action)
            except (AssertionError, subprocess.SubprocessError):
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream-active", action="store_true")
    options = parser.parse_args()
    if options.stream_active:
        run_live()
    else:
        run()
