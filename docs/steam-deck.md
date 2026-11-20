# deckystream Steam Deck guide

OBSGod runs an isolated OBS Studio Flatpak and exposes streaming controls in
Decky's Quick Access panel. Stock OBS still needs a graphical session; this is
managed background OBS, not a headless OBS server. SteamOS/Linux x86_64 is the
supported target. Normal use does not disable SteamOS read-only protection.

**This is the current-source guide.** Use the exact candidate and checksums in
your review packet, not an older published preview as evidence of newer fixes.
Cloud tests do not establish actual Steam Deck, Flatpak, Gamescope, AMD encoder,
controller, audio or Kick compatibility. Required device checks remain open.

## Current standard-plugin setup

The current source produces one `obsgod-decky.zip`, installed through Decky's
normal plugin controls. Do not substitute a GitHub source-code ZIP. A separate
Desktop application/updater is optional and its version need not match the plugin.
The [current review checkpoint](pre-migration-qualified-checkpoint.md) and
[numbered tests](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-TESTS.md)
identify exact source and checksums; remaining qualification is tracked in
[#85](https://github.com/szmyty/obsgod/issues/85). The retained
[4699235 review installer](current-review-install.md) is explicitly historical.

1. Install Decky Loader from its official project if needed. Stop streaming,
   recording and replay before replacing a plugin; unknown output requires
   recovery/inspection first. Use the exact ZIP/checksum supplied by the review.
2. Open **••• → Decky → deckystream** in Gaming Mode. Existing installation
   identity may still be **OBSGod**. First-run setup lists missing user-scoped
   OBS/GStreamer dependencies; choose **Install** or **Later**. Declining leaves
   setup required. Downloads do not run merely because Decky loads the plugin.
3. In **Stream destination**, enter the provider's server and separate stream key.
   Saved settings collapse behind **Edit saved destination**. STEAM + X opens
   the keyboard; a saved key is never read back. Saving does not start output.
4. Make a **10-second test clip**, then verify picture and sound. The streaming
   indicator remains stopped during a local recording. Explicitly Start only
   after choosing capture/audio, and verify the channel from another device.

Desktop Setup is an optional authenticated loopback tool for advanced profiles,
idle media and storage choices. The panel provides **Optional Desktop Setup
instructions** for the bundled `setup.py`; Decky's ZIP install does not create
a separate Applications launcher. Never share the private local page URL.

## Retained Desktop archive installation

The steps below apply to older reviewed Desktop/runtime archives or an explicitly
chosen optional Desktop installation. They are not prerequisites for the standard
plugin flow above. Preserve the exact source/checksums of the archive being used.

1. In **Desktop Mode**, download the reviewed candidate archive ending in
   `_linux_amd64.tar.gz` and extract the entire archive. Leave an existing OBSGod
   installation in place; settings and the stream key should be preserved.
   Stop streaming, local recording and replay first. If an older version cannot
   confirm replay/output state, follow its named inspection/recovery path before
   replacement. Restarting is not a close-to-edit operation or proof of idle.
   The installer refuses active or unconfirmed output.
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
4. In **Decky Stream Setup**, choose Kick, Twitch, YouTube or custom RTMP(S),
   then enter the server URL and secret key from that destination’s dashboard. For the initial test use 4500 kbps, 30 fps and AMD H.264; switch to
   software H.264 if hardware encoding fails. Microphone is off unless selected.
   Save and choose **Finish and close setup**. Existing settings do not require
   key re-entry. Never share the private setup link or the key.
5. Return to **Gaming Mode**, then open **••• → Decky → Decky Stream** (the installed compatibility ID remains OBSGod). Make a
   **10-second test clip** first. This never broadcasts, so a red streaming dot
   during the clip is normal. The clip is saved in **Videos/OBSGod**; check its
   video and sound in Desktop Mode before broadcasting.
6. Choose **Start streaming**, then watch your destination channel on another device.
   Confirm both picture and sound. Use **Cancel operation** while starting or
   **Stop streaming** when output is active. Unknown output retains a recovery
   Stop action; inspect OBS and the channel if stopping cannot be confirmed.

A game is not required for OBS lifecycle or its control connection. Actual
full-screen capture must still deliver usable nonblank frames before a test or
broadcast starts. Game-only mode permits the explicitly selected between-game
screen when no verified game capture is available. Some Gamescope versions cannot capture the Steam UI with no game; a
blank/unavailable feed is an explicit platform blocker, not proof that OBS
failed to launch. The M3 candidate also supports imported local idle images/video;
see [idle media](idle-media.md) for rights acknowledgement and muted soundtrack.

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
Green describes OBS output health, not what a viewer receives.

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
Desktop Setup now offers credential-free local connection information, an explicit
read-only connection test, and password change/reset while managed OBS is fully
closed. See [destinations and control recovery](stream-destinations.md).

Configure basic destination/password settings in the native panel, or use optional
Desktop Setup for its advanced controls. Start inside Gaming Mode. Session switching may
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
Desktop Setup can import a local PNG/JPEG image or MP4/WebM video after you
confirm permission to use it. The managed copy is private, video sound stays
muted, and a missing/invalid asset falls back to black. See [idle media](idle-media.md).

The M3 candidate adds [quality profiles](advanced-profiles.md),
[recording/replay and clips](recording-replay.md),
[bounded recovery](runtime-resilience.md) and [measured health](stream-health.md).
Profile settings apply only to an explicit new output; game detection and
recovery never start broadcasting. Real Deck/controller qualification remains
separate from the prepared controls and Linux/browser evidence.
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
the saved clip and a separate viewer on another device. A meter or AAC track alone
is not proof of audible viewer output. If changing headphones/output routes,
stop and start again so discovery selects the new output; live hot-plug routing
is not yet qualified. System mute/zero volume is reported, never silently changed.

If OBS cannot see the selected monitor, the action explains that the
Steam/Flatpak audio connection needs attention. The earlier PulseAudio symlink
warning remains evidence to investigate on the actual Deck; no sockets or Pulse
configuration are deleted or replaced by the installer.

## Updates and recovery

**Check for updates** near the bottom of the panel observes the loaded plugin's
version and distribution channel. It reports a compatible newer release,
no update, offline or an actionable failure; checking never replaces files or
interrupts output. A manual review-artifact branch is not an updater offer.
Version alone may match across previews, so also retain the exact source/hash
from your review packet.

For a standard ZIP installation, use **Decky's own plugin update/replacement
controls** with the exact verified candidate. Stop streaming, recording and
replay and confirm fresh idle first; recover unknown state before replacement.
Decky's loader owns replacement. Plugin shutdown hooks are best effort and
cannot veto a loader operation or promise that output stopped. After reopening,
check the loaded version/source, fresh status and retained settings/media.
A Reinstall button may reuse its offered package; it does not prove that the
latest repository source was fetched. The real loader journey remains #86.

### Optional legacy Desktop app recovery

Only installations that actually have the separate Desktop app/updater use
**Update OBSGod** under Applications → Multimedia, `Update OBSGod.desktop` or
`Update OBSGod.sh`. A normal Decky ZIP creates none of these. Its optional app
version need not equal the loaded plugin, and its absence does not require
installing a second copy or repairing a pair.

The legacy updater checks output safety and verifies its selected archive before
using the unified installer. Review exactly which app/plugin version it will
replace; preserve settings, keys, media, ordinary OBS and other plugins. On a
partial failure, use its reported recovery rather than manually deleting folders.
Historical preview4.1 is a fixed preview4 bootstrap and cannot fetch newer bytes;
its immutable URL/hash stays unchanged. Maintained dynamic-updater compatibility
and actual-device upgrade success remain distinct evidence.

Legacy installer transport needs Steam's normal Desktop frontend available.
Closing Big Picture was not a proven explanation for the earlier failure.
Protocol fixtures preserve the frontend's WebSocket rather than taking its
single connection; actual Steam/Decky behavior still needs the owner test.

## Uninstall, reset and wipe

For a normal plugin-only installation, stop all outputs, confirm fresh idle,
and use **Decky's plugin removal controls**. Preserve the existing private
settings/media and review your backup/recovery plan first. The plugin's hooks
are best effort; do not infer successful teardown or data retention from a click.
Actual supported-loader removal/preservation is recorded in the owner test loop.

### Optional Desktop cleanup, reset and explicit wipe

Only if the legacy Desktop app is installed, open **Uninstall Decky Stream** in
Desktop Mode or use its reviewed `uninstall.py`. The current cleanup helper can
also inventory those legacy pieces without installing the Desktop app. A normal
Decky ZIP does not create the Applications launcher or the path below.
For an existing default-location Desktop installation:

```sh
python3 ~/.local/share/obsgod/current/uninstall.py --dry-run --json
python3 ~/.local/share/obsgod/current/uninstall.py
```

If you selected `XDG_DATA_HOME`, use the `current/uninstall.py` path shown by your
installer. The tool preserves an existing legacy installation location until a
deliberate migration; it refuses conflicting installations instead of guessing.

- Default uninstall removes the app/plugin and owned shortcuts, retaining
  settings, credentials, history and recordings.
- `--reset` resets owned settings, credentials, isolated OBS, state and cache
  while retaining the installed app/plugin.
- `--wipe` first creates a verified private recovery export, then removes owned
  app/data/rollback copies. The export survives wipe and may contain credentials;
  recordings remain a separate explicit choice.
- `--delete-recordings` additionally selects standard OBS date-named MKVs in
  `Videos/OBSGod`; use repeatable `--recording PATH` for an explicitly selected
  other MKV there. Review the exact dry-run inventory first.
- `--yes` is the noninteractive equivalent of confirming the displayed plan.

### Private recovery export before wipe

These guarantees belong to the **current reviewed cleanup helper**, not an old
installed Desktop launcher. A plugin-only update does not replace a separately
installed legacy `uninstall.py`. Before reset/wipe, use the helper/source/hash
provided by your current review packet; an older same-version script may lack
`--export` and these guards. Stage the verified helper archive without running
its installer. See the [current cleanup preparation](legacy-cleanup-kit.md).

`--wipe` now requires a successful private recovery TAR before it can remove the
plugin or selected data. Its fresh inventory names the export and explicitly
states that it can contain stream keys, OBS passwords and private history.
The default is `${XDG_DATA_HOME:-~/.local/share}/obsgod-wipe-exports/` with a
unique filename. The owned export directory is mode0700 and the archive0600;
this is filesystem privacy, not encryption. It is outside the removal roots.

To select a new archive in a dedicated private folder, use the same exact path
for preview and the later explicit operation:

```sh
python3 uninstall.py --wipe --export "$HOME/.local/share/obsgod-wipe-exports/migration-1.tar" --dry-run
python3 uninstall.py --wipe --export "$HOME/.local/share/obsgod-wipe-exports/migration-1.tar"
```

An existing archive is never overwritten. Unsafe paths/links/ownership, changed
inventory, failed copying/verification or durability failure stop before the
first removal. A later interruption can leave partial removal, with an honest
result and the completed export's path/hash when still available. Review and
retry rather than bypassing a safety refusal. Large selections may exceed the
bounded export budget; they are not deleted after a failed export.

Keep this TAR private; do not attach it to an issue, log console or support
bundle. For recovery, stage it only in a new private directory, inspect
`RECOVERY.json` and its file hashes, then recover selected owned data deliberately
while outputs are stopped. Never extract over HOME. Alias entries are metadata,
not instructions to recreate links. Reinstall a separately verified plugin ZIP;
verified export is not proof of an automatic restore or application rollback.
After successful recovery/testing, delete the exact retained archive deliberately
if no recovery copy should remain. Normal uninstall, reset and legacy retirement
do not automatically create this export or change their existing scopes.

Removal requires idle, known output and a supported Decky removal path; missing
or malformed status is not permission to delete. A partial failure stops with
an honest recovery result. Ordinary OBS, other plugins and shared OBS/GStreamer
Flatpaks remain separate. The legacy `--purge-settings` option remains supported.

For a nonstandard Decky installation, supply its verified root through
`DECKY_HOME` before planning removal. The tool lists the exact plugin/settings/
data/log paths it knows. An unknown loaded-plugin root blocks removal, and an
unknown wipe root remains an explicit pending gate; it is never guessed or
reported as a complete wipe.

## Funding and configuration

The optional Support section opens the five configured external funding pages
only after a click. It does not affect streaming or offline use. Cryptocurrency
receive controls remain hidden until public receiving addresses and explicit
networks are configured. See [support configuration](support.md).

The versioned [CLI configuration reference](configuration.md) documents flags,
`OBSGOD_*`/legacy `OBS_*` variables, private secret references, XDG connection
profiles and offline shell help. Managed Deck settings stay separate from a
remote-OBS connection profile. The adapter uses Decky's supplied plugin/user
paths when present; Desktop and CLI share the same managed settings.

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
- Actual viewer picture/sound on a second device for each claimed destination,
  plus game FPS/encoder load. Provider presets alone are not viewer qualification.
- Update checks while streaming do not mutate files; applying while active,
  recording or unconfirmed is blocked. Verify no-update, offline, bad checksum,
  interrupted apply, same-version repair and recovery.

Do not run failure tests during an unintended public broadcast. Passed cloud
checks cannot close #10, #21 or #22 without the required actual-device evidence
and owner review. See [qualification](steam-deck-qualification.md) for the exact
candidate matrix and remaining gates.
