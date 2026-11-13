# Decky Stream branding owner packet

Prepared 2026-11-13. Issues: #35 (owner/name), #38 (Identity kit), #43
(site). This is reviewable preparation, not creative approval or publication.

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

The candidate is original, simple SVG geometry: a mint play triangle and
transmission arc inside a dark rounded field. The monochrome Decky projection
uses the native foreground color, with no colored square or theme override.
Live product visuals remain unchanged while these candidates are reviewed.

Source/rights inventory: `.identity/candidates/inventory.json`. The geometry was
AI-assisted work authored by OpenAI Codex for this repository on 2026-11-13.
There is no copied Valve/Decky/OBS/provider logo. This describes the actual
method; it does not establish trademark clearance, human authorship, copyright
eligibility or a transfer of rights. MIT is proposed for owner review; no source
is falsely marked license-approved. DejaVu Sans supplies the draft wordmark
text; its separate Bitstream Vera/DejaVu notice is retained in the kit. No font
binary is redistributed.

```sh
python3 scripts/generate-brand-kit.py --raster
python3 scripts/generate-brand-kit.py --raster --check
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
cover master mark, native monochrome Decky icon, favicon 16/32, documentation
64, repository avatars 256/512, wordmark, GitHub 1280×640 preview, metadata,
palette, rights inventory, font notice, contrast report and size sheet.

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
