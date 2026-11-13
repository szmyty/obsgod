# Install the completion review candidate

Candidate **0.1.0-deck.9** comes from exact clean source
`1a482808a8281c8bce092cea057df758836b34e9` (tree `fba5cfaed616313e2a6b679a55ff234d21a21538`). The available local matrix passed at that revision;
actual Steam Deck/OBS33/Flatpak/Gamescope/controller, external viewers/adoption,
required hosted CI and owner review remain open. This is an immutable review
download, **not a published GitHub release**. See the
[owner packet](completion-review.md) and [dated audit](../audits/audit-2026-11-13.md).

In Steam Deck **Desktop Mode**, keep normal Steam open and Decky Loader installed.
Stop streaming, recording and replay, then close idle managed OBS using **Restart
OBS** before upgrading. The installer upgrades in place and preserves settings,
keys and media. Keep the existing installation; deleting its data is unnecessary.

Open Konsole and paste the whole block. It verifies the archive before extraction
and leaves Konsole open on failure; installer prompts still accept input:

```bash
bash -c '
set -euo pipefail
decky_stream_stage=$(mktemp -d -t decky-stream.XXXXXXXX)
printf "Downloading candidate 9 to %s\n" "$decky_stream_stage"
curl --fail --location --show-error --proto "=https" --proto-redir "=https" \
  "https://raw.githubusercontent.com/szmyty/obsgod/d0a4973f9b1835471e99b046d2d4313b042f9ae2/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz" \
  --output "$decky_stream_stage/candidate.tar.gz"
printf "%s  %s\n" "879ad44ebb28fb695877c071d9708959a7afc39b7b2b9032421f117a267bf803" "$decky_stream_stage/candidate.tar.gz" | sha256sum --check -
tar -xzf "$decky_stream_stage/candidate.tar.gz" -C "$decky_stream_stage"
python3 "$decky_stream_stage/OBSGod-0.1.0-deck.9/install.py"
'
```

Follow the local setup page, then return to Gaming Mode. Under **Audio controls**,
enable the microphone, choose an available input, check its meter, and explicitly
unmute. Mic and system/game gains affect OBS outputs, not system volume. A lost
input stays muted/unconfirmed. The LCD built-in mic can become unavailable with
something in the 3.5 mm jack; actual device availability drives the controls.
On OLED, built-in mic with wired headphones still needs a local test.

Save a local clip and listen with headphones before streaming. Confirm picture,
game/system sound and your voice; then start an intentional stream and verify it
from a separate viewer. Optional hold-to-talk is a **focused panel action**, not a
global controller shortcut; use ordinary mute until physical controls are checked.
An unavailable OBS connection means actual mute is unknown. See
[microphone behavior](microphone.md) and the [device checklist](m3-device-acceptance.md).

A game is unnecessary for OBS control or the configured game-only idle scene.
Entire-screen mode includes menus. Game-only video does not imply per-app audio
isolation. Existing local profiles, idle media, recording/replay, clips and bounded
recovery remain available. Saved live mixer preferences take precedence over the
profile's initial microphone default.

If installation stops, keep its visible error and temporary-directory path. Do
not use sudo or wipe settings. Tested legacy4/6 upgrade paths use the full package;
the fixed historical updater4.1 cannot discover this candidate. Normal release
discovery will not offer an unpublished review download. Compatibility names
`obsgod`/`OBSGod` remain; final repository/plugin/storage migration is separate.

Immutable artifact checkpoint: `d0a4973f9b1835471e99b046d2d4313b042f9ae2`. Runtime SHA256:
`879ad44ebb28fb695877c071d9708959a7afc39b7b2b9032421f117a267bf803`. Downloaded public bytes were checked against the selected
runtime/plugin/updater and their internal inventories. Checksums and the included
unsigned audit establish consistency, not a publisher signature. No release or
site deployment was performed.
