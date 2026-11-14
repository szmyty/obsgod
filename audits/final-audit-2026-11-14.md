# Proposed final audit and readiness roadmap

Audit baseline: **12ef52f9d22a7c1101f8743094325f66e3948270**,
`szmyty/obsgod`, 2026-11-14 UTC. Parent: [#84](https://github.com/szmyty/obsgod/issues/84).

**Current status: runtime stage #96–#100 is implemented through merged #106/#107,
with [exact-source qualification](../docs/runtime-correctness-checkpoint.md).
The open source stack was merged. Other stages remain proposed/separately scoped.** The original planning
checkpoint below is retained as history; see the
[runtime contract](../docs/runtime-correctness.md) for the implemented stage.

This pass inspected the repository and ran focused synthetic reproductions. It
changed planning documents and issues, not product code, UI or artwork. The owner
does not have the Steam Deck available; that does not block software preparation
after the sync. Physical tests remain unrun in #86.

The recommendation is to repair the observed runtime/lifecycle defects first,
then finish the existing aurora/UI/docs work, then freeze one exact-source test
candidate. The current architecture has usable boundaries; a framework rewrite
or component-library project would add scope without addressing these findings.

[Detailed machine-readable findings](../docs/evidence/final-audit-20261114.json)
include severity, evidence level, exact locations, triggers and acceptance.
[The evidence ZIP](../docs/evidence/final-audit-20261114.zip) retains six audit
reports, focused reproduction scripts/results and selected UI screenshots.
There are 26 observations across the reports, including overlaps, already-planned
work and optional improvements; this is not a claim of 26 independent bugs.

## Proposed execution sequence

Priority order is guidance, not a replacement for the original dependencies.
Independent work can proceed in parallel after approval of the plan.

| Stage | Issues | Concrete result |
| --- | --- | --- |
| Runtime, output and process correctness | [#96](https://github.com/szmyty/obsgod/issues/96), [#97](https://github.com/szmyty/obsgod/issues/97), [#98](https://github.com/szmyty/obsgod/issues/98), [#99](https://github.com/szmyty/obsgod/issues/99), [#100](https://github.com/szmyty/obsgod/issues/100) | Preserve live microphone policy, recheck capture ownership, validate recording state, discard unusable connections and cancel owned work within the loader deadline |
| Cleanup, update and recovery | [#101](https://github.com/szmyty/obsgod/issues/101), [#102](https://github.com/szmyty/obsgod/issues/102), existing [#82](https://github.com/szmyty/obsgod/issues/82) | Stable lock identity, protected paths, safe dependency preflight and truthful Decky versus retained Desktop update/recovery behavior |
| Async settings boundary | [#103](https://github.com/szmyty/obsgod/issues/103) | Coherent deadlines/pending outcomes and incomplete readback that fails closed |
| Branding and controller UI | Existing [#80](https://github.com/szmyty/obsgod/issues/80) / [#81](https://github.com/szmyty/obsgod/issues/81) | Selected lowercase aurora kit, primary controls first, progressive settings, visible loading/error/help states |
| Bounded refactors and current docs | Existing [#84](https://github.com/szmyty/obsgod/issues/84) | Small shared helpers tied to the defects; clear current installation/configuration/update/removal and historical download guidance |
| Build and final software qualification | [#104](https://github.com/szmyty/obsgod/issues/104), existing [#85](https://github.com/szmyty/obsgod/issues/85) | Maintained primary-build coverage, repeatable free local CI, final exact-source matrix, verified candidate/rollback and numbered owner test packet |
| Owner test and migration | [#86](https://github.com/szmyty/obsgod/issues/86) → [#87](https://github.com/szmyty/obsgod/issues/87), [#95](https://github.com/szmyty/obsgod/issues/95), [#88](https://github.com/szmyty/obsgod/issues/88) | Current-install Deck fix loop; approved exact migration; dependency graph/service verification; actual new-install retest and v1 approval packet |

## Findings requiring repair before the final test candidate

| Issue | Priority / evidence | Finding and bounded repair |
| --- | --- | --- |
| #96 | P1; protocol reproduction | `capture_video.go:104–120,223` uses the legacy microphone default for scene whitelisting after live mixer preferences enabled the microphone. The observer disables MicAudio in game and idle scenes while mixer intent remains enabled. Reuse effective microphone policy; preserve mute, gain and push-to-talk intent. |
| #97 | P2; protocol reproduction | `capture_watch_linux.go:67–103` observes managed ownership, waits for game discovery, then mutates without a fresh ownership/output check or shared control lease. A collection switch during discovery is followed by a scene mutation in the wrong collection. Recheck immediately before mutation, yield to explicit control and retain a bounded startup handshake. |
| #98 | P1; protocol reproduction | `pkg/automation/setup.go:105–109,219–259` accepts malformed successful recording observations through generated false defaults. A fixture stays recording while public StopRecording returns a supposedly finalized path. Use validated raw recording observations throughout runtime/preflight/finalization; unknown state cannot authorize or confirm output changes. |
| #99 | P2; protocol reproduction | `pkg/automation/client.go:157,248` and `pkg/api/v1/client.go:123` can retain a connection after an SDK response timeout. A late reply then corrupts correlation for a subsequent applied mutation. Classify interruption safely and close the owned connection before reuse; preserve numeric OBS rejection behavior. |
| #100 | P1; process reproduction | `steamdeck/decky/main.py:770–799` can await slow cleanup/mixer work before cancelling Start. The pinned loader terminates a backend after five seconds. A disposable Start child completes after the simulated backend kill; other tracked readers can also outlive unload. Latch cancellation and supervise owned work before slow cleanup, with truthful bounded results. |
| #101 | P2; filesystem reproduction / confirmed validation gap | `uninstall.py:135,231,244–256` deletes held lock paths during wipe, permitting another lock inode. Retained path validators also accept writable nonsticky ancestry that native storage rejects. Keep coordination identity stable and apply the existing protection policy without broad path rewrites. |
| #102 | P2; composition/version reproduction | `install.py:350–362` can mutate dependencies before idle/shared-lease checks. `decky/main.py:748–753` prefers an older Desktop version when checking updates: Desktop 4 + plugin 9 + candidate 5 recommends the older candidate and an updater absent from the standard ZIP. Align recovery preflight, trust and actual distribution channel; make any deliberate downgrade explicit. |
| #103 | P2; source-proven timing path and projection reproduction | Capture-mode UI gives up after 15s while Go/Python permit 75/85s, so a queued mutation can finish after its UI timeout. Incomplete successful configuration readback can also synthesize writable defaults. Current Go does not emit that malformed view. Bound quick operations or retain authoritative pending identity; require complete validated readback. |
| #104 | P2; CI source gap / observed resource limitation | Candidate CI builds only through `package-deck.py`, while `package-decky.py` is the primary entry. The latter passed manual verification but is not executed end-to-end by a maintained workflow. Final local CI also needed a manual compiler-cache cleanup at native startup. Cover the primary path and support a bounded resource preflight/cache policy. |

These are proposed repairs, not completed fixes. Reproduction fixtures deliberately
demonstrate current defects; a fixture successfully reproducing a bug is not a
passing product acceptance case. Protocol/process fixtures did not start real OBS,
Flatpak installations or provider broadcasts.

## UI and branding work already in the roadmap

Keep #80/#81 as the implementation home; their existing outcomes do not need
duplicate umbrella issues. The audit adds concrete cases:

- Put observed status and Start/Stop before saved setup forms. In the 400×800
  simulated Decky host using HTML component stubs, Stop is around 1839px down while streaming. This is
  fixture geometry, not a physical Deck measurement.
- Show recovery failures even when health details are collapsed. Distinguish
  clip loading, confirmed empty, populated, failed and refreshing states.
- Guard failed provider-guide navigation with accessible feedback. Provide
  discoverable instructions for the existing optional protected Desktop Setup.
- Align update text with the installed channel; do not advertise a bundled
  updater missing from the standard plugin package.
- Produce the selected **01 / aurora** masters/exports, lowercase wordmark,
  small-size treatments, ordinary PNGs and offline gallery. Keep older concepts.
  Integrate local decorative branding separately from observed status.
- Generate fresh selected-source manifests and size/contrast evidence. All 31 old
  output hashes match; the older source records omit seven later concept files
  and hash the earlier brief. Historical evidence is intact and remains historical.

## Useful bounded refactors and documentation

Tie extractions to the demonstrated repairs: one effective microphone policy,
validated recording observation, owned-action teardown/deadline policy and neutral
packaging helpers. Preserve independent public/legacy types and layered Go/Python
path validation where they defend different trust boundaries.

`Status` performs a repeated runtime observation: source counting found five
redundant OBS requests inside its two-second budget. Independent dependency polls
can launch up to 72 Flatpak queries/minute. Remove proven duplicate observations
and measure before adding another polling/cache layer. No target CPU, battery or
latency improvement has been measured; new caching cannot authorize actions from
stale readiness. This is a proposed optimization under #84, not a new framework.

README/user/support/site source still leads through older Desktop installers and
setup. Reconcile current normal Decky install → consented dependency setup →
native key form, while preserving historical review downloads and hashes. Keep
future `deckystream`, unresolved repository owner, stable brand ID and current
`obsgod`/`OBSGod` installed identities distinct. Align changelog/version/release
preparation without adding automatic publication.

A maintained publication-safe evidence exporter is optional after the required
repairs. Current raw maintainer logs are documented private; previous public
export required deliberate Actions-mask-value redaction with separate raw/public
hashes. No current product credential disclosure was found by this audit.

## Migration reminder and facts

[#95](https://github.com/szmyty/obsgod/issues/95) is created and linked from #87:
after the approved actual new public repository exists, verify/enable dependency
graph, manifest ingestion and dependency review using a real PR's exact base/head.
Record permissions, fork status and billing separately. An enabled setting or
repository move is not service acceptance; a current 403 does not prove what will
be configured at an unselected future destination.

Live baseline: current repository is public, a fork, default `master` at
`da89b9dba6e9fa15774136a706cdaea469dada0b`; branch API reports protected=false.
The exact destination owner is unresolved. Latest published artifact remains
prerelease `v0.1.0-deck.4-updater.1`; no stable release was found. Draft source
stack is #73 → #74 → #75 → #90 → #92. This audit's docs-only checkpoint follows
#92. No merge, retirement, transfer or release occurred.

## Verification and limits

Reviewed: Go runtime/API, Python adapter/install/update/removal/jobs/storage,
native/browser UI, packaging/workflows/release trust, README/site/docs, Identity
consumer assets/provenance, funding and live GitHub state.

- Four runtime findings have focused loopback/Go overlay reproductions.
- Lifecycle findings use disposable fake child processes, filesystem fixtures
  and side-effect-free installer/version composition. Dependency job tests:
  18 passed, one skipped.
- UI browser probes use the actual source 378b46c ZIP with unchanged frontend bytes
  relative to audit baseline 12ef52f; 22 focused state tests passed. No actual
  controller/Steam keyboard/rendering acceptance was claimed.
- Funding/product drift checks passed; retained asset hashes/decode, offline
  gallery/preview and local documentation targets were inspected. Original
  attribution/notices/preferred dependency source remain present.
- Six source workflows retain read-only permissions and snapshot publication
  disabled; no automatic release/site deployment was found. The prior complete
  local matrix passed at 378b46c for its recorded cases, with its documented cache
  maintenance. This audit did not repeat that matrix or qualify a new candidate.
- All 230 original criteria and their dependency statements remain byte-identical.
  No issue was closed or acceptance gate passed by planning.

Implementation waits for the owner's next sync. After approved repairs, #85
must qualify the final exact source and supply the short Deck checklist. Actual
SteamOS/Decky/Flatpak/OBS 33/Gamescope/AMD/controller/headset/Kick viewer, native
other-platform runtime, required hosted CI/reviews, rights and publication gates
remain explicit. Provider OAuth/phone login stays deferred in #89; monetization
and Store work are not activated. No paid service or other repository change is
part of this roadmap.
