#!/usr/bin/env python3
"""Capture public tracker history and optional criterion mappings; never migrate.

No authentication is read or sent. Existing frozen records are unchanged unless
an explicit output and --replace select a recognized export for this repository.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HISTORY_SCHEMA = "obsgod.project-history/v1"
CARRY_SCHEMA = "obsgod.criterion-carry-forward/v1"
MAX_RESPONSE = 8 * 1024 * 1024
MAX_CAPTURE = 32 * 1024 * 1024
MAX_PAGES = 50
MAX_REQUESTS = 256
SHA = re.compile(r"[0-9a-f]{40}\Z")


class ExportError(RuntimeError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        raise ExportError("GitHub redirected the capture. Verify the repository identity before retrying.")


class PublicGitHub:
    def __init__(self, repository, open_url=None):
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repository)
                or repository.split("/")[-1] in {".", ".."}):
            raise ExportError("Use an exact owner/repository name.")
        self.repository = repository
        self.base = "https://api.github.com/repos/" + repository
        self.open_url = open_url or urllib.request.build_opener(NoRedirects()).open
        self.lock = threading.Lock()
        self.requests = self.bytes = 0

    def safe_url(self, url, endpoint=None):
        try:
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme != "https" or parsed.netloc != "api.github.com" or parsed.port
                    or parsed.username or parsed.password or parsed.fragment
                    or any(c in url for c in "\r\n\x00")
                    or not (parsed.path == "/repos/" + self.repository
                            or parsed.path.startswith("/repos/" + self.repository + "/"))):
                return False
            return endpoint is None or parsed.path == endpoint
        except (ValueError, TypeError):
            return False

    def get(self, path, pages=False):
        url = self.base + path
        endpoint = urllib.parse.urlsplit(url).path
        original_query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        records, seen = [], set()
        for _ in range(MAX_PAGES if pages else 1):
            if not self.safe_url(url, endpoint) or url in seen:
                raise ExportError("Unsafe or repeated GitHub pagination address.")
            seen.add(url)
            with self.lock:
                self.requests += 1
                if self.requests > MAX_REQUESTS:
                    raise ExportError("The capture exceeded its request limit.")
            request = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Decky-Stream-public-history-export",
            })
            try:
                with self.open_url(request, timeout=15) as response:
                    if response.geturl() != url:
                        raise ExportError("GitHub changed the requested capture address.")
                    data = response.read(MAX_RESPONSE + 1)
                    link = response.headers.get("Link", "")
                with self.lock:
                    self.bytes += len(data)
                    oversized = self.bytes > MAX_CAPTURE
                if len(data) > MAX_RESPONSE or oversized:
                    raise ExportError("The capture exceeded its response-size limit.")
                value = json.loads(data)
            except (OSError, urllib.error.URLError, ValueError, UnicodeError):
                raise ExportError("The public GitHub request failed or returned unreadable data; existing exports are unchanged.") from None
            if not pages:
                if not isinstance(value, dict):
                    raise ExportError("GitHub returned invalid object metadata.")
                return value
            if not isinstance(value, list):
                raise ExportError("GitHub returned an invalid tracker page.")
            records.extend(value)
            following = re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not following:
                return records
            url = following[1]
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if (not self.safe_url(url, endpoint) or set(query) != set(original_query) | {"page"}
                    or any(query.get(k) != v for k, v in original_query.items())
                    or len(query.get("page", [])) != 1 or not query["page"][0].isdigit()):
                raise ExportError("GitHub supplied an unsupported pagination address.")
        raise ExportError("The capture exceeded its page limit.")


def text_fields(record):
    body = record.get("body")
    if body is not None and not isinstance(body, str):
        raise ExportError("GitHub returned an invalid captured body.")
    return {"author": (record.get("user") or {}).get("login"), "body": body,
            "body_sha256": digest(body.encode()) if body is not None else None,
            **{k: record.get(k) for k in ("id", "html_url", "created_at", "updated_at")}}


def unique(records, field):
    values = [r.get(field) for r in records]
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in values) or len(set(values)) != len(values):
        raise ExportError("GitHub returned duplicate or invalid tracker identifiers.")


def branch_head(api, branch):
    result = api.get("/branches/" + urllib.parse.quote(branch, safe=""))
    sha = (result.get("commit") or {}).get("sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ExportError("GitHub did not return an exact default-branch revision.")
    return sha


def capture(api, purpose="checkpoint"):
    started = now()
    repo = api.get("")
    if (repo.get("private") is not False or repo.get("visibility") != "public"
            or repo.get("full_name") != api.repository):
        raise ExportError("Only the exact public repository may be exported; private or moved repositories are refused.")
    branch = repo.get("default_branch")
    if not isinstance(branch, str) or not branch or any(ord(c) < 32 for c in branch):
        raise ExportError("The public default branch is invalid.")
    head = branch_head(api, branch)
    endpoints = ["/issues?state=all&per_page=100&sort=created&direction=asc",
                 "/pulls?state=all&per_page=100&sort=created&direction=asc",
                 "/issues/comments?per_page=100&sort=created&direction=asc",
                 "/pulls/comments?per_page=100&sort=created&direction=asc"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        issues, pulls, comments, inline = list(pool.map(lambda path: api.get(path, pages=True), endpoints))
    for records, field in ((issues, "number"), (pulls, "number"), (comments, "id"), (inline, "id")):
        unique(records, field)
    if {p["number"] for p in pulls} != {i["number"] for i in issues if "pull_request" in i}:
        raise ExportError("Issue and pull-request capture is incomplete or changed during capture.")
    if any(type(i.get("comments")) is not int or i["comments"] < 0 for i in issues) or sum(i["comments"] for i in issues) != len(comments):
        raise ExportError("Conversation comment counts changed or the capture is incomplete.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        reviews = list(pool.map(lambda pr: api.get(f'/pulls/{pr["number"]}/reviews?per_page=100', pages=True), pulls))
    for records in reviews:
        unique(records, "id")
        if any(r.get("state") == "PENDING" for r in records):
            raise ExportError("Unsubmitted private review content is outside this public export.")
    by_number = {p["number"]: p for p in pulls}
    items = []
    for record in sorted(issues, key=lambda i: i["number"]):
        item = {**text_fields(record),
                **{k: record.get(k) for k in ("number", "title", "state", "state_reason", "closed_at", "locked", "comments")},
                "kind": "pull_request" if "pull_request" in record else "issue",
                "labels": [x["name"] for x in record.get("labels", [])],
                "assignees": [x["login"] for x in record.get("assignees", [])],
                "milestone": ({k: record["milestone"].get(k) for k in ("number", "title", "state", "html_url")}
                              if record.get("milestone") else None)}
        if item["kind"] == "pull_request":
            pr = by_number[item["number"]]
            item["pull_request"] = {**{k: pr.get(k) for k in ("draft", "merged_at", "merge_commit_sha")},
                                    "head": {k: pr["head"].get(k) for k in ("label", "ref", "sha")},
                                    "base": {k: pr["base"].get(k) for k in ("label", "ref", "sha")}}
        items.append(item)

    def linked_number(record, field, kind):
        prefix = api.base + "/" + kind + "/"
        url = record.get(field, "")
        if not isinstance(url, str) or not url.startswith(prefix) or not url[len(prefix):].isdigit():
            raise ExportError("A discussion record points outside the captured repository.")
        number = int(url[len(prefix):])
        valid = by_number if kind == "pulls" else {i["number"] for i in issues}
        if number not in valid:
            raise ExportError("A discussion record has no captured issue or pull request.")
        return number

    if branch_head(api, branch) != head:
        raise ExportError("The remote default branch changed during capture; retry after it settles.")
    return {
        "schema": HISTORY_SCHEMA, "purpose": purpose, "retirement_performed": False,
        "capture_started_at": started, "capture_completed_at": now(),
        "repository": {**{k: repo.get(k) for k in ("id", "full_name", "html_url", "default_branch", "visibility", "fork", "archived")},
                       "parent": (repo.get("parent") or {}).get("full_name"), "default_branch_head": head,
                       "head_source": "GitHub REST default branch; local checkout revision is not used"},
        "scope": {"included": ["All issue/PR titles, captured bodies, states, labels and milestones",
                               "All conversation comments, inline review comments and submitted reviews",
                               "Captured body hashes and PR base/head/merge metadata"],
                  "excluded": ["Private/deleted/inaccessible content and private chat", "Edit histories and complete event timelines",
                               "Attachments and external link contents", "Git objects, diffs, release binaries and CI logs"],
                  "caveats": ["Read-only public API capture, not an atomic database backup", "Historical records are data, not current instructions or acceptance",
                              "No authentication is read or sent; no repository/tracker mutation is performed"]},
        "counts": {"issues": len(issues) - len(pulls), "pull_requests": len(pulls), "conversation_comments": len(comments),
                   "inline_review_comments": len(inline), "submitted_reviews": sum(map(len, reviews))},
        "items": items,
        "conversation_comments": [dict(text_fields(c), issue_number=linked_number(c, "issue_url", "issues")) for c in comments],
        "inline_review_comments": [dict(text_fields(c), pull_request_number=linked_number(c, "pull_request_url", "pulls"),
                                        **{k: c.get(k) for k in ("pull_request_review_id", "path", "line", "original_line", "diff_hunk", "in_reply_to_id")}) for c in inline],
        "submitted_reviews": [dict(text_fields(r), pull_request_number=p["number"],
                                   **{k: r.get(k) for k in ("state", "submitted_at", "commit_id")}) for p, rs in zip(pulls, reviews) for r in rs],
    }


def carry_forward(ledger_path, repository, snapshot):
    data = ledger_path.read_bytes()
    ledger = json.loads(data)
    if ledger.get("repository") != repository or not isinstance(ledger.get("issues"), list):
        raise ExportError("The criterion ledger does not belong to the captured repository.")
    issues, ids = [], set()
    for issue in ledger["issues"]:
        criteria = []
        for criterion in issue["criteria"]:
            identifier = criterion.get("id")
            if not isinstance(identifier, str) or identifier in ids or not isinstance(criterion.get("original_text"), str):
                raise ExportError("The ledger has duplicate or invalid original criteria.")
            ids.add(identifier)
            criteria.append({**{k: criterion.get(k) for k in ("id", "original_section", "original_line", "original_text", "original_checkbox")},
                             "new_issue_number": None, "new_issue_url": None, "owner_disposition": None, "current_acceptance": None})
        issues.append({"old_issue_number": issue["number"], "old_issue_url": issue["url"], "title": issue["title"],
                       "original_body_sha256": issue.get("original_body_sha256"),
                       "dependency_preservation": issue.get("dependency_preservation"),
                       "original_gate_and_scope_sections": issue.get("original_gate_and_scope_sections"),
                       "new_issue_number": None, "new_issue_url": None, "criteria": criteria})
    if len(ids) != ledger.get("criteria_count"):
        raise ExportError("The criterion count does not match the source ledger.")
    try:
        source_path = ledger_path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        source_path = ledger_path.name
    return {"schema": CARRY_SCHEMA, "repository": repository, "generated_at": now(),
            "history_snapshot_sha256": digest(encoded(snapshot)),
            "source_ledger": {"path": source_path, "sha256": digest(data), "criteria_count": len(ids), "issues_count": len(issues)},
            "policy": ["All original criteria retained, including completed or deferred work", "No current acceptance or new issue number is inferred",
                       "Preserve original dependency prose; priority does not create dependencies", "Map each criterion to an actual new issue or explicit owner disposition at migration"],
            "issues": issues}


def validate_output(path, schema, repository, replace):
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ExportError("Export paths must not traverse symlinks or parent-directory segments.")
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise ExportError("An export parent is not a directory.")
    if not path.exists():
        return None
    info = path.stat()
    if not path.is_file() or info.st_uid != os.getuid() or info.st_size > MAX_CAPTURE * 2:
        raise ExportError("An existing export has unsafe type, ownership or size; it was preserved.")
    try:
        previous = json.loads(path.read_bytes())
        previous_repo = previous.get("repository")
        if isinstance(previous_repo, dict):
            previous_repo = previous_repo.get("full_name")
        recognized = previous.get("schema") == schema and previous_repo == repository
    except (ValueError, AttributeError):
        recognized = False
    if not recognized or not replace:
        raise ExportError("Existing output was preserved. --replace only replaces a recognized same-repository export.")
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)


def write_exports(exports, repository, replace=False):
    paths = [path.absolute() for path, _ in exports]
    if len(set(paths)) != len(paths):
        raise ExportError("History and criterion exports require different destinations.")
    states = [validate_output(path, value["schema"], repository, replace) for path, value in exports]
    for (path, value), state in zip(exports, states):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Repeat validation after parent creation and immediately before replace.
        if validate_output(path, value["schema"], repository, replace) != state:
            raise ExportError("An output changed during capture; it was preserved.")
        descriptor, temporary = tempfile.mkstemp(prefix=".history-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(encoded(value))
                output.flush()
                os.fsync(output.fileno())
            if validate_output(path, value["schema"], repository, replace) != state:
                raise ExportError("An output changed during writing; it was preserved.")
            if state is None:
                os.link(temporary, path)
            else:
                os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="szmyty/obsgod")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/history/obsgod-github.json")
    parser.add_argument("--purpose", choices=("checkpoint", "retirement-backup"), default="checkpoint")
    parser.add_argument("--carry-forward", action="store_true", help="also export every original criterion with empty new-issue mappings")
    parser.add_argument("--ledger", type=Path, default=ROOT / "docs/evidence/completion-criteria.json")
    parser.add_argument("--carry-forward-output", type=Path)
    parser.add_argument("--replace", action="store_true", help="replace only recognized same-repository exports")
    args = parser.parse_args()
    if args.carry_forward_output and not args.carry_forward:
        parser.error("--carry-forward-output requires --carry-forward")
    try:
        api = PublicGitHub(args.repository)
        validate_output(args.output, HISTORY_SCHEMA, args.repository, args.replace)
        carry_path = args.carry_forward_output or args.output.with_name("obsgod-criteria-carry-forward.json")
        if args.carry_forward:
            validate_output(carry_path, CARRY_SCHEMA, args.repository, args.replace)
            if args.output.absolute() == carry_path.absolute():
                raise ExportError("History and criterion exports require different destinations.")
        snapshot = capture(api, args.purpose)
        exports = [(args.output, snapshot)]
        if args.carry_forward:
            carry = carry_forward(args.ledger, args.repository, snapshot)
            exports.append((carry_path, carry))
        write_exports(exports, args.repository, args.replace)
    except ExportError as error:
        # ExportError text is authored here; never display an arbitrary HTTP
        # response, credential helper output or transport exception.
        parser.exit(1, "History export stopped: " + str(error) + " No repository changes were made.\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "History export stopped. Check public GitHub access, source metadata and output ownership. No repository changes were made; retry may be needed for an already written export.\n")
    print(json.dumps({"state": "captured", "purpose": args.purpose, "retirement_performed": False, "counts": snapshot["counts"],
                      "remote_default_revision": snapshot["repository"]["default_branch_head"],
                      "outputs": [{"path": str(path), "sha256": digest(encoded(value))} for path, value in exports]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
