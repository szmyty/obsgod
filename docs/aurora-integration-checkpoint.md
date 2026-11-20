# Aurora integration and current review candidate

[PR #112](https://github.com/szmyty/obsgod/pull/112) merged normally at
`069db4a21ec0a173b7dd30c12a53018c7700f79b` after fresh focused validation of
`448b15dc1ee91ff8ca6c5ec9b02cad4bac850024`. Its tree matched the reviewed head.
No protection was bypassed. Its two primary builds, 160 Node tests,
typecheck/build and three packaged browser suites passed; those historical
receipts do not qualify the later source.

[Draft PR #113](https://github.com/szmyty/obsgod/pull/113) implements the selected
01 / aurora kit, lowercase `deckystream` presentation, local native marks with a
separate observed-state badge, README/site branding and bounded current setup
documentation corrections. Stable compatibility IDs, private settings, explicit
Start and the original 230 criteria/dependencies remain intact. Source-changing
integration repairs preceded the qualification below. This checkpoint's later
notes/evidence commit does not change the identity of the qualified source.

## Exact source and artifacts

Qualified source: **`af7a20fdd0c62404e9b11d540fb605368e269380`**; clean tree
`d6149d9ec670cffcc30db355262aa688382b5e7e`, 617 preferred-source files.
Standard Decky candidate version **0.1.0-deck.9**, **4,570,728 bytes**, SHA256:

```text
4deece2bcaba6440c168d5cb7b1bc585e346d6b2f06655a1672c0d9638afeab8
```

Two complete primary builds produced exactly these bytes: 33 payload files,
matching source/build manifests, licenses and preferred source. Pinned official
Decky CLI 0.0.7 and its default builder separately assembled and compared all
33 prepared files with networking disabled. That additional check is neither
source compilation nor reproducibility of the official CLI's raw ZIP.

The immutable review-artifact commit is
[`f2b160823800e3befd7440e6bcce8d135845a008`](https://github.com/szmyty/obsgod/tree/f2b160823800e3befd7440e6bcce8d135845a008). All 18 files were freshly downloaded from their public pinned URLs and matched
their expected bytes/hashes. The independently reviewed text-only proof ZIP is
586,090 bytes, SHA256
`de58f9171eaa6b3b091dbe3a10d0ab5bb1515cc3d922cb2a4f44b61aba643241`.

Review download, evidence hashes and machine/Deck instructions are linked in the
[owner packet](aurora-owner-packet.md). Use that candidate-specific packet;
[current-review-install.md](current-review-install.md) deliberately preserves
the older immutable 4699235 Desktop installer and does not install af7.
No mandatory Desktop companion is needed: normal Decky ZIP, consented native
OBS/GStreamer setup and private native destination settings are the current path.

## Current-source results

The [summary](evidence/aurora-af7-qualification.json) and the independently
reviewed public proof archive retain exact commands, tool/platform versions,
original/public hashes and limitations. Main controller: **67 passed command
predicates and 1 unavailable command**, completed. These are not 67 test cases
or six passing ACT jobs; an expected-exit-1 primary rejection is a passed
negative predicate. Overall full qualification remains **unavailable**.

| Area | Actual result at af7 |
| --- | --- |
| Application / tooling Python | 269 passed + 2 privilege-wrapper skips / 124 passed |
| Go | race, serial process tests, vet, staticcheck, govulncheck passed; host coverage 62.4% |
| Frontend | 161 Node tests, typecheck/build, dependency audit; absent and reused frontend-output cases passed |
| Branding | 33 tests with no skips; all 38 output files repeat byte-identically; drift and pinned Identity source checks passed |
| Packaged browsers | All 10 flows passed, including native settings, dependencies, recovery, recording/replay and site |
| Native Linux OBS | All 3 synthetic harnesses passed: capture, game/idle and system/mic/media; OBS 30.2.3 is not Deck OBS 33 |
| Package integration | 218 CPython / 240 simulated-frozen cases; 22 guarded child calls per mode passed |
| Snapshot and installs | 20 cross-platform archives and 15 Linux packages audited; Linux archive/deb/rpm/apk install smokes passed |
| Offline gallery | Loopback gallery decoded 16 PNGs at both viewports and verified actual PNG download bytes; zero external requests |
| Gallery file URL | Unavailable: browser administrator policy blocked direct navigation; failed attempt retained |
| Optional Fish execution | Unavailable: interpreter absent; generated completion text checked |
| Full supported ACT matrix | Preflight refused before runner/probe allocation; all six jobs unrun |
| Hosted af7 Actions | 15 billing refusals + 1 expected push-only skip, zero executed steps; no executed non-billing source failure |
| Owner machine / actual Deck / viewer | Unrun |

Supported ACT preflight measured root **2,597,666,816 bytes available** against
**7,544,361,132 required**: short **4,946,694,316 bytes** at that attempt. Separate
scratch was sufficient. A fresh preflight on a capable free Linux environment is
needed; this is a real capacity gate, not a reason to lower the threshold or
claim standalone commands ran the workflow jobs. Compiler-only trim preserved
modules and prior outputs; no unrelated cache, Docker image or network preset
was removed. Hosted billing, dependency-advisory services and local capacity are
separate limitations.

A later [read-only resource feasibility audit](evidence/aurora-af7-resource-feasibility.md)
measured a **5,425,688,748-byte root shortfall**. Maximum relocation while keeping
6GiB scratch plus even optimistic optional-builder reclamation still falls short
by1,220,358,316bytes. The apparent older native images share required layers;
removing their names would reclaim none. No images/caches/outputs were deleted
or moved. This additional audit does not change the original matrix refusal or
67+1 command-row dispositions.

## Criterion evidence and remaining gates

The [independent criterion review](evidence/aurora-af7-criteria.json) maps all
**7 literal #80 criteria and 14 literal #81 criteria** to current source and
measured local results, with no blocking source or visual finding. This is an
agent review, not a formal GitHub human approval. Both issues stay open for the
review decision; source merge alone never supplies closure evidence.

A separate [foundation reconciliation](evidence/aurora-af7-foundation-criteria.md)
now maps all27 #76–#79 source contracts to fresh af7 evidence, with no new
source gap. Physical-controller/service facts and #79's explicit review/device
keep-open instruction remain separate; no issue closure is performed.

The [remaining inventory](evidence/aurora-remaining-acceptance.json) preserves all
104 current bounded criteria and their next evidence/actions. The original
230-entry ledger is unchanged, SHA256
`0795e6594c7bbde195bb8ebfcbc4050f0d5ecbe9c879767edbe0050540386df6`.

The generated hero and separately authored vector interpretation have recorded
provenance, font/third-party notices and proposed rights fields. Production
artwork rights/license, publisher/contact, exact destination owner, site/release
publication and production adoption are decisions still to resolve. The
consumer's reviewed Identity source pin is retained; no Identity repository
change, production compiler claim or upstream release was made.

Next: review draft #113, run the owner-machine matrix on capable free resources,
then the numbered current-install Deck test/fix loop under #86. The real
supported-loader install/load/unload/reload lifecycle in #82-C1 remains explicit.
SteamOS/Gamescope/AMD/controller/headset/provider reception, required platform/
CI/review and independent/new-user adoption are not proved by fixture tests.
After that loop, resolve exact migration/publication facts under #87/#88 and
verify the actual destination dependency graph/PR comparison under #95. #89
OAuth/phone login and #51 Store/monetization research remain separate.

No product release, deployment, migration, Store submission, paid resource or
other-repository change occurred. The artifact branch is a review checkpoint,
not a release or updater offer. New source requires affected requalification.
