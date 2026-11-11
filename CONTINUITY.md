# Current work

Repository: `szmyty/obsgod`. Active campaign:
[Roadmap 1 / #8](https://github.com/szmyty/obsgod/issues/8).

The owner approved implementing Roadmap 1 on 2026-11-11. Work through its scoped
children and push reviewable draft PR checkpoints. Keep all merges and issue
closure for owner review. Do not publish a release, deploy, spend money, change
other repositories, implement Roadmap 2, or expand the deferred product backlog
as part of this campaign.

Read [the execution record](docs/roadmap1-development.md) for inspected source,
artifact provenance, PR sequence, preservation and qualification requirements.
Read the live issue/PR bodies before resuming. The existing isolated checkout
is sufficient; no additional worktrees are needed.

Current starting branch was `codex/steam-deck-streaming` at
`0eb8324c2b1f23fea069570eded1cd0c75d99274` (draft #15). `master` is
`d0268d13381b463f5950d202917f437a6288a3e4`. Published preview 4 still has unresolved
owner-device OBS readiness and automated Decky update failures. Do not treat its
native/mock receipts as Steam Deck qualification.

Final source/artifact revisions and evidence will be recorded in the campaign's
qualification documents. No issue is complete merely because code or a package
exists; required device, CI and review gaps remain explicit closure gates.

Implementation checkpoints are stacked drafts #26 (plan), #27 (runtime), #28
(state), #29 (installer) and #30 (updater). The integration/qualification branch
is `codex/roadmap1-qualification` (draft #31). Read each PR's base before
reviewing/merging; these branches depend on the preserved draft #15 foundation.

Available local qualification passed at exact candidate source
`2287ed4c2f3fcc9b8ec42bbd68ac531063b5d578`. Review artifacts are immutable commit
`1fbf92ff36eea77bee0f3da186e99d856c80774e` on
`artifacts/roadmap1-deck5-review`; that orphan artifact branch must never be merged
into source. Later evidence-only documentation does not relabel that candidate.
Read [the current acceptance packet](docs/roadmap1-acceptance.md) before resuming.
Do not rebuild another SHA and reuse its receipts.

All Roadmap 1 issues remain open: actual Steam Deck/Kick/adoption and owner
review are missing, and current GitHub CI jobs did not start because GitHub
reports an account billing lock. No money was spent or billing changed. Source
`master` and preview PR #15 are unchanged. No release/tag/deployment/merge/closure
was performed. Roadmap 2 and deferred backlog remain untouched.
