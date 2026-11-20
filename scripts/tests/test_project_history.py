"""Public capture completeness, original criteria and output preservation."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("project_history", ROOT / "scripts/export-project-history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
REPOSITORY = "szmyty/obsgod"
API = "https://api.github.com/repos/" + REPOSITORY
HEAD = "a" * 40
# Exact public repository ID and next-page cursor observed in GitHub's Link
# header on 2026-11-20; a cursor is public pagination metadata, not a credential.
REPOSITORY_ID = 1263344065
CURSOR = "Y3Vyc29yOnYyOpLPAAABodwRKrjPAAAAAX1CUqw%3D"


class Response(io.BytesIO):
    def __init__(self, url, body, link="", final_url=None):
        super().__init__(json.dumps(body).encode() if not isinstance(body, bytes) else body)
        self.url = final_url or url
        self.headers = {"Link": link}

    def geturl(self):
        return self.url


class Fixture:
    def __init__(self):
        self.calls = []
        self.branch_reads = 0
        common = {"user": {"login": "owner"}, "labels": [], "assignees": [], "milestone": None,
                  "body": "captured body\nincluding Unicode →", "state": "closed", "comments": 1}
        self.issue = {**common, "number": 1, "id": 1, "title": "Original issue", "html_url": "https://github.com/" + REPOSITORY + "/issues/1"}
        self.pull = {**common, "number": 2, "id": 2, "title": "Original PR", "pull_request": {},
                     "html_url": "https://github.com/" + REPOSITORY + "/pull/2"}
        self.repo = {"id": 10, "full_name": REPOSITORY, "html_url": "https://github.com/" + REPOSITORY,
                     "private": False, "visibility": "public", "default_branch": "main", "fork": True,
                     "archived": False, "parent": {"full_name": "muesli/obs-cli"}}
        self.issues_url = API + "/issues?state=all&per_page=100&sort=created&direction=asc"
        self.comments_url = API + "/issues/comments?per_page=100&sort=created&direction=asc"
        self.routes = {
            API: (self.repo, ""),
            self.issues_url: ([self.issue], '<' + self.issues_url + '&page=2>; rel="next"'),
            self.issues_url + "&page=2": ([self.pull], ""),
            API + "/pulls?state=all&per_page=100&sort=created&direction=asc": ([{
                **self.pull, "draft": False, "merged_at": "2026-11-14T00:00:00Z", "merge_commit_sha": "b" * 40,
                "head": {"label": "owner:topic", "ref": "topic", "sha": "c" * 40},
                "base": {"label": "owner:main", "ref": "main", "sha": HEAD},
            }], ""),
            self.comments_url: ([{"id": 11, "body": "issue discussion", "user": {"login": "owner"}, "issue_url": API + "/issues/1"}],
                                '<' + self.comments_url + '&page=2>; rel="next"'),
            self.comments_url + "&page=2": ([{"id": 12, "body": None, "issue_url": API + "/issues/2"}], ""),
            API + "/pulls/comments?per_page=100&sort=created&direction=asc": ([{
                "id": 13, "body": "inline review", "pull_request_url": API + "/pulls/2", "path": "main.go",
                "line": 1, "original_line": 1, "diff_hunk": "@@ fixture", "pull_request_review_id": 14,
            }], ""),
            API + "/pulls/2/reviews?per_page=100": ([{"id": 14, "state": "APPROVED", "body": "submitted review", "commit_id": "c" * 40}], ""),
        }
        self.changed_head = False

    def open(self, request, timeout):
        self.calls.append((request.full_url, dict(request.header_items()), timeout))
        if request.full_url == API + "/branches/main":
            self.branch_reads += 1
            return Response(request.full_url, {"commit": {"sha": "f" * 40 if self.changed_head and self.branch_reads > 1 else HEAD}})
        body, link = self.routes[request.full_url]
        return Response(request.full_url, body, link)

    def api(self):
        return history.PublicGitHub(REPOSITORY, self.open)


class PublicHistory(unittest.TestCase):
    def test_paginated_capture_keeps_bodies_counts_and_remote_head_without_git_or_auth(self):
        fixture = Fixture()
        with patch.dict(os.environ, {"GH_TOKEN": "fixture-token-must-not-be-captured", "GITHUB_TOKEN": "second-fixture-token"}), \
                patch("subprocess.check_output", side_effect=AssertionError("local Git must not determine remote HEAD")):
            snapshot = history.capture(fixture.api())
        self.assertEqual(snapshot["counts"], {"issues": 1, "pull_requests": 1, "conversation_comments": 2,
                                              "inline_review_comments": 1, "submitted_reviews": 1})
        self.assertEqual(snapshot["repository"]["default_branch_head"], HEAD)
        self.assertEqual(fixture.branch_reads, 2)
        self.assertEqual([i["number"] for i in snapshot["items"]], [1, 2])
        self.assertEqual(snapshot["items"][0]["body"], fixture.issue["body"])
        self.assertEqual(snapshot["items"][0]["body_sha256"], hashlib.sha256(fixture.issue["body"].encode()).hexdigest())
        self.assertEqual(snapshot["conversation_comments"][1]["body_sha256"], None)
        self.assertFalse(snapshot["retirement_performed"])
        for _url, headers, timeout in fixture.calls:
            self.assertNotIn("authorization", {k.lower() for k in headers})
            self.assertEqual(timeout, 15)
        self.assertNotIn("fixture-token", json.dumps(snapshot))

    def test_private_or_moved_repository_is_refused_before_tracker_requests(self):
        for changed in ({"private": True, "visibility": "private"}, {"full_name": "other/project"},
                        *({"id": value} for value in (None, True, 0, -1, "10", 1.5))):
            fixture = Fixture()
            fixture.repo.update(changed)
            with self.subTest(changed=changed), self.assertRaises(history.ExportError):
                history.capture(fixture.api())
            self.assertEqual([c[0] for c in fixture.calls], [API])

    def test_actual_numeric_id_and_cursor_header_requests_canonical_verified_repository(self):
        fixture = Fixture()
        fixture.repo["id"] = REPOSITORY_ID
        next_url = ("https://api.github.com/repositories/1263344065/issues"
                    "?state=all&per_page=100&sort=created&direction=asc&after=" + CURSOR + "&page=2")
        fixture.routes[fixture.issues_url] = ([fixture.issue], '<' + next_url + '>; rel="next"')
        canonical = fixture.issues_url + "&after=" + CURSOR + "&page=2"
        fixture.routes[canonical] = ([fixture.pull], "")
        snapshot = history.capture(fixture.api())
        self.assertEqual(snapshot["repository"]["id"], REPOSITORY_ID)
        self.assertEqual([i["number"] for i in snapshot["items"]], [1, 2])
        self.assertIn(canonical, [call[0] for call in fixture.calls])
        self.assertNotIn(next_url, [call[0] for call in fixture.calls])
        for url, headers, _timeout in fixture.calls:
            self.assertTrue(url.startswith(API))
            self.assertNotIn("authorization", {key.lower() for key in headers})

    def test_verified_numeric_alias_is_exact_for_each_endpoint(self):
        for path in ("/issues/comments?per_page=100&sort=created&direction=asc",
                     "/pulls?state=all&per_page=100&sort=created&direction=asc",
                     "/pulls/comments?per_page=100&sort=created&direction=asc",
                     "/pulls/2/reviews?per_page=100"):
            fixture = Fixture()
            api = fixture.api()
            api.verify_repository(fixture.repo)
            original = API + path
            numeric = original.replace("/repos/" + REPOSITORY, "/repositories/10")
            fixture.routes[original] = ([{"id": 21}], '<' + numeric + '&page=2>; rel="next"')
            fixture.routes[original + "&page=2"] = ([{"id": 22}], "")
            with self.subTest(path=path):
                self.assertEqual(api.get(path, pages=True), [{"id": 21}, {"id": 22}])
                self.assertEqual([call[0] for call in fixture.calls], [original, original + "&page=2"])

    def test_numeric_alias_requires_metadata_binding_and_cannot_rebind(self):
        fixture = Fixture()
        numeric = fixture.issues_url.replace("/repos/" + REPOSITORY, "/repositories/10")
        fixture.routes[fixture.issues_url] = ([fixture.issue], '<' + numeric + '&page=2>; rel="next"')
        with self.assertRaisesRegex(history.ExportError, "pagination"):
            fixture.api().get("/issues?state=all&per_page=100&sort=created&direction=asc", pages=True)
        self.assertEqual(len(fixture.calls), 1)
        api = fixture.api()
        api.verify_repository(fixture.repo)
        with self.assertRaises(history.ExportError):
            api.verify_repository(dict(fixture.repo, id=11))
        self.assertEqual(api.repository_id, 10)

    def test_remote_branch_changes_are_reported_instead_of_claimed_atomic_backup(self):
        fixture = Fixture()
        fixture.changed_head = True
        with self.assertRaisesRegex(history.ExportError, "changed during capture"):
            history.capture(fixture.api())

    def test_incomplete_comments_duplicate_items_and_pending_reviews_are_refused(self):
        fixture = Fixture()
        fixture.issue["comments"] = 2
        with self.assertRaisesRegex(history.ExportError, "comment counts"):
            history.capture(fixture.api())
        fixture = Fixture()
        fixture.routes[fixture.issues_url + "&page=2"] = ([fixture.issue], "")
        with self.assertRaisesRegex(history.ExportError, "duplicate"):
            history.capture(fixture.api())
        fixture = Fixture()
        fixture.routes[API + "/pulls/2/reviews?per_page=100"][0][0]["state"] = "PENDING"
        with self.assertRaisesRegex(history.ExportError, "private review"):
            history.capture(fixture.api())

    def test_pagination_cannot_escape_owner_endpoint_or_add_secret_queries(self):
        for url in ("https://api.github.com/repos/attacker/project/issues?page=2",
                    API + "/pulls?page=2", "https://example.invalid/data",
                    API + "/issues?state=all&per_page=100&sort=created&direction=asc&page=2&access_token=fixture"):
            fixture = Fixture()
            fixture.routes[fixture.issues_url] = ([fixture.issue], '<' + url + '>; rel="next"')
            with self.subTest(url=url), self.assertRaisesRegex(history.ExportError, "pagination"):
                fixture.api().get("/issues?state=all&per_page=100&sort=created&direction=asc", pages=True)
            self.assertEqual(len(fixture.calls), 1)

    def test_numeric_pagination_rejects_identity_endpoint_authority_and_query_confusion(self):
        numeric = "https://api.github.com/repositories/1263344065/issues"
        query = "?state=all&per_page=100&sort=created&direction=asc"
        valid = numeric + query + "&after=" + CURSOR + "&page=2"
        urls = [
            valid.replace("1263344065", "1263344066"),
            valid.replace("1263344065", "01263344065"),
            valid.replace("1263344065", "1263344065-extra"),
            valid.replace("/issues?", "/issues/comments?"),
            valid.replace("/issues?", "/pulls?"),
            valid.replace("/issues?", "/issues/../issues?"),
            valid.replace("/issues?", "/%69ssues?"),
            valid.replace("https://", "http://"),
            valid.replace("https:", ""),
            valid.replace("api.github.com", "api.github.com.attacker.invalid"),
            valid.replace("api.github.com", "api.github.com:443"),
            valid.replace("api.github.com", "user@api.github.com"),
            valid.replace("api.github.com", "api.github.com@attacker.invalid"),
            valid.replace("api.github.com", "api.github.com."),
            valid + "#", valid + "#fragment", valid + "\t",
            valid + "&access_token=fixture", valid + "&access_token=",
            valid + "&page=2", valid + "&per_page=100", valid + "&after=" + CURSOR,
            valid.replace("state=all", "state=open"),
            valid.replace("sort=created", "sort=updated"),
            valid.replace("&page=2", "&page=0"), valid.replace("&page=2", "&page=01"),
            valid.replace("&page=2", "&page=3"), valid.replace("&page=2", "&page=２"),
            valid.replace("&page=2", "&page="),
            numeric + query + "&after=&page=2",
            numeric + query + "&after=" + "a" * 1025 + "&page=2",
            numeric + query + "&after=cursor%26access_token%3Dfixture&page=2",
            numeric + query + "&after=cursor%0Avalue&page=2",
            numeric + query + "&before=" + CURSOR + "&page=2",
        ]
        for url in urls:
            fixture = Fixture()
            fixture.repo["id"] = REPOSITORY_ID
            fixture.routes[fixture.issues_url] = ([fixture.issue], '<' + url + '>; rel="next"')
            api = fixture.api()
            api.verify_repository(fixture.repo)
            with self.subTest(url=url), self.assertRaisesRegex(history.ExportError, "pagination"):
                api.get("/issues?state=all&per_page=100&sort=created&direction=asc", pages=True)
            self.assertEqual([call[0] for call in fixture.calls], [fixture.issues_url])

    def test_verified_alias_does_not_authorize_a_response_redirect(self):
        fixture = Fixture()
        numeric = fixture.issues_url.replace("/repos/" + REPOSITORY, "/repositories/10")
        fixture.routes[fixture.issues_url] = ([fixture.issue], '<' + numeric + '&page=2>; rel="next"')
        def open_response(request, timeout):
            if "page=2" in request.full_url:
                return Response(request.full_url, [fixture.pull], final_url=numeric + "&page=2")
            return fixture.open(request, timeout)
        api = history.PublicGitHub(REPOSITORY, open_response)
        api.verify_repository(fixture.repo)
        with self.assertRaisesRegex(history.ExportError, "changed the requested"):
            api.get("/issues?state=all&per_page=100&sort=created&direction=asc", pages=True)

    def test_redirect_and_response_page_request_limits_fail_closed(self):
        api = history.PublicGitHub(REPOSITORY, lambda request, **_kw: Response(request.full_url, {}, final_url=API + "/other"))
        with self.assertRaisesRegex(history.ExportError, "changed the requested"):
            api.get("")
        with self.assertRaises(history.ExportError):
            history.NoRedirects().redirect_request(None, None, 302, "Found", {}, "https://example.invalid/")
        fixture = Fixture()
        with patch.object(history, "MAX_PAGES", 1), self.assertRaisesRegex(history.ExportError, "page limit"):
            fixture.api().get("/issues?state=all&per_page=100&sort=created&direction=asc", pages=True)
        with patch.object(history, "MAX_RESPONSE", 8), self.assertRaisesRegex(history.ExportError, "size limit"):
            Fixture().api().get("")
        with patch.object(history, "MAX_REQUESTS", 0), self.assertRaisesRegex(history.ExportError, "request limit"):
            Fixture().api().get("")


class OutputAndCriteria(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.snapshot = history.capture(Fixture().api())

    def test_new_and_explicit_recognized_replacement_are_valid_json(self):
        output = self.root / "new/history.json"
        history.write_exports([(output, self.snapshot)], REPOSITORY)
        self.assertEqual(json.loads(output.read_bytes()), self.snapshot)
        before = output.read_bytes()
        with self.assertRaises(history.ExportError):
            history.write_exports([(output, self.snapshot)], REPOSITORY)
        self.assertEqual(output.read_bytes(), before)
        changed = dict(self.snapshot, purpose="retirement-backup")
        history.write_exports([(output, changed)], REPOSITORY, replace=True)
        self.assertEqual(json.loads(output.read_bytes())["purpose"], "retirement-backup")
        self.assertEqual(list(output.parent.glob(".history-*")), [])

    def test_unknown_foreign_symlink_and_unsafe_second_output_preserve_files(self):
        output = self.root / "keep.json"
        output.write_text("owner content")
        for replace in (False, True):
            with self.assertRaises(history.ExportError):
                history.write_exports([(output, self.snapshot)], REPOSITORY, replace)
            self.assertEqual(output.read_text(), "owner content")
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(history.ExportError):
            history.write_exports([(linked / "new.json", self.snapshot)], REPOSITORY)
        new = self.root / "new.json"
        with self.assertRaises(history.ExportError):
            history.write_exports([(new, self.snapshot), (output, {"schema": history.CARRY_SCHEMA})], REPOSITORY, True)
        self.assertFalse(new.exists())
        with patch.object(history.os, "getuid", return_value=os.getuid() + 1), self.assertRaisesRegex(history.ExportError, "ownership"):
            history.validate_output(output, history.HISTORY_SCHEMA, REPOSITORY, True)

    def test_all_230_original_criteria_and_dependencies_survive_without_new_acceptance(self):
        ledger_path = ROOT / "docs/evidence/completion-criteria.json"
        ledger = json.loads(ledger_path.read_bytes())
        carried = history.carry_forward(ledger_path, REPOSITORY, self.snapshot)
        self.assertEqual(carried["source_ledger"]["criteria_count"], 230)
        self.assertEqual(carried["source_ledger"]["sha256"], hashlib.sha256(ledger_path.read_bytes()).hexdigest())
        self.assertEqual(carried["history_snapshot_sha256"], hashlib.sha256(history.encoded(self.snapshot)).hexdigest())
        old = {c["id"]: c for i in ledger["issues"] for c in i["criteria"]}
        new = {c["id"]: c for i in carried["issues"] for c in i["criteria"]}
        self.assertEqual(set(old), set(new))
        for identifier, record in new.items():
            for field in ("original_text", "original_section", "original_line", "original_checkbox"):
                self.assertEqual(record[field], old[identifier].get(field))
            for field in ("new_issue_number", "new_issue_url", "owner_disposition", "current_acceptance"):
                self.assertIsNone(record[field])
        by_number = {i["number"]: i for i in ledger["issues"]}
        for issue in carried["issues"]:
            self.assertEqual(issue["dependency_preservation"], by_number[issue["old_issue_number"]].get("dependency_preservation"))
            self.assertEqual(issue["original_gate_and_scope_sections"], by_number[issue["old_issue_number"]].get("original_gate_and_scope_sections"))
            self.assertIsNone(issue["new_issue_number"])

    def test_duplicate_criteria_and_wrong_repository_are_refused(self):
        ledger_path = self.root / "ledger.json"
        criterion = {"id": "1.AC1", "original_text": "Original acceptance"}
        ledger = {"repository": REPOSITORY, "criteria_count": 2,
                  "issues": [{"number": 1, "url": "https://github.com/" + REPOSITORY + "/issues/1", "title": "Original",
                              "criteria": [criterion, dict(criterion)]}]}
        ledger_path.write_text(json.dumps(ledger))
        with self.assertRaisesRegex(history.ExportError, "duplicate"):
            history.carry_forward(ledger_path, REPOSITORY, self.snapshot)
        ledger["repository"] = "other/project"
        ledger_path.write_text(json.dumps(ledger))
        with self.assertRaisesRegex(history.ExportError, "does not belong"):
            history.carry_forward(ledger_path, REPOSITORY, self.snapshot)


if __name__ == "__main__":
    unittest.main()
