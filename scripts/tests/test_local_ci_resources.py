"""Resource refusals and cache isolation must precede workflow side effects."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("resource_ci", Path(__file__).parents[1] / "local-ci.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)
R = CI.RESOURCES


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        self.scratch = self.base / "scratch"
        self.scratch.mkdir(mode=0o700)
        self.real_metadata = R.docker_metadata
        metadata = patch.object(R, "docker_metadata", return_value={"driver": "overlay2", "image_size_bytes": 1024})
        metadata.start()
        self.addCleanup(metadata.stop)
        capacity = patch.object(R, "disk", return_value={"available_bytes": 20 * R.GIB, "device": 1})
        capacity.start()
        self.addCleanup(capacity.stop)

    def attempt(self):
        return R.allocate_attempt(self.scratch, "fixture", self.checkout)

    def probe(self, command, **kwargs):
        source = next(value for value in command if value.startswith("type=bind,src="))
        attempt = Path(source.split("src=", 1)[1].split(",dst=", 1)[0])
        marker = (attempt / ".daemon-volume-probe").read_text()
        (attempt / ".daemon-volume-probe-output").write_text(marker)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"marker": marker,
            "docker_root": {"available_bytes": 8 * R.GIB}, "scratch": {"available_bytes": 8 * R.GIB}}))

    def test_preflight_records_exact_shortfall_before_any_workflow(self):
        attempt = self.attempt()
        def disk(path):
            return {"available_bytes": 3 * R.GIB if Path(path) == self.checkout else 8 * R.GIB,
                    "total_bytes": 32 * R.GIB, "device": 1 if Path(path) == self.checkout else 2}
        with patch.object(R, "disk", side_effect=disk), patch.object(R.subprocess, "run", side_effect=self.probe) as run:
            receipt = R.preflight(self.checkout, attempt, CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "refused")
        self.assertEqual(receipt["shortfalls"], [{"location": "host_root", "available_bytes": 3 * R.GIB,
            "required_bytes": 4 * R.GIB, "missing_bytes": R.GIB}])
        run.assert_not_called()
        self.assertEqual(receipt["probe"]["status"], "unrun")
        self.assertFalse((attempt / ".daemon-volume-probe").exists())

    def test_sufficient_capacity_checks_actual_owner_read_write_with_cached_image(self):
        attempt = self.attempt()
        with patch.object(R.subprocess, "run", side_effect=self.probe) as run:
            receipt = R.preflight(self.checkout, attempt, CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "passed")
        command = run.call_args.args[0]
        self.assertIn("--pull=never", command)
        self.assertEqual(command[command.index("--host") + 1], "unix:///var/run/docker.sock")
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertEqual(command[command.index("--user") + 1], f"{os.getuid()}:{os.getgid()}")
        self.assertTrue(receipt["owner_write_verified"])
        self.assertFalse((attempt / ".daemon-volume-probe").exists())
        self.assertFalse((attempt / ".daemon-volume-probe-output").exists())

    def test_vfs_copy_budget_refuses_before_creating_container(self):
        size = 1_624_696_918
        available = 5 * R.GIB
        def disk(path):
            return {"available_bytes": available if Path(path) == self.checkout else 8 * R.GIB,
                    "device": 1 if Path(path) == self.checkout else 2}
        with patch.object(R, "docker_metadata", return_value={"driver": "vfs", "image_size_bytes": size}) as metadata, \
                patch.object(R, "disk", side_effect=disk), patch.object(R.subprocess, "run") as run:
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        metadata.assert_called_once()
        run.assert_not_called()
        self.assertEqual(receipt["status"], "refused")
        self.assertEqual(receipt["requirements"]["root_bytes"], 4 * R.GIB + 2 * size)
        self.assertEqual(receipt["shortfalls"], [{"location": "host_root", "available_bytes": available,
            "required_bytes": 4 * R.GIB + 2 * size, "missing_bytes": 4 * R.GIB + 2 * size - available}])
        self.assertEqual(receipt["probe"]["status"], "unrun")

    def test_same_vfs_filesystem_combines_scratch_and_runner_allocation(self):
        size = 1_624_696_918
        with patch.object(R, "docker_metadata", return_value={"driver": "vfs", "image_size_bytes": size}), \
                patch.object(R, "disk", return_value={"available_bytes": 11 * R.GIB, "device": 1}), \
                patch.object(R.subprocess, "run") as run:
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        run.assert_not_called()
        self.assertEqual(receipt["status"], "refused")
        self.assertEqual(receipt["requirements"]["same_filesystem_bytes"], 10 * R.GIB + 2 * size)
        self.assertTrue(all(row["required_bytes"] == 10 * R.GIB + 2 * size for row in receipt["shortfalls"]))

    def test_metadata_is_cached_local_only_and_does_not_create_container(self):
        results = [SimpleNamespace(returncode=0, stdout='"vfs"'), SimpleNamespace(returncode=0, stdout='1624696918')]
        with patch.object(R.subprocess, "run", side_effect=results) as run:
            metadata = self.real_metadata(CI.IMAGE, {"HTTP_PROXY": "preserved"})
        self.assertEqual(metadata["driver"], "vfs")
        self.assertEqual(metadata["image_size_bytes"], 1_624_696_918)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:3], ["docker", "--host", "unix:///var/run/docker.sock"])
            self.assertNotIn("run", command)
            self.assertNotIn("pull", command)

    def test_same_filesystem_requires_combined_budget(self):
        with patch.object(R, "disk", return_value={"available_bytes": 9 * R.GIB, "device": 1}), \
                patch.object(R.subprocess, "run", side_effect=self.probe):
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "refused")
        self.assertEqual([row["required_bytes"] for row in receipt["shortfalls"]], [10 * R.GIB, 10 * R.GIB])

    def test_daemon_cannot_fake_host_visibility(self):
        def wrong_marker(command, **kwargs):
            value = self.probe(command, **kwargs)
            payload = json.loads(value.stdout)
            payload["marker"] = "different daemon filesystem"
            value.stdout = json.dumps(payload)
            return value
        with patch.object(R.subprocess, "run", side_effect=wrong_marker):
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIn("cannot observe", receipt["reason"])
        self.assertEqual(receipt["probe"]["status"], "failed")
        self.assertEqual(receipt["probe"]["exit_code"], 0)

    def test_owner_write_failure_is_unavailable_before_workflow(self):
        def no_write(command, **kwargs):
            value = self.probe(command, **kwargs)
            source = next(part for part in command if part.startswith("type=bind,src="))
            attempt = Path(source.split("src=", 1)[1].split(",dst=", 1)[0])
            (attempt / ".daemon-volume-probe-output").unlink()
            return value
        with patch.object(R.subprocess, "run", side_effect=no_write):
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIn("cannot write", receipt["reason"])
        self.assertEqual(receipt["probe"]["status"], "failed")
        self.assertEqual(receipt["probe"]["exit_code"], 0)

    def test_missing_daemon_is_unavailable_not_capacity_or_check_pass(self):
        with patch.object(R.subprocess, "run", side_effect=OSError("fixture missing daemon")):
            receipt = R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIsNone(receipt["probe"]["exit_code"])

    def test_repeated_attempts_have_fresh_temp_and_evidence(self):
        first, second = self.attempt(), self.attempt()
        (first / "tmp" / "unfinished.json").write_text("partial old evidence")
        self.assertNotEqual(first, second)
        self.assertEqual(list((second / "tmp").iterdir()), [])
        self.assertEqual((first / "tmp" / "unfinished.json").read_text(), "partial old evidence")

    def test_scratch_symlinks_checkout_or_foreign_permissions_refused(self):
        link = self.base / "link"
        link.symlink_to(self.scratch, target_is_directory=True)
        for path in (link / "child", self.checkout / "output"):
            with self.assertRaises(ValueError):
                R.allocate_attempt(path, "fixture", self.checkout)
        self.scratch.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "owned private"):
            self.attempt()

    def test_traversal_and_unprotected_ancestor_refused_before_mkdir(self):
        escaped = self.scratch / ".." / "checkout" / "inside"
        with self.assertRaisesRegex(ValueError, "traversal"):
            R.allocate_attempt(escaped, "fixture", self.checkout)
        self.assertFalse((self.checkout / "inside").exists())
        self.scratch.chmod(0o777)
        with self.assertRaisesRegex(ValueError, "unprotected"):
            R.allocate_attempt(self.scratch / "new-child", "fixture", self.checkout)
        self.assertFalse((self.scratch / "new-child").exists())

    def test_probe_never_uses_remote_context_or_host(self):
        values = {"DOCKER_HOST": "tcp://invalid.example:1234", "DOCKER_CONTEXT": "wrong-context",
                  "DOCKER_TLS_VERIFY": "1", "DOCKER_CERT_PATH": "/private/certs", "HTTP_PROXY": "preserved"}
        with patch.dict(os.environ, values, clear=True), patch.object(R.subprocess, "run", side_effect=self.probe) as run:
            R.preflight(self.checkout, self.attempt(), CI.IMAGE, "a" * 40)
        actual = run.call_args.kwargs["env"]
        self.assertEqual(actual, {"HTTP_PROXY": "preserved"})

    def environment(self, attempt):
        return {"OBSGOD_LOCAL_PROFILE": "constrained", "OBSGOD_LOCAL_SCRATCH": str(attempt),
                "OBSGOD_LOCAL_RESOURCE_RECEIPT": str(attempt / "resource-policy.json"),
                "OBSGOD_LOCAL_OWNER_UID": str(os.getuid()), "GOCACHE": str(attempt / "go-build-root")}

    def test_trim_refuses_host_cache_before_executing_go(self):
        attempt = self.attempt()
        env = self.environment(attempt)
        env["GOCACHE"] = str(self.base / "host-cache")
        with patch.dict(os.environ, env, clear=True), patch.object(R.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "exact private"):
                R.trim_compiler_cache()
        run.assert_not_called()

    def test_trim_is_opt_in_and_preserves_modules_artifacts_evidence(self):
        attempt = self.attempt()
        cache = attempt / "go-build-root"
        user_cache = attempt / ("go-build-user-" + str(os.getuid()))
        user_cache.mkdir()
        for path in (cache, user_cache):
            (path / "object.a").write_bytes(b"disposable compiler cache")
        sentinels = [attempt / name for name in ("modules", "artifact.zip", "preflight.json")]
        for sentinel in sentinels:
            sentinel.write_text("preserve exactly")
        def clean(command, **kwargs):
            self.assertEqual(command, ["go", "clean", "-cache"])
            actual = Path(kwargs["env"]["GOCACHE"])
            self.assertIn(actual, [cache, user_cache])
            (actual / "object.a").unlink()
            return SimpleNamespace(returncode=0)
        with patch.dict(os.environ, self.environment(attempt), clear=True), \
                patch.object(R, "active_compilers", return_value=[]), \
                patch.object(R.subprocess, "check_output", side_effect=lambda command, **kwargs: kwargs["env"]["GOCACHE"]), \
                patch.object(R.subprocess, "run", side_effect=clean):
            self.assertEqual(R.trim_compiler_cache(), 0)
        receipt = json.loads((attempt / "resource-policy.json").read_text())
        self.assertTrue(receipt["completed"])
        self.assertEqual(len(receipt["phases"]), 2)
        self.assertTrue(all(row["before"]["bytes"] > 0 and row["after"]["bytes"] == 0 for row in receipt["phases"]))
        self.assertTrue(all(sentinel.read_text() == "preserve exactly" for sentinel in sentinels))
        with patch.dict(os.environ, {}, clear=True), patch.object(R.subprocess, "run") as run:
            self.assertEqual(R.trim_compiler_cache(), 0)
        run.assert_not_called()

    def test_trim_rejects_unexpected_user_cache_without_mutation(self):
        attempt = self.attempt()
        (attempt / "go-build-user-999999").mkdir()
        with patch.dict(os.environ, self.environment(attempt), clear=True), patch.object(R.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                R.trim_compiler_cache()
        run.assert_not_called()

    def test_trim_waits_for_all_compiler_consumers(self):
        attempt = self.attempt()
        with patch.dict(os.environ, self.environment(attempt), clear=True), \
                patch.object(R, "active_compilers", return_value=[{"pid": 123, "name": "go"}]), \
                patch.object(R.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "still active"):
                R.trim_compiler_cache()
        run.assert_not_called()


class MatrixTests(unittest.TestCase):
    setUp = ResourceTests.setUp

    def git(self, *arguments):
        return "" if arguments[0] == "status" else "a" * 40

    def args(self):
        return SimpleNamespace(scratch=self.scratch, act=self.base / "act")

    def test_refusal_leaves_all_jobs_unrun_and_old_sessions_intact(self):
        state = self.base / "state"
        old = state / "sessions" / "old"
        old.mkdir(parents=True)
        (old / "partial.json").write_text("old unfinished run")
        with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                patch.object(R, "preflight", return_value={"status": "refused"}), patch.object(CI.subprocess, "run") as run:
            self.assertEqual(CI.matrix(self.args(), state), 3)
        run.assert_not_called()
        self.assertEqual((old / "partial.json").read_text(), "old unfinished run")
        session = next(path for path in (state / "sessions").iterdir() if path != old)
        receipt = json.loads((session / "session.json").read_text())
        self.assertFalse(receipt["completed"])
        self.assertTrue(all(row["result"] == "unrun" for row in receipt["jobs"]))

    def test_zero_exit_without_receipt_is_not_a_passing_matrix(self):
        with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                patch.object(R, "preflight", return_value={"status": "passed"}), \
                patch.object(CI.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(CI.matrix(self.args(), self.base / "state"), 1)
        self.assertEqual(run.call_count, 1)

    def test_six_jobs_are_serial_and_require_actual_completed_receipts(self):
        order = []
        def child(command, **kwargs):
            action = command[2]
            order.append(action)
            state = Path(command[command.index("--state") + 1])
            prefix = state / ("20261118T000000Z-" + action)
            prefix.with_suffix(".log").write_text("actual fixture job completed\n")
            prefix.with_suffix(".json").write_text(json.dumps({"action": action, "revision": "a" * 40, "source_tree": "a" * 40,
                "dirty": False, "result": "passed", "exit_code": 0, "log_sha256": CI.sha(prefix.with_suffix(".log").read_bytes())}))
            return SimpleNamespace(returncode=0)
        state = self.base / "state"
        with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                patch.object(R, "preflight", return_value={"status": "passed"}), patch.object(CI.subprocess, "run", side_effect=child):
            self.assertEqual(CI.matrix(self.args(), state), 0)
        self.assertEqual(order, list(CI.MATRIX_ORDER))
        receipt = json.loads(next(state.glob("sessions/*/session.json")).read_text())
        self.assertTrue(receipt["completed"])
        self.assertTrue(all(row["receipt"] for row in receipt["jobs"]))

    def test_malformed_receipt_is_failed_integrity_not_a_running_session(self):
        def child(command, **kwargs):
            state = Path(command[command.index("--state") + 1])
            (state / "20261118T000000Z-lint.json").write_text("broken JSON")
            return SimpleNamespace(returncode=0)
        state = self.base / "state"
        with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                patch.object(R, "preflight", return_value={"status": "passed"}), patch.object(CI.subprocess, "run", side_effect=child):
            self.assertEqual(CI.matrix(self.args(), state), 1)
        receipt = json.loads(next(state.glob("sessions/*/session.json")).read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertFalse(receipt["completed"])

    def test_missing_or_different_action_cannot_qualify_expected_job(self):
        for action in (None, "candidate"):
            with self.subTest(action=action):
                state = self.base / ("state-" + str(action))
                def child(command, **kwargs):
                    directory = Path(command[command.index("--state") + 1])
                    prefix = directory / "20261118T000000Z-lint"
                    prefix.with_suffix(".log").write_text("completed another check\n")
                    value = {"revision": "a" * 40, "source_tree": "a" * 40, "dirty": False,
                             "result": "passed", "exit_code": 0, "log_sha256": CI.sha(prefix.with_suffix(".log").read_bytes())}
                    if action is not None:
                        value["action"] = action
                    prefix.with_suffix(".json").write_text(json.dumps(value))
                    return SimpleNamespace(returncode=0)
                with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                        patch.object(R, "preflight", return_value={"status": "passed"}), patch.object(CI.subprocess, "run", side_effect=child) as run:
                    self.assertEqual(CI.matrix(self.args(), state), 1)
                self.assertEqual(run.call_count, 1)

    def test_per_job_capacity_refusal_keeps_workflow_unrun(self):
        def child(command, **kwargs):
            scratch = Path(command[command.index("--scratch") + 1]) / "job-refused"
            scratch.mkdir()
            (scratch / "preflight.json").write_text(json.dumps({"profile": "constrained", "revision": "a" * 40, "status": "refused"}))
            return SimpleNamespace(returncode=3)
        state = self.base / "state"
        with patch.object(CI, "ROOT", self.checkout), patch.object(CI, "git", side_effect=self.git), \
                patch.object(R, "preflight", return_value={"status": "passed"}), patch.object(CI.subprocess, "run", side_effect=child):
            self.assertEqual(CI.matrix(self.args(), state), 3)
        receipt = json.loads(next(state.glob("sessions/*/session.json")).read_text())
        self.assertEqual(receipt["result"], "unavailable")
        self.assertTrue(all(row["result"] == "unrun" for row in receipt["jobs"]))
        self.assertEqual(receipt["jobs"][0]["exit_code"], 3)


if __name__ == "__main__":
    unittest.main()
