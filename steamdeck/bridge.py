"""Small local process boundary. Never echo command input or stderr."""
import json
import os
from pathlib import Path
import signal
import subprocess


def cli_path():
    return Path(__file__).resolve().parent / "obsgod"


def run_cli(action, settings=None, timeout=85):
    if action not in {"status", "doctor", "configure", "start", "stop", "test-recording", "restart", "open-obs", "connection-info", "test-connection", "change-obs-password", "stream-profiles", "set-idle-media", "media", "stream-health", "retry-recovery", "mixer"}:
        return {"ok": False, "state": "error", "message": "Unknown operation"}
    payload = json.dumps(settings).encode() if settings is not None else b""
    process = subprocess.Popen(
        [str(cli_path()), "deck", action], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        output, _ = process.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.send_signal(signal.SIGINT)
        try:
            process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        return {"ok": False, "state": "unknown", "message": "Operation timed out. Check OBS and use Stop streaming; output state is unknown."}
    try:
        result = json.loads(output)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError()
        return result
    except (ValueError, UnicodeDecodeError):
        return {"ok": False, "state": "unknown", "message": "Could not read OBSGod output. Check the installation and inspect OBS before broadcasting."}


def private_process():
    os.umask(0o077)
