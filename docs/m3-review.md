# Milestone 3 owner and publisher packet

Prepared 2026-11-13. The owner authorized #47/#24/#48/#49/#50 and expressly
excluded #51. Implementation is prepared in draft **[#58](https://github.com/szmyty/obsgod/pull/58)
→ [#59](https://github.com/szmyty/obsgod/pull/59) → [#60](https://github.com/szmyty/obsgod/pull/60)**.
No source merges or issue closures occurred. Default `master` remains at
`ed7d100d356ce803d2cb1c1afef3836759deef10`.

## Exact candidate and review downloads

- Candidate: **0.1.0-deck.8**; clean source `bf72ca4ae028f78895eadee6d3874734a1cccd05`.
- Qualified tree: `b66b749199928f79658abe5daeeb5bd26a65b6e7`.
- Runtime SHA256: `d33c976905e6cde8f7ab9491eef62a08a394c80b0c35d65a61bafa34a27dd9f2`.
- Immutable review artifact commit: `9ad051ecbb41df92c723a54bdfb6aaaeb1097898` on
  `artifacts/m3-deck8-review`. Never merge this orphan artifact tree into source.
- [Download and install](candidate-8-install.md),
  [complete qualification](https://github.com/szmyty/obsgod/blob/9ad051ecbb41df92c723a54bdfb6aaaeb1097898/qualification.json),
  [criterion ledger](evidence/m3-criteria.json),
  [all artifacts and receipts](https://github.com/szmyty/obsgod/tree/9ad051ecbb41df92c723a54bdfb6aaaeb1097898).

The current evidence/documentation commits do not rebuild or relabel this
candidate. Passing receipts qualify only the exact source and bytes above.
Earlier failed deccefd/1fe5ec1 attempts are preserved in the packet and are not
passing qualification. They exposed synthetic producer scheduling/lifetime races
and a real retained-stream-counter defect. Fresh advancing-pair confirmation
repaired the latter without changing timeout or frame gates.

## Qualification and limits

| Check | Result at the exact candidate source |
| --- | --- |
| Go race | 175 top-level tests / 338 pass events; one optional existing-OBS test skipped |
| Desktop/backend Python | 121 passed |
| Panel | 19 Node tests, typecheck and build passed |
| Static/security | vet passed; zero Go/npm findings |
| Packaging | Runtime/updater rebuilt twice identically; internal payload hashes verified |
| Actual-package browser | Seven fresh/old4/old6/panel/M3/support flows passed |
| Decky/updater/removal | Pinned Decky 3.3.1 protocol, paired install/update/repair/rollback checks, preserved settings/media, checksum rejection and own-plugin removal passed with declared service/network fixtures |
| Native Linux OBS30.2.3 | Three suites passed: capture protocol; actual audio/recording/replay/profiles/restarts/password recovery; game/idle/image/video transitions and decoded loopback audio/video |
| Site preview | 11 tests, extra safety fixtures and 40 viewport cases passed; no external requests |
| Other platform binaries | Six compiled only; execution unrun |
| file:// preview | Unavailable under browser policy; offline loopback HTTP passed |
| GitHub CI | Unavailable: [candidate job](https://github.com/szmyty/obsgod/actions/runs/43375325487) executed zero steps due to account billing lock |
| Actual Deck/provider/adoption | Unrun for candidate 8; no newer capability is qualified by older user reports |

Native receipts include actual 540p30/720p60 encoded dimensions with moving video
and audible 440 Hz audio; local recording/replay/stream coexistence; new finalized
replay paths; preserved cancellation/export; reserve-triggered local finalization;
two live audio-route changes preserving mixer policy; positive measured bitrate,
FPS and audio signal; muted custom-video soundtrack; missing-asset black fallback;
and no implicit restart. These are synthetic Linux/software-encoder observations,
not SteamOS/Flatpak/Gamescope/AMD/controller or provider-viewer proof. GPU usage
and viewer reception remain unknown. No adaptive quality or hidden telemetry is
introduced. Focusable panel actions do not register a global Steam button chord.

## Verified facts and unresolved owner facts

The repository is currently `szmyty/obsgod`; Decky Stream is the selected working
display name. Existing `obsgod`/`OBSGod` CLI/plugin/storage identities and the
trusted update repository are retained. The repository MIT license preserves
its 2020 Christian Muehlhaeuser copyright notice; do not claim exclusive ownership
of all inherited code. Packages retain notices, capture preferred source and
replaceable LGPL Decky API source/license inputs. OBS/obs-gstreamer remain
separately installed software. No new dependency or final branding asset was
introduced in this batch.

Final organization, migration, durable mark/domain, approved Identity SVG masters,
creative/rights/attribution decisions and Store eligibility remain separate M2
owner decisions. No Identity repository change or unsupported provenance
attestation was made. Custom idle assets require the user's explicit rights
acknowledgement; original synthetic test assets do not establish production asset
rights. Wallet activation remains deliberately deferred and #51 is excluded.

## Consumer actions, adoption and publication gates

1. Review the three drafts and exact evidence. Required human source review is
   pending; a source merge does not close hardware acceptance.
2. Install the checksum-verified candidate on the real Deck and complete the
   [device checklist](m3-device-acceptance.md), recording versions, clips, provider
   viewer sound/picture, controller use and named failures/performance limits.
   Actual successful candidate 8 adoption has not been demonstrated.
3. Resolve the GitHub account billing restriction and rerun required jobs at the
   exact reviewed source; no account/payment change or spending was performed.
4. Retain #24's #10/#17/#21 dependencies and all original issue criteria. Keep
   parent #46 and broader #7/#9/#12/#13/#14 ledgers open. #51 remains out of scope.
5. After the remaining acceptance and M2 identity/rights decisions, separately
   approve an exact release candidate/artifacts, responsible publisher, GitHub
   release destination, documentation/landing hosting destination and any other
   repository submission. Those owners/destinations are not invented here.

Proposed direct release destination remains this repository's GitHub Releases;
it has not been published. No site hosting deployment, Decky Store submission,
repository transfer, external maintainer contact, paid offering, account creation,
payment or spending was performed. The review checkpoint is the concrete result
for review; it is distinct from a release and from an environment snapshot.
