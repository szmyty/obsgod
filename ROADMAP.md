# Product roadmap

Updated 2026-11-13. **Milestone 2 source PRs #52–#57 are merged; target/CI and
owner publication acceptance remain open. Milestone 3 features #47/#24/#48/#49/#50
are implementation-authorized; #51 is excluded.** See the
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

Checked 2026-11-12: the official
[submission policy](https://wiki.deckbrew.xyz/en/plugin-dev/submitting-plugins#ai-llms-and-so-on)
rejects LLM-based code. The official
[addition template at `0fdb6a6`](https://github.com/SteamDeckHomebrew/decky-plugin-database/blob/0fdb6a686d7c0e79366f85c9d551576cad3ecee5/.github/PULL_REQUEST_TEMPLATE/plugin_addition.md)
also requires: “Generative AI was NOT used to write a majority of the code I am
submitting.” This project has substantial AI-assisted implementation history;
no majority audit or eligibility decision exists. Do not hide provenance or
check that box without evidence. This is the Store's admission policy, not a
legal conclusion about the project.

The current native `.so` submission path also requires developer Stable/Beta
and independent SteamOS Preview testing. Cloud native OBS tests do not supply
that proof. The official
[monetization policy](https://wiki.deckbrew.xyz/en/plugin-dev/submitting-plugins#monetization)
is restrictive about paid core/accessibility features. Neither a Store payment
API nor blanket permission for a support link has been established. Recheck
these policies before any submission; direct distribution remains independent.

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
- **Validate one optional paid offering before building it:** interview willing
  users, test an owner-approved offer and measure conversion, net receipts,
  fees, operating cost and support time
  ([#51](https://github.com/szmyty/obsgod/issues/51)). Candidate experiments include
  optional licensed scene packs, paid setup/support or a separately costed hosted
  service. None is selected, promised or allowed to obstruct the local core.
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
