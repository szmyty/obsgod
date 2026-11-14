# Identity and migration decisions

The owner selected **Decky Stream** as the working display name and deferred
the organization decision. No new organization, domain, repository transfer,
payment account or final brand asset has been created. This is an independent
community project; the name does not imply endorsement by Decky, Valve or OBS.
Name/mark availability and final asset approval remain open.

## Current identity map

| Surface | Current value | Treatment |
| --- | --- | --- |
| Display metadata | Decky Stream, `product.json` | One versioned build input |
| Repository/update trust | `szmyty/obsgod` | Retained until approved transition |
| Go module/import path | `github.com/szmyty/obsgod` | Compatibility identity |
| CLI and install command | `obsgod` | Retained alias |
| Decky loader name | `OBSGod` | Retained, affects routing/identity |
| Decky plugin directory | `obsgod` | Retained |
| XDG namespace | `obsgod` | Retained for keys/settings/state |
| Managed OBS profile/scenes/port | Existing `OBSGod` IDs, local 4457 | Retained |
| Historical download commits | Exact immutable SHAs | Retained by archive tags |

The Decky adapter consumes supplied plugin/user paths and metadata when available.
The Desktop installer and CLI share canonical XDG paths; they do not create a
second settings/key store under Decky's own adapter settings directory. Decky's
plugin runtime-data directory is persistent and is not `XDG_RUNTIME_DIR`.

## Preferred fresh-repository path

The owner now prefers a clean independent Decky Stream repository, with a fresh
initial commit and rewritten remaining issues. `egohygiene/decky-stream` is the
working destination discussed; no new repository, retirement or final brand
adoption has occurred. Keep [the memorial](../MEMORIAL.md) and its portable
tracker records with the new source; preserve attribution and every unfinished
criterion. A private backup in `szmyty/archive` cannot by itself preserve public
downloads. The old/new installer, settings and updater trust still need the
same explicit rehearsal below. See [the actionable plan](pre-migration-plan.md).

## Transfer or fresh-install transition preparation

Before changing the canonical repository or an installed ID:

1. Record the actual owner-approved destination, repository ownership, support
   identity, stable product ID and old-to-new map.
2. Inventory exact URL allowlists in `steamdeck/releases.py`, update manifests,
   immutable artifact links, Go imports, installer paths, Desktop entries,
   Decky routing/settings and managed OBS identifiers.
3. Prepare a transition build that trusts only the explicitly approved old and
   new identities. Do not weaken validation to arbitrary redirect destinations.
4. Rehearse old install -> transition -> new identity -> repair -> rollback ->
   uninstall, preserving settings/key binding, recordings and ordinary OBS.
5. Prove old/new plugins cannot concurrently control the same managed endpoint.
6. Obtain concrete owner approval for the transfer, final assets and publication.

There is no approved destination yet. A current-identity repair fixture or a
GitHub redirect is not proof that a future ownership migration works.

## Identity framework preparation

Use `egohygiene/identity` read-only and keep final consumer `.identity/` source
in the product repository. The framework inspected during planning was main
`401b2f1de298a171fbb5bf4ee6b510e0cf12c301`; stable v1.0.0 was distinct. Recheck
and pin a compatible immutable producer/profile version during final authoring.
Use supported manual v1 authoring, real approved SVG masters, creator/rights/
attribution facts, reproducible manifests and drift checks. Do not claim the
legacy initializer creates v1 or assume a built-in Decky profile exists.

Final organization/name, creative brief, rights and human asset approval precede
final art. The current metadata/UI/site work is provisional preparation, not
accepted Identity branding. No Identity repository modifications are required.
