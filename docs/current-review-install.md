# Install the qualified source review

This manual review build is package **0.1.0-deck.9** from exact source
`4699235e9e925b76ca492d5a00a375ed37fb338e`. Its immutable
[19-file checkpoint](https://github.com/szmyty/obsgod/tree/eb92598f3a4a0dc426749c290bacfe7251452909)
contains the runtime/plugin/updater, full 401-file source, notices, unsigned audit
and qualification evidence. All downloaded files and internal inventories were
verified. [Results and remaining gates](../audits/qualification-4699235.md).

The older [1a/d0a candidate](candidate-9-install.md) remains unchanged. These
builds share a package version but have different source revisions and checksums.
This checkpoint is not a GitHub release or an offer from “Check for updates.”
Actual Steam Deck/OBS33/Flatpak/Gamescope/headset/controller and separate viewer
acceptance remains to be collected.

## Desktop installation

Stop streaming, recording and replay first. Keep Steam and Decky running in
Desktop Mode. Preserve your existing installation/settings/media; the full
installer checks dependencies and installs the paired Decky plugin. It refuses
active or unknown output state and retains the previous release for recovery.

Paste this entire block into an open Desktop terminal:

```bash
bash <<'DECKY_STREAM_REVIEW_INSTALL'
set -euo pipefail
decky_stream_review_dir=$(mktemp -d "${TMPDIR:-/tmp}/decky-stream-review.XXXXXX")
trap 'printf "\nReview files kept at: %s\n" "$decky_stream_review_dir"' EXIT
cd "$decky_stream_review_dir"
curl --fail --location --show-error --proto '=https' --proto-redir '=https' \
  'https://raw.githubusercontent.com/szmyty/obsgod/eb92598f3a4a0dc426749c290bacfe7251452909/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz' \
  --output runtime.tar.gz
printf '%s  %s\n' \
  'b4222fb703aa198a7ea200721afbc06dcb86dec56e8c1bebd77f5bb614aad53d' \
  runtime.tar.gz | sha256sum --check -
tar -xzf runtime.tar.gz
python3 - <<'VERIFY_REVIEW_SOURCE'
import json
from pathlib import Path
manifest = json.loads(Path('OBSGod-0.1.0-deck.9/manifest.json').read_text())
assert manifest['revision'] == '4699235e9e925b76ca492d5a00a375ed37fb338e'
assert manifest['dirty'] is False
print('Verified review source:', manifest['revision'])
VERIFY_REVIEW_SOURCE
python3 "$decky_stream_review_dir/OBSGod-0.1.0-deck.9/install.py" --no-launch
printf '\nOpen Decky Stream Setup from Applications to continue.\n'
DECKY_STREAM_REVIEW_INSTALL
```

Use the full installer without sudo. `install.py` has no `--repair` flag; a
different verified manifest/payload preserves the old release and selects a new
suffixed directory even at the same package version. The download folder remains
available if installation fails. Do not wipe data to work around a refusal.
No installation starts a broadcast.

## First acceptance checkpoint

Record Deck model and SteamOS/channel, Steam, Decky, OBS Flatpak and GStreamer
versions. Configure the destination/key locally. Make and play a moving local
test clip with an audible source; then check the actual microphone/input/mute/
gain/hold-to-talk behavior, game-only/menu privacy and idle/game changes. A
separate provider viewer must confirm intended picture and system/mic audio.
Continue with [the device checklist](m3-device-acceptance.md) and preservation/
update/recovery/uninstall checks. Share filtered diagnostics, never stream keys,
OBS passwords or private setup tokens.

Successful cloud downloads/fixtures are not actual Deck installation or consumer
adoption proof. Product release, deployment and Store contact/submission remain
separate explicit owner actions.
