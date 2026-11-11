# OBSGod Steam Deck preview

This preview adds Desktop setup and a Decky Quick Access toggle to OBSGod. It
uses OBS Studio's Flatpak, an isolated OBSGod profile, and the upstream GStreamer
plugin to capture Gamescope. It requires SteamOS/Linux x86_64 and Decky Loader.
It does not require per-game launch options or disabling SteamOS read-only mode.

**Status:** cloud Linux tests do not establish Steam Deck hardware compatibility.
The preview is for the first real Deck test. Gamescope capture, AMD VAAPI,
controller navigation, audio routing and Kick viewer output need verification on
your device. See the qualification evidence attached to the
[preview release](https://github.com/szmyty/obsgod/releases).

## Install tomorrow morning

1. In **Desktop Mode**, open [OBSGod releases](https://github.com/szmyty/obsgod/releases)
   and download the Steam Deck preview archive ending in `_linux_amd64.tar.gz`.
   Extract it in Downloads.
2. Open **Install OBSGod.desktop** in the extracted folder. Choose **Execute** if
   KDE asks. If your file manager opens it as text, open Konsole in that folder
   and run `python3 install.py`. Do not use sudo.
   Keep the terminal open until you choose **Finish and close setup** in the
   browser. The launcher waits for Enter afterward so any error stays visible.
   If the browser does not open automatically, use the local setup link printed
   in the terminal. Do not share that link.
3. The local **OBSGod Setup** page opens in your browser. Click **Install / check
   OBS + capture plugin**. The initial Flathub download can take several minutes
   and a few GB. The installer uses user Flatpaks, including when a system OBS
   already exists.
4. Paste your Kick dashboard's **server URL** and **secret stream key** into the
   separate fields. Keep **4500 kbps, 30 fps, AMD hardware H.264** for the first
   attempt. Microphone is **off by default**. Save settings and finish setup.
5. If Decky is not installed, follow [Decky's official installation](https://decky.xyz/).
   Switch to **Gaming Mode**. Press **••• → Decky → Settings → General**, enable
   **Developer mode**, then open **Developer → Install Plugin from ZIP**. Select
   `obsgod-decky.zip` from the extracted download folder. The installed copy also
   lives at `/home/deck/.local/share/obsgod/current/obsgod-decky.zip` for the default
   `deck` user.
6. **Open a game**. Press **••• → Decky → OBSGod → Make 10-second test clip**.
   This does not broadcast. Return to Desktop Mode and watch the saved MKV in
   **Videos/OBSGod** to check the game picture, game audio and optional microphone.
7. Return to Gaming Mode, open your game and choose **Start streaming**. Watch
   your Kick channel on another device to verify the live picture and sound.
   Use **Stop streaming / cancel** when finished.

Decky lives in the **••• Quick Access panel**, which is on the right side on a
standard Steam Deck. The STEAM button's left-side menu is a different menu.
This preview does not install itself into Decky's public plugin store.

If an older preview's launcher flashes closed, open a terminal in the extracted
folder and run `python3 install.py --no-launch`. If that succeeds, open
**OBSGod Setup** from Applications, or run
`python3 ~/.local/share/obsgod/current/setup.py`. Once the browser page opens,
continue setup there; reinstalling is unnecessary.

## Status indicator

| Indicator | Meaning |
| --- | --- |
| Green — OBS streaming | OBS reports active output, no reconnect, and recent byte progress. |
| Red — Stopped | OBS reports inactive output, or its managed process/port is offline. |
| Amber — Connecting / stalled | Output is reconnecting or byte progress stopped. |
| Amber — Check OBS | The output state could not be confirmed. It may still be live. |
| Amber — Setup required | Save URL/key in Desktop setup first. |

The icon and panel reflect the same state. Green is **OBS output health**, not a
Kick API confirmation. An ingest connection cannot prove that viewers see the
right game or hear your microphone. A nonblank screenshot is required before a
new broadcast; a game loading screen may need a few seconds before retrying.

## Runtime and settings

Configure in Desktop Mode, but **start inside Gaming Mode**. Switching sessions
may terminate OBS. This preview makes no promise that a Desktop stream survives
the mode transition. It starts a fresh managed OBS as needed and uses the current
Steam session's display, D-Bus and audio environment.

Settings live in `~/.config/obsgod/deck.json` (or `$XDG_CONFIG_HOME/obsgod`). Keys
and a random OBS WebSocket password live in `secrets.json` with mode 0600 inside
a mode 0700 directory. OBS maintains its own service settings inside:

`~/.var/app/com.obsproject.Studio/config/obsgod/obs-studio/`

This is separate from your ordinary OBS configuration. These local files are not
encrypted against your own account or a privileged local user. Never attach them
to an issue. The setup HTTP server binds only to `127.0.0.1`, requires a random
per-run token for API access and rejects other website origins. Finish setup to
close that server. It does not become a background service.

The OBS connection uses localhost port **4457**, a random password, and OBS's
normal authenticated WebSocket listener. OBS itself may listen on other network
interfaces; no router port forwarding is needed. Do not expose that port publicly.

Stop capture before changing settings. In Desktop setup, use **Close idle OBS /
apply settings**, save changes, then start again in Gaming Mode. That button
refuses to close an active recording or stream. Stopping a broadcast leaves the
managed OBS available and switches to an empty idle scene to release capture.
Plugin unload requests a stream stop; a crash or lost connection still requires
checking OBS/Kick. Sleep, network loss and session changes are not continuity
guarantees.

Output is H.264/AAC, 1280×720, 30 fps by default, 2-second keyframes, 4500 kbps.
The game fits inside the canvas without stretching. The hardware preset uses
AMD VAAPI on `/dev/dri/renderD128`; software x264 is an explicit fallback and may
reduce game performance. Capture follows the default game-audio output and, when
enabled, the default microphone. Changing devices during a stream is unqualified.
OBS's initial global microphone inputs are muted automatically.

## Troubleshooting

- **Find the full error:** open OBSGod in Decky and read **Diagnostic console**
  directly below **Refresh status**. It updates while an operation is running,
  retains the last 100 events across reloads/updates and shows the newest first.
  Use **Older events** / **Latest events** to read history and **Clear console**
  to erase it without stopping a stream. **Copy console log** copies all retained
  events across every page, with timestamps and the plugin version, for pasting
  into a support message. It reports success or clipboard failure without
  changing streaming state. Logs use fixed diagnostic messages and
  numeric OBS/launch codes; keys, server URLs and raw OBS output are excluded.
  Events live at `~/.local/state/obsgod/diagnostics/events.json` (or beneath
  `$XDG_STATE_HOME/obsgod`) with private file permissions.
  A local ten-second recording does not broadcast, so its streaming dot stays red.
  A game must be open in Gaming Mode before testing; a timeout by itself does
  not tell us what failed. Report the stage/error from the console.
- **OBS will not start / missing input:** rerun setup's dependency installation.
  Both OBS and `com.obsproject.Studio.Plugin.Gstreamer` must be user Flatpaks.
  Run diagnostics. If another process uses 4457, resolve that conflict first.
- **No visible frames:** start a game first; try SDR and an updated SteamOS stable
  build. Some Gamescope versions have upstream black-frame issues, including
  [#2508](https://github.com/ValveSoftware/gamescope/issues/2508) and
  [#1898](https://github.com/ValveSoftware/gamescope/issues/1898). OBSGod will refuse
  a new broadcast if it cannot see nonblank capture. It cannot repair Gamescope.
- **Encoder failure:** stop, return to Desktop setup, close idle managed OBS,
  select software H.264, save and retry a local test. This uses more CPU.
- **No sound:** check the Deck's default output/microphone, enable microphone in
  setup if wanted, and make another local clip. Do not infer audio from green.
- **Start failed or status unknown:** press Stop. If stop cannot be confirmed,
  inspect OBS and your Kick dashboard immediately. A missing connection is not
  proof that streaming stopped.
- **OBS appears as another running app:** this is an ordinary GUI OBS process
  launched within Gaming Mode. SteamOS can list it. Do not force-quit it during a
  stream; use the panel's Stop first.

## Update / uninstall

For an update without terminal commands or manually replacing the plugin,
download the [one-click updater](https://github.com/szmyty/obsgod/releases/tag/v0.1.0-deck.4-updater.1).
In **Desktop Mode**, extract the entire updater ZIP and open **Update
OBSGod.desktop**. Keep Steam's Big Picture window closed until it finishes.
Choose **Execute** if Dolphin asks. The updater checks/downloads the pinned,
qualified preview **0.1.0-deck.4**, closes idle managed OBS after confirming its
output is stopped, checks user Flatpak dependencies, backs up saved preferences
and credentials privately, installs the Desktop app and replaces/enables OBSGod
using Decky's authenticated local installer. It verifies the resulting plugin
version and preserves other plugins' relative order. No sudo, password entry,
manual plugin removal or stream-key re-entry is needed for an existing setup.

This updates **OBSGod**, using the Decky Loader you already installed. It does not
install Decky Loader itself. If output cannot be confirmed stopped, it pauses
with instructions instead of killing OBS. If the plugin update fails after the
Desktop app installs, it reports that partial state and can be rerun. A completion
or error dialog keeps the result visible; if no dialog tool is available, close
the terminal window when it finishes. Fresh setups open the local settings page
for their own URL/key. This updater does not establish a fix for the reported OBS
readiness timeout; use **Copy console log** if a subsequent game test still fails.

For manual updates:

Download/extract the next preview, stop streaming, close idle managed OBS, run its
installer, then use Decky's **Install Plugin from ZIP** to replace OBSGod with
the new `obsgod-decky.zip`. There is no need to uninstall first or enter the key
again. The Desktop installation and Decky ZIP are separate updates: check the
plugin version shown in its console after replacing the ZIP. Decky itself is
still installed separately.

Repeat installation and same-version replacement are supported. The installer
verifies and stages the payload, preserves earlier release directories, and
switches the current release after preparing the application entries. A failed
activation rolls back those entries. A damaged installed copy is repaired using
a fresh directory; existing processes keep their original files. Settings, keys,
recordings, diagnostics and ordinary OBS scenes are preserved. Existing
`~/.local/bin/obsgod` executables are backed up under
`~/.local/share/obsgod/backups/`; the installer never overwrites their contents.

Uninstall the plugin through Decky, then run:

```sh
python3 ~/.local/share/obsgod/current/uninstall.py
```

Add `--purge-settings` to also remove OBSGod credentials and isolated OBS settings.
Recordings and executable backups are always preserved. OBS/GStreamer Flatpaks
remain installed and can be removed through Discover if no longer wanted.

## Acceptance on your Deck

Record SteamOS, Deck LCD/OLED, OBS, GStreamer plugin and Decky versions. Check:

- Install/update/uninstall without sudo or changing SteamOS read-only settings.
- Settings persist across Desktop → Gaming Mode and a reboot; stream stays off
  until explicitly started.
- Test clip contains moving game video at 720p, game audio, and only the selected
  microphone policy. No key appears in process arguments or ordinary output.
- Start reaches green and the Kick viewer sees/hears correct output.
- Game launch/exit, QAM close/reopen and controller focus remain usable.
- Repeated Start/Stop is safe. Red follows confirmed stop; unknown stays amber.
- Bad key, disconnected network, OBS exit and cancellation show truthful status
  and allow recovery. Do not perform failure tests during a public stream.
- Measure game FPS / encoder load and confirm any selected 60 fps preset.

Those results, not cloud builds, qualify #10's real Gaming Mode acceptance.
