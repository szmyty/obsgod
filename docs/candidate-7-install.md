# Install the reviewed Milestone 2 candidate

This is **0.1.0-deck.7**, an unpublished review candidate built from exact source
`0eac1ed9746e6a5999a196777bde5455222f46eb`. All available local checks passed;
actual Steam Deck/OBS33/provider and required CI/review acceptance remain open.
See [the owner packet](release-readiness.md) for hashes, evidence and limits.

In Steam Deck **Desktop Mode**, keep normal Steam open and Decky Loader installed.
Open Konsole and paste the following. It verifies the immutable archive before
extraction and runs the unified installer in place, preserving existing settings,
keys and recordings. It does not remove your previous configuration.

```bash
#!/usr/bin/env bash
set -euo pipefail
decky_stream_stage=$(mktemp -d -t decky-stream.XXXXXXXX)
printf 'Downloading the reviewed Decky Stream candidate to %s\n' "$decky_stream_stage"
curl --fail --location --show-error --proto '=https' --proto-redir '=https' \
  'https://raw.githubusercontent.com/szmyty/obsgod/e202f34070ef6174fbf86b75f9cc87ace74d6a14/obsgod-deck_0.1.0-deck.7_linux_amd64.tar.gz' \
  --output "$decky_stream_stage/candidate.tar.gz"
printf '%s  %s\n' '4205e4725fd432ea99a59fe8c1a78f0f7b29c7ddbd6c79e3cf4afd8c2c67c9c3' "$decky_stream_stage/candidate.tar.gz" | sha256sum --check -
tar -xzf "$decky_stream_stage/candidate.tar.gz" -C "$decky_stream_stage"
python3 "$decky_stream_stage/OBSGod-0.1.0-deck.7/install.py"
```

Follow the installer and local setup page. Return to Gaming Mode and make a
10-second local clip first; listen to it before an explicit stream. Then verify
picture and sound on a separate viewer. The display name is Decky Stream; legacy
filenames/plugin/CLI/storage IDs remain OBSGod/obsgod for compatibility.

If installation stops, retain the visible error and printed temporary-directory
path for repair. Do not run the installer with sudo. Existing fixed updater4.1
only downloads runtime4; use this current full installer to leave that version.

For removal, use Uninstall Decky Stream and review its inventory. Wipe/reset and
recording deletion are explicit choices. For custom Decky roots supply verified
DECKY_HOME; unknown roots fail closed. Crypto addresses intentionally remain null
and hidden until optional owner activation. No release or site deployment is
implied by this review download.
