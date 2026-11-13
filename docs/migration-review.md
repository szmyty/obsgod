# Repository and name migration rehearsal packet

Issues #35/#36. This is a staged plan and local compatibility inventory. It does
not transfer or rename a repository, create an organization, deploy a site, or
publish a release. Intended slug: `decky-stream`; display: **Decky Stream**.
Current source/release trust stays `szmyty/obsgod` until the new owner and exact
repository are chosen, authorized and tested.

## Compatibility inventory

| Surface | Current / intended behavior |
| --- | --- |
| Human display | `Decky Stream`, centralized in `product.json` and generated projections. |
| Current repository | `szmyty/obsgod`; owner of a future `<owner>/decky-stream` is unresolved. |
| CLI / package artifact names | `obsgod`, `obsgod-deck_VERSION_linux_amd64.tar.gz`, `obsgod-decky.zip`; preserve old entry points/artifacts during transition. |
| Decky plugin | Plugin identity `OBSGod`, installed directory `obsgod`; preserve one instance controlling the managed endpoint. |
| XDG application paths | `obsgod` under config/data/state/cache roots; retain existing private credentials, connection/profiles, receipts, clip index and history. |
| Temporary IPC / Decky context | Existing private runtime paths; documented Decky user/plugin environment stays authoritative for the adapter. |
| Managed OBS | Existing private Flatpak configuration and managed scene/input/profile names; leave ordinary OBS and unrelated plugins alone. |
| Media | Existing XDG Videos `OBSGod` default and selected custom directory; never rename or delete shared media as a side effect of branding. |
| Desktop launchers / updater | Existing launch paths, current symlink, retained installs/backups and uninstall inventory must remain recognized. |
| Public API / secrets | Existing protocol routes/config formats and stream-key/OBS-password pairing; display renaming must not start output or reset secrets. |

`product.json` is product metadata, not an environment variable. Operational
configuration uses documented CLI/file/environment precedence; a runtime
environment variable must not silently change update trust or installed IDs.

## Narrow release trust contract

Before any move, choose exactly one new canonical `OWNER/decky-stream`. A staged
transition must enumerate the exact old and new owners/repos, supported release
tags and bounded sunset policy. No `*/decky-stream`, arbitrary GitHub owner,
user-supplied download URL, generic redirect trust or mutable branch artifact
should become an accepted updater source.

Current checks inspect release-list URL, resolved release tag revision,
manifest/version/platform/file digests, archive digest, supported asset names,
and immutable historical artifact commits. The transfer rehearsal must preserve
their agreement across:

- `api.github.com/repos/OWNER/REPO/releases?per_page=100` and the exact tag's
  `commits/TAG` API path;
- `github.com/OWNER/REPO/releases/download/TAG/ASSET` release destinations;
- `raw.githubusercontent.com/OWNER/REPO/FULL_COMMIT/ASSET` historical artifacts;
- redirected final hosts/paths and the release metadata's canonical identity;
- package manifest source revision, updater version and trusted repository fields.

The current candidate explicitly rejects moved API/raw/repository redirects
before following them. A single hop from an already validated current-project
release-asset URL to the official GitHub release-asset CDN is permitted only for
its bounded asset path. An arbitrary host, a new repository and a second hop do
not inherit trust. Redirect tests exercise the permitted signed-CDN route and
rejected moved/unrelated destinations. This closes the current implicit-redirect
gap; it does not activate a future owner or qualify a repository transfer.

Any new repository identity, redirect or signing/provenance scheme must be tested
as part of the transition. Checksums prove transport integrity relative to the
trusted metadata; they are not independent signatures. A repository redirect by
itself neither repairs the old hard-coded path checks nor proves new ownership.
Leave activation blocked while the exact destination is unknown. Existing
immutable old releases and source/artifact refs must remain recoverable.

## Disposable rehearsal, before an external rename

Use an isolated user-home fixture with copies of nonsecret synthetic settings,
two fake secret sentinels, profiles, state/clip index/history, one ordinary OBS
profile, another Decky plugin and representative finalized/interrupted media.
Never copy a real stream key into the fixture or a report. Record exact old,
transition and new source/artifact revisions plus commands/platform/outcomes.

1. Install the current old-identity artifact. Confirm app/plugin/updater versions,
   one plugin folder, synthetic credentials and all sentinel paths.
2. Offer a narrowly trusted transition artifact through the old identity. Check
   without installing; then upgrade with every output positively stopped. Verify
   the three package versions, same private paths, preserved secret pair and one
   endpoint owner. Repair the same version twice and compare ownership inventory.
3. Offer the new canonical identity through the bounded policy. Reject an
   unlisted owner, unrelated redirected host/path, mixed old/new metadata, moving
   tag, bad digest, unsafe archive, missing source/artifact and offline response.
   Failures must preserve the installed version and stopped/unknown-output rules.
4. Rehearse retained rollback to the exact prior artifact. Confirm version,
   settings/profiles, secrets, media and ordinary OBS/other plugin sentinels.
   Roll forward and repair again; no duplicate plugin or controller may appear.
5. Dry-run uninstall. Normal uninstall preserves settings/media/history; reset
   and wipe affect only documented owned paths after separate explicit choices.
   Verify ordinary OBS, other plugins, custom/shared media and unselected files.
6. On a real Deck, repeat upgrade/repair/rollback across Gaming/Desktop sessions,
   make an audible local clip and explicitly confirm start/stop on a viewer.
   Fixture success does not establish Flatpak/Decky permissions or hardware proof.

Existing installer/updater/unit smoke checks can cover old-identity behavior.
They are not a completed old→transition→new receipt until the actual new identity
and candidate are supplied and exercised. Keep that criterion open.

## Exact owner checklist for the future move

- Choose the organization, who can administer it, repository destination and
  canonical support/contact/domain. Confirm access and transfer authority.
- Approve the exact transition source/artifact, trust allowlist, retention window,
  user notice and rollback artifact after the local and device rehearsal passes.
- Inspect GitHub rulesets/protection, Actions permissions/secrets/environments,
  release/tag behavior, Pages domains and auto-publish/deploy side effects on the
  proposed destination. Obtain separate release/deployment approval.
- Transfer/rename through GitHub only after the approved transition is available
  to existing users; record old/new repository IDs, redirects and exact time.
- Update the remote only after verifying GitHub's new canonical repository ID:
  `git remote set-url origin https://github.com/OWNER/decky-stream.git`.
  `OWNER` is a deliberately unresolved value, not an executable recommendation.
- Requery live APIs/refs/releases/protection and verify historical artifacts,
  fresh install, old updater transition, repair, rollback, uninstall and docs
  links on the actual destination. Publish only with exact owner approval.
- Keep old artifact/source refs and documented recovery until the approved sunset
  criteria are met. Do not remove old IDs solely to make names look consistent.

This packet supplies a reviewable path while preserving current installs. Owner
choice, narrow trust activation, real transition receipt and external move remain
explicit gates; no fictional organization or success receipt fills them.
