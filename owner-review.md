# Candidate9 owner and publisher review

All required available local checks passed at exact clean source
`1a482808a8281c8bce092cea057df758836b34e9` (350 tracked files). Candidate:
**0.1.0-deck.9**. The compatible product remains Decky Stream display name,
`obsgod` executable/module/storage and `OBSGod` installed Decky identity.

The candidate is ready for source review and actual Steam Deck qualification.
The immutable artifact commit and independent public-download verification are
**pending at packet creation**. This is a review checkpoint, not a published
release, deployment, supported-hardware certification or completed stable-v1.

Review/merge order is **#58 → #59 → #60 → #62 → #63 → #64 → #65**. The four
new completion drafts are #62–#65. No source merge or issue closure occurred.

## Exact candidate and artifacts

| Item | SHA256 |
| --- | --- |
| Runtime `obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz` | `879ad44ebb28fb695877c071d9708959a7afc39b7b2b9032421f117a267bf803` |
| Plugin `obsgod-decky.zip` | `9e613d282d242d5be930af1beeb05a8724453ab971a59165c47e22204b296b57` |
| Updater `obsgod-one-click-update_0.1.0-deck.9_linux_amd64.zip` | `e7d24d9860f2a207a130d9002c0e21f3f89c3221e352393b5e9b2b65da9bdc69` |
| Exact 350-file source archive | `4b6751acc9222996cb0205468d19ae941e756868da6aff908489738832713f1e` |

All **14 selected product/audit entries match across the two complete runs**;
each candidate job also builds runtime/updater and generates the audit twice.
Actual notices/native preferred source/SDK source, SPDX and unsigned provenance
passed the exact-source audit. Unsigned self-reported inventory establishes
byte/source consistency, not authenticated publisher or trusted-builder identity.

The complete 230-criterion ledger preserves 35 original implementation issues,
exact criterion text, original body hashes, dependencies, scoped evidence and
remaining actions. Historical receipts remain historical. Local evidence does
not pass physical target, hosted CI, review, rights or adoption requirements.

## What changed

- Stream-only microphone controls with observed input selection, separate gain/
  mute/meters, safe explicit unmute, mute on route/device loss and a bounded
  private hold-to-talk guardian. Host system volume/default input stay unchanged.
- Importable `pkg/api/v1` and `obsgod api`: independent models/errors, bounded
  context-aware serialized operations, invocation approvals and schema1 JSON.
- `pkg/creator/v1` and creator plan/start/status/stop/extensions: strict non-secret
  profiles, environment-backed RTMP transport adapters and safe partial-state
  reporting, above the reusable OBS core.
- Canonical architecture/vocabulary/decision/maintainer docs, generated CLI
  reference, security/support/contributor/changelog/conduct/review guidance.
- Reproducible unapproved Identity consumer kit and static site preview, explicit
  migration inventory and fail-closed updater trust. Live approved visuals and
  installed compatibility identifiers remain intact.
- Pinned local act/action-source acquisition, complete static/security/coverage
  workflow paths and deterministic artifact/source/license/SPDX/provenance audit.

## Qualification results

| Check | Result at the exact qualified source |
| --- | --- |
| Go | **213 top-level / 386 pass events**, race with `-count=1`; one optional existing-OBS read-only test skipped |
| Python | **127** backend/installer/updater/removal tests passed |
| Tooling | **23** script tests passed |
| Frontend | **30** Node tests, typecheck/build passed; npm audit reported zero findings |
| Static/security | Formatting, vet, pinned staticcheck passed; Go vulnerability scan reported zero findings |
| Other targets | Six binaries compiled; native target execution unrun |
| Local act | Both complete six-job sequences and PR static passed: **13 local job passes**; provider dependency-review unavailable with explicit reason/API fallback |
| Coverage | **58.1%** statement baseline in both final runs; prior 58.0% is historical context. No arbitrary percentage gate |
| Package/audit | Twice-built runtime/updater and audits per job; **14/14** selected entries identical across runs; full selected-runtime source/notices/SPDX/unsigned provenance passed |
| Native OBS | Two complete Linux OBS30.2.3 runs of capture, actual moving/audible media, game/idle, live mixer/PTT/device-loss, password, recording/replay and recovery suites passed |
| Product browser | Seven product flows plus site per act run; additional setup upgrades from previews 4/6 passed |
| Legacy transport | Both old/current pinned Decky 3.3.1 install/update/repair/rollback/removal/bootstrap fixtures passed |
| CLI/Fish | Twelve exact-source CLI/API/creator/help/reference/config/completion checks and disposable Fish-container validation passed; host Fish unavailable |
| Draft brand/site | Eight brand and eleven site tests, deterministic 25-file kit/nine-page site and 45 host viewport cases passed |
| File/offline browser | ACT site browser actual file-offline navigation passed. Managed host file:// was unavailable by policy; its loopback HTTP passed. These are separate environment results |
| Hosted CI | **Unavailable:** nine exact-source runs, zero executed steps; actual annotation says account locked due to billing |
| Actual Deck/viewer/adoption | **Unrun** for candidate 9; native/protocol/browser fixtures cannot supply this proof |
| Human/creative/rights review | **Pending** where applicable |

Earlier failures are retained as history: artifact-service addressing, static
error capitalization, generic snapshot archive/version collisions, npm pin,
root fixture environment, resource headroom and stale generated capture output.
The product correctly refused capture/storage when prerequisites were invalid.
Only identified own act cache blobs and project host Go build cache were cleared
with inventories. The browser reserve scenario was **2048 MiB**; the recorded
native refusal was **1024 MiB**, with **894,406,656 bytes** available. Production
capture/output/storage guards were unchanged. Final source reruns passed.

## First owner actions

1. Review the seven drafts and exact evidence, then merge in the recorded order
   if accepted. Preserve branch protections and immutable artifact/download refs.
2. Install the exact candidate on the real Deck without wiping existing private
   settings/media. Record model, SteamOS/channel, Steam/Decky, OBS Flatpak/bundled
   WebSocket and GStreamer versions. Verify an audible moving local clip first.
3. Test built-in and actually available 3.5 mm/USB/Bluetooth inputs, gain/mute/
   meters, device/default-route changes, system mute and hold/release/focus-loss/
   close/reconnect/lease-expiry behavior. On LCD the jack can disable built-in mic;
   actual device availability is authoritative. Lost OBS control cannot guarantee
   physical mute and must remain visibly uncertain.
4. Test game-only/menu privacy, idle/game switching, session/sleep/controller/
   performance, install/update/rollback/uninstall. A separate viewer confirms
   intended picture and audible system/mic sound per supported provider. Collect
   a real new-user install→clip→viewer→update/recovery→uninstall journey.
5. Resolve the Actions account/billing lock, then obtain required hosted runs and
   reviews. The final real-ref provider action separately reported **“Dependency
   review is not supported on this repository. Please ensure that Dependency
   graph is enabled.”** The graph comparison API returned 403 with otherwise
   working injected Git/API access. Inspect that repository feature/access and
   rerun the real action. Earlier synthetic missing-context errors are historical.
   macOS capacity notices are separate; local act is not hosted success.
6. After target/CI/review gates, review exact publisher/destination and unsigned
   verification policy before **publishing this product release**. Deployment,
   transfer, other-repository changes and spending remain precise separate actions.

## Implementation remainders and future activation

- **#9:** legacy commands retain `internal/obs` ACK/output/approval semantics.
  Full compatible CLI-to-facade migration/deprecation and tests remain work.
- **#13:** the dedicated StreamGod project is uncreated and the current creator
  connects to existing OBS without managed launch/exit. Choose an approved
  destination or explicit scope amendment, then implement/qualify the intended
  companion launch boundary. Owner approval alone does not implement it.
- **#14:** optional provider APIs/OAuth/multistream and creator/content modules
  remain focused follow-up work; interfaces/strategy are not their implementation.
- **#12:** generic 20-target snapshot archives still need their own complete
  notices/SBOM/install/native qualification before additional generic publication.
  The selected Deck runtime/updater audit already includes its notices/preferred
  source/SBOM. Generic distribution is not a new gate for the compatible mic preview.
- Final organization/repository/name/mark/contact/domain, creative/rights/license
  decisions, approved Identity production promotion, actual migration/redirect/
  duplicate-plugin proof and hosted site activation remain separate future lanes.
  Identity is a read-only pinned framework, not another release project here.
- Optional support needs real owner recipient/control/readiness facts. Crypto
  wallets may remain null/hidden. No wallet/payment activation or final branding/
  transfer/site decision is invented as a prerequisite for this compatible preview.

## Repository and post-review issue reconciliation

Fresh 12:32:36 UTC query: **36 open issues, seven draft PRs**, `master` remains
`ed7d100d356ce803d2cb1c1afef3836759deef10`; `main` 404, protection details 403,
rulesets `[]`. Latest published tag is updater-only `v0.1.0-deck.4-updater.1`.
Candidate9 is not published. Metadata `admin: true` did not provide usable branch
administration scope: one prior-authorized `master`→`main` rename returned 403
“Resource not accessible by integration.” The owner can rename it in GitHub UI,
separately from repository transfer/branding. No settings/protection changed.

After review/merges, reuse **#46** for surviving implementation/pair work and keep
**#51** unchanged as monetization/Decky Store research. Close transferred issues
as superseded with their intact criterion/dependency/evidence links, without
calling unrun acceptance passed. #37/conditional Store research is preserved for
that separate journey; no research/contact/submission was performed here.

Preserve immutable artifact/download refs, source/artifact commits, hashes and
URLs during later source-branch cleanup; never merge the orphan artifact tree.
Root will add the artifact self-commit and independent public-byte verification
following upload, then refresh live issues/PRs/releases/default/protections again.
No release, deployment, transfer, spending, source merge or issue closure is
performed by this review packet.
