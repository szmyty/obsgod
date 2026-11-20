"""Real ref binding, bounded GETs and public-safe service/billing observations."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SPEC = importlib.util.spec_from_file_location("destination_readiness", Path(__file__).parents[1] / "destination-readiness.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
REPO = "example/deckystream"
BASE, HEAD = "a" * 40, "b" * 40
DEFAULT_TREE, HEAD_TREE = "c" * 40, "d" * 40
API = "https://api.github.com/repos/" + REPO
PRIVATE = "private-annotation-body-and-token-never-copy"
WORKFLOW = """name: lint
on: [push, pull_request]
permissions:
  contents: read
jobs:
  dependency-review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      - name: Check dependency advisories
        uses: actions/dependency-review-action@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        with:
          fail-on-severity: high
          comment-summary-in-pr: never
"""


class Response(io.BytesIO):
    def __init__(self, url, data, final_url=None):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.url = final_url or url

    def geturl(self):
        return self.url


class Fixture:
    def __init__(self):
        self.calls = []
        self.routes = {}
        self.pr_reads = self.branch_reads = 0
        self.change_pr = self.change_default = False
        self.repo = {"id": 42, "full_name": REPO, "private": False, "visibility": "public", "fork": False,
                     "archived": False, "default_branch": "main", "permissions": {"admin": True, "pull": True, "push": True},
                     "arbitrary_private_server_field": PRIVATE}
        self.pr = {"number": 17, "state": "open", "draft": False, "body": PRIVATE,
                   "base": {"sha": BASE, "repo": copy.deepcopy(self.repo)},
                   "head": {"sha": HEAD, "repo": copy.deepcopy(self.repo)}}
        go = b"module example.invalid/deckystream\n\ngo 1.27.4\nrequire example.invalid/module v1.0.0\n"
        npm = json.dumps({"lockfileVersion": 3, "packages": {"": {}, "node_modules/example": {"version": "1.0.0"}}}).encode()
        self.entries = []
        for path, raw in {"go.mod": go, "steamdeck/decky/package-lock.json": npm,
                          ".github/workflows/lint.yml": WORKFLOW.encode()}.items():
            sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            self.entries.append({"path": path, "sha": sha, "type": "blob", "mode": "100644"})
            self.routes[API + "/git/blobs/" + sha] = {"sha": sha, "encoding": "base64", "size": len(raw),
                                                     "content": base64.b64encode(raw).decode()}
        self.routes.update({
            API: self.repo,
            API + "/git/commits/" + BASE: {"sha": BASE, "tree": {"sha": DEFAULT_TREE}},
            API + "/git/commits/" + HEAD: {"sha": HEAD, "tree": {"sha": HEAD_TREE}},
            API + "/git/trees/" + DEFAULT_TREE + "?recursive=1": {"sha": DEFAULT_TREE, "truncated": False, "tree": self.entries},
            API + "/git/trees/" + HEAD_TREE + "?recursive=1": {"sha": HEAD_TREE, "truncated": False, "tree": self.entries},
            API + "/dependency-graph/sbom": {"sbom": {"packages": [
                {"externalRefs": [{"referenceLocator": "pkg:golang/example.invalid/module@v1.0.0"}]},
                {"externalRefs": [{"referenceLocator": "pkg:npm/example@1.0.0"}]}], "private_field": PRIVATE}},
            API + "/dependency-graph/compare/" + BASE + "..." + HEAD: [
                {"manifest": "go.mod", "ecosystem": "Go", "vulnerabilities": [], "arbitrary_field": PRIVATE},
                {"manifest": "steamdeck/decky/package-lock.json", "ecosystem": "npm", "vulnerabilities": []}],
            API + "/commits/" + HEAD + "/check-runs?per_page=100": {"total_count": 1, "check_runs": [
                {"id": 9001, "name": "dependency-review", "head_sha": HEAD, "app": {"slug": "github-actions"},
                 "details_url": "https://github.com/" + REPO + "/actions/runs/501/job/101"}]},
            API + "/actions/jobs/101": {"id": 101, "run_id": 501, "head_sha": HEAD, "workflow_name": "lint",
                                       "runner_id": 123, "conclusion": "success", "steps": [{"conclusion": "success", "name": "Check dependency advisories"}]},
            API + "/actions/runs/501": {"id": 501, "head_sha": HEAD, "event": "pull_request", "path": ".github/workflows/lint.yml",
                                       "repository": {"id": 42}, "pull_requests": [{"number": 17,
                                       "base": {"sha": BASE, "repo": {"id": 42}}, "head": {"sha": HEAD, "repo": {"id": 42}}}]},
            API + "/check-runs/9001/annotations?per_page=100": [{"message": PRIVATE, "raw_details": PRIVATE}],
        })

    def open(self, request, timeout):
        self.calls.append({"url": request.full_url, "method": request.get_method(), "headers": dict(request.header_items()), "timeout": timeout})
        if request.full_url == API + "/pulls/17":
            self.pr_reads += 1
            data = copy.deepcopy(self.pr)
            if self.change_pr and self.pr_reads > 1:
                data["head"]["sha"] = "f" * 40
            return Response(request.full_url, data)
        if request.full_url == API + "/branches/main":
            self.branch_reads += 1
            return Response(request.full_url, {"commit": {"sha": "f" * 40 if self.change_default and self.branch_reads > 1 else BASE}})
        result = self.routes[request.full_url]
        if isinstance(result, int):
            raise urllib.error.HTTPError(request.full_url, result, PRIVATE, {}, io.BytesIO(PRIVATE.encode()))
        return Response(request.full_url, result)

    def api(self):
        return D.GitHub("fixture-auth-token-held-only-in-memory", self.open)

    def collect(self):
        return D.collect(self.api(), REPO, 17, {"source": "existing-gh-authentication", "credential_values_recorded": False})

    def replace_workflow(self, text):
        raw = text.encode()
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        next(e for e in self.entries if e["path"] == ".github/workflows/lint.yml")["sha"] = sha
        self.routes[API + "/git/blobs/" + sha] = {"sha": sha, "encoding": "base64", "size": len(raw),
                                                  "content": base64.b64encode(raw).decode()}


class ReadinessCollection(unittest.TestCase):
    def test_exact_real_pr_commit_tree_blob_and_job_bindings_have_bounded_get_evidence(self):
        f = Fixture()
        report = f.collect()
        self.assertEqual(report["gates"], [])
        self.assertEqual(report["readiness"], "observations-supported-review-required")
        self.assertEqual(report["pull_request"]["head_sha"], HEAD)
        self.assertEqual(report["commit_trees"], {"default": DEFAULT_TREE, "base": DEFAULT_TREE, "head": HEAD_TREE})
        self.assertTrue(report["ref_binding_stable_during_capture"])
        self.assertTrue(report["dependency_review_policy_observed"])
        self.assertTrue(report["manifest_ingestion"]["source_specific_support"])
        self.assertEqual(report["hosted"]["counts"]["observed_steps"], 1)
        self.assertEqual(report["hosted"]["review_jobs"], [101])
        text = json.dumps(report) + D.markdown(report)
        self.assertNotIn(PRIVATE, text)
        self.assertNotIn("fixture-auth-token", text)
        self.assertFalse(report["mutations_performed"])
        self.assertTrue(all(c["method"] == "GET" and c["url"].startswith(API) and 0 < c["timeout"] <= 8 for c in f.calls))
        self.assertTrue(all(c["headers"].get("Authorization", "").startswith("Bearer ") for c in f.calls))
        self.assertEqual(f.pr_reads, 2)
        self.assertEqual(f.branch_reads, 2)

    def test_private_moved_or_wrong_real_pr_is_refused_before_broad_collection(self):
        for change in ({"private": True}, {"full_name": "other/project"}):
            f = Fixture()
            f.repo.update(change)
            with self.subTest(change=change), self.assertRaises(D.ReadinessError):
                f.collect()
            self.assertEqual(len(f.calls), 1)
        f = Fixture()
        f.pr["base"]["repo"]["id"] = 99
        with self.assertRaisesRegex(D.ReadinessError, "does not belong"):
            f.collect()
        self.assertEqual(len(f.calls), 2)
        f = Fixture()
        f.pr["number"] = 18
        with self.assertRaisesRegex(D.ReadinessError, "different pull request"):
            f.collect()

    def test_exact_commit_or_blob_substitution_is_not_consumed_as_source(self):
        f = Fixture()
        f.routes[API + "/git/commits/" + HEAD]["sha"] = BASE
        with self.assertRaisesRegex(D.ReadinessError, "exact requested revision"):
            f.collect()
        f = Fixture()
        sha = f.entries[0]["sha"]
        f.routes[API + "/git/blobs/" + sha]["content"] = base64.b64encode(b"substituted bytes").decode()
        with self.assertRaisesRegex(D.ReadinessError, "Git identity"):
            f.collect()

    def test_changed_real_refs_during_capture_remain_a_gate(self):
        for name in ("change_pr", "change_default"):
            f = Fixture()
            setattr(f, name, True)
            with self.subTest(name=name):
                report = f.collect()
                self.assertFalse(report["ref_binding_stable_during_capture"])
                self.assertIn("repository-or-pr-refs-changed-or-end-check-unavailable", report["gates"])

    def test_403_comparison_and_404_sbom_are_unavailable_not_graph_disabled_or_auth_absent(self):
        f = Fixture()
        f.routes[API + "/dependency-graph/sbom"] = 404
        f.routes[API + "/dependency-graph/compare/" + BASE + "..." + HEAD] = 403
        report = f.collect()
        self.assertEqual(report["authentication"]["source"], "existing-gh-authentication")
        self.assertTrue(report["repository"]["authenticated_permissions"]["admin"])
        self.assertEqual(report["dependency_sbom"]["http_status"], 404)
        self.assertEqual(report["dependency_comparison"]["http_status"], 403)
        self.assertEqual(report["manifest_ingestion"]["graph_enabled_setting"], "not-directly-observed-by-this-collector")
        self.assertFalse(report["manifest_ingestion"]["source_specific_support"])
        self.assertEqual(report["readiness"], "unavailable-or-incomplete")
        self.assertNotIn(PRIVATE, json.dumps(report))
        self.assertEqual(sum("dependency-graph/compare" in c["url"] for c in f.calls), 1)

    def test_empty_real_comparison_does_not_prove_manifest_ingestion(self):
        f = Fixture()
        f.routes[API + "/dependency-graph/compare/" + BASE + "..." + HEAD] = []
        report = f.collect()
        self.assertEqual(report["dependency_comparison"]["status"], "available-empty")
        self.assertTrue(report["manifest_ingestion"]["repository_ecosystems_observed_in_sbom"])
        self.assertFalse(report["manifest_ingestion"]["source_specific_support"])
        self.assertIn("both-manifest-ingestion-evidence-incomplete", report["gates"])

    def test_billing_requires_annotation_empty_steps_and_no_assigned_runner(self):
        f = Fixture()
        job = f.routes[API + "/actions/jobs/101"]
        job.update(conclusion="failure", steps=[], runner_id=0)
        f.routes[API + "/check-runs/9001/annotations?per_page=100"] = [
            {"message": "The job was not started because your account is locked due to a billing issue. " + PRIVATE,
             "raw_details": PRIVATE, "title": PRIVATE}]
        report = f.collect()
        row = report["hosted"]["jobs"][0]
        self.assertEqual(row["classification"], "billing-refused-before-execution")
        self.assertEqual(report["hosted"]["counts"]["billing_refusals"], 1)
        self.assertEqual(report["hosted"]["counts"]["observed_steps"], 0)
        self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])
        self.assertNotIn(PRIVATE, json.dumps(report) + D.markdown(report))
        job["steps"] = [{"conclusion": "failure", "name": PRIVATE}]
        report = f.collect()
        self.assertEqual(report["hosted"]["counts"]["billing_refusals"], 0)
        self.assertEqual(report["hosted"]["jobs"][0]["classification"], "billing-reported-with-execution-or-identity-uncertainty")

    def test_skipped_or_zero_step_success_is_not_an_executed_review_pass(self):
        for conclusion in ("skipped", "success"):
            f = Fixture()
            f.routes[API + "/actions/jobs/101"].update(conclusion=conclusion, steps=[], runner_id=0)
            with self.subTest(conclusion=conclusion):
                report = f.collect()
                self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])
                if conclusion == "skipped":
                    self.assertEqual(report["hosted"]["jobs"][0]["classification"], "skipped-not-a-pass")

    def test_wrong_job_head_and_arbitrary_job_url_cannot_bind_hosted_acceptance(self):
        f = Fixture()
        f.routes[API + "/actions/jobs/101"]["head_sha"] = BASE
        with self.assertRaisesRegex(D.ReadinessError, "exact head"):
            f.collect()
        f = Fixture()
        f.routes[API + "/commits/" + HEAD + "/check-runs?per_page=100"]["check_runs"][0]["details_url"] = "https://evil.invalid/job/101"
        report = f.collect()
        self.assertEqual(report["hosted"]["jobs"][0]["reason"], "job-url-unbound")
        self.assertTrue(all("evil.invalid" not in c["url"] for c in f.calls))

    def test_review_requires_exact_pr_event_base_head_workflow_and_actual_action_step(self):
        for changes in ({"event": "push"}, {"path": ".github/workflows/other.yml"},
                        {"pull_requests": []}, {"head_sha": BASE}):
            f = Fixture()
            f.routes[API + "/actions/runs/501"].update(changes)
            with self.subTest(changes=changes):
                report = f.collect()
                self.assertFalse(report["hosted"]["jobs"][0]["exact_pr_run_binding"])
                self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])
        for changed_field in ("number", "base", "head"):
            f = Fixture()
            run_pr = f.routes[API + "/actions/runs/501"]["pull_requests"][0]
            if changed_field == "number":
                run_pr[changed_field] = 99
            else:
                run_pr[changed_field]["sha"] = "f" * 40
            with self.subTest(changed_field=changed_field):
                self.assertFalse(f.collect()["hosted"]["jobs"][0]["exact_pr_run_binding"])
        f = Fixture()
        f.routes[API + "/actions/jobs/101"]["steps"] = [{"name": "Set up job", "conclusion": "success"},
                                                        {"name": "Check dependency advisories", "conclusion": "skipped"}]
        report = f.collect()
        self.assertTrue(report["hosted"]["jobs"][0]["exact_pr_run_binding"])
        self.assertFalse(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
        self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_duplicate_runtime_label_cannot_replace_skipped_or_absent_actual_review(self):
        for later in ("skipped", "success", None):
            f = Fixture()
            steps = [{"name": "Check dependency advisories", "conclusion": "success"}]
            if later is not None:
                steps.append({"name": "Check dependency advisories", "conclusion": later})
            else:
                # Actual action is absent; source discloses the unrelated same-name step.
                f.replace_workflow(WORKFLOW.replace("      - name: Check dependency advisories", "      - name: Check dependency advisories\n        run: echo unrelated\n      - name: Check dependency advisories"))
            f.routes[API + "/actions/jobs/101"]["steps"] = steps
            with self.subTest(actual_review=later):
                report = f.collect()
                row = report["hosted"]["jobs"][0]
                self.assertTrue(row["exact_pr_run_binding"])
                self.assertFalse(row["review_action_step_succeeded"])
                self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])
                if later is None:
                    self.assertFalse(row["review_step_source_label_unique"])
                else:
                    self.assertEqual(row["review_step_runtime_match_count"], 2)

    def test_duplicate_source_labels_and_unknown_labels_cannot_prove_review_execution(self):
        for extra in ("      - name: Check dependency advisories\n        run: echo unrelated\n",
                      "      - run: echo unnamed-step-has-unconfirmed-label\n"):
            f = Fixture()
            f.replace_workflow(WORKFLOW.replace("      - name: Check dependency advisories", extra + "      - name: Check dependency advisories"))
            # A single successful matching runtime label is still ambiguous in source.
            report = f.collect()
            target = report["workflows"][0]["dependency_review_jobs"][0]
            self.assertFalse(target["review_step_label_unique"])
            self.assertFalse(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
            self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_review_name_after_uses_is_bound_and_differently_named_setup_cannot_substitute(self):
        f = Fixture()
        f.replace_workflow(WORKFLOW.replace("      - name: Check dependency advisories\n        uses:", "      - uses:")
                           .replace("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n        name: Check dependency advisories\n"))
        report = f.collect()
        target = report["workflows"][0]["dependency_review_jobs"][0]
        self.assertEqual(target["review_step_name"], "Check dependency advisories")
        self.assertTrue(target["review_step_label_unique"])
        self.assertTrue(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
        for steps in ([{"name": "Set up job", "conclusion": "success"}],
                      [{"name": "Set up job", "conclusion": "success"}, {"name": "Check dependency advisories", "conclusion": "skipped"}]):
            f.routes[API + "/actions/jobs/101"]["steps"] = steps
            report = f.collect()
            self.assertFalse(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
            self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_ordinary_job_with_review_job_and_step_names_cannot_stand_in_for_review(self):
        ordinary = """  ordinary:
    name: dependency-review
    runs-on: ubuntu-24.04
    steps:
      - name: Check dependency advisories
        run: echo unrelated success
"""
        for actual in ("absent", "skipped"):
            f = Fixture()
            f.replace_workflow(WORKFLOW + ordinary)
            # Job101 is the unrelated success. The real review is absent/skipped.
            if actual == "skipped":
                checks = f.routes[API + "/commits/" + HEAD + "/check-runs?per_page=100"]
                checks["total_count"] = 2
                checks["check_runs"].append({"id": 9002, "name": "dependency-review", "head_sha": HEAD,
                    "app": {"slug": "github-actions"}, "details_url": "https://github.com/" + REPO + "/actions/runs/501/job/102"})
                f.routes[API + "/actions/jobs/102"] = {"id": 102, "run_id": 501, "head_sha": HEAD, "workflow_name": "lint",
                    "runner_id": 0, "conclusion": "skipped", "steps": [{"name": "Check dependency advisories", "conclusion": "skipped"}]}
            with self.subTest(actual_review=actual):
                report = f.collect()
                target = report["workflows"][0]["dependency_review_jobs"][0]
                self.assertEqual(target["job_source_display_name_count"], 2)
                self.assertFalse(target["job_source_display_unique"])
                self.assertTrue(report["hosted"]["jobs"][0]["exact_pr_run_binding"])
                self.assertTrue(report["hosted"]["jobs"][0]["review_step_source_label_unique"])
                self.assertEqual(report["hosted"]["jobs"][0]["review_step_runtime_match_count"], 1)
                self.assertFalse(any(row.get("review_action_step_succeeded") for row in report["hosted"]["jobs"]))
                self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_unknown_or_dynamic_ordinary_job_display_cannot_prove_review_job_uniqueness(self):
        for configuration in ("    name: ${{ matrix.alias }}\n    runs-on: ubuntu-24.04\n",
                              "    strategy:\n      matrix:\n        alias: [one, two]\n    runs-on: ubuntu-24.04\n",
                              "    uses: example/reusable/.github/workflows/check.yml@" + "a" * 40 + "\n"):
            f = Fixture()
            f.replace_workflow(WORKFLOW + "  ordinary:\n" + configuration)
            with self.subTest(configuration=configuration):
                report = f.collect()
                self.assertFalse(report["workflows"][0]["job_display_identities_confirmed"])
                self.assertFalse(report["hosted"]["jobs"][0]["review_job_source_display_unique"])
                self.assertFalse(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
                self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_explicit_review_display_name_cannot_be_replaced_by_a_job_id_alias(self):
        f = Fixture()
        f.replace_workflow(WORKFLOW.replace("  dependency-review:\n", "  dependency-review:\n    name: 'Review dependency findings'\n")
                           + "  ordinary:\n    name: dependency-review\n    runs-on: ubuntu-24.04\n    steps:\n      - name: Check dependency advisories\n        run: echo unrelated\n")
        check = f.routes[API + "/commits/" + HEAD + "/check-runs?per_page=100"]["check_runs"][0]
        check["name"] = "Review dependency findings"
        report = f.collect()
        self.assertTrue(report["workflows"][0]["dependency_review_jobs"][0]["job_source_display_unique"])
        self.assertTrue(report["hosted"]["jobs"][0]["review_action_step_succeeded"])
        check["name"] = "dependency-review"  # Only the unrelated job is observed now.
        report = f.collect()
        self.assertEqual(report["hosted"]["review_jobs"], [])
        self.assertFalse(any(row.get("review_action_step_succeeded") for row in report["hosted"]["jobs"]))
        self.assertIn("actual-executed-dependency-review-success-unconfirmed", report["gates"])

    def test_real_comparison_array_vulnerabilities_and_pagination_are_distinct(self):
        row = D.comparison_observation({"status": "ok", "http_status": 200, "data": [
            {"manifest": "go.mod", "ecosystem": "Go", "vulnerabilities": [{"private_field": PRIVATE}]}]}, BASE, HEAD)
        self.assertEqual(row["vulnerability_count"], 1)
        self.assertNotIn(PRIVATE, json.dumps(row))
        with self.assertRaises(D.ReadinessError):
            D.comparison_observation({"status": "ok", "http_status": 200, "data": {"diff": []}}, BASE, HEAD)
        row = D.comparison_observation({"status": "ok", "http_status": 200, "more_pages": True, "data": []}, BASE, HEAD)
        self.assertEqual(row["status"], "available-partial")

    def test_truncated_trees_checks_and_unrecognized_permissions_remain_explicit(self):
        f = Fixture()
        f.routes[API + "/git/trees/" + HEAD_TREE + "?recursive=1"]["truncated"] = True
        report = f.collect()
        self.assertIn("dependency-review-source-policy-needs-review", report["gates"])
        f = Fixture()
        f.routes[API + "/commits/" + HEAD + "/check-runs?per_page=100"]["total_count"] = 101
        report = f.collect()
        self.assertEqual(report["hosted"]["coverage"], "partial-or-bounded")
        for changed in (WORKFLOW.replace("contents: read", "contents: write"),
                        WORKFLOW.replace("permissions:\n  contents: read", "permissions: {contents: read}"),
                        WORKFLOW.replace("fail-on-severity: high", "fail-on-severity: critical"),
                        WORKFLOW.replace("@" + "b" * 40, "@main"),
                        WORKFLOW.replace("fail-on-severity: high", "fail-on-severity: high\n          warn-only: true"),
                        WORKFLOW.replace("    runs-on:", "    continue-on-error: true\n    runs-on:"),
                        WORKFLOW.replace("github.event_name == 'pull_request'", "github.event_name == 'pull_request' || true")):
            row = D.workflow_observation(".github/workflows/lint.yml", changed.encode())
            target = row["dependency_review_jobs"][0]
            self.assertFalse(target["action_commit_pinned"] and target["high_and_critical_policy"]
                             and target["pr_only_guard_observed"] and target["permissions"].get("read_only") is True
                             and target["permissions"].get("contents_read") is True)


class TransportAndOutput(unittest.TestCase):
    def test_no_redirects_or_arbitrary_hosts_with_existing_gh_auth(self):
        called = []
        def opener(request, timeout):
            called.append(request.full_url)
            return Response(request.full_url, {}, final_url="https://evil.invalid/redirect")
        api = D.GitHub("fixture-auth-token", opener)
        self.assertEqual(api.get("/repos/" + REPO)["reason"], "redirect-refused")
        self.assertEqual(called, [API])
        for path in ("https://evil.invalid/", "//evil.invalid/repos/a/b", "/repos/a/b/../other", "/repos/a/b\nheader"):
            with self.subTest(path=path), self.assertRaises(D.ReadinessError):
                api.get(path)
        with self.assertRaises(D.ReadinessError):
            D.NoRedirects().redirect_request(None, None, 302, "private", {}, "https://evil.invalid/")

    def test_call_response_total_time_and_job_budgets_stop_without_retries(self):
        f = Fixture()
        with patch.object(D, "MAX_REQUESTS", 5):
            api = f.api()
            report = D.collect(api, REPO, 17)
            self.assertEqual(len(f.calls), 5)
            self.assertEqual(api.requests, 5)
            self.assertEqual(report["readiness"], "unavailable-or-incomplete")
        for budget, value in (("MAX_RESPONSE", 4), ("MAX_TOTAL", 4)):
            with patch.object(D, budget, value):
                result = D.GitHub(open_url=lambda req, timeout: Response(req.full_url, b'{"long":true}')).get("/repos/" + REPO)
                self.assertEqual(result["reason"], "response-budget")
        ticks = iter([0, 121])
        api = D.GitHub(open_url=lambda *args, **kwargs: self.fail("must not request"), clock=lambda: next(ticks))
        self.assertEqual(api.get("/repos/" + REPO)["reason"], "request-budget")
        f = Fixture()
        with patch.object(D, "MAX_JOBS", 0):
            report = f.collect()
        self.assertEqual(report["hosted"]["coverage"], "partial-or-bounded")
        self.assertFalse(any("/actions/jobs/" in c["url"] for c in f.calls))

    def test_auth_resolution_uses_gh_not_token_variable_presence_or_stderr(self):
        result = subprocess.CompletedProcess([], 0, b"fixture-auth-token-never-print\n", PRIVATE.encode())
        with patch.object(D.shutil, "which", return_value="/existing/gh"), patch.object(D.subprocess, "run", return_value=result) as run, \
                patch.dict(os.environ, {"GH_TOKEN": "", "GITHUB_TOKEN": ""}):
            token, metadata = D.gh_authentication()
        self.assertEqual(token, "fixture-auth-token-never-print")
        self.assertEqual(metadata["source"], "existing-gh-authentication")
        self.assertEqual(run.call_args.args[0], ["gh", "auth", "token", "--hostname", "github.com"])
        self.assertNotIn(token, json.dumps(metadata))
        result = subprocess.CompletedProcess([], 1, b"", PRIVATE.encode())
        with patch.object(D.shutil, "which", return_value="/existing/gh"), patch.object(D.subprocess, "run", return_value=result):
            token, metadata = D.gh_authentication()
        self.assertIsNone(token)
        self.assertNotIn(PRIVATE, json.dumps(metadata))

    def test_reports_refuse_overwrite_symlink_or_unprotected_output_and_never_include_raw_private_fields(self):
        report = Fixture().collect()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "receipt"
            D.write_report(output, report)
            self.assertEqual(json.loads((output / "readiness.json").read_text())["schema"], D.SCHEMA)
            self.assertNotIn(PRIVATE, (output / "readiness.md").read_text())
            original = (output / "readiness.json").read_bytes()
            with self.assertRaises(D.ReadinessError):
                D.write_report(output, report)
            self.assertEqual((output / "readiness.json").read_bytes(), original)
            linked = root / "linked"
            linked.symlink_to(output, target_is_directory=True)
            with self.assertRaises(D.ReadinessError):
                D.write_report(linked / "new", report)
            unsafe = root / "unsafe"
            unsafe.mkdir(mode=0o777)
            unsafe.chmod(0o777)
            with self.assertRaises(D.ReadinessError):
                D.write_report(unsafe / "new", report)


if __name__ == "__main__":
    unittest.main()
