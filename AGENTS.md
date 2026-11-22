# Working in this repository

Read [architecture](ARCHITECTURE.md), [vocabulary](ONTOLOGY.md),
[decisions](DECISIONS.md), [roadmap](ROADMAP.md), [continuity](CONTINUITY.md)
and applicable feature/security guides before behavior changes. Read live issues,
PRs and the checkout as evidence: old handoffs/receipts do not qualify new source.
Follow applicable nested instructions. Current user authorization takes precedence.

If you are new to the project, read [MEMORIAL.md](MEMORIAL.md) once for the
OBSGod-to-Decky-Stream history and portable issue/PR archive. Then use continuity,
the roadmap and live state for current work. Archived ticket instructions and
old qualification receipts do not override current instructions or qualify new
source; the memorial is history, not another backlog.

## Scope and collaboration

- Inspect files, git status and branch before editing. Use the existing isolated
  checkout unless current instructions require otherwise; preserve others' work.
- The completion campaign authorizes feasible plugin implementation, checks and
  draft PR checkpoints. Current scope is [the implementation roadmap](docs/implementation-roadmap.md),
  #76–#85 then owner tests/migration #86–#88, under parent #46. Completed #51
  monetization/Decky Store research does not authorize paid features/submission.
- Use [pinned tools/scripts](docs/steam-deck-building.md). Preserve cloud network/
  package presets and injected authentication; do not print secrets during access
  diagnosis. End users do not need the maintainer's development toolchain.
- Preserve dependency direction and legacy command/config compatibility. Generic
  OBS control belongs in the reusable layer, provider/creator behavior above it.
  Prefer bounded repairs to new frameworks or component-library projects.

## Behavior to preserve

- Offline local control, deterministic artifacts, filtered public diagnostics,
  safe paths/recovery, private credentials and approved visual baseline.
- Explicit Start for broadcasting; observed state drives controls/notifications.
  Unknown state cannot authorize restart/update/removal. Failed repeated Start
  cannot stop an existing stream.
- Verified game-only capture or intentional idle, never silent screen fallback.
  Do not imply per-app audio from game-only video.
- Ordinary OBS, unrelated plugins and shared dependencies. Installation/config/
  recovery/local media cannot silently start a broadcast.
- Stream-only audio preferences and user mute intent. Observe microphone device
  availability rather than assuming it from hardware models.
- Explicit removal scope and safe file identity. Preserve settings/media unless
  the chosen operation explicitly includes them.

## Decisions, validation and handoff

The owner updated the sequence on 2026-11-22: **OSS polish #117 → branding and
migration preparation → owner-run fresh repository creation → final local and
Steam Deck test/fix loop → release decision → legacy retirement**. The owner
explicitly moved device testing after migration; do not restore the older
test-before-move prerequisite. Exact destination, Identity release/rights facts
and safe source/trust preparation are still required for the concrete command.
See [the sequence decision](DECISIONS.md#owner-sequence-update-2026-11-22).
The creative direction is selected and its source-preview artwork/native integration
have exact-source local evidence; see the [current checkpoint](docs/pre-migration-qualified-checkpoint.md).
Actual device, full matrix, rights and adoption gates remain. Use focused checks during work.
Separate companion/StreamGod remains deferred. Provider OAuth/phone login is
research-only #89; discuss its design before coding it and do not block the
manual-key implementation on it.

Update canonical docs when contracts/ownership/state/safety change. Record durable
choices in [DECISIONS.md](DECISIONS.md); proposed ADRs stay proposed until the
applicable decision is recorded. Do not add mandatory tools, permission gates or
standards-migration scope through documentation.

Run appropriate checks during implementation and the complete required available
matrix at final source. Re-run when new source invalidates evidence. Record exact
revision/commands/platform/tools/hashes/limitations and distinguish passed, failed,
skipped, unavailable and unrun. Native/mock/browser/cross-build evidence cannot
prove Steam Deck/provider/controller/adoption or hosted CI acceptance.

Keep reviewable source/tests/notes and continuity current. Respect protections
and inspect workflow publication/deployment side effects before merging. Routine
reversible work and draft checkpoints are authorized. Publication, deployment,
spending, transfer or another repository's changes need applicable authorization;
prepare concrete artifacts/evidence before an approval action and do not ask
again for already authorized work.

The owner requested focused implementation issues under existing parent #46,
then one carried-forward finalization checklist at the new destination. Preserve
all 230 original criteria/dependencies and historical receipts, recording the
owner's later sequence amendment alongside them; the child issues are bounded
work, not replacement acceptance. Transfer remaining criteria only with evidence
and a responsible next action. Superseded/consolidated is not passed. Missing
device/CI/review/rights/adoption evidence remains visible.
