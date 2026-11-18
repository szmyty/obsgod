# Settings boundary checkpoint

Draft [PR #110](https://github.com/szmyty/obsgod/pull/110) implements bounded
[#103](https://github.com/szmyty/obsgod/issues/103), stacked on unmerged draft
[#109](https://github.com/szmyty/obsgod/pull/109). The issue remains open for
review. All 230 original criteria and dependencies remain intact.

The exact clean qualified source is
**4eac7a469285cbafad5dc5a7ea07205374293dfd**, tree
**2ca38c6e704ce9c9ea19b50938e99af98714b7d9**. Subsequent evidence/documentation
commits are not relabeled as that source. See the
[machine report](evidence/settings-boundary-4eac7a4.json),
[indexed proof ZIP](evidence/settings-boundary-4eac7a4-proof.zip) and
[separate evidence review](evidence/settings-boundary-4eac7a4-review.json).
Proof ZIP SHA256: **e5bd203af8d774c803e5b889cf3eb61fd374ff8cf2600b81d37b7e9a2be81082**.

## Behavior and original criteria

The complete capture-mode operation now includes Go mutation and post-status,
Python preflight/owned cleanup/fresh readback, and the frontend timer. The normal
nominal envelope is 11.7 seconds beneath the UI's 15 seconds. A process that
cannot yet be reaped retains the same pending identity until exit; these are
not hard real-time OS guarantees. Stop/recovery, caller-disconnect ownership,
key/settings binding and explicit Start remain intact. A committed settings
pair is preserved when later readback is unconfirmed.

Both clients require complete, consistent schema-v1 configuration facts before
granting readiness. Supported legacy defaults remain valid. Missing output
knowledge grants no new output/configuration/destructive permission or green
streaming indication. Read [the contract](settings-boundary.md).

| Original #103 criterion | Local evidence at the qualified source |
| --- | --- |
| D1: actual lock held past UI budget; no later unconfirmed write | Passed actual bundled Python→Go process case; lock held at least 16 seconds, RPC completes under 12 seconds, owned child exits before release, bound pair remains unchanged afterward |
| D2: near deadline, disconnect, watcher lease, Stop and repeats | All six packaged scenarios passed; 42 guarded child calls; focused process/signal/lease tests preserve binding and broadcast authorization |
| D3: complete timeout ordering | Go action/post-status and Python preflight/cleanup/new readback are included; command acknowledgement alone is insufficient |
| R1: incomplete/types/contradictory readback | Go-produced shared corpus and both client suites reject malformed readiness and disable edit/close |
| R2: legitimate emitted states | First-run/configured/running-idle/streaming/legacy-zero/unavailable states retain their intended decisions across 106 corpus cases (16 valid, 90 malformed) |
| R3: unknown/absent output knowledge | Explicit knowledge is required for new output and permissions; Stop/recovery remains available |

This is criterion-level local eligibility, not issue closure, GitHub review or
actual Deck/provider acceptance.

## Exact-source qualification

All six serial free local ACT jobs have passing completed runs: lint, Linux
build, race/coverage, nonpublishing cross-platform snapshot, docs and Steam Deck
candidate. The selected candidate is `20261118T204648Z`. The bounded completed-run
report includes all nine same-source completed attempts: six PASS and three
historical FAIL, with zero unresolved failure groups and zero integrity errors
**in that completed-run selection**. Overall external acceptance remains partial.

The earlier `200445Z` reconnect killed its controller before completion and left
no final exit/checksum. It remains unverifiable and unqualified. Original state,
its provisional receipt and partial log remain unchanged; the fresh original-state
report still reports that integrity error despite the six later selected passes.
The proof includes both reports, the provisional receipt, filtered partial log and hash-bound
selection inventory. No missing completion or checksum was invented, and no
completed failure was omitted.

| Check | Result |
| --- | --- |
| Application Python | 271 total: 269 passed, two root-only wrapper cases skipped because the outer fixture already runs as an unprivileged user |
| Tooling Python | 85 passed |
| Frontend | 156 Node tests; typecheck, build and audit passed |
| Packaged browser flows | Setup, panel, dependencies, native settings, media, mixer, support and site passed |
| Packaged settings boundary | Six real lock/process scenarios passed using the actual ZIP and bundled Go executable |
| Native Linux OBS/audio/capture/game/idle | Passed; 18 filtered proof files, 15 distinct hashes |
| Broad packaged adapter→Go | 218 CPython and 240 simulated-frozen checks; 22 guarded Go calls per mode |
| Supplemental transport/CLI/upgrades | Passed; optional Fish syntax unavailable |
| Normal-user frontend output absent/reused | All six typecheck/test/build commands passed; generated output owned by UID1000 |

The primary standard ZIP matches both repeated workflow builds and all 33 files
assembled by pinned official Decky CLI 0.0.7/default builder. Its SHA256 is
**2c40cba7b89065f410ec9e20cc73973e2638edd612e250c7bdf2aef3328c72e0**.
The official CLI comparison assembles prepared bytes; its raw ZIP is not claimed
reproducible or source-compilation evidence. Exact commands, artifact hashes,
platforms and pinned tool/image identities are in the proof. Native qualification
uses Debian Linux OBS30.2.3 and Python3.13.5; host Python is3.12.14 and ACT
Python3.12.16. This is a local candidate, not a published release.

## Repairs, runner assistance and remaining gates

The first integrated Go test collided with another package's simulated OBS port;
the real process case now runs serially with `deck_process`. An old M3 assertion
was updated for the deadline-bound read-only status call. The first complete
e2928ff matrix then exposed a fixed-sleep worker-fixture race. A test-only release/
completion-marker/kernel-lease handshake repaired it; the production three-second
worker and module are unchanged. Final qualification is at the newer 4eac7a4.

At that source, recording/export safety reserves correctly refused insufficient
runner disk space. Only disposable active-container compiler caches were cleared;
the exact private fixture volume was moved temporarily to the separate host
volume without changing its logical bind path. A later repeat correctly refused
to overwrite old settings-test evidence; the previous folder was preserved and
the successful run used a fresh one. All failed/interrupted attempts remain
historical. These measured accommodations do not complete #104's unassisted
resource/primary-build acceptance. Five preserved cache/tool/artifact locations
and the fixture volume were restored with matching current before/after hashes;
network, authentication and package presets stayed unchanged.

Frozen-source hosted jobs executed zero steps: 12 billing refusals, two unstarted
macOS cancellations and one expected push skip. Actual PR dependency comparison
and detailed protection APIs return403; no protection was bypassed. Actual
supported-loader/Steam Deck/SteamOS/Flatpak OBS33/Gamescope/AMD/controller/headset/
provider-viewer checks, native non-Linux execution and actual Python3.9 runtime
remain unrun. These remain #86/original-ledger gates. Drafts #109/#110 have no
submitted GitHub reviews. No release, deployment, migration, Store submission,
spending or consumer adoption occurred. Remaining artwork/UI/docs/#104/#85 work
is separate.
