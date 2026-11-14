# Monetization and Decky Store research

Prepared 2026-11-13 America/New_York for [issue #51](https://github.com/szmyty/obsgod/issues/51). Source retrieval times are recorded in UTC. This is a research decision packet, separate from the implementation and qualification checklist in #46. No offer, provider, price, account, release, Store submission or external contact is approved by it.

**Recommendation: finish the free direct-download product, retain optional voluntary support, and defer a paid offering. Defer Store implementation/submission until the owner resolves the conflicting policy wording and chooses whether the additional channel work is worthwhile.** Direct-only distribution and no paid product are valid outcomes. Neither recommendation promises revenue or Store admission.

## Journey 1 — whether and how to monetize

### What the evidence establishes

The recorded product problems are installation/startup friction, audio, privacy during game changes and recovery. The owner has reported earlier streaming success, but that single-user history is not a new-source hardware receipt or an independent customer cohort. Current actual Deck/provider/new-user adoption remains unrun in the candidate review packet.

The live GitHub snapshot returned 0 stars, 0 forks and 0 subscribers, with 40 issue records whose GitHub author is the repository owner. Those tickets include planned engineering work; they are not 40 independent customer complaints. Five published prereleases were returned with empty attached-asset lists, so usable release-asset download counters are **unavailable**, not evidence of zero downloads. The manual candidate downloads on artifact Git branches are outside such counters. None of these observations establish the number of users, retention, willingness to pay, contributions or commercial demand. No interviews, payment records, support-time records or owner capacity commitment were available.

Existing implementation supplies five nonblocking external support destinations from `.github/FUNDING.yml`. `docs/support.md` explicitly says the handles do not prove payout readiness or successful receipt. Bitcoin/Ethereum/Solana receiving addresses are null and hidden; no wallet should be activated from this research. The preview has no promised response SLA, and voluntary support does not buy one. The local core works without a support account and the plugin does not collect payment information or support-click telemetry.

Project source was inspected at `d6f67159fb88e664a4dad2e57950c29c0407653f`; immutable file URLs/hashes are in the source index. This is an assessment of the recorded source and evidence, not a fresh product qualification.

### Options and tradeoffs

| Option | Value and practical implication | Decision now |
| --- | --- | --- |
| Keep the product entirely free | Preserves the simplest local/offline/privacy model. Maintenance still consumes time; income is not expected. | Viable default. Finish qualification and state support limits honestly. |
| Voluntary support for the existing free product | Fits the existing interface and creates no new paid-service promise. Configured links are not verified recipients or demand evidence. | Retain the option; owner verifies destination/control/readiness and applicable distribution-channel treatment before public promotion. Null wallets can stay hidden indefinitely. |
| Optional original/licensed scene assets | Could save users setup time while the core and accessibility remain free. Actual interest, distinctive assets and rights are unverified. Current draft marks have humanApproval:null. | Defer; do not sell unapproved brand candidates or assume a scene-pack market. |
| Bounded paid setup/support | Could address installation complexity if people actually request it. Requires available human capacity, clear scope/terms/refunds and safe handling of sensitive setup. | Defer until users independently request a priced, bounded service and the owner chooses to provide it. Contributions must not silently become an SLA. |
| Optional hosted service or other paid feature | Could justify ongoing payment only if it solves a demonstrated recurring problem. Creates operating, privacy, reliability and support obligations absent from the free local core. | Do not build now. No recurring service need, budget, operator or unit economics has been established. |

The MIT license expressly permits sale subject to preserving its notice, including the inherited Christian Muehlhaeuser attribution. It does not prove exclusive ownership of inherited code or cover unrelated dependencies, marks or user media. The selected runtime audit retains third-party notices, capture preferred source and Decky API LGPL source/license material; it is an inventory/integrity receipt rather than a legal opinion. Any paid assets need their own real rights/source record. Generic snapshot packages have separate unfinished distribution evidence and should not be marketed as supported products.

There is no mandatory hosted product service in the local design. Distribution/build/support costs still exist, but their amount and who will absorb them are unknown. Price and profit cannot be responsibly estimated from the available material. If an offer is later proposed, record gross receipts, fees, refunds, applicable taxes, operating expense and actual support time separately. Do not convert voluntary contributions into recurring-revenue or customer-count claims, and do not invent fee rates or labor-cost assumptions.

### Small next experiment — proposed, not executed

After real-device qualification, an owner-approved, zero-purchase discovery pilot can test the problem before selecting a paid product. Invite a small number of independent volunteer Deck users with their consent; collect versioned install→audible local clip→viewer→update/recovery→uninstall outcomes, observed help time and an optional free-text answer about the most valuable missing capability. Do not collect stream keys, private profiles, wallet data or background telemetry. Recruitment/contact is a separate owner-authorized action.

Success means retaining actual independent completion and support-effort evidence, plus repeated unsolicited interest in a specific optional extra. It does **not** mean a payment market is validated. Stop for privacy/safety problems, repeated installation failures or capacity pressure. If no repeated need emerges, keep the product free and stop paid-product work. If a repeated need emerges, prepare a separate offer/price/cost/terms experiment for owner review; no vendor, account, price or spend is selected here. The owner sets recruitment scope and time budget before execution; unavailable data is not filled with invented conversion targets.

## Journey 2 — Decky Store feasibility and direct distribution

The Store path is **clarification needed and technically unprepared**. The current [official-source brief](store-policy-research.md) records the exact excerpts, source dates, technical requirements and interpretations. The sources are pinned to wiki `ec9d4cf8b07cdc7bc7706fd118d68a272f653cb4`, plugin database `0fdb6a686d7c0e79366f85c9d551576cad3ecee5`, and template `90d0780e882a17f5714fc6de044c645f22608290`.

| Finding | Consequence for this project |
| --- | --- |
| The older submission guide says no plugin using “any LLM based code.” The newer submission checkbox says generative AI did not write a “majority”; the newer safety guide says “excessive.” Merged database PR #1025 explains the later checkbox. | These are conflicting official texts. The project discloses substantial AI-assisted implementation and AI-authored draft SVGs; no majority audit or eligibility finding exists. Do not assert the weaker checkbox overrides the guide, claim automatic rejection forever, conceal history or manufacture an attestation by rewriting/retyping. Owner-approved truthful clarification is needed before Store investment. |
| Store CI reads root `package.json`/`plugin.json` and builds the submitted submodule root. The current manifests are under `steamdeck/decky`; the direct packager bundles a Python adapter, Go binary and native GStreamer library. | The current monorepo/direct ZIP is not a ready Store-submodule submission. A reviewed root-layout/export and exact Store-CLI build/source mapping would be separate work after channel disposition. No other repository is created or changed by this research. |
| Native binary/custom-backend paths require actual third-party SteamOS Preview testing. The template also asks for Stable AND Beta, while review prose uses different wording. | Obtain the applicable real target matrix and truthful reports. Cloud OBS/native/browser/ACT checks do not satisfy those device attestations. Do not silently choose the weaker wording. |
| Public reviewable source, non-obfuscated code, checksum verification, licenses and applicable template/asset attribution are required. | Existing source/notices/audit preparation is useful, but not Store approval. Check actual derivation before adding template attribution; preserve existing inherited notices and unapproved asset status. |
| The safety guide lists self-update systems as a denial reason. | The panel only checks versions and directs users to the separate Desktop updater; it does not install updates. The Desktop updater can replace the paired app/plugin, so a Store channel needs an explicit reviewed update boundary. The check-only button alone is not a demonstrated violation. |
| Monetization is contextual and discretionary: costly service/peripheral features are likely acceptable, core/accessibility paywalls likely denied. The inspected material does not explicitly settle voluntary-support or crypto-link treatment. | No blanket support-link approval or donation ban is established. Keep the free core intact and prepare precise channel questions before implementing an uncertain paid path. |

Official documentation describes manual ZIP/URL installation; newer safety guidance discourages it and says Decky does not support non-Store plugins. Direct distribution is a documented technical path, not Decky endorsement. It preserves the existing product architecture and update path, but puts source/download trust, qualification, support, updates and rollback on this project's publisher. Store distribution would add discovery and the review/testing channel, but also policy, packaging, update-model and real-device gates; admission cannot be promised. No current alternatives audit establishes uniqueness: the database's `decky-recorder` entry is a relevant comparison candidate, not proof of equivalence or differentiation.

The recommended current path is to finish the qualified free direct preview with its existing publisher/rights/release gates, while treating Store work as deferred pending owner choice and clarification. Waiting for a policy change is also legitimate. Rebuilding provenance or hiding AI assistance is not a research recommendation.

## Owner decision checklist

- Retain the free core and decide whether voluntary support alone is enough for now; defer a paid offer unless actual demand changes that choice.
- Verify the existing intended recipients/control/readiness before promoting support; leave null wallets hidden unless separately approved.
- Choose whether to remain direct-only, defer Store work, or authorize sending the prepared policy questions. No maintainer has been contacted.
- If clarification is desired, ask which AI wording governs the fully disclosed project; the exact native Stable/Beta/Preview matrix; accepted Store update/helper boundaries; root-layout/build requirements; and treatment of nonblocking support links.
- If a Store path is viable and worth its cost, separately approve the source/destination/layout and actual build/device rehearsal. Research completion does not require accepted Store admission.
- Supply any existing independent user/receipt/support-capacity facts the owner wants considered. Their current absence supports deferral; it does not prove no market exists.

This packet completes bounded discovery, alternatives, uncertainty and next-action preparation. It does not supply missing device/review/rights/adoption evidence, choose a final organization/name/domain, create an offer, activate a wallet, contact maintainers, publish a release or spend money. The implementation, owner decisions and external outcomes remain separately tracked.

## Evidence notes

`research-51-sources.json` binds official/project source URLs, revisions and SHA256s and records the public repository observation scope. Public counters are a single snapshot, not an acquisition funnel. The exact issue body and full source snapshots are retained privately for review. Full wiki copies are not republished under the project's MIT license; the site advertises CC-BY-NC-SA, so this packet uses linked, attributed excerpts and source metadata instead.
