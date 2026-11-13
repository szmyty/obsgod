Current completion review: [candidate9 owner packet](completion-review.md),
[install guide](candidate-9-install.md), [230-criterion ledger](evidence/completion-criteria.json)
and [post-review consolidation proposal](finalboss-plan.md). Exact qualified source
1a482808 passed the full available local matrix; hardware/hosted/review gates remain.
Candidate8 details below are historical. No issue is closed or release published.

# Milestone 3 streaming implementation

Owner authorized 2026-11-13: implement #47, #24, #48, #49 and #50. **#51 is
excluded.** Existing architecture/API/production/companion/ecosystem ledgers
remain intact; this batch does not expand into those projects.

Base: `ed7d100d356ce803d2cb1c1afef3836759deef10` on default `master`.
Work proceeds in a shared isolated checkout with draft PR checkpoints.

Candidate **0.1.0-deck.8** is prepared at exact source
`bf72ca4ae028f78895eadee6d3874734a1cccd05` in drafts #58 → #59 → #60.
See [the owner packet](m3-review.md), [full matrix](evidence/m3-qualification.json),
[criterion ledger](evidence/m3-criteria.json) and [install guide](candidate-8-install.md).
Actual device/CI/review acceptance remains open; no source merge or issue closure.

## Acceptance ledger

| Issue | Source work | Qualification and remaining evidence |
| --- | --- | --- |
| #47 | [Profiles](advanced-profiles.md): versioned profiles, validated advanced video/audio settings, presets, preview/reset and secret-free export | Source implemented; available local qualification passed at the exact candidate revision. Presets are starting points; no measured Deck hardware promise. Actual picture/audio/performance/controller evidence required. |
| #24 | [Idle media](idle-media.md): local image/video, rights acknowledgement and safe game transitions | Source implemented; available local qualification passed at the exact candidate revision. Preserve original #10/#17/#21 dependencies and actual Deck transition/privacy evidence. |
| #48 | [Recovery](runtime-resilience.md): bounded audio-device/session observation without output starts | Source implemented; available local qualification passed at the exact candidate revision. Named headset/Bluetooth/session/Deck failure cases must be qualified on device. |
| #49 | [Recording/replay](recording-replay.md): confirmed controls, clip/storage/export choices | Source implemented; available local qualification passed at the exact candidate revision. Actual moving video/audio, file finalization and controller operation required. |
| #50 | [Health](stream-health.md): measured fresh/unknown metrics, useful advice and redacted diagnostics | Source implemented; available local qualification passed at the exact candidate revision. Device/network/load degradation acceptance remains required. |

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
