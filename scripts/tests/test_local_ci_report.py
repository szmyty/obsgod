"""Exercise report integrity, real log formats and exact-source matrix boundaries."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("local_ci_report", Path(__file__).parents[1] / "local-ci-report.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
REVISION = "a" * 40


def receipt(state, stamp, action, log, result="passed", revision=REVISION, **extra):
    path = state / (stamp + "-" + action + ".json")
    path.with_suffix(".log").write_text(log)
    data = {"revision": revision, "source_tree": "b" * 40, "dirty": False,
            "started_utc": stamp, "action": action, "result": result,
            "exit_code": 0 if result == "passed" else 1,
            "log_sha256": hashlib.sha256(log.encode()).hexdigest(),
            "command": ["/fixture/act", "push", "-W", ".github/workflows/build.yml", "-j", action],
            "workflow_sha256": {"build.yml": "c" * 64}, "act": "act version 0.2.97",
            "act_binary_sha256": "d" * 64, "actrc_sha256": "e" * 64,
            "runner_image": "example.invalid/runner@sha256:" + "f" * 64,
            **extra}
    path.write_text(json.dumps(data))
    return path


def json_log(*messages):
    return "".join(json.dumps({"level": "info", "msg": value}) + "\n" for value in messages)


class LocalCIReportTests(unittest.TestCase):
    def test_json_failures_preserve_counts_hashes_and_provider_raw_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            for index in (1, 2):
                log = json_log("⭐ Run Main Compile", json.dumps({"Action": "pass", "Package": "example/pkg", "Test": "TestGood"}),
                               json.dumps({"Action": "skip", "Package": "example/pkg", "Test": "TestOptional"}),
                               json.dumps({"Action": "fail", "Package": "example/pkg", "Test": "TestBad"}),
                               "error: EACCES permission denied /tmp/run" + str(index) + "/output",
                               "❌ Failure - Main Compile [1s]", "🏁 Job failed")
                receipt(state, "20261113T10000" + str(index) + "Z", "build", log, "failed")
            provider = receipt(state, "20261113T100003Z", "dependency-review",
                               json_log("⭐ Run Main Dependency review", "::error::Dependency review is not supported on this repository",
                                        "❌ Failure - Main Dependency review [1s]"), "failed")
            data = json.loads(provider.read_text())
            data.update(source_revision=data.pop("revision"), job=data.pop("action"), outcome="unavailable")
            data.pop("result")
            provider.write_text(json.dumps(data))
            report = REPORT.build_report(state, REVISION)
            self.assertEqual(report["result"], "failed")
            self.assertEqual(report["counts"]["raw_results"], {"failed": 3})
            self.assertEqual(len(report["failure_groups"]), 2)
            permission = next(group for group in report["failure_groups"] if group["category"] == "environment_permissions")
            self.assertEqual(len(permission["occurrences"]), 2)
            provider_group = next(group for group in report["failure_groups"] if group["category"] == "provider_gate")
            self.assertEqual(provider_group["raw_result"], "failed")
            self.assertEqual(report["external_gates"][0]["status"], "unavailable")
            self.assertEqual(report["external_gates"][0]["raw_results"], ["failed"])
            first = report["runs"][0]
            self.assertEqual(first["observations"]["counts"]["go_test_events"], {"passed": 1, "skipped": 1, "failed": 1})
            self.assertEqual(first["provenance"]["act_binary_sha256"], "d" * 64)
            self.assertEqual(first["provenance"]["actrc_sha256"], "e" * 64)
            self.assertEqual(first["runner_digest_sha256"], "f" * 64)
            self.assertTrue(permission["reproduction"]["command"])
            self.assertEqual(permission["reproduction"]["command"][-2:], ["--act", "/fixture/act"])
            self.assertIn(".log:", REPORT.markdown(report))
            self.assertNotIn("file://", REPORT.markdown(report))

    def test_plain_pass_keeps_negative_controls_diagnostic_and_real_summary_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            log = "\n".join(["[build/build] ⭐ Run Main Fixtures", "[build/build] | error: expected rejected fixture",
                              "[build/build] | Ran 7 tests in 0.01s", "[build/build] | OK (skipped=1)",
                              "[build/build] | ℹ tests 3", "[build/build] | ℹ pass 3", "[build/build] | ℹ fail 0",
                              "[build/build] | ℹ skipped 0", "[build/build] ✅ Success - Main Fixtures [1s]", ""])
            receipt(state, "20261113T100001Z", "build", log)
            report = REPORT.build_report(state, REVISION)
            self.assertFalse(report["failure_groups"])
            observations = report["runs"][0]["observations"]
            self.assertEqual(observations["summaries"][0]["tests"], 7)
            self.assertEqual(observations["summaries"][0]["passed"], 6)
            self.assertEqual(observations["summaries"][0]["skipped"], 1)
            self.assertEqual(observations["summaries"][1]["passed"], 3)
            self.assertEqual(len(observations["diagnostics"]), 1)
            self.assertEqual(next(row for row in report["local_matrix"] if row["action"] == "build")["status"], "passed")
            self.assertEqual(sum(row["status"] == "unrun" for row in report["local_matrix"]), 5)

    def test_log_hash_mismatch_never_consumes_or_qualifies_the_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            path = receipt(state, "20261113T100001Z", "build", "original\n")
            path.with_suffix(".log").write_text("❌ Failure - injected unverified content\n")
            report = REPORT.build_report(state, REVISION)
            self.assertEqual(report["result"], "failed")
            self.assertEqual(report["runs"][0]["status"], "unavailable")
            self.assertIsNone(report["runs"][0]["observations"])
            self.assertFalse(report["failure_groups"])
            self.assertEqual(report["evidence_errors"][0]["reason"], "adjacent_log_sha256_mismatch")
            self.assertNotIn("injected unverified", json.dumps(report))

    def test_source_filter_clean_coverage_and_pr_static_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            for index, action in enumerate(REPORT.CI.JOBS):
                receipt(state, "20261113T10000" + str(index) + "Z", action, "✅ Success - Complete job\n")
            wrong = receipt(state, "20261113T110001Z", "build", "wrong source\n", "failed", revision="0" * 40)
            wrong.with_suffix(".log").write_text("wrong-source tampering must not affect selected source\n")
            receipt(state, "20261113T110002Z", "lint", "✅ Success - Complete job\n", pull_request_fixture=True)
            report = REPORT.build_report(state, REVISION)
            self.assertEqual(report["local_result"], "passed")
            self.assertEqual(report["overall_result"], "partial")
            self.assertEqual(report["counts"]["local_matrix"], {"passed": 6})
            self.assertEqual(len(report["pr_static_runs"]), 1)
            self.assertEqual(len(report["excluded_other_revision_receipts"]), 1)
            self.assertFalse(report["evidence_errors"])
            self.assertTrue(all(gate["status"] == "unrun" for gate in report["external_gates"]))
            dirty_state = state / "dirty"
            dirty_state.mkdir()
            receipt(dirty_state, "20261113T110003Z", "build", "✅ Success\n", dirty=True)
            dirty = REPORT.build_report(dirty_state, REVISION)
            self.assertEqual(dirty["runs"][0]["raw_result"], "passed")
            self.assertFalse(dirty["runs"][0]["qualifies_clean_source"])
            self.assertEqual(dirty["local_matrix"][0]["status"], "unavailable")

    def test_diagnostic_metadata_and_provider_gate_do_not_change_six_job_success(self):
        with tempfile.TemporaryDirectory(prefix="local ci report ") as temporary:
            state = Path(temporary) / "state"
            state.mkdir()
            for index, action in enumerate(REPORT.CI.JOBS):
                receipt(state, "20261113T10000" + str(index) + "Z", action, "✅ Success - Complete job\n")
            (state / "1a482808-native-image-platform.json").write_text(json.dumps({
                "revision": REVISION, "command": ["docker", "image", "inspect", "fixture"],
                "exit_code": 0, "source_clean_after": True}))
            provider = receipt(state, "20261113T110001Z", "dependency-review", json_log(
                "⭐ Run Main Dependency review", "::error::Dependency review is not supported on this repository",
                "❌ Failure - Main Dependency review [1s]"), "failed")
            data = json.loads(provider.read_text())
            data.update(job=data.pop("action"), outcome="unavailable")
            data.pop("result")
            provider.write_text(json.dumps(data))
            report = REPORT.build_report(state, REVISION)
            self.assertEqual(report["local_result"], "passed")
            self.assertEqual(report["overall_result"], "partial")
            self.assertEqual(report["counts"]["local_matrix"], {"passed": 6})
            self.assertFalse(report["evidence_errors"])
            self.assertEqual(len(report["runs"]), 7)
            self.assertEqual(report["external_gates"][0]["raw_results"], ["failed"])
            output = Path(temporary) / "report"
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(REPORT.main(["--state", str(state), "--revision", REVISION, "--output", str(output)]), 0)
            markdown = (output / "report.md").read_text()
            self.assertIn("Local result: **passed** · Overall: **partial**", markdown)
            self.assertNotIn("file://", markdown)
            self.assertIn("%20", markdown)

    def test_cli_writes_both_outputs_without_overwriting_prior_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"
            state.mkdir()
            receipt(state, "20261113T100001Z", "build",
                    json_log('expected error: connect https://user:private-fixture-password@example.invalid/path'))
            output = Path(temporary) / "report"
            arguments = ["--state", str(state), "--revision", REVISION, "--output", str(output)]
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(REPORT.main(arguments), 1)  # other five jobs remain unrun
            self.assertTrue((output / "report.json").is_file())
            self.assertTrue((output / "report.md").is_file())
            before = (output / "report.json").read_bytes()
            self.assertNotIn(b"private-fixture-password", before)
            with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as stopped:
                REPORT.main(arguments)
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual((output / "report.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
