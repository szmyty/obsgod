# Milestone 3 streaming implementation

Owner authorized 2026-11-13: implement #47, #24, #48, #49 and #50. **#51 is
excluded.** Existing architecture/API/production/companion/ecosystem ledgers
remain intact; this batch does not expand into those projects.

Base: `ed7d100d356ce803d2cb1c1afef3836759deef10` on default `master`.
Work proceeds in a shared isolated checkout with draft PR checkpoints.

## Acceptance ledger

| Issue | Source work | Qualification and remaining evidence |
| --- | --- | --- |
| #47 | Versioned profiles, validated advanced video/audio settings, presets, preview/reset and secret-free export | Implementation pending. Presets are starting points; no measured Deck hardware promise. Actual picture/audio/performance/controller evidence required. |
| #24 | Local image/video idle media, rights acknowledgement, game-aware safe transitions | Implementation pending. Preserve original #10/#17/#21 dependencies and actual Deck transition/privacy evidence. |
| #48 | Bounded audio-device/session observation and recovery without output starts | Implementation pending. Named headset/Bluetooth/session/Deck failure cases must be qualified on device. |
| #49 | Confirmed local recording/replay controls, safe clip/storage/export choices | Implementation pending. Actual moving video/audio, file finalization and controller operation required. |
| #50 | Measured fresh/unknown health, useful advice and redacted diagnostics | Implementation pending. Device/network/load degradation acceptance remains required. |

## Invariants

- Explicit Start remains the only path that starts broadcasting. Recovery,
  restored connections, game detection, media import and profile changes never do.
- Settings and media changes require confirmed idle output, including replay.
  Stop streaming does not silently cancel local recording or replay.
- Game-only capture never falls back to whole-screen capture. Ambiguity uses the
  configured idle scene. Local media never requires a network URL or embeds audio
  that silently changes the selected system/microphone policy.
- Profile exports and support bundles exclude keys, passwords and destination
  secrets. No undisclosed telemetry, account or paid service is introduced.
- Preserve existing configuration/credential bindings and user media. Retention
  and removal need an explicit reviewed scope; ordinary OBS remains independent.

## Qualification

Run focused checks during implementation and the complete applicable matrix on
the final clean revision. Record exact commands, tool/platform versions, source,
artifacts and outcomes, including failed/skipped/unavailable/unrun separately.
Do not apply candidate7 receipts to newer source. Cloud native OBS and browser
fixtures do not establish actual SteamOS/Flatpak/Gamescope/AMD/controller/provider
or independent adoption proof. CI must execute successfully; a billing-blocked
zero-step run is not a pass.

No release, deployment, Store submission, repository transfer or spending is
authorized here. Keep issues open until all their acceptance evidence exists.
