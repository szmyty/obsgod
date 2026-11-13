# Completion review and remaining owner checklist

Status: **prepared for review; final source qualification is pending**. This
campaign implements feasible local work across the plugin backlog. It does not
publish a release, deploy a site, move a repository, spend money or declare
actual Steam Deck/CI/adoption acceptance.

The live inventory contained **36 open issues: 35 implementation/carryover
issues and separate research #51**. The [criterion ledger](evidence/completion-criteria.json)
preserves **230 original acceptance/quality requirements**, original issue/body
digests, scope/gate prose, explicit dependencies, implementation references,
historical assessments and a concrete remaining action per criterion. Historical
passing receipts qualify only their recorded source. Its empty current-receipt
registry deliberately awaits final source/artifact/command/platform evidence.

The owner's current direction is to review/merge prepared changes, then reuse
[#46](https://github.com/szmyty/obsgod/issues/46) as the one consolidated
implementation checklist and retain
[#51](https://github.com/szmyty/obsgod/issues/51) as separate research. This
document performs no closure. After those checkpoints, superseded tickets must
link the intact ledger; administrative closure must not imply their unrun
criteria passed. Priority adds no hard dependency, and original dependencies
remain recorded verbatim.

## What can be reviewed now

- Canonical [architecture](../ARCHITECTURE.md), [vocabulary](../ONTOLOGY.md),
  [decisions](../DECISIONS.md) and [agent guidance](../AGENTS.md) explain the
  actual runtimes, safety rules and responsibility boundaries.
- Existing managed streaming, state/notifications, installation/update/removal,
  provider presets, profiles, idle media, local recording/replay and health
  remain the starting source. This push adds API/creator, microphone/mixer/UI,
  branding preparation and release/CI hardening; each needs fresh evidence at
  the final integrated source.
- The API facade and creator adapter are local candidates. Legacy commands
  retain a compatibility path. Creator connects to existing OBS; it does not
  create the originally requested separate StreamGod repository or establish
  an actual one-command managed Steam Deck journey.
- The [Identity brand review](branding-review.md),
  [migration review](migration-review.md) and
  [site preview](branding-site-preview.md) make the remaining identity choices
  concrete. Draft source/assets are not approved creative work; the requested
  `decky-stream` identity is not an executed repository/plugin/data migration.
- [Local CI](local-ci.md) and [release engineering](release-engineering.md)
  provide retained commands and artifact audits. An `act` run is local evidence;
  it cannot substitute for a required successful hosted job.

## Smallest owner-dependent steps

- **Review the pending PR stack.** Root's final continuity/PR list supplies exact
  bases and merge order. Review current source, checks and open gates before
  merging; then approve the administrative consolidation if still desired.
- **Choose identity and companion disposition.** Confirm final organization/
  canonical repository or explicitly retain the current namespace. Review the
  Decky Stream name/mark, draft creative brief/SVG/rights facts, contact/domain
  and publisher. For #13, choose an approved separate companion destination,
  explicitly amend the original separate-repository scope, or keep it pending.
  Preparation does not create or transfer another repository.
- **Resolve required hosted CI access.** The existing GitHub account restriction
  has prevented hosted steps. The account owner must restore permitted Actions
  execution, then obtain fresh required CI and review results. No paid
  remediation is authorized or presumed.
- **Run the exact final candidate on the Steam Deck.** Record model, SteamOS
  channel/build, Steam/Decky/OBS Flatpak/bundled WebSocket/GStreamer versions.
  Execute the [device checklist](m3-device-acceptance.md), including the microphone
  cases below. Do not use an older preview's video success as newer audio proof.
- **Supply real provider/adoption proof.** A separate viewer verifies picture and
  audible system/microphone audio for each destination claimed supported. A new
  user's install → configure → audible local clip → viewer → update/recovery →
  uninstall journey provides adoption proof. Account readiness and any actual
  broadcast action remain under the responsible user's control.
- **Verify optional support facts.** Confirm control of the existing recipient
  links, contact wording and provider-approved link/payment path without agent
  spending. Crypto addresses can remain null/hidden; activation needs the owner's
  exact network/address facts. No contribution or payout readiness is invented.
- **Decide publication only with the final packet.** Root must first supply exact
  source/artifact revisions, hashes, qualified results, limitations, destination
  and responsible publisher. Release publication, site deployment, transfers,
  other-repository submissions and spending remain precise separate actions.

## Microphone and hardware review

Steam Deck has built-in microphones. On LCD hardware, plugging into the 3.5 mm
jack can make the built-in microphone unavailable; software must report actual
available sources rather than infer success from the model. Verify built-in,
headset/USB/Bluetooth choices actually present on the test device, then test:

- System audio and speech are separately audible in a saved clip and viewer.
  Selecting game-only video does not promise per-app audio isolation.
- Per-source mute/gain and selected device persist without altering system
  volume. Missing/changed devices are visible, and recovery preserves mute intent.
- Hold/release push-to-talk, panel close, lost focus, reconnect and lost renewal
  release safely. Actual controller controls must be demonstrated; a browser
  fixture is not proof of the physical controller path.
- Device changes, sleep/session changes and bounded retry escalation do not
  start a stopped stream, expose the desktop or falsely claim output stopped.

## Original issue-to-work map

Every row's exact original criteria and remaining actions are in the ledger
under that issue number (`AC`, startup/readiness `SR`, quality `QG`, or definition
of done `DD` identifiers). A source reference describes implementation, not a
criterion pass.

| Original issue | Prepared source/evidence boundary | Remaining acceptance |
| --- | --- | --- |
| [#7](https://github.com/szmyty/obsgod/issues/7) | Canonical root docs and focused decision records | Final component/link review; README/roadmap integration |
| [#8](https://github.com/szmyty/obsgod/issues/8) | Managed runtime and Roadmap 1 packet | Final child/device/viewer/CI/review evidence |
| [#9](https://github.com/szmyty/obsgod/issues/9) | Public facade, API CLI and automation | Final contract tests; legacy commands still use compatibility service |
| [#10](https://github.com/szmyty/obsgod/issues/10) | Flatpak isolation/readiness/diagnosis | Actual installed launch, measured budgets, graphical/session/audio/capture matrix |
| [#11](https://github.com/szmyty/obsgod/issues/11) | Configuration, profiles, help/completions and JSON | Final integration/new-user/contract checks |
| [#12](https://github.com/szmyty/obsgod/issues/12) | CI/security/build/audit/release operations | Fresh full matrix, required hosted CI/reviews and stable-v1 audit |
| [#13](https://github.com/szmyty/obsgod/issues/13) | In-repo creator consumer over public API | Dedicated-project decision, managed launch scope and actual Deck journey |
| [#14](https://github.com/szmyty/obsgod/issues/14) | Provider/creator/local-content boundaries | Actual provider validation, multistream strategy/follow-up disposition |
| [#16](https://github.com/szmyty/obsgod/issues/16) | Historical provenance/PR/archive records | Exact current stack/artifacts/device provenance and owner review |
| [#17](https://github.com/szmyty/obsgod/issues/17) | State reducer, automatic snapshots and filtered console | Real OBS plus actual Decky/QAM/reconnect lifecycle |
| [#18](https://github.com/szmyty/obsgod/issues/18) | State-driven controls, cancel and safe cleanup | Actual repeated-action/notification/failure/cancel acceptance |
| [#19](https://github.com/szmyty/obsgod/issues/19) | Unified Decky installer/dependency/repair flow | Actual active-Steam install failure regression and preservation matrix |
| [#20](https://github.com/szmyty/obsgod/issues/20) | Bundled updater/checker and strict trust | Actual safe apply, interruption, rollback and final app/plugin verification |
| [#21](https://github.com/szmyty/obsgod/issues/21) | Independent game/control/capture facts | Actual no-game/screen/game launch/exit frames and honest blockers |
| [#22](https://github.com/szmyty/obsgod/issues/22) | Final-candidate/device procedures | Fresh all-criterion matrix, installed Deck/viewer evidence and review |
| [#23](https://github.com/szmyty/obsgod/issues/23) | M2 source and owner packet | Identity/migration, target/CI/review, optional support and publication decisions |
| [#24](https://github.com/szmyty/obsgod/issues/24) | Local hashed idle image/video and transitions | Owner rights/creative approval and actual Deck transition/audio tests |
| [#25](https://github.com/szmyty/obsgod/issues/25) | Private connection/password test/rotate/recover | Actual safe idle rotation/mismatch recovery and final redaction |
| [#35](https://github.com/szmyty/obsgod/issues/35) | Working name and explicit compatibility inventory | Final organization/repository/name/owner facts |
| [#36](https://github.com/szmyty/obsgod/issues/36) | Migration/trust/alias/rollback review preparation | Approved identities and actual old→new/recovery/removal/redirect evidence |
| [#37](https://github.com/szmyty/obsgod/issues/37) | Historical truthful provenance/policy inventory | Fresh Store research moves to separate #51; no new research here |
| [#38](https://github.com/szmyty/obsgod/issues/38) | Manual Identity source and reproducible draft kit | Actual rights/creative approval, approved-source generation and target visual proof |
| [#39](https://github.com/szmyty/obsgod/issues/39) | Controller-facing setup/state/recovery/mixer UI | Real controller/new-user/offline/error/privacy acceptance |
| [#40](https://github.com/szmyty/obsgod/issues/40) | Kick/Twitch/YouTube/custom RTMP(S) configuration | Separate audible viewer proof for each supported claim |
| [#41](https://github.com/szmyty/obsgod/issues/41) | Safe preview/reset/uninstall/wipe | Actual old/new/partial/interruption/removal/reinstall preservation |
| [#42](https://github.com/szmyty/obsgod/issues/42) | Optional recipient buttons and hidden null wallets | Owner recipient/control/readiness verification; policy research stays #51 |
| [#43](https://github.com/szmyty/obsgod/issues/43) | Offline documentation/landing preview | Final creative/contact/domain/host review, clean preview and deployment proof |
| [#44](https://github.com/szmyty/obsgod/issues/44) | Release/security/support/audit operations | Actual supported Deck claim, final CI/reviews and publication packet |
| [#45](https://github.com/szmyty/obsgod/issues/45) | Direct-download/candidate/adoption preparation | Real new-user journey and owner launch; conditional Store work stays #51 |
| [#46](https://github.com/szmyty/obsgod/issues/46) | M3 parent proposed for final-boss reuse | Owner review/merges, intact consolidation, actual value/support observations |
| [#47](https://github.com/szmyty/obsgod/issues/47) | Versioned quality profiles/editor | Measured Deck presets, picture/audio/performance/controller evidence |
| [#48](https://github.com/szmyty/obsgod/issues/48) | Bounded recovery plus live mixer/microphone work | Actual routing/device/session/PTT/controller/performance cases |
| [#49](https://github.com/szmyty/obsgod/issues/49) | Recording/replay/storage/retention | Actual audible media, finalization, disk/recovery and controller shortcuts |
| [#50](https://github.com/szmyty/obsgod/issues/50) | Fresh bounded health and safe advice | Actual degraded hardware/network/load validation; no silent adaptive quality |
| [#61](https://github.com/szmyty/obsgod/issues/61) | Retained `act` setup/job inventory/fixes | Every job/matrix outcome plus second final-source run and sanitized receipts |

## Consolidation procedure after review and merges

1. Refresh live issues, PRs, default-branch revision/protections and release state.
   Attach exact final matrix/artifacts and limitations to the criterion ledger.
2. Rewrite #46 around the surviving owner/pair-work checklist and link this review
   plus every original criterion/dependency. Record the separate-project and
   conditional research dispositions explicitly.
3. Close transferred issues as superseded only after the agreed review/merge
   checkpoint. Use a note that says the criteria moved and unrun acceptance is
   pending; do not label hardware/CI/rights/adoption complete.
4. Keep #51 open as separate monetization and Decky Store research. This push
   does not perform that research or imply store eligibility/submission.
5. Query open issues again. The intended bookkeeping result is #46 and #51;
   any newly discovered issue or unmet transfer must remain visible.
