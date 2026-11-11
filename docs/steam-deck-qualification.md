# Steam Deck preview qualification

## Current Roadmap 1 candidate

Candidate `0.1.0-deck.5` is locally qualified at exact source
`2287ed4c2f3fcc9b8ec42bbd68ac531063b5d578` and available as a **draft review
artifact**, not a release. Read [the acceptance/review packet](roadmap1-acceptance.md)
for downloads, hashes, criterion-level evidence, failed-run repairs and gates.
Go 56/Python 56/Node 8, static/security, actual-package browsers, pinned Decky
installer/updater fixtures, reproducible builds and native OBS media/lifecycle
checks passed. One optional existing-OBS test was skipped. Cross-builds were
not executed. Real Steam Deck/Kick acceptance and owner review remain open.

GitHub Actions jobs were created but no steps ran: GitHub reports an account
billing lock. Their failure/cancelled conclusions do not establish code-test
results. Clearing that lock and running required checks remains a closure gate.

## Historical previews and evidence interpretation

Each [preview release](https://github.com/szmyty/obsgod/releases) carries its exact
source revision in `manifest.json`, artifact hashes in `SHA256SUMS`, and commands,
outcomes and limitations in `qualification.json`. Use that release's receipts;
an earlier passing run does not qualify newer source. This is a hardware preview
and does not establish stable v1 readiness.

## Required evidence

- Go unit/protocol tests, race detection, vet and reachable-vulnerability scan.
- Desktop setup HTTP security and installer safety checks.
- Decky typecheck/build, status-indicator tests and browser rendering checks.
- Reproducible package checksums and a clean-home install from the actual archive.
- Real Linux OBS with synthetic PipeWire video/audio, local recording, local RTMP,
  repeated start/stop, frame dimensions and audio content.
- Real SteamOS / AMD VAAPI / controller / Kick viewer acceptance, explicitly
  unavailable in the cloud runtime and retained under #10.

No user stream key, live provider account or paid resource is used by cloud tests.

## Interpretation

| Environment | Evidence meaning |
| --- | --- |
| Linux x86_64 cloud | Unit/protocol, race, static, installer, browser and native OBS checks can run here. |
| Native OBS container | Real OBS 30.2.3 / GStreamer 1.26.2 / PipeWire / PulseAudio / software H.264/AAC, with synthetic game video and local RTMP. |
| Simulated Decky host | Actual ZIP frontend and SDK browser imports; loader calls and Steam components are fixtures. |
| Linux ARM64 / Windows x86_64 / macOS ARM64 | CLI cross-build checks only; these are not Steam Deck runtime qualifications. |
| Steam Deck / SteamOS | Unavailable here: actual Flatpak sandbox, Gamescope, AMD VAAPI, audio devices, controller focus and session lifecycle. |
| Kick viewer | Unrun here: user URL/key and real channel picture/audio must be checked on the device. |
| GitHub Actions | Current candidate jobs did not start because GitHub reports an account billing lock; local results are not CI receipts. |

The native harness verifies moving, nonblank recorded video, nonblank streamed
video, audio content, repeated start/stop, failed-start cleanup and no unexpected
late connection when a receiver appears. See [reproduction](steam-deck-building.md).
Source repairs were prompted by real integration failures: a first-run wizard,
zero scene scale, preview-dependent capture startup and a transient PipeWire node.

The broader #7–#14 issues remain open. In particular, #10 requires real-device
acceptance; #12's stable v1 requirements are not satisfied by this preview release.
