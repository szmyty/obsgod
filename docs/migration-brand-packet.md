# deckystream branding adoption packet

Keep the selected **01 / aurora** design: lowercase name, orbital stream mark,
midnight field and aqua/violet finish. This is the existing selected design,
not a request to create another logo. The [gallery and ordinary PNG kit](../branding/aurora/README.md)
already cover marks, small treatments, avatars, wordmark, README headers, social
preview, favicons and light/dark/focus samples. Original concepts remain intact.

## Concrete source and export inventory

| Item | Retained source / evidence |
| --- | --- |
| Selected direction | `.identity/candidates/concepts/selection.json` |
| Main vector | `.identity/candidates/aurora/mark.svg`, SHA-256 `f3b68d3937e49767a80415d98177f36f9d80adcd4b6cc8d0441ce0b87485a9c3` |
| Small vector | `.identity/candidates/aurora/mark-small.svg`, SHA-256 `e53ee844953468d21e8c7255bea8e1e18f715859ffb2eead6ae5d05ca9819356` |
| Retained generated hero | `.identity/candidates/aurora/hero-master.png`, SHA-256 `6b3c458e2f81b9d31435fcbc87c86e8f5c8ad7df579dfca34f578beac5e75b2c` |
| Actual generation details | `.identity/candidates/aurora/hero-generation.json`; original generated raster and separately authored vector remain distinct |
| Export inventory / rights | `branding/aurora/metadata/rights-and-sources.json` and the kit manifest; no owner/license approval invented |
| Product UI | Local compact SVG projection from `scripts/generate-aurora-ui.py`; streaming state stays a separate observed cue |
| Presentation | Light/dark README PNGs, offline site assets, gallery and flat PNG/full-kit downloads |

The vectors propose MIT subject to the owner's decision; the hero's proposed
license is currently null. Existing code and font notices remain unchanged.
Decide actual license/attribution treatment before production adoption; choosing
a palette or repository does not create those rights facts.

## Identity version boundary

Fresh follow-through inspection of the full releases collection found only
published stable **v1.0.0** and prerelease **v1.0.0-rc.2**. Upstream main is now
`ec8fce30c3c96c7781238eb0a8899d6f0cee0a40`; the
[Identity owner packet](https://github.com/egohygiene/identity/blob/ec8fce30c3c96c7781238eb0a8899d6f0cee0a40/docs/work/98/OWNER_PACKET.md)
still records **v1.1.0 as proposed**, an unselected release commit and Cargo
version 1.0.0. There are no newly qualified release artifacts to pin. The
anticipated release is not assumed published. The current consumer lock remains
`cfb6c29bd02589a47fc48050ab02e7e0da359719`, an explicitly unreleased additive
implementation supporting nullable guidance. Do not relabel it as v1.0.0.

After the owner's new release exists:

1. Resolve its exact tag/commit, checksums and supported consumer commands. Pin
   the actual release/tools instead of a moving branch; recheck its contracts.
2. Keep stable brand ID `decky-stream` and installed IDs unless a separate
   deliberate change is selected. Set the actual canonical project repository.
3. Adopt actual approved masters, matching digests, palette/token overrides,
   license/attribution and public usage decisions with their real subjects.
4. Use the supported production compiler/adoption route. The present local
   draft exporter intentionally rejects production approvals; filling the
   governance arrays and rerunning it is not an adoption method.
5. Keep raster hero handling separate where necessary: the inspected native
   bridge loads every provenance asset as UTF-8 lowercase SVG. A PNG provenance
   declaration alone does not make that compiler support raster. Use the actual
   released governed byte-copy/package route for raster assets if supported.
6. Generate/verify the native targets and product-specific exports, assemble
   the selected public kit and run drift/rights/source checks. Retain the exact
   commands/source/tool/artifact evidence and later actual Deck legibility.

GitHub native preview sizing inspected is 1280×640 under 999,999 bytes; web
favicon profiles include SVG plus 32/64 PNG. README headers, Decky marks and
other product exports need their own documented target choices. No built-in
Decky profile, native compiler output or production approval is invented here.

## Ready for review, not a second design exercise

The current kit can be checked with
`python3 scripts/generate-aurora-kit.py --raster --check` and
`python3 scripts/generate-aurora-ui.py --check`. Those checks establish source/
export consistency, not a published Identity adoption or artwork rights grant.
The remaining concrete inputs are the new release tag and actual asset license/
usage/publisher decisions. This packet changes no other repository or public site.
