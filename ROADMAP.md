# Product roadmap

## Current state — qualified follow-up and remaining acceptance

The owner authorized merging the prepared audit and progressing the remaining
issues. #67 and follow-up source #69/#70/#71 are merged; #72 contains the final
research/evidence follow-up. Default remains `master`; exact source/merge
revisions are in the [fresh qualification record](audits/qualification-4699235.md)
and GitHub. No branch protection was changed or bypassed.

Exact source 4699235 passed both complete local ACT sequences and fresh
supplemental checks. #68 has actual absent/reused-output normal-user rebuild
proof. #51 has completed bounded [monetization/Store research](docs/research-51.md),
with recommendations and owner choices distinct from implementation, income or
Store admission. #46 retains every original criterion/dependency and all remaining
engineering/target/CI/review/rights/adoption work. Neither source merges nor
research delivery complete those gates.

The [current-source manual review download](docs/current-review-install.md)
is source 4699235/artifact eb92598f, with 19 verified public files and full 401-file
source. The older 1a/d0a review download remains unchanged. No product release,
site/environment snapshot, transfer or spending occurred. Actual Deck/provider
acceptance, full legacy CLI transport migration, NFPM/native support and selected
companion/ecosystem/identity/publisher work remain explicit. Historical planning
below preserves the earlier issue references and original scope.

## Historical campaign planning

The earlier independent completion campaign covered all open
issues except #51, including partial preparation at genuine owner/external gates.
See [the completion ledger](docs/completion-campaign.md),
[review checklist](docs/completion-review.md) and
[all 230 original criteria](docs/evidence/completion-criteria.json).
Completion PRs #62 foundation -> #63 mixer -> #64 API/creator -> #65
qualification are merged. Exact source 1a482808 passed the complete available local matrix and
both full act sequences; [install candidate 9](docs/candidate-9-install.md) and
[review the audit](audits/audit-2026-11-13.md). Intended slug:
**decky-stream**; compatibility/migration and final branding review remain explicit.
#51 now holds two separate research journeys (monetization and Decky Store).
After source review/merges, remaining acceptance was consolidated into #46,
preserving original criteria and evidence; #68 is a newly demonstrated scoped defect.

Updated 2026-11-13. **Milestone 2 source PRs #52–#57 are merged; target/CI and
owner publication acceptance remain open. Milestone 3 features #47/#24/#48/#49/#50
were merged through PRs #58–#60 with available local checks passed. #51 remains
separate research. Device/CI/review acceptance remains open.** See the
[M3 implementation ledger](docs/milestone-3.md).
The organization, final product name, domain and payment destination remain TBD.
**Decky Stream** is the owner-selected working display name. Final identity and
name/mark review remain pending. The goal is
simple, reliable OBS streaming from Steam Deck, with a free local core and an
optional way to support its development.

## Starting point

PRs [#32](https://github.com/szmyty/obsgod/pull/32),
[#33](https://github.com/szmyty/obsgod/pull/33) and
[#34](https://github.com/szmyty/obsgod/pull/34) merged in that order. Their combined
source is on the default branch. All 22 nonprimary remote branches were archived
at their exact tips and deleted; see [the archive record](docs/branch-archive.md).
The default branch remains `master`: the integration cannot perform the requested
rename to `main` (HTTP 403). The owner can rename it on GitHub's Branches page;
the candidate workflow accepts either name. New M2 draft branches are review
checkpoints after that consolidation; see [the implementation ledger](docs/milestone-2.md).

Preview6 has substantial local qualification, including real native OBS audio
and game/fallback transitions. Actual Steam Deck audio, Flatpak/Gamescope privacy,
controller/session/performance and viewer proof remain open. Fresh GitHub jobs
ran zero steps because of the account billing lock. A merge or a cross-build
does not complete these acceptance criteria. Read the
[exact-source evidence](docs/audio-capture-upgrade.md).

## Milestone 2: supported public launch and optional funding

[Milestone 2](https://github.com/szmyty/obsgod/milestone/2) ·
[parent #23](https://github.com/szmyty/obsgod/issues/23).
This is a priority order; issue bodies retain their specific dependencies.
Independent qualification and repairs can proceed while naming is pending.

1. **Set the identity once.** Choose the tools organization, product name,
   repository ownership and durable product boundary
   ([#35](https://github.com/szmyty/obsgod/issues/35)). Prepare a compatible
   repository/plugin/updater/data transition before any transfer or rename
   ([#36](https://github.com/szmyty/obsgod/issues/36)). Preserve old commands,
   installed plugin identity, private keys, settings, recordings and rollback.
   Strict updater URL allowlists need a deliberate transition; GitHub redirects
   alone do not establish compatibility.
2. **Decide distribution feasibility early.** Check truthful source provenance,
   licensing, native-build and monetization rules with Decky's current policy
   ([#37](https://github.com/szmyty/obsgod/issues/37)). Keep a verified direct
   channel available independently of Store admission.
3. **Finish foundation acceptance.** Carry forward
   [#8](https://github.com/szmyty/obsgod/issues/8),
   [#10](https://github.com/szmyty/obsgod/issues/10) and
   [#16–#22](https://github.com/szmyty/obsgod/issues/22).
   Repair demonstrated gaps and record exact Deck/SteamOS/OBS/Decky versions,
   local clips, live viewer audio/video, capture privacy, update/recovery and
   required CI/review evidence. The earlier milestone was administratively
   closed; its outstanding issue criteria were not passed by that closure.
4. **Create one coherent brand.** Use
   [egohygiene/identity](https://github.com/egohygiene/identity) as a consumer
   framework after the name/organization decision
   ([#38](https://github.com/szmyty/obsgod/issues/38)). Keep approved SVG masters,
   rights/attribution, tokens and reproducible manifests in the product's
   `.identity/` source. Pin compatible tooling and use supported manual v1
   authoring; do not assume its current `init` produces v1. Generate approved
   assets for Decky, GitHub, docs and landing page without changing Identity.
5. **Make installation and configuration predictable.** Complete
   [#11](https://github.com/szmyty/obsgod/issues/11),
   [#19](https://github.com/szmyty/obsgod/issues/19) and
   [#20](https://github.com/szmyty/obsgod/issues/20): guided Desktop installation,
   Decky detection and an explicit dependency path, OBS 28+ with its bundled
   WebSocket, capture/audio prerequisites, idempotent upgrade, repair and
   rollback. Do not install a second WebSocket plugin. Diagnose session,
   permissions, graphics/audio, space, offline/network and cancellation failures.
   Use **flags > environment > XDG config file > defaults**, versioned profiles,
   useful CLI help and machine-readable status. Put config, data, state, cache
   and runtime files in their respective XDG locations. Keep secrets out of
   required command arguments and diagnostic output; environment support does
   not require exposing keys in process listings or shell history.
6. **Polish the controller experience.** Redesign setup, streaming status,
   audio/capture selection and actionable recovery
   ([#39](https://github.com/szmyty/obsgod/issues/39)). Preserve automatic status,
   manual refresh, readable/copyable filtered diagnostics, state-driven controls
   and accessible status beyond color. Add connection/password recovery
   ([#25](https://github.com/szmyty/obsgod/issues/25)). Basic game-only, black and
   plain-text idle acceptance stays in #21/#22; richer media is Milestone 3.
7. **Support more destinations.** Guide Kick, Twitch, YouTube and custom RTMP(S)
   setup, validate each supported path and keep keys private
   ([#40](https://github.com/szmyty/obsgod/issues/40)). Do not claim OAuth or
   simultaneous multistream support from a preset alone.
8. **Make leaving easy.** Provide uninstall, reset and explicit complete
   owned-data wipe ([#41](https://github.com/szmyty/obsgod/issues/41)). Show the
   scope, offer a separate recordings/media choice, stop owned services safely,
   and preserve ordinary OBS, other plugins and shared dependencies.
9. **Prepare a sustainable public launch.** Establish supported versions,
   release/security/support operations and exact artifact qualification
   ([#44](https://github.com/szmyty/obsgod/issues/44)); add an optional, clearly
   labelled **Support development** button at the bottom of the panel
   ([#42](https://github.com/szmyty/obsgod/issues/42)); prepare the documentation
   site and landing page with install/update/uninstall/troubleshooting/privacy
   guidance ([#43](https://github.com/szmyty/obsgod/issues/43)). The owner selects
   and verifies the recipient/account. Local operation, Stop, recovery and
   accessibility stay available without payment or a service login.
10. **Launch the qualified direct channel, then the Store if eligible.** Prepare
    concrete release artifacts, provenance, installation/adoption evidence and
    approval packets ([#45](https://github.com/szmyty/obsgod/issues/45)). Publish
    releases/sites or submit to another repository only with the applicable
    authorization. A direct-only outcome is valid; Store listing is external.

### Decky Store constraint

The [2026-11-13 official-source research](docs/store-policy-research.md) supersedes
the earlier categorical summary. The older submission guide says “any LLM based
code”; newer official template/safety text says “majority”/“excessive.” Those
published statements conflict. No majority audit or eligibility determination
exists for this AI-assisted project. Preserve truthful provenance and seek
owner-approved clarification before investing in Store submission.

Additional work includes root-layout/Store build compatibility, real native
Stable/Beta/third-party Preview testing and an approved update-channel boundary.
The panel's check-only button is distinct from the paired Desktop updater;
neither is silently declared approved or prohibited by this research. Voluntary
support-link treatment remains unclear. The [two-journey recommendation](docs/research-51.md)
is to finish the free direct product and defer paid/Store implementation pending
demand evidence and owner/channel choices. No maintainer has been contacted.

## Milestone 3: advanced streaming and validated paid offerings

[Milestone 3](https://github.com/szmyty/obsgod/milestone/3) ·
[parent #46](https://github.com/szmyty/obsgod/issues/46).
Prioritize from actual user needs after a supported launch.

- **Easy advanced profiles:** resolution, FPS, bitrate, encoder, audio and
  destination settings with understandable defaults, validation, previews and
  recovery ([#47](https://github.com/szmyty/obsgod/issues/47)).
- **Richer between-game scenes:** owner-supplied/licensed images, video and
  transitions, keeping the stream active without exposing menus or silently
  switching to whole-screen capture
  ([#24](https://github.com/szmyty/obsgod/issues/24)).
- **More resilient audio and runtime:** device changes, sleep/wake,
  reconnection, capture/session changes and bounded recovery
  ([#48](https://github.com/szmyty/obsgod/issues/48)).
- **Recording, replay and clips:** simple controls, disk limits, retention and
  export ([#49](https://github.com/szmyty/obsgod/issues/49)).
- **Useful stream health:** measured bitrate/dropped frames/audio/network and
  understandable recommendations with private diagnostics
  ([#50](https://github.com/szmyty/obsgod/issues/50)).
- **Separate monetization and Store research:** compare free/voluntary-support/
  optional offerings and direct/Store paths, distinguish real observations from
  unknown demand/capacity/rights, and prepare explicit recommendations/questions
  ([#51](https://github.com/szmyty/obsgod/issues/51)). The bounded
  [research packet](docs/research-51.md) recommends deferring paid offerings and
  Store implementation for now. A future discovery/offer experiment requires its
  own owner choice; no offer, price, provider or account is selected.
- **Preserve the broader ledgers:** architecture/governance
  [#7](https://github.com/szmyty/obsgod/issues/7), reusable API
  [#9](https://github.com/szmyty/obsgod/issues/9), production v1
  [#12](https://github.com/szmyty/obsgod/issues/12), companion boundary
  [#13](https://github.com/szmyty/obsgod/issues/13) and provider/multistream/creator
  ecosystem [#14](https://github.com/szmyty/obsgod/issues/14). Their original
  criteria remain intact; a Steam Deck launch does not complete the ecosystem.

## Revenue and completion

Start with a free useful product and voluntary support. Publish a clear promise,
make installation reliable, demonstrate real users can stream, and learn what
they will fund. Then test one paid extra with explicit costs and support terms.
There is no revenue guarantee or assumed payment provider, recipient or domain.
No tracking/telemetry is implied by success measurement; use voluntary feedback
and the owner's actual payment/support records with appropriate privacy choices.

Close issues from criterion-level source/artifact/device/review evidence. Record
failed, skipped, unavailable and unrun checks separately. Organization creation,
repository migration, creative approval, release/site publication, other-repo
submission and spending remain concrete owner decisions. This proposal performs
none of those actions.
