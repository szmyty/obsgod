# Read-only destination and dependency-review evidence

Issue #95 and #88's post-migration service checks need facts from the **actual
chosen public repository and an actual pull request**. Migration, an enabled
Graph setting, available authentication, local ACT and a successful dependency
comparison are separate facts. This maintainer collector prepares evidence;
it never chooses/creates a destination or changes its settings.

[`scripts/destination-readiness.py`](../scripts/destination-readiness.py) uses
Python's standard library and existing `gh` authentication. It asks
`gh auth token --hostname github.com` through a bounded captured subprocess;
missing `GH_TOKEN`/`GITHUB_TOKEN` variables do not establish missing authentication.
The credential stays in memory and is sent only to exact `api.github.com`
HTTPS GET requests. It is never printed, written to reports, put in an argument,
or sent through a redirect. If existing gh authentication cannot be resolved,
public unauthenticated reads remain possible and that limitation is recorded.
End users installing the plugin do not need this maintainer tool or gh.

## Collect a checkpoint

Use an explicit existing repository and real PR number. This concrete command
can inspect the current compatible repository; **it cannot qualify a future
destination or resolve its existing Graph/billing gates**:

```bash
umask 077
deckystream_readiness_parent=$(mktemp -d)
python3 scripts/destination-readiness.py \
  --repository szmyty/obsgod \
  --pull-request 114 \
  --output "$deckystream_readiness_parent/current-repository"
```

The output directory must be new, under existing protected ancestry. Existing
reports, links and unsafe paths are preserved. It contains `readiness.json` and
`readiness.md`. Keep them for review before sharing. A closed/merged PR can still
provide a real historical base/head observation; no synthetic ACT refs are used.
After an approved migration, supply the actual chosen `OWNER/deckystream` and
its real PR number, rather than treating the example above as destination proof.

Exit codes:

- **0:** the bounded source/service observations support review. This is still
  not a Graph-setting, required-review, migration, issue-closure or release approval.
- **3:** evidence was collected but at least one gate is unavailable/incomplete.
  Inspect both report files. This is expected for the current billing/capability
  block, an empty docs-only comparison, pending jobs or missing manifest evidence.
- **1:** invalid/inaccessible metadata, changed source-object binding or unsafe
  output prevented collection. No raw server/credential text is printed.

There is no retry, Graph-enable, workflow-run, publish or deploy option. Do not
repeat a known account billing refusal hoping it becomes a source pass.

## What the packet records

- Exact public repository ID, supplied name, default branch, fork state and
  available authenticated permission flags. Admin access does not imply that
  every dependency service is available. The source policy expects default
  `main` and a confirmed standalone destination; it never renames either.
- The real PR's repository identity and exact base/head, default revision and
  exact commit/tree/blob identities. The default revision and PR metadata are
  read again at the end; changed/unavailable refs leave a gate. A public fork PR
  head is bound to its actual public head repository, not a guessed local branch.
- Committed `go.mod` and `steamdeck/decky/package-lock.json` at the default and
  PR-head revisions. Npm lockfile v2/v3 shape and Go module directive are observed;
  package scripts/dependencies are not executed or installed.
- Exact-head workflow/action pins, ordinary mapping-style dependency-review job
  permissions, real-PR guard and `fail-on-severity: high`. High covers both high
  and critical findings; a critical-only policy does not meet that observation.
  Known `warn-only`/`continue-on-error` weakening, expanded non-PR guards,
  unpinned action uses and unsupported YAML shapes remain unconfirmed. Known publishing/deployment markers
  are listed conservatively; their absence does not audit arbitrary invoked code.
- One repository SBOM request and **one exact real base...head comparison**.
  HTTP403 remains permission/capability uncertainty; HTTP404 remains
  missing/inaccessible/unsupported uncertainty. Neither proves Graph disabled.
  A 200 empty comparison is an available empty diff, not ingestion or advisory
  success. The report separates committed manifests, SBOM ecosystem observations
  and manifest-specific real-PR changes. A docs-only PR may legitimately lack the
  evidence needed to establish both Go/npm ingestion; do not manufacture changes
  or claim that missing comparison evidence means dependencies are absent.
- Current-head GitHub Actions check/job metadata and actual step counts.
  Only a billing annotation plus zero steps and runner ID 0 is classified as
  a billing refusal before execution. A skip or zero-step success is not an
  executed dependency-review pass. An annotation that mentions billing while
  steps exist retains that conflict; it does not erase actual execution.
  A review success additionally requires its actual Actions run to bind this PR,
  base/head, repository, pull-request event and workflow path, plus success of
  the specifically named dependency-review action step. That label must be
  uniquely identifiable among the source job's steps and match exactly one
  successful runtime step. Duplicate, missing or unknown labels cannot establish
  execution; an unrelated success cannot stand in for a skipped/absent review.
  The review job's effective display identity must also be uniquely known across
  all source workflow jobs. Duplicate job names, dynamic names, matrix/reusable
  job identities or unsupported job mappings leave execution unconfirmed. A job
  ID cannot stand in for a different explicitly configured display name.
  Successful setup alone or another PR at the same head is insufficient.

The collector does **not** directly read or enable the Graph setting. The owner
must correlate its actual setting and manifest-ingestion evidence with these
bounded service observations. It also does not qualify the owner Deck/provider,
adoption, rights, publication, complete hosted CI or required human reviews.

## Bounds and privacy

All remote requests are GETs to the exact GitHub API host, redirects refused,
no retries. Limits are 64 requests, 2MiB per response, 16MiB total response data.
A 120-second budget is checked before new requests and incremental body reads;
the socket inactivity timeout is at most 8 seconds. This is not a hard overall
wall-clock guarantee for urllib's complete request/header exchange. It inspects at most 12
workflow files and 24 Actions jobs. Truncated trees/check pages, paginated comparison responses or omitted jobs
remain incomplete, rather than silently passing. The packet records its actual
request/byte counts and observed bounds.

Reports deliberately exclude PR bodies, annotation text/raw details, HTTP error
bodies, workflow contents, credentials, environment dumps and arbitrary server
messages. They retain named statuses, safe public IDs/labels, hashes and bounded
counts. Do not copy private logs/profiles/keys into the output directory. No
repository, account, workflow, protection, network/package preset or other
project is modified; no release, deployment, external message or spending occurs.

Focused maintainer verification:

```bash
python3 -B -m unittest discover -s scripts/tests -p test_destination_readiness.py -v
```

Attach the reviewed packet to #88 only for its actual repository/PR/revisions.
Retain unavailable/failed/skipped/unrun facts and original dependencies; a
collector report never closes #95 or passes its destination requirements alone.
