# Current work

Current installer repair: the owner reported Decky ready, followed by an OBS 28+
rejection while Discover showed OBS 33.0.1. Confirmed defect: `flatpak info
--show-version` is not supported by Flatpak; the installer mislabeled its command
failure as an old OBS version. The repair uses supported `info --show-ref` and
`list --columns=ref,version`, matches the launched user ref, and reports query/
metadata failures separately from a confirmed version below 28. Tests and the
installer protocol fixture must reject unsupported flags. Candidate 5.1 rebuilds
the CLI/plugin/updater with matching versions; do not use old runtime-5 receipts
to qualify its new artifacts. Actual owner-device acceptance remains open.

Repository: `szmyty/obsgod`. Active campaign:
[Roadmap 1 / #8](https://github.com/szmyty/obsgod/issues/8).

The owner approved implementing Roadmap 1 on 2026-11-11, then explicitly requested
merging the prepared PR stack and closing milestone 1. Normal merges and
owner-directed administrative milestone closure are now authorized. Keep
unverified acceptance issues open: closure of the implementation milestone does
not establish actual Deck/Kick or CI success. Do not bypass branch protections,
publish a release, deploy, spend money, change other repositories, implement
Roadmap 2, or expand the deferred product backlog.

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

Actual Steam Deck/Kick/adoption and successful CI remain unverified; previous CI
jobs did not start because GitHub reported an account billing lock. The owner has
now authorized implementation merges despite those recorded gaps. Check live PR,
master and milestone state for merge/administrative-closure results; keep the
remaining acceptance issues and their original criteria intact. No money or
billing changes, release/tag publication or deployment are authorized. Roadmap 2
and the deferred backlog remain separate.
