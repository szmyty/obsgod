# Audio and capture-mode upgrade

## Owner request and observed device result

After following candidate 5.2 instructions, the owner reported that a local clip
saved and played successfully, then that live streaming worked but audio did not.
This is owner-reported video-path evidence, not an instrumented device receipt:
installed versions, audio routes, microphone state and actual media probes were
not supplied. The previous PulseAudio symlink warning remains a lead, not a proven
cause. Do not relabel the cloud native test as actual Deck audio success.

The owner now authorizes a bounded upgrade: repair audio, provide entire-screen
versus game-only video selection, and keep an explicitly started output running
through game changes using a black or custom-message fallback. This activates
the relevant portion of #24/#23; user-facing WebSocket password controls #25,
custom video assets and broader ecosystem work remain deferred. No release,
deployment, new merge or spending is requested by this upgrade.

## Implementation and acceptance plan

- Preserve candidate 5.2 launcher/installer repairs by stacking this draft on #33.
- Inspect host and OBS-visible audio devices; repair routing and persisted source
  volume/mixers without mutating host sockets or global user audio settings.
- Keep game-only video isolated from whole-screen capture. Unsupported or
  ambiguous game discovery must show fallback; never silently capture the screen.
- Keep mode changes explicit and blocked while output is active or unconfirmed.
  Automatic scene changes may never start a broadcast, stop it, or declare it live.
- Keep the stream key, settings, ordinary OBS configuration, recordings, offline
  behavior, redacted diagnostics and safe recovery intact. Legacy settings hashes
  must still load after adding optional fields.
- Test real media audio above a numerical threshold, with digital silence as a
  negative control, and test the selected video source separately from the full
  screen and transitions. Record exact source/artifact revisions and limitations.

Game-only is a video selection, not per-application audio isolation. The selected
system-output monitor can include other applications; the microphone remains
opt-in. Native Linux/fixture evidence cannot establish SteamOS/Gamescope/VAAPI,
controller/session behavior or actual Kick sound. A new device retry remains a
required gate even if all available local checks pass.

## Current status

Implementation is prepared as candidate `0.1.0-deck.6` in draft
[PR #34](https://github.com/szmyty/obsgod/pull/34), stacked on #33/#32, on
`codex/deck-audio-capture-modes`. Final clean-source qualification is in progress.
Development tests passed actual OBS audio routing/media and continuous game/idle
transitions, plus the portable plugin's app selection/unsupported/buffer/producer
identity cases. These development receipts do not qualify the final package.

The app-filtered source first verifies a producer-advertised non-modifier BGRx
format with Gamescope's app-ID parameter, pins that producer's object serial,
and verifies negotiated selection before accepting frames. Late duplicate or
removed producers, unsupported selection and malformed buffers fail closed.
Corrupt/empty buffers are dropped; stale frames become black. The observer only
selects Game/Idle scenes while an existing output is confirmed, and reroutes
audio once per game identity change without starting/stopping output. Mode
changes wait for the previous observer to release ownership before saving.

The default legacy capture remains the compositor feed. Game-only video and
black/custom-message fallback are explicit choices. Audio remains the selected
system output plus opt-in microphone; viewer mute/volume and actual Deck sound
must be checked separately. A real game's static/no-new-commit picture may
trigger the conservative stale-frame fallback. Capture-plugin ABI/loading,
Gamescope semantics, graphics/performance and actual Kick reception still need
recorded device qualification. No external custom assets are included.

The portable builder and full native dependency notices/source descriptors are
included with preferred capture source. No new Flatpak filesystem permission,
Pulse socket cleanup or host volume changes are applied. Do not use older candidate receipts to qualify
newer source. No acceptance issue is closed by code or a saved clip notification.
