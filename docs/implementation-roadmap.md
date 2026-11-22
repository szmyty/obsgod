# Current sequence amendment
The owner moved testing after migration on 2026-11-22. Follow the active
[roadmap](../ROADMAP.md#active-journey-polish-prepare-migrate-then-test) and
[recorded decision](../DECISIONS.md#owner-sequence-update-2026-11-22).
The original implementation/dependency record below remains historical evidence;
the amendment does not mark its unfinished acceptance criteria passed.

---

# deckystream implementation and migration roadmap

## Current merged implementation and remaining sequence

#113 and #114 are merged in order; implementation merge `a315224` has the same
tree as reviewed head `68f7a288`. The existing test candidate remains exact source
`772230a`, not the merge revision. Its
[checkpoint](pre-migration-qualified-checkpoint.md) links the immutable
[owner packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md),
standard ZIP, checksums, rollback and numbered tests. Available qualification
recorded 70 passed command checks and two unavailable; actual manual cases,
supported ACT capacity, hosted/services, rights/review and adoption remain open.

Follow the [ordered pre-test work](../ROADMAP.md#before-manual-testing): current
#84 handoff cleanup, literal source-acceptance bookkeeping, #85 candidate/matrix
evidence and parallel #87/#88 owner facts. Then use the paired #86 test/fix loop
before the approved #87 migration, actual #95 service verification and #88 clean
installation/v1 packet. #46 closes last. #89 stays research-only until owner
design discussion; manual-key testing does not depend on it. This sequence
preserves the original dependencies and all 230 criteria rather than creating
new prerequisites or publication authority.

## Earlier selected aurora review candidate

#112 merged normally at **069db4a**. Draft [#113](https://github.com/szmyty/obsgod/pull/113)
implements selected 01 / aurora assets, lowercase presentation, local native
branding with separate observed state, README/site integration and bounded setup
documentation repairs. Clean source **af7a20f** has67 passed command predicates;
the fullACT matrix remains unavailable and all6 jobs unrun. Hosted af7 jobs
executed0steps due15 billing refusals/1expected skip. No current-source platform,
provider, rights, review or adoption gate is waived.

Read the [qualified source, results and limitations](aurora-integration-checkpoint.md) and
[immutable review download/owner packet](aurora-owner-packet.md). All18 published review files
were downloaded and hash-verified; no release/deployment/migration occurred.
Next: review #113, complete #85 on a capable free machine, run #86 actual Deck
cases/fix loop, then approved #87 migration and #88 new-install/v1 packet with
#95 dependency graph/real PR comparison. #89 authentication stays research-only.
All230 original criteria/dependencies and104 bounded current criteria remain.
Later notes/evidence commits are not the qualified af7 package revision.

## Earlier checkpoints

#111 merged into actual `master` at **699fac3**, and #104 closed after six
bounded criterion mappings; source qualification remains exact 0c79846. The owner
now authorizes selected aurora artwork and native UI #80/#81. Follow the
[batch checkpoint](aurora-ui-checkpoint.md): draft #112 contains functional UI
source **3943f3c**, independently inspected but not build/browser qualified;
selected artwork/logo/lowercase exports remain pending. Preserve all 230 original criteria/
dependencies and keep final machine testing then actual Steam Deck validation
as explicit, unrun acceptance. Current Cloud startup failed; new draft changes
are not qualified by earlier receipts. No release/deployment/migration occurred.

## Earlier implementation checkpoints

Owner-authorized **#109/#110** source is merged into `master` at **cdcc668**.
Independent bounded acceptance reconciliation closed #101(7), #102(8), #103(6).
**#104** is implemented in draft [#111](https://github.com/szmyty/obsgod/pull/111),
with six locally supported criteria at exact clean **0c79846**. See the
[primary/resource checkpoint](primary-ci-checkpoint.md). Two complete primary
builds and standalone package/native/browser/snapshot checks pass. The supported
ACT matrix correctly refuses insufficient root capacity; all six workflows stay
unrun, with a latest measured need for at least4.6GiB more root/Docker space.
Next source work is selected #80/#81 artwork/controller UI, then final #85 and
actual #86 owner testing. Hosted/target acceptance remains separate. All230
original criteria/dependencies remain intact. Draft-state notes below preserve
their historical checkpoints and do not describe current issue/PR state.

Settings boundary **#103** is implemented in draft **#110**, stacked on unmerged
#109. Exact source **4eac7a4** passed six local ACT jobs, six actual packaged
settings scenarios and all six bounded criteria. Read the
[reviewed checkpoint](settings-boundary-checkpoint.md) for source/artifacts,
completed-run selection, preserved failures/interruption and external gates.
This is a review checkpoint; neither issue closure nor final #85/#86 acceptance
is implied. All230 original criteria/dependencies remain intact.

Cleanup/recovery **#101/#102** is implemented in draft **#109**, with all six
local ACT jobs and bounded criterion evidence at exact clean **aa323f0**. Read
the [review checkpoint](cleanup-recovery-checkpoint.md). Issues remain open for
review; actual supported-loader/device/provider and hosted gates remain separate.

Current runtime checkpoint: **#96–#100** are implemented through merged
#106/#107 and qualified at exact source **9038e23**. See the
[20-criterion evidence and full local matrix](runtime-correctness-checkpoint.md).
Remaining audit stage #104, selected artwork/UI and final owner test/migration
remain separate; this checkpoint does not replace their acceptance or the
original 230 criteria/dependencies.

Owner-directed plan, recorded 2026-11-14. Parent:
[#46](https://github.com/szmyty/obsgod/issues/46). The owner selected
**01 / aurora**, retained older artwork as concepts, and chose **deckystream**
as the future repository name. The exact destination owner is still unresolved.

Build a working standard Decky plugin under **szmyty/obsgod** first, using the
owner's existing compatible OBSGod installation. Deliver a verified candidate
and short manual test cases. Fix the reported problems before migrating; then
repeat the actual new download and clean installation. Planning issues are not
implementation, qualification or permission to publish a product release.

## Implementation: ready for the owner's Deck tests

[Milestone 4](https://github.com/szmyty/obsgod/milestone/4) contains ten bounded
tasks. Each issue includes acceptance criteria, verification and original-scope
links. These tasks reuse the existing core, capture, audio, microphone, media,
state/diagnostic and recovery implementation.

| Issue | Result | Implementation inputs |
| --- | --- | --- |
| [#76](https://github.com/szmyty/obsgod/issues/76) | One standard Decky package/build with bundled runtime and complete plugin setup payload | Can start independently |
| [#77](https://github.com/szmyty/obsgod/issues/77) | Decky-provided state paths with a safe legacy-data compatibility transition | Can start independently |
| [#78](https://github.com/szmyty/obsgod/issues/78) | Consented OBS/GStreamer setup, background progress, cancel and retry | #76, #77 |
| [#79](https://github.com/szmyty/obsgod/issues/79) | Private manual-key/provider configuration inside the panel | #77, #78 |
| [#80](https://github.com/szmyty/obsgod/issues/80) | Selected aurora source/exports and lowercase deckystream branding | Can start independently |
| [#81](https://github.com/szmyty/obsgod/issues/81) | Native, controller-friendly setup/controls with a subtle gradient logo | #79, #80 |
| [#82](https://github.com/szmyty/obsgod/issues/82) | Safe Decky replacement/removal, bounded legacy recovery and cleanup | #76, #77, #78; independent of artwork |
| [#83](https://github.com/szmyty/obsgod/issues/83) | Demonstrated integration repairs and meaningful edge-case regressions | Integrated #76–#79, #81, #82 |
| [#84](https://github.com/szmyty/obsgod/issues/84) | Repository audit, useful bounded refactors and current docs/release preparation | Integrated implementation and artwork |
| [#85](https://github.com/szmyty/obsgod/issues/85) | Final exact-source local qualification, current-identity build and manual test packet | #84 and all source-changing repairs |

Package, storage and brand work can proceed in parallel. The table identifies
integration inputs, not new dependencies on the original issues. The old
dependency statements remain intact under #46. Review existing draft work in
order **#73 → #74 → #75**; these planning changes do not merge those PRs.

### Required behavior

- Decky installs the plugin normally. First-run setup is separate: no dependency
  downloads in `_main`/`_migration`, explicit Install/Later, an installed but
  setup-required state after decline, and safe background cancellation/retry.
- Observe actual user/session context, Flatpak scope and compatible refs. Keep
  shared OBS/GStreamer, ordinary OBS and unrelated plugins intact; no SteamOS
  unlock or extra WebSocket plugin.
- Reuse backend configuration, key binding and private managed OBS credentials.
  Save, readiness checks, local clips, reconnect and recovery cannot broadcast.
  The current manual-key path is sufficient for the implementation milestone.
- Keep observed stream status independent of the decorative logo. Preserve
  automatic status, diagnostics/copy, explicit screen/game-only selection,
  intentional idle, system/mic controls, local media and unknown-state safety.
- Prefer normal Decky replacement/removal. Check its actual hook/process
  behavior rather than assuming an unload hook always runs or can veto updates.
  Inventory/preview any later legacy wipe and preserve data by default.
- Keep original concept PNGs/prompts/hashes. Direction selection does not invent
  final vectors, rights/licensing, target visual proof or publication authority.

### Test-ready completion

The autonomous implementation milestone delivers reviewable source, appropriate
focused checks and the complete required available final matrix, a checksum-bound
current-identity installable package, rollback, numbered owner test cases and a
secret-free failure report template. Record precise source/artifact revisions,
commands, tool/platform versions and passed/failed/skipped/unavailable/unrun
outcomes. Old receipts do not qualify the new package or UI.

Use available free local/ACT execution. The known hosted billing lock and fork
dependency-comparison limitation remain unavailable evidence; do not spend or
repeatedly trigger known zero-step refusals. Required device/review/rights/CI
criteria cannot be marked passed by local mocks, source merges or scope wording.

## Owner validation and migration

[Milestone 5](https://github.com/szmyty/obsgod/milestone/5) keeps these three
stages visible rather than blocking independent implementation on hardware.

| Issue | Result | Gate |
| --- | --- | --- |
| [#86](https://github.com/szmyty/obsgod/issues/86) | Step-by-step current-install Deck test and agent bug-fix/retest loop | Exact #85 candidate; owner Deck/account/viewer evidence |
| [#87](https://github.com/szmyty/obsgod/issues/87) | Prepared owner packet, then the approved fresh deckystream migration and scoped old-install cleanup | Preparation can run in parallel; actual move follows #86 and exact destination authority |
| [#88](https://github.com/szmyty/obsgod/issues/88) | Actual new download/official-install retest and concrete v1 decision packet | Actual #87 destination and affected requalification |

The first manual pass covers setup decline/cancel/retry, private Kick settings,
an audible moving local clip, explicit streaming with a separate viewer, mic and
headset changes/mute, game-only/menu privacy, idle/game switching, local media,
recovery and install/update/removal preservation. A reported failure gets an
exact replacement candidate and affected regression steps. Record actual Deck,
SteamOS/Steam/Decky/OBS/Flatpak and available device versions.

Before the external move, prepare source/attribution/rights, retained public
downloads/rollback, current MEMORIAL and tracker export, all original criteria,
actual destination issues, default `main`, exact trust/ID/path map and a reviewed
old-install cleanup plan. The owner has not selected the final repository owner.
The old `egohygiene/decky-stream` fixture does not qualify an eventual
`OWNER/deckystream`; repeat destination-dependent checks at the actual identity.

The final post-move pass uses the actual new package/install path. Prepare
semantic versioning, changelog and release automation during implementation,
then present the exact v1 artifacts/evidence/owners and any remaining approval
actions. No release, site deployment, paid service or Store submission happens
automatically because the roadmap or migration exists.

## Independent authentication research

[#89](https://github.com/szmyty/obsgod/issues/89) is a separate mini-roadmap,
carrying forward the login intent from original #14/#40. See
[provider authentication options](authentication-options.md) for dated official
sources and unrun account/device checks.

1. Verify Twitch/Kick public-client support, account/app ownership, scopes and
   stream-key access. OBS still needs ingest credentials internally.
2. Choose the phone journey: Twitch documents a public-client device flow;
   Kick's documented PKCE exchange/refresh still requires a confidential secret.
   Resolve Kick's constraints rather than shipping an embedded shared secret.
3. Specify private state, refresh/revocation, account switching, recovery and
   manual/offline fallback. A QR to a local setup page is not provider login.
4. Prepare real phone/Deck/account and negative-case test steps with precise
   owner actions; no account or successful provider authorization is invented.
5. Discuss the decision packet with the owner before authentication coding.

This research has no blocking dependency on the manual-key implementation. It
does not authorize app registration, hosting/brokers, paid services or live
ingest, and does not reopen the broader deferred companion/content ecosystem.

## Original acceptance and existing evidence

All **230 original criteria** and dependency statements remain under #46 and in
the unchanged [canonical ledger](evidence/completion-criteria.json). New child
issues cover bounded implementation/results, not replacement acceptance. Their
origin links are captured in [the machine-readable plan](evidence/implementation-roadmap.json).

- Existing shared API/39 legacy operations, Linux package audits and focused
  migration mechanisms in #75 are source to reuse, not broad new build tasks.
  The [4ac engineering evidence](pre-migration-completion.md) remains bound to
  its original source; #85 qualifies the resulting new integrated candidate.
- Original #13 companion remains deferred. #14's optional multistream/content
  ecosystem remains deferred; only the bounded login research moves into #89.
- Existing monetization/Store research #51 stays completed as research. It does
  not activate monetization, verify recipients, obtain Store admission or
  authorize submission. Optional support/wallet choices do not gate local use.
- Broader native-platform claims, hosted CI, independent review, rights,
  publisher, hosted sites and actual new-user adoption retain their evidence
  gates or explicit owner scope disposition. Steam Deck focus does not turn
  them into passes. Deployment and any Store pursuit remain separate actions.
- #46 closes only after its accepted scope has evidence or an explicit recorded
  disposition. Creating issues, merging code or migrating source cannot close
  it by themselves.

## Live planning baseline

Queried 2026-11-14: default `master` is
`da89b9dba6e9fa15774136a706cdaea469dada0b`; the planning branch began at
`8f4ed4710af2e91beba13c1111ca678eee152088`. Drafts #73/#74/#75 remain open.
The latest published artifact is still prerelease
`v0.1.0-deck.4-updater.1`; no new release was published. Master metadata reports
unprotected and repository rulesets are empty; detailed protection access is
403, not a claim of complete administration visibility. No settings changed.
