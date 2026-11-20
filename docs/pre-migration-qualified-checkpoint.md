# Pre-migration available-check checkpoint

The implementation merged through [#113](https://github.com/szmyty/obsgod/pull/113)
then [#114](https://github.com/szmyty/obsgod/pull/114). Merge `a315224` matches the
reviewed `68f7a288` tree; see [continuity](../CONTINUITY.md) for full revisions.
The batch repairs the
missing private export before explicit wipe, corrects normal Decky update/removal
guidance, fixes verified GitHub history pagination, and adds a read-only
repository/real-PR readiness collector. Authentication remains proposed research
under #89; no login, account registration or broker was implemented.

The packaged source is exactly **772230a32a8fdb237a58b8a637947b31671ad509**, clean tree
**f157ea77d16a1f1ce04bf1e47b584f9183c9c359**, with **648 tracked files**.
Package version remains `0.1.0-deck.9`; compatible OBSGod identifiers remain.
This document and its continuity updates are a **notes-only follow-up**, not the
qualified packaged revision. Newer notes receive relevant documentation checks;
they do not rebuild or relabel the immutable candidate.

## Review artifacts

Use the [immutable review checkpoint](https://github.com/szmyty/obsgod/tree/430cc391cb63f080214aacc279e5c04b1092c7a5),
[owner packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md),
[numbered tests](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-TESTS.md),
[checksums](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/SHA256SUMS), and
[reproduction commands](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/REPRODUCE.md).
All 21 files were downloaded from that exact commit and matched the reviewed
checksums. The download-verification receipt SHA256 is
`4b5e6366c52c8ff0a93449e8c3d904ed9cf0202f75fd819b7738385c14bf755f`.

Never merge the artifact branch into source. It is a review download, not a
product release, automatic updater offer, deployment or migrated installation.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `obsgod-decky.zip` | 4,570,722 | `fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a` |
| `obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz` | 12,053,779 | `e8d32968573989565dc74eb4e2bd8bd41e97107ebdbd6f57e56e69f565ef1487` |
| `pre-migration-772230a-public-proof.zip` | 683,339 | `b3b117bd4527643a1525be87481e8b0bb594939854c9b5126a45d514a9237c43` |
| `development-history-772230a.zip` | 202,064 | `3f037e45d9f9613b68946d0e4ea12ffd448dc24b43c7525a4db1732381a31d18` |

The ZIP is the normal Decky installation. The same-source
`obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz` is an optional current cleanup kit;
its checksum is in the packet. A plugin update cannot update an older Desktop
uninstaller. Use its [read-only preview](legacy-cleanup-kit.md), not an extra app
installation, when reviewing later legacy retirement. No owner data was wiped
or retired during development qualification.

## Exact-source results and limits

The fresh completed standalone run records **70 passed command predicates,
two unavailable, zero failed**. Predicates include preparation, audits and
expected nonzero negative controls; they are not test-suite or ACT-job counts.
The [summary](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/qualification-summary.json) and indexed proof retain exact
commands, logs, source bindings, pinned tools/platforms, outcomes and limitations.
The completed main report SHA256 is
`4727b7dbcb5b3a81c024ee0b0738a2b61bcb38c5c1ed5ced9bf3d25157c29c31`.

- Two complete primary source builds produced the same standard ZIP, with
  33 payload files and a 648-file tracked-source hash inventory. The inventory
  count is not the number of entries inside the plugin ZIP. Official CLI `0.0.7` separately
  assembled prepared bytes and matched all 33 files. This does not claim that
  its builder compiled our source or that its raw ZIP is reproducible.
- Go race/process/static/security checks, Python application checks
  (291 outcomes: 289 passed, two privilege-wrapper skips), 151 tooling tests,
  161 frontend tests with absent/reused builds, and 33 branding tests passed.
  The 20 new wipe-export and 35 retained removal focused tests passed with no
  skips. All ten packaged browser flows and all three native Linux OBS
  audio/capture/game-idle harnesses passed.
- Host snapshot, repeated generic/NFPM package audits, notices/source/security
  checks, reproducibility and available Linux package smokes passed. Cross-build
  or container evidence does not establish other native platforms or Steam Deck.
- **Local ACT remains unavailable.** The supported preflight required
  7,544,361,132 root/Docker bytes and observed 3,629,019,136 available: a
  3,915,341,996-byte shortfall. The probe and all six jobs—lint, build, coverage,
  snapshot, docs and candidate—remain **unrun**. Standalone checks are not ACT jobs.
- **GitHub readiness remains unavailable/incomplete.** Current collector source
  queried real PR #114 at base `736be3e2964179f180de34d21dbe81dd33fd8c52` and
  head `772230a32a8fdb237a58b8a637947b31671ad509` using 57 GET requests. SBOM returned 404;
  dependency comparison returned 403. Sixteen hosted jobs had 15 billing refusals,
  one skip and zero executed steps; no executed non-billing failure was observed.
  The exact readiness report SHA256 is
  `2ba94abb987e9a87a7030d835901263b447c172037d7242ad548cad962faeb16`.
  These observations do not prove Graph is disabled, authentication absent or
  a future repository ready. No hosted workflow was repeatedly rerun or paid for.

The first 772230a attempt remains separately **failed/incomplete**: 44 passed,
one unavailable, one native game/idle failure. It contains ENOSPC evidence;
the sole WebSocket-disconnect cause remains unproven. Its logs and dispositions
are retained in a failed-attempt appendix. None of its passes substitutes for
the distinct completed run above.

The 184-member public proof contains only reviewed text and retains failed,
skipped, unavailable and unrun observations. Raw public tracker history is in
the separate five-member history ZIP, with its own exact-byte privacy review
and one documented public-example exception. The strict scanner is unchanged;
no general password exception or private wipe archive enters public proof.
The current exporter observed remote default `069db4a` and captured 67 issues,
47 PRs, 41 conversation comments and three reviews. This is a development
capture, not an atomic retirement backup; refresh it at actual retirement.

## Remaining acceptance

All **230 original criteria and dependencies** remain unchanged. Current review
maps **111 checklist clauses**: 104 bounded implementation/migration clauses plus
seven separate #89 research clauses. Software-only literals do not acquire new
blanket device/full-ACT prerequisites; their original gates remain authoritative.

- #79 retains its explicit review/device-open instruction. #82-C1 still needs
  actual supported-loader lifecycle evidence. #83/#86 actual Decky, SteamOS,
  OBS Flatpak/Gamescope/AMD, controller, microphone/headset, provider/viewer,
  privacy, session and recovery cases remain unrun until the owner tests.
- Required full ACT, hosted/service, platform, human review, rights/license/
  publisher and independent adoption evidence remains open where required.
  Agent source/privacy review is not formal human GitHub approval.
- #87 needs the actual current-install fix loop, exact `OWNER/deckystream`
  destination and applicable creation/retirement authority. #88 needs actual
  new canonical downloads/installation and the concrete v1 packet; #95 needs
  actual destination Graph/manifest/real-PR executed-review evidence. No move
  or trust/ID activation occurred.
- #89's source-backed proposal is ready for owner discussion. Twitch public
  device authorization is proposed first; Kick manual keys remain proposed
  until confidential/public-client ownership is resolved. Authentication coding
  remains outside this batch.

The original qualification did not merge source or close issues. The later
implementation merges do not waive the acceptance above. No product release,
site deployment, repository migration, account registration or spending is
authorized by this checkpoint.
The old af7 review artifacts and historical installer URLs/hashes are unchanged.
