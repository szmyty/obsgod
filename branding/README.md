# Proposed Decky Stream brand kit

The editable candidates and honest rights inventory are in
[`.identity/candidates`](../.identity/candidates/). They are **unapproved** and do
not replace the product's existing visual baseline or native Decky icon.

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

Default output: `dist/branding-draft/`. Open `review/index.html` locally; the ZIP
is `decky-stream-proposed.zip`. Both are preparation artifacts. The content-bound
manifest records every source and export hash; identical inputs with the same
pinned raster tools produce identical bytes. SHA-256 integrity is not a creator
signature or human approval. The archive has fixed paths, timestamps and file
modes and contains no fonts, secrets, scripts or remote assets.

Draft profiles: source mark SVG, native monochrome Decky SVG, favicon SVG plus
16/32 PNG, 64px documentation mark, 256/512px repository avatar, wordmark SVG/PNG,
1280×640 GitHub preview SVG/PNG, candidate palette CSS/JSON, metadata, rights,
font notice, contrast report and actual-size 16/24/32/64/128 review sheet.
The wordmark is editable SVG text using the pinned DejaVu Sans face; it is not
an outline-only portable logotype. Use its raster projection for exact preview,
or approve and produce a portable outline master before production adoption.

Core/tokens/metadata/web/docs/GitHub source profiles are selected in the Identity
consumer declaration. The Decky icon is a local custom draft profile. None is
claimed to be verified production output from the upstream Identity compiler.
See [the owner review packet](../docs/branding-review.md) before adopting any art.
