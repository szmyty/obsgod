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
The preview checks the real rendered program scene for nonblank pixels before starting a broadcast;
this is not proof that every game, audio route or SteamOS build works.

2026-11-11 implementation checkpoints: PR #15 preserves 0cbcb57 and 02c3f16.
Desktop archive install/configure/reload/uninstall passed in Chromium. The actual
Decky frontend ZIP passed in a simulated loader. Native OBS 30.2.3 with GStreamer
1.26.2 and synthetic PipeWire/PulseAudio passed moving 720p recording, nonblank
local RTMP with audio, repeated start/stop, failed-start cleanup and a later
listener receiving no unexpected connection. These are Linux synthetic results,
not Steam Deck or Kick acceptance.

Integration repairs included disabling the first-run OBS wizard in global.ini
and user.ini, setting nonzero scene scale, checking the rendered scene, and
running capture independently of transient preview visibility during preflight.
Stop explicitly pauses that capture. A three-second bounded node-readiness retry
handles the synthetic producer's reconnect transition. Backend cancellation also
covers Stop arriving before Start's child process has attached.

Security qualification required upgrading the pinned compiler to Go 1.27.4,
patching jsonparser to v1.1.2, and replacing Decky's old Rollup preset. Stream keys
remain local/stdin only; normal output is redacted. Publication will be a hardware
preview from a clean exact commit with fresh artifact receipts; no roadmap issue
is closed by these synthetic tests. See steam-deck-building.md for reproduction.

2026-11-11 installer follow-up: the user reported that the desktop launcher
opened and immediately closed a terminal. They then reported successful manual
installation with `python3 install.py --no-launch` and an open browser setup page.
That establishes their manual install/browser recovery, not the cause of the
original double-click behavior or successful game capture.

Confirmed preview defects: setup child output was discarded, the desktop entry
did not hold the terminal, and setup attempted to launch a browser before serving
HTTP. The installer now runs setup visibly in the foreground; launcher failures
wait for Enter; the server serves before browser launch. Regression tests execute
the desktop entry for missing extraction and setup crashes, including spaces,
literal percent escapes and file URIs. Browser qualification now launches the
actual archive entrypoint instead of importing SetupServer directly. These are
installer/startup changes; the OBS streaming implementation is unchanged.
