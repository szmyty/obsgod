# OBSGod Steam Deck reliability candidate

OBSGod runs an isolated OBS Studio Flatpak and exposes streaming controls in
Decky's Quick Access panel. Stock OBS still needs a graphical session; this is
managed background OBS, not a headless OBS server. SteamOS/Linux x86_64 is the
supported target. Normal use does not disable SteamOS read-only protection.

**The audio/capture upgrade is under draft review.** Use the candidate and checksums identified
in its draft PRs, not an older published preview as evidence of these fixes.
Cloud tests do not establish actual Steam Deck, Flatpak, Gamescope, AMD encoder,
controller, audio or Kick compatibility. Required device checks remain open.

## Install or upgrade

1. In **Desktop Mode**, download the reviewed candidate archive ending in
   `_linux_amd64.tar.gz` and extract the entire archive. Leave an existing OBSGod
   installation in place; settings and the stream key should be preserved.
2. Make sure **Decky Loader** is installed and Steam is running normally in
   Desktop Mode. Decky is part of the **••• Quick Access panel** in Gaming Mode;
   it is not a normal Desktop Applications entry. If Decky is missing or its
   frontend is unavailable, the installer stops with a concrete recovery step.
   Follow [Decky's official installation](https://decky.xyz/) if needed, then
   rerun OBSGod. Do not manually delete plugin directories or run OBSGod as root.
3. Open **Install OBSGod.desktop** in the extracted folder and choose **Execute**
   if asked. Keep the terminal open. The installer checks dependencies, verifies
   its files and installs both the app and the exact bundled OBSGod Decky plugin.
   Its final result stays visible; errors must not disappear with the terminal.
4. In **OBSGod Setup**, enter the server URL and secret key from your Kick
   dashboard. For the initial test use 4500 kbps, 30 fps and AMD H.264; switch to
   software H.264 if hardware encoding fails. Microphone is off unless selected.
   Save and choose **Finish and close setup**. Existing settings do not require
   key re-entry. Never share the private setup link or the key.
5. Return to **Gaming Mode**, then open **••• → Decky → OBSGod**. Make a
   **10-second test clip** first. This never broadcasts, so a red streaming dot
   during the clip is normal. The clip is saved in **Videos/OBSGod**; check its
   video and sound in Desktop Mode before broadcasting.
6. Choose **Start streaming**, then watch the Kick channel on another device.
   Confirm both picture and sound. Use **Cancel operation** while starting or
   **Stop streaming** when output is active. Unknown output retains a recovery
   Stop action; inspect OBS and the channel if stopping cannot be confirmed.

A game is not required for OBS lifecycle or its control connection. Actual
full-screen capture must still deliver usable nonblank frames before a test or
broadcast starts. Game-only mode permits the explicitly selected between-game
screen when no verified game capture is available. Some Gamescope versions cannot capture the Steam UI with no game; a
blank/unavailable feed is an explicit platform blocker, not proof that OBS
failed to launch. Custom idle images/videos belong to Roadmap 2.

If the launcher is opened as text, open Konsole in the extracted folder and run
`python3 install.py`. `--no-launch` installs without opening setup. Use the normal
unified installer for a complete install; an explicitly requested app-only
repair does not establish that Decky's plugin was upgraded.

## Live state and diagnostics

Status updates automatically. **Refresh status** remains available for a manual
resynchronization. The icon and panel use the same observations:

| Indicator | Meaning |
| --- | --- |
| Green — OBS streaming | OBS reports active output, no reconnect, and recent byte progress. |
| Red — Stopped | Output is confirmed inactive, or the managed process/listener is absent. |
| Amber — Connecting / stalled | Output is reconnecting or recent byte progress stopped. |
| Amber — Check OBS | Output is unconfirmed; it may still be live. |
| Amber — Setup required | Complete local configuration. |

A click is not proof of a stream transition. Controls follow current state;
repeated requests are coalesced and successful stream notifications follow
confirmed transitions. Action errors do not overwrite a still-live stream.
Green describes OBS output health, not what a Kick viewer receives.

The **Diagnostic console** below Refresh shows startup stages and persists the
latest 100 filtered events. **Copy console log** copies all retained pages,
including UTC timestamps, severity and plugin version. Keys, URLs and raw OBS
output are excluded. Copying does not change output state. If copying fails,
the panel says so and leaves the console selectable. Logs live beneath
`~/.local/state/obsgod/diagnostics/` (or `$XDG_STATE_HOME/obsgod`).

For startup failure, copy the log while still in the same Gaming Mode session.
Report the visible error and installed versions. Switching to Desktop may end
OBS, so its absence afterward does not prove launch never occurred. Startup has
separate bounded connection and cold-start budgets; a timeout is not a diagnosis.
A recovery/safe-mode dialog, display failure, disabled WebSocket or authentication
mismatch must be distinguished through observed diagnostics. Never start a
second unmanaged OBS instance to work around an occupied control port.

## OBS, capture and settings

Compatible OBS 28+ includes **obs-websocket**. OBSGod verifies the installed OBS
and capture dependencies and maintains an enabled local WebSocket listener with
a random password; a separate WebSocket plugin download is normally unnecessary.
User-facing password change/reset controls are deferred to Roadmap 2.

Configure in Desktop Mode and start inside Gaming Mode. Session switching may
terminate OBS; Desktop-to-Gaming stream continuity is not promised without
recorded platform evidence. The launcher follows the current Steam graphical,
D-Bus and audio session without forcing an incompatible Qt backend.

Settings live in `~/.config/obsgod/deck.json`; the stream key and generated OBS
password are in `secrets.json` with private permissions. Managed OBS files live
under `~/.var/app/com.obsproject.Studio/config/obsgod/obs-studio/`. Ordinary OBS
profiles are separate. Never edit secrets into command arguments or support logs.

Gamescope feeds the separately installed obs-gstreamer plugin. Video, game audio
and microphone are independent checks. Upstream black-frame limitations include
[Gamescope #2508](https://github.com/ValveSoftware/gamescope/issues/2508) and
[#1898](https://github.com/ValveSoftware/gamescope/issues/1898). OBSGod must refuse
a new full-screen broadcast from blank capture; game-only mode uses its explicit
between-game screen instead of substituting the compositor.

## Capture modes and between-game screen

**Entire screen** preserves the existing Gamescope feed, including Steam UI and
other visible content. **Game only** requests a nonzero game app ID through
Gamescope's app-filtered PipeWire format. It does not silently fall back to the
whole screen. Select the mode in Desktop Setup or use the mode button in Decky
while streaming and recording are confirmed stopped. A mode change applies to
the next explicit Start or local test; it does not start a broadcast.

Game-only mode shows **black** or a **custom placeholder message** when no game
is identified, more than one game is ambiguous, the compositor lacks the required
format, or captured game frames cannot be verified. The default message is
“Game starting soon”; edit it in Desktop Setup. No external artwork is bundled.
Arbitrary image/video backgrounds and password controls remain separate work.
An already started stream stays live while game capture and fallback alternate.
The green indicator follows OBS output progress even during an intentional
between-game screen. Opening Steam menus should not change the app-filtered
source to a compositor feed; overlays drawn inside a game cannot be separated.

This source requires Gamescope to advertise and honor its custom app-ID format;
older or incompatible versions show fallback. Stock PipeWire/GStreamer capture
cannot provide the same filter. Steam-tagged processes identify the game; if
multiple games overlap, an available graphics-focus query can select one,
otherwise the fallback remains. Actual Deck/SteamOS builds, native Wayland
applications and transition performance still require device qualification.

## Audio checks

The upgrade resolves a unique active Steam game's output monitor when possible,
otherwise the current system default output monitor. It verifies that the same
device exists inside OBS, attaches the managed source to output/fallback scenes,
and reapplies volume, unmute, audio track 1 and monitoring-off settings. Other
applications playing through that output may also be heard: game-only video is
not per-application audio isolation. Microphone remains off unless explicitly
selected, and an output-monitor loopback cannot be selected as microphone.

The panel reports routed audio and short **signal / silent / unknown** meter
observations separately from the streaming dot. Silence during a quiet moment
does not stop streaming. Play game sound during the local clip, then listen to
the saved clip and a Kick viewer on another device. A meter or AAC track alone
is not proof of audible viewer output. If changing headphones/output routes,
stop and start again so discovery selects the new output; live hot-plug routing
is not yet qualified. System mute/zero volume is reported, never silently changed.

If OBS cannot see the selected monitor, the action explains that the
Steam/Flatpak audio connection needs attention. The earlier PulseAudio symlink
warning remains evidence to investigate on the actual Deck; no sockets or Pulse
configuration are deleted or replaced by the installer.

## Updates and recovery

**Check for updates** is at the bottom of the panel. It shows the installed and
latest compatible runtime versions, no-update, offline or failure results. A
check never replaces files or interrupts output. Updater-only releases are not
mistaken for new streaming runtimes. Historical immutable same-repository
artifacts and normal GitHub release assets are validated through their manifests
and checksums; downloads are never accepted from arbitrary repositories.

To apply an update, stop streaming and recording, enter **Desktop Mode**, and
open **Update OBSGod** from Applications → Multimedia, or the bundled
**Update OBSGod.desktop** (also available as `Update OBSGod.sh`). The updater checks output safety, downloads/verifies a
compatible candidate and runs the same unified installer. It preserves key,
settings, media and unrelated plugins. Repeated installation and same-version
repair are supported; a partial failure must show what changed and how to retry
or recover. Do not assume Decky's own Reinstall button fetches a newer OBSGod
runtime.

Keep Steam's normal Desktop frontend available for Decky's supported installer
bridge. The earlier generic instruction to close Big Picture was not a proven
cause of the owner's failure. The new transport preserves the frontend's
WebSocket instead of taking its single connection. Cloud protocol fixtures do
not prove the actual Steam frontend works; that remains a device check.

To uninstall, remove OBSGod through Decky and run
`python3 ~/.local/share/obsgod/current/uninstall.py`.
Add `--purge-settings` only to delete OBSGod credentials and isolated OBS settings.
Recordings and executable backups remain. OBS/capture Flatpaks remain separately
installed and can be removed through Discover if no longer wanted.

## Required device acceptance

Record the candidate source SHA, archive/plugin hashes, SteamOS/device model,
OBS/GStreamer/Decky/Steam versions, encoder settings and exact outcomes:

- Fresh install, reinstall, old-preview upgrade, interrupted update and recovery;
  verify app/plugin versions, preserved key/settings/media and other plugins.
- Cold/warm startup, authentication, early exit, bounded failure, cancellation,
  OBS restart and output-state recovery.
- Local clip with moving 720p video, game sound and the selected microphone
  policy; no credentials in ordinary output or process arguments.
- Game-open and game-closed capture, launch/exit, QAM reopen, controller focus,
  reboot and the supported session topology. Record unsupported cases explicitly.
- Start, repeated clicks, Stop and Cancel; red only after confirmed stop, amber
  for unknown/reconnecting/stalled output, no duplicate success notifications.
- Actual Kick viewer picture/sound on a second device, plus game FPS/encoder load.
- Update checks while streaming do not mutate files; applying while active,
  recording or unconfirmed is blocked. Verify no-update, offline, bad checksum,
  interrupted apply, same-version repair and recovery.

Do not run failure tests during an unintended public broadcast. Passed cloud
checks cannot close #10, #21 or #22 without the required actual-device evidence
and owner review. See [qualification](steam-deck-qualification.md) for the exact
candidate matrix and remaining gates.
