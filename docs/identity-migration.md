# Identity and migration decisions

The owner selected lowercase **deckystream** display styling and the 01 / aurora
creative direction, while deferring the organization decision. Selected
source/export candidates are implemented; final production rights/adoption
remain separate. No new organization, domain, repository transfer or payment
account has been created. This is an independent
community project; the name does not imply endorsement by Decky, Valve or OBS.
Name/mark availability and final asset approval remain open.

## Current identity map

| Surface | Current value | Treatment |
| --- | --- | --- |
| Display metadata | deckystream, `product.json` | One versioned build input; installed IDs unchanged |
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
initial commit and rewritten remaining issues. The intended repository name is
`deckystream` (owner preference updated 2026-11-14); `egohygiene` is the working
owner discussed, not a finalized destination. No new repository, retirement or final brand
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
in the product repository. The earlier planning pin was `401b2f1`; the actual
consumer lock pins immutable source **cfb6c29bd02589a47fc48050ab02e7e0da359719**,
including the hash-verified validator. It is an additive source implementation,
not a claim about published stable v1.0.0. The current candidate uses supported
manual v1 authoring, separately authored SVG geometry, actual creator/rights/
attribution facts, reproducible manifests and drift checks. Do not claim the
legacy initializer creates v1 or assume a built-in Decky profile exists.

Creative direction and lowercase display are selected. Candidate source/export
work is reviewable; final rights/license, publisher, production adoption and
actual device rendering remain owner/evidence facts. Empty governance arrays
are not filled with invented approvals. See [selected aurora](selected-aurora.md).
No Identity repository modification or accepted production compiler claim is made.
