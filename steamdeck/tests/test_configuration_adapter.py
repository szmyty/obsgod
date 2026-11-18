"""Private native configuration wiring, races and real JSON-stdin execution."""
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


spec = importlib.util.spec_from_file_location("configuration_adapter", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

KEY = "synthetic-private-stream-key-79"
PASSWORD = "synthetic-private-obs-password-79"
SERVER = "rtmps://fixture.invalid/app"
CONNECTION = {"ok": True, "host": "127.0.0.1", "port": "4457", "authentication_required": True,
              "credentials_available": True, "connected": False, "managed": False, "process": "absent",
              "output_known": True, "state": "stopped", "message": "Managed OBS is closed"}
VIEW = {"schema_version": 1, "ok": True, "configured": True, "key_configured": True,
        "settings": {"version": 1, "server": SERVER, "bitrate": 4500, "fps": 30, "encoder": "vaapi",
                     "width": 1280, "height": 720, "capture_mode": "game", "microphone": False},
        "connection": CONNECTION, "output_known": True, "can_configure": True, "can_close": False,
        "message": "Saving settings does not start OBS or broadcast"}
IDLE = {"ok": True, "state": "stopped", "output_known": True, "stream": {"active": False},
        "process": "absent", "media": {"known": True, "replay_active": False}, "message": "Idle"}


class ConfigurationAdapter(unittest.IsolatedAsyncioTestCase):
    def test_shared_go_wire_corpus_requires_complete_consistent_readiness(self):
        corpus = json.loads((Path(__file__).parent / "fixtures/configuration-contract.json").read_text())
        self.assertEqual(corpus["schema_version"], 1)
        for case in corpus["cases"]:
            with self.subTest(case=case["name"]):
                value = case["input"]
                self.assertEqual(backend._valid_configuration(value), case["valid"])
                projected = backend._public_configuration(value)
                self.assertEqual(projected["can_configure"], case["can_configure"])
                self.assertEqual(projected["can_close"], case["can_close"])
                password = (projected["can_configure"] and projected["configured"] and
                            projected["connection"]["process"] == "absent" and projected["connection"]["output_known"])
                self.assertEqual(password, case["can_change_password"])
                for name, expected in case.get("normalized_settings", {}).items():
                    self.assertEqual(projected["settings"][name], expected)
                if not case["valid"]:
                    self.assertFalse(projected["ok"])
                    self.assertFalse(projected["output_known"])

    async def test_real_child_receives_literal_json_stdin_and_only_fixed_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            log = root / "commands.jsonl"
            script = root / "bin/obsgod"
            script.write_text("#!" + sys.executable + "\n" +
                "import json,pathlib,sys\n" +
                "action=sys.argv[2];payload=sys.stdin.read()\n" +
                "with pathlib.Path(" + repr(str(log)) + ").open('a') as f:f.write(json.dumps({'argv':sys.argv[1:],'stdin':payload})+'\\n')\n" +
                "view=json.loads(" + repr(json.dumps(VIEW)) + ")\n" +
                "result=view if action=='configuration' else view['connection'] if action=='test-connection' else {'ok':True,'message':'Saved privately'}\n" +
                "print(json.dumps(result))\n")
            script.chmod(0o700)
            plugin = backend.Plugin()
            literal = KEY + " '$(echo bad)' ; $HOME `echo nope`"
            payload = {"server": SERVER, "stream_key": literal, "capture_mode": "game"}
            with patch.object(plugin, "_plugin_root", return_value=root), patch.object(plugin, "_child_environment", return_value=dict(os.environ)):
                saved = await plugin.configure_destination(payload)
                changed = await plugin.change_control_password({"password": PASSWORD, "confirm": True})
                tested = await plugin.test_control_connection()
                closed = await plugin.close_managed_obs()
            self.assertTrue(saved["action_result"]["ok"])
            self.assertTrue(changed["action_result"]["ok"])
            self.assertTrue(tested["connection"]["authentication_required"])
            self.assertTrue(closed["action_result"]["ok"])
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            actions = [item["argv"][1] for item in commands]
            self.assertEqual([name for name in actions if name != "configuration"],
                             ["configure-fields", "change-obs-password", "test-connection", "restart"])
            self.assertEqual(json.loads(commands[0]["stdin"]), payload)
            self.assertTrue(all(item["argv"][0] == "deck" and len(item["argv"]) == 2 for item in commands))
            self.assertNotIn(literal, json.dumps([item["argv"] for item in commands]))
            self.assertEqual(payload["stream_key"], literal)
            self.assertIsNone(plugin._control_payload)
            self.assertNotIn(KEY, json.dumps(plugin._last_action))
            self.assertNotIn(PASSWORD, json.dumps(plugin._last_action))

    async def test_public_projection_drops_unexpected_secrets_and_private_paths(self):
        raw = copy.deepcopy(VIEW)
        raw.update(stream_key=KEY, setup_token=PASSWORD, message="stream_key=" + KEY)
        raw["settings"].update(stream_key=KEY, obs_password=PASSWORD, idle_media="/home/private/clip.mp4")
        raw["connection"].update(password=PASSWORD, message="password=" + PASSWORD)
        plugin = backend.Plugin()
        with patch.object(plugin, "_run", AsyncMock(return_value=raw)):
            result = await plugin.configuration_status()
        serialized = json.dumps(result)
        for private in (KEY, PASSWORD, "/home/private", "stream_key", "setup_token", "obs_password"):
            self.assertNotIn(private, serialized)
        self.assertEqual(result["settings"]["server"], SERVER)

    async def test_malformed_configuration_is_closed_to_writes(self):
        cases = [None, [], {"ok": True}, {**VIEW, "schema_version": True},
                 {**VIEW, "settings": {"server": [KEY]}}, {**VIEW, "output_known": "yes"},
                 {**VIEW, "connection": {"password": KEY, "connected": "yes", "host": []}}]
        for raw in cases:
            with self.subTest(raw=raw):
                plugin = backend.Plugin()
                with patch.object(plugin, "_run", AsyncMock(return_value=raw)):
                    result = await plugin.configuration_status()
                self.assertFalse(result["can_configure"])
                self.assertFalse(result["can_close"])
                self.assertNotIn(KEY, json.dumps(result))

    async def test_invalid_native_payloads_do_not_reach_go(self):
        plugin = backend.Plugin()
        with patch.object(plugin, "_run", AsyncMock()) as run:
            for payload in [None, [], {}, {"server": None}, {"stream_key": [KEY]},
                            {"unsupported": KEY}, {"server": "x" * 17000}, {"bitrate": float("nan")}]:
                result = await plugin.configure_destination(payload)
                self.assertEqual(result["schema_version"], 1)
                self.assertFalse(result["action_result"]["ok"])
            for payload in [{"password": PASSWORD}, {"confirm": 1, "password": PASSWORD},
                            {"confirm": True, "password": {"nested": PASSWORD}}]:
                result = await plugin.change_control_password(payload)
                self.assertFalse(result["action_result"]["ok"])
        run.assert_not_called()

    async def test_repeated_save_coalesces_and_different_control_is_refused(self):
        plugin = backend.Plugin()
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def run(action, payload=None):
            calls.append(action)
            if action == "configure-fields":
                entered.set()
                await release.wait()
                return {"ok": True, "message": "Settings saved privately"}
            return copy.deepcopy(VIEW if action == "configuration" else IDLE)

        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.configure_destination({"stream_key": KEY}))
            await entered.wait()
            repeated = asyncio.create_task(plugin.configure_destination({"stream_key": KEY}))
            different = await plugin.configure_destination({"stream_key": "another-synthetic-key"})
            start = await plugin.start()
            self.assertFalse(different["action_result"]["ok"])
            self.assertFalse(start["action_result"]["ok"])
            self.assertFalse(different["can_configure"])
            release.set()
            saved, duplicate = await asyncio.gather(first, repeated)
        self.assertEqual(saved["action_result"]["id"], duplicate["action_result"]["id"])
        self.assertEqual(calls.count("configure-fields"), 1)
        self.assertNotIn("start", calls)
        self.assertTrue(saved["can_configure"])
        self.assertIsNone(plugin._control_payload)

    async def test_stop_is_available_during_save_and_save_is_blocked_during_stop(self):
        plugin = backend.Plugin()
        saving, finish_save = asyncio.Event(), asyncio.Event()
        stopping, finish_stop = asyncio.Event(), asyncio.Event()
        calls = []

        async def run(action, payload=None):
            calls.append(action)
            if action == "configure-fields":
                saving.set()
                await finish_save.wait()
                return {"ok": True, "message": "Saved privately"}
            if action == "stop":
                stopping.set()
                await finish_stop.wait()
                return {"ok": True, "message": "Stopped"}
            if action == "configuration":
                return copy.deepcopy(VIEW)
            return {**IDLE, "stream": {"active": True}}

        with patch.object(plugin, "_run", side_effect=run):
            save = asyncio.create_task(plugin.configure_destination({"stream_key": KEY}))
            await saving.wait()
            stop = asyncio.create_task(plugin.stop())
            await stopping.wait()
            refused = await plugin.configure_destination({"bitrate": 5000})
            self.assertFalse(refused["action_result"]["ok"])
            self.assertFalse(refused["can_configure"])
            finish_save.set()
            await save
            finish_stop.set()
            await stop
        self.assertEqual(calls.count("configure-fields"), 1)
        self.assertEqual(calls.count("stop"), 1)
        self.assertNotIn("start", calls)

    async def test_busy_closing_and_dependency_flags_override_a_read_in_flight(self):
        for flag in ("closing", "setup_requested", "dependency"):
            plugin = backend.Plugin()
            entered, release = asyncio.Event(), asyncio.Event()

            async def run(action, payload=None):
                entered.set()
                await release.wait()
                return copy.deepcopy(VIEW)

            with self.subTest(flag=flag), patch.object(plugin, "_run", side_effect=run):
                reading = asyncio.create_task(plugin.configuration_status())
                await entered.wait()
                if flag == "closing": plugin._closing = True
                elif flag == "setup_requested": plugin._setup_requested = True
                else: plugin._dependency_job = SimpleNamespace(running=True)
                release.set()
                result = await reading
                self.assertFalse(result["can_configure"])
                self.assertFalse(result["can_close"])
                refused = await plugin.configure_destination({"stream_key": KEY})
                self.assertFalse(refused["action_result"]["ok"])

    async def test_configuration_is_allowed_offline_without_a_dependency_job(self):
        plugin = backend.Plugin()
        calls = []

        async def run(action, payload=None):
            calls.append(action)
            return copy.deepcopy(VIEW) if action == "configuration" else {"ok": True, "message": "Saved privately"}

        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.configure_destination({"server": SERVER, "stream_key": KEY})
        self.assertTrue(result["action_result"]["ok"])
        self.assertEqual(calls, ["configure-fields", "configuration"])

    async def test_old_read_is_invalidated_and_readers_share_the_fresh_generation(self):
        plugin = backend.Plugin()
        old_entered, release_old = asyncio.Event(), asyncio.Event()
        changed = copy.deepcopy(VIEW)
        changed["settings"]["server"] = "rtmps://new.invalid/app"
        reads = 0

        async def run(action, payload=None):
            nonlocal reads
            if action == "configuration":
                reads += 1
                if reads == 1:
                    old_entered.set()
                    await release_old.wait()
                    return copy.deepcopy(VIEW)
                return copy.deepcopy(changed)
            return {"ok": True, "message": "Saved privately"}

        with patch.object(plugin, "_run", side_effect=run):
            old = asyncio.create_task(plugin.configuration_status())
            await old_entered.wait()
            saved = await plugin.configure_destination({"server": changed["settings"]["server"], "stream_key": KEY})
            release_old.set()
            late = await old
        self.assertEqual(saved["settings"]["server"], changed["settings"]["server"])
        self.assertEqual(late["settings"]["server"], changed["settings"]["server"])
        self.assertGreaterEqual(reads, 2)

    async def test_caller_cancellation_cannot_erase_the_owned_queued_key(self):
        plugin = backend.Plugin()
        entered, release = asyncio.Event(), asyncio.Event()
        seen = []

        async def run(action, payload=None):
            if action == "configure-fields":
                entered.set()
                await release.wait()
                seen.append(payload["stream_key"])
                return {"ok": True, "message": "Saved privately"}
            return copy.deepcopy(VIEW)

        with patch.object(plugin, "_run", side_effect=run):
            caller = asyncio.create_task(plugin.configure_destination({"stream_key": KEY}))
            await entered.wait()
            caller.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await caller
            self.assertEqual(plugin._control_payload["stream_key"], KEY)
            release.set()
            await plugin._control_task
        self.assertEqual(seen, [KEY])
        self.assertIsNone(plugin._control_payload)
        self.assertNotIn(KEY, json.dumps(plugin._last_action))

    async def test_unknown_and_active_refusals_delegate_to_go_without_auto_stop_or_start(self):
        for current in ({**VIEW, "output_known": False}, {**VIEW, "can_configure": False, "can_close": False}):
            plugin = backend.Plugin()
            calls = []

            async def run(action, payload=None):
                calls.append(action)
                return copy.deepcopy(current) if action == "configuration" else {"ok": False, "message": "Close managed OBS before saving settings"}

            with patch.object(plugin, "_run", side_effect=run):
                result = await plugin.configure_destination({"stream_key": KEY})
            self.assertFalse(result["action_result"]["ok"])
            self.assertFalse(result["can_configure"])
            self.assertEqual(calls, ["configure-fields", "configuration"])
            self.assertIsNone(plugin._control_payload)

    async def test_tested_connection_is_projected_and_secret_error_echo_is_removed(self):
        plugin = backend.Plugin()
        tested = {**CONNECTION, "connected": True, "managed": True, "process": "running", "state": "streaming",
                  "password": PASSWORD, "stream_key": KEY, "message": "password=" + PASSWORD}

        async def run(action, payload=None):
            return copy.deepcopy(VIEW) if action == "configuration" else tested

        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.test_control_connection()
        self.assertTrue(result["connection"]["connected"])
        self.assertEqual(result["connection"]["state"], "streaming")
        self.assertFalse(result["output_known"])
        self.assertFalse(result["can_configure"])
        self.assertFalse(result["can_close"])
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn(PASSWORD, json.dumps(result))

    async def test_closed_failed_connection_test_preserves_coherent_offline_configuration(self):
        plugin = backend.Plugin()
        tested = {**CONNECTION, "ok": False, "message": "Managed OBS is offline"}

        async def run(action, payload=None):
            return copy.deepcopy(VIEW) if action == "configuration" else tested

        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.test_control_connection()
        self.assertFalse(result["connection"]["ok"])
        self.assertTrue(result["can_configure"])
        self.assertTrue(backend._valid_configuration(result))

    async def test_failed_or_cancelled_private_operations_clear_payload(self):
        for failure in (OSError("private-path-" + KEY), asyncio.CancelledError()):
            plugin = backend.Plugin()

            async def run(action, payload=None):
                if action == "change-obs-password":
                    raise failure
                return copy.deepcopy(VIEW)

            with self.subTest(failure=type(failure).__name__), patch.object(plugin, "_run", side_effect=run):
                if isinstance(failure, asyncio.CancelledError):
                    with self.assertRaises(asyncio.CancelledError):
                        await plugin.change_control_password({"password": PASSWORD, "confirm": True})
                else:
                    result = await plugin.change_control_password({"password": PASSWORD, "confirm": True})
                    self.assertNotIn(KEY, json.dumps(result))
                await asyncio.sleep(0)
                self.assertIsNone(plugin._control_payload)


if __name__ == "__main__":
    unittest.main()
