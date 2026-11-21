# Optional printable booklet export

The editable guide is [testing-booklet.md](../testing-booklet.md). Its PDF uses
Pandoc 3.1.11.1, XeTeX from TeX Live 2025 and DejaVu Sans/DejaVu Sans Mono.
These are optional maintainer documentation tools, not Steam Deck prerequisites
or new requirements for the plugin's ordinary builds.

From the repository root:

```sh
SOURCE_DATE_EPOCH=$(git show -s --format=%ct a2137bf214c77efda3ce3fb87879f88004c6477c) \
FORCE_SOURCE_DATE=1 \
pandoc docs/testing-booklet.md --from=gfm --pdf-engine=xelatex \
  --lua-filter=docs/booklet-export/layout.lua \
  --include-in-header=docs/booklet-export/header.tex \
  --metadata title='deckystream: testing together' --metadata date='' \
  --variable papersize=letter --variable geometry:margin=18mm \
  --variable fontsize=11pt --variable mainfont='DejaVu Sans' \
  --variable monofont='DejaVu Sans Mono' \
  --output docs/testing-booklet.pdf
```

Keep the guide, PDF and export receipt together. Review every page boundary,
links and extracted text after changing the guide; regenerate the receipt's
hashes. The export is a guide, not an executed test or a new product build.
The filter resolves appendix links against the recorded source baseline so
they work when the PDF is opened outside the checkout. A fixed source epoch
stabilizes metadata; byte-for-byte PDF reproducibility is not asserted.
