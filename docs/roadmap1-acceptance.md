# Roadmap 1 review packet

Implementation and available local qualification are prepared in stacked draft
PRs. **Roadmap 1 is not closed.** Actual Deck/Kick acceptance, functioning GitHub
CI and owner PR review remain gates. No merge, issue closure, release publication,
deployment, billing change or other-repository change was performed.

## Exact candidate and review order

- Candidate: `0.1.0-deck.5`, Linux x86_64.
- Qualified source: `2287ed4c2f3fcc9b8ec42bbd68ac531063b5d578`.
- Immutable review artifact commit: `1fbf92ff36eea77bee0f3da186e99d856c80774e`.
- Foundation: draft [#15](https://github.com/szmyty/obsgod/pull/15), unchanged at
  `0eb8324c2b1f23fea069570eded1cd0c75d99274`.
- Stacked review/merge order, after acceptance and owner review: [#26](https://github.com/szmyty/obsgod/pull/26)
  provenance → [#27](https://github.com/szmyty/obsgod/pull/27) runtime →
  [#28](https://github.com/szmyty/obsgod/pull/28) state →
  [#29](https://github.com/szmyty/obsgod/pull/29) installation →
  [#30](https://github.com/szmyty/obsgod/pull/30) updates →
  [#31](https://github.com/szmyty/obsgod/pull/31) integration/qualification.

Later evidence-only documentation commits do not relabel the candidate source.
Use its exact manifest and receipts; do not infer qualification for a rebuilt
package from another revision.

## Downloads and installation for review

[Complete candidate installer](https://raw.githubusercontent.com/szmyty/obsgod/1fbf92ff36eea77bee0f3da186e99d856c80774e/obsgod-deck_0.1.0-deck.5_linux_amd64.tar.gz)
· [Decky ZIP](https://raw.githubusercontent.com/szmyty/obsgod/1fbf92ff36eea77bee0f3da186e99d856c80774e/obsgod-decky.zip)
· [Standalone updater](https://raw.githubusercontent.com/szmyty/obsgod/1fbf92ff36eea77bee0f3da186e99d856c80774e/obsgod-one-click-update_0.1.0-deck.5_linux_amd64.zip)
· [Full checksums](https://raw.githubusercontent.com/szmyty/obsgod/1fbf92ff36eea77bee0f3da186e99d856c80774e/CANDIDATE-SHA256SUMS)
· [Exact qualification JSON](https://raw.githubusercontent.com/szmyty/obsgod/1fbf92ff36eea77bee0f3da186e99d856c80774e/roadmap1-qualification.json)
· [Command logs/media probes/CI annotations](https://github.com/szmyty/obsgod/tree/1fbf92ff36eea77bee0f3da186e99d856c80774e/evidence).

For the candidate device test, use the **complete installer**, extract the whole
archive in Desktop Mode, then open `Install OBSGod.desktop`. Keep normal Steam
running for Decky's existing frontend connection. Leave the existing OBSGod
installation in place. The default flow verifies/installs both app and plugin
and should retain settings/key/media and unrelated plugins. If Decky is missing,
use the official guided instructions and retry; OBSGod does not silently install
a privileged service. Inspect the final result and plugin version before testing.

The standalone updater follows published releases. It cannot install an
unpublished candidate from this review branch. The Check for updates button may
show published runtime 4 while candidate 5 is installed; it must not downgrade.
The full installation/use/recovery procedure is in [the guide](steam-deck.md).

| Artifact | SHA256 |
| --- | --- |
| Runtime archive | `bc22ebaab2fb4d5d443e7cd1594d4db02298cf72bad6172d6dba8f40d21d8faf` |
| Decky ZIP | `2bbae56db09722ffa5d956f2db37f0cd3bb7788c465cd9c8623217d8f196ad67` |
| Updater ZIP | `d2558d05502e748d130442c349d42682cc89aa62be69cbfa97facd762ecfa66f` |

All seven core public files, every internal runtime payload hash and the public
plugin version were downloaded and verified against the tested local files.
The candidate uses repository/tag/HTTPS/checksum verification, not code signing.

## Qualification at the exact candidate source

| Check | Outcome and limit |
| --- | --- |
| Go protocol/runtime/helper/CLI race tests | **Passed: 56**; one optional existing-OBS read-only test **skipped** because its opt-in address/password were unset. The separate native OBS integration did run. |
| Go vet and pinned govulncheck v1.9.0 | **Passed**; no diagnostics or vulnerability findings. |
| Python installer/setup/backend/release/updater cases | **Passed: 56**. |
| Node state/health cases; TypeScript/build | **Passed: 8**, typecheck and build passed. |
| npm audit | **Passed**, zero reported vulnerabilities. |
| Runtime and standalone updater packages | **Passed**, two clean builds produced identical checksums. |
| Actual archive Desktop/browser flow | **Passed**, fresh/repeat/old-preview upgrade/uninstall; private key/settings/media/OBS preservation. Explicit app-only mode isolates this browser path; full Decky installation is separately exercised below. |
| Actual Decky ZIP browser flow | **Passed**, automatic polls, stale/counter reset/disconnect handling, duplicate Start, idle Stop, Cancel, confirmed notifications, full console copy/history/fallback/redaction and read-only update UI. Steam UI/controller components are simulated. |
| Pinned Decky 3.3.1 frontend/backend/installer | **Passed**, old competing-socket failure reproduced; helper installs through the existing frontend. Actual default unified installer runs twice, preserves other plugins/order/prompts and app/key/media/history. CDP forwarding, installed-version lookup, ownership/service lifecycle and Flatpak availability/version are fixtures. |
| Actual extracted Desktop updater | **Passed**, official-shape network fixture, exact source/manifest/archive validation, upgrade/no-update/explicit repair/corrupted-download preservation, private backups/retry journal. No production URL override or product source edits. |
| Real native OBS | **Passed**, OBS 30.2.3 / WebSocket 5.5.2 / GStreamer 1.26.2 / PipeWire / PulseAudio / software H.264/AAC: moving 720p recording with audio, nonblank local RTMP, repeated lifecycle, failed-start cleanup/no late broadcast, recording stop and managed process shutdown. Native Flatpak invocation and Gamescope producer are substituted. |
| Linux ARM64 / Windows AMD64 / macOS ARM64 | **Passed compilation**, execution **unrun**. |
| Live public release discovery | **Passed**, correctly selects runtime 4/source `55c03dd…`, validates immutable metadata and ignores the newer updater-only release. Candidate 5 is unpublished. |
| GitHub Actions | **Unavailable execution**: current source jobs conclude failure/cancelled without running steps. GitHub annotation: “The job was not started because your account is locked due to a billing issue.” |
| Actual Steam Deck platform/performance and Kick viewer/adoption | **Unavailable/unrun**; no attached Deck or real key/channel test. |

Environment: Linux x86_64, Go 1.27.4, Node 24.19.0, npm 11.9.0, Python 3.12.14,
Playwright 1.62.0, Chromium 151.0.7922.173 and Docker 28.4.0. The exact native
image ID, source pins, commands and individual outcomes are in qualification JSON.

## Criterion-level issue reconciliation

| Issue / criterion group | Prepared evidence | Remaining acceptance |
| --- | --- | --- |
| #16 provenance and existing work | Exact master/preview/updater/source/artifact hashes, observed failures and scoped PR bases recorded; existing code repaired. | Actual installed device versions and owner PR review. |
| #10 compatible OBS/authenticated readiness | Built-in WebSocket/password config, bounded 20-second startup/one-second connect, stage errors, cancelled/silent auth socket cleanup, visible managed recovery and early-exit cases. Native authenticated OBS ran. | Actual installed Flatpak/WebSocket/plugin versions, Deck timing/dialog/display behavior. |
| #10 safe lifecycle/recovery | Known-PID shutdown through discovery loss, terminal processes, missing/unreadable live processes, unknown-output protection and recording confirmation tested; native restart passed. | Desktop/Gaming transitions, actual launch topology, reboot/service recovery. |
| #10 capture/audio/performance | Native moving 720p/software encode/game-audio surrogate, repeated output and failure checks. | Real game/microphone/VAAPI capture, continuity, controller/game FPS and presets. |
| #17 independent authoritative state | Process/connection/output/recording/pending operation/capture/frames/game-unknown facts; real current-program screenshots; unit/native/browser evidence. | Actual Steam/QAM lifecycle integration. |
| #17 live/manual refresh and stale recovery | Bounded shared polling, stale/backend/counter resets, manual resync, disconnect/reopen models and console persistence/copy tested. | Real Decky/Steam/controller behavior. |
| #18 state-aware controls | Confirmed-idle Stop suppression; pending Cancel; recovery Stop for unknown; backend coalescing/late-attach/unload cleanup tested. | Actual repeated controller operations and disconnect recovery. |
| #18 notifications and preservation | Confirmed transitions only; action errors separate; preexisting stream/recording retained on failed repeated Start; native repeated Start/Stop passed. | Owner device evidence and review. |
| #19 unified installer/dependencies | Default app+plugin transaction, real frontend protocol, version/capability detection, OBS 28+ check, missing-Decky guided stop, installed menu entries. | Actual privileged Decky service, Steam CDP path and user Flatpak installation. |
| #19 upgrades/recovery/preservation | Fresh/repeat/old-preview upgrade, failed activation, private recovery records, pending-mutation guard, settings/key/media/history/other plugins/order and safe path checks. | Device interruption/reinstall/recovery proof. |
| #20 checks/version/channel | Bottom read-only check, separate app/plugin/updater versions, stable/preview ordering, updater-only filtering, live official metadata verification, offline/error cases. | Actual panel behavior on Deck. |
| #20 safe verified application | Bundled maintained updater; exact trusted source/artifact validation; idle/output/operation guards; no downgrade; backups/no-update/repair/bad hash/interruption tests. | Actual Desktop update/rollback behavior; published-candidate update remains unrun because no release is authorized. |
| #21 no artificial game gate | OBS launch/control precedes capture checks; game presence stays unknown rather than inferred from a feed; missing/blank messages truthful; nonblank safety preserved. | **Usable real no-game Gaming Mode frames remain an explicit blocker**. A custom banner does not satisfy this criterion. |
| #21 launch/exit and output health | Capture/current-program/unknown observations, no implicit broadcast or fabricated fallback. | Real game launch/exit and Steam UI capture. |
| #22 final matrix and handoff | Exact candidate, commands, tools, statuses, package hashes, public downloads, local integration and instructions prepared. | Billing lock cleared, required CI executed successfully, device/Kick/adoption proof and owner review. |
| Parent #8 | Scope, dependencies, PR sequence and preserved original planning reconciled. | All child acceptance and required reviews before closing parent/milestone. |

No child is closed from code or package existence. Broad optional workflow/API/
CLI/stable-v1/StreamGod acceptance remains in #7/#9/#11/#12/#13/#14. Roadmap 2
#23/#24/#25 remains deferred: custom idle media/transitions and user-facing
password controls were not implemented. Generated authenticated connectivity is
already part of Roadmap 1.

## Failed runs and repairs

Earlier receipts are retained separately and do not qualify this candidate:
`e90a6a1` failed final native shutdown confirmation; `fe6bbd8` exposed a connection
timeout classification race and a failed synthetic feed with WirePlumber exiting
before PipeWire readiness. Repairs added terminal/known-PID handling, asynchronous
record-stop confirmation, monotonic timeout classification and ordered fixture
startup. The exact source of each historical producer link teardown remains
unproven. The GStreamer synthetic producer still has a documented teardown
limitation; this passing run does not establish real Gamescope stability.

An older browser waiter evaluated strings under the real CSP; it was changed to
a locator expectation. One exploratory updater fixture overlapped repeated
packaging and correctly rejected an inconsistent checksum. Final package checks
ran against frozen artifacts after the repeat-build comparison.

## Owner actions and publication path

1. Review the draft stack and this candidate. Clear GitHub's account billing
   lock, then rerun all required checks; no billing change or spending was attempted.
2. Install this exact candidate on the Deck. Record version/hash/device details,
   test the local clip, no-game/game launch/exit/QAM/recovery/update cases and
   performance. Copy the diagnostic console for any failure; never send a key.
3. When ready to broadcast, explicitly Start and confirm correct Kick picture
   and sound from a second device. That owner-device result is adoption proof;
   the prior preview installation is not candidate adoption.
4. After acceptance and review, merge in stack order and close only satisfied
   issues/milestone. A later exact source rebuild requires its own qualification.
5. Release publication remains a separate owner approval. Proposed destination
   is this repository's GitHub prerelease `v0.1.0-deck.5`, tagged at the exact
   candidate source with these exact artifacts/receipts. The repository owner
   controls publication; native asset-upload access was previously unavailable,
   so immutable same-repository links are the prepared alternative. No tag or
   release has been created. No deployment or plugin-store submission is planned.

Rights/licensing facts: the existing MIT LICENSE is preserved; dependency
notices and the replaceable Decky API LGPL source/license remain included. OBS,
obs-gstreamer and Decky Loader are installed separately; pinned GPL reference
sources are test inputs outside the product. No new creative assets or rights
decisions are introduced; those remain in deferred Roadmap 2.
