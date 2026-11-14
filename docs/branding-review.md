# Decky Stream branding owner packet

Prepared 2026-11-13. Issues: #35 (owner/name), #38 (Identity kit), #43
(site). This is reviewable preparation, not creative approval or publication.

Refreshed 2026-11-14 UTC: the live Identity pin is unchanged. The owner requested
asset generation in chat and repository presentation before a fresh Decky Stream
repository. The new mint-signal board, prompt/method/hash record and separately
authored editable SVG candidates are under `.identity/candidates/`. The README
uses staged draft artwork; installed plugin visuals and empty approval arrays
are unchanged. See [remaining work](pre-migration-plan.md).

## Presentation validation checkpoint

Exact presentation source `f3d2413b5f72aa858992996839aa8569ac5db331`
passed the [recorded checks](../branding/evidence/presentation-review.json):
nine exporter tests, pinned source-contract validation, both raster drift
checks, support/product metadata and an independent byte-identical 33-file
repeat. All 20 input hashes, 27 staged output hashes, 83 relative links,
10 self-contained SVGs, PNG dimensions/byte cap and concept digest passed.
The imported font notice is byte-identical to its source; only that new copy's
upstream trailing whitespace is excluded from whitespace lint.

Full-kit ZIP SHA-256:
`fd92a99f1a0a09182a0f519a39f40847b378621b5a002a6c918f6236d68d7f36`.
This is draft artwork validation, not runtime/device qualification or human
creative/rights approval. Later evidence-only notes do not relabel that source.

## Verified facts and unresolved decisions

| Item | Evidence / disposition |
| --- | --- |
| User-facing name | User selected **Decky Stream** and requested intended slug **decky-stream**. `product.json` already supplies the display name. |
| Current source and release trust | `https://github.com/szmyty/obsgod`; no repository transfer or rename is performed by this packet. |
| Organization | Not selected. No new organization identity, authorization, license holder or inherited palette is invented. |
| Stable local identifiers | CLI/storage namespace `obsgod`, plugin `OBSGod`, directory `obsgod`, existing OBS managed object names and media locations remain compatible. |
| Product boundary | Local OBS control core with a Steam Deck/Decky adapter. No affiliation with Valve, Decky or OBS is asserted. |
| Support/contact | Existing reviewed funding metadata remains the source. New wallets, payees, contact addresses and support commitments require owner facts. |
| Domain/hosting | None selected or provisioned. Local preview is ready; deployment needs separate owner authorization. |
| Creative/rights | New candidates are explicitly unapproved; human creative, rights/license and name-clearance decisions remain. |

The final issue should link the owner's actual name/org/rights decision and exact
artifact digest. A merge of this preparation must not be used as that decision.

## Identity source and exact toolchain

Read-only inspection found Identity live main
`cfb6c29bd02589a47fc48050ab02e7e0da359719`. The older local checkout was not used
as authority. Published stable is still `v1.0.0`; current nullable-guidance
authoring is additive source, not a claim about that stable release.

`.identity/toolchain.lock.json` records immutable source URLs and SHA-256 values
for the manual authoring docs, validator, five schemas and upstream license.
Validator pin:
`aea7ba3ff1f331acb0cf2d05501c56c4d89c15ad41c8c57b4fd7448b323175f5`.
It runs with Python's standard library, without network or pip. The nullable
guidance declaration, empty adopted token layers and empty governance arrays
are intentional. No example fictional approvals or sample artwork were copied.

Initial exact-source command (the verified tool is outside the consumer repo):

```sh
python3 /path/to/verified/validate_identity.py --repository-root . --format json --snapshot
```

Source validity is separate from rights, human approval and output generation.
The local draft exporter is not Identity's production compiler. Core, tokens,
metadata, web, docs and GitHub source profiles are selected at version `1.0.0`;
the monochrome Decky projection is a local custom draft profile. PWA, social
campaigns and broad archives are not required for this bounded plugin kit.

## Proposed creative kit

The candidate is original, simple SVG geometry: a mint play triangle and two
transmission arcs inside a rounded outline on deep ink. The monochrome Decky projection
uses the native foreground color, with no colored square or theme override.
Live product visuals remain unchanged while these candidates are reviewed.

Source/rights inventory: `.identity/candidates/inventory.json`. The geometry was
AI-assisted work authored by OpenAI Codex for this repository and refined for
the 2026-11-14 mint-signal concept. The generated PNG concept board has its own
complete prompt, image-generation method and digest in
`.identity/candidates/concepts/mint-signal-board.json`. It is a review reference,
not an approved SVG source or a native Identity compiler output. Its status
rows are design concepts, not product screenshots.
There is no copied Valve/Decky/OBS/provider logo. This describes the actual
method; it does not establish trademark clearance, human authorship, copyright
eligibility or a transfer of rights. MIT is proposed for owner review; no source
is falsely marked license-approved. DejaVu Sans supplies the draft wordmark
text; its separate Bitstream Vera/DejaVu notice is retained in the kit. No font
binary is redistributed.

```sh
python3 scripts/generate-brand-kit.py --raster
python3 scripts/generate-brand-kit.py --raster --check
python3 scripts/generate-brand-kit.py --raster --repository-assets
python3 scripts/generate-brand-kit.py --raster --repository-assets --check
python3 branding/tests/test_brand_kit.py
```

The raster path requires Inkscape `1.4 (e7c3feb100, 2024-10-09)` and exact font
SHA-256 `57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e`.
SVG-only preparation is available without those tools. A mismatching raster
toolchain fails explicitly. The generated manifest binds source bytes and every
export; ZIP metadata is deterministic. `--check` is read-only. The exporter
refuses foreign output files and symbolic links. Recovery is to rebuild the
known generated directory from reviewed source, not to edit hashes manually.

Review `dist/branding-draft/review/index.html` and the companion ZIP. Exports
cover master/transparent/light marks, native monochrome Decky icon, favicon
16/32/64, documentation 64, repository avatars 256/512, wordmark, dark/light
1600×600 README headers, GitHub 1280×640 preview, metadata, palette, rights
inventory, font notice, contrast report and size sheet. The full raster kit has
33 files; the tracked `branding/repository/` projection has 28 files including
its manifest. GitHub PNG size is checked against the native v1 999,999-byte cap.

The current [specification review](../.identity/references/specification-review.json)
records immutable upstream sources. Native v1 `web` and `github` dimensions
inform these draft projections; native `docs` produces document CSS. README
headers, avatars, wordmark and Decky monochrome art are useful product-specific
exports, not native compiler target claims. Generic social and PWA exports are
not selected. The live Identity pin is unchanged; no Identity repository was
modified or approval invented.

## Review checklist before adoption

- Owner: accept/change name, stable ID, actual organization and current repository
  disposition. Check name/trademark availability as appropriate to the chosen use.
- Owner: accept/change the creative direction and AI-assisted creation method;
  decide license, attribution and any additional creator/rights facts.
- Reviewer on Deck: inspect native foreground icon at 16/24/32px in actual theme,
  readable labels, focus order and controller targets. Inspect favicon and GitHub
  crops, ordinary/reduced-motion layouts and wordmark readability. Draft normal
  text palette pairs are checked numerically; that is not device legibility proof.
- Designer/owner: if retaining the wordmark, approve an outline master for portable
  production use. The current SVG text has a pinned raster projection but may
  render differently on systems without the font.
- Maintainer: record an actual same-subject human approval and source provenance
  with exact digest/license/creator/method/usage/accessibility. Promote only that
  approved source through the pinned Identity generation and verify path.
- Maintainer: apply only approved outputs consistently to repository/docs/site
  and the native plugin projection, then rerun drift, link, contrast, browser and
  real-device checks on that revision.
- Owner: approve exact publication destinations and responsible owners. Publishing
  the brand, site, runtime release or repository rename is a separate action.

The remaining owner gates are concrete: organization/repository decision,
creative/rights/license decision, final mark/wordmark decision, contact/domain/
hosting selection, native Deck review and exact publication authorization.
