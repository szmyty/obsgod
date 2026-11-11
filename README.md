# OBSGod one-click updater

Download/extract the entire ZIP in Steam Deck Desktop Mode. Open Update OBSGod.desktop and choose Execute if Dolphin asks. Keep Steam Big Picture closed until it finishes. The script updates the app and Decky plugin to preview 0.1.0-deck.4, checks missing user Flatpaks and preserves the key, preferences, recordings and other plugins. No manual removal, sudo, commands or key re-entry are needed for an existing setup. The updater uses Decky Loader already installed on the device; it does not install the loader itself.

Source: 0eb8324c2b1f23fea069570eded1cd0c75d99274. See updater-qualification.json for exact commands, pinned upstream sources, results and hardware limits. Actual Steam Deck installation remains unverified, and the original OBS startup timeout still needs device diagnostics. No streaming fix is claimed.

This orphan branch contains release artifacts. Do not merge it into source. Review: https://github.com/szmyty/obsgod/pull/15
