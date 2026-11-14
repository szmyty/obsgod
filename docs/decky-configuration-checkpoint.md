# Gaming Mode configuration and Actions repairs

Implemented [#79](https://github.com/szmyty/obsgod/issues/79) and repaired the
demonstrated failures in [#91](https://github.com/szmyty/obsgod/issues/91),
[#93](https://github.com/szmyty/obsgod/issues/93) and
[#94](https://github.com/szmyty/obsgod/issues/94), in draft
[#92](https://github.com/szmyty/obsgod/pull/92).
Review stack: #73 → #74 → #75 → #90 → #92. No merge or issue closure occurred.

**Qualified source: `378b46cb8c4a9281f9d6890b2e13b223650626d5`.**
All six supported local ACT jobs pass at that exact revision. The overall
acceptance result remains **partial** for the external/device/review gates below.
Later evidence-only documentation does not qualify a different source revision.

[Criterion/matrix summary](evidence/decky-configuration-378b46c.json) and
[72-file public evidence ZIP](evidence/decky-configuration-378b46c.zip) retain
exact commands, source/tool/image hashes, platforms, outcomes and limitations.
ZIP SHA256: `f62ee97c492f22affd26fb7ed6291226bd0f3187f33d6308af7ea98b079cf7af`.

## What changed

The normal Decky panel now has [native destination setup](native-configuration.md):
Kick/Twitch/YouTube/custom RTMP(S) guides, server/key fields, masked typing,
paste/show/hide, stream quality/capture defaults and separate private OBS control
password recovery. A blank key retains only the existing bound destination;
changed servers or explicitly changed accounts/events require a replacement.

Sparse settings merge through the existing Go Configure writer under the shared
control lock. Unedited advanced preferences, idle media/rights, live mute/gain
intent and the canonical XDG store remain intact. Saving requires confirmed
closed/idle managed OBS. Closing an idle instance is separately confirmed.
Save and read-only connection testing never launch OBS or broadcast. The adapter
projects named public fields, rejects stale/busy state and clears private
payloads; the UI clears private drafts on save, destination changes, dismissal
and removal. Provider OAuth/phone login remains deferred in #89.

Three reproducible source/harness failures were repaired:

| Issue | Demonstrated failure | Repair and current evidence |
| --- | --- | --- |
| #91 | Pinned staticcheck ST1005 rejected the capitalized storage-map error | Lowercase lead-in; final ACT lint passes without disabling the rule |
| #93 | ACT root fixtures inherited TMPDIR under UID 1000-owned workspace ancestors | Runner-owned temp only for Go/tooling test steps; shared native-builder paths and production guards retained; build/coverage/candidate pass |
| #94 | ARMv6 Debian package was armhf while the strict auditor expected armel | Exact pinned NFPM 2.49.0 mapping corrected; all 15 format/architecture pairs and wrong-label refusal covered; actual package audits/smoke pass |

## Checks at qualified source

| Check | Outcome |
| --- | --- |
| ACT lint / Ubuntu build / coverage | Passed; full-source staticcheck/vet and Go tests; coverage 60.2% |
| ACT snapshot | Passed; 20 generic archives, 15 Linux packages, repeated unsigned inventories, pinned Debian/Fedora/Alpine install-removal smoke; publish/sign disabled |
| ACT documentation preview | Passed; metadata/site checks and 11 tests; local artifact service only |
| ACT candidate | Passed; Go/race/vet/vulnerability, 184 application Python tests (183 passed, one root-only skip), 85 tooling tests, 43 Node tests, typecheck/build/npm audit |
| Candidate artifact/browser/native steps | Passed; two identical runtime/updater builds and audits; 10 browser harnesses including the new setup/key form; real OBS audio/capture/game transitions in synthetic Linux |
| Host Go race, count1 | Passed as UID 1000: 259 top-level tests / 545 pass events; optional real-OBS test and root-only negative test skipped explicitly |
| Primary standard Decky package | Passed; matches the candidate workflow ZIP; official CLI 0.0.7/default pinned builder compared all 33 payload files with container networking disabled |
| Actual packaged Python → packaged Go | Passed: 150 assertions for binding, sparse preservation, private password changes and redacted readback; zero OBS/Flatpak/Desktop launches |
| Primary-ZIP browser checks | Passed: native configuration nine cases, dependency setup six cases, existing panel suite |
| Host frontend after ACT | Passed typecheck/test/build with absent and reused output, real UID 1000 ownership and clean source |

Seven ACT attempts at this revision are retained: six successful jobs plus the
first candidate failure from disk exhaustion at native fixture startup. The
unchanged-source retry cleared only disposable container Go compiler cache after
all Go builds/audits, before native tests. Exact command and before/after bytes
are retained. No required step was skipped. The reporter verifies original
receipt/log hashes and marks the old failure superseded by the successful retry;
it reports zero open failure groups and no evidence integrity errors. No optional
cache-save warnings occurred on this revision. Earlier 4c5af7f/5935803 failures
and skips remain separate historical evidence.

Inactive host caches were temporarily relocated for space. Original cache paths
were restored; package-manager/browser cache contents were retained. Two inactive
historical Go compiler caches were pruned with the pinned `go clean -cache`.
Source, artifacts, module caches, network/package presets and evidence were kept.

Host: Linux 6.18.57 x86_64, UID 1000, Go 1.27.4, Node 24.19.0, npm 11.9.0,
Python 3.12.14, Docker 28.4.0, ACT 0.2.97, Playwright 1.62.0. ACT uses the pinned
Ubuntu 24 runner. Native fixtures use the exact Debian image/script/binary/library
hashes in `native/index.json`, with real OBS/PipeWire/PulseAudio/GStreamer and
software encoding; 18 filtered JSON proofs represent 15 distinct hashes.

## Artifact and remaining gates

```text
Version: 0.1.0-deck.9
Source: 378b46cb8c4a9281f9d6890b2e13b223650626d5 (dirty=false)
Platform: linux/amd64
ZIP SHA256: 077234a0b917e58a4723d846ed56ff5f8ba23bc4721f344c99889e66a7a719db
Go binary SHA256: 0ca92907fa9012d52ea3aed57666fbe4842b72826890d30396517893e0fbb281
```

Local review ZIP: `/workspace/.obsgod-tools/native-config-candidate-3/obsgod-decky.zip`.
This is not a published release or migration. The canonical ZIP is reproducible;
the upstream raw assembly ZIP retains nondeterministic timestamps. Official
assembly verification compares prepared bytes, not upstream source compilation.

The fresh hosted audit at this source found nine failed runs, 15 jobs and zero
executed steps: 14 exact billing-lock failures plus one correctly skipped
push-event dependency-review job. No executed hosted nonbilling failure was
found. An actual PR #92 base/head dependency-comparison API read returned 403; its
service acceptance remains unavailable. No billing retry, paid resource or
repository security setting change was made.

Actual Steam Deck/SteamOS/Flatpak/OBS 33/Gamescope/AMD/controller/Steam keyboard,
headset routing and Kick viewer reception remain unrun owner checks. Native
Windows/macOS/ARM runtime and required hosted CI/reviews are not established by
Linux/cross-build/mock evidence. OAuth remains #89; later #80–#88 work and the
final owner test/release/migration packet remain open. No release, deployment,
migration, Store submission or spending occurred.

Public evidence logs redact Actions mask values, including ephemeral local
artifact-cache capabilities. `INDEX.json` distinguishes original/private log
hashes from public/redacted hashes. Raw receipt integrity was verified before
redaction; redacted files are not relabeled as original bytes. The packet excludes
OBS profiles, secret stores, raw configs and raw native logs.
