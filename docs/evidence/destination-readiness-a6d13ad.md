# Destination readiness observations

Repository: `szmyty/obsgod`; real PR #114.

Disposition: **unavailable-or-incomplete**. This is read-only evidence preparation, not issue closure or permission to migrate/publish.

Exact PR base: `736be3e2964179f180de34d21dbe81dd33fd8c52`; head: `a6d13ad85b132101453dc76a7c96152cf47fcfdd`.

Public repository ID 1263344065; default `master`; fork=True.

Hosted observed counts: `{"billing_refusals": 15, "observed_jobs": 16, "observed_steps": 0, "other_failures": 0, "skipped": 1}`. Zero-step billing refusals are unavailable execution, never source test passes.

## Remaining observations/gates

- `default-branch-is-not-main`
- `standalone-destination-not-confirmed`
- `real-pr-dependency-comparison-unavailable`
- `both-manifest-ingestion-evidence-incomplete`
- `actual-executed-dependency-review-success-unconfirmed`

## Limits

- This collector neither reads nor enables the actual Graph setting; correlate its bounded service observations with the destination owner's setting/manifest evidence.
- Static workflow markers are not a full YAML/action/script security audit; no publication/deployment action is executed.
- Auth/admin access, fork/default identity, source policy, comparison, ingestion and job billing are separate facts.
- No raw PR body, annotation/error response, token, environment dump or workflow content is included.
- The time budget is checked before requests and incremental body reads; urllib's socket inactivity timeout is not a hard end-to-end wall-clock guarantee.
- No source merge, required review/CI, platform/device, migration, rights or publication acceptance is granted.
