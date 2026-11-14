# Engineering checkpoint before the new logo

Prepared 2026-11-14 UTC. Draft [PR #75](https://github.com/szmyty/obsgod/pull/75)
follows memorial #73 and presentation #74. This completes the current feasible
engineering pass; it does not close overall product acceptance or perform the
final full matrix, migration or publication.

The owner-directed sequence remains: **engineering → new logo ideas/artwork →
final full available tests → bug fixes/retests → migration**. Separate companion/
StreamGod and provider OAuth work are deferred, with original criteria retained.

## Delivered source and focused evidence

Engineering source is `4ac20bfd9e8b2fe17ab1942eeedd3fc78e38b6fb`, tree
`e621214690a8ff001e18ee69c20f56369f56e5eb`. Go integration checks ran at
`59665ad45629f4e2ee3e4b01fd9a6e184536dc5e`; no Go/module inputs changed between
those revisions. Later evidence-only notes do not relabel either revision.

| Lane | Result | Evidence and limits |
| --- | --- | --- |
| Legacy CLI / 9.AC2 | All 39 legacy operations now use a typed, allowlisted shared API/application compatibility path. Lazy injected dialing, exact ACK/output/request ordering and invocation approvals are retained. Acquired cancellation closes the owned socket promptly; queued cancellation leaves the active owner alone. | Six affected Go packages: **222 top-level tests / 456 pass events**, race/count1; one optional existing-OBS test skipped. Vet passed seven packages. Normal v1 confirmed-state/unknown-state behavior remains unchanged. SDK cleanup is not a join of every SDK worker. |
| Generic packaging / 12.AC4/5/7/8 | `.deb`, `.rpm`, `.apk` readers verify exact contents, notices/source metadata, modes, hashes, linked Go dependencies, SPDX and unsigned provenance. Strict RPM header allowlists reject scripts/triggers. | **10 NFPM + 12 generic tests**; actual Debian/Fedora/Alpine Linux amd64 install, repeated install, removal, eight installed-file hashes, UID65534 offline CLI and settings/media preservation passed. Three packages plus tar matched across independent builds; eight audit documents matched. Full 15-package/20-archive and other native targets remain for the final matrix. |
| Publisher migration / 36.AC1/2/3 | Update URLs derive from one build-selected repository identity. Current trust remains `szmyty/obsgod`; no environment override or arbitrary redirect is accepted. Real temporary files exercise old/new install, repair, update, rollback, corruption/interruption and scoped removal. | **7 new migration + 57 existing release/install/update/uninstall tests** passed. Decky/OBS/Flatpak/network boundaries are explicit fixtures. The future publisher is a separately loaded fixture, not an activated or created repository. Stable aliases/XDG/plugin IDs preserve one managed identity. |
| Brand opening compatibility / 38.AC3/4 preparation | Added a flat PNG-only pack and a self-contained offline gallery. The previous source/metadata ZIP was intact; the user's exact app/file failure is unknown. Existing artwork stays proposed while awaiting new logo ideas. | **11 tests**, CRC/mode/path checks, offline Chromium mobile/desktop galleries and all 14 extracted PNG decodes passed. All 11 previous repository PNGs stayed byte-identical. No phone-specific result or final brand approval is asserted. |
| History/backlog carry-forward | Added a bounded public-only exporter for the final retirement capture and all original criterion/dependency mappings. Existing frozen history is unchanged. | **10 focused tests** and a real development capture of 40 issues/35 PRs/41 comments/three reviews passed. All **230 criteria across 35 ledgers** remain verbatim, with null new-issue/acceptance fields. The actual retirement export remains for retirement. |

The `.deb`/`.rpm`/`.apk` A→B case is a genuine upward package-version upgrade
from source `4ea56460958f57e9bc014504e630c4d18394aa27` to `59665ad…`, checked
again with the clean final harness at `4ac20bf…`. A→C is separately labelled
replacement/downgrade: commit-hash snapshot versions are not chronological.
Repeated `apk add` is idempotence, not a claim that damaged files were repaired.

## Recorded repairs, including failed attempts

Focused execution found and repaired a real hung-request cancellation delay,
missing RPM script/trigger exclusions, umask-dependent packaged-document modes,
and inaccessible private artifact mounts under capability-restricted containers.
Debian's intentional document pruning and Fedora's read-only directory modes
needed narrowly scoped changes inside disposable test overlays. No capabilities,
host package-manager presets or original private artifact permissions were
weakened. An existing root-owned ignored catalog refused access; its attempted
preservation rename also failed without changes. Private staging avoids it, and
its hashes/owners/modes remain unchanged. The failed/debug attempts stay recorded
separately from final successful receipts.

## Review the files and receipts

- [Engineering/criterion mapping](evidence/pre-migration-engineering.json).
- [Package source, exact commands, artifacts, images and outcomes](evidence/pre-migration-nfpm.json).
- [58-member raw evidence ZIP](evidence/pre-migration-focused.zip), SHA-256
  `7d19bdf4d9740feea9ecf17e1717cb940315919aa29fb0da54b119f95af38f7f`.
- [PNG preview pack](../branding/repository/decky-stream-png-previews.zip),
  SHA-256 `cd7a4c1f14500a9ab37f4ae6de80ae720d2d3cb3516ff1ba91d356a5198db8ad`.
- [Standalone gallery](../branding/repository/index.html): download and open the
  HTML locally in a browser; it needs no neighboring files or network.
- [History export commands and exclusions](history/README.md).

Inventories/checksums are unsigned self-reported evidence, not authenticated
publisher attestations. The original ledger and historical runtime receipts
remain unchanged; old passing results do not qualify this newer source.

## What remains, in the agreed order

1. Receive the owner's new logo direction; prepare and review the actual source,
   rights/usage facts and asset choice. Then regenerate/apply the accepted kit
   through the pinned Identity path without inventing an approval.
2. Freeze the resulting candidate and run the complete required available local
   matrix, including both retained ACT sequences, full builds/packages, browsers,
   native Linux OBS/capture/audio and update/recovery checks. Repair failures and
   rerun the applicable checks. **This final matrix is intentionally unrun now.**
3. Prepare the exact fresh-repository/source/installer candidate, preserve public
   old artifact URLs and every unfinished criterion, then perform the authorized
   migration and verify its real paths/downloads/install/update behavior. A new
   `main` branch avoids needing to rename the old archive's `master` first.

Collect available actual Deck/OBS33/Flatpak/Gamescope/controller/headset/session,
audible local media, independent viewer and adoption evidence during qualification.
Missing native-platform/review/rights/publisher/consumer evidence remains an
explicit product acceptance gate and carries into the new tracker. It does not
become a newly invented prerequisite for creating the fresh source repository.

Hosted Actions remain unavailable under the billing lock. The fork-specific
dependency-review API restriction still exists here; verify the graph/API in the
future standalone public repository. Neither spending nor repeated known billing
refusals is part of this plan. Releases/sites remain unpublished, no new repository
was created, and #46 remains open for actual remaining acceptance.
