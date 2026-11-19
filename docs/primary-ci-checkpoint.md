# Primary build and constrained local CI checkpoint

Draft [PR #111](https://github.com/szmyty/obsgod/pull/111) implements bounded
[#104](https://github.com/szmyty/obsgod/issues/104). All six literal criteria
have local evidence; the issue and PR remain open for review. The complete
six-job ACT matrix is **unavailable**, with every workflow **unrun**. This
checkpoint does not complete #85 or #86.

Exact clean source: **0c798468ecadd753c43bb8970b76e88f263f3a5c**; tree
**b5d95741d3352d8eccfc954085895fda8268fa38**. Later evidence-only commits
are not relabeled as that source or a newly built candidate. Read the
[machine report](evidence/primary-ci-0c79846.json),
[indexed proof ZIP](evidence/primary-ci-0c79846-proof.zip) and
[independent proof review](evidence/primary-ci-0c79846-review.json).
Proof ZIP SHA256:
**58334d517a9c0f3dbe19b433a52a3b69dcda586a88c8f86330b40dc9f46887e9**.
The archive contains 172 selected text members and their index; original and
public hashes distinguish reviewed redactions from raw evidence.

## Implementation and original criteria

The candidate workflow now executes the complete primary `package-decky.py`
entry twice using the checkout's non-root owner. It audits exact source,
manifest, private payload, license/SDK/native inputs and canonical ZIP bytes.
Existing packaged browser/adapter/settings checks consume that actual ZIP;
legacy compatibility archives must contain identical plugin bytes. The root
guard remains active. Optional official CLI verification assembles prepared
bytes and compares all 33 files; it does not establish official source
compilation or reproducible raw official ZIPs.

The constrained profile uses fresh session/attempt directories, serial jobs,
private compiler caches and explicit post-consumer cleanup. It retains module
caches, artifacts, evidence, source, pinned tools and existing presets. Before
allocating a runner it measures free space and cached Docker image metadata.
VFS requires an additional allowance of twice the image's logical size. Low
capacity returns exit 3 with a concrete need, leaving the Docker probe and all
six workflows unrun. This is a conservative allowance, not a peak-space guarantee.

| Original #104 criterion | Current bounded evidence |
| --- | --- |
| P1: primary-only entry failure fails the candidate | Actual maintained shell rejects a wrong revision with exit 1; raw primary failure is retained and success exports are absent. This proves step failure propagation, not an executed ACT job. |
| P2: exact source, audits, actual package fixtures and deterministic repeats | Two complete UID1000 primary builds match; actual ZIP fixtures, repeated compatibility/updater builds and source/privacy audits pass. |
| P3: no publication, root bypass or mandatory pair | Standalone plugin and ownership guards remain; no publishing/deployment or mandatory paired app was added. |
| R1: finish without manual Docker intervention or refuse early with a concrete need | The supported full-matrix command actually exits 3 before runner allocation, with measured capacity and six unrun jobs. This satisfies the criterion's explicit refusal alternative. |
| R2: compiler-only cleanup after consumers with exact inventories | Maintained cleanup ran last; exact private cache inventories/disk measurements and successful cleanup exits are recorded. Module inventory is unchanged across that interval. |
| R3: presets and every required test retained; free resources | Required checks and reserves remain, standalone checks pass, and network/package/auth presets are unchanged. No paid resource was used. |

## Exact-source results

The completed standalone report verifies **61 passed command-check predicates**
and one capacity-unavailable command. These are neither 61 test cases nor 61
exit-zero invocations: the negative check passes by observing the expected
nonzero primary failure. Twenty-three passing rows and the matrix refusal are
retained unchanged from the earlier same-source execution; 38 later rows passed.
All 62 current log hashes and clean before/after source bindings verify.

| Check | Result and scope |
| --- | --- |
| Complete primary build | Passed twice, UID1000; canonical ZIP SHA256 `7fc9faada008280f2edfa0ff59f92e4a61edfae0d1f20675f629a88ccad81984`; both optional official assembly comparisons passed |
| Application Python | 271 total: 269 passed; two root-wrapper cases skipped because the fixture already runs unprivileged |
| Tooling Python | 116 passed |
| Go | Race, serial `deck_process`, vet, staticcheck, govulncheck, host build/tests/coverage/format passed |
| Frontend | 156 Node tests; normal-user absent/reused-output typecheck/test/build, npm audit passed |
| Actual packaged settings | Six process/lock/deadline scenarios, 42 guarded children passed |
| Packaged browser flows | Ten flows passed through the maintained short-path wrapper using host Chromium |
| Packaged adapters | 218 CPython and 240 simulated-frozen checks; 22 guarded calls per mode passed |
| Native Linux OBS/audio/capture/game/idle | Three serial Docker harnesses passed; 18 filtered proof files, 15 distinct original hashes |
| Compatibility, transport, CLI and upgrades | Repeated canonical artifacts, source/privacy audits and supplemental checks passed; optional Fish syntax remains unavailable |
| Nonpublishing snapshot | Unmodified GoReleaser configuration, parallelism 1, `--skip=publish,sign`: 20 archives and 15 Linux packages; repeat audits and Linux native/package installation smokes passed |
| Funding, documentation and site | Funding check, offline build/check and 11 site safety tests passed |
| Supported ACT matrix | Unavailable; lint/build/coverage/snapshot/docs/candidate all unrun after preflight refusal |
| Hosted checks | At frozen source: 14 billing refusals, one expected push dependency-review skip, zero executed steps. Actual PR dependency comparison separately returned 403. |

Host: Linux x86_64, Python3.12.14, Go1.27.4, Node24.19.0, npm11.9.0,
Chromium151.0.7922.173, Docker28.4.0/VFS and ACT0.2.97. The native image
`sha256:74e5068d35ebfb2344b1be935fd7e48ed09b1383cc702fe88c1854a50823c9b5`
contains OBS30.2.3, Python3.13.5, ffmpeg7.1.5, PipeWire/GStreamer1.4.2 and
PulseAudio17.0. Exact command arrays, dates, image/tool identities, platform
receipts, inventories and artifact hashes are in the indexed proof.

## Resource measurements and preserved history

The actual matrix preflight recorded a 4,441,321,644-byte root-space shortfall.
After all artifacts and evidence were prepared, a fresh preflight required
7,544,361,132 bytes on root/Docker's filesystem and observed 2,684,194,816,
leaving **4,860,166,316 bytes** missing. Separate scratch requires 6GiB and has
enough space. The smallest next action for the full ACT matrix is to free at
least **4.6GiB more on the root/Docker filesystem**, or use a free workspace
meeting the printed root/scratch requirements. Keep all required tests intact.

The maintained cleanup removed only disposable private compiler entries after
all Go consumers. The user cache changed from 2,777,516,899 bytes to 228 bytes
of Go housekeeping files; the root cache was empty. Module inventory remained
639 files/2,881,186 bytes with SHA256
`049fed17ea1f79059737bd170679abf2411f3359a527c0a4679b4918f9c593e4`
before and after cleanup. This proves the standalone policy path; root ACT cache
execution remains unrun. Old root-owned generated `dist` and notice staging
were preserved by literal same-mount rename using a pinned, network-disabled
Alpine helper. No recursive checkout ownership change, host-cache relocation,
global Docker prune or preset change occurred.

The earlier 4108 source and first VFS allocation failure remain historical;
the final repair checks image metadata before allocating a container. An initial
private collector also failed on old generated-output permissions, then a
same-source browser launch failed because its long temporary path exceeded a
Unix socket limit. The maintained workflow already used the short-path wrapper.
The corrected private invocation passed without source changes. Original failed
reports/logs and retained row/hash provenance remain explicit; no completion was
invented and no older source pass qualifies 0c79846.

## Integration and remaining gates

Normal merges #109 then #110 produced master
**cdcc668dc21f86748dbb5a8a00d2516affb83c7e**. Independent literal-criterion
reconciliation closed #101(7), #102(8), #103(6); see the
[closure assessment](evidence/audit-101-103-closure.json). In particular #102-D4
requires no dependency download during lifecycle initialization; actual
supported-loader startup remains unrun under #86. No protection was bypassed.

All 230 original criteria/dependencies remain intact. Full ACT and hosted CI,
actual supported Deck/SteamOS/Flatpak OBS33/Gamescope/AMD/controller/headset/
provider behavior, native non-Linux execution, rights, migration and consumer
adoption remain separate gates. Selected aurora artwork/controller UI and the
final source-changing integration work precede #85's final candidate; #86 is
the owner device test/fix loop. No release, deployment, migration, Store action,
paid resource or consumer adoption occurred.
