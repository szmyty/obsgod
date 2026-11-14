# Proposed Decky Stream brand kit

The editable candidates and honest rights inventory are in
[`.identity/candidates`](../.identity/candidates/). They are **unapproved** and do
not replace the product's existing visual baseline or native Decky icon.

The mint-signal concept was generated in chat on 2026-11-14. Its original PNG,
full prompt, method and digest are retained in
[the concept record](../.identity/candidates/concepts/mint-signal-board.json).
The separately authored SVG master projects to the repository assets below;
the concept board is not a screenshot or an approved compiler input.

The [tracked review assets](repository/README.md) include dark/light README
headers, mark/transparent/light variants, monochrome icon, wordmark, avatars,
16/32/64 favicons and the 1280×640 GitHub preview. The README uses the PNG
headers for exact font rendering with an accessible text fallback.

Prepare review artifacts locally, with no network:

```sh
python3 scripts/generate-brand-kit.py
python3 scripts/generate-brand-kit.py --check
python3 branding/tests/test_brand_kit.py
```

After obtaining the immutable validator and verifying its lock-file digest,
record portable source-contract evidence without downloads or installation:

```sh
python3 scripts/generate-brand-identity-proof.py --validator /path/to/verified/validate_identity.py
```

`evidence/identity-source.json` is the initial content-bound result. Re-run it
after source edits; it does not qualify candidate art or a runtime revision.

For all raster exports, use the exact Inkscape/font pins in
`.identity/toolchain.lock.json`, then run:

```sh
python3 scripts/generate-brand-kit.py --raster
python3 scripts/generate-brand-kit.py --raster --check
```

Stage the bounded repository projection and verify it without rewriting:

```sh
python3 scripts/generate-brand-kit.py --raster --repository-assets
python3 scripts/generate-brand-kit.py --raster --repository-assets --check
```

Its manifest binds all sources and 27 output files; the manifest itself is the
28th staged file. The exporter preserves unrelated files and refuses unsafe or
symlinked destinations. Do not modify generated artwork or hashes by hand.

Default output: `dist/branding-draft/`. Open `review/index.html` locally; the ZIP
is `decky-stream-proposed.zip`. Both are preparation artifacts. The content-bound
manifest records every source and export hash; identical inputs with the same
pinned raster tools produce identical bytes. SHA-256 integrity is not a creator
signature or human approval. The archive has fixed paths, timestamps and file
modes and contains no fonts, secrets, scripts or remote assets.

Draft profiles: source mark SVG, native monochrome Decky SVG, favicon SVG plus
16/32/64 PNG, transparent/light mark variants, 64px documentation mark,
256/512px repository avatar, wordmark SVG/PNG, 1600×600 dark/light README headers,
1280×640 GitHub preview SVG/PNG, candidate palette CSS/JSON, metadata, rights,
font notice, contrast report and actual-size 16/24/32/64/128 review sheet.
The wordmark is editable SVG text using the pinned DejaVu Sans face; it is not
an outline-only portable logotype. Use its raster projection for exact preview,
or approve and produce a portable outline master before production adoption.

Core/tokens/metadata/web/docs/GitHub source profiles are selected in the Identity
consumer declaration. The Decky icon is a local custom draft profile. None is
claimed to be verified production output from the upstream Identity compiler.
The [current specification review](../.identity/references/specification-review.json)
separates native v1 dimensions from product-specific draft exports: native `web`
uses SVG plus 32/64 PNG favicons; `github` uses a 1280×640 PNG under 1,000,000 bytes;
native `docs` produces document CSS. README headers, avatars, wordmark and
monochrome Decky art are custom exports. PWA and generic social profiles are not
selected for this bounded plugin kit.
See [the owner review packet](../docs/branding-review.md) before adopting any art.
