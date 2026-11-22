#!/usr/bin/env python3
"""Plan a fresh public OWNER/deckystream snapshot; --apply alone creates/pushes.

Preparation never writes to GitHub. Use a clean checkout at an explicit full SHA.
An optional new, private local output directory holds source.tar, plan.json and
criterion/history sidecars. Existing directories and repositories are preserved.
--stage-canonical-identity changes five explicit metadata/projection files only
in the snapshot, leaving the checkout and source.tar untouched. Review the
canonical diff/digests before applying. No generated code is executed.
Apply requires matching canonical metadata and a matching public history
export from export-project-history.py --purpose retirement-backup. It creates
one independent public repository and one main commit, with no release, settings
change, deployment, old-repository mutation, force push or automatic deletion.
"""
import argparse
import ast
import datetime
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile


SOURCE_REPOSITORY = "szmyty/obsgod"
SCHEMA = "obsgod.fresh-repository/v1"
HISTORY_SCHEMA = "obsgod.project-history/v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
SIDECARS = {
    "plan.json": "docs/history/fresh-repository-plan.json",
    "criteria-carry-forward.json": "docs/history/fresh-repository-carry-forward.json",
    "public-history.json": "docs/history/fresh-repository-public-history.json",
    "canonical-changes.json": "docs/history/fresh-repository-canonical-changes.json",
    "canonical-changes.diff": "docs/history/fresh-repository-canonical-changes.diff",
}
CANONICAL_PATHS = ("product.json", "steamdeck/product.py", "steamdeck/decky/src/product.ts",
                   "steamdeck/releases.py", ".identity/identity.json")
REQUIRED = ("LICENSE", "MEMORIAL.md", "CONTINUITY.md", "ROADMAP.md", "DECISIONS.md",
            "product.json", "scripts/generate-product.py", "steamdeck/product.py",
            "steamdeck/decky/src/product.ts", "steamdeck/releases.py",
            "docs/evidence/completion-criteria.json", "docs/history/obsgod-github.json",
            "docs/migration-review.md", "docs/selected-aurora.md", ".identity/identity.json")


class PreparationError(RuntimeError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def run(arguments, cwd=None, data=None):
    """Never shell-interpolate or expose credential helper/API error output."""
    environment = os.environ.copy()
    if arguments[0] == "git":
        # -C does not override these variables: inherited values could write a
        # caller's real index/object store during construction of the new tree.
        for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                    "GIT_NAMESPACE", "GIT_QUARANTINE_PATH", "GIT_PREFIX"):
            environment.pop(key, None)
        environment["GIT_NO_REPLACE_OBJECTS"] = "1"
        environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(arguments, cwd=cwd, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=environment, timeout=180, check=False)
    if result.returncode:
        raise PreparationError("A local preparation operation failed; no tool output containing credentials is printed.")
    return result.stdout


def git(source, *arguments, data=None):
    return run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), *arguments], data=data)


def destination_name(value):
    parts = value.split("/")
    if (len(parts) != 2 or not OWNER.fullmatch(parts[0]) or "--" in parts[0]
            or parts[0].upper() == "OWNER" or parts[1] != "deckystream"
            or value.casefold() == SOURCE_REPOSITORY.casefold()):
        raise PreparationError("Supply one exact, selected GitHub owner/deckystream (no placeholder, URL or wildcard).")
    return value


def safe_path(path):
    path = Path(path).absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise PreparationError("Paths may not traverse symlinks or parent-directory segments.")
    return path


def output_path(path, source):
    path = safe_path(path)
    if path == source or source in path.parents:
        raise PreparationError("The output directory must be outside the source checkout.")
    parent = path.parent
    if (os.path.lexists(path) or not parent.is_dir() or parent.stat().st_uid != os.getuid()
            or parent.stat().st_mode & 0o022):
        raise PreparationError("Use a nonexistent output directory in an existing private, owned parent; nothing is overwritten.")
    return path


def canonical_remote(value):
    allowed = {"https://github.com/" + SOURCE_REPOSITORY,
               "git@github.com:" + SOURCE_REPOSITORY,
               "ssh://git@github.com/" + SOURCE_REPOSITORY}
    return value.removesuffix(".git") in allowed


def source_snapshot(source, revision):
    source = safe_path(source)
    if not SHA.fullmatch(revision):
        raise PreparationError("--source-sha must be a full lowercase 40-character commit SHA.")
    if git(source, "rev-parse", "--show-toplevel").decode().strip() != str(source):
        raise PreparationError("--source must be the checkout root.")
    if git(source, "rev-parse", "HEAD").decode().strip() != revision:
        raise PreparationError("The explicit source SHA must equal the checked-out HEAD.")
    if git(source, "status", "--porcelain=v1", "--untracked-files=all"):
        raise PreparationError("Source must be clean, including untracked files; source files were preserved.")
    if not canonical_remote(git(source, "remote", "get-url", "origin").decode().strip()):
        raise PreparationError("Source origin must identify exactly " + SOURCE_REPOSITORY + ".")
    entries = {}
    for row in git(source, "ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path).parts
        if (kind != "blob" or mode not in {"100644", "100755", "120000"}
                or not parts or path.startswith("/") or any(p in {"..", ".git"} for p in parts)
                or any(ord(c) < 32 or ord(c) == 127 for c in path)):
            raise PreparationError("Unsupported or unsafe source tree entry; no partial snapshot is published.")
        entries[path] = {"mode": mode, "git_blob": oid}
    if any(path not in entries for path in REQUIRED):
        raise PreparationError("Source is missing required attribution, identity, history or backlog records.")
    if any(path in entries for path in SIDECARS.values()):
        raise PreparationError("Fresh migration sidecar paths already exist; refusing to overwrite prior migration evidence.")
    archive = git(source, "archive", "--format=tar", revision)
    payload = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as captured:
        for member in captured:
            if member.isdir():
                continue
            if member.name not in entries or member.name in payload:
                raise PreparationError("git archive contains unexpected or duplicate entries.")
            expected = entries[member.name]
            if member.issym() and expected["mode"] == "120000":
                data = member.linkname.encode("utf-8")
            elif member.isfile() and expected["mode"] != "120000":
                data = captured.extractfile(member).read()
                if bool(member.mode & 0o111) != (expected["mode"] == "100755"):
                    raise PreparationError("git archive changed source executable modes.")
            else:
                raise PreparationError("git archive changed a source entry type.")
            oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if oid != expected["git_blob"]:
                raise PreparationError("git archive changed source bytes (including export-subst); refusing publication.")
            payload[member.name] = data
            expected.update({"sha256": digest(data), "bytes": len(data)})
    if payload.keys() != entries.keys():
        raise PreparationError("git archive omitted tracked source (including export-ignore); refusing publication.")
    return source, archive, entries, payload


def recheck_source(source, revision):
    if (git(source, "rev-parse", "HEAD").decode().strip() != revision
            or git(source, "status", "--porcelain=v1", "--untracked-files=all")
            or not canonical_remote(git(source, "remote", "get-url", "origin").decode().strip())):
        raise PreparationError("The source checkout changed during preparation; no repository is created.")


def history_backup(path, revision):
    if path is None:
        return None
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise PreparationError("History backup must be a bounded regular public export.")
    value = json.loads(path.read_bytes())
    repo = value.get("repository", {})
    if (value.get("schema") != HISTORY_SCHEMA or value.get("purpose") != "retirement-backup"
            or value.get("retirement_performed") is not False or repo.get("full_name") != SOURCE_REPOSITORY
            or repo.get("visibility") != "public" or repo.get("default_branch_head") != revision
            or type(repo.get("id")) is not int or repo["id"] <= 0):
        raise PreparationError("Use a public retirement-backup export bound to the exact source default-branch SHA.")
    items, counts = value.get("items"), value.get("counts", {})
    if (not isinstance(items, list) or any(not isinstance(i, dict) for i in items)
            or sum(i.get("kind") == "issue" for i in items) != counts.get("issues")
            or sum(i.get("kind") == "pull_request" for i in items) != counts.get("pull_requests")):
        raise PreparationError("Public history item counts are inconsistent.")
    for field, count in (("conversation_comments", "conversation_comments"),
                         ("inline_review_comments", "inline_review_comments"),
                         ("submitted_reviews", "submitted_reviews")):
        if not isinstance(value.get(field), list) or len(value[field]) != counts.get(count):
            raise PreparationError("Public history discussion counts are inconsistent.")
    return value


def generated_product_outputs(product):
    """Pure rendering of the reviewed generate-product.py v1 contract.

    This deliberately executes neither the source nor the staged generator.
    Exact parity with the maintained generator is covered by fixture tests.
    """
    if product.get("schema_version") != 1:
        raise PreparationError("Unsupported product metadata schema; canonical staging is refused.")
    for key in ("display_name", "description", "repository"):
        value = product.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 120 or any(ord(c) < 32 for c in value):
            raise PreparationError("Invalid product metadata; canonical staging is refused.")
    expected = {"cli": "obsgod", "plugin": "OBSGod", "plugin_directory": "obsgod", "storage_namespace": "obsgod"}
    if product.get("compatibility") != expected:
        raise PreparationError("Installed compatibility identity changes are outside canonical snapshot staging.")
    frontend = {"displayName": product["display_name"], "description": product["description"],
                "repository": product["repository"], "compatibility": expected}
    ts = "// Generated by scripts/generate-product.py from product.json.\n"
    ts += "export const product = " + json.dumps(frontend, indent=2) + " as const;\nexport default product;\n"
    py = '"""Generated by scripts/generate-product.py from product.json."""\n'
    py += "DISPLAY_NAME = " + repr(product["display_name"]) + "\n"
    py += "DESCRIPTION = " + repr(product["description"]) + "\n"
    py += "REPOSITORY = " + repr(product["repository"]) + "\n"
    py += "CLI_NAME = " + repr(expected["cli"]) + "\nPLUGIN_ID = " + repr(expected["plugin"]) + "\n"
    return {"steamdeck/decky/src/product.ts": ts.encode(), "steamdeck/product.py": py.encode()}


def repository_assignment(data):
    tree = ast.parse(data)
    assignments = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "REPOSITORY"]
    stores = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "REPOSITORY" and isinstance(n.ctx, ast.Store)]
    if len(assignments) != 1 or len(stores) != 1 or not isinstance(assignments[0].value, ast.Constant):
        raise PreparationError("Updater repository must be one top-level literal assignment; policy rewrites are refused.")
    value = assignments[0].value
    if not isinstance(value.value, str):
        raise PreparationError("Updater repository literal is invalid.")
    return value


def canonical_gates(payload, destination):
    product = json.loads(payload["product.json"])
    gates = []
    if product.get("repository") != destination:
        gates.append("product.repository-must-equal-exact-destination")
    for path, expected in generated_product_outputs(product).items():
        if payload[path] != expected:
            gates.append(path + ":generated-projection-drift")
    if repository_assignment(payload["steamdeck/releases.py"]).value != destination:
        gates.append("steamdeck/releases.py:REPOSITORY-must-equal-exact-destination")
    identity = json.loads(payload[".identity/identity.json"])
    if identity.get("schema") != "identity.project/v1":
        raise PreparationError("Unsupported Identity schema; canonical staging is refused.")
    if identity.get("project", {}).get("repository") != "https://github.com/" + destination:
        gates.append(".identity/identity.json:project.repository-must-equal-exact-destination")
    return product, gates


def replace_json_repository(data, keys, destination):
    value = json.loads(data)
    leaf = value
    for key in keys[:-1]:
        leaf = leaf[key]
    previous = leaf[keys[-1]]
    if previous == destination:
        return data
    before = json.dumps(previous, ensure_ascii=False).encode()
    if not isinstance(previous, str) or data.count(before) != 1:
        raise PreparationError("Canonical JSON repository value is ambiguous; no broad replacement is permitted.")
    changed = data.replace(before, json.dumps(destination, ensure_ascii=False).encode(), 1)
    leaf[keys[-1]] = destination
    if json.loads(changed) != value:
        raise PreparationError("Canonical JSON staging changed an unrelated value.")
    return changed


def stage_canonical_identity(payload, destination):
    """Change only explicit canonical fields/projections in an in-memory copy."""
    product = json.loads(payload["product.json"])
    original_repository = product.get("repository")
    if original_repository not in (SOURCE_REPOSITORY, destination):
        raise PreparationError("Canonical staging accepts only the exact original source or selected destination repository.")
    for path, expected in generated_product_outputs(product).items():
        if payload[path] != expected:
            raise PreparationError("Source generated projections drift; repair/review the source before canonical staging.")
    assignment = repository_assignment(payload["steamdeck/releases.py"])
    identity = json.loads(payload[".identity/identity.json"])
    if (assignment.value != original_repository or identity.get("schema") != "identity.project/v1"
            or identity.get("project", {}).get("repository") != "https://github.com/" + original_repository):
        raise PreparationError("Source canonical repository fields disagree; no implicit mixed-identity repair is permitted.")
    staged = dict(payload)
    staged["product.json"] = replace_json_repository(payload["product.json"], ("repository",), destination)
    staged.update(generated_product_outputs(json.loads(staged["product.json"])))
    staged[".identity/identity.json"] = replace_json_repository(payload[".identity/identity.json"], ("project", "repository"), "https://github.com/" + destination)
    lines = payload["steamdeck/releases.py"].splitlines(keepends=True)
    start = sum(map(len, lines[:assignment.lineno - 1])) + assignment.col_offset
    end = sum(map(len, lines[:assignment.end_lineno - 1])) + assignment.end_col_offset
    staged["steamdeck/releases.py"] = payload["steamdeck/releases.py"][:start] + json.dumps(destination).encode() + payload["steamdeck/releases.py"][end:]
    changes, diffs = [], []
    for path in sorted(payload):
        if staged[path] == payload[path]:
            continue
        if path not in CANONICAL_PATHS:
            raise PreparationError("Canonical staging changed an unlisted file.")
        changes.append({"path": path, "before_sha256": digest(payload[path]), "after_sha256": digest(staged[path])})
        diffs.extend(difflib.unified_diff(payload[path].decode().splitlines(keepends=True),
                                        staged[path].decode().splitlines(keepends=True), fromfile="source/" + path, tofile="snapshot/" + path))
    if canonical_gates(staged, destination)[1]:
        raise PreparationError("Staged canonical projections do not agree exactly.")
    return staged, changes, "".join(diffs).encode()


def payload_archive(payload, inventory):
    """Deterministic source-only TAR, before adding plan/history sidecars."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path, data in sorted(payload.items()):
            member = tarfile.TarInfo(path)
            mode = inventory[path]["mode"]
            member.mode = 0o755 if mode == "100755" else 0o644
            if mode == "120000":
                member.type = tarfile.SYMTYPE
                member.linkname = data.decode()
                archive.addfile(member)
            else:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def criterion_carry(payload, destination):
    data = payload["docs/evidence/completion-criteria.json"]
    ledger = json.loads(data)
    if ledger.get("repository") != SOURCE_REPOSITORY or not isinstance(ledger.get("issues"), list):
        raise PreparationError("Original criterion ledger must retain its original source repository.")
    ids, issues = set(), []
    for issue in ledger["issues"]:
        for criterion in issue["criteria"]:
            key = criterion.get("id")
            if not isinstance(key, str) or key in ids or not isinstance(criterion.get("original_text"), str):
                raise PreparationError("Original criteria contain invalid or duplicate identifiers/text.")
            ids.add(key)
        issues.append({"original": issue, "destination_issue": None, "owner_disposition": None})
    if len(ids) != ledger.get("criteria_count"):
        raise PreparationError("Original criterion count does not match the ledger.")
    return {"schema": "obsgod.fresh-criterion-carry-forward/v1", "source_repository": SOURCE_REPOSITORY,
            "destination_repository": destination, "source_ledger_sha256": digest(data),
            "criteria_count": len(ids), "issues": issues,
            "policy": "Every original criterion, dependency and historical status is retained. No acceptance is inferred. Map every remainder to a real destination issue or explicit owner disposition; #46 closes last."}


class GitHub:
    """Bounded gh API calls to github.com, with explicit methods and no raw logs."""
    def request(self, method, path, body=None, missing=False):
        if (not path.startswith(("/repos/", "/users/", "/orgs/", "/user"))
                or any(c in path for c in ("\n", "\r", "?", "#", ".."))):
            raise PreparationError("Unsupported GitHub API path.")
        command = ["gh", "api", "--hostname", "github.com", "--include", "--method", method, path]
        if body is not None:
            command += ["--input", "-"]
        result = subprocess.run(command, input=encoded(body) if body is not None else None,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        raw = result.stdout.replace(b"\r\n", b"\n")
        header, separator, content = raw.partition(b"\n\n")
        match = re.match(rb"HTTP/\S+ (\d{3})\b", header)
        if not separator or not match or len(content) > 8 * 1024 * 1024:
            raise PreparationError("GitHub response is unavailable or unsupported; authentication errors are not absence.")
        status = int(match.group(1))
        if missing and status == 404:
            return None
        if result.returncode or status not in (200, 201):
            raise PreparationError("GitHub refused the exact operation; inspect access separately. No error body is printed.")
        return json.loads(content)


def verify_repo(value, name, independent=False):
    if (not isinstance(value, dict) or value.get("full_name") != name or type(value.get("id")) is not int
            or value["id"] <= 0 or value.get("private") is not False or value.get("visibility") != "public"
            or (independent and value.get("fork") is not False)):
        raise PreparationError("GitHub repository identity/visibility differs from the exact requested repository.")


def inspect_destination(api, destination, source_sha, source_id=None):
    owner = destination.split("/")[0]
    user = api.request("GET", "/user")
    account = api.request("GET", "/users/" + owner)
    if not isinstance(user.get("login"), str) or account.get("login") != owner:
        raise PreparationError("Authenticated user or canonical owner identity is unconfirmed.")
    kind = account.get("type")
    if kind == "User":
        if user["login"] != owner:
            raise PreparationError("The authenticated user must own the exact personal destination.")
        create_path = "/user/repos"
        authority = "authenticated-personal-owner"
    elif kind == "Organization":
        membership = api.request("GET", "/orgs/" + owner + "/memberships/" + user["login"])
        if membership.get("state") != "active" or membership.get("role") != "admin":
            raise PreparationError("An active administrator membership is required for the exact destination organization.")
        create_path = "/orgs/" + owner + "/repos"
        authority = "authenticated-organization-admin"
    else:
        raise PreparationError("Unsupported destination owner account type.")
    source = api.request("GET", "/repos/" + SOURCE_REPOSITORY)
    verify_repo(source, SOURCE_REPOSITORY)
    branch = source.get("default_branch")
    if (not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}", branch)
            or ".." in branch or "//" in branch or (source_id is not None and source["id"] != source_id)):
        raise PreparationError("Source repository ID/default branch differs from the public history backup.")
    ref = api.request("GET", "/repos/" + SOURCE_REPOSITORY + "/git/ref/heads/" + branch)
    if ref.get("object", {}).get("sha") != source_sha:
        raise PreparationError("The live source default branch must still equal the pinned snapshot/history SHA.")
    if api.request("GET", "/repos/" + destination, missing=True) is not None:
        raise PreparationError("The destination already exists; it is preserved and will never be overwritten or reused.")
    return {"state": "authenticated-owner-lookup-404", "authority": authority,
            "source_repository_id": source["id"], "source_default_branch": branch,
            "source_default_branch_sha": source_sha, "creation_endpoint": create_path,
            "limitation": "A 404 is not a global name reservation; creation must still succeed without collision. Repository policies, billing and hosted execution remain unqualified."}


def prepare(source, revision, destination, backup=None, api=None, stage_identity=False):
    destination = destination_name(destination)
    source, archive, inventory, payload = source_snapshot(source, revision)
    source_inventory = {path: dict(row) for path, row in inventory.items()}
    changes, canonical_diff = [], b""
    if stage_identity:
        payload, changes, canonical_diff = stage_canonical_identity(payload, destination)
        for change in changes:
            path = change["path"]
            data = payload[path]
            inventory[path] = {**inventory[path], "sha256": digest(data), "bytes": len(data),
                               "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
    snapshot_archive = payload_archive(payload, inventory)
    history = history_backup(backup, revision)
    product, gates = canonical_gates(payload, destination)
    carry = criterion_carry(payload, destination)
    if history is None:
        gates.append("fresh-public-retirement-history-backup-required")
    inspection = (inspect_destination(api, destination, revision,
                  history["repository"]["id"] if history else None)
                  if api is not None else {"state": "uninspected"})
    def paths(predicate):
        return [p for p in sorted(inventory) if predicate(p)]
    plan = {"schema": SCHEMA, "mode": "preparation", "source_repository": SOURCE_REPOSITORY,
            "source_sha": revision, "source_tree": git(source, "rev-parse", revision + "^{tree}").decode().strip(),
            "destination": destination, "default_branch": "main", "source_archive_sha256": digest(archive),
            "snapshot_archive_sha256": digest(snapshot_archive), "source_payload": source_inventory,
            "canonical_identity_staging": {"requested": stage_identity, "allowed_paths": list(CANONICAL_PATHS), "changes": changes,
                                            "scope": "Only product.repository, its two generated projections, updater REPOSITORY and Identity project.repository. Existing updater policy is unchanged apart from its exact repository literal. No binary/artifact qualification is inferred."},
            "payload": inventory, "preserved": {
                "license_attribution": paths(lambda p: any(t in p.lower() for t in ("license", "notice", "attribution"))),
                "branding_identity": paths(lambda p: p.startswith(("branding/", ".identity/")) or p == "product.json"),
                "history_backlog_evidence": paths(lambda p: p.startswith(("docs/history/", "docs/evidence/", "audits/", "docs/decisions/")) or p in ("MEMORIAL.md", "CONTINUITY.md", "ROADMAP.md", "DECISIONS.md", "docs/implementation-roadmap.md"))},
            "product_metadata": product, "criteria_count": carry["criteria_count"],
            "history_backup": ({"sha256": digest(encoded(history)), "counts": history["counts"],
                                "capture_completed_at": history.get("capture_completed_at"),
                                "freshness": "Refresh the public tracker export at actual retirement. Matching source SHA does not capture later issue/PR activity; apply records the observed capture age without an arbitrary expiry.",
                                "open_items": [{"number": i["number"], "kind": i["kind"], "title": i["title"]}
                                               for i in history["items"] if i.get("state") == "open"]} if history else None),
            "destination_inspection": inspection, "apply_blockers": gates,
            "sidecars_added_to_snapshot": [SIDECARS[p] for p in ("plan.json", "criteria-carry-forward.json", *(("public-history.json",) if history else ()), *(("canonical-changes.json", "canonical-changes.diff") if stage_identity else ()))],
            "unchanged_contracts": ["Original checkout/source.tar bytes are preserved. Only explicitly listed canonical snapshot fields/projections can change; historical URLs, evidence, licenses, branding provenance, installed IDs and secrets stay unchanged.",
                                    "Original source and Git history remain in the old repository and checkout.",
                                    "Public tracker backup excludes private/deleted content, attachments, Git objects and release binaries; retained old public artifact URLs are still required."],
            "owner_facts_visible": ["Exact destination selection and applicable creation authority", "Publisher/contact and artwork rights/license/name clearance", "Final product version and signing/unsigned policy", "Canonical support/site destinations and old-source/artifact retention"],
            "after_actual_migration_unrun": ["New canonical download/install and affected updater/repair/rollback/removal tests", "Real Steam Deck, provider/viewer and controller/audio/privacy acceptance", "Actual destination dependency graph, manifest ingestion and real PR dependency-review execution", "Remaining criterion mapping, independent adoption, review, rights and final v1 decision"],
            "initial_push": {"commit_message": "Initial deckystream snapshot [skip ci]", "branch": "main", "history": "one new root commit", "workflow_policy": "Existing workflow files are preserved. [skip ci] requests suppression for push/pull_request workflows; no jobs, skipped jobs or billing refusals are not passes. No Actions settings are changed."},
            "never_performed": ["release", "deployment", "repository transfer/rename", "archive/delete old or new repository", "force push", "repository settings changes", "issue closure or acceptance inference"]}
    sidecars = {"plan.json": encoded(plan), "criteria-carry-forward.json": encoded(carry)}
    if history is not None:
        sidecars["public-history.json"] = encoded(history)
    if stage_identity:
        sidecars["canonical-changes.json"] = encoded(plan["canonical_identity_staging"])
        sidecars["canonical-changes.diff"] = canonical_diff
    return source, archive, inventory, payload, plan, sidecars, snapshot_archive


def write_new(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_preparation(output, prepared):
    output.mkdir(mode=0o700)
    sync_directory(output.parent)
    write_new(output / "source.tar", prepared[1])
    write_new(output / "snapshot.tar", prepared[6])
    for name, data in prepared[5].items():
        write_new(output / name, data)


def receipt(output, value):
    # Only our own private output file is replaced, never a source/remote file.
    target = output / "apply-receipt.json"
    temporary = output / ".apply-receipt.json"
    write_new(temporary, encoded(value))
    if target.is_symlink():
        raise PreparationError("Receipt path changed; it was preserved.")
    os.replace(temporary, target)
    sync_directory(output)


def snapshot_commit(repository, payload, inventory, sidecars):
    run(["git", "init", "--bare", "--template=", "--object-format=sha1", "--initial-branch=main", str(repository)])
    index = []
    items = [(p, data, inventory[p]["mode"]) for p, data in payload.items()]
    items += [(SIDECARS[p], data, "100644") for p, data in sidecars.items()]
    for path, data, mode in sorted(items):
        oid = git(repository, "hash-object", "-w", "--stdin", data=data).decode().strip()
        index.append(mode.encode() + b" " + oid.encode() + b"\t" + path.encode() + b"\0")
    git(repository, "update-index", "-z", "--index-info", data=b"".join(index))
    tree = git(repository, "write-tree").decode().strip()
    commit = git(repository, "commit-tree", tree, "-m", "Initial deckystream snapshot [skip ci]").decode().strip()
    if not SHA.fullmatch(commit):
        raise PreparationError("Snapshot commit must be a full 40-character SHA1 before repository creation.")
    git(repository, "update-ref", "refs/heads/main", commit)
    return commit


def exact_push_remote(repository, destination):
    """Inspect both fetch/push URL expansion before any remote mutation."""
    url = "https://github.com/" + destination + ".git"
    git(repository, "remote", "add", "fresh-snapshot", url)
    for options in (("--all",), ("--all", "--push")):
        actual = git(repository, "remote", "get-url", *options, "fresh-snapshot").decode().splitlines()
        if actual != [url]:
            raise PreparationError("Git URL rewrite or multiple destination URLs detected; no repository is created or pushed.")
    return "fresh-snapshot"


def apply(prepared, output, api):
    source, _, inventory, payload, plan, sidecars = prepared[:6]
    # Revalidate the exact in-memory payload; execute no copied generator code.
    if canonical_gates(payload, plan["destination"])[1] != [g for g in plan["apply_blockers"] if g != "fresh-public-retirement-history-backup-required"]:
        raise PreparationError("Canonical snapshot payload changed after planning.")
    if plan["apply_blockers"]:
        raise PreparationError("Apply is blocked: " + "; ".join(plan["apply_blockers"]) + ". Prepare the reviewed canonical transition first.")
    history = json.loads(sidecars["public-history.json"])
    try:
        completed = datetime.datetime.fromisoformat(history["capture_completed_at"].replace("Z", "+00:00"))
        age = (datetime.datetime.now(datetime.timezone.utc) - completed).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise PreparationError("The public retirement-backup must record a valid capture timestamp with timezone.") from None
    inspection = inspect_destination(api, plan["destination"], plan["source_sha"], history["repository"]["id"])
    state = {"schema": SCHEMA, "state": "local-preparation", "destination": plan["destination"],
             "source_sha": plan["source_sha"], "source_repository_preserved": True,
             "history_capture_completed_at": history["capture_completed_at"], "history_age_seconds_at_apply": age,
             "history_freshness": "Refresh the public tracker export at actual retirement; matching source SHA does not capture later tracker activity.",
             "remote_created": False, "creation_attempted": False, "push_attempted": False, "push_verified": False,
             "recovery": "Preserve the source and any partial destination. Inspect this receipt and live repository before a new reviewed action; never delete or force push automatically."}
    write_preparation(output, prepared)
    receipt(output, state)
    try:
        with tempfile.TemporaryDirectory(prefix="fresh-deckystream-") as temporary:
            repository = Path(temporary) / "snapshot.git"
            state["snapshot_commit"] = snapshot_commit(repository, payload, inventory, sidecars)
            if not isinstance(state["snapshot_commit"], str) or not SHA.fullmatch(state["snapshot_commit"]):
                raise PreparationError("Snapshot commit must be a full 40-character SHA1 before repository creation.")
            remote = exact_push_remote(repository, plan["destination"])
            state["state"] = "ready-to-create"
            receipt(output, state)
            # Recheck immediately before creation; a collision fails creation and
            # cannot become permission to reuse an existing repository.
            inspect_destination(api, plan["destination"], plan["source_sha"], history["repository"]["id"])
            recheck_source(source, plan["source_sha"])
            state.update({"state": "creation-attempted-outcome-unknown", "creation_attempted": True, "remote_created": None})
            receipt(output, state)
            created = api.request("POST", inspection["creation_endpoint"],
                                  {"name": "deckystream", "private": False, "auto_init": False})
            state["state"] = "creation-response-unverified"
            if isinstance(created, dict) and type(created.get("id")) is int:
                state["destination_repository_id"] = created["id"]
            receipt(output, state)
            verify_repo(created, plan["destination"], independent=True)
            state.update({"remote_created": True, "state": "created-not-pushed"})
            receipt(output, state)
            url = "https://github.com/" + plan["destination"] + ".git"
            transport = ("-c", "http.followRedirects=false", "-c", "http." + url + ".followRedirects=false")
            if git(repository, *transport, "ls-remote", remote):
                raise PreparationError("The newly created destination already has refs; it is preserved without a push.")
            state.update({"state": "push-attempted-outcome-unknown", "push_attempted": True})
            receipt(output, state)
            git(repository, *transport, "-c", "push.followTags=false", "-c", "remote.fresh-snapshot.mirror=false",
                "push", "--porcelain", "--no-follow-tags",
                "--recurse-submodules=no", remote, "refs/heads/main:refs/heads/main")
            state["state"] = "pushed-verification-pending"
            receipt(output, state)
            actual = api.request("GET", "/repos/" + plan["destination"])
            verify_repo(actual, plan["destination"], independent=True)
            if actual["id"] != created["id"] or actual.get("default_branch") != "main":
                raise PreparationError("Destination ID or default main branch is unconfirmed; no settings are changed.")
            ref = api.request("GET", "/repos/" + plan["destination"] + "/git/ref/heads/main")
            if ref.get("object", {}).get("sha") != state["snapshot_commit"]:
                raise PreparationError("Destination main does not match the exact snapshot commit.")
            state.update({"state": "snapshot-pushed-post-migration-tests-unrun", "push_verified": True})
            receipt(output, state)
    except Exception:
        state["outcome"] = "stopped-with-state-preserved"
        receipt(output, state)
        raise
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--destination", required=True, help="exact selected OWNER/deckystream")
    parser.add_argument("--history-backup", type=Path, help="matching public retirement-backup from export-project-history.py; refresh at actual retirement")
    parser.add_argument("--output", type=Path, help="new local directory outside the source, inside a private owned parent")
    parser.add_argument("--inspect-destination", action="store_true", help="read authenticated owner/repository metadata using existing gh auth")
    parser.add_argument("--stage-canonical-identity", action="store_true", help="stage only five exact canonical metadata/projection files in snapshot.tar; preserve source.tar and checkout")
    parser.add_argument("--apply", action="store_true", help="create/push only the exact fresh public repository after all preconditions pass")
    args = parser.parse_args(argv)
    if args.apply and not args.output:
        parser.error("--apply requires a new --output directory for durable backup and recovery receipts")
    try:
        source = safe_path(args.source)
        output = output_path(args.output, source) if args.output else None
        api = GitHub()
        prepared = prepare(source, args.source_sha, args.destination, args.history_backup,
                           api if args.inspect_destination else None, args.stage_canonical_identity)
        if args.apply:
            result = apply(prepared, output, api)
        else:
            if output:
                write_preparation(output, prepared)
            result = prepared[4]
    except (PreparationError, OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError, tarfile.TarError):
        import sys
        error = sys.exc_info()[1]
        detail = str(error) if isinstance(error, PreparationError) else "Check source metadata, local paths, tools and access; raw error output is withheld."
        parser.exit(1, "Fresh repository preparation stopped: " + detail + " Source and existing repositories were preserved; inspect any output receipt for a partial new destination.\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
