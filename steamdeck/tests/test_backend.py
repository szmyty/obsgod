import asyncio
import importlib.util
import json
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

spec = importlib.util.spec_from_file_location("decky_backend", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

IDLE = {"ok": True, "state": "stopped", "output_known": True,
        "stream": {"active": False}, "message": "fixture idle"}
LIVE = {"ok": True, "state": "streaming", "output_known": True,
        "stream": {"active": True, "bytes": 4096}, "message": "fixture live"}


class FakeProcess:
    def __init__(self, wait=False):
        self.returncode = None
        self.done = asyncio.Event()
        self.signals = []
        self.input = None
        if not wait:
            self.done.set()

    async def communicate(self, input=None):
        self.input = input
        await self.done.wait()
        self.returncode = self.returncode or 0
        return json.dumps({**IDLE, "ok": self.returncode == 0}).encode(), b""

    def send_signal(self, value):
        self.signals.append(value)
        self.returncode = 130
        self.done.set()

    def kill(self):
        self.send_signal(signal.SIGKILL)


class BackendState(unittest.IsolatedAsyncioTestCase):
    async def test_capture_mode_uses_json_stdin_without_shell_or_settings_in_argv(self):
        plugin = backend.Plugin()
        process = FakeProcess()
        with patch.object(backend.os, "access", return_value=True), patch.object(
                backend.asyncio, "create_subprocess_exec", return_value=process) as spawn:
            result = await plugin._run("set-capture-mode", {"capture_mode": "game"})
        self.assertTrue(result["ok"])
        self.assertEqual(json.loads(process.input), {"capture_mode": "game"})
        self.assertEqual(spawn.call_args.args[-2:], ("deck", "set-capture-mode"))
        self.assertEqual(spawn.call_args.kwargs["stdin"], asyncio.subprocess.PIPE)
        self.assertNotIn("game", spawn.call_args.args)

    async def test_capture_mode_rechecks_real_output_and_refuses_live_unknown_or_recording(self):
        for current in [LIVE, {**IDLE, "output_known": False}, {**IDLE, "recording": True}]:
            with self.subTest(current=current):
                plugin = backend.Plugin()
                calls = []
                async def run(action, payload=None):
                    calls.append((action, payload))
                    return current
                with patch.object(plugin, "_run", side_effect=run):
                    result = await plugin.set_capture_mode("game")
                self.assertFalse(result["action_result"]["ok"])
                self.assertIn("confirmed status", result["action_result"]["message"])
                self.assertTrue(all(action == "status" for action, _ in calls))
                self.assertEqual(result.get("output_known"), current.get("output_known"))
                self.assertEqual(result.get("stream"), current.get("stream"))

    async def test_capture_mode_reserves_control_and_coalesces_only_matching_mode(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        finish = asyncio.Event()
        calls = []
        mode = "screen"
        async def run(action, payload=None):
            nonlocal mode
            calls.append((action, payload))
            if action == "set-capture-mode":
                entered.set()
                await finish.wait()
                mode = payload["capture_mode"]
            return {**IDLE, "configured": True, "settings": {"capture_mode": mode}}
        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.set_capture_mode("game"))
            await entered.wait()
            same = asyncio.create_task(plugin.set_capture_mode("game"))
            different = await plugin.set_capture_mode("screen")
            start = await plugin.start()
            self.assertFalse(different["action_result"]["ok"])
            self.assertFalse(start["action_result"]["ok"])
            self.assertEqual(different["operation"]["action"], "set-capture-mode")
            finish.set()
            changed, duplicate = await asyncio.gather(first, same)
        self.assertTrue(changed["action_result"]["ok"])
        self.assertEqual(changed["action_result"]["id"], duplicate["action_result"]["id"])
        self.assertEqual(changed["settings"]["capture_mode"], "game")
        self.assertEqual(sum(action == "set-capture-mode" for action, _ in calls), 1)
        self.assertNotIn("start", [action for action, _ in calls])

    async def test_invalid_capture_mode_never_reaches_cli_mutation(self):
        plugin = backend.Plugin()
        with patch.object(plugin, "_run", AsyncMock(return_value=IDLE)) as run:
            for mode in ["desktop", "game; unexpected", None, ["game"]]:
                result = await plugin.set_capture_mode(mode)
                self.assertFalse(result["action_result"]["ok"])
        self.assertTrue(all(call.args == ("status",) for call in run.call_args_list))

    async def test_stop_cancels_start_even_before_process_is_attached(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        attach = asyncio.Event()
        start_process = FakeProcess(wait=True)

        async def spawn(*args, **_kwargs):
            if args[-1] == "start":
                entered.set()
                await attach.wait()
                return start_process
            return FakeProcess()

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(plugin.start())
            await entered.wait()
            duplicate = asyncio.create_task(plugin.start())
            await asyncio.sleep(0)
            self.assertIsNone(plugin.pending)
            stopped = await plugin.stop()
            self.assertTrue(stopped["action_result"]["ok"])
            self.assertEqual(stopped["operation"]["state"], "cancelling")
            attach.set()
            result, repeated = await asyncio.gather(task, duplicate)
        self.assertIn(signal.SIGINT, start_process.signals)
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["action_result"]["id"], repeated["action_result"]["id"])
        self.assertFalse(plugin.busy)
        self.assertIsNone(plugin.pending)

    async def test_unload_waits_for_late_start_and_rejects_new_start(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        stop_entered = asyncio.Event()
        attach = asyncio.Event()
        process = FakeProcess(wait=True)
        starts = []

        async def spawn(*args, **_kwargs):
            if args[-1] == "start":
                starts.append(1)
                entered.set()
                await attach.wait()
                return process
            if args[-1] == "stop":
                stop_entered.set()
            return FakeProcess()

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            start_task = asyncio.create_task(plugin.start())
            await entered.wait()
            unloading = asyncio.create_task(plugin._unload())
            await stop_entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(unloading.done())
            rejected = await plugin.start()
            self.assertFalse(rejected["action_result"]["ok"])
            attach.set()
            await start_task
            result = await unloading
        self.assertTrue(result["output_known"])
        self.assertFalse(result["stream"]["active"])
        self.assertEqual(starts, [1])
        self.assertIn(signal.SIGINT, process.signals)
        self.assertFalse(plugin.busy)
        self.assertIsNone(plugin.pending)

    async def test_cancelled_spawn_keeps_ownership_until_late_child_is_reaped(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        attach = asyncio.Event()
        process = FakeProcess(wait=True)

        async def spawn(*_args, **_kwargs):
            entered.set()
            await attach.wait()
            return process

        with patch.object(backend.os, "access", return_value=True), patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(plugin._run("start"))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(plugin._cleanup_tasks)
            attach.set()
            await asyncio.gather(*plugin._cleanup_tasks)
        self.assertIn(signal.SIGINT, process.signals)
        self.assertIsNotNone(process.returncode)

    async def test_concurrent_start_and_stop_requests_are_coalesced(self):
        plugin = backend.Plugin()
        entered = asyncio.Event()
        finish = asyncio.Event()
        calls = []

        async def run(action):
            calls.append(action)
            if action == "start":
                entered.set()
                await finish.wait()
            return IDLE

        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.start())
            await entered.wait()
            second = asyncio.create_task(plugin.start())
            stopping = asyncio.create_task(plugin.stop())
            repeated_stop = asyncio.create_task(plugin.stop())
            await asyncio.sleep(0)
            finish.set()
            results = await asyncio.gather(first, second, stopping, repeated_stop)
        self.assertEqual(calls.count("start"), 1)
        self.assertEqual(calls.count("stop"), 1)
        self.assertEqual(results[0]["action_result"]["id"], results[1]["action_result"]["id"])
        self.assertEqual(results[2]["action_result"]["id"], results[3]["action_result"]["id"])

    async def test_failed_action_does_not_replace_observed_live_state(self):
        plugin = backend.Plugin()

        async def run(action):
            if action == "status":
                return LIVE
            return {"ok": False, "state": "error", "message": "fixture command failed"}

        with patch.object(plugin, "_run", side_effect=run):
            result = await plugin.start()
        self.assertTrue(result["stream"]["active"])
        self.assertTrue(result["output_known"])
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["action_result"]["message"], "fixture command failed")

    async def test_status_clients_share_query_and_pending_operation_metadata(self):
        plugin = backend.Plugin()
        finish = asyncio.Event()
        entered = asyncio.Event()
        calls = []

        async def run(action):
            calls.append(action)
            entered.set()
            await finish.wait()
            return IDLE

        with patch.object(plugin, "_run", side_effect=run):
            first = asyncio.create_task(plugin.status())
            await entered.wait()
            second = asyncio.create_task(plugin.status())
            await asyncio.sleep(0)
            finish.set()
            one, two = await asyncio.gather(first, second)
        self.assertEqual(calls, ["status"])
        self.assertEqual(one["snapshot_id"], two["snapshot_id"])
        self.assertEqual(one["backend_id"], two["backend_id"])
        self.assertIsNone(one["operation"])

    async def test_update_checks_coalesce_and_compare_the_app_not_only_the_plugin(self):
        plugin = backend.Plugin()
        calls = []

        def check(version, channel):
            calls.append((version, channel))
            return {"ok": True, "available": True, "state": "update-available", "message": "Update available"}

        module = SimpleNamespace(check_updates=check, current_versions=lambda _, **_kwargs: {
            "app": "0.1.0-deck.1", "plugin": "0.1.0-deck.4", "updater": "not-bundled", "mismatch": True})
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(backend.importlib.util, "spec_from_file_location", return_value=fake_spec), patch.object(backend.importlib.util, "module_from_spec", return_value=module):
            one, two = await asyncio.gather(plugin.check_for_updates(), plugin.check_for_updates())
        self.assertEqual(calls, [("0.1.0-deck.1", "preview")])
        self.assertEqual(one, two)
        self.assertTrue(one["mismatch"])
        self.assertEqual(one["current_app_version"], "0.1.0-deck.1")
        self.assertEqual(one["current_plugin_version"], "0.1.0-deck.4")
        self.assertIn("Desktop installer", one["message"])

    async def test_idle_stop_does_not_issue_another_command(self):
        plugin = backend.Plugin()
        run = AsyncMock(return_value=IDLE)
        with patch.object(plugin, "_run", run):
            result = await plugin.stop()
            await plugin.stop()
        self.assertTrue(result["action_result"]["ok"])
        self.assertNotIn("stop", [call.args[0] for call in run.call_args_list])

    async def test_unknown_output_keeps_recovery_stop_available(self):
        plugin = backend.Plugin()
        unknown = {"ok": False, "state": "unknown", "output_known": False, "message": "fixture unknown"}
        run = AsyncMock(return_value=unknown)
        with patch.object(plugin, "_run", run):
            result = await plugin.stop()
        self.assertFalse(result["output_known"])
        self.assertIn("stop", [call.args[0] for call in run.call_args_list])


class BackendContext(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch.dict(backend.os.environ, {}, clear=True))
        self.enterContext(patch.dict("sys.modules", {"decky": None}))
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)

    async def test_loader_paths_and_player_context_are_applied_only_to_child(self):
        plugin_dir = self.root / "custom-homebrew/plugins/OBSGod"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "package.json").write_text('{"version":"0.1.0-deck.6"}')
        home = self.root / "player"
        home.mkdir()
        service = self.root / "service"
        service.mkdir()
        runtime = str(self.root / "run/user/1000")
        values = {"HOME": str(service), "DECKY_PLUGIN_DIR": str(plugin_dir),
                  "DECKY_PLUGIN_VERSION": "0.1.0-deck.7", "DECKY_USER_HOME": str(home),
                  "DECKY_USER": "player", "XDG_CONFIG_HOME": str(service / ".config"),
                  "XDG_DATA_HOME": str(service / ".local/share"),
                  "XDG_STATE_HOME": str(self.root / "shared-state"),
                  "XDG_RUNTIME_DIR": runtime,
                  "DECKY_PLUGIN_SETTINGS_DIR": str(self.root / "loader-settings"),
                  "DECKY_PLUGIN_RUNTIME_DIR": str(self.root / "persistent-data")}
        with patch.dict(backend.os.environ, values), patch.object(backend.os, "umask") as umask:
            plugin = backend.Plugin()
            await plugin._main()
            process = FakeProcess()
            with patch.object(backend.os, "access", return_value=True), patch.object(
                    backend.asyncio, "create_subprocess_exec", return_value=process) as spawn:
                result = await plugin._run("status")
            self.assertTrue(result["ok"])
            self.assertEqual(spawn.call_args.args[0], str(plugin_dir / "bin/obsgod"))
            child = spawn.call_args.kwargs["env"]
            self.assertEqual(child["HOME"], str(home))
            self.assertEqual(child["USER"], "player")
            self.assertEqual(child["LOGNAME"], "player")
            self.assertNotIn("XDG_CONFIG_HOME", child)
            self.assertNotIn("XDG_DATA_HOME", child)
            self.assertEqual(child["XDG_STATE_HOME"], str(self.root / "shared-state"))
            self.assertEqual(child["XDG_RUNTIME_DIR"], runtime)
            self.assertEqual(backend.os.environ["HOME"], str(service))
            self.assertEqual(backend.os.environ["XDG_CONFIG_HOME"], str(service / ".config"))
            self.assertEqual(plugin._version(), "0.1.0-deck.7")
            umask.assert_called_once_with(0o077)

    async def test_invalid_plugin_directory_refuses_execution(self):
        ordinary_file = self.root / "not-a-directory"
        ordinary_file.write_text("fixture")
        for directory in ["relative/plugins", str(self.root / "missing"), str(ordinary_file), "/bad\npath"]:
            with self.subTest(directory=directory), patch.dict(backend.os.environ, {"DECKY_PLUGIN_DIR": directory}), patch.object(
                    backend.asyncio, "create_subprocess_exec") as spawn:
                result = await backend.Plugin().status()
                self.assertFalse(result["ok"])
                self.assertFalse(result["output_known"])
                spawn.assert_not_called()

    async def test_invalid_player_home_refuses_execution(self):
        for home in ["relative", str(self.root / "missing"), "\nunsafe"]:
            with self.subTest(home=home), patch.dict(backend.os.environ, {"DECKY_USER_HOME": home}), patch.object(
                    backend.os, "access", return_value=True), patch.object(
                    backend.asyncio, "create_subprocess_exec") as spawn:
                result = await backend.Plugin().status()
                self.assertFalse(result["output_known"])
                spawn.assert_not_called()

    def test_missing_variables_fall_back_to_bundle_and_preserve_standalone_environment(self):
        plugin = backend.Plugin()
        with patch.dict(backend.os.environ, {"HOME": str(self.root), "XDG_CONFIG_HOME": str(self.root / "config")}):
            self.assertEqual(plugin._plugin_root(), Path(backend.__file__).resolve().parent)
            self.assertEqual(plugin._child_environment()["XDG_CONFIG_HOME"], str(self.root / "config"))
            expected = json.loads((plugin._plugin_root() / "package.json").read_text())["version"]
            self.assertEqual(plugin._version(), expected)

    def test_old_loader_python_interface_is_feature_detected_without_optional_uid(self):
        module = SimpleNamespace(DECKY_USER_HOME=str(self.root), DECKY_USER="deck",
                                 DECKY_PLUGIN_DIR=str(self.root), DECKY_PLUGIN_VERSION="1.2.3")
        with patch.dict("sys.modules", {"decky": module}):
            plugin = backend.Plugin()
            self.assertEqual(plugin._plugin_root(), self.root)
            self.assertEqual(plugin._version(), "1.2.3")
            self.assertEqual(plugin._child_environment()["HOME"], str(self.root))
            self.assertEqual(plugin._child_environment()["USER"], "deck")

    def test_older_python_interface_empty_defaults_use_standalone_fallback(self):
        module = SimpleNamespace(DECKY_PLUGIN_DIR="", DECKY_USER_HOME="", DECKY_PLUGIN_VERSION="")
        with patch.dict("sys.modules", {"decky": module}), patch.dict(backend.os.environ, {"HOME": str(self.root)}):
            plugin = backend.Plugin()
            self.assertEqual(plugin._plugin_root(), Path(backend.__file__).resolve().parent)
            self.assertEqual(plugin._child_environment()["HOME"], str(self.root))
            self.assertNotEqual(plugin._version(), "unknown")

    def test_invalid_version_falls_back_and_metadata_is_bounded(self):
        (self.root / "package.json").write_text('{"version":"1.2.3"}')
        values = {"DECKY_PLUGIN_DIR": str(self.root), "DECKY_PLUGIN_VERSION": "bad\nversion",
                  "DECKY_VERSION": "v3.3.1", "DECKY_PLUGIN_NAME": "OBSGod",
                  "DECKY_PLUGIN_AUTHOR": "unsafe\nauthor", "UNRELATED_SECRET": "not-for-diagnostics"}
        with patch.dict(backend.os.environ, values):
            plugin = backend.Plugin()
            self.assertEqual(plugin._version(), "1.2.3")
            self.assertEqual(plugin._loader_metadata(), {"version": "v3.3.1", "plugin_name": "OBSGod"})
            decorated = plugin._decorate(IDLE)
            self.assertNotIn("not-for-diagnostics", json.dumps(decorated))
        with patch.dict(backend.os.environ, {"DECKY_PLUGIN_AUTHOR": "x" * 81}):
            self.assertNotIn("plugin_author", backend.Plugin()._loader_metadata())

    async def test_update_inventory_uses_same_explicit_player_context(self):
        home = self.root / "player"
        home.mkdir()
        current_versions = Mock(return_value={"app": "1.2.3", "plugin": "1.2.3",
                                             "updater": "1.2.3", "mismatch": False})
        module = SimpleNamespace(current_versions=current_versions,
                                 check_updates=lambda *_args, **_kwargs: {"ok": True, "message": "No update"})
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        values = {"HOME": str(self.root), "DECKY_USER_HOME": str(home),
                  "DECKY_PLUGIN_DIR": str(self.root), "DECKY_PLUGIN_VERSION": "1.2.3"}
        with patch.dict(backend.os.environ, values), patch.object(
                backend.importlib.util, "spec_from_file_location", return_value=fake_spec) as load, patch.object(
                backend.importlib.util, "module_from_spec", return_value=module):
            result = await backend.Plugin().check_for_updates()
            self.assertTrue(result["ok"])
            self.assertEqual(current_versions.call_args.kwargs["environ"]["HOME"], str(home))
            self.assertEqual(backend.os.environ["HOME"], str(self.root))
            self.assertEqual(load.call_args.args[1], self.root / "releases.py")


if __name__ == "__main__":
    unittest.main()
