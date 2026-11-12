# Current work

## 2026-11-12 consolidation and proposed product plan

The latest owner request authorizes merging all open PRs, deleting nonprimary
branches, and preparing a proposed monetizable-product roadmap. PRs #32, #33,
#34 are now MERGED in order; final merge is
`cc5e5b6b6d4c18c54b1040722924c6b68e5c4ccd`. Its tree equals prior PR34 head
`5f2e1816285c55e3e1d879998d3fc46bba7ce5a7`; fresh merged-tree Go race checks
(94 pass events/64 top-level; one optional existing-OBS skip), Python70 and
Node9 passed. No device/CI acceptance issue was closed from merging. Fresh CI
executed zero steps because of the existing account billing lock.

All22 nonprimary remote branches and13 existing local branches were deleted
AFTER exact tip verification against non-release recovery tags
`archive/2026-11-12/<old-branch-name>`. See [the archive record](docs/branch-archive.md).
This preserves orphan artifact commits and immutable download URLs; never merge
artifact histories into source. Only `master` remains. The owner-requested rename
to `main` returned403 `Resource not accessible by integration`; the owner must
rename it on GitHub's Branches page. Do not create a duplicate main branch.
The Steam Deck workflow accepts both branch names. No protection bypass occurred.

Read [ROADMAP.md](ROADMAP.md) and the live issue bodies before new work.
Milestone2/parent#23 now propose a supported public launch and optional funding:
#35–#45 plus original#11/#25 and foundation acceptance#8/#10/#16–#22.
Milestone3/parent#46 propose advanced streaming/validated paid offerings:
#47–#51 plus richer media#24 and preserved broad#7/#9/#12/#13/#14 ledgers.
All original criteria/history/dependencies were retained. M1's administrative
closure does not pass its outstanding acceptance. No existing issue was closed.
Organization/name/domain/recipient remain TBD; `decky-obs` is only a candidate.
Identity was inspected read-only at main `401b2f1de298a171fbb5bf4ee6b510e0cf12c301`
(stable v1.0.0); choose compatible tooling during implementation, author supported
manual v1 consumer source, and approve real SVG masters/rights after naming.
Do not produce final assets twice or modify the Identity repository.

Store eligibility is unresolved: current Decky policy and submission templates
restrict AI-authored source; no majority audit or maintainer decision exists.
Never make an unsupported provenance attestation. Direct distribution and an
optional owner-verified support destination remain independently proposed.
Required real Stable/Beta and independent Preview testing is not supplied by
cloud OBS tests. Account/payment facts and revenue are not invented.

Preview6 stays tied to exact packaged source
`33dcd8476606a1ed7a3bbca06e81fb156dfebcc7`, version `0.1.0-deck.6`, immutable
artifact `71143dce72654bae2ad76ebe382dd810990c2c85`, now retained by archive tag
`archive/2026-11-12/artifacts/deck6-audio-game`. RuntimeSHA256
`23cc2c484b7524756a3b632bf8a8e7231ac7c515c06a08183422ed91b7e82650` is unchanged.
Actual new6 Deck audio/Flatpak/Gamescope privacy/game changes/hardware/controller/
session/performance/Kick sound remain open. Owner reported5.2 video success and
silent audio, not complete6 acceptance. Read the exact evidence packet below.

This turn is planning and branch consolidation, not authorization to implement
the proposed M2/M3 work, create/transfer organizations/repositories, publish an
Identity/product release, deploy sites, submit to another repository, create
payment accounts or spend money. No new product release/deployment occurred.
Normal injected HTTPS GitHub authentication works without explicit Authorization
headers; stale CLI credential401 does not mean all authentication is absent.
Existing private checkpoint helper hardcodes a NOW-DELETED feature branch:
never use it unchanged. Verify the current default/ref before a fast-forward.

## Historical records (superseded by the status above)

Prepared preview6, final exact qualified source
`33dcd8476606a1ed7a3bbca06e81fb156dfebcc7`, draftPR34 (base33, base32).
All available local checks passed FRESH:94Go including subtests(64top-level),
70Python,9Node,static/security/frontend/repro packages, actual archive browsers,
pinnedDecky/default installer/Desktop updater fixtures, real native OBS audio/
media/lifecycle,13app-filter protocol cases and actual OBS continuous game/idle/
RTMP transitions with decoded video+audio. One optional existing-OBS test skipped;
six cross-builds compiled only. Read [the criterion/evidence packet](docs/audio-capture-upgrade.md).
Immutable review artifacts: `71143dce72654bae2ad76ebe382dd810990c2c85` on
`artifacts/deck6-audio-game`; never merge that orphan branch into source. Full
runtime SHA256 `23cc2c484b7524756a3b632bf8a8e7231ac7c515c06a08183422ed91b7e82650`.
Actual Deck audio/Flatpak load/game-only privacy/transitions/performance/Kick and
required review/CI remain gates. Fresh CI jobs executed zero steps due to account
billing lock. No new merge/release/tag/deploy/issue closure. Master still4a8a38a.
Historical failed fixture runs c392/d80 are retained separately, not relabeled.
All seven public downloads, internal payloads, component versions, native
library/preferred source/licenses and the Desktop install command were independently
verified after upload; see docs/evidence/deck6-public-download.json. Later evidence-only
commits must not change the exact packaged revision above.


Active owner-authorized upgrade: after 5.2 instructions the owner reports local
video recording and live stream video WORK, but audio is silent. Exact installed
versions/routes and audio/microphone media evidence remain missing. They request
audio repair, full-screen/game-only selection and black/custom-message fallback
between games while the stream stays active. This explicitly activates the
bounded idle/transition part of #24/#23; #25 password controls and arbitrary video
assets remain deferred. Work is stacked on draft #33 in
`codex/deck-audio-capture-modes`; read [the upgrade plan](docs/audio-capture-upgrade.md).
Candidate6 implementation is prepared in draftPR34; developmentGo94/Python70/
Node9, native audio, app-filtered protocol and real OBS game/idle/RTMP transition
checks passed. Final qualification caught two test setup gaps: workflow input permissions for
runner/container UID differences, then the new native game fixture raced scene
initialization after authentication (OBS207). Only that fixture now waits for
frontend readiness under a bounded deadline; other errors still fail. Historical
source29/c392receipts are retained separately and cannot qualify the new revision.
Final exact-source package/repro/matrix qualification is next;
record its clean revision and artifacts before delivery. SourceC/Go/tests are
now stable; do not modify code while final packages/tests run. Existing explicit
CLI GitHub credentials began returning401, but normal HTTPS API requests with
inherited proxy/CA and NO explicit Authorization header successfully use injected
authentication. Private checkpoint helper under `.obsgod-tools/audio-game-upgrade/`
preserves exact git commit SHAs via Git data API and normal fast-forward; no
credentials were read/changed. GitHub plugin writes and public git fetch work.
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
