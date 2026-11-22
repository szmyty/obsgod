# Current work

## Pinned owner entrypoint follow-through

After the recommendation to use `egohygiene/deckystream`, the owner said
"ok lets do it". Preparation and the owner-run entrypoint now target that exact
repository. This does not establish organization administration rights or an
executed migration; the existing connection's organization-membership read was
403, while ordinary repository and user reads worked.

Work on the existing checkout prepares a one-shot Bash entrypoint that clones
the exact supplied source SHA into a retained private workspace, refreshes the
public history, then invokes the guarded snapshot tool. Default preparation
does not create a GitHub repository. Explicit `--apply` uses the owner's normal
authenticated GitHub CLI and the existing exact-source/owner/destination checks.
No system installation, release, deployment, old-repo deletion or automatic
retry is part of the entrypoint.

[PR #120](https://github.com/szmyty/obsgod/pull/120) records the launcher and
its [scoped evidence](docs/evidence/migration-entrypoint-review.json). Source
`bd5d016` passed 13 entrypoint, 30 snapshot/migration and 24 updater tests, plus
Bash syntax, whitespace and 279 local documentation links. A real default run
fetched live source `685f337`, captured public history and prepared all 671
tracked entries and 230 criteria without requesting GitHub writes. Independent
code review accepted the process-group/caller-preservation checks; operator
review clarified actual Git identity/HTTPS push and organization-admin
prerequisites. These results do not qualify a new product binary or actual apply.

Fresh release inspection still observes Identity stable v1.0.0 only. The
anticipated new release tag and explicit SVG/PNG artwork license choice remain
needed for production branding adoption; general go-ahead is not recorded as
a fabricated license/rights decision. Keep selected aurora source/exports and
the unreleased cfb6 authoring pin honest while completing independent work.

## Fresh-repository preparation after #117

#117 is merged and closed through [PR #118](https://github.com/szmyty/obsgod/pull/118)
at **852320741d3f23aa513e3798528b3576b8b179fb**; its tree matches reviewed
2014528. All 12 bounded OSS criteria have [recorded evidence](docs/oss-experience-review.md).
Current work prepares #87 under the owner's new migration-before-testing order.

The [owner-run runbook](docs/fresh-repository-runbook.md) describes a source-only
fresh snapshot and explicit apply. `scripts/prepare-fresh-repository.py` defaults
to an offline plan, retains the original archive and stages only the five
declared canonical repository metadata/projection files in a separate snapshot.
It preserves current source/history/installed IDs and refuses existing remote
destinations. No actual creation/push to another repository was performed.

[PR #119](https://github.com/szmyty/obsgod/pull/119) checkpoints this preparation.
Code at `a8dbf8a` passed 30 fresh-repository and 24 existing release tests; the
same suites pass in a disposable staged destination tree. Fifteen public-history
tests also pass. A real offline CLI run at `9a02e9d` retained 670 source entries
and all 230 criteria, with exactly five staged canonical paths. The
[scoped review](docs/evidence/fresh-repository-preparation-review.json) records
hashes and limitations. Independent review found and fixed publisher-specific
fixtures and inherited SHA256 Git defaults before any actual creation. The
remaining plan input is a matching public tracker backup; this preparation
neither performs authenticated destination inspection nor passes hardware/CI.

The assistant recommends `egohygiene/deckystream` after the owner asked for
advice; this is preparation, not a fabricated final owner selection. The owner
will select the exact destination by the command they run. Source remains
`szmyty/obsgod`; no runtime update trust is activated here.

The [brand packet](docs/migration-brand-packet.md) binds existing selected assets
and the new Identity version boundary. Latest observed published stable is still
v1.0.0; the current cfb6 authoring pin is explicitly unreleased. New release tag,
actual artwork license/usage and publisher facts remain unresolved. All 38
selected exports passed fresh read-only raster drift checking; six UI projection
and two PNG regressions passed. These are not production adoption or device proof.

Prepared body templates consolidate the remaining work into one
[finalization/test issue](docs/finalization-checklist.md) and separate
[optional login research](docs/auth-research-carry-forward.md) after the new
repository exists. Do not invent fresh issue numbers or close old remainders
before recording real destination links. Full ACT/hosted/service/device results
remain separate, and no release, deployment, archive copy or deletion occurred.

## OSS polish and revised migration-first journey

The owner authorized implementing and merging #117, followed by branding and
migration preparation, then testing the finished installation after migration.
The [sequence decision](DECISIONS.md#owner-sequence-update-2026-11-22) supersedes
the earlier test-before-move order below. Original criteria/evidence remain;
none of the absent device/service/rights results becomes a pass.

The #117 source adds a task-oriented [documentation map](docs/README.md), four
README audience routes, documentation/CLI/Decky contributor entry points,
separate CLI/feature intake and visible historical-installer context. The
five funding providers already agree with generated packaged buttons; Patreon
remains inactive and unconfigured wallets hidden. Focused documentation review
is recorded in the [criterion review](docs/oss-experience-review.md), separately
from runtime qualification. [PR #118](https://github.com/szmyty/obsgod/pull/118)
holds this bounded documentation work.

The next exact Identity release is not assumed from pending upstream work.
Selected 01 / aurora and existing concepts remain intact. Final destination
(`egohygiene/deckystream` or `incomprisllc/deckystream`) is not selected by a
question in chat. Prepare the reviewable source/rights/history packet and
owner-run command while those facts are resolved; do not change another
repository, publish a release or delete the current repository as a side effect.

The runtime candidate remains exact `772230a` / immutable artifact `430cc391`.
Documentation changes do not rebuild or relabel it. Actual Deck/provider tests
remain unrun and move to the post-migration finalization checklist. #89 remains
separate research before owner design discussion.

## Guided testing handoff

The owner requested all feasible pre-manual work, source integration and a simple
booklet for testing together one step at a time. Start with the
[testing booklet](docs/testing-booklet.md) or [printable PDF](docs/testing-booklet.pdf).
The [readiness record](docs/pretest-readiness.md) separates completed preparation,
external gates and the exact candidate; the booklet itself is not a passed test.

Implementation PR #113 merged at **c05e06e208bf44fd3e3cfaee5ea9342935a9279a**,
#114 at **a315224a8a5cdf8e415a9e5bdc8b9bc5a8740640**, then current-link and
acceptance handoff #115 at **a2137bf214c77efda3ce3fb87879f88004c6477c**.
The #115 merge tree **6795ecffc02440b3096409c100fb1b59b331754c** matches its
reviewed documentation head. The default branch remains `master`; the future
approved destination will use `main`.

Bounded source issues **#76, #77, #78, #80, #81 and #84 are closed** against the
[47-clause assessment](docs/evidence/bounded-source-closure-20261120.md), not
merge alone. All 230 original criteria/dependencies remain unchanged. Ten issues
remain: #46, #79, #82, #83, #85, #86, #87, #88, #89 and #95. Actual #79 device
acceptance, #82-C1 supported-loader lifecycle and #83/#86 hardware/provider cases
remain **UNRUN**.

The test download stays pinned to exact clean source
**772230a32a8fdb237a58b8a637947b31671ad509**, tree
**f157ea77d16a1f1ce04bf1e47b584f9183c9c359**, with 648 tracked-source inventory
entries. The [immutable 430cc391 packet](https://github.com/szmyty/obsgod/tree/430cc391cb63f080214aacc279e5c04b1092c7a5)
provides version 0.1.0-deck.9, standard ZIP, checksums, optional current cleanup
helper, rollback and detailed evidence. All 21 review downloads were verified.
At that exact source, 70 command checks passed and two were unavailable; all
three native OBS harnesses and ten packaged browser flows passed. The earlier
failed attempt remains separately recorded. Later Markdown/evidence-only
changes do not relabel or rebuild the qualified candidate.

A fresh maintained matrix invocation at clean **a2137bf** exited 3 at preflight:
root/Docker required **7,544,361,132 bytes**, available **3,123,400,704**, short
**4,420,960,428**. Scratch had 8,664,485,888 bytes versus 6,442,450,944 required.
The Docker probe and all six ACT workflows remain **UNRUN**. Fresh hosted reads
at that same revision observed five runs/eight jobs: seven billing-lock failures,
one push-only dependency-review skip and zero executed steps, with no non-billing
failed job. This is unavailable execution, not source failure or passing CI.
The [filtered evidence](docs/evidence/pretest-readiness.json) retains commands,
input hashes, measured budgets, job IDs and annotation-message hashes without
publishing raw private logs or credentials. The previous exact-PR SBOM 404/
comparison 403 observations stay separate from actual future-destination #95.

Next is our guided #86 test/fix loop on the current compatible installation.
Start with inspection only, then setup, playable local picture/audio, intentional
capture privacy, opt-in microphone/headsets and an explicitly chosen live test.
Later session/update/recovery/removal cases preserve ordinary OBS, shared
Flatpaks, credentials and media. Do not wipe or retire legacy files to prepare
normal testing. Record exact outcomes and filtered diagnostics; actual failures
receive a new pinned candidate and affected requalification.

Owner destination, rights/license/publisher/contact, signing and site choices
can be prepared in parallel and remain unresolved. They do not block a local
clip on the current installation. After current-install acceptance and exact
authority, execute #87, verify actual #95 services, then #88 canonical new-install/
adoption/v1 preparation; #46 closes last. #89 remains research-only before owner
design discussion. No product release, deployment, migration, account registration
or spending occurred. Old af7 artifacts and historical installer hashes stay intact.

## Earlier aurora review candidate and qualification

#112 merged normally at **069db4a21ec0a173b7dd30c12a53018c7700f79b** after
fresh focused checks at448b15d. Its two verified-merged branches were removed.
Draft [#113](https://github.com/szmyty/obsgod/pull/113) integrates the selected
01 / aurora source kit, lowercase deckystream, local native marks plus an
independent observed-state badge, README/site assets and current setup docs.

Qualified clean source is **af7a20fdd0c62404e9b11d540fb605368e269380**, tree
**d6149d9ec670cffcc30db355262aa688382b5e7e**. The completed controller has
**67 passed command predicates and1 unavailable matrix command**. All10
packaged browser flows,3 native Linux OBS harnesses,161 Node tests,33 branding
tests,38-file export repeat, Go/Python/security and package/install audits passed
with recorded skips/limits. Two complete primary builds match ZIP **4deece2b**.
Read the [exact-source checkpoint](docs/aurora-integration-checkpoint.md) and
[owner packet](docs/aurora-owner-packet.md).

All18 immutable review-artifact files at **f2b160823800e3befd7440e6bcce8d135845a008**
were publicly downloaded and hash-verified. This is a review branch, never a
source merge target or release/updater offer. Actual proof ZIP, original/public
hashes, independent source/visual/privacy reviews and all104 bounded criterion
remainders are recorded. The original230 ledger/dependencies remain unchanged.
All21 literal #80/#81 local criteria have evidence; issues stay open for review.
The [foundation reconciliation](docs/evidence/aurora-af7-foundation-criteria.md)
maps27 #76–#79 source contracts to fresh af7 evidence,0new gaps. No new
fullACT/hardware dependency was imposed on source-only literals; real controller/
Flatpak/provider and #79's explicit review/device keep-open checkpoint remain.

FullACT preflight refused before allocation: root shortfall4,946,694,316bytes at
the recorded attempt; all6 jobs/probe unrun. Standalone commands are not ACT jobs.
Hosted af7:15 billing refusals+1skip,0steps, no executed non-billing source failure.
A later read-only [capacity audit](docs/evidence/aurora-af7-resource-feasibility.md)
found no safe reclaim/relocation plan: even optimistic measures remain short;
no images/caches/outputs were removed. Original matrix dispositions are unchanged.
Machine OS is still unknown; next is the capable-free-machine matrix and numbered
owner tests, then actual #86 Steam Deck/loader/provider/controller/headset loop.
#82-C1 real supported-loader lifecycle remains explicit. #87/#88 migration/new
install/v1 and #95 actual destination dependency graph follow their original
gates; #89 OAuth/phone research remains separate. Rights/license/publisher,
required CI/platform/review and independent/new-user adoption remain open.

Later evidence/documentation commits do not relabel af7 package/source bytes as
a newer qualified revision. No release, deployment, migration, Store submission,
paid resource or other-repository change occurred. No network/package preset or
injected authentication change was made. Existing checkout remains the source
workspace; old receipts apply only to their stated revisions.

## Earlier checkpoints

## Aurora branding and native panel batch in progress

The owner authorized merging #111 and proceeding with #80/#81, with the final
machine test pass followed by Steam Deck validation. #111 merged normally into
`master` at **699fac3503decc05345ec992f09eeedea8080fce**; its tree matches
reviewed head bed3daf. #104 closed after independent evidence for its six literal
criteria. Its exact qualified source remains 0c79846, not this merge metadata.

Work continues on **work/aurora-native-panel**. Draft **#112** now contains
functional UI source **3943f3c** with independent static review; new repository
build/typecheck/Node/browser checks remain **UNRUN**. The selected 01 / aurora direction
and all retained concepts remain intact. Source now refines native panel order,
progressive disclosure, safe navigation feedback, collapsed recovery errors and
clip loading/retry presentation while preserving observed-state/action gates.
Read the [batch checkpoint](docs/aurora-ui-checkpoint.md) for source facts,
remaining artwork work and verification status.

The Cloud execution server failed to start with “environment configuration was
canceled”; a shell probe confirms no usable runtime. GitHub access works. Remote
reviewable checkpoints preserve the existing offline checkout and any local edits.
New build/typecheck/test/render checks are **UNRUN**, and earlier receipts do not
qualify new source. Restart/reconnect the Cloud workspace to resume the pinned
tools and focused checks. The later owner-machine and actual Deck tests remain
explicit #85/#86 gates; deferring them does not mark them passed.

All 230 original criteria/dependencies remain intact. Existing executable/plugin/
storage IDs, public API and approved state/privacy behavior remain compatible.
No rights/production-art approval, Identity repository change, release, deployment,
migration, Store action or paid resource is implied.

## Earlier primary builder and local qualification checkpoint

The owner explicitly requested merging all open PRs and starting the next batch
on 2026-11-18. Normal merge order **#109 → retarget #110 to master → #110**
completed at **2fbb0cb67bbb42adae6e52210124f6aa5a22d6d6** and
**cdcc668dc21f86748dbb5a8a00d2516affb83c7e**. Default remains `master`. The
final merge tree exactly matches the reviewed #110 head85dc65c; this does not
relabel the older4eac runtime qualification as a newly built merge candidate.
Effective branch rules/check requirements were empty; no protection was bypassed.
Hosted jobs executed zero steps under the known billing gate. Source merges alone close no issues. Independent criterion reconciliation supports
closing101(7/7),102(8/8) and103(6/6) for their literal bounded software contracts;
[the closure assessment](docs/evidence/audit-101-103-closure.json) retains actual
supported-loader/device/CI/rights/adoption gates separately. In particular102-D4
prohibits dependency downloads during initialization; its actual-loader startup
observation remains UNRUN under86, rather than being claimed as target proof.

**#104** is implemented in draft [#111](https://github.com/szmyty/obsgod/pull/111)
on **fix/repeatable-primary-ci**, based on cdcc668. Exact clean qualified source
**0c798468ecadd753c43bb8970b76e88f263f3a5c**, tree
**b5d95741d3352d8eccfc954085895fda8268fa38**, has local evidence for all six
literal criteria. Read the [checkpoint and reviewed proof](docs/primary-ci-checkpoint.md).
Two complete non-root primary builds match canonical ZIP **7fc9faad**;
optional official assembly compares33 files. Standalone application269/two
skips, tooling116, frontend156, actual packaged/browser/native/adapter/snapshot
checks pass. The completed report verifies61 passed command-check predicates
plus one capacity-unavailable command; these are not61 test cases or ACT passes.

The supported constrained matrix actually exits3 before allocation: all six ACT
workflows and the Docker probe remain **UNRUN**. R1 explicitly permits an early
refusal with a concrete need; this does not satisfy #85's full matrix. Latest
preflight requires7,544,361,132 root bytes but observes2,684,194,816: free at
least **4.6GiB more on root/Docker**, or use a free workspace meeting the printed
root/scratch budgets. Separate scratch has enough space. Hosted jobs execute
zero steps under billing; actual dependency comparison separately returns403.

Post-consumer cleanup touched only private compiler caches; module inventory
before/after matches. Source, artifacts/evidence, tools and presets remain.
Old root-owned generated outputs were preserved by literal same-mount rename;
no recursive chown, host-cache move, global prune or paid resource. Historical
4108 VFS allocation, generated-output permission failures and the private long-TMP
browser failure are retained. The final metadata-only VFS preflight refuses
before any allocation; the maintained short-path wrapper passes browser checks
at unchanged0c source. Later evidence-only commits do not qualify newer runtime.

All230 original criteria/dependencies remain intact. PR111/104 remain open for
review. Next source batch is selected aurora artwork/controller UI/current docs
under #80/#81, before final #85 qualification and owner #86 test loop. No release,
deploy, migration, Store action or other-repository change occurred.

## Earlier settings boundary #103 local review checkpoint

Draft **#110** implements the bounded capture deadline/readback contract on
**fix/settings-boundary**, stacked on still-unmerged draft **#109**. Exact clean
qualified source **4eac7a469285cbafad5dc5a7ea07205374293dfd**, tree
**2ca38c6e704ce9c9ea19b50938e99af98714b7d9**, passed all six local ACT jobs,
application269/two skips, tooling85, frontend156, six actual packaged settings
cases, native18 proofs and all11 supplemental/postmatrix commands. Read the
[criterion-level checkpoint, proof and independent review](docs/settings-boundary-checkpoint.md).
Later evidence-only commits do not qualify newer runtime or become a release.

All six original #103 criteria have local evidence; #103 and drafts #109/#110
remain open for review. Actual default `master` remains **1440f993**. All230
original criteria/dependencies, #86 owner Deck/provider/loader/controller/headset
gates and hosted/dependency-review limits remain intact. No merge, release,
deployment, migration, Store submission, spending or consumer adoption occurred.

The report uses an explicit hash-verified view of all nine completed same-source
runs (six PASS/three FAIL). The original interrupted `200445Z` provisional record
has no final exit/checksum and remains unchanged/unverifiable/unqualified. Both
reports, its filtered partial log and the selection inventory are preserved;
the original-state report still exposes that integrity error. Zero integrity
errors applies only to the completed-run selection.

Runner reserve refusals and the repeated-evidence guard were retained, then
resolved with measured disposable compiler-cache assistance, a preserved separate
fixture volume and fresh test-output preparation. All five cache/tool/artifact
locations and the fixture volume were restored with matching current hashes;
network/auth/package presets are unchanged. This does not complete #104.
Next separate work is selected aurora artwork/controller UI/current docs, bounded
#104 build/resource work, then #85 final qualification and the #86 owner test loop.
Do not reuse this receipt to qualify those future changes.

## Earlier #103 authorization and implementation checkpoints

The owner requested the next batch on 2026-11-18. This authorizes bounded
**#103** implementation, focused checks and a new exact-source qualification;
it supersedes that issue's planning pause. Existing draft **#109** is still
unmerged at **6968ad9ebb577c2f37ae42bf51f2f1862c319e8a**, while actual default
`master` remains **1440f993b445a8d90168de5d1bfc36066a6f9af1**.

Use existing isolated checkout branch **fix/settings-boundary**, stacked on
#109's branch for a reviewable #103-only diff. This is an integration checkpoint,
not a new hard dependency or permission to merge #109. Preserve all230 original
criteria/dependencies and all prior evidence as historical for newer source.

The batch bounds complete capture-mode operations across Go action/post-status,
Python preflight/cleanup/readback and UI deadlines, preserving explicit Start,
Stop/recovery, caller-disconnect ownership and microphone leases. It also
requires complete, consistent configuration readback using one small shared
Go-produced JSON corpus across Go/Python/JS, including documented legacy
omitted/zero dimensions. No schema generator, new validation library or framework.
Actual Deck/provider/hosted gates, remaining settings/artwork/resource work,
release/deployment/migration, OAuth and spending remain separate.

The environment is running/connected; actual shell, Git/API, pinned tools and
Docker work. Preserve network/package/auth presets. Temporary cache relocation
is measured with deterministic hashes and must be restored after qualification.
No old aa323f0 receipt qualifies this new source. Continue source integration,
focused regression/process/browser checks, independent review, then the complete
required available matrix at the final committed source.


### First settings matrix: worker fixture synchronization

Exact source **e2928ffea50eaf9988be30c47d2c471c8653434e** passed five local
ACT jobs, but the candidate failed an unchanged dependency-worker test. Its
fixed1.1-second sleep raced the real worker's inherited lease release; observed
`running` was correct while that lease was held. Preserve the failed complete
attempt and do not call e2928ff fully qualified. Its separate actual packaged
settings check did pass all six cases, including the lock held beyond UI15.

The bounded repair changes only the test: controlled fake-child release, normal
completion marker and actual kernel setup-lease release precede the interrupted
status assertion. The real three-second worker budget and product module stay
unchanged. Assertions retain/strengthen running/retry-blocked/same-ID/exact-one-
mutation, then interrupted/compatible/retryable states. Twelve normal-user host
repeats, twelve isolated-container repeats and the dependency module pass.
Commit the repair, rebuild the exact candidate and rerun all six jobs at the new
clean source before final qualification. No old pass is promoted.

### Earlier settings source checkpoint in draft #110

Draft [#110](https://github.com/szmyty/obsgod/pull/110) is stacked on unmerged
#109. Source now bounds the full capture operation, preserves pending identity
until owned process exit, requires canonical preflight and strict configuration
readback, and removes fixture-only output-known defaults. The shared106-case
corpus covers actual Go emission and malformed wire cases, including legacy
fields, legitimate nested-connection differences and JSON numeric/URL parity.
Read [the contract](docs/settings-boundary.md).

Focused Go, Python52 and frontend checks pass with independent lane review.
The first integrated Go race failed when the new real CLI process test collided
with the deck package's fixed-port simulated OBS. Keep that original evidence;
the new process case now has the explicit `deck_process` tag and runs serially
in the candidate workflow. Full default race, the isolated tagged case and vet
then pass. Assertions and deadline limits were retained. The workflow also runs
actual packaged Python/Go under a control lock held beyond the panel deadline.

Current source is ready for a committed candidate and actual packaged checks.
The complete new exact-source matrix, final independent evidence review and
qualification records remain pending; older aa323f0 receipts are historical.
Actual supported Deck/provider/hosted and all release/migration gates remain
unchanged. #103 and both drafts stay open for review. No paid resource used.

## Cleanup/recovery implemented and qualified; draft #109 for review

The requested previous PR stack was already merged into actual default
`master` at **1440f993b445a8d90168de5d1bfc36066a6f9af1**. The next bounded
batch **#101/#102** is implemented on **fix/cleanup-recovery**, in draft
[#109](https://github.com/szmyty/obsgod/pull/109). Both issues remain open for
review; no merge or target acceptance is inferred from local tests.

Exact clean qualified source: **aa323f0119e2d3c475d04a30860a4c3e314620bc**,
tree **9f987b34b33daad2922c0de0c49f51aeb27b1931**. All six serial free local
ACT jobs pass, with zero evidence errors/open failure groups. Application tests:
258 passed/2 skipped; tooling85 and frontend43 pass. Both actual packaged
transport/upgrade/removal runs, supplemental CLI/browser upgrades, 18 filtered
native proofs, 218 CPython/240 simulated-frozen adapter checks and six normal-user
frontend checks pass. The primary ZIP matches both repeated workflow builds and
all33 official CLI payload files. Read the
[checkpoint, criterion evidence and limits](docs/cleanup-recovery-checkpoint.md).
Evidence-only followups do not relabel aa323f0 qualification.

The batch preserves live update/install/control lock generations, pins cleanup
roots/ancestors through partial recovery, rejects unsafe writable ancestry,
shares verified native dependency policy, separates loaded-plugin updates from
optional Desktop app inventory, and binds exact-version recovery/rollback.
Explicit legacy-app-only retirement preserves the active plugin/shared stores.
Serial integration exposed real release-tree self-mutation; import bytecode and
redundant chmod were repaired before final qualification. Original339 failures
and the earlier overlapping port4457 tests remain historical, not hidden.

All temporary cache relocations are restored; package/network presets stayed
unchanged. Disposable container compiler-cache assistance is recorded and does
not complete #104. PNPM restored file count/bytes match, but its first unordered
aggregate hash cannot prove byte equality; other2 caches have matching hashes.
Independent finished-proof privacy/integrity review passes. No product release,
deployment, migration, Store submission, spending or consumer adoption occurred.

Actual supported-loader startup (#102-D4), Steam Deck/SteamOS/Flatpak OBS33/
Gamescope/AMD/controller/headset/provider proof remains #86/original ledgers.
Hosted jobs remain billing-unavailable with zero steps; actual dependency
comparison is separately403. Original230 criteria/dependencies remain intact.
Next bounded audit item is settings boundary **#103**, then selected artwork/UI/
docs/#104/#85 preparation under applicable owner direction. Do not silently
start authentication, migration or publication from this record.

## Runtime correctness complete; source stack merged and qualified

Owner-authorized **#96–#100** are implemented through merged **#106/#107**;
the earlier stack **#73 → #74 → #75 → #90 → #92 → #105** is also merged into
actual default `master`. The qualified source is
**9038e23e1a7bfe79c0a5731546f1d3e1a1a74e41**, tree
**47366b98531c97778976fe354ccdf7aa53a9bac6**. Later evidence-only commits do
not change or relabel that qualification. Read the
[criterion-level checkpoint](docs/runtime-correctness-checkpoint.md),
[machine report](docs/evidence/runtime-correctness-9038e23.json) and indexed ZIP.

All six free local ACT jobs pass at that exact source, with verified receipts
and zero open failure groups. Current primary ZIP SHA256
**8833c0a11db6bbc06f75dad931e9810e3513d491e904450774cf3edced766d33**
matches all 33 files assembled by pinned official Decky CLI/default builder and
the repeated workflow ZIP. Actual packaged adapter→Go passes 218 CPython and
240 simulated-frozen checks. Supplemental CLI, pinned Decky transport, old/current
upgrades and six normal-user absent/reused frontend checks pass. Eighteen filtered
native proofs cover real Linux OBS/audio/capture/game/idle fixtures. All three
temporarily relocated caches were restored with file/link hashes matching.

The first complete matrix at **4b3e0bf** failed the unchanged local clip/game
fixture despite five passing jobs. #107 retained the initiating recording lease
and drove guarded capture during the bounded wait; final/deferred Stop now
rechecks ownership. The unchanged fixture then passed, followed by the complete
new-source matrix. Initial Go fixture and outdated packed-harness failures remain
historical evidence. Both ACT attempts record constrained-runner compiler-cache
assistance; they are not unassisted resource-policy proof for #104.

Runtime child closure uses all 20 bounded criteria, focused independent review
and final matrix evidence, not merge state. Bounded Actions repairs #91/#93/#94
also have merged fixes and current checks. Parent #46 and all 230 original
criteria/dependencies remain open/intact. Next proposed audit work is #101/#102
cleanup/recovery, then #103 and existing artwork/UI/docs/#104/#85 preparation.
Do not start those from this record without the applicable owner instruction.

Hosted checks remain billing-unavailable (zero executed steps); actual PR #107
dependency comparison is 403. Actual Steam Deck/SteamOS/Flatpak/OBS 33/Gamescope/
AMD/controller/headset/provider and native other-platform/adoption gates remain
unrun in #86 and the original ledgers. No product release, deployment, migration,
Store submission or spending occurred. OAuth #89 and migration/graph #87/#95 are
separate. Requery live issues/PRs/default state before the next batch.

## Historical local-test integration checkpoint in #107

The unchanged native game/OBS and idle-media fixtures now pass the previously
failed clip path. The parent retains its initiating lease and drives the same
guarded capture helper during the original bounded ten-second wait, using
separate tick connections. Detached observers still acquire their short lease
and yield. Fresh managed/output/recording checks gate each tick and final/deferred
Stop, so ownership loss cannot fall through to unconditional cleanup.

Focused race and independent review pass, including game/idle transition while
holding the lease, detached-observer yield, malformed/stopped output, changed
settings/ownership, cancellation and timer completion. Preserve the original
4b3e0bf five-pass/one-fail matrix as historical evidence. Merge #107 after the
integrated Go/cross-build checks, then build and qualify the new exact merged
revision; no old receipt is promoted. Runtime issues remain open until that
qualification is reconciled. No fixture assertions/timeouts were weakened.

## Historical first qualification: local-test capture lease gap

The seven requested PRs are merged into `master` at
**4b3e0bf88411289178b9e6462bf2ad2fc8da8ce9**. Five local ACT jobs passed, but
the candidate job failed the unchanged native game/OBS fixture: `clip-game`
never selected the game scene during `TestRecording`. Native OBS/audio and
app-scoped capture checks passed before that failure. Do not call this revision
fully qualified or close #96–#100 yet.

The initiating local-test command holds the shared control lease for the full
ten-second clip; the corrected independent observer now properly yields. Repair
this on **fix/local-clip-capture-lease** by reusing capture mutation under the
initiating owner's lease during its bounded wait. Keep that lease rather than
releasing it and risking finalization of a replacement recording. Independent
observers still need their own short lease. Recheck managed ownership/output
before every mutation and cleanup; preserve the unchanged native assertions and
timeouts. Then review, merge the bounded repair and run the complete available
matrix at the new exact merged source. Retain all first-attempt receipts and
resource-assistance details. No release/deploy/migration/spending is authorized.

## Runtime source checkpoint in #106

The five bounded runtime repairs are implemented on `feat/runtime-correctness`
in [#106](https://github.com/szmyty/obsgod/pull/106), with independent cross-review.
Read [the changed contracts](docs/runtime-correctness.md). Review also repaired
initial observer readiness, canonical versus case-insensitive recording flags,
workflow timeout identity and frozen Decky's non-Python `sys.executable`.
The system-Python helper correction also applies to the existing leased
dependency worker without changing its ownership/recovery model.

Focused regression/process tests passed. The first integrated Go race run found
three older status fixtures sharing a response without `outputPaused`; the
fixture now supplies a real boolean and the full race rerun passes. Preserve
that initial failure as superseded evidence. Fresh vet, tooling and frontend
typecheck/tests/build pass; complete Python, primary packaging and the final
exact-merged-source six-job local ACT matrix are still being completed. Do not
call this checkpoint final qualification or close acceptance from this note.

Next: finish premerge checks/primary package, retarget and merge the seven-PR
stack into actual default `master`, then qualify that exact merged source and
publish evidence-only review records. No product release/deploy/migration is
authorized. Remaining audit stages #101–#104 and artwork/UI remain outside this
batch; actual Deck/provider/hosted acceptance stays explicit.

## Runtime correctness #96–#100 authorized; merge the open PR stack

The owner explicitly approved the runtime-correctness stage and requested merging
all open PRs. This supersedes the planning pause for **#96–#100** and the merges;
#101–#104 and the remaining branding/UI work are not part of this implementation
batch. Use the existing checkout on **feat/runtime-correctness**, from
**8b18001a7fac8d82e17e620963c60c64da845db3**. No additional worktree is needed.

Five implementation lanes cover effective microphone policy, capture-observer
ownership/shared leases, strict recording observations, timeout/correlation
connection invalidation and bounded backend/child teardown. Run focused checks
and independent review before source integration; qualify the final exact source.
Do not inherit the earlier 378b46c receipts for these changes.

Live premerge stack is #73 → #74 → #75 → #90 → #92 → #105, then the runtime
checkpoint. Retarget each dependent PR to the actual default `master` only after
its predecessor is merged; merging a stack into its old feature base is not a
default-branch integration. Current branch API says protected=false; active
rulesets and branch rules return empty lists. Detailed protection read is 403;
do not claim that capability succeeded. Existing submitted reviews are empty.
Respect any live gate that appears before merging. User merge authority does not
turn billing-blocked checks, missing device proof or reviews into passing checks.

Inspected workflows have contents:read and snapshot publish/sign disabled; docs
preview retains an artifact and does not deploy. No merge-authorized publication,
deployment, transfer, other-repository change or spending is implied. Keep original
criteria and remaining owner/target/service acceptance open as required, and
requery actual PR/default/issue state after integration.

## Prior proposed audit checkpoint (runtime stage now authorized above)

The owner requested a full audit and proposed issues, explicitly followed by a
sync before executing the audit roadmap. Current work is planning only; do not
start its product fixes, UI/artwork changes or migration before that sync.
Use existing checkout branch **docs/final-audit-roadmap**, based on
**12ef52f9d22a7c1101f8743094325f66e3948270**. Product source is unchanged.

[#84](https://github.com/szmyty/obsgod/issues/84) now links nine bounded proposed
children **#96–#104** with source/fixture evidence and acceptance. Existing
#80/#81 carry selected aurora and UI work; #82/#83 lifecycle/integration and
#84 docs/refactors are refined, not recreated. The source audit has 26 observations
including overlaps, already-planned gaps and optional improvements. It does not
claim 26 independent bugs or that any proposed repair is implemented.

Read [the proposed audit and order](audits/final-audit-2026-11-14.md),
[all findings](docs/evidence/final-audit-20261114.json) and the indexed evidence
ZIP. Reproductions cover mic policy, capture ownership, recording state, SDK
timeouts, loader cancellation, lock identity and retained helper/version flow.
UI probes use HTML component stubs and the actual source 378b46c ZIP whose frontend
matches baseline 12ef52f; physical Deck/controller/keyboard/provider tests stay unrun.

Recommended after sync: #96–#100 runtime/process correctness → #101/#102 cleanup
and recovery → #103 action contracts → existing #80/#81 branding/compact UI and
#84 bounded docs/refactors → #104/#85 primary CI/final exact-source candidate.
These are priorities, not replacement original dependencies. Owner Deck testing
#86 follows when hardware is available; independent software preparation need
not wait for it.

New **#95** is linked from migration #87 and retest #88: after the actual approved
new public repository exists, verify/enable dependency graph, manifest ingestion
and real PR dependency review; distinguish permissions/fork and billing facts.
It does not authorize a migration now or establish the unselected destination.
OAuth remains deferred #89. All 230 original criteria/dependencies and historical
receipts are intact. No product source/UI/artwork change, issue closure, merge,
release/deploy, migration, paid resource or other-repository modification occurred.

## #79 native configuration and Actions repairs qualified at 378b46c

Draft [#92](https://github.com/szmyty/obsgod/pull/92), after #73 → #74 → #75 →
#90, implements private Gaming Mode server/key settings and repairs demonstrated
nonbilling failures #91 (ST1005), #93 (Go/tooling temporary ownership), and #94
(strict ARMv6 Debian metadata expectation). Source is committed and pushed.
Exact qualified source: **378b46cb8c4a9281f9d6890b2e13b223650626d5**. Later
evidence-only docs do not qualify a newer source revision.

All six supported local ACT jobs pass. Seven raw attempts are retained, including
the first candidate ENOSPC failure; the successful same-source retry cleared
only disposable container Go compiler cache after builds/audits, before native
tests. Reporter integrity passes, zero open failure groups; overall partial for
external gates. No optional cache-save warnings occurred at this revision.
The normal-user frontend also passed absent/reused-output postconditions.
All temporary cache paths were restored; package/browser caches, source,
artifacts, module caches and evidence were retained. Only two inactive historical
Go compiler caches were pruned with the pinned tool.

Primary standard ZIP SHA256 **077234a0b917e58a4723d846ed56ff5f8ba23bc4721f344c99889e66a7a719db**
matches repeated workflow ZIPs and all 33 payload files assembled by pinned official
CLI/default builder. Actual packaged Python→Go passed 150 assertions without launch
or broadcasting. Non-root Go race passed 259 top-level tests / 545 pass events with two explicit skips;
application Python 183 passed / one skipped, tooling 85 passed, Node 43 passed; browser and native
OBS/audio/capture/game-transition fixtures passed with 18 filtered JSON proofs.
Read [the checkpoint](docs/decky-configuration-checkpoint.md),
[criterion report](docs/evidence/decky-configuration-378b46c.json) and independently
privacy/integrity-reviewed 72-file public proof ZIP. Its INDEX distinguishes
original receipt hashes and redacted public logs. Source and artifacts remain
local/draft review checkpoints, with no release publication.

Fresh hosted audit: nine failed runs / 15 jobs / zero steps; 14 billing-lock failures and one
expected push dependency-review skip. Actual PR #92 dependency comparison 403 remains
unavailable. Actual Deck/SteamOS/Flatpak/OBS 33/Gamescope/AMD/Steam keyboard/controller/
headset/Kick viewer and native other-platform/review/hosted gates remain open.
No merge, issue closure, release, deployment, migration or spending occurred.
OAuth remains deferred in #89. Next roadmap implementation is #80/#81 selected aurora
exports/UI adoption, then #82–#85 and owner testing #86 before migration #87/#88.

## Native destination implementation and original Actions audit (history)

The owner requested fixing reproducible nonbilling Actions failures and manual
Kick key setup directly in Gaming Mode; OAuth remains deferred #89. Work uses
the existing checkout/branch **feat/decky-native-configuration**, stacked after
#73 → #74 → #75 → #90 in draft [#92](https://github.com/szmyty/obsgod/pull/92).
No merge, release, deployment, migration or spending is part of this checkpoint.

The [native form and contract](docs/native-configuration.md) reuse Go Configure
under the existing shared control lock. Sparse patches preserve advanced state;
same-destination blank keys retain their binding, changed destinations/accounts
require a replacement, and secrets are never read back. Offline saving needs
positively closed/idle managed OBS. Closing an idle instance and changing its
separate control password are explicit confirmations. Saving/testing never
launches OBS or broadcasts. Python serializes actions, coalesces reads and invalidates stale observations
and clears private payloads; UI readiness expires and private drafts clear on
save, destination changes, modal dismissal or removal. The candidate workflow
now includes dependency-setup and native-configuration packaged browser checks.

The live audit at 2026-11-14T20:08:03Z found 42 failed runs, 69 jobs and zero executed
steps across default/master and then-current PR73/74/75/90 heads: 64 billing-lock
annotations and 5 expected push-only dependency-review skips. No executed current
hosted nonbilling failure was found. A reproducible local staticcheck ST1005 was
tracked as [#91](https://github.com/szmyty/obsgod/issues/91) and repaired in
56677e1 by lowercasing the storage-map error lead-in. Dependency comparison 403
remains a separate service/fork capability gate. Do not disable it or call local
ACT evidence hosted acceptance.

Actual ACT at clean source **4c5af7f7192079fb005c8b8ae56eaa0dd51bb525**
passed lint, then build and coverage failed because Go fixtures ran as root with
TMPDIR under UID1000-owned workspace ancestors. [#93](https://github.com/szmyty/obsgod/issues/93)
retains those failures and the reproduction: identical root Go tests fail under
the foreign-owned shared temp and pass under runner-owned `/tmp`. The bounded
repair selects runner.temp only for Go test steps in build/coverage/candidate;
production guards, test cases and shared native-builder temporary paths stay
intact. The remaining three jobs at that old source were unrun after the batch
was stopped. Its official CLI assembly also failed during a separate rootfs
space exhaustion; no candidate or pass was claimed. Inactive host Go/PNPM cache
contents were preserved on the separate temporary filesystem, with logical cache
paths retained. The corrected clean source needs a fresh complete six-job run.

At **5935803b00fc62579e759c52b68fce24533c1dcb**, all six ACT jobs executed:
lint/build/coverage/docs passed. Snapshot failed the strict NFPM audit because
its ARMv6 Debian expectation was armel while pinned NFPM 2.49.0 emits armhf;
[#94](https://github.com/szmyty/obsgod/issues/94) records the exact 15-package
comparison, upstream rule and reviewed one-label correction. Candidate passed
Go/race/vet/vulnerability and application Python checks, then failed two tooling
fixtures for the same root/foreign-TMPDIR cause. #93's runner-local temp scope
now also covers that test-only step; nested package/native builders retain the
shared daemon-visible path. No guard weakening or test skip was introduced.
New source must run the complete matrix again; 5935803's four passes do not qualify it.
Some passed jobs warned that optional Go cache persistence ran out of disk space;
their job outcomes are retained, and successful cache persistence is not claimed.

The standard 5935803 package itself built successfully and matched all 33 payload files
under pinned official CLI/default-builder assembly with networking disabled.
Its actual Python adapter→bundled Go configuration integration passed 150 assertions
without an OBS/Flatpak/desktop launch or broadcast. Native-config/dependency/panel
packaged browsers passed, as did non-root full Go race: 259 top-level passes / 545 pass events with two
explicit skips. These remain revision 5935803 receipts, not a new-source release.

Focused Go/native, Python, Node/typecheck and simulated packaged browser checks
passed during implementation, with independent review. These dirty-tree/diagnostic
checks do not qualify a clean candidate. The next clean source checkpoint is
to run all six supported nonpublishing ACT jobs, build the standard Decky ZIP,
and retain exact source/artifact/matrix evidence. Actual Deck/controller/provider
proof, required hosted CI/reviews and later #80–#88 work remain explicit gates.

## #76–#78 source implemented; qualified batch7e539ca in draft #90

User-requested package/storage/dependency setup is implemented in draft
[#90](https://github.com/szmyty/obsgod/pull/90), after #73 → #74 → #75.
Exact source **7e539ca8bcf237e3da1d0c42c5045ea44d638973** produced two identical
33-file ZIPs, SHA256 **80b956ea208b465626640a8ad432185aca5455192c367bd50e38d6608f90830c**.
[The checkpoint](docs/decky-foundation-checkpoint.md),
[criterion/matrix report](docs/evidence/decky-foundation-7e539ca.json) and raw
24-file evidence ZIP retain exact commands, revisions, tool/platform/outcomes.
Later documentation does not relabel this artifact or qualify newer code.

At that clean source: Go race/count1 passed156top/268events (one root-only skip),
vet passed; Python171discovered/170passed/one root-wrapper skip; Node37;
packaging9/audit16/frontend-ownership6; four actual-ZIP browsers passed including
six setup scenarios. Official CLI/default pinned builder matched all33 files.
Actual unpacked Go/version/status/authenticated setup and Python-map→packaged-Go
checks passed, with no OBS/Flatpak command or broadcast during setup/status.

Review reproduced writable-ancestor directory replacement/split control locks;
the bounded Python/Go/job/build repair and held-lock/sticky regressions pass.
Primary setup now respects original XDG data/cache roots and retains one legacy
credential/state/control store plus Decky-owned private metadata/jobs/logs.
The untouched SDK source archive works with the default official builder.

No merge/issue closure/release/deploy/migration/spending. #76–#78 stay open for
review/recorded limits. Actual Deck/Flathub/session/controller/audio/viewer proof
is unrun; hosted candidate job failed with zero steps and a billing-lock
annotation. Full campaign ACT/native/platform/security matrix remains #85.
Next implementation is #79 private in-panel configuration, #80 selected aurora
exports and #81 UI adoption, then the remaining roadmap. Owner testing remains
#86 after a final test-ready build; actual migration/new install are #87/#88.

## Executing #76–#78: Decky package, storage compatibility and setup jobs

The owner explicitly requested implementation of #76, #77 and #78. Work uses
the existing isolated checkout on **feat/decky-native-foundation**, based on
planning commit **6c01b93f18b471d7168ef192ca5ab8bae185e381**. The earlier draft
stack #73 → #74 → #75 stays intact; the next draft is based on #75's branch.

Chosen compatibility approach: retain one canonical XDG settings/secrets and
managed state/control-lock store for current CLI/Desktop users. Decky's injected
settings directory holds a versioned storage map/receipt, runtime-data holds
plugin-owned persistent setup jobs, and logs holds plugin-owned logs. No secret
copy, Flatpak config relocation or recording move. Preserve the actual player
context and original XDG_DATA_HOME for user Flatpaks.

Draft [#90](https://github.com/szmyty/obsgod/pull/90) is based on #75 and preserves
the early frontend checkpoint d8412f0. The source now integrates the backend
jobs/storage map, shared-lock preflight, guarded standard package builder,
optional self-contained loopback setup, native Install/Later UI and regressions.
Official CLI assembly exposed an SDK-source exclusion; a deterministic preferred
source archive preserves the LGPL source with the default builder. Go Flatpak
launches now retain the original XDG data/cache roots.

The source is being frozen for a clean actual package build, repeated-byte and
unpacked/browser checks. Focused tests have passed during implementation; exact
final batch evidence follows after these checks. This is not final campaign
qualification or actual Steam Deck acceptance. No issue is closed and no product
release, migration or deployment occurs. #79 key-entry UI and #80/#81 selected
branding adoption remain subsequent implementation, not part of this batch.

Initial clean source480c477 produced two identical canonical ZIPs and passed
pinned official CLI assembly, unpacked actual-Go/browser-setup smoke and the
packaged panel checks. Independent review then reproduced unsafe writable
ancestors for build output and managed state/control locks. The bounded repair
rejects those ancestors in Python/Go/job/build paths, including legacy Go Lock
without a map, with sticky-positive and held-lock rename/recreate regressions.
Final corrected-source builds/checks must supersede480's artifact evidence.

## Active roadmap: implementation first, current Deck tests, then migration

The owner locked **01 / aurora** and retained earlier artwork as concepts. The
exact creative selection/reference hashes are in
[selection.json](.identity/candidates/concepts/selection.json); source/exports,
rights, live UI and target rendering are not thereby implemented or qualified.
Future repository name is **deckystream**, with final owner still unresolved.

Live parent #46 now links native sub-issues **#76–#88**. Implementation milestone
4 has **#76–#85**: package, safe Decky state paths, recoverable dependency jobs,
private manual-key setup, selected brand assets, native UI, lifecycle/cleanup,
integration regressions, bounded audit and final local qualification/test build.
Milestone 5 has **#86–#88**: owner current-install Deck test/fix loop; prepare then
gate the actual migration; retest the official new install and prepare v1 facts.
[The detailed plan](docs/implementation-roadmap.md) and
[machine-readable issue snapshot](docs/evidence/implementation-roadmap.json)
retain inputs, acceptance, original-scope links and exact live baseline.

All 230 original criteria/dependencies and #46's original details tail are
preserved exactly; older checkpoint narrative is collapsed as historical.
No issue is closed or marked implemented by planning. Drafts remain #73 → #74
→ #75; default master remains da89b9d. Latest release is unchanged prerelease
v0.1.0-deck.4-updater.1. Protection detail read is 403; no settings change.

**#89** is separate OAuth/phone/QR research from preserved #14/#40, not a main
implementation dependency. [Official-source findings](docs/authentication-options.md):
Twitch documents public-client device authorization and user stream-key access;
Kick documents PKCE plus a confidential client secret and key scopes/schema.
Resolve its native-client/callback constraints before promising the same flow.
OBS still needs ingest credentials internally. All real OAuth/phone/account
tests are unrun; discuss the auth design before implementation. Companion stays
deferred; #51 research is not reopened or turned into monetization/Store work.

This checkpoint creates the roadmap and records branding selection/research;
the new package/setup/UI code and final full matrix are not yet executed. Next
execution uses the existing isolated checkout, preserves injected auth/network
presets and pinned tools, and pushes reviewable checkpoints. No release, deploy,
repository creation/retirement or spending occurred. This current sequence
supersedes older notes that say to wait for a new-logo direction.

## Intended repository name: deckystream

On 2026-11-14 the owner preferred **deckystream** as the future repository name,
matching the lowercase/single-word direction. This supersedes earlier planned
`decky-stream` spellings in historical notes. Exact destination owner remains
unresolved. Current `szmyty/obsgod`, remotes, release trust, installed IDs, private
paths and published artifacts are unchanged. Naming is preparation; migration
still follows implementation, checks and manual Deck testing. Older synthetic
destination fixtures do not qualify the newly selected slug or actual publisher.

## Branding discussion: orbital-stream and gradient primary icon

The owner confirmed the proposed normal Decky ZIP plus plugin-managed first-run
OBS/GStreamer setup, with explicit consent, graceful decline, background progress,
cancellation and retry. This remains upcoming implementation; current plugin
onboarding has not changed or been qualified in Gaming Mode. Dependency setup
is separate from Decky's plugin installation. OBS/extension come from Flathub;
our release is a Decky plugin package. Keep manual Deck test cases before
migration and repeat installation checks at the actual new destination.

The immediate request is creative design before roadmap execution. A new
[orbital-stream board](.identity/candidates/concepts/orbital-stream-board.png)
was generated from the requested Mindgarden/Identity aesthetic and saved with
the complete prompt, image digest and draft status. The owner likes this direction
and requested the banner's aqua/violet glow and depth for the primary icon;
[the square preview](.identity/candidates/concepts/orbital-stream-gradient-icon.png)
and its full reference/prompt record are saved. This new variant awaits feedback.
The owner then asked to see alternatives. The saved
[four-color comparison](.identity/candidates/concepts/orbital-stream-color-alternatives.png)
shows 01 aurora (original aqua/violet), 02 afterglow (purple/pink), 03 solar
(coral/gold) and 04 pearl (iridescent pale tones), with full prompt/reference
metadata. No final palette choice is inferred from the request to compare them.
Decky's JSX icon slot supports color/gradients; monochrome was a proposed
legibility choice, not an API restriction. Actual small-size/on-Deck rendering
remains unqualified, and observed stream-state cues must survive any icon change.
Earlier art, selected masters, generated kit and runtime visuals are unchanged.
Next is owner visual feedback, then the final roadmap discussion
(including any key-configuration questions), branding exports and implementation.
No final full matrix, migration, publication, issue closure or device acceptance
is claimed by this image-only checkpoint.

## Current question: align the Steam Deck product with normal Decky conventions

The owner narrowed the shipping focus to Steam Deck/SteamOS and asked whether
the plugin follows Decky's recommended approach before specifying new batches.
[The live-source comparison](docs/decky-conventions-review.md) confirms the modern
SDK/Python/native-bin runtime already matches the template. The main differences
are nested/custom build, mandatory paired Desktop onboarding/updater and shared
XDG state rather than Decky-only storage. Proposed next batch is a conventional
plugin package with complete first-run setup, Decky-managed replacement and a
safe storage compatibility plan. This is a recommendation, not an implemented
rewrite or approval of every proposed change. Retain generic CLI capability as
optional; it is not the primary Steam Deck installation method.

Current official template90d0780/wiki ec9d4cf/loader ffd103b9/preset5e861bc pins
and source hashes are saved. Actual Syncthing example confirms Flatpak dependency
plus bundled native helper is normal. No runtime change, final matrix, Store
submission, migration or external contact occurred. Wait for the owner's next
batches/logo direction; any selected source-changing cleanup precedes final
qualification. Engineering source4ac and previous receipts remain unchanged.

## Engineering pass complete; next owner step is the new logo

Draft #75 now contains the nondeferred engineering, after #73/#74. Exact source
is4ac20bfd9e8b2fe17ab1942eeedd3fc78e38b6fb; [checkpoint](docs/pre-migration-completion.md)
and [criterion/evidence map](docs/evidence/pre-migration-engineering.json).
All39legacy operations share the typed API/application path with original ACK
semantics and prompt owned-socket cancellation. Go regressions at59665ad (Go
inputs unchanged at4ac) passed222top-level/456events across6affected packages
with race/count1 and one optional existing-OBS skip; vet passed7packages.

At clean4ac, actual Debian/Fedora/Alpine Linuxamd64 package lifecycle, filehash,
UID65534 offlineCLI and data preservation checks passed. Three packages plus tar
and8audit documents reproduced identically. Genuine A→B upward upgrade and A→C
replacement/downgrade have separate exact-source receipts. RPM scripts/triggers,
document modes, private staging and container fixture permissions were repaired;
the existing root-owned catalog and original artifacts remained unchanged.

Focused checks also passed64migration/release/install/update/uninstall cases,
10NFPM/12generic/10history/11brand tests and actual offline image decoding.
Publicly re-downloaded PNG-only ZIP is14ordinaryPNGs plus START-HERE; gallery is
self-contained HTML. Current art is unchanged/proposed. New history tooling
preserves all230criteria/dependencies and captures public tracker history without
rewriting the frozen snapshot or performing retirement. Raw58-member evidence
ZIP and compact package receipt are tracked beside the checkpoint.

Next phase is the owner's new logo ideas, then final full qualification, bug
repairs/retests and migration. The final full matrix is deliberately UNRUN now;
old469 runtime receipts do not qualify this source. Companion/OAuth are deferred.
Actual Deck/native/viewer/adoption, real destination/brand/rights/publisher and
publication facts remain explicit. No issue was closed, source merged, repository
created/archived/transferred, release/site deployed or money spent. Drafts remain
in review order #73 → #74 → #75; use live state before the next phase.

## Implementation-phase authorization (preserved)

The owner reported that some brand-kit files could not be opened and authorized
finishing all remaining feasible engineering. Current phase order is explicit:
repair ordinary-viewer asset delivery; complete nondeferred source work with
focused checks; receive the owner's new logo ideas; run the final full matrix on
the resulting candidate; fix bugs/retest; then perform the agreed migration.
The final full qualification is intentionally **not run before the new logo**.
This latest sequencing supersedes older instructions to run it immediately.

Companion/StreamGod and provider OAuth are deferred by the owner. Existing
creator/RTMP behavior stays compatible; deferral is not implementation acceptance.
Read-only review of all 230 original criteria found four current engineering
lanes: legacy CLI/shared application integration (9.AC2), NFPM package audit and
container lifecycle checks (12.AC4/5/7/8), installer identity/migration rehearsal
(36.AC1/2/3), and usable brand-kit delivery (38.AC3/4). Final logo/rights adoption,
actual device/native/viewer/adoption evidence and publication facts remain distinct.

Continue in the existing checkout on `feat/pre-migration-completion`, based on
presentation head08d5965. Memorial #73 and presentation #74 remain preceding
drafts. Keep scoped source commits and draft checkpoints pushed; no repository
creation/retirement, product release, deployment or spending occurs in this phase.
Use pinned Go1.27.4 at `.obsgod-tools/toolchains/go1.27.4/go/bin/go` outside this
checkout: `/usr/bin/go` here is a board game. Docker28.4, Node24.19 and Python3.12
are available. Full runtime qualification remains historical at4699235 until the
later approved final-test phase; focused results must identify their own source.

## Decky Stream draft artwork, README and pre-migration inventory

The owner requested a fresh look at Identity specifications, asset generation
in chat, the Hygiene/Holon README baseline and matching funding. Identity live
main remains cfb6c29bd02589a47fc48050ab02e7e0da359719; immutable specification
sources and hashes are recorded in `.identity/references/specification-review.json`.
The generated mint-signal board and its actual prompt/method/digest are retained
under `.identity/candidates/concepts/`; editable SVG masters were separately
authored. Empty approval/provenance arrays and proposed asset status remain.

The draft exporter now prepares 33 full-kit files and a 28-file tracked
`branding/repository/` projection: dark/light 1600×600 README headers, mark
variants, monochrome Decky icon, avatars, favicon sizes, wordmark, palette and
1280×640 GitHub PNG (53,297 bytes). README follows pinned Hygiene/Holon guidance
with light/dark PNG artwork and text fallback. Funding's five active handles
already match org defaults; Patreon stays commented under the recorded broken
destination exception. Support data is unchanged.

[The pre-migration plan](docs/pre-migration-plan.md) separates doable legacy
transport/NFPM/migration-rehearsal/candidate/export work from actual device,
native-platform, viewer/adoption and owner/publication facts. Companion/OAuth
expansion does not become a new prerequisite for creating the fresh repository.
Installed plugin/runtime identities, updater trust and native visuals are
unchanged. Product qualification remains at4699235; no new runtime matrix, release,
deployment, repository creation/transfer/archival, paid resource or other-repo
write occurred. Nine draft-export tests, source-contract validation, reproducible
raster exports/drift, source/output hashes, dimensions/byte cap, SVG checks,
relative links and generated metadata checks passed; exact evidence follows in
the [presentation review record](branding/evidence/presentation-review.json).
Exact presentation source is f3d2413b5f72aa858992996839aa8569ac5db331; later
evidence notes do not relabel it. Draft PR #74 stacks on memorial PR #73: review
and merge #73 before #74. The full 33-file repeat was byte-identical; ZIP digest
fd92a99f1a0a09182a0f519a39f40847b378621b5a002a6c918f6236d68d7f36.

## Portable history before a possible fresh Decky Stream repository

The owner prefers a fresh repository and requested a practical `MEMORIAL.md`
history for future agents, rather than preserving Git/GitHub history for its own
sake. Added [the short history](MEMORIAL.md), its new-agent pointer in AGENTS.md,
and [a portable tracker snapshot](docs/history/obsgod-github.json). Read-only
capture on 2026-11-14 UTC covers all 40 issues/32 PRs, 41 conversation comments,
three submitted reviews and zero inline comments at default da89b9d. Only #46
was open; no PR was open. The export predates this documentation PR and is not a
final retirement snapshot. Its scope/exclusions and refresh-at-retirement plan
are recorded in the memorial.

Documentation checks passed: all 72 tracker IDs and 116 captured body hashes,
41-comment completeness, 62 relative links, source revisions, remote immutable
artifact ref, credential-pattern scan and diff whitespace. Independent read-only
review found no remaining correction. Product checks were not rerun for this
documentation-only change; existing qualification stays revision-bound.

No runtime changes or new runtime qualification are part of this documentation.
Exact qualified source4699235 and immutable artifact eb92598f remain unchanged.
`egohygiene/decky-stream` is the working fresh-repository destination discussed;
final creation/retirement and branding decisions/actions are not performed here.
Private `szmyty/archive` exists, but a backup there alone cannot preserve public
install/artifact URLs. Prepare a tested installer/updater/settings transition,
carry every unfinished criterion into the new tracker, retain upstream notices,
and refresh the memorial/export at actual retirement. Read earlier sections as
historical checkpoints; use live state before continuing implementation.

## Qualified follow-up: source469, verified review checkpoint and remaining #46

The owner instructed “okay merge everything and push forward with those few”.
PR #67 merged normally at575e4e278599a94bbeeef334531cc60fb6714115. The prepared
follow-up source is exact `4699235e9e925b76ca492d5a00a375ed37fb338e`, tree
`3c09ea82d85ddcdf47c347afa44961f7b1b6956e` (401 files). Full available local
qualification passed at that clean source; later evidence documents do not relabel
it. [Audit and criterion evidence](audits/qualification-4699235.md).

Both six-job ACT sequences plus real-reference PR static passed. Both immediate
normal-host typecheck/test/build sets passed UID1000 with all frontend output
owner-writable (first absent, then reused). Primary14, generic20 archives and42
sidecars matched across independent runs. Fresh Go race/count1 passed 219 top-level
and 399 events with one optional skip; Python 127/tooling 50/Node 30, browser/native,
legacy4/dynamic6/current transport/updater, browser upgrades4/6 and container
Fish 3.6.0 passed. Host Fish remains unavailable. Provider raw exit 1/unavailable,
API 403 and hosted billing lock (9 runs/15 jobs/0 steps) remain explicit; actual
Deck/OBS 33/Flatpak/Gamescope/AMD/headset/controller/provider/adoption and required
independent creative/rights/publisher acceptance are not established.

Source PRs #69→#70→#71 merged normally at62467b5ffe21388855f1ea3d9296aa007f01300e,
6c16bdff6e023599f3eb2b58c88e07987dc309c2 and27c92ede4d17614c3281b52ddaae489b2a0eebc1.
PR #72 holds the research and final evidence follow-up; actual final merge/state
is recorded by GitHub. All five #68 acceptance criteria now have fresh evidence;
all 14 current #51 research criteria have deliverables. Research recommends free
core/verified voluntary support and defers paid/Store work, without claiming
owner adoption, revenue, recipient readiness or Store eligibility. Original 230
criteria/dependencies remain in #46. Full legacy shared-transport migration,
NFPM/native support and companion/ecosystem work are not silently completed.

New immutable manual review artifact `eb92598f3a4a0dc426749c290bacfe7251452909`
on artifacts/qualification-4699235-review has 19 independently downloaded and
verified files, including full 401-file source. Runtime SHA256
`b4222fb703aa198a7ea200721afbc06dcb86dec56e8c1bebd77f5bb614aad53d`.
[Desktop install and owner checkpoint](docs/current-review-install.md). The older
1a/d0a artifact remains unchanged. Preserve both artifact branches/commits and
reachable qualified source when deleting merged source branches. Never merge an
orphan artifact tree. No GitHub product release, site deployment, environment
snapshot, other-repository write or spending occurred.

The historical root-owned ignored frontend backup steamdeck/decky/.local-ci
retains exact mode/owner/content hashes. Only an inventoried regenerable host Go
cache and already-identical external generic evidence copies were optimized for
space; source, active inputs and storage guards stayed unchanged. All execution
holds are released. Use the existing checkout; refresh live default/PR/issues
before new work. Next owner action is exact-candidate real Deck versions and an
audible moving clip, then device/viewer/preservation acceptance. Billing/graph
access and organization/creative/rights/companion/publication decisions stay
separate. No broad new approval or hidden prerequisite is invented.

## Completed audit: org-aligned ACT setup, reports and issue triage

The owner requested following the egohygiene `.actrc` pattern, running ACT in the
local workspace, collecting reports and turning new findings into issues for
sync-up. This authorizes scoped new issue creation for demonstrated findings;
known requirements already in #46 must not be duplicated. #51 remains separate.

Start from clean merged master9d29a977 in the existing checkout. Read-only live
org references are pinned in [local CI documentation](docs/local-ci.md):
egohygiene/egohygiene060d15a790 and Reflector23f164cf89. Reflector now uses the same
Ubuntu24 digest and JSON output; older local graph/Node16 examples are stale.
Preserve the qualified runner/tool pins and existing host CA/proxy/socket/cache/
artifact/native-fixture handling. Add structured logs and a bounded report command,
then commit/freeze source before running serial workflow audit sequences.

Reports must retain exact source/commands/configuration/client/image/workflow/
log hashes, raw passed/failed outcomes and explicit skipped/unavailable/unrun
matrix portions. Older1a candidate receipts remain historical for their exact
bytes. Locally generated workflow packages do not replace the immutable published
review-download checkpoint or authorize a release. No other-repo write, spending,
deployment, Store research/contact or automatic publication is authorized.

Draft [PR #67](https://github.com/szmyty/obsgod/pull/67) contains the setup and
report tooling. Exact clean source `cf12abe6c620dcbea3b806d1aa63a4715adea26a`, tree
`d24d5435af64400da8bb665714b908cbbe638f7c`, passed both six-job local sequences and
PR static checks: 13 completed passes. The actual provider probe remains raw
failed/exit1 and classified unavailable; comparison API 403. Fresh hosted evidence
records nine runs/15 jobs/zero steps and account billing-lock annotations.
[Audit/report/evidence](audits/local-act-2026-11-13.md) records exact commands,
hashes, native/browser limits and interrupted attempts. A cloud-interrupted
candidate receipt stays unfinalized; its successful retry and full independent
repeat qualify only cf12. All14 product/audit hashes matched. Later documentation
does not relabel that source or replace the immutable public 1a/d0a candidate.

The fresh-output ACT→normal-user frontend rebuild failed with EACCES. New scoped
[#68](https://github.com/szmyty/obsgod/issues/68) contains reproduction and
acceptance; known #46 gates were not duplicated and #51 was untouched. The
root-owned ignored output was preserved by same-parent rename to the previously
absent `steamdeck/decky/.local-ci`; normal UID1000 rebuild then passed without
sudo/chown/chmod, source and all14 root candidate hashes unchanged. An earlier
cross-parent preservation rename failed without changes. This is a recorded
workaround, not an ownership fix. Fresh uncached Go race/count1 passed213 top-level
tests/386 pass events with one optional skip. Source/tool setup is saved, applied
and exercised; no environment snapshot, product release or deployment was
published. Keep PR #67 draft for owner sync. Next bounded repair is #68, followed
by real target/provider/review acceptance already in #46. Earlier entries follow.

## Owner-approved merges and issue consolidation completed

On 2026-11-13 the owner instructed “Ok merge them !” after the candidate/evidence
and known gates were disclosed. PRs #58 → #59 → #60 → #62 → #63 → #64 → #65
merged through ordinary APIs with expected-head checks. Feature merge source
`a8b19b3f20d5cf358b6250e120b74b3e63848803` has exact reviewed tree `261aa3f8406d4afed0c68aeada1aecd0a425130c`
from b7013a64; no protection change or bypass was used. This later follow-up is
documentation/evidence only, not a newly qualified runtime build.

Fresh merged-source Go race/count1 (213 top-level/386 events, one optional test
skip), vet/staticcheck/gofmt/vulnerability scan, Python 127, tooling 23, Node 30,
typecheck/build/audit, generated files and site 11/reproducibility passed. The
ignored root-owned frontend output was preserved and rebuilt as UID1000;
source and root dist stayed unchanged. Hosted CI has 5 runs/0 steps and the actual
billing-lock annotation. [Merge evidence](docs/evidence/completion-merge.json).

All 230 original criteria/dependencies are retained in open
[#46](https://github.com/szmyty/obsgod/issues/46). The 34 transferred issues were
closed as not_planned/superseded, not as accepted. Open
[#51](https://github.com/szmyty/obsgod/issues/51) remains unchanged independent
research. No open source PR remained after feature merges. Seven merged source
branches were removed normally; the three artifact branches were preserved.
All 47 candidate 9 public files and internal inventories were reverified after
cleanup. Source 1a482808 remains reachable from default history; candidate bytes,
full qualification and immutable artifact d0a4973f are unchanged and are not
relabeled as the merge SHA. [Install](docs/candidate-9-install.md).

Actual target/provider/adoption, required hosted/independent review and broader
API/companion/provider/generic distribution work remain in #46. Source merge does
not approve proposed ADRs, brand rights/creative decisions or publication. No
release/deployment/Store submission/other-repo change/spending occurred. Default
is still master; requested main rename remains an owner UI action after 403.
Earlier sections below are historical checkpoints, not current open-PR state.

## Completion candidate 9 qualified; owner review and target gates remain

Exact packaged source `1a482808a8281c8bce092cea057df758836b34e9`, tree `fba5cfaed616313e2a6b679a55ff234d21a21538`,
passed both complete local act sequences and the fresh standalone matrix.
Seven drafts remain open in order **#58 → #59 → #60 → #62 → #63 → #64 → #65**.
No merge or issue closure occurred. This is a later docs-only evidence follow-up;
the packaged source remains the revision above, not the evidence commit HEAD.

[Owner packet](docs/completion-review.md), [install command](docs/candidate-9-install.md),
[qualification](docs/evidence/completion-qualification.json),
[230 original criteria](docs/evidence/completion-criteria.json),
[dated audit](audits/audit-2026-11-13.md),
[public-byte proof](docs/evidence/completion-public-download.json) and
[proposed final-boss consolidation](docs/finalboss-plan.md) are current.
Artifact checkpoint `d0a4973f9b1835471e99b046d2d4313b042f9ae2` on
`artifacts/completion-deck9-review` contains47 verified public files and full
350-file source. Runtime SHA256 `879ad44ebb28fb695877c071d9708959a7afc39b7b2b9032421f117a267bf803`.
Never merge artifact trees; retain reachable exact source/artifact refs/URLs when
source branches are eventually cleaned, then verify downloads again.

Passed:213 Go top-level/386 pass events with race/count1,127 Python,23 tooling,
30 Node;12 CLI checks plus container Fish; formatting/vet/staticcheck and zero
reported Go/npm findings;6 compile targets;20 generic snapshot targets compiled;
13 local jobs including two full six-job sequences and PR static;58.1% coverage;
14/14 product/audit files identical across complete runs; two full native OBS30
suites, actual-package browsers, legacy4/6 transport and browser upgrades; pinned
Identity source/draft brand/site determinism and45 host viewport cases. One opt-in
existing-OBS test skipped; host Fish/file navigation unavailable but container
Fish and ACT file-offline cases passed. Exact commands/platforms/limits are linked.

Actual Deck/OBS 33/Flatpak/Gamescope/AMD/controller/headset/provider/adoption remain
unrun. Hosted CI ran zero steps due to the account billing lock; provider
Dependency graph review is unsupported/API 403. Human reviews and applicable
rights/publisher/publication actions remain. Master→main rename requires owner
GitHub UI after actual403. Broader9/13/14 and generic distribution implementation
remainders remain explicit. No release/deployment/Store submission/transfer,
other-repo write, wallet activation or spending. #51 is unchanged research.

After review/merges, consolidate intact remaining criteria/dependencies into #46
and retain #51; administrative supersession is not acceptance. Refresh live
issues/PRs/releases/default/protections before that step. Older progress below
is historical and does not supersede this completed local qualification record.

## Active: finish independent product work; keep #51 research separate

On 2026-11-13 the owner authorized working through **every open issue except
#51**, including partial implementation/preparation wherever owner or external
facts remain. #51 has separately been rescoped into monetization and Decky Store
research journeys; do not perform those journeys during this implementation
campaign. This supersedes the older five-feature-only scope below.

Start from clean draft-stack head `250b29b437c14429a3049f3f0206bd6f16e0253d`;
default `master` remains `ed7d100d356ce803d2cb1c1afef3836759deef10` and drafts
#58 -> #59 -> #60 remain open. Use the existing shared isolated checkout without
additional worktrees. Keep early/meaningful draft checkpoints pushed.

The owner selected intended slug **decky-stream** and wants practical Identity
framework bootstrapping, not strict adoption of an evolving standards library.
Prepare branding/rename/migration source; final creative, organization/domain,
publisher and real target evidence remain owner inputs. Preserve installed
`obsgod`/`OBSGod` compatibility and current update trust until the approved
transition is actually qualified. No other-repository write, release, deployment,
paid resource or payment is authorized by this implementation request.

Read [the completion ledger](docs/completion-campaign.md). Work includes live
stream-only microphone controls, truthful device/LCD-jack observation, useful
API/CLI/creator contracts, practical architecture/governance, supply-chain/CI
preparation and local act execution under newly discovered #61. Real device,
provider, CI billing, owner reviews and publication facts cannot be invented.

After review/merges, consolidate all remaining criteria into **one final-boss
issue plus #51**. Preserve each original acceptance criterion, dependency,
evidence and pending owner action; close superseded tickets as consolidated,
without presenting unrun acceptance as passed. Prepare this mapping now; do not
close the pre-merge issue graph prematurely. Candidate8 remains immutable at
its recorded exact source. New source requires fresh candidate 9 qualification.


## Final upgrade fixture checkpoint

At `e32e8a05f2613702e0e513cd59f25d504e89c1d7`, both complete local act
sequences passed lint/build/coverage/snapshot/docs/candidate, plus PR static
checks. The actual dependency-review action is unavailable for this repository;
its comparison API returned403. Hosted jobs executed zero steps. These remain
explicit provider/owner gates, separate from local passes.

Additional legacy transport qualification found that its staged-network fixture
intercepted only `urlopen`, while the hardened production updater uses a custom
opener. The fixture now maps both entry points to the same exact staged URL
inventory and rejects unmapped requests. Production redirects/trust and version
selection are unchanged. Exploratory preflights passed legacy4→9 installation,
dynamic updater6, legacy6→9 installation and both browser upgrade paths. Their
logs explicitly record dirty fixture provenance, not final qualification.

Freeze this checkpoint, rerun both complete local act sequences and the fresh
standalone matrix at its exact clean revision, then create the immutable review
packet. Preserve earlier receipts as historical. No release, deployment, merge,
issue closure, default-branch rename or research51 work has occurred.

## Privacy-state reconciliation and short browser paths

The e34892e candidate preflight passed pinned setup, managed APT trust for all
configured repositories, Go checks,127 real nonroot Python fixtures,22 script
tests, frontend/security checks and two reproducible runtime/updater/audit
builds. Chromium then rejected an overlong Unix socket path. The test helper now
uses short private `/tmp/ogt-*` HOME/TMPDIR paths; the daemon-visible build temp
path and persistent evidence remain separate. A real socket-bind regression and
23 script tests pass. Earlier partial artifacts/results are retained.

Two demonstrated microphone-state gaps are repaired in the same checkpoint:
profile/reset copy now describes the initial microphone default and explicitly
preserves saved live audio preferences; browser cases verify actual unknown
state while OBS is closed and fresh observation after reopening. Main Status
invalidates cached mixer/input/meter/talking claims until its existing managed
connection/runtime/output checks succeed. Saved preferences/cache/settings/
credentials remain unchanged and no extra queries are added. Three connection
integration cases and focused race checks pass;30 Node tests and focused UI
browsers pass. The CLI reference reflects the same microphone precedence.

Source is ready for another clean candidate preflight through all browser/native
stages, followed by both full localCI sequences and final standalone matrix.
These diagnostic results qualify only their recorded attempts, not a later SHA.

## CI user-fixture identity and APT trust repair

At `218e26bfb5f31fb64e5327e9a82082fde4f25f47`, the snapshot job passed all
20 cross-build targets, unique archives and 15 Linux packages without publishing
or signing. The candidate passed pinned npm/browser setup and Go race/static/
vulnerability checks. Its Python installation tests then correctly refused the
act runner's UID0. Production root guards remain enabled: a new test-only helper
drops actual UID/GID/groups and uses private test HOME/TMPDIR. All installer and
browser fixtures run through it with a readable shared browser cache and owned
external evidence. Real Docker root→UID1000 diagnostics passed all127 existing
Python tests, and22 helper/audit tests passed. No source tree permissions change.

A read-only ephemeral APT CaInfo snippet uses the existing combined CA for HTTPS
indices while preserving package repositories, proxy settings and TLS. Earlier
218 results and warning/failure evidence are retained. Run the clean candidate
preflight through all package/browser/native stages, then both complete final
localCI sequences and the standalone matrix at the final exact source.

## Snapshot/npm integration repair; default-branch administration unavailable

Lookahead at `548ae195b1ae087370a06da8c9de23c3a0acc6f3` passed the docs job
(9pages/11tests/local artifact). GoReleaser compiled20unique targets but failed
ARMv6/v7 archive-name collision; its old snapshot version also inherited a
slash-containing archive tag. The candidate job stopped before tests because
Node24.19.0 bundled npm11.17.0 rather than pinned11.9.0. This checkpoint gives
ARM archives distinct names, uses commit-based snapshot SemVer/current fields
and explicitly installs npm11.9.0 without changing registry/TLS presets.

The already-requested `master`→`main` rename was inspected and attempted once:
`main` absent, default `master` ated7d100, branchmetadata `protected:false`,
rulesets empty, detailedprotection endpoint403. Repo metadata reports admin but
rename API returned403 `Resource not accessible by integration` on2026-11-13.
No repository branch/settings changed. Keep that concrete owner UI action in
the handoff; do not infer access from coarse admin metadata or missing env vars.

Snapshot and candidate preflight must pass before the two complete final localCI
sequences. Older548/7173/8757 attempts remain explicit superseded evidence.

## Full-source lint repair; remaining CI preflight active

At `7173ff91c599a37c8446048782098137b9e987b0`, tracked local artifact delivery
passed with the actual coverage artifact, and build/coverage passed at58.0%
statements. Full-source staticcheck then reported four ST1005 initial-case errors
for proper-name-prefixed messages. This checkpoint adds lowercase prefixes while
preserving Steam Deck/Gamescope/Flatpak names and behavior. Pinned host staticcheck,
formatting and vet pass. Prior7173 receipts are retained as superseded, not final.
Run snapshot/docs/candidate preflight next to expose any remaining integration
failures, then the complete available matrix and both full localCI sequences at
the final exact clean source. All prepared drafts remain open for owner review.

## Candidate 9 qualification repair checkpoint

The first clean attempt at `8757df4efd6a2723e0b83995140db5984b03f683` passed
212 Go top-level tests/382 events (one optional endpoint skip),127 Python tests,
6 cross-builds, vet/vulnerability checks, brand/site determinism and45 site
viewports. Its local act coverage test passed at58.0% statements but artifact
delivery failed:0.0.0.0 was advertised into bridge containers and local requests
used the inherited proxy. A demonstrated corrected local address/NO_PROXY
exemption delivered the actual coverage artifact; hosted delivery is separate.

This checkpoint repairs dynamic local service advertising while preserving
network presets, token-only/blank-password log redaction, exact required audit
payload inventories and streaming tar expansion bounds. Malformed updater
redirects now produce fixed unsupported results. The new native mixer harness
uses a1e-6 linear-gain tolerance for OBS float32 storage; strict mute assertions
remain intact. Exploratory real OBS mixer/lease/input-loss checks passed without
changing stream state or credentials. These are diagnostic results, not final
candidate/package qualification. Retain both initial failures and run the entire
required available matrix again on the next clean source revision.

## Completion source prepared; candidate 9 qualification active

Source checkpoints are pushed as #62 foundation, #63 live mixer and #64 API/creator,
after the existing #58 -> #59 -> #60 stack. Foundation head is
`b1ee00d58227b5a0d41fa5df03a5ccc5700f8ebe`; audio head is
`fcfa0c2577b5260e1b7036d83daece4a9452e41c`. The next qualification branch
records demonstrated integration repairs, actual clean-source matrix results
and candidate 9 review downloads. No implementation issue or PR is closed/merged.

New source includes persisted stream-only microphone controls, observed inputs/
meters/gains, mute-preserving recovery and independent hold-to-talk guarding;
versioned public API and safe local creator orchestration; canonical governance;
proposed pinned Identity source/creative kit and nine-page site; pinned local CI
and offline unsigned artifact/SBOM/provenance audit. Independent review repaired
three concrete PTT races/state bugs and renewal now checks guardian liveness.
Focused tests pass; full clean-source qualification is still pending. The first
working-tree act Linux build passed; it does not qualify final source.

[Completion review](docs/completion-review.md) and its
[230-criterion ledger](docs/evidence/completion-criteria.json) preserve all35
implementation issues from the live36-issue inventory. #51 remains separate and
unchanged. Finish all available final checks, retain failed attempts, then supply
exact artifacts and smallest owner actions. Native OBS suites precede host
transport, which precedes browser fixtures. Do not race act snapshot/candidate
dist writers with root package/native evidence; execute local CI twice at final
clean source. Required physical Deck/OBS 33/provider/adoption, hostedCI/review,
identity/rights/migration and publication gates remain explicit.

## Milestone 3 candidate 8: all available local checks passed

Prepared in draft #58 -> #59 -> #60 for #47/#24/#48/#49/#50; #51 remains
excluded. Exact clean qualified source:
`bf72ca4ae028f78895eadee6d3874734a1cccd05`. Runtime SHA256:
`d33c976905e6cde8f7ab9491eef62a08a394c80b0c35d65a61bafa34a27dd9f2`.
Review [the owner packet](docs/m3-review.md),
[criterion ledger](docs/evidence/m3-criteria.json) and
[checksum-verifying install command](docs/candidate-8-install.md).

Fresh final checks passed: 175 Go top-level /338 events (one optional existing-OBS
skip), 121 Python, 19 Node, vet/typecheck/build, zero Go/npm findings, reproducible
runtime/updater and payload hashes; seven actual-package browser flows; pinned
Decky 3.3.1 paired install/update/repair/uninstall and old4/6 bootstrap fixtures;
11 site tests/40 viewports; three native OBS30.2.3 suites covering capture,
actual moving/audible recording/replay/profiles/live health/hotplug/media/idle,
repeated stream restarts and generated/manual password recovery. Six binaries
compiled only. file:// was unavailable by browser policy; offline HTTP passed.
CI executed zero steps due to billing lock. Real Deck/OBS 33/Flatpak/Gamescope/
AMD/controller/provider/adoption, human review and M2 identity/publication gates
remain open. No source merges, issue closures, releases, deployments or spending.

Immutable review artifacts are on orphan commit
`9ad051ecbb41df92c723a54bdfb6aaaeb1097898` at
`artifacts/m3-deck8-review`; never merge its tree into source. All36 public files
were independently downloaded and matched, including internal runtime/updater
payloads. Evidence-only follow-ups do not rebuild/relabel the qualified package
or qualify their newer revisions. Historical candidate7 remains unchanged;
failed deccefd/1fe5ec1 attempts are explicit superseded receipts, not passes.

## Active: authorized Milestone 3 streaming features, excluding #51

On 2026-11-13 the owner explicitly requested implementation of #47, #24, #48,
#49 and #50. This supersedes the proposal-only status for those five issues.
#51 is expressly excluded; broader #7/#9/#12/#13/#14 ledgers remain separate.
Start from clean default `master` at
`ed7d100d356ce803d2cb1c1afef3836759deef10`. No additional worktree is needed.
Use reviewable draft checkpoints; implementation approval is not release,
deployment, spending, ownership-transfer or other-repository authorization.

Read [the M3 implementation ledger](docs/milestone-3.md). Preserve explicit
broadcast authorization, game-only capture privacy, v0 compatibility, offline
operation and private configuration. Add recording/replay to every active-output
guard so settings, update/removal and capture cleanup cannot disrupt local output.
Keep exact-source qualification and actual Deck/CI evidence distinct. Existing
M2 target/adoption, CI billing, final identity and publication gates remain open.

Core API checkpoint is draft #58 (`codex/m3-stream-workspace`) at `8df2884`.
Controller/Desktop integration, lifecycle guards, candidate8 packaging and new
native/browser qualification stack on `codex/m3-controller-workflows`. No source
merge is performed by this implementation turn. Candidate8 qualification must
use its own final exact revision; historical candidate7 remains immutable.

Qualification exposed a real retained-output-counter defect: OBS keeps the prior
stopped stream's byte total, so a later stream could transmit successfully while
Start waited to exceed that historical total. A bounded follow-up on
`codex/m3-output-confirmation` establishes fresh advancing samples for new output
and resets on counter/duration/reconnection changes. The updater's own preflight
also guards replay before backup/download application. Do not weaken frame or
output confirmation gates. Preserve failed receipts for `deccefd` and `1fe5ec1`;
neither is a fully qualified candidate.

Host browser/Decky transport/native tests must run in separate phases: they can
contend for port1337 and the conservative same-UID OBS process inspection. Run
native suites first, then transport, then browsers. This scheduling does not
waive or relax process ownership checks. The synthetic video fixture now uses
the existing stable C producer after a demonstrated gst-launch node-teardown
race; production capture still requires verified rendered frames.


## Milestone 2 source merged; Milestone 3 is proposed

The owner explicitly requested merging all six prepared PRs and listing the
next milestone. PRs #52 -> #53 -> #54 -> #55 -> #56 -> #57 are now merged normally
into default `master`; final merge is `df89e8bf3038b43c181e32e09f91e85c8a97e9e2`.
The merged tree exactly equals reviewed head
`48712a1687b0ac907090a6fcea8b6c22c38e6043`. Fresh post-merge Go race checks
passed 110 top-level/206 events (one optional existing-OBS skip), 111 Python and
16 Node tests. No protection/admin bypass was used: branch protection and required
status enforcement were off, rulesets empty. Fresh CI still ran zero steps due
to the account billing lock. Owner source-merge approval does not waive target,
CI, issue-closure or publication requirements.

Working checkout returns to `master`; merged source branches are removed only
after exact-head and reachability verification. The separate immutable review
artifact history remains on `artifacts/m2-deck7-review` and must not be merged.
Candidate7 remains tied to exact source
`0eac1ed9746e6a5999a196777bde5455222f46eb` and unchanged artifacts/evidence below;
merging/evidence-only commits do not qualify a newly rebuilt package. No release,
deployment, Store submission, transfer, payment or issue closure occurred.

Milestone3/parent#46 is still proposed, not implementation-authorized by this
merge/list request. Recommended first feature batch: #47 easy stream/profile
editor + #24 rich custom idle/BRB media. Then #48 audio/runtime resilience,
#49 recording/replay/clips, #50 measured stream health and #51 validation of one
optional paid offering. Broader #7/#9/#12/#13/#14 ledgers remain separately
bounded; do not create a StreamGod repository without the owner's boundary
decision and approval. M2 real Deck/provider/adoption, CI, final identity/assets
and release/site decisions remain open. Crypto activation is intentionally
deferred and is not a prerequisite to the prepared UI.

## Milestone 2 review candidate: all available checks passed

Candidate `0.1.0-deck.7` is locally qualified at exact clean source
`0eac1ed9746e6a5999a196777bde5455222f46eb`. RuntimeSHA256
`4205e4725fd432ea99a59fe8c1a78f0f7b29c7ddbd6c79e3cf4afd8c2c67c9c3`.
Read [the owner packet](docs/release-readiness.md),
[full matrix](docs/evidence/m2-qualification.json) and
[criterion ledger](docs/evidence/m2-criteria.json).
Draft stack #52 -> #53 -> #54 -> #55 -> #56 -> #57 remains for owner review.
Current branch `codex/m2-launch-preparation`; later evidence-only commits must
not rebuild/relabel the qualified candidate or claim tests at their newer SHA.

Fresh available checks passed: 110 Go top-level tests/206 events (one optional
existing-OBS skip), 111 Python, 16 Node, vet, zero Go/npm findings, metadata,
reproducible packages/payloads, actual-package browsers, old4/6 upgrades, current
updater/dynamic6 bootstrap, pinned Decky3.3.1 uninstall, 11 site safety cases/
40 viewports, 13 native capture cases and real OBS30.2.3 audible media/game
fallback/password rotation/old-password rejection/settings-only workflow.
Six cross-builds compiled only. Direct file:// was unavailable by browser policy;
offline loopback HTTP passed. Fresh CI executed zero steps due to the billing lock.

Actual Deck/Flatpak/OBS33/Gamescope/AMD/controller/session/performance/provider
viewer/adoption, required human review, final organization/Identity creative/
rights assets, real funding/wallet readiness and release/site/Store publication
remain explicit gates. No issues were closed, new PRs merged, GitHub release
published, sites deployed, ownership transferred, payments made or money spent.
Crypto addresses remain null/hidden.

Historical459d0fe failed on an ambiguous browser-test locator; one selector was
scoped and the entire matrix rerun at0eac. Earlier passing receipts remain tied
to their historical source. Product source is stable; only evidence, continuity
and owner-packet updates follow qualification.

Review artifacts were pushed to orphan commit
`e202f34070ef6174fbf86b75f9cc87ace74d6a14` on
`artifacts/m2-deck7-review`; never merge its artifact tree into source. All33
public files were independently downloaded and matched, including internal
runtime/updater manifests, capture preferred sources, versions and licenses.
The checksum-verifying [Desktop install command](docs/candidate-7-install.md)
passed syntax/order/URL/hash review without installing on this cloud host.
This is a review checkpoint, not a release or website deployment. Optional
crypto activation was explicitly deferred by the owner; null/hidden wallets
are accepted preparation, not an invented prerequisite to source completion.

## Active: authorized Milestone 2 implementation

After the pre-implementation sync the owner explicitly said to proceed with
Milestone2. Working display name: **Decky Stream**. Organization/final brand and
wallet addresses remain pending. This authorization supersedes the older
proposal-only status below. Read [the implementation ledger](docs/milestone-2.md).
Use one versioned product metadata source; retain current compatibility IDs and
the exact trusted update repository until an approved migration is qualified.
Use Decky-provided environment metadata/paths where applicable, and one shared
Desktop/CLI XDG configuration. Decky's persistent runtime-data directory is not
`XDG_RUNTIME_DIR`. Bottom support buttons use the owner's five common funding
destinations; Bitcoin/Ethereum/Solana receive UI is hidden until public addresses
and explicit networks are configured. No wallet/account/transaction facts invented.

Work is stacked in draft #52 (`codex/m2-product-foundation`) then #53
(`codex/m2-support-panel`), #54 (`codex/m2-installation-lifecycle`),
#55 (`codex/m2-destinations-control`), and the CLI/workflow follow-on,
based on clean default `master`
`539bb54a7a6796558c396ef21b6a72c3aeb03ce5`. The main rename remains403-blocked.
Keep bounded draft checkpoints and current acceptance evidence. No release,
deployment, organization transfer, other-repository submission or spending is
authorized by implementation approval alone. Actual Deck and successful CI/review
gates remain open. Do not apply old preview6 receipts to newer source.

All independent M2 implementation is prepared: metadata/Decky paths, layered
configuration and explicit workflow profiles, funding/local crypto receive UI,
controller panel, provider guides, local password recovery, XDG install/update
and reviewed reset/uninstall/wipe. Remaining docs/site/release preparation is
being checkpointed before a clean-source **0.1.0-deck.7** matrix. Custom Decky
roots require verified DECKY_HOME; unknown-root removal/wipe fails closed.
Published updater4.1 is fixed to runtime4; maintained dynamic6 bootstrap is a
separate tested path, never rewrite old immutable updater bytes.

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
