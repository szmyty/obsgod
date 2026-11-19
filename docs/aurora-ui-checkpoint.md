# Aurora and native panel work checkpoint

Parent #46; bounded work [#80](https://github.com/szmyty/obsgod/issues/80)
and [#81](https://github.com/szmyty/obsgod/issues/81).
The owner authorized this batch after merging #111, with machine testing at the
end followed by final Steam Deck validation. This is an in-progress source
checkpoint, not artwork approval, qualification, release or issue closure.

## Functional UI source checkpoint — not qualified

Draft [#112](https://github.com/szmyty/obsgod/pull/112) now contains the
functional UI edits at exact source **3943f3c10189dc4b2cc7cc11bc98fe9501c0c1c0**, tree
**57e5eadf55c3802eecbfff737b3a3b119af57fab**. Later documentation-only commits are not
relabeled as that source. [Independent static review](evidence/aurora-ui-3943f3c-static-review.json)
records the exact eleven changed source/test blobs and its limits.

The source now places observed stream state and Start/Stop before setup, without
changing component order during polling. First-run configuration opens once;
saved destination and connection controls collapse. Leaving destination editing
clears private drafts, visibility, clipboard epoch and confirmation modals,
restores the saved public draft and does not mutate stored configuration.
Existing mutation/readiness/unknown-state guards remain unchanged.

Provider guides use the fixed public inventory and generic navigation failure
feedback. Clips distinguish loading, confirmed empty, populated and error states,
with explicit refresh and separate request identity. Hide invalidates late list
results; a local pending gate spans the complete request and final status
refresh so reopening cannot race it. Media action identity remains independent.
Health/recovery failures remain visible while details are collapsed, with
secret-free generic feedback. Optional Desktop Setup instructions describe the
existing bundled, authenticated loopback page; no new service is introduced.

Four focused Node test cases and the existing native-configuration/M3/panel
browser fixtures were extended. The fixture has controlled delayed/empty/failed
clip responses and a held final-status response; the race case first establishes
that hold and explicitly checks the global-busy-cleared/local-list-still-pending
window. These are authored tests, **not passing executions**.

Static review found and repaired two pre-execution gaps: clip-list pending could
outlive the global busy flag during final refresh, and an existing browser
assertion still expected the old “destination above” wording. The final race
fixture also uses explicit response synchronization rather than relying on
poll timing. These were source-review findings, not recorded runtime failures.
Independent final source/fixture review reports no remaining material findings;
it is not a formal GitHub approval, typecheck, build, browser/controller pass or
release qualification.

All new repository Node/typecheck/build/Python/browser/package/site checks
remain **UNRUN** because the execution server is unavailable. Limited authoring
language/static probes are not promoted into repository test results.
Aurora production source/exports, icon/logo integration, lowercase display
generation and actual-size/rendering evidence remain pending #80/#81. Both
issues stay open; this draft is not a test-ready installation.

## Current source and execution boundary

#111 merged normally at **699fac3503decc05345ec992f09eeedea8080fce**, tree
**5781f285b6b0121c88fb209f430c0545d2b5df9a**. Its tree equals reviewed head
bed3daf. #104's six bounded criteria closed using independent exact-source
evidence at 0c79846; those receipts do not qualify new UI or artwork.

Cloud startup failed with “environment configuration was canceled” and an actual
shell probe returned no usable execution environment. GitHub reads/writes work.
Remote branch **work/aurora-native-panel** preserves the existing offline
checkout and any local edits. No tool/network/package/auth presets are changed.
New build/typecheck/Node/browser/export/decode/render checks remain **UNRUN**.
A runtime reconnect is needed before executing pinned tools; no missing command
completion, screenshot, font check or passing receipt is invented.

## Selected artwork facts

[selection.json](../.identity/candidates/concepts/selection.json) selects
01 / aurora: open orbital ring with upper-right gap, flowing S-shaped ribbon,
aqua/cyan-to-violet finish, controlled glow/depth and near-black field. Retain
the original files and concept records:

| Reference | Retained PNG SHA256 |
| --- | --- |
| Selected comparison, top-left 01 | `4e2076ce7ba139a97d1ecf3b730de6db0cb15d9452cfcefbd8885b2af7b9c801` |
| Original orbital board | `5301893b21e08872262cced4e6415e117ddf20900e0ee64e816f912b298c8a5e` |
| Original gradient icon | `4c59ae9c7716c3889bd837071b55cef0e8641419405ded250f8d73620eab5f49` |

These are recorded reference hashes, not freshly executed decode/rehash evidence.
Production artwork/export files have not been generated by this checkpoint.
The existing mint outputs and old source-bound evidence stay historical.
The identity README now reflects intended slug **deckystream** and unresolved
destination ownership without changing stable brand or installed IDs.

Remaining #80 implementation uses separately authored, traceable selected source
geometry; it cannot claim automatic or identical raster-to-vector conversion.
Produce gradient/light/dark/transparent/small-size PNGs, wordmark, banner,
repository/docs projections, actual-size/focused sheets and offline gallery.
Reuse the pinned exporter/font path from
[the toolchain lock](../.identity/toolchain.lock.json): Inkscape1.4 and DejaVu Sans
hash `57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e`.
Record actual tool/source/output hashes and update consumer evidence only after
execution. No new Identity repository change or tooling/rights approval is made.

## Inspected native UI gaps and bounded repair scope

Source inspection at the merged base identifies these existing gaps:

| File | Demonstrated gap | Required behavior |
| --- | --- | --- |
| `steamdeck/decky/src/index.tsx` | Dependency setup and full configuration precede stream controls | Configured/streaming view prioritizes observed state and explicit Start/Stop; setup remains prominent when needed |
| `Configuration.tsx` | Saved destination/connection always expanded; direct provider-guide navigation | Explicit editing/progressive disclosure, stable focus, cleared private drafts/late clipboard protection, guarded secret-free link feedback |
| `Advanced.tsx` | Clip array starts empty; collapsed health feedback hidden | Distinct loading/confirmed-empty/populated/error/retry states; recovery failure visible even with details closed |
| Optional Desktop Setup entry | Existing optional callback has no supplied launcher | Discoverable Desktop Mode instructions for the existing authenticated loopback setup; no new LAN service or mandatory companion |

These are source-confirmed presentation gaps, not measurements on a Steam Deck.
Retain the existing robust observed-state polling, unknown/busy gates, action
serialization/deduplication, explicit Start, capture privacy and mic intent.
Decorative aurora color cannot become an observed stream-status cue.
No unverified game-only selection silently falls back to desktop capture.

## Verification to execute

1. Resume the existing checkout, inspect local changes/branch, fetch the remote
   checkpoint and reconcile without overwriting local edits. Use supported pinned
   tools; keep all required tests and presets.
2. Run meaningful focused model/frontend/typecheck/build checks and actual
   packaged browser fixtures at the new committed source. Exercise configured
   400x800 primary controls before setup, polling focus, private draft disposal,
   collapsed failures, delayed clips, retry/refresh and guarded guide navigation.
   Adapt fixtures that formerly assumed an always-open editor.
3. Decode and hash retained art, generate/repeat selected exports with pinned
   tools/font, check manifest/drift/dimensions, ordinary PNG downloads and
   offline gallery. Inspect real16/24/32/64 sizes and dark/focused states.
4. Integrate selected local assets and lowercase display styling while preserving
   compatibility IDs. Run affected frontend/package/site checks after changes.
5. Finish source-changing repairs, then #85's exact-source complete available
   matrix and owner-machine packet. Full ACT, hosted and target limitations must
   remain separate. Run the owner-machine checks and resolve reported problems.
6. Execute #86's actual Steam Deck/loader/OBS/provider/controller/headset tests,
   then approved migration/new-install retest under #87/#88.

All 230 original criteria/dependencies remain intact. Priority does not add hard
dependencies. Proposed ADRs remain proposed; creator/rights/licensing, publisher,
ownership and adoption facts are not invented. No OAuth implementation, release,
deployment, migration, Store submission, other-repository change or paid resource.
