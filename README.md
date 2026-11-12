# OBSGod 5.2: preserve the managed configuration inside Flatpak

Review candidate 0.1.0-deck.5.2, source e10383598a01b7bfab946735d4187a458a5177e5.
Draft PR #33: https://github.com/szmyty/obsgod/pull/33 (based on installer fix #32).

The owner confirmed that Flatpak replaced the requested configuration ending in config/obsgod with the ordinary config directory. The old launcher could therefore miss the enabled private WebSocket settings and wait for a listener that never appeared. The new launcher applies XDG_CONFIG_HOME inside the sandbox through /usr/bin/env before OBS starts. It uses no shell or credential arguments and never starts output automatically.

The new executable regression models Flatpak's environment reset for background and visible recovery. The real native OBS harness also models that reset and verifies authentication, moving 720p/audio recording, local RTMP, lifecycle/failure cleanup and unchanged ordinary OBS configuration. Fresh checks: 59 Go cases passed (one optional existing-OBS test skipped), 60 Python and 8 Node cases passed; static/security, actual package browsers, pinned Decky/unified-installer/updater fixtures and repeated identical package checksums passed. Three other platforms compiled only.

Download the complete obsgod-deck_0.1.0-deck.5.2_linux_amd64.tar.gz, extract it in Desktop Mode and run Install OBSGod.desktop or python3 install.py. Keep normal Steam running and stop streaming/recording first. Leave the old installation in place: the installer replaces the app/plugin, preserves keys/settings/media and retains rollback copies. It includes installer fix 5.1.

The owner has not tried the corrected launch yet. Actual SteamOS/Gamescope/VAAPI/audio/controller/session/Kick acceptance remains open. A pulse-symlink warning from the owner's read-only probe is retained for audio follow-up; no sockets were deleted and no audio recovery is claimed. GitHub CI remains unavailable because of the account billing lock.

Use the full installer for this unpublished candidate. The standalone updater follows published releases and cannot fetch an unpublished review artifact. This branch is not a release or deployment and must never be merged into source. Qualification, limits and filtered fixture evidence are included.
