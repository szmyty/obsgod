"""Capture edits use real owned children/file locks without OBS or port 4457."""
import asyncio
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("capture_adapter", Path(__file__).resolve().parents[1] / "decky/main.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

CLI = r'''import fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent.parent
options=json.loads((root/'options.json').read_text())
action=sys.argv[2]
with (root/'calls.jsonl').open('a') as log:log.write(json.dumps({'action':action,'pid':os.getpid()})+'\n')
if options.get('ignore_sigint'):signal.signal(signal.SIGINT,signal.SIG_IGN)
if action=='set-capture-mode':
 request=json.loads(sys.stdin.read())
 (root/'command-started').write_text('started')
 if options.get('inherit_stdout'):
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
  (root/'descendant-pid').write_text(str(child.pid))
  sys.exit(0)
 lock=(root/'control.lock').open('a+')
 fcntl.flock(lock,fcntl.LOCK_EX)
 time.sleep(options.get('command_delay',0))
 state=json.loads((root/'settings.json').read_text());state['capture_mode']=request['capture_mode']
 temporary=root/'settings.new';temporary.write_text(json.dumps(state));temporary.replace(root/'settings.json')
 (root/'saved').write_text('saved')
 time.sleep(options.get('post_action_delay',0))
 print(json.dumps({'ok':True,'message':'Capture mode saved'}))
elif action in ('status','stop'):
 if action=='stop':(root/'stop-observed').write_text('stopped')
 saved=(root/'saved').exists()
 time.sleep(options.get('readback_delay' if saved else 'preflight_delay',0))
 state=json.loads((root/'settings.json').read_text())
 mode='screen' if saved and options.get('wrong_readback') else state['capture_mode']
 print(json.dumps({'ok':True,'configured':True,'state':'stopped','output_known':True,'process':'absent',
  'recording':False,'stream':{'active':False,'reconnecting':False},'settings':{'capture_mode':mode},
  'media':{'known':True,'replay_active':False,'recording':{'active':False,'paused':False}},'message':'Observed idle'}))
else:sys.exit(70)
'''


class CaptureModeAdapter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="capture-mode-adapter-")
        self.root = Path(self.temporary.name)
        (self.root / "bin").mkdir()
        binary = self.root / "bin/obsgod"
        binary.write_text("#!" + sys.executable + "\n" + CLI)
        binary.chmod(0o700)
        self.options = {}
        self.write_options()
        self.initial = {"capture_mode": "screen", "stream_key": "synthetic-private-capture-key", "settings_binding": "preserved"}
        (self.root / "settings.json").write_text(json.dumps(self.initial))
        self.plugin = backend.Plugin()
        self.enterContext(patch.object(self.plugin, "_plugin_root", return_value=self.root))
        self.enterContext(patch.object(self.plugin, "_child_environment", return_value=dict(os.environ)))
        self.enterContext(patch.dict(backend.CAPTURE_MODE_BUDGET,
            {"preflight": 0.7, "command": 0.8, "readback": 0.7, "cleanup": 0.2}))

    async def asyncTearDown(self):
        for child in tuple(self.plugin._children):
            if child.returncode is None:
                child.kill()
        if self.plugin._cleanup_tasks:
            await asyncio.gather(*self.plugin._cleanup_tasks, return_exceptions=True)
        descendant = self.root / "descendant-pid"
        if descendant.exists():
            try:os.kill(int(descendant.read_text()), signal.SIGKILL)
            except ProcessLookupError:pass
        self.temporary.cleanup()

    def write_options(self):
        (self.root / "options.json").write_text(json.dumps(self.options))

    def settings(self):
        return json.loads((self.root / "settings.json").read_text())

    def actions(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line)["action"] for line in path.read_text().splitlines()] if path.exists() else []

    async def started(self):
        async def wait():
            while not (self.root / "command-started").exists():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait(), 2)

    async def test_actual_lock_waiter_is_terminated_before_failure_and_cannot_write_after_release(self):
        self.options["ignore_sigint"] = True
        self.write_options()
        with (self.root / "control.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            began = time.monotonic()
            result = await asyncio.wait_for(self.plugin.set_capture_mode("game"), 3)
            self.assertLess(time.monotonic() - began, 2.5)
            self.assertFalse(result["action_result"]["ok"])
            self.assertFalse(self.plugin.busy)
            self.assertFalse(self.plugin._children)
            self.assertEqual(self.settings(), self.initial)
        await asyncio.sleep(0.15)
        self.assertEqual(self.settings(), self.initial)
        self.assertEqual(self.actions().count("set-capture-mode"), 1)

    async def test_near_deadline_success_includes_post_action_and_fresh_readback_without_old_query_join(self):
        self.options.update(command_delay=0.3, post_action_delay=0.2, readback_delay=0.2)
        self.write_options()
        old = asyncio.create_task(asyncio.sleep(30))
        self.plugin._status_task = old
        try:
            result = await asyncio.wait_for(self.plugin.set_capture_mode("game"), 3)
            self.assertTrue(result["action_result"]["ok"])
            self.assertFalse(old.done())
            self.assertEqual(self.actions(), ["status", "set-capture-mode", "status"])
            self.assertEqual(self.settings(), {**self.initial, "capture_mode": "game"})
        finally:
            old.cancel()
            await asyncio.gather(old, return_exceptions=True)

    async def test_disconnected_and_repeated_callers_share_the_owned_bounded_edit(self):
        self.options["command_delay"] = 0.3
        self.write_options()
        caller = asyncio.create_task(self.plugin.set_capture_mode("game"))
        await self.started()
        caller.cancel()
        with self.assertRaises(asyncio.CancelledError):await caller
        current = await self.plugin.status()
        self.assertEqual(current["operation"]["action"], "set-capture-mode")
        duplicate = await self.plugin.set_capture_mode("game")
        self.assertTrue(duplicate["action_result"]["ok"])
        self.assertEqual(self.actions().count("set-capture-mode"), 1)
        self.assertEqual(self.settings()["stream_key"], self.initial["stream_key"])

    async def test_stop_signals_waiting_capture_without_starting_any_output_or_a_late_write(self):
        self.options["command_delay"] = 1
        self.write_options()
        caller = asyncio.create_task(self.plugin.set_capture_mode("game"))
        await self.started()
        stopped, edited = await asyncio.gather(self.plugin.stop(), caller)
        self.assertEqual(stopped["action_result"]["action"], "stop")
        self.assertFalse(edited["action_result"]["ok"])
        self.assertEqual(self.settings(), self.initial)
        self.assertNotIn("start", self.actions())
        await asyncio.sleep(0.1)
        self.assertEqual(self.settings(), self.initial)

    async def test_timeout_after_commit_keeps_saved_pair_and_reports_unconfirmed_instead_of_rollback(self):
        self.options.update(post_action_delay=2, ignore_sigint=True)
        self.write_options()
        result = await asyncio.wait_for(self.plugin.set_capture_mode("game"), 3)
        self.assertFalse(result["action_result"]["ok"])
        self.assertEqual(result["settings"]["capture_mode"], "game")
        self.assertEqual(self.settings(), {**self.initial, "capture_mode": "game"})

    async def test_ack_without_fresh_matching_readback_is_not_reported_as_success(self):
        self.options["wrong_readback"] = True
        self.write_options()
        result = await self.plugin.set_capture_mode("game")
        self.assertFalse(result["action_result"]["ok"])
        self.assertIn("fresh settings", result["action_result"]["message"])
        self.assertEqual(self.settings()["capture_mode"], "game")

    async def test_late_spawn_attachment_never_receives_execution_permission(self):
        original = backend.asyncio.create_subprocess_exec
        async def delayed(*args, **kwargs):
            await asyncio.sleep(0.15)
            return await original(*args, **kwargs)
        with patch.dict(backend.CAPTURE_MODE_BUDGET, {"preflight": 0.03, "readback": 0.03}), \
                patch.object(backend.asyncio, "create_subprocess_exec", side_effect=delayed):
            result = await self.plugin.set_capture_mode("game")
        self.assertFalse(result["action_result"]["ok"])
        await asyncio.sleep(0.25)
        if self.plugin._cleanup_tasks:await asyncio.gather(*self.plugin._cleanup_tasks)
        self.assertEqual(self.actions(), [])
        self.assertEqual(self.settings(), self.initial)

    async def test_inherited_stdout_cannot_extend_capture_cleanup_after_owned_leader_exit(self):
        self.options["inherit_stdout"] = True
        self.write_options()
        began = time.monotonic()
        result = await asyncio.wait_for(self.plugin.set_capture_mode("game"), 3)
        self.assertFalse(result["action_result"]["ok"])
        self.assertLess(time.monotonic() - began, 2.5)
        self.assertFalse(self.plugin._children)
        self.assertEqual(self.settings(), self.initial)

    async def test_unconfirmed_leader_exit_retains_same_pending_operation_until_reaped(self):
        released, killed = asyncio.Event(), asyncio.Event()

        class DelayedExit:
            returncode = None
            stdout = stderr = None

            async def communicate(self, _input=None):
                await asyncio.Future()

            def send_signal(self, _signal):
                pass

            def kill(self):
                killed.set()

            async def wait(self):
                await released.wait()
                self.returncode = -9
                return self.returncode

        original = backend.asyncio.create_subprocess_exec
        child = DelayedExit()

        async def spawn(*args, **kwargs):
            return child if args[-1] == "set-capture-mode" else await original(*args, **kwargs)

        with patch.dict(backend.CAPTURE_MODE_BUDGET, {"command": 0.1}), \
                patch.object(backend.asyncio, "create_subprocess_exec", side_effect=spawn):
            caller = asyncio.create_task(self.plugin.set_capture_mode("game"))
            await asyncio.wait_for(killed.wait(), 2)
            try:
                self.assertFalse(caller.done())
                self.assertTrue(self.plugin.busy)
                observed = await self.plugin.status()
                self.assertEqual(observed["operation"]["action"], "set-capture-mode")
                self.assertEqual(observed["operation"]["id"], self.plugin._operation_id)
                self.assertEqual(observed["operation"]["state"], "running")
            finally:
                released.set()
            result = await asyncio.wait_for(caller, 2)
        self.assertFalse(result["action_result"]["ok"])
        self.assertFalse(self.plugin.busy)


if __name__ == "__main__":
    unittest.main()
