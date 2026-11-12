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
`codex/deck-audio-capture-modes`. Final clean-source qualification passed; the exact receipts are below.
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


## Final candidate and evidence

The exact qualified source is `33dcd8476606a1ed7a3bbca06e81fb156dfebcc7`,
candidate `0.1.0-deck.6`. Immutable review artifacts are commit
`71143dce72654bae2ad76ebe382dd810990c2c85` on
`artifacts/deck6-audio-game`. Never merge this orphan artifact branch into source.
[Full command/platform/outcome/hash packet](https://raw.githubusercontent.com/szmyty/obsgod/71143dce72654bae2ad76ebe382dd810990c2c85/audio-game-qualification.json)
and [matrices, logs, source research and native proof](https://github.com/szmyty/obsgod/tree/71143dce72654bae2ad76ebe382dd810990c2c85)
are adjacent to the runtime, Decky ZIP and optional standalone updater. All seven public core downloads and internal runtime/updater payloads were
independently verified after upload; native library, preferred source/licenses
and the install command matched ([download proof](evidence/deck6-public-download.json)).
No release
or tag was published, no new PR merged, and no acceptance issue was closed.

Runtime SHA-256:
`23cc2c484b7524756a3b632bf8a8e7231ac7c515c06a08183422ed91b7e82650`.
The app, plugin, updater, native library and preferred source are built from the
same source, with two identical runtime/updater package builds. Later evidence
and continuity-only commits do not relabel these source/artifact receipts.

| Requirement | Available evidence at the exact source | Remaining gate |
| --- | --- | --- |
| Actual output monitor, OBS visibility, mute/gain/track1/monitoring policy | Fresh unit/protocol tests and real OBS decoded recording/RTMP over a default decoy, stale-mixer repair, game-exit/default-output changes | Actual Deck output, microphone and Flatpak audio mapping; silent-audio cause remains unproven |
| Screen/game selection, safe idle/unknown/recording gates and old observer handoff | Go, backend and actual ZIP browser tests | Controller/device interaction and actual installed versions |
| Strict app-filtered video, producer advertisement/echo/identity, unsupported source/buffers | 13 native protocol cases, including EMPTY, mixed DMA-only capability and late duplicate producer rejection | Actual Gamescope build and Steam-menu/game privacy on Deck |
| Black/custom plain-text fallback and continuous output across games | Real OBS local clip and one RTMP output through GameA/placeholder/GameB/unsupported fallback, plus explicit no-game black; decoded picture/audio in all five phases | Actual Deck game launch/exit and session/performance/color behavior |
| No automatic broadcast from game detection | Native started/stopped event counts and later game launch while output off; focused protocol tests forbid Start/Stop | Device retry; no Desktop/Gaming session continuity claim |
| Scene/source isolation and opt-in microphone policy | Scene allowlists disable legacy display/sentinel items, reset file-reading text options; audio enabled in managed output/fallback scenes | Physical microphone and other actual device routes |
| Upgrade/reinstall/updater preservation | Actual archive 5.2-to6 upgrade/repeat with pinned Decky3.3.1 routers/default installer/Desktop updater fixtures; key/settings/media/history/other plugins/ordinary OBS preserved | Actual Deck service/Steam/CDP/loader retry |
| Regression/static/security/build | 64 top-level Go passes (94 including subtests), 70 Python, 9 Node, vet/typecheck/frontend build, zero Go/npm vulnerability findings | One optional existing-OBS read test skipped; six cross-builds compiled only |
| GitHub CI | Fresh candidate jobs recorded with zero executed steps | GitHub account billing lock; no spending or account changes attempted |
| Consumer reception and final acceptance | Owner reports5.2 local/live video working but audio silent | New6 local clip sound, unmuted Kick viewer picture/sound, Steam menus and between-game behavior |
| Review, publication and broader Roadmap2 | Draft34 stacks on33/32; source/rights/notices and candidate prepared | Required reviews, device/CI evidence; any release approval. Arbitrary image/video assets and25 password controls remain deferred |

Final qualification re-executed all required available checks after the fixture
repairs. Historical source `c392033...` failed native bootstrap with OBS207;
`d80e308...` failed a new process-environment test's immediate-read assumption.
Those failures remain recorded separately. The frontend wait retries only207
under a bounded deadline; the process test waits for the unchanged actual
ownership/tag/live predicate and passed100 forced race repetitions. Neither
repair weakened production checks. Old passing receipts were not reused.

For the owner retry: stop output, keep normal Steam open in Desktop Mode, use the
complete verified6 installer in place, select **Capture video → Game only** and
black or custom-message fallback, then return to Gaming Mode. Run a local clip
with audible game content and check it in Videos/OBSGod. Next check an unmuted
Kick viewer on another device while opening Steam menus and switching games.
Observe fallback without a stream restart, then explicitly Stop. If local audio
works but viewer sound does not, check viewer mute/volume before changing capture.
The published-version updater does not fetch this unpublished review checkpoint.
