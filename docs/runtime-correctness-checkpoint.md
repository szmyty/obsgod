# Runtime correctness qualification

Qualified source: **9038e23e1a7bfe79c0a5731546f1d3e1a1a74e41**; tree **47366b98531c97778976fe354ccdf7aa53a9bac6**.

The source stack [#73](https://github.com/szmyty/obsgod/pull/73) → [#74](https://github.com/szmyty/obsgod/pull/74) → [#75](https://github.com/szmyty/obsgod/pull/75) → [#90](https://github.com/szmyty/obsgod/pull/90) → [#92](https://github.com/szmyty/obsgod/pull/92) → [#105](https://github.com/szmyty/obsgod/pull/105) → [#106](https://github.com/szmyty/obsgod/pull/106), then integration repair [#107](https://github.com/szmyty/obsgod/pull/107), was merged into actual default `master`, retargeting dependent PRs after their predecessors. The first merged source `4b3e0bf` failed the unchanged native local-clip fixture. Follow-up checkpoint `61bcd3d` and merged `9038e23` have identical Git trees. Later evidence-only commits do not change the qualified revision.

The owner authorized the bounded runtime stage #96–#100 and merges. The [contract](runtime-correctness.md) explains capture ownership, microphone intent, strict recording state, connection disposal and guarded four-second teardown. Other audit stages #101–#104, artwork/UI and actual owner testing remain separate.

## Criterion-level bounded repair evidence

All 20 original runtime acceptance bullets are retained in the [machine-readable evidence](evidence/runtime-correctness-9038e23.json) and indexed proof ZIP. Local evidence completes the bounded repair criteria; actual Deck/audible/controller/provider checks explicitly assigned to #86 remain unrun.

| Criterion | Local proof |
| --- | --- |
| 96.1: Run the actual observer path with legacy microphone=false plus mixer microphone_enabled=true; mic scene items remain connected in game and idle before/after transitions. | `TestCaptureWatchPreservesEffectiveMixerMicrophoneThroughGameAndIdle`, `TestCaptureWatchRefreshesMixerMicrophonePolicyForCachedGame` |
| 96.2: Check disabled, explicitly muted and push-to-talk preferences remain muted and never gain an implicit unmute. | `TestCaptureWatchPreservesEffectiveMixerMicrophoneThroughGameAndIdle` |
| 96.3: Verify game/idle transitions preserve gain, route, source mute and all independent output states; use protocol fixtures during repair and actual audible Deck clip/viewer evidence under #86. | `TestCaptureWatchPreservesEffectiveMixerMicrophoneThroughGameAndIdle` |
| 97.1: Switch collection/profile or stop output during a blocked discovery callback: no scene/input mutation follows the stale observation. | `TestCaptureWatchRechecksOwnershipOutputAndSettingsAfterBlockedDiscovery` |
| 97.2: Hold the shared control lease for an explicit stop/configuration: the watcher yields and later re-observes rather than acting on old state. | `TestCaptureWatchYieldsToSharedLeaseAndAttachesWithoutDeadlock`, `TestCaptureWatchObservesIdleWithoutTakingOutputControlOrMutating` |
| 97.3: Starting output plus attaching the watcher while the initiating command holds its lease remains bounded and does not deadlock. | `TestCaptureWatchYieldsToSharedLeaseAndAttachesWithoutDeadlock`, `TestCaptureWatchReadinessTimeoutIsBounded` |
| 97.4: Retain game-only privacy: no full-display fallback and no automatic output start/restart. | `TestGameVideoNeverFallsBackToDisplayAndExcludesUnknownSources`, `TestCaptureWatchTransitionsRerouteAudioWithoutStartingOrStoppingOutput` |
| 98.1: Table-test omitted, null and wrong-type outputActive at each recording lifecycle observation; unknown preflight dispatches no StartRecord or StopRecord. | `TestRecordingLifecycleRejectsUnknownActive`, `TestPublicRecordingLifecycleValidatesEveryObservation` |
| 98.2: Malformed finalization polls return an error and no finalized path even after StopRecord ACK; valid delayed shutdown still waits until explicitly inactive. | `TestRecordingLifecycleRejectsUnknownActive`, `TestPublicRecordingLifecycleValidatesEveryObservation` |
| 98.3: RuntimeStatus and managed configuration/capture preflights cannot convert unknown recording state into idle authorization. | `TestRecordingLifecycleRejectsUnknownActive`, `TestRecordingObservationsUseValidatedCanonicalFlags` |
| 98.4: If outputPaused is exposed as known, omitted/null/wrong-type paused flags remain unknown/error rather than false. | `TestRecordingStatusRequiresKnownPaused`, `TestRecordingObservationsUseValidatedCanonicalFlags` |
| 98.5: Retain existing stream/record/replay coexistence, partial-media preservation and legacy request-ACK contracts; focused Go protocol/race checks only during repair, final matrix remains #85. | `TestRecordingLifecyclePreservesDelayedShutdownAndIndependentOutputs`, `TestLegacyRecordingStillReturnsRequestAcknowledgement` |
| 99.1: A delayed-ACK fixture with shorter SDK response budget than public deadline returns a safe timeout/unavailable failure and marks the connection closed. | `TestSDKResponseInterruptionInvalidatesBeforeNextRequest` |
| 99.2: A subsequent operation on that client is rejected before any new request reaches the fixture; reconnect/observe remains caller-explicit. | `TestSDKResponseInterruptionInvalidatesBeforeNextRequest`, `TestWorkflowPreservesResponseFailureAtEverySanitizationBoundary` |
| 99.3: A valid numeric OBS rejection preserves obs_request plus its OBS code and need not poison the connection. | `TestNumericOBSRejectionKeepsLegacyConnectionHealthy`, `TestResponseFailureClassificationExcludesServerDetails` |
| 99.4: Keep caller-deadline cancellation ownership, waiting-cancellation independence, once-only physical close, and no raw endpoint/key/server-message exposure. | `TestCancellationClosesAcquiredConnection`, `TestWaitingCancellationDoesNotInterruptOwner` |
| 100.1: A faithful five-second loader stop fixture with slow microphone/dependency observations cannot permit a pending Start to mutate after backend death/reload acknowledgement | `test_official_five_second_stop_budget_cancels_start_before_slow_observations`, `test_final_stop_acquires_control_lease_after_stuck_start_is_killed` |
| 100.2: Late spawn ownership, active stream/record/replay, unknown output and abrupt parent death are tested separately; no forced kill of ordinary OBS or unrelated processes | `test_late_attachment_never_receives_exec_permission_after_unload_acknowledgement`, `test_abrupt_backend_death_kills_only_its_owned_command` |
| 100.3: All tracked RPC/read/update tasks have defined shutdown behavior and no child/lease is silently orphaned | `test_shutdown_drains_invalidated_readers_direct_rpcs_and_update_bookkeeping`, `test_closing_reads_and_mutations_cannot_spawn_or_query_dependencies` |
| 100.4: Document that hooks are best effort and cannot veto normal Decky replacement/removal; leave actual supported Decky/SteamOS execution unrun until owner test | `test_official_five_second_stop_budget_cancels_start_before_slow_observations` |

Follow-up #107 additionally proves parent-owned local clip capture under the shared lease, detached-observer yield, cancellation, timer and fresh-ownership cleanup. The unchanged native fixture now passes the original failed clip path and game/idle transitions; its assertions and readiness timeouts were retained.

## Matrix and artifacts

All six supported local ACT jobs passed at the exact clean merged source above: lint, build, race coverage, non-publishing snapshot, docs preview and Steam Deck candidate. Reporter integrity passes with zero open failure groups; overall qualification remains partial for external gates.

| Check | Result |
| --- | --- |
| Six ACT workflows | Passed 6/6; exact commands and raw receipt/log hashes in proof ZIP |
| Go race/vet/staticcheck/govulncheck | Passed; host race: 284 top-level tests/732 pass events, two explicit skips |
| Application Python | 197 passed / 1 explicit root-runner skip (198 total) |
| Tooling Python and Node | 85 and 43 passed; typecheck/build/audits passed |
| Reproducibility | Runtime/updater packages and unsigned artifact inventories repeated with matching checksums |
| Primary standard plugin |33 payload files match pinned official CLI 0.0.7/default builder assembly; workflow ZIP equals primary ZIP |
| Actual packed Python→Go |218 CPython / 240 simulated-frozen checks;22 real guarded calls each; no OBS launch/broadcast |
| Browser/native | All workflow browser cases; 18 filtered native OBS/audio/capture/game/idle proofs passed |
| Supplemental CLI/Decky/upgrade | Passed; pinned unmodified Decky 3.3.1 source, version 4 / dynamic 6 / current 9 and version 6 / current 9 fixture paths |
| Normal-user frontend after ACT | All 6 absent/reused-output checks passed; original output preserved |

Primary ZIP SHA256: **8833c0a11db6bbc06f75dad931e9810e3513d491e904450774cf3edced766d33**. It remains a local review build, with no product release publication. OfficialCLI assembly verifies prepared bytes; its raw ZIP timestamps are not claimed reproducible.

[Machine-readable qualification/20criteria](evidence/runtime-correctness-9038e23.json) and [indexed proof ZIP](evidence/runtime-correctness-9038e23.zip) retain the exact commands, tool/platform/container versions, original/public hashes, source inventory, reviews and limits. Proof ZIP: 214 members/SHA256 **fd07c055a61b2f1a788fedb5277f1b3c7413544bb66f77c61e1928548563af3d**. Actions mask values were redacted in 10 members; index hashes distinguish private originals and public bytes.

Native fixtures use Debian 13 / OBS 30.2.3 / Python 3.13.5 / PulseAudio 17 / FFmpeg 7.1.5 and synthetic PipeWire producers with software encoding. They do not test OBS 33 Flatpak or SteamOS. Host tools are Go 1.27.4, Python 3.12.14, Node 24.19.0 / npm 11.9.0, Docker 28.4.0, Playwright 1.62.0 and ACT 0.2.97; image IDs and pins are in evidence.

Both ACT attempts used recorded constrained-runner assistance: discard only the active candidate container's disposable Go compiler cache after builds/audits, before native tests. No workflow step/source/artifact/module/toolchain was dropped. Three inactive host caches were temporarily relocated, then restored with every regular-file/link hash matching. No package/network preset changed.

The failed original `4b3e0bf` matrix (5 passed / 1 failed), initial dirty Go fixture failures and old direct-argv integration harness failure remain explicit historical diagnostics, followed by actual fixes and new-source passes. Optional real-OBS read and host fish syntax execution are skipped/unavailable as recorded; generated completions are separate from execution. Earlier passing receipts are never relabeled.

## Evidence limits

[Independent evidence review](evidence/runtime-correctness-9038e23-review.json)
approved the exact proof ZIP with zero blockers. It verifies original/public log
bindings, all indexed member hashes, decoded privacy scans, criteria and external
limits. The review is separate from the ZIP to avoid a circular hash claim.

Hosted workflows are unavailable because the account billing lock prevented all recorded steps from executing; a skipped push dependency-review job is expected. Actual PR #107 dependency comparison returned 403 and remains unavailable. Detailed branch-protection access returned 403; branch metadata reported protected=false and active rulesets/branch rules were empty. No protection was changed or bypassed, and no GitHub review submissions were present. Independent source/evidence reviews are recorded separately.

Physical Steam Deck/SteamOS/Flatpak/OBS 33/Gamescope/AMD/controller/keyboard/headset/provider and native Windows/macOS/arm64 runtime acceptance remain unrun. Synthetic Linux, browser and frozen-loader fixtures cannot supply those facts. No consumer adoption, product release, deployment, migration, Store submission or spending occurred. The latest published preview remains unchanged.

All 230 original campaign criteria/dependencies remain intact. The remaining current backlog is #46, #76–#89, #95 and #101–#104; the later exact-identity candidate/owner test/migration gates remain open. This is an intermediate correctness checkpoint, not the final v1 release candidate.
