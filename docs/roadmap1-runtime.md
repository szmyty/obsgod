# Roadmap 1 runtime changes and remaining device gates

The runtime preserves the isolated OBSGod OBS configuration, generated private
WebSocket password, explicit broadcast request, rendered-frame preflight and
confirmed output start/stop. OBS remains a graphical application; background
operation is not a headless OBS server or proof that sessions survive a mode
switch.

## Startup and connection

Each authenticated connection attempt is limited to one second. OBS readiness
has a separate 20-second budget, including launch and frontend readiness. These
are provisional defaults, with cancellation and early process-exit handling;
actual Steam Deck cold/warm timings still require measurement. The outer CLI
operation budget remains 75 seconds so capture setup and a local recording do
not borrow their entire budget from startup.

Connection failures expose fixed stages only: listener unavailable,
authentication failure/incomplete authentication, or authenticated OBS frontend
not yet accepting requests. Raw OBS output, endpoints and passwords are not
written to the diagnostic console. Failed or cancelled authentication closes
its transport, including an upgraded socket that never supplies Hello.

The launch no longer forces `QT_QPA_PLATFORM=xcb`. Current official OBS Flatpak
permissions provide Wayland and fallback X11; forcing X11 while Wayland is
available can select a backend whose socket the sandbox has not exposed. The
current Steam session replaces stale inherited display/session variables.
Missing both X11 and Wayland display variables fails immediately.

The obsolete `--disable-shutdown-check` flag is removed. Both the older
`obs-studio/safe_mode` marker and current `.sentinel/run_*` crash markers are
detected without deletion. Their presence is reported as a possible recovery
prompt, not proof that a prompt caused the owner's timeout. Safe Mode is never
selected automatically because it disables the required WebSocket and capture
plugins. A stuck startup needs inspection of the **managed** OBS window; an
ordinary OBS launch uses a different configuration. `deck open-obs` is an explicit
visible Desktop recovery action using the managed profile, without automatic
stream/recording. It refuses a duplicate managed process or occupied control port.
The Desktop setup offers this action without requiring a terminal command.

## Snapshot contract

Existing result fields remain. The additive fields are:

- `process`: `running`, `absent`, or `unknown`.
- `connection`: `ready`, `disconnected`, or `unavailable`.
- `output_known`: true only for a verified managed stream/recording snapshot,
  or when both managed process and control listener are absent.
- `recording`: OBS-reported local recording state when output is known.
- `capture`: `available`, `unavailable`, or `unknown` for the Gamescope feed.
- `frames`: `visible`, `blank`, or `unknown` for sampled rendered output.
- `game`: `unknown`; feed presence does not establish that a game is running.
- `runtime.websocket_version`: the connected OBS WebSocket version.

A streaming state does not establish viewer-side reception or picture/sound.
Active output retains recovery Stop even if capture is blank or unavailable.
Action errors return a fresh conservative snapshot instead of replacing output
state with a generic error. Recording and streaming remain separate facts.
Unreadable environment information for an owned OBS process stays unknown,
whereas an identifiable ordinary OBS profile is left alone. Starting a new
stream refuses an existing local recording before changing capture. Failure of
a repeated Start preserves a preexisting stream; failed/cancelled new-start
capture cleanup runs only after both stream and recording are confirmed idle.
Frame health samples the current program scene, not an unused managed source.

## No-game boundary

A local test now launches/authenticates OBS before checking capture. No game
process check gates startup or control. Missing-feed and blank-frame messages
report actual observations, with no unconditional instruction to open a game.
The existing Gamescope PipeWire source remains the supported capture candidate;
there is no custom banner or new automatic broadcast on game launch/exit.

Real usable no-game Gaming Mode frames, game launch/exit transitions, Flatpak
rendering, AMD encoding, game/microphone audio and Kick reception remain explicit
acceptance gates. These changes cannot establish those results in a native
Linux or protocol fixture. A no-game black feed remains a blocker under #21,
not a reason to mark that issue complete or defer its acceptance to Roadmap 2.

## Inspected upstream sources

- OBS 33.0.1 revision `65c320b46e1af5c7a555161aea6182cdf7a8c524`:
  [official Flatpak manifest](https://github.com/obsproject/obs-studio/blob/65c320b46e1af5c7a555161aea6182cdf7a8c524/build-aux/com.obsproject.Studio.json),
  [argument parser/help](https://github.com/obsproject/obs-studio/blob/65c320b46e1af5c7a555161aea6182cdf7a8c524/frontend/obs-main.cpp),
  [recovery prompt](https://github.com/obsproject/obs-studio/blob/65c320b46e1af5c7a555161aea6182cdf7a8c524/frontend/OBSApp.cpp),
  [crash sentinel storage](https://github.com/obsproject/obs-studio/blob/65c320b46e1af5c7a555161aea6182cdf7a8c524/frontend/utility/CrashHandler.cpp).
- [Flatpak 1.16.1 socket documentation](https://github.com/flatpak/flatpak/blob/1.16.1/doc/flatpak-build-finish.xml):
  fallback X11 is exposed only when no Wayland socket exists.
- [OBS 30.2.3 legacy flag](https://github.com/obsproject/obs-studio/blob/144599fbff18e348652ccadfc3ca08794a03d970/UI/obs-app.cpp):
  the previous shutdown-check flag existed here, but not in current OBS 33.

The owner's actual installed versions and cause of the observed startup timeout
remain unverified until fresh device diagnostics are available.
