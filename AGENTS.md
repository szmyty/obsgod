# Working in this repository

Read [architecture](ARCHITECTURE.md), [vocabulary](ONTOLOGY.md),
[decisions](DECISIONS.md), [roadmap](ROADMAP.md), [continuity](CONTINUITY.md)
and applicable feature/security guides before behavior changes. Read live issues,
PRs and the checkout as evidence: old handoffs/receipts do not qualify new source.
Follow applicable nested instructions. Current user authorization takes precedence.

## Scope and collaboration

- Inspect files, git status and branch before editing. Use the existing isolated
  checkout unless current instructions require otherwise; preserve others' work.
- The completion campaign authorizes feasible plugin implementation, checks and
  draft PR checkpoints. #51 is separate monetization/Decky Store research; do not
  perform it as feature scope or resolve it with unsupported policy assertions.
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

The owner requested issue consolidation after review/merges, leaving one
implementation checklist and separate #51 research. Transfer every remaining
original criterion/dependency with evidence and a responsible next action. Close
transferred tickets as superseded/consolidated with that link, not as passed.
Do not consolidate pending implementation tickets before agreed review/merge
checkpoints. Missing device/CI/review/rights/adoption evidence remains visible.
