#!/usr/bin/env python3
"""Collect bounded, GET-only GitHub destination/real-PR evidence; never migrate.

Existing ``gh auth token`` resolves injected/stored authentication. Its value is
held only in memory for exact api.github.com requests and never enters reports.
Missing gh authentication falls back to public reads, with that limit recorded.
"""
import argparse
import base64
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

SCHEMA = "deckystream.destination-readiness/v1"
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_RESPONSE = 2 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_REQUESTS = 64
MAX_SECONDS = 120
MAX_WORKFLOWS = 12
MAX_JOBS = 24
MANIFESTS = {"go.mod": "Go", "steamdeck/decky/package-lock.json": "npm"}
BILLING = "account is locked due to a billing issue"


class ReadinessError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ReadinessError(message)


def repository_name(value):
    require(isinstance(value, str) and REPOSITORY.fullmatch(value)
            and value.split("/")[1] not in {".", ".."}, "Use an exact owner/repository name.")
    return value


def positive(value):
    return type(value) is int and value > 0


def commit_sha(value):
    require(isinstance(value, str) and SHA.fullmatch(value), "GitHub returned an invalid exact revision.")
    return value


def label(value):
    # Only fixed-shape public labels; never arbitrary annotation/response text.
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9 ._()/,:'+@-]{1,160}", value) else "unconfirmed"


def gh_authentication():
    if not shutil.which("gh"):
        return None, {"source": "public-unauthenticated", "reason": "gh-unavailable"}
    try:
        result = subprocess.run(["gh", "auth", "token", "--hostname", "github.com"],
                                capture_output=True, timeout=8, check=False)
        token = result.stdout.decode("ascii").strip()
        if result.returncode == 0 and re.fullmatch(r"[A-Za-z0-9_.-]{8,512}", token):
            return token, {"source": "existing-gh-authentication", "credential_values_recorded": False}
    except (OSError, UnicodeError, subprocess.SubprocessError):
        pass
    return None, {"source": "public-unauthenticated", "reason": "existing-gh-authentication-unavailable"}


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        raise ReadinessError("redirect-refused")


class GitHub:
    """Exact-host GET transport with response/call/time budgets and no retries."""
    def __init__(self, token=None, open_url=None, clock=time.monotonic):
        self.token = token
        self.open_url = open_url or urllib.request.build_opener(NoRedirects()).open
        self.clock = clock
        self.started = clock()
        self.requests = self.bytes = 0

    def get(self, path):
        require(isinstance(path, str) and path.startswith("/repos/") and not path.startswith("//")
                and not any(c in path for c in "\r\n\x00\\") and "#" not in path,
                "Unsafe GitHub resource path.")
        parsed = urllib.parse.urlsplit(path)
        require(not parsed.scheme and not parsed.netloc and all(p not in {".", ".."} for p in parsed.path.split("/")),
                "Unsafe GitHub resource path.")
        parts = parsed.path.split("/")
        require(len(parts) >= 4, "Unsafe GitHub resource path.")
        repository_name(parts[2] + "/" + parts[3])
        if self.requests >= MAX_REQUESTS or self.bytes >= MAX_TOTAL or self.clock() - self.started >= MAX_SECONDS:
            return {"status": "unavailable", "reason": "request-budget", "http_status": None}
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "deckystream-destination-readiness"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        url = "https://api.github.com" + path
        request = urllib.request.Request(url, headers=headers, method="GET")
        self.requests += 1
        try:
            with self.open_url(request, timeout=min(8, max(0.1, MAX_SECONDS - (self.clock() - self.started)))) as response:
                require(response.geturl() == url, "redirect-refused")
                more_pages = bool(re.search(r';\s*rel="next"', getattr(response, "headers", {}).get("Link", "")))
                chunks, size = [], 0
                read = getattr(response, "read1", response.read)
                while size <= MAX_RESPONSE:
                    if self.clock() - self.started >= MAX_SECONDS:
                        self.bytes += size
                        return {"status": "unavailable", "reason": "request-budget", "http_status": 200}
                    chunk = read(min(65536, MAX_RESPONSE + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                raw = b"".join(chunks)
            self.bytes += len(raw)
            if len(raw) > MAX_RESPONSE or self.bytes > MAX_TOTAL:
                return {"status": "unavailable", "reason": "response-budget", "http_status": 200}
            return {"status": "ok", "http_status": 200, "data": json.loads(raw), "more_pages": more_pages}
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            return {"status": "unavailable", "http_status": code,
                    "reason": {401: "authentication", 403: "permission-or-capability", 404: "missing-or-inaccessible-or-unsupported",
                               429: "rate-limit"}.get(code, "http-error")}
        except ReadinessError:
            return {"status": "unavailable", "reason": "redirect-refused", "http_status": None}
        except (OSError, urllib.error.URLError, ValueError, UnicodeError):
            return {"status": "unavailable", "reason": "network-or-unreadable-response", "http_status": None}


def observation(reply):
    return {k: reply[k] for k in ("status", "http_status", "reason") if k in reply}


def repository_metadata(value, expected):
    require(isinstance(value, dict) and value.get("full_name") == expected and positive(value.get("id")),
            "Repository identity did not match the explicit input.")
    require(value.get("private") is False and value.get("visibility") == "public",
            "Only a confirmed public repository may be collected.")
    default = value.get("default_branch")
    require(isinstance(default, str) and 0 < len(default) <= 200 and not any(ord(c) < 32 for c in default),
            "GitHub returned an invalid default branch.")
    permissions = value.get("permissions", {})
    return {"full_name": expected, "id": value["id"], "public": True, "default_branch": default,
            "fork": value.get("fork") if type(value.get("fork")) is bool else None,
            "archived": value.get("archived") if type(value.get("archived")) is bool else None,
            "authenticated_permissions": {k: permissions.get(k) if type(permissions.get(k)) is bool else None
                                          for k in ("admin", "maintain", "push", "pull")}}


def real_pr(value, repo):
    require(isinstance(value, dict) and positive(value.get("number")) and "base" in value and "head" in value,
            "GitHub did not return a real pull request.")
    base, head = value["base"], value["head"]
    require(isinstance(base, dict) and isinstance(head, dict), "Invalid pull-request ref metadata.")
    base_repo = base.get("repo") or {}
    require(base_repo.get("full_name") == repo["full_name"] and base_repo.get("id") == repo["id"],
            "Pull request does not belong to the explicit repository.")
    head_repo = head.get("repo") or {}
    require(head_repo.get("private") is False and positive(head_repo.get("id")),
            "Pull-request head repository is not confirmed public.")
    return {"number": value["number"], "state": value.get("state") if value.get("state") in {"open", "closed"} else "unknown",
            "draft": value.get("draft") if type(value.get("draft")) is bool else None,
            "base_sha": commit_sha(base.get("sha")), "head_sha": commit_sha(head.get("sha")),
            "head_repository": repository_name(head_repo.get("full_name")), "head_repository_id": head_repo["id"]}


def commit_tree(api, repo, sha):
    reply = api.get("/repos/" + repo + "/git/commits/" + sha)
    if reply["status"] != "ok":
        return None, observation(reply)
    data = reply["data"]
    require(isinstance(data, dict) and data.get("sha") == sha, "Commit response did not match the exact requested revision.")
    return commit_sha((data.get("tree") or {}).get("sha")), observation(reply)


def tree_entries(api, repo, tree):
    reply = api.get("/repos/" + repo + "/git/trees/" + tree + "?recursive=1")
    if reply["status"] != "ok":
        return None, observation(reply)
    data = reply["data"]
    require(isinstance(data, dict) and data.get("sha") == tree and isinstance(data.get("tree"), list), "Invalid exact-tree response.")
    if data.get("truncated") is not False:
        return None, {"status": "unavailable", "reason": "truncated-tree"}
    result = {}
    for entry in data["tree"]:
        path = entry.get("path")
        require(isinstance(path, str) and path not in result and not path.startswith("/")
                and not any(x in {".", ".."} for x in path.split("/")) and not any(ord(c) < 32 for c in path),
                "Invalid or duplicate tracked path.")
        result[path] = entry
    return result, observation(reply)


def blob(api, repo, entry, limit=512 * 1024):
    sha = commit_sha(entry.get("sha"))
    require(entry.get("type") == "blob" and entry.get("mode") in {"100644", "100755"}, "Refusing a linked or non-file source object.")
    reply = api.get("/repos/" + repo + "/git/blobs/" + sha)
    if reply["status"] != "ok":
        return None, observation(reply)
    data = reply["data"]
    require(isinstance(data, dict) and data.get("sha") == sha and data.get("encoding") == "base64"
            and isinstance(data.get("content"), str), "Invalid exact source blob.")
    try:
        raw = base64.b64decode("".join(data["content"].split()), validate=True)
    except ValueError:
        raise ReadinessError("Invalid source blob encoding.") from None
    require(len(raw) <= limit and data.get("size") == len(raw)
            and hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == sha,
            "Source blob contents did not match their bounded Git identity.")
    return raw, observation(reply)


def manifests(api, repo, entries, scope):
    rows = []
    for path, ecosystem in MANIFESTS.items():
        row = {"path": path, "ecosystem": ecosystem, "source_scope": scope}
        if entries is None or path not in entries:
            rows.append({**row, "status": "unavailable", "reason": "manifest-not-observed"})
            continue
        raw, result = blob(api, repo, entries[path])
        row.update(result)
        row["git_blob"] = entries[path]["sha"]
        if raw is not None:
            row["sha256"] = hashlib.sha256(raw).hexdigest()
            try:
                if ecosystem == "npm":
                    data = json.loads(raw)
                    require(isinstance(data, dict) and data.get("lockfileVersion") in {2, 3}
                            and isinstance(data.get("packages"), dict), "Unsupported npm lockfile shape.")
                    row.update(lockfile_version=data["lockfileVersion"], declared_package_entries=len(data["packages"]))
                else:
                    text = raw.decode("utf-8")
                    require(re.search(r"(?m)^module\s+\S+\s*$", text) is not None, "Unsupported Go module shape.")
                    row["module_directive_observed"] = True
            except (ValueError, UnicodeError, ReadinessError):
                row.update(status="unavailable", reason="unrecognized-manifest")
        rows.append(row)
    return rows


def permission_observation(text, indent):
    lines = text.splitlines()
    starts = [(i, line) for i, line in enumerate(lines) if re.match(r"^" + " " * indent + r"permissions\s*:", line)]
    if not starts:
        return {"status": "absent"}
    if len(starts) != 1:
        return {"status": "unknown"}
    index, line = starts[0]
    scalar = line.split(":", 1)[1].split("#", 1)[0].strip()
    if scalar:
        return {"status": "known", "read_only": scalar in {"read-all", "{}"}, "contents_read": scalar == "read-all"}
    values = {}
    for line in lines[index + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        match = re.fullmatch(r"\s+([a-z-]+):\s*(read|write|none)\s*(?:#.*)?", line)
        if not match:
            return {"status": "unknown"}
        if match[1] in values:
            return {"status": "unknown"}
        values[match[1]] = match[2]
    return {"status": "known", "read_only": bool(values) and all(v in {"read", "none"} for v in values.values()),
            "contents_read": values.get("contents") == "read"}


def source_step_labels(job):
    """Conservative labels for ordinary six-space step lists, without YAML execution.

    Unknown labels cannot establish uniqueness. In particular a successful step
    with a duplicate display name cannot substitute for the actual review action.
    """
    lines = job.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^      -\s+", line)]
    result = []
    for start, end in zip(starts, starts[1:] + [len(lines)]):
        block = lines[start:end]
        names, uses = [], []
        for line in block:
            match = re.fullmatch(r"(?:      -\s+|        )(name|uses):\s*(.+)", line)
            if match:
                value = match[2].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                (names if match[1] == "name" else uses).append(value)
        if len(names) == 1:
            name = label(names[0])
        elif not names and len(uses) == 1:
            name = label("Run " + uses[0])
        else:
            name = "unconfirmed"
        result.append({"name": name, "review_action": len(uses) == 1
                       and bool(re.fullmatch(r"actions/dependency-review-action@[^\s#]+", uses[0]))})
    return result


def source_jobs(lines):
    """Ordinary mapping-style jobs and their static effective display identities."""
    roots = [i for i, line in enumerate(lines) if re.fullmatch(r"jobs:\s*(?:#.*)?", line)]
    if len(roots) != 1:
        return [], False
    start, end = roots[0] + 1, len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip() and not lines[i].lstrip().startswith("#") and not lines[i].startswith(" "):
            end = i
            break
    boundaries = [i for i in range(start, end) if lines[i].strip() and not lines[i].lstrip().startswith("#")
                  and len(lines[i]) - len(lines[i].lstrip()) == 2]
    result, known, seen = [], True, set()
    for index, limit in zip(boundaries, boundaries[1:] + [end]):
        match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):\s*(?:#.*)?", lines[index])
        if not match:
            known = False
            continue
        identifier = match[1]
        if identifier in seen:
            known = False
        seen.add(identifier)
        body = "\n".join(lines[index + 1:limit])
        names = re.findall(r"(?m)^    name:\s*([^\n]+)", body)
        name = identifier if not names else "unconfirmed"
        if len(names) == 1:
            value = names[0].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            elif value[:1] in "'\"":
                value = "unconfirmed"
            name = label(value)
        # Matrix expansion, reusable jobs and YAML merges do not have a fully
        # known display identity in this deliberately small static observer.
        if re.search(r"(?m)^    (?:strategy|uses|<<):", body):
            name = "unconfirmed"
        if name == "unconfirmed":
            known = False
        result.append({"id": identifier, "name": name, "body": body})
    return result, known and bool(result)


def workflow_observation(path, raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return {"path": path, "status": "unknown", "reason": "workflow-not-utf8"}
    actions = []
    for match in re.finditer(r"(?m)^\s*-?\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([^\s#]+)", text):
        actions.append({"action": match[1], "pinned_commit": bool(SHA.fullmatch(match[2]))})
    all_uses = re.findall(r"(?m)^\s*-?\s*uses:\s*[^\n]+", text)
    dep_jobs = []
    lines = text.splitlines()
    jobs, job_identities_known = source_jobs(lines)
    for source_job in jobs:
        job = source_job["body"]
        action = re.search(r"(?m)^\s*-?\s*uses:\s*actions/dependency-review-action@([^\s#]+)", job)
        if not action:
            continue
        permissions = permission_observation(job, 4)
        if permissions["status"] == "absent":
            permissions = permission_observation(text, 0)
        workflow_name = re.search(r"(?m)^name:\s*([^\n#]+)", text)
        guard_line = re.search(r"(?m)^    if:\s*([^\n#]+)", job)
        guard = guard_line[1].strip() if guard_line else ""
        if guard.startswith("${{") and guard.endswith("}}"):
            guard = guard[3:-2].strip()
        pr_only = guard in {"github.event_name == 'pull_request'", 'github.event_name == "pull_request"'}
        weakening = any(value.strip().strip("'\"").lower() != "false"
                        for value in re.findall(r"(?m)^\s+(?:warn-only|continue-on-error):\s*([^\n#]+)", job))
        severity_values = re.findall(r"(?m)^\s+fail-on-severity:\s*([^\n#]+)", job)
        source_steps = source_step_labels(job)
        review_steps = [s for s in source_steps if s["review_action"]]
        expected_step = review_steps[0]["name"] if len(review_steps) == 1 else "unconfirmed"
        target_count = sum(s["name"] == expected_step for s in source_steps) if expected_step != "unconfirmed" else 0
        unique_target = (len(review_steps) == 1 and target_count == 1
                         and all(s["name"] != "unconfirmed" for s in source_steps))
        display_count = sum(j["name"] == source_job["name"] for j in jobs) if source_job["name"] != "unconfirmed" else 0
        dep_jobs.append({"job_id": source_job["id"], "job_name": source_job["name"],
                         "job_source_display_name_count": display_count,
                         "job_source_display_unique": job_identities_known and display_count == 1,
                         "workflow_path": path, "review_step_name": expected_step,
                         "review_step_source_label_count": target_count,
                         "review_step_label_unique": unique_target,
                         "workflow_name": label(workflow_name[1].strip()) if workflow_name else "unconfirmed",
                         "action_commit_pinned": bool(SHA.fullmatch(action[1])),
                         "high_and_critical_policy": len(severity_values) == 1 and severity_values[0].strip().strip("'\"") == "high" and not weakening,
                         "weakening_or_unknown_error_policy": weakening,
                         "pr_only_guard_observed": pr_only,
                         "permissions": permissions})
    markers = []
    for kind, pattern in {"release-command": r"\bgh\s+release\s+(?:create|upload)\b",
                          "git-push": r"\bgit\s+push\b", "package-publish": r"\b(?:npm|pnpm)\s+publish\b",
                          "deployment-action": r"(?:actions/deploy-pages|peaceiris/actions-gh-pages|cloudflare/pages-action|JamesIves/github-pages-deploy-action)@"}.items():
        if re.search(pattern, text, re.I):
            markers.append(kind)
    if "goreleaser" in text and not re.search(r"--snapshot\b[^\n]*--skip=publish(?:,sign)?\b", text):
        markers.append("goreleaser-needs-manual-review")
    return {"path": path, "status": "observed", "sha256": hashlib.sha256(raw).hexdigest(),
            "actions": actions, "dependency_review_jobs": dep_jobs, "known_write_markers": markers,
            "job_display_identities_confirmed": job_identities_known,
            "all_action_uses_commit_pinned": len(actions) == len(all_uses) and all(a["pinned_commit"] for a in actions),
            "side_effect_scope": "Conservative static markers only; absence is not proof that arbitrary invoked scripts cannot publish/deploy."}


def comparison_observation(reply, base, head):
    result = {**observation(reply), "base_sha": base, "head_sha": head}
    if reply["status"] != "ok":
        return result
    data = reply["data"]
    # REST dependency-graph/compare (diffRange) returns an array, not {diff:...}.
    require(isinstance(data, list), "Invalid dependency comparison response.")
    require(len(data) <= 2000, "Dependency comparison exceeds its record budget.")
    ecosystems, manifests_seen, vulnerabilities = collections.Counter(), collections.Counter(), 0
    for item in data:
        require(isinstance(item, dict), "Invalid dependency comparison record.")
        ecosystem = label(item.get("ecosystem"))
        ecosystems[ecosystem] += 1
        path = item.get("manifest")
        if path in MANIFESTS:
            manifests_seen[path] += 1
        findings = item.get("vulnerabilities", [])
        if isinstance(findings, list):
            vulnerabilities += len(findings)
    result.update(status="available-partial" if reply.get("more_pages") else "available-changes" if data else "available-empty",
                  coverage="first-page-only" if reply.get("more_pages") else "complete-response", change_count=len(data),
                  ecosystem_counts=dict(ecosystems), expected_manifest_change_counts=dict(manifests_seen), vulnerability_count=vulnerabilities,
                  scope="Exact real PR base...head comparison. Empty diff is not proof of manifest ingestion or advisory policy success.")
    return result


def sbom_observation(reply):
    result = observation(reply)
    if reply["status"] != "ok":
        return result
    data = reply["data"]
    packages = (data.get("sbom") or {}).get("packages") if isinstance(data, dict) else None
    require(isinstance(packages, list) and len(packages) <= 10000, "Invalid or oversized dependency SBOM.")
    counts = {"Go": 0, "npm": 0}
    for package in packages:
        refs = package.get("externalRefs", []) if isinstance(package, dict) else []
        ecosystems = set()
        for ref in refs if isinstance(refs, list) else []:
            locator = ref.get("referenceLocator", "") if isinstance(ref, dict) else ""
            if isinstance(locator, str):
                if locator.startswith("pkg:golang/"):
                    ecosystems.add("Go")
                elif locator.startswith("pkg:npm/"):
                    ecosystems.add("npm")
        for ecosystem in ecosystems:
            counts[ecosystem] += 1
    result.update(package_count=len(packages), ecosystem_package_counts=counts,
                  scope="Repository SBOM observation; not cryptographic proof that these packages were ingested from a particular PR-head lockfile.")
    return result


def hosted_jobs(api, repo, head, targets, pr, repo_id):
    reply = api.get("/repos/" + repo + "/commits/" + head + "/check-runs?per_page=100")
    result = {**observation(reply), "jobs": [], "review_jobs": [], "coverage": "unavailable"}
    if reply["status"] != "ok":
        return result
    data = reply["data"]
    require(isinstance(data, dict) and isinstance(data.get("check_runs"), list), "Invalid check-run response.")
    rows = data["check_runs"]
    complete = type(data.get("total_count")) is int and data["total_count"] == len(rows)
    selected = [x for x in rows if isinstance(x, dict) and (x.get("app") or {}).get("slug") == "github-actions"]
    if len(selected) > MAX_JOBS:
        complete = False
    run_cache = {}
    for check in selected[:MAX_JOBS]:
        row = {"check_run_id": check.get("id"), "name": label(check.get("name")), "status": "unavailable"}
        if not positive(check.get("id")) or check.get("head_sha") != head:
            row["reason"] = "check-head-unbound"
            complete = False
            result["jobs"].append(row)
            continue
        url = check.get("details_url", "")
        match = re.fullmatch(r"https://github\.com/" + re.escape(repo) + r"/actions/runs/([1-9][0-9]*)/job/([1-9][0-9]*)", url)
        if not match:
            row["reason"] = "job-url-unbound"
            complete = False
            result["jobs"].append(row)
            continue
        job_reply = api.get("/repos/" + repo + "/actions/jobs/" + match[2])
        if job_reply["status"] != "ok":
            row.update(observation(job_reply))
            complete = False
            result["jobs"].append(row)
            continue
        job = job_reply["data"]
        require(isinstance(job, dict) and job.get("id") == int(match[2]) and job.get("run_id") == int(match[1])
                and job.get("head_sha") == head and isinstance(job.get("steps"), list), "Hosted job did not match the exact head/check route.")
        steps = job["steps"]
        require(len(steps) <= 100, "Hosted step list exceeds its budget.")
        conclusion = job.get("conclusion") if job.get("conclusion") in {"success", "failure", "cancelled", "skipped", "neutral", "timed_out", "action_required", None} else "unknown"
        executed = sum(isinstance(s, dict) and s.get("conclusion") in {"success", "failure", "cancelled", "timed_out"} for s in steps)
        row.update(status="observed", job_id=job["id"], run_id=job["run_id"], head_sha=head, conclusion=conclusion,
                   observed_step_count=len(steps), executed_step_count=executed,
                   runner_assigned=job.get("runner_id") > 0 if type(job.get("runner_id")) is int else None,
                   workflow_name=label(job.get("workflow_name")), classification="observed-job")
        if conclusion == "failure":
            annotations = api.get("/repos/" + repo + "/check-runs/" + str(check["id"]) + "/annotations?per_page=100")
            row["annotation_observation"] = observation(annotations)
            if annotations["status"] == "ok":
                values = annotations["data"]
                require(isinstance(values, list) and len(values) <= 100, "Invalid annotation page.")
                billing = any(isinstance(a, dict) and BILLING in str(a.get("message", "")).lower() for a in values)
                row["billing_annotation_observed"] = billing
                row["annotation_count"] = len(values)
                row["annotation_text_recorded"] = False
                expected_count = (check.get("output") or {}).get("annotations_count")
                annotations_complete = (not annotations.get("more_pages")
                                        and (expected_count is None or type(expected_count) is int and expected_count == len(values)))
                row["annotation_coverage"] = "complete-current-page" if annotations_complete else "partial-or-bounded"
                if not annotations_complete:
                    complete = False
                if billing and not steps and job.get("runner_id") == 0:
                    row["classification"] = "billing-refused-before-execution"
                elif billing:
                    row["classification"] = "billing-reported-with-execution-or-identity-uncertainty"
                else:
                    row["classification"] = "other-failure-observed"
            else:
                complete = False
                row["classification"] = "failure-cause-unavailable"
        elif conclusion == "skipped":
            row["classification"] = "skipped-not-a-pass"
        matching_targets = [t for t in targets if t["job_name"] != "unconfirmed" and row["name"] == t["job_name"]
                            and row["workflow_name"] == t["workflow_name"]]
        if matching_targets:
            row["dependency_review_job"] = True
            result["review_jobs"].append(job["id"])
            if job["run_id"] not in run_cache:
                run_cache[job["run_id"]] = api.get("/repos/" + repo + "/actions/runs/" + str(job["run_id"]))
            run_reply = run_cache[job["run_id"]]
            row["run_observation"] = observation(run_reply)
            bound = False
            if run_reply["status"] == "ok":
                run = run_reply["data"]
                require(isinstance(run, dict), "Invalid Actions run metadata.")
                run_prs = run.get("pull_requests", [])
                bound = (run.get("id") == job["run_id"] and run.get("head_sha") == head
                         and run.get("event") == "pull_request" and (run.get("repository") or {}).get("id") == repo_id
                         and run.get("path") in {t["workflow_path"] for t in matching_targets}
                         and isinstance(run_prs, list) and any(
                             isinstance(p, dict) and p.get("number") == pr["number"]
                             and (p.get("base") or {}).get("sha") == pr["base_sha"]
                             and (p.get("head") or {}).get("sha") == pr["head_sha"]
                             and ((p.get("base") or {}).get("repo") or {}).get("id") == repo_id
                             and ((p.get("head") or {}).get("repo") or {}).get("id") == pr["head_repository_id"] for p in run_prs))
            row["exact_pr_run_binding"] = bound
            eligible_targets = [t for t in matching_targets if t.get("review_step_label_unique") is True]
            expected_steps = {t["review_step_name"] for t in matching_targets if t["review_step_name"] != "unconfirmed"}
            runtime_matches = [step for step in steps if isinstance(step, dict) and step.get("name") in expected_steps]
            row["review_step_source_label_unique"] = len(matching_targets) == 1 and len(eligible_targets) == 1
            row["review_job_source_display_unique"] = (len(matching_targets) == 1
                                                        and matching_targets[0].get("job_source_display_unique") is True)
            row["review_step_runtime_match_count"] = len(runtime_matches)
            row["review_action_step_succeeded"] = (bound and row["review_job_source_display_unique"] and row["review_step_source_label_unique"]
                                                   and len(runtime_matches) == 1 and runtime_matches[0].get("conclusion") == "success")
        result["jobs"].append(row)
    result["coverage"] = "complete-current-page" if complete else "partial-or-bounded"
    result["counts"] = {"observed_jobs": len(result["jobs"]),
                        "billing_refusals": sum(x.get("classification") == "billing-refused-before-execution" for x in result["jobs"]),
                        "skipped": sum(x.get("conclusion") == "skipped" for x in result["jobs"]),
                        "observed_steps": sum(x.get("observed_step_count", 0) for x in result["jobs"]),
                        "other_failures": sum(x.get("classification") == "other-failure-observed" for x in result["jobs"])}
    return result


def collect(api, repo_name, pr_number, auth=None):
    repo_name = repository_name(repo_name)
    require(positive(pr_number), "Use a positive real pull-request number.")
    prefix = "/repos/" + repo_name
    report = {"schema": SCHEMA, "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "requested_repository": repo_name, "requested_pull_request": pr_number,
              "authentication": auth or {"source": "provided-test-transport"}, "observations": {}, "gates": [],
              "scope": "Read-only preparation. No issue criterion, actual migration, Graph setting, required review, device or publication acceptance is inferred.",
              "mutations_performed": False, "raw_annotation_or_pr_body_recorded": False}
    def get(key, path):
        reply = api.get(path)
        report["observations"][key] = observation(reply)
        return reply
    repo_reply = get("repository", prefix)
    if repo_reply["status"] != "ok":
        report["gates"].append("public-repository-identity-unavailable")
        return finish(api, report)
    repo = repository_metadata(repo_reply["data"], repo_name)
    report["repository"] = repo
    if repo["default_branch"] != "main":
        report["gates"].append("default-branch-is-not-main")
    if repo["fork"] is not False:
        report["gates"].append("standalone-destination-not-confirmed")
    pr_reply = get("pull_request", prefix + "/pulls/" + str(pr_number))
    if pr_reply["status"] != "ok":
        report["gates"].append("real-pr-unavailable")
        return finish(api, report)
    pr = real_pr(pr_reply["data"], repo)
    require(pr["number"] == pr_number, "GitHub returned a different pull request.")
    report["pull_request"] = pr
    if pr["head_repository"] != repo_name:
        head_reply = get("head_repository", "/repos/" + pr["head_repository"])
        if head_reply["status"] != "ok":
            report["gates"].append("public-head-repository-unavailable")
            return finish(api, report)
        head_meta = repository_metadata(head_reply["data"], pr["head_repository"])
        require(head_meta["id"] == pr["head_repository_id"], "Head repository identity changed.")
    branch_path = prefix + "/branches/" + urllib.parse.quote(repo["default_branch"], safe="")
    branch_reply = get("default_branch_start", branch_path)
    if branch_reply["status"] != "ok":
        report["gates"].append("default-revision-unavailable")
        return finish(api, report)
    default_sha = commit_sha((branch_reply["data"].get("commit") or {}).get("sha"))
    report["default_revision"] = default_sha
    trees = {}
    bindings = [("default", repo_name, default_sha), ("base", repo_name, pr["base_sha"]),
                ("head", pr["head_repository"], pr["head_sha"])]
    for scope, source_repo, sha in bindings:
        tree, result = commit_tree(api, source_repo, sha)
        report["observations"][scope + "_commit"] = result
        if tree:
            trees[scope] = tree
    if len(trees) != 3:
        report["gates"].append("exact-commit-binding-unavailable")
        return finish(api, report)
    report["commit_trees"] = trees
    head_entries, result = tree_entries(api, pr["head_repository"], trees["head"])
    report["observations"]["head_tree"] = result
    if default_sha == pr["head_sha"] and pr["head_repository"] == repo_name:
        default_entries = head_entries
    else:
        default_entries, result = tree_entries(api, repo_name, trees["default"])
        report["observations"]["default_tree"] = result
    report["committed_manifests"] = manifests(api, repo_name, default_entries, "default-revision")
    report["pr_head_manifests"] = manifests(api, pr["head_repository"], head_entries, "pr-head")
    if any(x["status"] != "ok" for x in report["committed_manifests"] + report["pr_head_manifests"]):
        report["gates"].append("supported-committed-manifests-unconfirmed")
    workflow_paths = sorted(p for p in head_entries or {} if re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", p))
    report["workflows"] = []
    if len(workflow_paths) > MAX_WORKFLOWS:
        report["gates"].append("workflow-inspection-bounded")
    for path in workflow_paths[:MAX_WORKFLOWS]:
        raw, result = blob(api, pr["head_repository"], head_entries[path], limit=128 * 1024)
        if raw is None:
            report["workflows"].append({"path": path, **result})
        else:
            report["workflows"].append({**workflow_observation(path, raw), "git_blob": head_entries[path]["sha"]})
    targets = [job for workflow in report["workflows"] for job in workflow.get("dependency_review_jobs", [])]
    policy = (bool(targets) and all(w.get("all_action_uses_commit_pinned") for w in report["workflows"] if w.get("dependency_review_jobs"))
              and all(t["action_commit_pinned"] and t["high_and_critical_policy"]
                                  and t["pr_only_guard_observed"] and t["permissions"].get("read_only") is True
                                  and t["permissions"].get("contents_read") is True for t in targets))
    report["dependency_review_policy_observed"] = policy
    if not policy:
        report["gates"].append("dependency-review-source-policy-needs-review")
    report["dependency_sbom"] = sbom_observation(get("dependency_sbom", prefix + "/dependency-graph/sbom"))
    comparison = comparison_observation(get("dependency_comparison", prefix + "/dependency-graph/compare/"
                                            + pr["base_sha"] + "..." + pr["head_sha"]), pr["base_sha"], pr["head_sha"])
    report["dependency_comparison"] = comparison
    if comparison["status"] not in {"available-changes", "available-empty"}:
        report["gates"].append("real-pr-dependency-comparison-unavailable")
    sbom = report["dependency_sbom"]
    ecosystem_observed = all(sbom.get("ecosystem_package_counts", {}).get(x, 0) > 0 for x in MANIFESTS.values())
    manifest_changes = set(comparison.get("expected_manifest_change_counts", {}))
    ingestion = ecosystem_observed and set(MANIFESTS) <= manifest_changes and comparison["status"] == "available-changes"
    report["manifest_ingestion"] = {"repository_ecosystems_observed_in_sbom": ecosystem_observed,
                                    "both_expected_manifests_observed_in_real_pr_comparison": set(MANIFESTS) <= manifest_changes,
                                    "source_specific_support": ingestion,
                                    "graph_enabled_setting": "not-directly-observed-by-this-collector",
                                    "scope": "Committed files, repository SBOM ecosystems and exact PR manifest changes are distinct observations. 404 does not establish disabled Graph; an empty comparison does not establish ingestion."}
    if not ingestion:
        report["gates"].append("both-manifest-ingestion-evidence-incomplete")
    report["hosted"] = hosted_jobs(api, repo_name, pr["head_sha"], targets, pr, repo["id"])
    review_success = any(j.get("dependency_review_job") and j.get("conclusion") == "success"
                         and j.get("review_action_step_succeeded") is True for j in report["hosted"]["jobs"])
    if not review_success:
        report["gates"].append("actual-executed-dependency-review-success-unconfirmed")
    if report["hosted"]["coverage"] != "complete-current-page":
        report["gates"].append("hosted-check-coverage-incomplete")
    final_pr = get("pull_request_end", prefix + "/pulls/" + str(pr_number))
    final_branch = get("default_branch_end", branch_path)
    final_repo = get("repository_end", prefix)
    stable = (final_pr["status"] == "ok" and final_branch["status"] == "ok" and final_repo["status"] == "ok"
              and repository_metadata(final_repo["data"], repo_name) == repo
              and real_pr(final_pr["data"], repo) == pr
              and ((final_branch["data"].get("commit") or {}).get("sha")) == default_sha)
    report["ref_binding_stable_during_capture"] = stable
    if not stable:
        report["gates"].append("repository-or-pr-refs-changed-or-end-check-unavailable")
    return finish(api, report)


def finish(api, report):
    report["readiness"] = "observations-supported-review-required" if not report["gates"] else "unavailable-or-incomplete"
    report["requests"] = {"count": api.requests, "response_bytes": api.bytes, "maximum_calls": MAX_REQUESTS,
                          "maximum_response_bytes": MAX_RESPONSE, "maximum_total_bytes": MAX_TOTAL,
                          "new_request_budget_seconds": MAX_SECONDS, "socket_inactivity_timeout_seconds": 8,
                          "retry_count": 0, "methods": ["GET"]}
    report["limits"] = ["This collector neither reads nor enables the actual Graph setting; correlate its bounded service observations with the destination owner's setting/manifest evidence.",
                        "Static workflow markers are not a full YAML/action/script security audit; no publication/deployment action is executed.",
                        "Auth/admin access, fork/default identity, source policy, comparison, ingestion and job billing are separate facts.",
                        "No raw PR body, annotation/error response, token, environment dump or workflow content is included.",
                        "The time budget is checked before requests and incremental body reads; urllib's socket inactivity timeout is not a hard end-to-end wall-clock guarantee.",
                        "No source merge, required review/CI, platform/device, migration, rights or publication acceptance is granted."]
    return report


def markdown(report):
    lines = ["# Destination readiness observations", "", "Repository: `" + report["requested_repository"] + "`; real PR #" + str(report["requested_pull_request"]) + ".",
             "", "Disposition: **" + report["readiness"] + "**. This is read-only evidence preparation, not issue closure or permission to migrate/publish.", ""]
    if "pull_request" in report:
        pr = report["pull_request"]
        lines += ["Exact PR base: `" + pr["base_sha"] + "`; head: `" + pr["head_sha"] + "`.", ""]
    if "repository" in report:
        repo = report["repository"]
        lines += ["Public repository ID " + str(repo["id"]) + "; default `" + label(repo["default_branch"]) + "`; fork=" + str(repo["fork"]) + ".", ""]
    hosted = report.get("hosted", {})
    if "counts" in hosted:
        lines += ["Hosted observed counts: `" + json.dumps(hosted["counts"], sort_keys=True) + "`. Zero-step billing refusals are unavailable execution, never source test passes.", ""]
    lines += ["## Remaining observations/gates", ""]
    lines += ["- `" + gate + "`" for gate in report["gates"]] or ["- Collected source/service observations support review; actual settings/required reviews and acceptance remain separate."]
    lines += ["", "## Limits", ""] + ["- " + item for item in report["limits"]]
    return "\n".join(lines) + "\n"


def write_report(output, report):
    output = output.absolute()
    require(".." not in output.parts and not output.exists() and not output.is_symlink(), "Use a new output directory; existing evidence is preserved.")
    for parent in (output.parent, *output.parent.parents):
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and (not hasattr(os, "getuid") or info.st_uid in {0, os.getuid()})
                and (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX), "Use protected owned output ancestry.")
    output.mkdir(mode=0o700)
    (output / "readiness.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "readiness.md").write_text(markdown(report))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Exact existing public owner/repository; never inferred")
    parser.add_argument("--pull-request", required=True, type=int, help="Existing real PR at that repository")
    parser.add_argument("--output", type=Path, required=True, help="New private report directory under existing protected ancestry")
    args = parser.parse_args(argv)
    try:
        repository_name(args.repository)
        require(positive(args.pull_request), "Use a positive real pull-request number.")
        token, auth = gh_authentication()
        report = collect(GitHub(token), args.repository, args.pull_request, auth)
        write_report(args.output, report)
        print(json.dumps({"readiness": report["readiness"], "gate_count": len(report["gates"]), "report": str(args.output.absolute()),
                          "mutations_performed": False}))
        return 3 if report["gates"] else 0
    except ReadinessError as error:
        # All ReadinessError messages are fixed authored text, never server bodies.
        parser.exit(1, "Readiness collection stopped: " + str(error) + " No GitHub changes were made.\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Readiness collection stopped: invalid/inaccessible metadata, source binding or output. No GitHub changes were made; no raw server or credential text is printed.\n")


if __name__ == "__main__":
    raise SystemExit(main())
