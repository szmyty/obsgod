# Steam Deck preview qualification

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
| GitHub Actions | No current branch checks were reported during implementation; local results are not CI receipts. |

The native harness verifies moving, nonblank recorded video, nonblank streamed
video, audio content, repeated start/stop, failed-start cleanup and no unexpected
late connection when a receiver appears. See [reproduction](steam-deck-building.md).
Source repairs were prompted by real integration failures: a first-run wizard,
zero scene scale, preview-dependent capture startup and a transient PipeWire node.

The broader #7–#14 issues remain open. In particular, #10 requires real-device
acceptance; #12's stable v1 requirements are not satisfied by this preview release.
