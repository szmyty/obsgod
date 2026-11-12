#!/usr/bin/env python3
"""Qualify managed password changes against actual OBS in the disposable fixture.

Secrets stay in process memory/private files and never enter arguments or proof.
The surrounding shell fixture supplies the actual OBS/display/Flatpak adapter.
This is cloud Linux OBS evidence, not Steam Deck or real Flatpak acceptance.
"""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import tempfile
import time


BINARY = Path("/src/dist/obsgod")
OUTPUT = Path("/work/output")
FIXTURE_HOME = Path("/work/home")
CONFIG = FIXTURE_HOME / ".config/obsgod/deck.json"
CREDENTIALS = FIXTURE_HOME / ".config/obsgod/secrets.json"
WEBSOCKET = FIXTURE_HOME / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/plugin_config/obs-websocket/config.json"
ORDINARY = FIXTURE_HOME / ".var/app/com.obsproject.Studio/config/obs-studio"
SENSITIVE = set()


def safe_write(name, value):
    """Reject a proof before writing if any privately observed secret occurs."""
    encoded = json.dumps(value, sort_keys=True)
    assert not any(secret and secret in encoded for secret in SENSITIVE), "A credential reached native proof output"
    (OUTPUT / name).write_text(encoded + "\n")


def private_credentials():
    mode = CREDENTIALS.lstat().st_mode
    assert stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o600, "Native fixture credentials are not a private regular file"
    value = json.loads(CREDENTIALS.read_text())
    for field in ["stream_key", "obs_password"]:
        assert isinstance(value.get(field), str) and value[field], "Native fixture is missing a required credential"
        SENSITIVE.add(value[field])
    return value


def command(action, body=None, artifact=None, expect_success=True):
    # Payload never enters argv or stderr capture. Raw stderr is deliberately
    # discarded; fixed assertion messages avoid dumping a failed secret request.
    result = subprocess.run(
        [str(BINARY), "deck", action],
        input=json.dumps(body).encode() if body is not None else b"",
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=12,
    )
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise AssertionError("Native control command did not return valid JSON") from None
    assert isinstance(value, dict) and isinstance(value.get("ok"), bool), "Native control command returned an invalid result"
    # A password change can introduce a newly generated value. Learn it privately
    # before validating/writing the otherwise public command result.
    if action == "change-obs-password" and CREDENTIALS.exists():
        private_credentials()
    encoded = json.dumps(value)
    assert not any(secret and secret in encoded for secret in SENSITIVE), "Native control command returned a credential"
    if expect_success is True:
        assert result.returncode == 0 and value["ok"], "Expected native control operation failed: " + action
    elif expect_success is False:
        assert result.returncode != 0 and not value["ok"], "Expected native control refusal did not occur"
    if artifact:
        safe_write(artifact, value)
    return value


def closed(result):
    return result.get("process") == "absent" and result.get("output_known") is True


def authenticated_idle(result):
    return (result.get("ok") is True and result.get("connected") is True
            and result.get("managed") is True and result.get("output_known") is True
            and result.get("state") == "stopped")


def wait_for_control(label):
    # OBS authentication can precede frontend profile/collection readiness. This
    # is a bounded bootstrap wait after our explicit visible managed launch.
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        result = subprocess.run([str(BINARY), "deck", "test-connection"],
                                input=b"", stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=5)
        try:
            value = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise AssertionError("Managed connection probe returned invalid JSON") from None
        if result.returncode == 0 and authenticated_idle(value):
            safe_write("control-password-" + label + "-connected.json", value)
            return value
        # Authentication mismatch after synchronized files is a real failure;
        # do not hide it behind a startup retry or launch another instance.
        assert "rejected" not in value.get("message", "").casefold(), "Actual OBS rejected the synchronized new password"
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(.2, remaining))
    raise AssertionError("Actual OBS did not verify the new local control connection within the bootstrap deadline")


async def old_password_rejected(password):
    """Only Hello/Identify traffic; never send an output or configuration RPC."""
    import websockets
    async with websockets.connect("ws://127.0.0.1:4457", open_timeout=3,
                                  max_size=16384) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 3))
        auth = hello.get("d", {}).get("authentication")
        assert hello.get("op") == 0 and auth and auth.get("salt") and auth.get("challenge"), "Actual OBS did not require password authentication"
        secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
        answer = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        await socket.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": 0, "authentication": answer}}))
        try:
            await asyncio.wait_for(socket.recv(), 3)
        except websockets.ConnectionClosed as error:
            received = getattr(error, "rcvd", None)
            code = received.code if received is not None else getattr(error, "code", None)
            assert code == 4009, "Old password failed for a reason other than authentication rejection"
            return {"status": "passed", "old_password_rejected": True,
                    "close_code": code, "requests": "Hello/Identify only"}
        raise AssertionError("Actual OBS accepted the previous local password")


def ordinary_snapshot():
    return {str(path.relative_to(ORDINARY)): path.read_bytes()
            for path in ORDINARY.rglob("*") if path.is_file()}


async def workflow_snapshot(password):
    """Independently observe real OBS using only read requests."""
    import websockets
    async with websockets.connect("ws://127.0.0.1:4457", open_timeout=3,
                                  max_size=1024 * 1024) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 3))
        auth = hello.get("d", {}).get("authentication")
        assert hello.get("op") == 0 and auth, "Workflow fixture OBS did not require authentication"
        secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
        answer = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        await socket.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": 0, "authentication": answer}}))
        identified = json.loads(await asyncio.wait_for(socket.recv(), 3))
        assert identified.get("op") == 2, "Workflow observer could not authenticate to real OBS"
        values = {}
        for number, operation in enumerate(["GetProfileList", "GetSceneCollectionList", "GetSceneList", "GetStreamStatus", "GetRecordStatus", "GetReplayBufferStatus"]):
            identifier = "workflow-" + str(number)
            await socket.send(json.dumps({"op": 6, "d": {"requestType": operation, "requestId": identifier}}))
            response = json.loads(await asyncio.wait_for(socket.recv(), 3))
            body = response.get("d", {})
            assert response.get("op") == 7 and body.get("requestId") == identifier, "Workflow observer received an unrelated response"
            status = body.get("requestStatus", {})
            if operation == "GetReplayBufferStatus" and status.get("code") == 604:
                values[operation] = {"outputActive": False, "unavailable": True}
            else:
                assert status.get("result") is True and status.get("code") == 100, "Workflow observer could not read required OBS state"
                values[operation] = body.get("responseData", {})
        for operation in ["GetStreamStatus", "GetRecordStatus", "GetReplayBufferStatus"]:
            assert values[operation].get("outputActive") is False, "Settings-only workflow observed unexpected active output"
        assert values["GetStreamStatus"].get("outputReconnecting") is False, "Settings-only workflow observed reconnecting output"
        return {"profile": values["GetProfileList"].get("currentProfileName"),
                "collection": values["GetSceneCollectionList"].get("currentSceneCollectionName"),
                "scene": values["GetSceneList"].get("currentProgramSceneName"),
                "scenes": [value.get("sceneName") for value in values["GetSceneList"].get("scenes", [])],
                "streaming": False, "recording": False, "replay_buffer": False}


def settings_workflow(password, initial_settings, initial_key, initial_hash):
    """Exercise the real CLI configuration/approval/OBS path without output."""
    before = asyncio.run(workflow_snapshot(password))
    assert before["profile"] == "OBSGod" and before["collection"] == "OBSGod", "Workflow fixture is outside its managed OBS identity"
    target = next((scene for scene in ["OBSGod Idle", "OBSGod Live"] if scene in before["scenes"]), None)
    assert target, "Workflow fixture has no existing managed idle/live scene"
    previous_secret, previous_ws = CREDENTIALS.read_bytes(), WEBSOCKET.read_bytes()
    with tempfile.TemporaryDirectory(prefix="workflow-control-", dir=FIXTURE_HOME) as directory:
        root = Path(directory)
        private_file = root / "obs-password"
        private_file.write_text(password + "\n")
        private_file.chmod(0o600)
        config = root / "config.json"
        config.write_text(json.dumps({"version": 1,
            "connection": {"host": "127.0.0.1", "port": 4457, "password_file": "obs-password"},
            "workflow_profiles": {"managed": {"obs_profile": before["profile"],
                "scene_collection": before["collection"], "starting_scene": target,
                "recording_enabled": False, "replay_buffer_enabled": False,
                "readiness_timeout": "5s", "post_start_delay": "0s"}}}))
        config.chmod(0o600)
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("OBS_", "OBSGOD_"))}
        result = subprocess.run([str(BINARY), "--config", str(config), "workflow", "apply", "managed", "--approve"],
                                input=b"", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=environment, timeout=15)
        try:
            value = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise AssertionError("Actual OBS workflow did not return valid JSON") from None
        assert result.returncode == 0 and value.get("ok") is True, "Actual OBS settings-only workflow failed"
        assert value.get("schema_version") == 1 and isinstance(value.get("applied"), list), "Actual workflow result has an invalid contract"
        assert not any(stage in value["applied"] for stage in ["recording", "replay_buffer"]), "Settings-only workflow enabled local output"
        safe_write("control-workflow-apply.json", value)
    after = asyncio.run(workflow_snapshot(password))
    assert after["profile"] == before["profile"] and after["collection"] == before["collection"] and after["scene"] == target, "Real OBS did not retain the selected workflow settings"
    assert CREDENTIALS.read_bytes() == previous_secret and WEBSOCKET.read_bytes() == previous_ws, "Generic workflow changed managed credentials"
    current = private_credentials()
    assert current["stream_key"] == initial_key and current["settings_hash"] == initial_hash, "Generic workflow changed the stream key/settings binding"
    assert CONFIG.read_bytes() == initial_settings, "Generic workflow rewrote managed Deck settings"
    proof = {"status": "passed", "target_profile": after["profile"],
             "target_collection": after["collection"], "target_scene": target,
             "actual_applied_stages": value["applied"], "all_output_remained_inactive": True,
             "managed_settings_and_credentials_preserved": True,
             "private_generic_configuration_removed": True}
    safe_write("control-workflow-qualification.json", proof)
    return proof


def run_case(label, initial_settings, initial_key, initial_hash):
    assert closed(command("status")), "Password case did not start after confirmed managed shutdown"
    previous = private_credentials()
    old_password = previous["obs_password"]
    info = command("connection-info", artifact="control-password-" + label + "-before.json")
    assert closed(info) and info["authentication_required"] and info["credentials_available"], "Closed native control details are inconsistent"
    request = {"confirm": True, "generate": True}
    if label == "manual":
        manual = "manual-" + secrets.token_urlsafe(32)
        SENSITIVE.add(manual)
        request = {"confirm": True, "generate": False, "password": manual}
    changed = command("change-obs-password", request,
                      "control-password-" + label + "-change.json")
    assert changed.get("awaiting_verification") is True and not changed.get("connected"), "A file update was falsely reported as verified reconnection"
    current = private_credentials()
    assert current["obs_password"] != old_password, "Native password did not change"
    assert current["stream_key"] == initial_key and current["settings_hash"] == initial_hash, "Password change damaged stream credentials or settings binding"
    assert CONFIG.read_bytes() == initial_settings, "Password change modified stream settings"
    mode = WEBSOCKET.lstat().st_mode
    assert stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o600, "Managed WebSocket settings are not private"
    ws = json.loads(WEBSOCKET.read_text())
    assert ws.get("server_password") == current["obs_password"], "Managed OBS/CLI passwords are not synchronized"
    assert ws.get("server_port") == 4457 and ws.get("server_enabled") is True and ws.get("auth_required") is True, "Password update disabled or exposed an unexpected control configuration"
    assert closed(command("connection-info")), "Password change unexpectedly launched OBS"

    command("open-obs", artifact="control-password-" + label + "-open.json")
    wait_for_control(label)
    workflow = settings_workflow(current["obs_password"], initial_settings, initial_key, initial_hash) if label == "generated" else None
    rejected = asyncio.run(old_password_rejected(old_password))
    safe_write("control-password-" + label + "-old-rejected.json", rejected)

    before_secret, before_ws = CREDENTIALS.read_bytes(), WEBSOCKET.read_bytes()
    refusal = command("change-obs-password", {"confirm": True, "generate": True},
                      "control-password-" + label + "-present-refused.json", expect_success=False)
    assert not refusal["ok"], "Present managed OBS allowed password replacement"
    assert CREDENTIALS.read_bytes() == before_secret and WEBSOCKET.read_bytes() == before_ws, "Refused password replacement modified private files"
    assert authenticated_idle(command("test-connection")), "Refused rotation damaged the working connection or started output"
    stopped = command("restart", artifact="control-password-" + label + "-closed.json")
    assert closed(stopped), "Native managed OBS shutdown was not confirmed after password verification"
    return {"status": "passed", "mode": label, "private_pair_synchronized": True,
            "stream_key_and_settings_binding_preserved": True,
            "file_update_awaited_verification": True,
            "actual_obs_new_password_authenticated": True,
            "old_password_rejected_code": rejected["close_code"],
            "rotation_while_present_refused_without_change": True,
            "output_stayed_stopped": True, "final_managed_shutdown_confirmed": True,
            "settings_only_workflow": workflow}


def main():
    assert Path("/.dockerenv").exists() and Path.home().resolve() == FIXTURE_HOME, "Run this helper only in its disposable /work/home container fixture"
    assert BINARY.is_file() and OUTPUT.is_dir(), "Native fixture paths are unavailable"
    credentials = private_credentials()
    settings = CONFIG.read_bytes()
    ordinary = ordinary_snapshot()
    cases = []
    try:
        for label in ["generated", "manual"]:
            cases.append(run_case(label, settings, credentials["stream_key"], credentials["settings_hash"]))
        assert ordinary_snapshot() == ordinary, "Password qualification changed ordinary OBS files"
        safe_write("control-password-qualification.json", {
            "status": "passed", "platform": "Linux disposable container, real OBS; modeled Flatpak invocation",
            "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
            "cases": cases, "ordinary_obs_preserved": True,
            "secret_values_exported": False,
            "limitations": ["Actual Steam Deck/SteamOS/Gamescope/Flatpak password recovery remains unrun", "No external provider account or broadcast was used"],
        })
        print("PASS: actual OBS generated/manual local password synchronization, new authenticated connection, previous-password rejection, present-instance refusal and confirmed shutdown; no stream or recording started by these cases.")
    finally:
        # On failure, close only an instance whose current authenticated output
        # is positively idle. The disposable container owns any unknown failure.
        try:
            result = command("test-connection", expect_success=None)
        except (AssertionError, OSError, subprocess.SubprocessError):
            result = None
        if result and authenticated_idle(result):
            command("restart")


if __name__ == "__main__":
    main()
