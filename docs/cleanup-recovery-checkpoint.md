# Cleanup and recovery checkpoint

Draft [PR #109](https://github.com/szmyty/obsgod/pull/109) implements bounded
[#101](https://github.com/szmyty/obsgod/issues/101) and
[#102](https://github.com/szmyty/obsgod/issues/102). Both issues remain open for
review. This checkpoint preserves all original criteria/dependencies and does
not close parent #46 or final device acceptance #86.

The exact clean qualified source is
**aa323f0119e2d3c475d04a30860a4c3e314620bc**, tree
**9f987b34b33daad2922c0de0c49f51aeb27b1931**. Evidence/documentation commits
that follow are not relabeled as that source. See the
[machine report](evidence/cleanup-recovery-aa323f0.json) and the
[indexed proof ZIP](evidence/cleanup-recovery-aa323f0-proof.zip), reviewed in the
[separate attestation](evidence/cleanup-recovery-aa323f0-review.json).
Proof ZIP SHA256:
**5483d8b16041fab343d2c87038c556ed5f4264d1e80f2982f431c35f893f4ec2**.

## Changes

- Cleanup retains update/install/control coordination inodes across wipe,
  partial deletion and retry. Pinned paths/ancestors reject changed previews;
  unsafe writable ancestry fails before writes, locks or deletion.
- Explicit legacy-app-only retirement preserves the active Decky plugin,
  shared settings/state/cache, rollback backups and media.
- Retained dependency repair uses the verified candidate ZIP's native setup
  policy and shared session/idle/lease guards. Ordinary plugin startup still
  downloads nothing before consent.
- Update checks compare the loaded plugin independently of optional Desktop
  app inventory. Standard releases require ZIP/receipt/checksum metadata.
  Recovery binds exact candidate/current plugin versions, rejects historical
  installers missing safeguards, and cannot roll back to an unrelated old app's
  plugin archive.

Read the [cleanup/recovery contract](cleanup-recovery.md) for exact behavior.

## Exact-source qualification

All six serial free local ACT jobs passed: lint, Linux build, race/coverage,
nonpublishing cross-platform snapshot, docs, and Steam Deck candidate. Receipts
and original log hashes verify with **zero evidence errors and zero open local
failure groups**. Overall acceptance remains partial because external gates
have not run.

| Check | Result |
| --- | --- |
| Application Python | 260 total: 258 passed, 2 root-wrapper cases skipped |
| Tooling Python | 85 passed |
| Frontend | 43 Node tests; typecheck and build passed |
| Packaged browser flows | Setup, panel, dependencies, native settings, media, mixer, support and site passed |
| Native Linux OBS/audio/capture/game/idle | Passed; 18 filtered proof files, 15 distinct hashes |
| Actual bundled adapter → Go | 218 CPython checks and 240 simulated-frozen checks; 22 guarded Go calls per mode |
| Legacy/current install/update/removal | Both pinned Decky transport runs passed with preservation checks |
| Supplemental CLI and browser upgrades | Passed; optional Fish syntax unavailable/skipped |
| Normal-user frontend output absent/reused | All six typecheck/test/build commands passed; output owned by UID1000 |

The primary standard ZIP matches both repeated workflow builds and all 33 files
assembled by pinned official Decky CLI 0.0.7/default builder. Its SHA256 is
**cb6f923f6e22efed96f98f08522a9c6f90e5b4f8d6cf398e5c8afc724ec054b8**.
Runtime and updater artifact hashes, exact commands, platforms, pinned tools,
source hashes and all 15 criterion mappings are in the machine report/proof.
This is a local candidate, not a published release.

## Historical failures and limits

The first 339484a transport attempt overlapped host Go tests using port4457;
the overlap is confirmed, but the exact failing raw status was unavailable.
A later serial diagnostic passed installation/updater checks and found a real
cleanup failure: sibling imports and redundant helper chmod changed the selected
release-tree identity. The repair suppresses these self-changes while retaining
external-change refusal. Final aa323f0 serial transport passes unchanged guards.
The original failed evidence is retained.

ACT used measured resource assistance: only the active candidate container's
disposable compiler cache was cleared after builds/audits, before native tests.
This is not unassisted resource-policy proof for #104. All three temporarily
relocated caches were restored and package/network presets stayed unchanged.
Two caches have matching deterministic before/after hashes. PNPM restoration
completed with identical file count/bytes, but its first aggregate comparison
used unordered traversal; that digest cannot establish byte equality. The exact
limitation and corrected inventory are preserved. A private postcheck receipt
writer typo was corrected after all ten commands had passed; product code did
not change.

Hosted checks remain billing-unavailable with zero executed steps; actual PR
comparison is separately403. Actual Steam Deck/SteamOS/Flatpak OBS33/Gamescope/
AMD/controller/headset/provider playback and native non-Linux execution remain
unrun. In particular, #102-D4's real supported-loader startup remains #86:
source/unit lifecycle checks and pinned transport fixtures do not establish it.
No release, deployment, migration, Store submission, spending or consumer
adoption occurred. Settings boundary #103 and remaining artwork/UI/docs/#104/
#85 preparation are separate next work.
