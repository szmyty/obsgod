# Install the reviewed Milestone 3 candidate

Candidate **0.1.0-deck.8** was built from exact clean source
`bf72ca4ae028f78895eadee6d3874734a1cccd05`. All available local checks passed. Actual Steam Deck/OBS33,
Flatpak/Gamescope/controller/provider/adoption and billing-blocked CI acceptance
remain open. [Evidence and owner packet](m3-review.md).

In Steam Deck **Desktop Mode**, keep normal Steam open and Decky Loader installed.
Stop streaming, recording and replay, then close idle managed OBS using **Restart
OBS** before upgrading from an older version. Keep your existing installation;
this command verifies the immutable archive and runs the complete installer in
place, preserving settings, keys and media. It does not wipe your configuration.

Open Konsole and paste this block. The child shell leaves Konsole open if an
error occurs and preserves interactive installer input:

```bash
bash -c '
set -euo pipefail
decky_stream_stage=$(mktemp -d -t decky-stream.XXXXXXXX)
printf "Downloading candidate 8 to %s\n" "$decky_stream_stage"
curl --fail --location --show-error --proto "=https" --proto-redir "=https" \
  "https://raw.githubusercontent.com/szmyty/obsgod/9ad051ecbb41df92c723a54bdfb6aaaeb1097898/obsgod-deck_0.1.0-deck.8_linux_amd64.tar.gz" \
  --output "$decky_stream_stage/candidate.tar.gz"
printf "%s  %s\n" "d33c976905e6cde8f7ab9491eef62a08a394c80b0c35d65a61bafa34a27dd9f2" "$decky_stream_stage/candidate.tar.gz" | sha256sum --check -
tar -xzf "$decky_stream_stage/candidate.tar.gz" -C "$decky_stream_stage"
python3 "$decky_stream_stage/OBSGod-0.1.0-deck.8/install.py"
'
```

Follow the local setup page. Desktop Setup has exact quality/profile controls,
local idle image/video import, recording storage/replay limits and clip export.
Return to Gaming Mode and make a local clip before broadcasting. Watch and listen
to it; then verify an explicit stream on a separate viewer. The panel adds
profiles, between-game media selection, recording/replay, bounded recovery and
measured health. [Device checklist](m3-device-acceptance.md).

A game is unnecessary for OBS control or the configured game-only idle scene.
Entire-screen capture still requires usable frames and includes menus. Game-only
video does not imply per-application audio isolation. Use assets you may stream;
imported video sound stays muted. Presets are starting points, not measured Deck
hardware promises. Stop streaming preserves independent recording/replay.

If the installer stops, keep the visible error and printed temporary-directory
path. Do not use sudo or delete your old settings. The fixed historical updater4.1
cannot discover this candidate; use the full installer above. Review downloads
are not GitHub releases, so normal release discovery will not offer candidate8.
No release or site deployment is implied. Original OBSGod/obsgod compatibility
IDs and existing media remain preserved.
