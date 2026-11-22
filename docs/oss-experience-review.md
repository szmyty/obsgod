# OSS experience review — #117

Reviewed source: `878b25ea645192d29b3d2ac727de05487c4db97b`, based on
`f4561aaaf131b4bfe94d1aa02834890e8884a104`. [PR #118](https://github.com/szmyty/obsgod/pull/118)
contains documentation, issue/PR templates and a testing-PDF preface. Later
review-record commits do not change the runtime candidate `772230a` or its
immutable `430cc391` artifact. No runtime qualification is claimed here.

## What improved

New visitors can choose a Steam Deck, generic CLI, contribution or help route
from the README. The documentation map groups user tasks, developer contracts,
qualification and history. Contributor guidance gives relevant source locations
and proportionate checks. Separate Deck/CLI/feature forms request safe reports.
Three old installer records retain their original content under visible
historical banners. The owner moved testing after migration; current overview
documents, the Markdown booklet and a new PDF preface record that amendment.

## Criterion review

| Criterion | Evidence and result |
| --- | --- |
| OSS-1 | README has four directly labelled audience routes and the pinned current review package. Passed. |
| OSS-2 | `docs/README.md` groups current guides, developer contracts and evidence/history without duplicating contracts. Passed. |
| OSS-3 | README/index/contributor guidance distinguish display name, compatibility names, standard ZIP and optional Desktop tools. Passed. |
| OSS-4 | Independent route walk reached packet/checksums, standard ZIP, private setup/local clip and help without an old installer. Passed. |
| OSS-5 | Explicit Start, local audiovisual checks, separate viewer, game-only audio limits and preview/UNRUN status remain. Passed. |
| OSS-6 | Historical banners were inserted in three guides; removing only those banners yields each original file exactly. Passed. |
| OSS-7 | Contributor docs/CLI/Decky routes link source and existing scoped checks; prose edits require no runtime matrix. Passed. |
| OSS-8 | Three parsed issue forms cover Deck, CLI and feature requests, with security routing and credential warnings; PR guidance requires applicable criterion evidence. Passed. |
| OSS-9 | Support/security/license links and existing five-provider funding remain consistent; Patreon inactive, wallets hidden. Passed. |
| OSS-10 | Reviewed headings, link labels, image alternatives and local light/dark/mobile reading order. Passed within the documented render scope. |
| OSS-11 | Local link/form/render checks and independent four-audience walkthrough are recorded below at the named source. Passed. |
| OSS-12 | Current roadmap, continuity, instructions and decision record document the owner's amended journey and remaining destination facts. This review supplies the handoff. Passed. |

## Checks and practical limits

Platform: Linux x86_64; Python 3.12.14; PyYAML 6.0.3; Pandoc 3.1.11.1;
Playwright 1.62.0 using installed Chromium 151.0.7922.173 for local document
previews. The Markdown-to-HTML preview is not a GitHub or Steam rendering claim.

- **Passed:** 291 local links/assets/heading anchors across the changed public
  Markdown surfaces; three issue forms and 12 unique per-form field IDs;
  original historical-guide contents; `git diff --check`.
- **Passed:** 12 local preview views: README, docs index, contributing and
  support, each at 1280px light/dark and 390px light. No broken images or
  whole-page horizontal overflow; wide tables remain horizontally scrollable.
  The README/index/contributor previews and PDF preface were visually inspected.
- **Passed:** independent Deck, CLI, contributor and help route walks. A stale
  booklet sequence found during review was corrected before acceptance.
- **Passed:** the updated technical PDF reads as 13 pages: one explicit
  sequence-amendment preface followed by the original 12 pages. All original
  page text, 28 named destinations and seven external URIs were retained. The
  original PDF remains available at immutable `f4561aa`.
- **Passed:** `node scripts/generate-support.mjs --check`,
  `python3 scripts/generate-product.py --check` and
  `python3 scripts/generate-aurora-ui.py --check`.
- **Unrun:** live GitHub issue-form rendering, HTTP verification/payment
  readiness of external support destinations, and actual Deck/controller/
  provider tests. Funding URLs are configured recipient links, not payout proof.
- **Unavailable/separate:** hosted Actions and the complete ACT/platform/service
  matrix. Read-only inspection at `878b25e` found 14 billing-locked check
  failures, one dependency-review skip and zero executed steps; no non-billing
  failed job ran. Their absence does not become a documentation failure or a passing
  runtime result. No runtime change justified repeating the existing product
  qualification for this bounded documentation issue.

The detailed local link/render/PDF receipts are retained in the private
`/workspace/.obsgod-tools/oss-polish-117` workspace. No private logs, credentials,
wipe exports or payment data are part of this review.

## Remaining journey

The approved sequence is polish → branding/migration preparation → exact
owner-run fresh repository → finalization/testing/fixes → release decision →
legacy retirement, with #89 separate. Exact organization, the anticipated
Identity release, final source/rights/publisher facts and destination-specific
trust handling remain real preparation work. This issue does not mark #85,
#86, #87, #95 or #88 passed, publish a release or delete the old repository.
