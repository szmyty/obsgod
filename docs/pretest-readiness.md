# Ready for the guided Steam Deck test

The feasible implementation and current testing handoff are prepared. Start with
the [short testing booklet](testing-booklet.md); we will work through one page at
a time and repair demonstrated failures before continuing dependent steps.
Actual Steam Deck results remain **UNRUN**. No manual result is inferred from
the Linux fixtures, source merges or the booklet itself.

## The build we will test

Use the existing compatible OBSGod installation path and the exact reviewed
`0.1.0-deck.9` candidate from source
`772230a32a8fdb237a58b8a637947b31671ad509`, tree
`f157ea77d16a1f1ce04bf1e47b584f9183c9c359`.

- [Standard plugin ZIP](https://raw.githubusercontent.com/szmyty/obsgod/430cc391cb63f080214aacc279e5c04b1092c7a5/obsgod-decky.zip):
  4,570,722 bytes, SHA256
  `fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a`.
- [Checksums](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/SHA256SUMS),
  [owner packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md)
  and [detailed cases](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-TESTS.md).

Its recorded available qualification has **70 passed command checks, two
unavailable and zero failed**. All three native Linux OBS harnesses and ten
packaged browser flows passed. There were two Python privilege-wrapper skips;
these results do not prove actual SteamOS, controller, Flatpak or provider use.
The original failed attempt is retained separately in the reviewed evidence.

Main `a2137bf` differs from that candidate only in thirteen Markdown/evidence
files. Later documentation is not relabeled as its qualified source. The
[exact-source checkpoint](pre-migration-qualified-checkpoint.md) preserves the
full revisions, tools, commands, hashes, failure history and limitations.
We will record the installed candidate during the session rather than assume it.

## Fresh checks before this handoff

The [readiness record](evidence/pretest-readiness.json) binds these observations
to exact main revision `a2137bf214c77efda3ce3fb87879f88004c6477c`.

| Check | Actual outcome | Remaining action |
| --- | --- | --- |
| Supported local ACT matrix | **UNAVAILABLE**: maintained invocation exited 3 before runner allocation; probe and all six workflows are **UNRUN**. | Use adequate free Linux root/Docker and scratch capacity; run a fresh preflight without weakening it. |
| Root/Docker capacity | 7,544,361,132 bytes required; 3,123,400,704 available; short 4,420,960,428 bytes. | Supply enough free capacity; this handoff does not prune preserved artifacts, caches, images or tools. |
| Scratch capacity | 8,664,485,888 bytes available versus 6,442,450,944 required. | Preserve the actual filesystem/path requirements. Scratch alone does not satisfy root capacity. |
| Hosted Actions on main | Five runs, eight jobs: seven billing-lock failures, one push-only dependency-review skip, zero executed steps. | Account/service access remains unavailable; no source failure or passing hosted check is inferred. No reruns or spending. |
| Dependency services | The earlier exact-PR collector retained SBOM 404/comparison 403. | Verify the actual new destination under #95 after approved migration. These responses do not prove Graph is disabled or authentication absent. |
| Actual Deck, loader, viewer and adoption | **UNRUN**. | Follow #86 and the booklet, including #79, #82-C1 and #83 observations. |

These unavailable checks remain #85 and the applicable final acceptance gates.
They do not manufacture a new prerequisite for gathering local manual evidence.
A new source or package change receives its own affected checks and revision.

## Owner facts for the later migration

These decisions can be prepared in parallel; they are not needed to make the
first local clip with the current compatible installation. No value below is
silently selected by this preparation.

| Fact | Verified now | Owner action still needed |
| --- | --- | --- |
| Repository | Current public fork is `szmyty/obsgod`, default `master`; future slug `deckystream` is selected. | Choose exact `OWNER/deckystream`, its administrator and creation/retirement authority. The new default will be `main`. |
| Branding and rights | Owner selected 01 / aurora; original code attribution/notices and artwork method/digests are retained. | Resolve final asset license/permission, name availability and production adoption. A selected direction is not a rights grant. |
| Publisher and support | Namespace is known; legal publisher and canonical support contact are unresolved. | Name the responsible publisher/contact and approve actual publication destinations. |
| Release and signing | Existing review artifacts are unsigned/self-reported, not a v1 release. | Choose the final version/notes and actual signing policy or transparent unsigned policy after the final source is known. |
| Sites | Landing/docs source exists offline. | Select canonical domains, hosting and responsible deployer; deployment needs its separate approval. |
| Optional login | #89 has a proposed Twitch device/QR and Kick feasibility packet. | Discuss/select a design before authentication coding or app registration. Manual-key streaming remains independent. |

## What happens next

1. Begin the booklet with inspection only. Confirm the device, versions, idle
   state and preserved settings before any replacement or recording.
2. Test setup and a playable local clip, then microphone/privacy and an explicitly
   chosen live-stream test. Report one outcome at a time; fixes receive a new
   pinned candidate and affected retesting.
3. Complete actual loader, update/recovery/removal, session and optional-feature
   cases safely. Normal testing needs no wipe or legacy retirement.
4. After current-install acceptance and exact authority, perform #87 migration,
   #95 real destination service verification and #88 canonical new-install/
   adoption/v1 preparation. Obtain precise release/deployment approval and close
   parent #46 last.

The ten open issues are #46, #79, #82, #83, #85, #86, #87, #88, #89 and #95.
The six bounded source issues #76–#78/#80–#81/#84 closed against their
[47-clause assessment](evidence/bounded-source-closure-20261120.md); all 230
original criteria and dependencies remain. No release, deployment, repository
move, account registration, paid service or manual test was performed here.
