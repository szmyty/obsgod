# Independent aurora acceptance review

Frozen source `af7a20fdd0c62404e9b11d540fb605368e269380` / tree `d6149d9ec670cffcc30db355262aa688382b5e7e`, clean 617-file inventory. Draft PR #113; #80 and #81 were both OPEN at the fresh issue observations. No GitHub action, source change or test rerun was performed by this reviewer.

**Result:** no blocking local source or inspected visual defect. The seven #80 and fourteen #81 literal local criteria have applicable passed evidence, with the stated unavailable/device/rights limits. This is not formal GitHub approval, issue closure, target-device acceptance, rights clearance or publication permission.

The separate full available qualification controller is completed; its exact report is bound below.

Canonical primary ZIP SHA256: `4deece2bcaba6440c168d5cb7b1bc585e346d6b2f06655a1672c0d9638afeab8`. Primary receipt SHA256: `d23cb8f370fbae5cf84dae9ffa137a0c22e7a71c900588ad4baf9e8eea0ca30a`.

## Criterion mapping

### 80-C1

Use .identity/candidates/concepts/selection.json and exact retained PNG hashes as the creative reference; keep mint-signal, the original orbital board/icon and alternatives accessible as concepts.

**supported-local-evidence-with-explicit-limits**. Selection binds exact original board, icon and selected 01 comparison PNG digests. Independent byte comparison against merged 069 verified all 41 retained mint/concept files unchanged; the current 617-file source inventory also matches.

Source: `.identity/candidates/concepts/selection.json`, `.identity/candidates/aurora/inventory.json`, `branding/repository`, `.identity/candidates/concepts`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`.

Limits: Direction approval is a creative-reference fact only.

### 80-C2

Finalize traceable selected source artwork and user-facing lowercase deckystream wordmark. Distinguish original raster masters from any separately authored vector geometry; do not claim automatic or identical PNG-to-SVG conversion.

**supported-local-evidence-with-explicit-limits**. Separately authored Codex vectors and a single unchanged image_gen raster master have distinct source hashes and actual creator/method records. Generated wordmark and user-facing product display are lowercase deckystream. The selected vector visibly interprets the orbital S motif; it is not an identical raster conversion.

Source: `.identity/candidates/aurora/mark.svg`, `.identity/candidates/aurora/mark-small.svg`, `.identity/candidates/aurora/hero-master.png`, `.identity/candidates/aurora/hero-generation.json`, `branding/aurora/docs/wordmark.svg`, `product.json`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`, `product-projection-check`.

Limits: Image generation itself is not deterministic; deterministic export starts from the pinned original raster. Final creative adoption and rights decisions remain unapproved.

### 80-C3

Generate the main gradient icon, appropriate small-size treatments, banner/README, repository preview/avatar and existing docs/landing assets from pinned sources, with reproducible exports where promised.

**supported-local-evidence-with-explicit-limits**. The 19 pinned source digests and all 36 manifest output digest/byte rows independently match source. The export directory contains 38 files: 36 manifest-bound outputs, its manifest and a full kit ZIP. It includes main/small/transparent/light marks, actual-size sheets, wordmark, README headers, repository avatars/preview, local docs/landing projections and PNG/full ZIP downloads. Fresh-directory repeat and raster drift checks actually passed.

Source: `scripts/generate-aurora-kit.py`, `scripts/generate-aurora-ui.py`, `branding/aurora/aurora-manifest.json`, `README.md`, `site/assets/brand-icon.png`, `site/assets/brand-hero.png`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`, `selected-brand-repeat`, `selected-ui-projection-check`, `browser-site`.

Limits: Reproducibility is conditional on the explicitly pinned Inkscape/font toolchain, not a claim that arbitrary renderers or image generation produce identical bytes.

### 80-C4

Create ordinary PNG downloads and an offline gallery that open without remote assets/fonts, with transparent/light/dark variants clearly explained.

**supported-local-evidence-with-explicit-limits**. Ordinary decoded PNG outputs and a self-contained data-URI gallery are present. The byte-identical HTML rendered at desktop/mobile loopback viewports with all 16 PNGs decoded, no external requests or browser errors, and a real PNG download matching its source/manifest bytes. Gallery copy explains transparent, dark and light variants.

Source: `branding/aurora/index.html`, `branding/aurora/deckystream-aurora-png.zip`, `branding/aurora/deckystream-aurora-kit.zip`, `branding/aurora/README.md`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`.

Limits: Direct file:// navigation was actually attempted and blocked by administration policy (ERR_BLOCKED_BY_ADMINISTRATOR); retained raw receipt exit 1 is UNAVAILABLE, never a file-open pass. Loopback proof establishes self-contained artifact rendering/downloads, not literal file-URL or target-device acceptance.

### 80-C5

Review real 16/24/32/64 sizes and normal/highlighted dark-menu presentation; a monochrome fallback is optional, not a Decky API requirement.

**supported-local-evidence-with-explicit-limits**. Independent visual reviewer opened actual 16/24/32/64 review sheets and selected raster exports: the ring/S remains identifiable on normal and highlighted dark fields, with no blocking visual defect. The recorded text contrast ratios exceed the declared 4.5 minimum; no monochrome API requirement is invented.

Source: `branding/aurora/review/menu-sheet.png`, `branding/aurora/review/legibility-sheet.png`, `branding/aurora/review/contrast.json`, `branding/aurora/web/favicon-16.png`, `branding/aurora/web/favicon-24.png`, `branding/aurora/web/favicon-32.png`, `branding/aurora/web/favicon-64.png`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`.

Limits: Physical Steam Deck display/controller perception is UNRUN under #86. Pixel-level visual inspection is human-agent review, not trademark/creative-rights approval.

### 80-C6

Keep actual creator/tool provenance, licenses/notices, rights gaps and chosen publication owners honest. Direction approval alone does not approve rights/licensing or qualify final output.

**supported-local-evidence-with-explicit-limits**. Actual Codex vector authoring and one image_gen hero operation are recorded without human/exclusive-rights claims. The font notice is bundled. Vector MIT is explicitly a proposed owner decision; hero license is unasserted. Final human approvals, rights clearance, organization/publisher selection and Identity adopted governance entries remain empty/pending rather than fabricated.

Source: `.identity/candidates/aurora/inventory.json`, `.identity/candidates/aurora/hero-generation.json`, `branding/aurora/metadata/rights-and-sources.json`, `branding/aurora/licenses/DejaVu.txt`, `.identity/governance/approvals.json`, `.identity/governance/provenance.json`.

Actually passed named receipt checks: `selected-brand-tests`, `selected-brand-drift`.

Limits: This satisfies honest provenance/gap reporting, not rights clearance or publication permission. Owner must decide legal/license/attribution and publication ownership in the consolidated owner packet before publication/adoption.

### 80-C7

Update Identity consumer source/evidence for the selected assets; earlier source-bound brand receipts remain historical. No Identity repository changes or deployment.

**supported-local-evidence-with-explicit-limits**. Selected candidate/source and lowercase consumer display are updated without changing stable project/plugin IDs. The immutable cfb6c29 Identity validator (recorded digest) actually validates current consumer source with no diagnostics. Separate export manifest binds art bytes; the Identity contract receipt does not falsely claim it validates every PNG. Historical mint/old-revision receipts remain present and distinct.

Source: `.identity/identity.json`, `.identity/README.md`, `.identity/brief.md`, `branding/evidence/aurora-identity-source.json`, `docs/selected-aurora.md`.

Actually passed named receipt checks: `identity-consumer-check`, `selected-brand-drift`.

Limits: No Identity repository mutation, deployment, adopted token-layer change, approved Identity compiler output or final artwork approval is asserted. Current upstream head is not silently substituted for the deliberately pinned consumer contract.

### 81-C1

Use native Decky components with predictable controller focus, readable text, touch targets, keyboard entry and compact progressive disclosure for advanced settings.

**supported-local-evidence-with-explicit-limits**. Native Decky components are composed with controls first, stable progressive-disclosure editors and keyboard/focus browser cases. Current packaged browser tests cover narrow configured panel geometry, save/paste/keyboard entry, locked pending edits and focus persistence. All six normal-user frontend commands passed; 161 Node tests passed in each test invocation.

Source: `steamdeck/decky/src/index.tsx:261`, `steamdeck/decky/src/Configuration.tsx:37`, `steamdeck/decky/src/Configuration.tsx:186`, `steamdeck/decky/src/Setup.tsx:87`, `steamdeck/decky/src/Advanced.tsx:132`.

Actually passed named receipt checks: `frontend-absent-typecheck`, `frontend-absent-test`, `frontend-absent-build`, `frontend-reused-typecheck`, `frontend-reused-test`, `frontend-reused-build`, `browser-panel`, `browser-configuration`, `browser-dependencies`.

Limits: Decky browser/native API fixtures do not prove physical controller behavior, actual Steam keyboard or SteamOS geometry; those remain #86 by the issue wording.

### 81-C2

Add the bundled aurora gradient logo subtly in the header/plugin icon and use the selected lowercase display styling; keep live observed status dot/text independent of decorative logo color.

**supported-local-evidence-with-explicit-limits**. Local generated gradient SVG appears in both header and actual plugin icon; lowercase display comes from product projection. Separate observed-state dot and aria-label/status text remain bound to health/currentResult, not decorative logo color. Actual live/unconfirmed/stopped screenshots show distinct green/yellow/red status with invariant aurora artwork.

Source: `steamdeck/decky/src/index.tsx:87`, `steamdeck/decky/src/index.tsx:89`, `steamdeck/decky/src/index.tsx:321`, `steamdeck/decky/src/AuroraMark.tsx`, `steamdeck/decky/src/aurora-brand.mjs`, `steamdeck/decky/src/product.ts`.

Actually passed named receipt checks: `selected-ui-projection-check`, `product-projection-check`, `browser-panel`.

Limits: Gradient art is a bundled review-preview projection; its color makes no streaming or approved-production claim.

### 81-C3

Expose setup/dependency job progress, missing configuration and recovery with specific actions; retain manual Refresh plus automatic current-state updates.

**supported-local-evidence-with-explicit-limits**. Manual Refresh remains available alongside 1.5-second status polling and setup/configuration polling. Current dependency browser cases prove consent/Later/cancel/retry/missing-only progress and surviving reload without restarting installation. Missing configuration, failed readiness and collapsed recovery feedback provide specific actions.

Source: `steamdeck/decky/src/index.tsx:320`, `steamdeck/decky/src/Setup.tsx:109`, `steamdeck/decky/src/Setup.tsx:136`, `steamdeck/decky/src/Configuration.tsx:104`, `steamdeck/decky/src/Advanced.tsx:174`.

Actually passed named receipt checks: `browser-panel`, `browser-dependencies`, `browser-configuration`, `browser-m3-panel`.

Limits: Actual Flatpak package installation/network interruption and Decky lifecycle remain separate target checks.

### 81-C4

Disable or serialize actions from actual streaming/recording/replay/busy/unknown state; repeated clicks cannot create repeated success notifications, duplicate work or accidental Stop.

**supported-local-evidence-with-explicit-limits**. Existing guarded state controls remain byte-identical to merged 069, with exact-af7 fresh tests. Browser cases cover streaming/recording/replay/busy/unknown controls, repeated output/edit requests, stale results and no false success. Actual packaged Python-to-Go contention exercised six cases and 42 guarded child calls, including long shared locks, deadline ownership, independent explicit Stop and duplicate coalescing.

Source: `steamdeck/decky/src/state.mjs`, `steamdeck/decky/src/index.tsx:273`, `steamdeck/decky/src/index.tsx:274`, `steamdeck/decky/src/Configuration.tsx:54`, `steamdeck/decky/src/advanced-state.mjs`.

Actually passed named receipt checks: `frontend-absent-test`, `browser-panel`, `browser-configuration`, `browser-m3-panel`, `browser-mixer-panel`, `packaged-settings`.

Limits: Simulated browser and synthetic-HOME process tests do not authorize real output or replace actual provider/OBS33/Deck qualification.

### 81-C5

Keep screen versus verified game-only capture explicit, with intentional idle state and no automatic desktop fallback; show system audio/microphone selection, mute and availability honestly.

**supported-local-evidence-with-explicit-limits**. Verified game-only versus screen capture, deliberate idle, no silent desktop fallback, and stream-only mixer/mic controls are preserved in existing source. Current packaged browser and Linux native OBS harnesses passed applicable transition/routing/privacy cases; availability, gain/mute and unknown states remain explicit.

Source: `steamdeck/decky/src/index.tsx`, `steamdeck/decky/src/Mixer.tsx`, `steamdeck/decky/src/mixer-state.mjs`, `steamdeck/decky/src/advanced-state.mjs`.

Actually passed named receipt checks: `browser-panel`, `browser-m3-panel`, `browser-mixer-panel`, `browser-mixer-setup`, `native-audio`, `native-capture`, `native-game-obs`.

Limits: Native harnesses are isolated Linux software/display/audio fixtures, not SteamOS/Gamescope/AMD/OBS33, actual Deck LCD/OLED/headset routing or provider acceptance.

### 81-C6

Retain useful diagnostic console/copy with redaction and existing local-media/health/settings workflows; optional support links stay unobtrusive, verified and payment-free for core functionality.

**supported-local-evidence-with-explicit-limits**. Current browser cases retain diagnostic console/copy/filter/redaction, protected settings, local clips/media/profiles and health recovery. Support uses verified funding inventory, guarded navigation and hidden unset wallets; it remains optional at the bottom with no core payment requirement.

Source: `steamdeck/decky/src/index.tsx:142`, `steamdeck/decky/src/index.tsx:147`, `steamdeck/decky/src/Advanced.tsx`, `steamdeck/decky/src/Support.tsx`, `.github/FUNDING.yml`.

Actually passed named receipt checks: `browser-panel`, `browser-m3-panel`, `browser-configuration`, `browser-support`, `browser-setup`, `browser-m3-setup`.

Limits: No wallet address, external support transaction, account registration or monetization/Store research is fabricated; #51 remains separate.

### 81-C7

Bundle assets locally and inspect dark/focused/stale/error/empty states; screenshot fixtures are not claimed as real Deck acceptance.

**supported-local-evidence-with-explicit-limits**. Logo images are locally bundled inline SVG and site imagery is local PNG; packaged browser assertions actually decode header/plugin images with no remote asset need. Inspected screenshots cover live/unconfirmed/stopped and focus; automated cases cover stale/error/loading/empty states. Independent visual review found no blocking defect.

Source: `steamdeck/decky/src/AuroraMark.tsx`, `steamdeck/decky/src/aurora-brand.mjs`, `steamdeck/decky/src/index.tsx`, `steamdeck/tests/browser-panel.py`, `steamdeck/tests/browser-native-configuration.py`, `steamdeck/tests/browser-m3-panel.py`.

Actually passed named receipt checks: `selected-ui-projection-check`, `browser-panel`, `browser-configuration`, `browser-m3-panel`, `browser-mixer-panel`, `browser-site`.

Limits: Screenshots are explicitly simulated packaged-frontend fixtures, never actual Deck acceptance.

### 81-A1

Configured/streaming view shows observed state and Start/Stop before setup/advanced forms; setup remains prominent when required. In the 400×800 simulated native host, Stop currently appears around 1839px below expanded setup. This is fixture geometry, not physical Deck measurement.

**supported-local-evidence-with-explicit-limits**. YOUR STREAM and Start/Stop are structurally before dependency/setup forms. A current configured streaming narrow-panel browser case verifies primary controls without scrolling; dependency setup remains visible when missing.

Source: `steamdeck/decky/src/index.tsx:261`, `steamdeck/decky/src/index.tsx:273`, `steamdeck/decky/src/index.tsx:274`, `steamdeck/decky/src/index.tsx:280`, `steamdeck/decky/src/index.tsx:281`.

Actually passed named receipt checks: `browser-configuration`, `browser-panel`, `browser-dependencies`.

Limits: The earlier 400x800 fixture Stop-at-1839px finding is historical and is not represented as a physical Deck measurement.

### 81-A2

Collapse saved destination/connection and advanced sections progressively; keep controller focus stable and clear private drafts when leaving editing.

**supported-local-evidence-with-explicit-limits**. Saved destination/connection and advanced sections collapse independently. Leaving editing clears both key/password refs, visibility and dialogs; increments the sensitive clipboard epoch so delayed clipboard resolution cannot restore a private draft. Poll results do not reopen/collapse a focused editor; current browser case exercises both privacy and focus.

Source: `steamdeck/decky/src/Configuration.tsx:48`, `steamdeck/decky/src/Configuration.tsx:52`, `steamdeck/decky/src/Configuration.tsx:54`, `steamdeck/decky/src/Configuration.tsx:65`, `steamdeck/decky/src/Configuration.tsx:79`, `steamdeck/decky/src/Configuration.tsx:123`.

Actually passed named receipt checks: `frontend-absent-test`, `browser-configuration`.

Limits: Physical controller navigation and Steam keyboard rendering remain #86.

### 81-A3

A failed health/recovery request is visibly reported even with health details collapsed.

**supported-local-evidence-with-explicit-limits**. Recovery/health failure is projected as generic public message outside the collapsed health details. Current browser tests hide details and verify failure remains visible without exposing private backend error sentinels.

Source: `steamdeck/decky/src/Advanced.tsx:167`, `steamdeck/decky/src/Advanced.tsx:174`, `steamdeck/tests/browser-m3-panel.py:125`.

Actually passed named receipt checks: `browser-m3-panel`.

Limits: A displayed failed request is not a successful recovery or proof of actual device fault remediation.

### 81-A4

Clip loading, confirmed empty, populated, failed and refresh states are distinct; loading cannot immediately claim an empty library.

**supported-local-evidence-with-explicit-limits**. Clip results explicitly project idle/loading/ready/empty/failed and strict public display fields. The local pending lock lasts through final tool status refresh. The maintained browser fixture actually holds status refresh after returning clips, verifies unrelated local-record action is available while Browse stays locked, then releases the refresh; hide invalidates late requests and retry is exercised.

Source: `steamdeck/decky/src/Advanced.tsx:94`, `steamdeck/decky/src/Advanced.tsx:108`, `steamdeck/decky/src/Advanced.tsx:114`, `steamdeck/decky/src/Advanced.tsx:117`, `steamdeck/decky/src/advanced-state.mjs:39`, `steamdeck/tests/browser-m3-panel.py:79`.

Actually passed named receipt checks: `frontend-absent-test`, `browser-m3-panel`.

Limits: Library states are packaged frontend/fixture tests; actual on-Deck storage/recovery cases remain separate.

### 81-A5

Failed provider-guide navigation gives accessible, secret-free feedback; reuse the existing guarded support-link pattern.

**supported-local-evidence-with-explicit-limits**. Provider guide URLs come only from the fixed own-property provider inventory. Synchronous/asynchronous navigation failure becomes accessible polite, generic feedback; user destination URL and secret drafts are never passed to the guide action.

Source: `steamdeck/decky/src/configuration-state.mjs:9`, `steamdeck/decky/src/Configuration.tsx:70`, `steamdeck/decky/src/Configuration.tsx:74`, `steamdeck/decky/src/Configuration.tsx:212`.

Actually passed named receipt checks: `frontend-absent-test`, `browser-configuration`.

Limits: No external provider authentication or successful navigation is claimed by the failure-path check.

### 81-A6

Advanced features have discoverable instructions/entry help for the existing protected optional Desktop Setup, with no separate mandatory application or unauthenticated LAN service.

**supported-local-evidence-with-explicit-limits**. Optional Desktop Setup instructions are reachable from native configuration and advanced stream tools and describe the protected existing setup path. No separate mandatory app, unauthenticated LAN service or output-triggering navigation is introduced.

Source: `steamdeck/decky/src/index.tsx:295`, `steamdeck/decky/src/index.tsx:296`, `steamdeck/decky/src/index.tsx:297`, `steamdeck/decky/src/Configuration.tsx:213`.

Actually passed named receipt checks: `browser-panel`, `browser-configuration`, `browser-setup`, `browser-m3-setup`, `browser-mixer-setup`.

Limits: Protected Desktop Setup is optional; OAuth/companion setup remains deferred, not silently delivered here.

### 81-A7

Apply the selected local aurora assets from #80; observed status color/text stay independent. Align update guidance with #102/#82 so no absent updater is advertised.

**supported-local-evidence-with-explicit-limits**. Selected local art is integrated with independent observed state. Update controls advertise the actual normal Decky ZIP/update path and optional Desktop Setup version; there is no native self-updater button or nonexistent updater claim.

Source: `steamdeck/decky/src/index.tsx:309`, `steamdeck/decky/src/index.tsx:310`, `steamdeck/decky/src/index.tsx:311`, `steamdeck/decky/src/index.tsx:321`, `steamdeck/decky/src/AuroraMark.tsx`.

Actually passed named receipt checks: `selected-ui-projection-check`, `product-projection-check`, `browser-panel`, `browser-configuration`.

Limits: No publishing/release, migration, installed-version update on a real Deck or Store eligibility is claimed.

## Evidence binding

- Review JSON: `/workspace/.obsgod-tools/aurora-20261120-de7c5a44/aurora-acceptance-review.json` (exact commands, log hashes, source before/after, issue snapshots and 21 literal criteria).
- Independent visual JSON: `/workspace/.obsgod-tools/aurora-20261120-de7c5a44/aurora-visual-independent.json` / SHA256 `342a4bdbc111331e5568dea492262f5401260cba435305cb6b693d7745c5d160`.
- Gallery aggregate: `/workspace/.obsgod-tools/aurora-20261120-de7c5a44/gallery-evidence-summary.json` / SHA256 `cef9c1d1b662c64abfa04fa9b10a95ea35f4509a08c9cd593b1314158d31596c`.
- Retained input comparison: 41 files, `/workspace/.obsgod-tools/aurora-20261120-de7c5a44/aurora-review-retained-inputs.json` / SHA256 `4bdf5fea910c4a39e3803528e8855cd536567e395f7dc8a0350c577af384a71b`.
- Original 230-criterion ledger remains byte-identical to merged 069, SHA256 `0795e6594c7bbde195bb8ebfcbc4050f0d5ecbe9c879767edbe0050540386df6`.
- Independently verified all 617 current source inventory digests, 19 selected manifest source hashes and 36 selected output hashes/byte counts. No mismatch.

- Completed available qualification: `/workspace/.obsgod-tools/aurora-20261120-de7c5a44/available-af7/available-checks.json` / SHA256 `9cc1a2f369fa7fa2be3e54056cb4dd7b9ea0fafdd25c3d559b8b965aa7061e59`.

## Explicit limits and remaining gates

- Physical Steam Deck/controller/Steam keyboard/rendering and actual SteamOS/Gamescope/AMD/OBS33/Flatpak/LCD-OLED/headset/provider validation remains #86/original criteria. Linux native fixtures do not substitute for it.
- Owner source/rights/license/attribution/creative adoption and chosen organization/publisher decisions remain unapproved original facts/gates; accurate gap reporting is supported, publication rights are not asserted.
- Consumer-owner actions, actual installed/adoption proof, release/publisher destinations and final owner packet remain separate original campaign work.
- Actual supported ACT matrix exited 3 on demonstrated capacity preflight. All six ACT jobs are UNRUN; direct standalone passes are never described as ACT passes.
- Direct gallery file:// navigation is UNAVAILABLE due administration policy, with failed raw receipt retained. Identical offline-content loopback rendering and download passed; literal file-open/target-device proof is not invented.
- Hosted CI, required reviews/branch protections and any remaining full-matrix evidence must be assessed by root before merge/closure. This private local review is not formal GitHub approval.
- No release, deployment, migration, account registration, other-repository change, Store submission, paid execution or issue closure occurred in this review.

## Parent disposition

- Use the exact frozen af7 candidate and bind the completed available-checks receipt only after the controller actually finishes; preserve every failed/skipped/unavailable/unrun distinction.
- Curate public criterion-level evidence and reconcile stale issue checkpoints without discarding original acceptance/dependency text.
- Inspect live protections/reviews/workflow side effects before any review, merge or issue disposition; no closure is performed or requested by this report.
- Keep genuine owner/device/publication/adoption gates in the consolidated packet and #86/original ledgers without broadening bounded #80/#81 criteria.
