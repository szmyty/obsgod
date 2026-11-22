# Selected aurora source preview

The owner selected **01 / aurora**: an open orbital ring, flowing S-shaped stream
ribbon, aqua/violet finish and a near-black field. The source-preview display is
lowercase **deckystream**. Stable brand ID `decky-stream`, installed `obsgod` /
`OBSGod` names, repository trust and storage remain compatible.

Read the [exact-source local results and remaining device/rights gates](aurora-integration-checkpoint.md)
and [current review packet](aurora-owner-packet.md).

## Source and exports

- [Original selection and exact references](../.identity/candidates/concepts/selection.json)
  remain unchanged, alongside mint-signal and the other retained concepts.
- [Selected source inventory](../.identity/candidates/aurora/inventory.json) records
  separately authored vector geometry and its relationship to those references.
  The vector is an interpretation, not automatic or identical raster conversion.
- [Hero generation](../.identity/candidates/aurora/hero-generation.json) records one
  actual image-generation operation. Its retained PNG is an input; image
  generation itself is not claimed reproducible.
- [Selected exports](../branding/aurora/README.md) include ordinary PNGs, a flat
  PNG download ZIP, full kit ZIP and self-contained offline gallery. The
  manifest binds input/output hashes and the pinned rasterizer/font.

The main mark has controlled depth. Compact 16/24/32/64 treatments omit glow.
Transparent artwork needs an appropriate field; light variants deliberately use
a dark inset plate for the gradient. Actual-size sheets show normal and focused
dark-menu samples. These are rendered samples, not Steam Deck screenshots.
No new font binary is redistributed; the font notice accompanies the exports.

Reproduce with the existing pinned Inkscape1.4 and DejaVu Sans hash in the lock:

```sh
python3 scripts/generate-aurora-kit.py --raster
python3 scripts/generate-aurora-ui.py
python3 scripts/generate-product.py
```

Read-only checks:

```sh
python3 scripts/generate-aurora-kit.py --raster --check
python3 scripts/generate-aurora-ui.py --check
python3 scripts/generate-product.py --check
```

The selected exporter owns only `branding/aurora/`. It refuses foreign profiles,
unsafe paths, active/external SVG content and linked output files, and uses
atomic replacement. The old mint kit and its receipts remain historical;
regenerating it is not part of this profile.

## Product integration

The native panel bundles a local SVG data URI: no external asset/font request or
SVG loader is required. A separate observed-state badge retains its text/color
and notification semantics; decorative aqua/violet is not a streaming cue.
The header uses the same compact mark and generated lowercase display metadata.
Saving settings, installing assets and navigating guides never authorize output.

The README and offline site use selected PNGs. PNG projections validate bounded
dimensions, chunk checksums, complete compressed rows and a static RGB/RGBA
profile. Site pages still prohibit remote assets, inline scripts/styles and
connections. Existing required tests and package/network presets remain.

## Rights and publication facts

| Fact | Current disposition |
| --- | --- |
| Creative direction | Owner selected 01 / aurora; final production artwork/device adoption is separate |
| Actual authors/tools | Recorded image-generation operation; separately authored Codex vector/source; pinned Inkscape/font exports |
| Source contract | Manually authored Identity v1 consumer source, checked with the existing immutable validator pin; no production compiler claim |
| Governance | Approval/provenance decisions and adopted token layers remain empty; no organization palette or approval invented |
| Rights/license | Existing code/font notices retained; final artwork rights/license treatment and name clearance remain owner facts |
| Destination/publisher | Current repository remains `szmyty/obsgod`; future slug `deckystream`, destination owner/organization unresolved |
| Consumer/target proof | Actual Decky/SteamOS/controller/headset/provider and new-install adoption remain the owner test/migration gates |

Source/export checks support a reviewable candidate, not a rights grant or product
release. The owner now prepares/migrates before final testing; see the
[brand adoption packet](migration-brand-packet.md) and [active roadmap](../ROADMAP.md).
Final source qualification and machine/Steam Deck observations remain explicit
in the carried-forward finalization checklist. All 230 original criteria/dependencies
remain intact. No Identity repository change, release, deployment, migration,
Store submission or paid resource is performed by these tools.
