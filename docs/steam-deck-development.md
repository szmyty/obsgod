# Steam Deck preview implementation

User journey: install to the user's home in Desktop Mode, enter a generic RTMP(S)
server and stream key on the device, install the included Decky ZIP, then start and
stop from Gaming Mode's Quick Access menu. No provider account API is required.

Implementation boundary:
- Go OBS automation uses the pinned goobs WebSocket v5 adapter.
- An isolated OBS Flatpak configuration owns its profile, collection and random
  WebSocket password. Existing OBS settings are not edited.
- Gamescope's PipeWire node feeds the upstream obs-gstreamer source. PulseAudio
  sources capture the default game output and optional default microphone.
- Desktop setup is a short-lived, authenticated loopback web application.
- The Decky backend invokes the bundled CLI and returns redacted JSON. No root
  plugin flag, additional daemon or public HTTP listener is required.
- Kick-specific UI wording stays outside reusable OBS automation.

The preview must distinguish automated Linux/mock-OBS qualification from real
SteamOS, controller, Gamescope, VAAPI and Kick evidence. Hardware validation stays
open under #10. This work does not close the broader #7–#14 roadmap.

## Working record

2026-11-11: cloned clean master d0268d13381b463f5950d202917f437a6288a3e4.
No AGENTS.md was present. Existing two CLI tests passed with Go 1.24.13.
Existing GitHub authentication works through the managed proxy; default sandbox
network access cannot reach the proxy. Docker 28.4.0 is available through the local
socket when sandbox permissions allow access. Branch-protection detail API is
403 for the injected integration; branch metadata reports master unprotected.
No published releases existed at inspection. No paid execution is authorized.

Official capture references inspected:
- https://github.com/ValveSoftware/gamescope/blob/master/src/pipewire.cpp
- https://github.com/fzwoch/obs-gstreamer/tree/v0.4.1
- https://github.com/flathub/com.obsproject.Studio.Plugin.Gstreamer
- https://github.com/SteamDeckHomebrew/decky-plugin-template

Upstream Gamescope issues #2508/#1898 describe black-frame/Steam UI limitations.
The preview checks for a real nonblank source image before starting a broadcast;
this is not proof that every game, audio route or SteamOS build works.
