# Current work

Active owner-authorized upgrade: after 5.2 instructions the owner reports local
video recording and live stream video WORK, but audio is silent. Exact installed
versions/routes and audio/microphone media evidence remain missing. They request
audio repair, full-screen/game-only selection and black/custom-message fallback
between games while the stream stays active. This explicitly activates the
bounded idle/transition part of #24/#23; #25 password controls and arbitrary video
assets remain deferred. Work is stacked on draft #33 in
`codex/deck-audio-capture-modes`; read [the upgrade plan](docs/audio-capture-upgrade.md).
No new merge, release publication, deployment or spending is authorized. Keep
actual Deck audio/game-only/privacy/session acceptance open and preserve settings,
credentials and ordinary OBS configuration. The older records below are history.


Current launch/isolation repair: the owner successfully installed 5.1, then
supplied a Gaming Mode photo showing a 20-second wait ending before the OBS
control listener appeared. The read-only effective-path probe CONFIRMED Flatpak
replaces the old CLI `--env=XDG_CONFIG_HOME` override with the ordinary app path.
The repair applies the private path through `/usr/bin/env` inside the sandbox,
for background and visible launches, without altering ordinary OBS configuration
or output authorization. Draft PR #33 builds on draft #32. Candidate 5.2 exact
qualified source is `e10383598a01b7bfab946735d4187a458a5177e5`; immutable artifact
commit `414480b8cdc23f0eb5e0ea209f45f98adcddaebd` on
`artifacts/deck5-config-isolation`. Never merge this orphan artifact branch.
Fresh local matrix passed: 59 Go (one optional skip), 60 Python, 8 Node, static/
security/frontend/package/repro/browser/Decky/updater and real native OBS media/
lifecycle checks with modeled Flatpak reset. Ordinary OBS configuration remained
untouched. Public downloads, internal payload hashes and source/version metadata
were independently verified. Cross-builds compiled only; fresh CI jobs did not start due to the
account billing lock. Actual corrected Deck startup/capture/audio/Kick retry is
unrun; the probe's PulseAudio symlink warning remains audio follow-up evidence.
Do not delete sockets or claim device recovery. Read [the isolation evidence](docs/flatpak-config-isolation.md)
for exact commands/platforms/hashes and persistent filtered-log retrieval. PRs
#32/#33 remain drafts, master remains `4a8a38a839a259e14a19ff003e6a9d71e719ef1d`,
and the prior seven merges/administrative milestone closure do not close missing
acceptance issues. No new merge, release/tag publication or deployment occurred.

Current installer repair: the owner reported Decky ready, followed by an OBS 28+
rejection while Discover showed OBS 33.0.1. Confirmed defect: `flatpak info
--show-version` is not supported by Flatpak; the installer mislabeled its command
failure as an old OBS version. The repair uses supported `info --show-ref` and
`list --columns=ref,version`, matches the launched user ref, and reports query/
metadata failures separately from a confirmed version below 28. Tests and the
installer protocol fixture must reject unsupported flags. Candidate 5.1 rebuilds
the CLI/plugin/updater with matching versions; do not use old runtime-5 receipts
to qualify its new artifacts. Actual owner-device acceptance remains open.

Prepared installer repair: draft PR #32, exact qualified source
`f43e5b53b473c35dfe3facec114d28cbeff6c35d`, version `0.1.0-deck.5.1`, immutable
artifact commit `afec6263fc43369917cd54b80a58055d5c00f0e6` on
`artifacts/deck5-flatpak-fix`. Read [the repair evidence](docs/installer-flatpak-fix.md).
Fresh local matrix and public file/hash verification passed; one optional test
was skipped, cross-builds compiled only, actual Deck retry and successful CI are
still missing. Do not merge the artifact branch or call this a release. The
earlier milestone closure and seven merges remain unchanged; PR #32 is a new
draft follow-up, not an already-merged fix. Reinstall in place; preserve keys and
rollback copies. The source branch is `codex/fix-flatpak-version-probe`.

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
