"""Fresh snapshot preparation and owner-run publication boundaries.

GitHub and push operations are fixtures only. Real temporary Git repositories
exercise git-archive byte/mode preservation and one-root-commit construction.
"""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fresh_repository", ROOT / "scripts/prepare-fresh-repository.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
DESTINATION = "selected-owner/deckystream"
COMMIT = "b" * 40


def local_git(path, *arguments, data=None):
    return subprocess.run(["git", "-C", str(path), *arguments], input=data, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def source_updater_fixture():
    """Keep the old-source fixture portable when ROOT is the new repository.

    Normalize only its one literal; all current updater policy code is retained.
    """
    data = (ROOT / "steamdeck/releases.py").read_bytes()
    assignment = M.repository_assignment(data)
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[:assignment.lineno - 1])) + assignment.col_offset
    end = sum(map(len, lines[:assignment.end_lineno - 1])) + assignment.end_col_offset
    return (data[:start] + json.dumps(M.SOURCE_REPOSITORY).encode() + data[end:]).decode()


class API:
    def __init__(self, organization=False):
        self.calls = []
        self.exists = False
        self.fail_create = self.fail_verify = False
        self.organization = organization
        self.role = "admin"
        self.source_sha = None
        self.created = {"id": 20, "full_name": DESTINATION, "private": False,
                        "visibility": "public", "fork": False, "default_branch": "main"}

    def request(self, method, path, body=None, missing=False):
        self.calls.append((method, path, body, missing))
        if path == "/user":
            return {"login": "operator" if self.organization else "selected-owner"}
        if path == "/users/selected-owner":
            return {"login": "selected-owner", "type": "Organization" if self.organization else "User"}
        if path == "/orgs/selected-owner/memberships/operator":
            return {"state": "active", "role": self.role}
        if path == "/repos/" + M.SOURCE_REPOSITORY:
            return {"id": 10, "full_name": M.SOURCE_REPOSITORY, "private": False, "visibility": "public", "default_branch": "master"}
        if path == "/repos/" + M.SOURCE_REPOSITORY + "/git/ref/heads/master":
            return {"object": {"sha": self.source_sha}}
        if method == "POST":
            if self.fail_create:
                raise M.PreparationError("Creation refused (collision or insufficient token scope).")
            self.exists = True
            return self.created
        if path == "/repos/" + DESTINATION:
            if self.fail_verify and not missing:
                raise M.PreparationError("Verification unavailable.")
            return self.created if self.exists else None
        if path == "/repos/" + DESTINATION + "/git/ref/heads/main":
            return {"object": {"sha": COMMIT}}
        raise AssertionError((method, path))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fresh-repository-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source with spaces"
        self.source.mkdir()
        local_git(self.source, "init", "--initial-branch=master")
        local_git(self.source, "config", "user.name", "Fixture Owner")
        local_git(self.source, "config", "user.email", "fixture@example.invalid")
        local_git(self.source, "remote", "add", "origin", "https://github.com/" + M.SOURCE_REPOSITORY + ".git")
        for name in M.REQUIRED:
            self.put(name, "Historical immutable URL https://github.com/szmyty/obsgod/tree/" + "a" * 40 + "\n")
        self.put("LICENSE", "MIT License\nCopyright original upstream author\n")
        self.put(".identity/metadata/rights.json", '{"approval": null, "source": "original"}\n')
        self.put("branding/masters/keep.svg", "original vector source")
        self.put("audits/history.md", "historical passed receipt remains historical")
        self.put(".github/workflows/preserved.yml", "on: push\njobs: {}\n")
        self.put(".gitignore", "private-sentinel\n")
        self.put("private-sentinel", "ignored-private-data-not-in-git")
        self.put("executable", "#!/bin/sh\nexit 0\n")
        (self.source / "executable").chmod(0o755)
        (self.source / "license-link").symlink_to("LICENSE")
        self.put("scripts/generate-product.py", (ROOT / "scripts/generate-product.py").read_text())
        self.product(M.SOURCE_REPOSITORY)
        criteria = [{"id": str(i) + ".AC1", "original_text": "Original criterion " + str(i),
                     "source_status": "historical_receipt_not_acceptance"} for i in range(1, 4)]
        ledger = {"repository": M.SOURCE_REPOSITORY, "criteria_count": len(criteria), "issues": [
            {"number": 46, "url": "https://github.com/" + M.SOURCE_REPOSITORY + "/issues/46",
             "title": "Retained backlog", "criteria": criteria,
             "dependency_preservation": {"verbatim_dependency_statements": ["Requires original #35."]},
             "remaining_scope_summary": "Actual device and rights remain"}]}
        self.put("docs/evidence/completion-criteria.json", M.encoded(ledger).decode())
        self.commit()
        self.output = self.base / "prepared snapshot"
        self.backup = self.base / "public-history.json"
        self.history()

    def put(self, path, content):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def product(self, repository):
        value = {"schema_version": 1, "display_name": "deckystream", "description": "Stream from Steam Deck with OBS",
                 "repository": repository, "compatibility": {"cli": "obsgod", "plugin": "OBSGod", "plugin_directory": "obsgod", "storage_namespace": "obsgod"}}
        self.put("product.json", M.encoded(value).decode())
        subprocess.run(["python3", str(self.source / "scripts/generate-product.py")], check=True)
        self.put("steamdeck/releases.py", 'REPOSITORY = "' + repository + '"\n')
        self.put(".identity/identity.json", json.dumps({"schema": "identity.project/v1", "project": {"id": "decky-stream", "repository": "https://github.com/" + repository}, "approval": None}, indent=2) + "\n")

    def commit(self):
        local_git(self.source, "add", "--all")
        local_git(self.source, "commit", "-m", "Fixture source")
        self.sha = local_git(self.source, "rev-parse", "HEAD").decode().strip()

    def history(self, **changes):
        value = {"schema": M.HISTORY_SCHEMA, "purpose": "retirement-backup", "retirement_performed": False,
                 "capture_completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "repository": {"id": 10, "full_name": M.SOURCE_REPOSITORY, "visibility": "public", "default_branch_head": self.sha},
                 "counts": {"issues": 1, "pull_requests": 0, "conversation_comments": 0, "inline_review_comments": 0, "submitted_reviews": 0},
                 "items": [{"number": 46, "kind": "issue", "state": "open", "title": "Remaining backlog", "body": "Full public original body"}],
                 "conversation_comments": [], "inline_review_comments": [], "submitted_reviews": []}
        value.update(changes)
        self.backup.write_bytes(M.encoded(value))
        return value

    def prepared(self, canonical=False, api=None, staged=False):
        if canonical:
            self.product(DESTINATION)
            self.commit()
            self.history()
        if api is not None:
            api.source_sha = self.sha
        return M.prepare(self.source, self.sha, DESTINATION, self.backup, api, staged)


class Preparation(Fixture):
    def test_staging_changes_exactly_five_canonical_files_and_preserves_source_archive(self):
        # Exercise the real reviewed updater; production never executes it while
        # staging, and all of its policy code must remain byte-identical.
        self.put("steamdeck/releases.py", source_updater_fixture())
        self.commit()
        self.history()
        original = self.prepared()
        staged = self.prepared(staged=True)
        repeated = self.prepared(staged=True)
        self.assertEqual(staged[1:], repeated[1:])
        self.assertEqual(staged[1], original[1])
        self.assertEqual(staged[4]["source_archive_sha256"], original[4]["source_archive_sha256"])
        self.assertEqual(staged[4]["apply_blockers"], [])
        changed = {p for p in original[3] if original[3][p] != staged[3][p]}
        self.assertEqual(changed, set(M.CANONICAL_PATHS))
        self.assertEqual(changed, {row["path"] for row in staged[4]["canonical_identity_staging"]["changes"]})
        for row in staged[4]["canonical_identity_staging"]["changes"]:
            self.assertEqual(row["before_sha256"], hashlib.sha256(original[3][row["path"]]).hexdigest())
            self.assertEqual(row["after_sha256"], hashlib.sha256(staged[3][row["path"]]).hexdigest())
        for path, content in original[3].items():
            if original[2][path]["mode"] != "120000":
                self.assertEqual((self.source / path).read_bytes(), content)
        self.assertEqual(local_git(self.source, "status", "--porcelain=v1", "--untracked-files=all"), b"")
        self.assertEqual(local_git(self.source, "rev-parse", "HEAD").strip(), self.sha.encode())
        staged_product = json.loads(staged[3]["product.json"])
        original_product = json.loads(original[3]["product.json"])
        self.assertEqual(staged_product, {**original_product, "repository": DESTINATION})
        original_identity = json.loads(original[3][".identity/identity.json"])
        original_identity["project"]["repository"] = "https://github.com/" + DESTINATION
        self.assertEqual(json.loads(staged[3][".identity/identity.json"]), original_identity)
        expected_updater = original[3]["steamdeck/releases.py"].replace(b'REPOSITORY = "szmyty/obsgod"', ('REPOSITORY = "' + DESTINATION + '"').encode(), 1)
        self.assertEqual(staged[3]["steamdeck/releases.py"], expected_updater)
        with tarfile.open(fileobj=io.BytesIO(staged[6]), mode="r:") as archive:
            for path in changed:
                self.assertEqual(archive.extractfile(path).read(), staged[3][path])
        M.write_preparation(self.output, staged)
        self.assertEqual((self.output / "source.tar").read_bytes(), original[1])
        self.assertEqual((self.output / "snapshot.tar").read_bytes(), staged[6])
        self.assertIn(b"source/.identity/identity.json", (self.output / "canonical-changes.diff").read_bytes())

    def test_staged_updater_accepts_only_exact_new_repository_and_rejects_old_source(self):
        self.put("steamdeck/releases.py", source_updater_fixture())
        self.commit()
        self.history()
        staged = self.prepared(staged=True)
        updater_path = self.base / "staged-updater.py"
        updater_path.write_bytes(staged[3]["steamdeck/releases.py"])
        spec = importlib.util.spec_from_file_location("staged_fixture_updater", updater_path)
        updater = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(updater)
        self.assertEqual(updater.REPOSITORY, DESTINATION)
        self.assertEqual(updater.RELEASES_URL, "https://api.github.com/repos/" + DESTINATION + "/releases?per_page=100")
        for repository in (DESTINATION, M.SOURCE_REPOSITORY, "another-owner/deckystream", "selected-owner/another-repo"):
            accepted = repository == DESTINATION
            urls = ("https://api.github.com/repos/" + repository + "/releases?per_page=100",
                    "https://api.github.com/repos/" + repository + "/commits/v0.1.0",
                    "https://github.com/" + repository + "/releases/download/v0.1.0/obsgod-decky.zip",
                    "https://raw.githubusercontent.com/" + repository + "/" + "a" * 40 + "/manifest.json")
            for url in urls:
                with self.subTest(url=url):
                    self.assertEqual(updater._safe_url(url), accepted)
        self.assertIn(b'REPOSITORY = "szmyty/obsgod"', (self.source / "steamdeck/releases.py").read_bytes())

    def test_existing_release_suite_passes_against_copied_staged_real_updater(self):
        self.put("steamdeck/releases.py", source_updater_fixture())
        self.commit()
        self.history()
        staged = self.prepared(staged=True)
        package = self.base / "existing release suite/steamdeck"
        tests = package / "tests"
        tests.mkdir(parents=True)
        (package / "releases.py").write_bytes(staged[3]["steamdeck/releases.py"])
        (package / "paths.py").write_bytes((ROOT / "steamdeck/paths.py").read_bytes())
        suite_path = tests / "test_releases.py"
        suite_path.write_bytes((ROOT / "steamdeck/tests/test_releases.py").read_bytes())
        suite_spec = importlib.util.spec_from_file_location("copied_staged_release_suite", suite_path)
        suite_module = importlib.util.module_from_spec(suite_spec)
        suite_spec.loader.exec_module(suite_module)
        self.assertEqual(suite_module.releases.REPOSITORY, DESTINATION)
        suite = unittest.defaultTestLoader.loadTestsFromModule(suite_module)
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(suite)
        self.assertGreaterEqual(result.testsRun, 24)
        self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_pure_projection_rendering_matches_existing_generator_semantics(self):
        value = json.loads((self.source / "product.json").read_bytes())
        value.update({"repository": DESTINATION, "description": 'Quotes " unicode \u00e9 and slash \\ remain exact'})
        self.put("product.json", json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        subprocess.run(["python3", str(self.source / "scripts/generate-product.py")], check=True)
        for path, data in M.generated_product_outputs(value).items():
            self.assertEqual(data, (self.source / path).read_bytes())

    def test_staging_refuses_mixed_identity_projection_drift_or_installed_id_changes(self):
        payload = self.prepared()[3]
        for path, data in (("steamdeck/releases.py", b'REPOSITORY = "another-owner/deckystream"\n'),
                           ("steamdeck/product.py", payload["steamdeck/product.py"] + b"# unrelated drift\n")):
            with self.subTest(path=path), self.assertRaises(M.PreparationError):
                M.stage_canonical_identity({**payload, path: data}, DESTINATION)
        product = json.loads(payload["product.json"])
        product["compatibility"]["plugin"] = "new-installed-ID"
        with self.assertRaisesRegex(M.PreparationError, "compatibility"):
            M.stage_canonical_identity({**payload, "product.json": M.encoded(product)}, DESTINATION)

    def test_offline_plan_is_deterministic_and_preserves_every_tracked_byte(self):
        before = local_git(self.source, "status", "--porcelain=v1", "--untracked-files=all")
        with patch.object(M, "GitHub", side_effect=AssertionError("No API during offline preparation")):
            first = self.prepared()
            second = self.prepared()
        self.assertEqual(first[1:], second[1:])
        source, archive, inventory, payload, plan, sidecars = first[:6]
        self.assertEqual(before, local_git(self.source, "status", "--porcelain=v1", "--untracked-files=all"))
        self.assertNotIn("private-sentinel", payload)
        self.assertFalse(any(".git" in Path(p).parts for p in payload))
        self.assertEqual(payload["LICENSE"], (self.source / "LICENSE").read_bytes())
        self.assertEqual(payload["license-link"], b"LICENSE")
        self.assertEqual(inventory["executable"]["mode"], "100755")
        self.assertIn(".identity/metadata/rights.json", plan["preserved"]["branding_identity"])
        self.assertIn("audits/history.md", plan["preserved"]["history_backlog_evidence"])
        self.assertEqual(plan["criteria_count"], 3)
        self.assertEqual(plan["default_branch"], "main")
        self.assertTrue(plan["apply_blockers"])
        self.assertIn("[skip ci]", plan["initial_push"]["commit_message"])
        carried = json.loads(sidecars["criteria-carry-forward.json"])
        self.assertEqual(carried["issues"][0]["original"]["dependency_preservation"], {"verbatim_dependency_statements": ["Requires original #35."]})
        self.assertIsNone(carried["issues"][0]["destination_issue"])
        self.assertEqual(plan["history_backup"]["open_items"][0]["number"], 46)
        M.write_preparation(self.output, first)
        self.assertEqual((self.output / "source.tar").read_bytes(), archive)
        self.assertEqual((self.output / "plan.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(M.PreparationError):
            M.output_path(self.output, self.source)

    def test_only_get_requests_during_explicit_authenticated_inspection(self):
        api = API(organization=True)
        prepared = self.prepared(api=api)
        self.assertTrue(api.calls)
        self.assertTrue(all(call[0] == "GET" for call in api.calls))
        self.assertEqual(prepared[4]["destination_inspection"]["authority"], "authenticated-organization-admin")
        api.exists = True
        with self.assertRaisesRegex(M.PreparationError, "already exists"):
            self.prepared(api=api)

    def test_exact_destination_source_and_output_controls(self):
        for destination in ("OWNER/deckystream", "selected-owner/decky-stream", "../deckystream", "a/b/deckystream", "https://github.com/a/deckystream", "a*/deckystream", "-owner/deckystream", "a--b/deckystream", "szmyty/obsgod", "a/deckystream\n"):
            with self.subTest(destination=destination), self.assertRaises(M.PreparationError):
                M.destination_name(destination)
        for revision in ("HEAD", "a" * 39, "a" * 40):
            with self.subTest(revision=revision), self.assertRaises(M.PreparationError):
                M.source_snapshot(self.source, revision)
        for path in (self.source / "new-output", self.base / ".." / "escape"):
            with self.assertRaises(M.PreparationError):
                M.output_path(path, self.source)
        (self.base / "linked").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(M.PreparationError):
            M.output_path(self.base / "linked/output", self.source)
        self.put("untracked-file", "must not leak")
        with self.assertRaisesRegex(M.PreparationError, "clean"):
            self.prepared()

    def test_source_remote_and_git_archive_attributes_cannot_change_snapshot(self):
        local_git(self.source, "remote", "set-url", "origin", "https://github.com/unrelated/repository.git")
        with self.assertRaisesRegex(M.PreparationError, "origin"):
            self.prepared()
        local_git(self.source, "remote", "set-url", "origin", "git@github.com:" + M.SOURCE_REPOSITORY + ".git")
        self.put(".gitattributes", "LICENSE export-ignore\n")
        self.commit()
        with self.assertRaisesRegex(M.PreparationError, "omitted"):
            self.prepared()
        self.put(".gitattributes", "LICENSE export-subst\n")
        self.put("LICENSE", "$Format:%H$\nOriginal attribution")
        self.commit()
        with self.assertRaisesRegex(M.PreparationError, "changed source bytes"):
            self.prepared()

    def test_history_must_be_public_complete_and_exact_source(self):
        for changes in ({"purpose": "checkpoint"}, {"retirement_performed": True},
                        {"repository": {"full_name": "other/repo"}}, {"items": []},
                        {"submitted_reviews": [{"private": "sentinel"}]}):
            self.history(**changes)
            with self.subTest(changes=changes), self.assertRaises(M.PreparationError):
                self.prepared()
        prepared = M.prepare(self.source, self.sha, DESTINATION)
        self.assertIn("fresh-public-retirement-history-backup-required", prepared[4]["apply_blockers"])

    def test_real_root_commit_preserves_all_blobs_modes_and_no_parent(self):
        prepared = self.prepared()
        repository = self.base / "snapshot.git"
        environment = {"GIT_AUTHOR_NAME": "Fixture Owner", "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture Owner", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        with patch.dict(os.environ, environment):
            commit = M.snapshot_commit(repository, prepared[3], prepared[2], prepared[5])
        self.assertEqual(local_git(repository, "rev-list", "--count", "main").strip(), b"1")
        self.assertEqual(local_git(repository, "rev-list", "--parents", "-n", "1", "main").strip(), commit.encode())
        for path, metadata in prepared[2].items():
            self.assertEqual(local_git(repository, "rev-parse", "main:" + path).strip(), metadata["git_blob"].encode())
        self.assertIn(b"[skip ci]", local_git(repository, "log", "-1", "--format=%B"))
        self.assertEqual(local_git(repository, "show", "main:docs/history/fresh-repository-public-history.json"), prepared[5]["public-history.json"])

    def test_git_environment_cannot_redirect_snapshot_index_or_objects(self):
        prepared = self.prepared()
        sentinel = self.base / "caller-index"
        sentinel.write_bytes(b"caller-owned index must survive")
        objects = self.base / "caller-objects"
        objects.mkdir()
        environment = {"GIT_INDEX_FILE": str(sentinel), "GIT_OBJECT_DIRECTORY": str(objects),
                       "GIT_DIR": str(self.source / ".git"), "GIT_WORK_TREE": str(self.source),
                       "GIT_AUTHOR_NAME": "Fixture Owner", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                       "GIT_COMMITTER_NAME": "Fixture Owner", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        with patch.dict(os.environ, environment):
            M.snapshot_commit(self.base / "isolated.git", prepared[3], prepared[2], prepared[5])
        self.assertEqual(sentinel.read_bytes(), b"caller-owned index must survive")
        self.assertEqual(list(objects.iterdir()), [])

    def test_snapshot_remains_sha1_under_inherited_sha256_defaults(self):
        prepared = self.prepared()
        repository = self.base / "explicit-sha1.git"
        environment = {"GIT_DEFAULT_HASH": "sha256", "GIT_CONFIG_COUNT": "1",
                       "GIT_CONFIG_KEY_0": "init.defaultObjectFormat", "GIT_CONFIG_VALUE_0": "sha256",
                       "GIT_AUTHOR_NAME": "Fixture Owner", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                       "GIT_COMMITTER_NAME": "Fixture Owner", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        with patch.dict(os.environ, environment):
            commit = M.snapshot_commit(repository, prepared[3], prepared[2], prepared[5])
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertEqual(local_git(repository, "rev-parse", "--show-object-format").strip(), b"sha1")
        self.assertEqual(local_git(repository, "rev-list", "--parents", "-n", "1", "main").strip(), commit.encode())
        for path, metadata in prepared[2].items():
            self.assertEqual(local_git(repository, "rev-parse", "main:" + path).strip(), metadata["git_blob"].encode())
            tree_entry = local_git(repository, "ls-tree", "main", "--", path).decode()
            self.assertTrue(tree_entry.startswith(metadata["mode"] + " blob "))

    def test_effective_git_fetch_and_push_rewrites_are_rejected_before_creation(self):
        url = "https://github.com/" + DESTINATION + ".git"
        for setting in ("insteadOf", "pushInsteadOf"):
            repository = self.base / (setting + ".git")
            local_git(self.source, "init", "--bare", "--template=", str(repository))
            local_git(repository, "config", "url.https://unrelated.invalid/repository.git." + setting, url)
            with self.subTest(setting=setting), self.assertRaisesRegex(M.PreparationError, "URL rewrite"):
                M.exact_push_remote(repository, DESTINATION)

    def test_replace_refs_cannot_substitute_a_different_pinned_source_tree(self):
        original = self.sha
        original_license = (self.source / "LICENSE").read_bytes()
        self.put("LICENSE", "replacement object must never replace pinned attribution")
        self.commit()
        replacement = self.sha
        local_git(self.source, "checkout", "--detach", original)
        local_git(self.source, "replace", original, replacement)
        captured = M.source_snapshot(self.source, original)
        self.assertEqual(captured[3]["LICENSE"], original_license)


class Apply(Fixture):
    def invoke_apply(self, prepared, api, remote_refs=b"", push_fails=False):
        calls = []
        api.source_sha = prepared[4]["source_sha"]
        def remote_git(repository, *arguments, data=None):
            if repository == self.source:
                return local_git(repository, *arguments, data=data)
            calls.append(arguments)
            if "ls-remote" in arguments:
                return remote_refs
            if "push" in arguments:
                if push_fails:
                    raise M.PreparationError("Push unavailable.")
                return b"fixture push"
            raise AssertionError(arguments)
        with patch.object(M, "snapshot_commit", return_value=COMMIT), patch.object(M, "exact_push_remote", return_value="fresh-snapshot"), patch.object(M, "git", side_effect=remote_git):
            result = M.apply(prepared, self.output, api)
        return result, calls

    def test_current_identity_refuses_apply_before_any_api_or_output(self):
        api = API()
        with self.assertRaisesRegex(M.PreparationError, "canonical transition"):
            self.invoke_apply(self.prepared(), api)
        self.assertEqual(api.calls, [])
        self.assertFalse(self.output.exists())

    def test_non_sha1_snapshot_commit_is_refused_before_remote_creation(self):
        prepared = self.prepared(canonical=True)
        api = API()
        api.source_sha = self.sha
        with patch.object(M, "snapshot_commit", return_value="f" * 64), self.assertRaisesRegex(M.PreparationError, "40-character SHA1"):
            M.apply(prepared, self.output, api)
        self.assertTrue(all(call[0] == "GET" for call in api.calls))
        state = json.loads((self.output / "apply-receipt.json").read_bytes())
        self.assertFalse(state["creation_attempted"])
        self.assertFalse(state["remote_created"])

    def test_explicit_staging_allows_mocked_apply_without_activating_old_checkout(self):
        source_product = (self.source / "product.json").read_bytes()
        api = API()
        state, _ = self.invoke_apply(self.prepared(staged=True), api)
        self.assertTrue(state["push_verified"])
        self.assertEqual((self.source / "product.json").read_bytes(), source_product)
        self.assertEqual(json.loads(source_product)["repository"], M.SOURCE_REPOSITORY)
        self.assertTrue((self.output / "canonical-changes.json").exists())
        self.assertTrue((self.output / "canonical-changes.diff").exists())

    def test_older_matching_backup_records_age_without_arbitrary_expiry(self):
        prepared = self.prepared(canonical=True)
        old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        self.history(capture_completed_at=old.isoformat())
        prepared = self.prepared()
        result, _ = self.invoke_apply(prepared, API())
        self.assertGreater(result["history_age_seconds_at_apply"], 24 * 60 * 60)
        self.assertIn("Refresh", result["history_freshness"])

    def test_gated_apply_creates_only_exact_blank_public_destination_then_main(self):
        api = API(organization=True)
        state, calls = self.invoke_apply(self.prepared(canonical=True), api)
        writes = [call for call in api.calls if call[0] != "GET"]
        self.assertEqual(writes, [("POST", "/orgs/selected-owner/repos", {"name": "deckystream", "private": False, "auto_init": False}, False)])
        self.assertTrue(state["push_verified"])
        self.assertEqual(state["state"], "snapshot-pushed-post-migration-tests-unrun")
        pushes = [args for args in calls if "push" in args]
        self.assertEqual(len(pushes), 1)
        self.assertEqual(pushes[0][-2:], ("fresh-snapshot", "refs/heads/main:refs/heads/main"))
        self.assertIn("http.followRedirects=false", pushes[0])
        self.assertIn("http.https://github.com/" + DESTINATION + ".git.followRedirects=false", pushes[0])
        self.assertIn("remote.fresh-snapshot.mirror=false", pushes[0])
        self.assertFalse(any("--force" in a or a.startswith("+") for args in calls for a in args))
        self.assertEqual(json.loads((self.output / "apply-receipt.json").read_bytes()), state)
        self.assertFalse(any(any(word in call[1] for word in ("releases", "deployments", "actions", "archive")) for call in api.calls))

    def test_existing_destination_and_nonadmin_never_write(self):
        prepared = self.prepared(canonical=True)
        for api in (API(), API(organization=True)):
            if api.organization:
                api.role = "member"
            else:
                api.exists = True
            with self.assertRaises(M.PreparationError):
                self.invoke_apply(prepared, api)
            self.assertTrue(all(call[0] == "GET" for call in api.calls))
        self.assertFalse(self.output.exists())

    def test_live_source_id_and_default_sha_must_match_backup_before_creation(self):
        prepared = self.prepared(canonical=True)
        for changed in ("id", "sha"):
            api = API()
            request = api.request
            def changed_request(method, path, body=None, missing=False):
                response = request(method, path, body, missing)
                if changed == "id" and path == "/repos/" + M.SOURCE_REPOSITORY:
                    response["id"] = 11
                if changed == "sha" and path.endswith("/git/ref/heads/master"):
                    response["object"]["sha"] = "a" * 40
                return response
            with patch.object(api, "request", side_effect=changed_request), self.assertRaises(M.PreparationError):
                self.invoke_apply(prepared, api)
            self.assertTrue(all(c[0] == "GET" for c in api.calls))
        self.assertFalse(self.output.exists())

    def test_generated_drift_refuses_apply_before_authenticated_access(self):
        self.prepared(canonical=True)
        path = self.source / "steamdeck/product.py"
        path.write_text(path.read_text().replace("Stream from Steam Deck with OBS", "unreviewed projection drift"))
        self.commit()
        self.history()
        prepared = self.prepared()
        self.assertIn("steamdeck/product.py:generated-projection-drift", prepared[4]["apply_blockers"])
        api = API()
        with self.assertRaises(M.PreparationError):
            self.invoke_apply(prepared, api)
        self.assertEqual(api.calls, [])
        self.assertFalse(self.output.exists())

    def test_updater_canonical_identity_must_match_before_apply(self):
        self.prepared(canonical=True)
        self.put("steamdeck/releases.py", 'REPOSITORY = "szmyty/obsgod"\n')
        self.commit()
        self.history()
        api = API()
        with self.assertRaisesRegex(M.PreparationError, "steamdeck/releases.py"):
            self.invoke_apply(self.prepared(), api)
        self.assertEqual(api.calls, [])

    def test_collision_creation_failure_preserves_receipt_and_never_pushes(self):
        prepared = self.prepared(canonical=True)
        api = API()
        api.fail_create = True
        with self.assertRaisesRegex(M.PreparationError, "Creation refused"):
            self.invoke_apply(prepared, api)
        state = json.loads((self.output / "apply-receipt.json").read_bytes())
        self.assertEqual(state["state"], "creation-attempted-outcome-unknown")
        self.assertIsNone(state["remote_created"])
        self.assertTrue(state["creation_attempted"])
        self.assertEqual([c[0] for c in api.calls if c[0] != "GET"], ["POST"])

    def test_push_failure_preserves_partial_destination_without_delete(self):
        api = API()
        with self.assertRaisesRegex(M.PreparationError, "Push unavailable"):
            self.invoke_apply(self.prepared(canonical=True), api, push_fails=True)
        state = json.loads((self.output / "apply-receipt.json").read_bytes())
        self.assertEqual(state["state"], "push-attempted-outcome-unknown")
        self.assertTrue(state["remote_created"])
        self.assertFalse(state["push_verified"])
        self.assertTrue(state["push_attempted"])
        self.assertFalse(any(call[0] in {"DELETE", "PATCH", "PUT"} for call in api.calls))
        self.assertTrue((self.output / "source.tar").exists())

    def test_new_destination_refs_never_authorize_a_push_or_cleanup(self):
        prepared = self.prepared(canonical=True)
        api = API()
        with self.assertRaisesRegex(M.PreparationError, "already has refs"):
            self.invoke_apply(prepared, api, remote_refs=b"fixture existing ref")
        self.assertFalse(any(call[0] == "DELETE" for call in api.calls))
        self.assertEqual(json.loads((self.output / "apply-receipt.json").read_bytes())["state"], "created-not-pushed")

    def test_post_push_verification_failure_keeps_destination_and_uncertainty(self):
        api = API()
        api.fail_verify = True
        with self.assertRaisesRegex(M.PreparationError, "Verification unavailable"):
            self.invoke_apply(self.prepared(canonical=True), api)
        state = json.loads((self.output / "apply-receipt.json").read_bytes())
        self.assertEqual(state["state"], "pushed-verification-pending")
        self.assertTrue(state["remote_created"])
        self.assertTrue(state["push_attempted"])
        self.assertFalse(state["push_verified"])
        self.assertFalse(any(c[0] in {"DELETE", "PATCH", "PUT"} for c in api.calls))


class Transport(unittest.TestCase):
    def test_gh_explicit_get_status_and_auth_errors_cannot_be_absence(self):
        api = M.GitHub()
        for status, code, expected in ((404, 1, None), (401, 1, "error"), (403, 1, "error"), (302, 0, "error")):
            result = subprocess.CompletedProcess([], code, ("HTTP/2.0 " + str(status) + " Example\r\nContent-Type: application/json\r\n\r\n{}\n").encode(), b"PRIVATE TOKEN SHOULD NOT PRINT")
            with patch.object(M.subprocess, "run", return_value=result) as command:
                if expected == "error":
                    with self.assertRaises(M.PreparationError) as error:
                        api.request("GET", "/repos/" + DESTINATION, missing=True)
                    self.assertNotIn("PRIVATE", str(error.exception))
                else:
                    self.assertIsNone(api.request("GET", "/repos/" + DESTINATION, missing=True))
                self.assertEqual(command.call_args.args[0], ["gh", "api", "--hostname", "github.com", "--include", "--method", "GET", "/repos/" + DESTINATION])

    def test_cli_explicit_apply_and_destination_arguments_are_required(self):
        for args in ([], ["--source-sha", "a" * 40], ["--source-sha", "a" * 40, "--destination", DESTINATION, "--apply"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                M.main(args)


if __name__ == "__main__":
    unittest.main()
