# Milestone 2 owner and publisher packet

Status: independent implementation and all available local qualification are
prepared for review. Candidate **0.1.0-deck.7** was built and checked at clean
source `0eac1ed9746e6a5999a196777bde5455222f46eb`. Required target, CI, owner
review and publication gates below remain open. No release is published.
Preview6 receipts qualify only preview6's recorded source.

## Exact review candidate

| Artifact | SHA256 |
| --- | --- |
| Runtime `obsgod-deck_0.1.0-deck.7_linux_amd64.tar.gz` | `4205e4725fd432ea99a59fe8c1a78f0f7b29c7ddbd6c79e3cf4afd8c2c67c9c3` |
| Plugin `obsgod-decky.zip` | `0a4d8afefa0f149cb053cddc988fa0cc46992602b73b73b581deab4414abf5c4` |
| Updater `obsgod-one-click-update_0.1.0-deck.7_linux_amd64.zip` | `5227e541e3c07cc9214e67f4400dda14065520789ebdecfdeca15b6c4152c68d` |

The complete commands/platforms/images/input and output hashes are in
[qualification JSON](qualification.json); individual criteria and
remaining gates are in [the acceptance ledger](criterion-ledger.json).
The artifact checkpoint is a review download, not a GitHub release or site
deployment. Later evidence-only commits do not change or requalify these bytes.

Passed freshly: Go110 top-level/206 pass events, Python111, Node16, vet and zero
Go/npm vulnerability findings; six cross-builds compiled only; deterministic
metadata, repeated runtime/updater builds and internal payload hashes; fresh/
preview4/preview6 package browsers, panel and three receiving dialogs; pinned
Decky3.3.1 install/update/uninstall/repair and dynamic6 bootstrap; site11 safety
cases/40 viewports; native13 capture cases, decoded OBS audio/video/game/idle,
generated/manual password rotation/old-password rejection and an actual
settings-only workflow. Native OBS was30.2.3, not the owner's OBS33 device.

One optional existing-OBS test skipped. Direct file:// site navigation was
unavailable under browser policy; offline loopback HTTP passed. Fresh GitHub CI
executed zero steps because of the billing lock. Actual Deck/provider viewers,
independent review, funding receipt and adoption remain unrun/pending.

An earlier459d0fe qualification attempt failed on an ambiguous browser-test
selector. The assertion was scoped, the source was recommitted and the complete
matrix rerun at0eac1ed. Earlier passing receipts were not relabelled.

## Verified facts and ownership

- Current repository/publisher namespace: `szmyty/obsgod`. The owner authorized
  work here and selected **Decky Stream** as the working display name.
- Organization, final canonical repository/domain, brand creative brief and
  final asset rights/approvals remain owner inputs. No new accounts or transfer
  were performed. See [identity and migration](IDENTITY-MIGRATION.md).
- The original CLI retains the MIT license and Christian Muehlhaeuser's 2020
  attribution. Bundled Go licenses, the replaceable LGPL Decky API and the MIT
  QR implementation's notice ship with the candidate. Native capture includes
  its preferred source/notices. OBS/GStreamer are separately installed software.
- Funding recipients come from the owner's existing configuration, with five
  common providers and Patreon excluded pending its broken-link conflict.
  Public profiles/configuration do not establish payout or tax readiness.
  All cryptocurrency addresses remain unconfigured; no funds were moved.
- Source history includes substantial AI-assisted implementation. Store
  eligibility remains unresolved; no contrary authorship declaration is made.

## Candidate and evidence

Before publication, record the exact source revision, clean/dirty status, app/
plugin/updater versions, runtime/plugin/updater/site artifacts and SHA256 values.
The implementation ledger and qualification JSON will identify those exact
inputs and commands. A later evidence-only commit must clearly identify the
earlier packaged source; it does not silently requalify a rebuilt package.

Required available matrix: Go race/unit/integration, vet/vulnerability scan,
Python installer/backend/update/uninstall, TypeScript/Node/build/audit, generated
metadata drift, reproducible packages, actual-package Desktop/panel browsers,
crypto receive browser fixtures, pinned Decky installer/update/uninstall protocol,
native capture protocol, real native OBS audio/video/lifecycle and continuous
game/idle transitions, docs/site links/accessibility/viewport checks and
cross-builds. Cross-build execution remains explicitly unrun.

Required target evidence: exact Steam Deck/SteamOS channel/Steam/Decky/OBS/
GStreamer versions; fresh install, repair, old-preview upgrade and interrupted
recovery; audible local clip; separate provider viewer audio/video; game-only
menu privacy, game changes and intentional idle; microphone policy; controller
focus/QAM/session/sleep/reboot/performance; update/uninstall safety. For any
Store native-backend route, current developer Stable/Beta and independent
SteamOS Preview evidence are additional external gates.

Upgrade compatibility is version-specific: the published preview4.1 updater
hardcodes the preview4 URL/hash and cannot fetch preview7. Owners of that
bootstrap need the current reviewed installer/updater. The maintained preview6
dynamic updater is a separate old-to-new compatibility fixture. Do not weaken
historical verification or claim the fixed updater acquired dynamic behavior.

## Publication and responsible owners

| Action | Proposed destination | Responsible party | Current status |
| --- | --- | --- | --- |
| Source review | Draft PR stack in `szmyty/obsgod` | Repository owner/reviewers | Authorized preparation |
| Product release | Same repository's Releases | Owner-approved publisher | Not published; approval required |
| Direct docs/landing | Built static preview; hosting/domain TBD | Owner | Preview only; deployment approval required |
| Identity assets | Consumer source in final product repository | Owner/actual creative rights holder | Final facts/approval pending |
| Funding links | Existing configured owner destinations | Owner/provider | Link UI prepared; payout readiness unverified |
| Crypto receiving | Owner-created public addresses + exact networks | Owner | Unconfigured; hidden |
| Repository transfer | Owner-selected organization TBD | Owner/admin | No destination or transfer approval |
| Decky Store | Official database only if truthful eligibility permits | Owner + maintainers/independent tester | No contact/submission/listing |

GitHub Actions currently cannot start because of an account billing lock. Record
fresh job annotations, not merely an old failure. The owner must resolve the
account restriction through GitHub; no paid remediation is authorized here.
The default branch remains `master` because the integration cannot rename it
to `main` (403). The owner can do that on GitHub's Branches page.

## Consumer adoption proof

Record a new user's exact candidate install -> configure -> audible local clip
-> separate viewer -> update/repair -> uninstall journey. Preserve versions,
commands, hashes, outcome and limitations without credentials. The earlier
owner report established video at preview5.2 and silent audio; it does not prove
preview7 audio, provider support, privacy or adoption. No new-user or donation
success is invented. Support success is optional and measured from owner records,
not undisclosed tracking.

## Prepared Store inquiry (not sent)

Only the owner can decide whether to contact maintainers or submit. The following
draft can accompany the exact final source/evidence; it makes no eligibility or
authorship assertion unsupported by the record:

> We maintain Decky Stream, an independent OBS control/capture plugin with a
> substantial AI-assisted implementation history and no runtime LLM feature.
> We have not established a truthful majority-not-AI-authored attestation.
> Your current template and wiki appear to restrict this provenance. Is this
> project eligible for submission under your current policy? We would disclose
> the source/history, native backend and exact testing evidence. The optional
> support UI opens existing external funding pages; unconfigured crypto entries
> are hidden, and the local core has no payment requirement. Please also clarify
> whether those optional links are permitted in an otherwise eligible plugin.

No inquiry, external repository change or submission was made. A direct-only
outcome remains viable; there is no promise of a policy exception or listing.

## Final approvals

Finish all independent code and available checks first. Then present the exact
candidate/artifacts/evidence and unresolved target evidence. Obtain concrete
approval before publishing a release, deploying the sites, changing another
repository, transferring ownership or spending. Activation of public receiving
addresses requires the owner's actual addresses/network verification. Missing
device, CI, required review and creative/rights evidence remain closure gates.
