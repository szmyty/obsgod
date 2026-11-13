#!/usr/bin/env python3
"""Summarize exact-revision local-CI receipts without executing CI or publishing.

Writes report.json and report.md into a new directory. Logs/receipts stay private
and immutable. Exit 0 means the six local jobs passed with no unresolved local/PR
execution or evidence-integrity failure; known provider gates may still leave the
overall result partial. Exit 1 means local failure/incompleteness or unverifiable
evidence; 2 means invalid arguments/output paths. External proof stays separate.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("obsgod_local_ci", ROOT / "scripts/local-ci.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)
MAX_RECEIPT = 2_000_000
MAX_LOG = 256_000_000
MAX_EVENTS = 4000
SHA = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
USERINFO = re.compile(r"(https?://)[^\s/@]+@", re.I)
STATUSES = {"passed", "failed", "skipped", "unavailable", "unrun", "running", "partial"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_text(value):
    return USERINFO.sub(r"\1[redacted]@", ANSI.sub("", str(value)))


def safe_value(value):
    if isinstance(value, str):
        return private_text(value)
    if isinstance(value, list):
        return [safe_value(item) for item in value]
    if isinstance(value, dict):
        return {private_text(key): safe_value(item) for key, item in value.items()}
    return value


def option(command, flag):
    try:
        return command[command.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def plain_message(line):
    """Decode an ACT JSON record before inspecting its msg/message text."""
    line = ANSI.sub("", line.rstrip("\r\n"))
    try:
        record = json.loads(line)
    except (ValueError, TypeError):
        return private_text(line), {}, "text"
    if not isinstance(record, dict):
        return private_text(line), {}, "text"
    record = safe_value(record)
    message = record.get("msg", record.get("message"))
    if not isinstance(message, str):
        return private_text(line), record, "json"
    return private_text(message), record, "json"


def body(message):
    # Plain ACT prefixes an application's output with [workflow/job] | . JSON
    # mode often supplies the same prefix inside msg; support both forms.
    return re.sub(r"^\[[^\]\r\n]+\]\s*(?:\|\s?)?", "", message).strip()


def parse_log(data):
    events, diagnostics, failures, summaries = [], [], [], []
    counts = {"act_steps": Counter(), "go_test_events": Counter(),
              "go_package_events": Counter(), "records": Counter()}
    current_step, recent, pending_python, node = "unknown step", [], None, None
    truncated = 0

    def event(kind, status, line, **details):
        nonlocal truncated
        item = {"kind": kind, "status": status, "line": line, **details}
        if len(events) < MAX_EVENTS:
            events.append(item)
        else:
            truncated += 1

    for number, raw in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        message, record, format_ = plain_message(raw)
        counts["records"][format_] += 1
        text = body(message)
        step = record.get("step")
        if not isinstance(step, str):
            step = current_step
        start = re.search(r"(?:⭐\s*Run|Run step:)\s+(.+)", text)
        if start:
            current_step = private_text(start[1])[:300]
            recent = []
            event("act_step", "started", number, step=current_step)
        finished = re.search(r"(?:Success|Failure|Skipped)\s+-\s+(.+)", text)
        if finished:
            status = "failed" if "Failure" in finished[0] else "skipped" if "Skipped" in finished[0] else "passed"
            name = re.sub(r"\s+\[[^\]]+\]$", "", finished[1])[:300]
            counts["act_steps"][status] += 1
            event("act_step", status, number, step=name)
            if status == "failed":
                failures.append({"step": name, "line": number, "diagnostics": list(recent[-5:])})
        if re.search(r"::error::|\berror:|\bError:|permission denied|no space left|--- FAIL:|FAIL\s+github\.", text, re.I) or record.get("level") in ("error", "fatal"):
            diagnostic = {"line": number, "step": private_text(step)[:300], "message": text[:700]}
            if len(diagnostics) < 80:
                diagnostics.append(diagnostic)
            recent.append(diagnostic)

        nested = record if "Action" in record else None
        if nested is None and text.startswith("{"):
            try:
                value = json.loads(text)
                if isinstance(value, dict):
                    nested = value
            except ValueError:
                pass
        if nested and nested.get("Action") in ("pass", "fail", "skip"):
            status = {"pass": "passed", "fail": "failed", "skip": "skipped"}[nested["Action"]]
            kind = "go_test_events" if nested.get("Test") else "go_package_events"
            counts[kind][status] += 1
            event(kind, status, number, package=nested.get("Package"), test=nested.get("Test"))
        elif match := re.match(r"--- (PASS|FAIL|SKIP):\s+(\S+)", text):
            status = {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}[match[1]]
            counts["go_test_events"][status] += 1
            event("go_test_events", status, number, test=match[2])
        elif re.match(r"(?:ok|FAIL)\s+github\.", text):
            counts["go_package_events"]["passed" if text.startswith("ok") else "failed"] += 1

        if match := re.search(r"\bRan (\d+) tests? in ", text):
            pending_python = {"framework": "python-unittest", "tests": int(match[1]), "status": "unrun", "line": number}
            summaries.append(pending_python)
        elif pending_python is not None and re.match(r"(?:OK|FAILED)(?:\s|$|\()", text):
            values = {key: int(value) for key, value in re.findall(r"(failures|errors|skipped)=(\d+)", text)}
            failed = values.get("failures", 0) + values.get("errors", 0)
            skipped = values.get("skipped", 0)
            pending_python.update(status="passed" if text.startswith("OK") else "failed", failed=failed,
                                  skipped=skipped, passed=max(0, pending_python["tests"] - failed - skipped))
            pending_python = None
        if match := re.match(r"(?:#|ℹ(?:\ufe0f)?)\s+(tests|pass|fail|cancelled|skipped|todo)\s+(\d+)\s*$", text):
            if match[1] == "tests":
                node = {"framework": "node-test", "line": number, "tests": int(match[2])}
                summaries.append(node)
            elif node is not None:
                node[{"pass": "passed", "fail": "failed"}.get(match[1], match[1])] = int(match[2])
        if nested and "Action" not in nested and isinstance(nested.get("status"), str):
            numeric = {key: value for key, value in nested.items()
                       if key in ("case_count", "tests", "tests_passed", "tests_failed", "tests_skipped")
                       and isinstance(value, int) and not isinstance(value, bool)}
            if numeric:
                summaries.append({"framework": "structured-output", "line": number,
                                  "status": nested["status"], **numeric})
    return {"counts": {key: dict(value) for key, value in counts.items()}, "summaries": summaries,
            "events": events, "events_truncated": truncated, "diagnostics": diagnostics,
            "failed_steps": failures, "count_scope": "Observed log events/summaries only; missing test-level output is not a zero-test proof."}


def raw_result(receipt):
    code = receipt.get("exit_code")
    if isinstance(code, int) and not isinstance(code, bool):
        return "passed" if code == 0 else "failed"
    return receipt.get("result", receipt.get("outcome", "unrun"))


def load_run(path, receipt, revision):
    command = receipt.get("command", [])
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        command = []
    action = receipt.get("action", receipt.get("job", option(command, "-j") or "unknown"))
    recorded = receipt.get("result", receipt.get("outcome", raw_result(receipt)))
    recorded = {"pass": "passed", "fail": "failed", "skip": "skipped"}.get(recorded, recorded)
    status = recorded if recorded in STATUSES else "unrun"
    raw = raw_result(receipt)
    if raw == "failed" and status == "passed":
        status = "failed"
    clean = not receipt["dirty"] if isinstance(receipt.get("dirty"), bool) else receipt.get("source_clean_after")
    event = receipt.get("event") or next((value for value in command if value in ("push", "pull_request", "workflow_dispatch")), None)
    is_pr = bool(receipt.get("pull_request_fixture")) or event == "pull_request"
    channel = "pr-static" if action == "lint" and is_pr else "provider" if action == "dependency-review" else "local" if action in CI.JOBS else "inspection"
    stamp = receipt.get("started_utc")
    if not isinstance(stamp, str):
        match = re.search(r"\d{8}T\d{6}Z", path.name)
        stamp = match[0] if match else path.stem
    runner = receipt.get("runner_image")
    digest = runner.split("@sha256:", 1)[1] if isinstance(runner, str) and "@sha256:" in runner else None
    run = {"id": path.stem, "revision": revision, "action": action, "channel": channel,
           "started_utc": stamp, "source_clean": clean, "status": status, "raw_result": raw,
           "recorded_result": recorded, "exit_code": receipt.get("exit_code"), "event": event,
           "receipt": str(path), "receipt_sha256": sha(path.read_bytes()), "log": str(path.with_suffix(".log")),
           "command": safe_value(command), "command_sha256": sha(json.dumps(command, separators=(",", ":")).encode()),
           "provenance": {key: safe_value(receipt.get(key)) for key in (
               "source_tree", "tracked_diff_sha256", "workflow_sha256", "act", "act_binary_sha256",
               "launcher_sha256", "actrc_sha256", "runner_image", "action_sources", "log_format", "log_record_counts")},
           "runner_digest_sha256": digest if digest and SHA.fullmatch(digest) else None,
           "integrity": "unavailable", "qualifies_clean_source": False, "observations": None}
    log = path.with_suffix(".log")
    expected = receipt.get("log_sha256")
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        run["evidence_error"] = "missing_or_invalid_log_sha256"
    elif log.is_symlink() or not log.is_file() or log.stat().st_size > MAX_LOG:
        run["evidence_error"] = "adjacent_log_missing_unsafe_or_oversized"
    else:
        data = log.read_bytes()
        run["log_sha256"] = sha(data)
        if run["log_sha256"] != expected:
            run["evidence_error"] = "adjacent_log_sha256_mismatch"
        else:
            run["integrity"] = "verified"
            run["observations"] = parse_log(data)
            run["qualifies_clean_source"] = clean is True
    if run["integrity"] != "verified":
        run["status"] = "unavailable"
    return run


def classify(action, text):
    lower = text.lower()
    if action == "dependency-review" and any(word in lower for word in ("not supported", "dependency graph", "403", "resource not accessible")):
        return "provider_gate", "Restore the repository's real dependency-review/graph/API capability with its owner; rerun the real PR check. Synthetic act cannot replace it."
    if "no space left" in lower or "disk quota" in lower:
        return "environment_storage", "Inspect free disk; preserve evidence and select only disposable cache cleanup, then rerun this exact job."
    if "permission denied" in lower or "eacces" in lower:
        return "environment_permissions", "Inspect ownership of the named generated output; preserve it and rebuild under the intended user. Keep production root guards enabled."
    if any(word in lower for word in ("certificate verify", "unknown authority", "local issuer certificate", "certificate signed by")):
        return "environment_trust", "Verify inherited proxy and combined CA mounts; preserve TLS verification and existing network/package presets before retrying."
    if "cannot connect to the docker daemon" in lower:
        return "environment_docker", "Restore the existing managed local Docker capability; inspect its diagnostics without starting a competing daemon."
    return "workflow_failure", "Reproduce the captured job from the exact clean revision, inspect its first failing step, repair the demonstrated source/fixture/environment cause, and retain the new receipt."


def findings(runs, state):
    groups = {}
    for run in runs:
        if run["raw_result"] != "failed" or run["integrity"] != "verified":
            continue
        observed = run["observations"]
        steps = observed["failed_steps"] or [{"step": "unidentified failing step", "line": 1,
                                                "diagnostics": observed["diagnostics"][-5:]}]
        for step in steps:
            text = " ".join(item["message"] for item in step["diagnostics"]) or step["step"]
            category, remedy = classify(run["action"], text)
            signature = re.sub(r"\b[0-9a-f]{40,64}\b|/tmp/\S+|\d{4}-\d\d-\d\dT\S+", "<variable>", text)[:400]
            key = sha(json.dumps([run["action"], step["step"], category, signature]).encode())
            if key not in groups:
                supported = run["action"] in CI.JOBS
                command = ["python3", "scripts/local-ci.py", run["action"], "--state", str(state)] if supported else run["command"]
                if supported and run["command"]:
                    command += ["--act", run["command"][0]]
                if supported and run["channel"] == "pr-static":
                    command.append("--pull-request")
                groups[key] = {"fingerprint": key, "title": run["action"] + ": " + step["step"],
                               "category": category, "availability": "unavailable" if category == "provider_gate" else "not_assumed",
                               "raw_result": "failed", "disposition": "open", "occurrences": [],
                               "reproduction": {"revision": run["revision"], "command": command,
                                                "captured_command_requires_context_review": not supported},
                               "next_steps": ["Confirm a clean checkout of " + run["revision"] + ".", remedy,
                                              "Compare new evidence without overwriting these receipts; review private logs before sharing."],
                               "evidence": []}
            group = groups[key]
            group["occurrences"].append({"run": run["id"], "line": step["line"], "step": step["step"],
                                         "recorded_result": run["recorded_result"], "exit_code": run["exit_code"]})
            group["evidence"].append({"receipt": run["receipt"], "log": run["log"], "line": step["line"],
                                      "log_sha256": run["log_sha256"], "diagnostics": step["diagnostics"]})
            later = [other for other in runs if other["action"] == run["action"] and other["channel"] == run["channel"]
                     and other["qualifies_clean_source"] and other["status"] == "passed" and other["started_utc"] > run["started_utc"]]
            if later:
                group["later_pass_receipts"] = sorted({other["receipt"] for other in later})
            else:
                group["has_unsuperseded_failure"] = True
    for group in groups.values():
        if not group.pop("has_unsuperseded_failure", False) and group.get("later_pass_receipts"):
            group["disposition"] = "superseded_by_later_pass"
    return sorted(groups.values(), key=lambda item: (item["disposition"], item["title"], item["fingerprint"]))


def build_report(state, revision):
    state = Path(state).resolve(strict=True)
    if not state.is_dir() or not REVISION.fullmatch(revision):
        raise ValueError("Use a state directory and full lowercase source SHA")
    runs, excluded, errors = [], [], []
    paths = sorted(state.glob("*.json"))
    if len(paths) > 1000:
        raise ValueError("State contains too many top-level JSON files; select one bounded local-CI state")
    for path in paths:
        receipt_like = bool(re.search(r"\d{8}T\d{6}Z|^receipt", path.name))
        if path.is_symlink() or path.stat().st_size > MAX_RECEIPT:
            if receipt_like:
                errors.append({"receipt": str(path), "reason": "unsafe_or_oversized_receipt"})
            continue
        try:
            receipt = json.loads(path.read_bytes())
        except (ValueError, OSError):
            if receipt_like:
                errors.append({"receipt": str(path), "reason": "receipt_json_unreadable"})
            continue
        if not isinstance(receipt, dict):
            continue
        source = receipt.get("revision", receipt.get("source_revision"))
        if not isinstance(source, str) or not REVISION.fullmatch(source):
            continue
        if source != revision:
            excluded.append({"receipt": str(path), "revision": source})
            continue
        # A platform/image probe may record a command and source revision, but
        # it is not an ACT execution receipt and need not have an adjacent log.
        if not any(isinstance(receipt.get(key), str) and receipt[key] for key in ("action", "job")):
            continue
        run = load_run(path, receipt, revision)
        runs.append(run)
        if run.get("evidence_error"):
            errors.append({"receipt": str(path), "reason": run["evidence_error"], "raw_result": run["raw_result"]})
    runs.sort(key=lambda run: (run["started_utc"], run["id"]))
    matrix = []
    for action, (workflow, job, event) in CI.JOBS.items():
        selected = [run for run in runs if run["action"] == action and run["channel"] == "local"]
        eligible = [run for run in selected if run["qualifies_clean_source"]]
        latest = eligible[-1] if eligible else None
        matrix.append({"action": action, "workflow": workflow, "job": job, "event": event,
                       "status": latest["status"] if latest else "unavailable" if selected else "unrun",
                       "selected_receipt": latest["receipt"] if latest else None,
                       "raw_result": latest["raw_result"] if latest else None,
                       "reason": None if latest else "No verified clean-source run for this matrix member."})
    groups = findings(runs, state)
    providers = [run for run in runs if run["channel"] == "provider"]
    gates = [{"member": "dependency-review (real PR/provider)", "status": "unavailable" if providers else "unrun",
              "raw_results": [run["raw_result"] for run in providers], "receipts": [run["receipt"] for run in providers],
              "reason": "PR static lint is separate; a local/synthetic event does not establish provider acceptance."}]
    for member in ("native Windows 2025", "native macOS 15", "Linux arm64 runtime", "actual Steam Deck/Flatpak/Gamescope/controller/audio", "provider viewer reception", "hosted GitHub CI/reviews/artifact delivery"):
        gates.append({"member": member, "status": "unrun", "reason": "Not established by these Linux ACT receipts."})
    local_result = "failed" if any(item["status"] == "failed" for item in matrix) else "passed" if all(item["status"] == "passed" for item in matrix) else "unavailable" if any(item["status"] == "unavailable" for item in matrix) else "unrun"
    open_execution_failure = any(group["disposition"] == "open" and group["category"] != "provider_gate" for group in groups)
    result = "failed" if errors or open_execution_failure or local_result == "failed" else "partial" if local_result != "passed" or any(gate["status"] != "passed" for gate in gates) else "passed"
    return {"schema_version": 1, "scope": "six supported local ACT jobs only; external gates remain explicit",
            "revision": revision, "state": str(state), "local_result": local_result,
            "overall_result": result, "result": result,
            "reporter_sha256": sha(Path(__file__).read_bytes()),
            "matrix_definition": {"path": "scripts/local-ci.py", "sha256": sha((ROOT / "scripts/local-ci.py").read_bytes()), "jobs": list(CI.JOBS)},
            "runs": runs, "local_matrix": matrix,
            "pr_static_runs": [run["id"] for run in runs if run["channel"] == "pr-static"],
            "external_gates": gates, "evidence_errors": errors, "excluded_other_revision_receipts": excluded,
            "failure_groups": groups,
            "counts": {"run_statuses": dict(Counter(run["status"] for run in runs)),
                       "raw_results": dict(Counter(run["raw_result"] for run in runs)),
                       "local_matrix": dict(Counter(item["status"] for item in matrix)),
                       "open_failure_groups": sum(group["disposition"] == "open" for group in groups)},
            "limitations": ["Only verified adjacent logs are parsed. Counts describe observed events/summaries, not unlogged tests.",
                            "Missing legacy provenance hashes remain null; current files do not reconstruct historical binaries/configuration.",
                            "Passed-job error text may be an expected negative control: it remains diagnostic, not a failure finding.",
                            "Private logs/reports require human review before sharing. No issue, provider action or publication is performed."]}


def md_text(value):
    return private_text(value).replace("\n", " ").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").replace("`", "'")


def link(path, line=None):
    target = str(Path(path).absolute()) + (":" + str(line) if line else "")
    return "[" + md_text(Path(path).name) + "](" + quote(target, safe="/:") + ")"


def markdown(report):
    lines = ["# Local CI report", "", "Source: `" + report["revision"] + "` · Local result: **" + report["local_result"] + "** · Overall: **" + report["overall_result"] + "**.",
             "", "Six supported Linux ACT jobs are separate from PR/provider, native-platform and physical-device gates.",
             "", "| Job | Status | Evidence |", "| --- | --- | --- |"]
    for item in report["local_matrix"]:
        lines.append("| " + item["action"] + " | " + item["status"] + " | " + (link(item["selected_receipt"]) if item["selected_receipt"] else "No verified clean-source receipt") + " |")
    lines += ["", "## Retained runs", "", "Raw outcomes, counts, commands and source/client/runner/workflow/configuration hashes are retained in report.json.",
              "", "| Run | Recorded / raw | Integrity / clean | Evidence |", "| --- | --- | --- | --- |"]
    for run in report["runs"]:
        lines.append("| " + md_text(run["id"]) + " | " + md_text(run["recorded_result"]) + " / " + md_text(run["raw_result"]) + " | " + run["integrity"] + " / " + str(run["source_clean"]) + " | " + link(run["receipt"]) + " · " + link(run["log"]) + " |")
    lines += ["", "## Actionable failure groups", ""]
    if not report["failure_groups"]:
        lines.append("No verified failed-run findings. This does not complete unrun or unavailable checks.")
    for group in report["failure_groups"]:
        lines += ["### " + md_text(group["title"]), "", "Classification: **" + group["category"] + "** · Raw execution: **failed** · " + group["disposition"] + ".", ""]
        command = shlex.join(group["reproduction"]["command"])
        lines += ["Reproduction (review captured context/placeholders before running):", "", "```sh", command.replace("```", "'''").replace("\r", " ").replace("\n", " "), "```", ""]
        lines += [str(number) + ". " + md_text(step) for number, step in enumerate(group["next_steps"], 1)]
        lines += ["", "Evidence: " + ", ".join(link(item["log"], item["line"]) for item in group["evidence"]), ""]
    lines += ["## Evidence errors", ""]
    lines += ["- " + link(item["receipt"]) + ": " + item["reason"] + ". Restore the original pair or retain a fresh run; do not edit a checksum to hide tampering." for item in report["evidence_errors"]] or ["None."]
    lines += ["", "## Separate gates", "", "PR static runs: " + (", ".join(md_text(item) for item in report["pr_static_runs"]) or "unrun") + ".", ""]
    lines += ["- " + item["member"] + ": **" + item["status"] + "**" + (" (raw " + ", ".join(item["raw_results"]) + ")" if item.get("raw_results") else "") + "." for item in report["external_gates"]]
    lines += ["", *["- " + item for item in report["limitations"]], ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        revision = args.revision.lower()
        report = build_report(args.state, revision)
        output = args.output.absolute()
        state = args.state.resolve()
        if output.is_symlink() or output.resolve().is_relative_to(state) or state.is_relative_to(output.resolve()):
            raise ValueError("Keep report output separate from its immutable input state")
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (output / "report.md").write_text(markdown(report))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"local_result": report["local_result"], "overall_result": report["overall_result"], "revision": revision, "report": str(output / "report.json"), "counts": report["counts"]}, sort_keys=True))
    return 0 if report["local_result"] == "passed" and report["overall_result"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
