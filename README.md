# OBSGod preview6 review candidate

Exact qualified source: `33dcd8476606a1ed7a3bbca06e81fb156dfebcc7`.
Draft PR: https://github.com/szmyty/obsgod/pull/34 (stacked on33/32).
This immutable artifact checkpoint is not a release/tag, deployment or merged source. Never merge this artifact branch into source.

## Changes

- Resolve the active game/default system-output monitor; verify OBS sees it and repair source membership, gain, mute, track1 and monitoring. Expose short audio-meter observations without treating silence as stopped streaming.
- Choose entire-screen or app-filtered game video, with black/custom-message fallback between games. Game detection only changes the selected scene of an existing output; it never starts/stops a broadcast.
- Verify the actual private Gamescope format before linking, pin its producer serial, reject unsupported/ambiguous producers and malformed buffers, and keep full-screen capture out of the strict game scene.
- Preserve legacy settings/key binding, recordings, ordinary OBS configuration, unrelated plugins and rollback copies. Full app/plugin/updater versions match.

## Qualification

All available local checks passed at the exact source above:94Go pass events(64top-level,1optional existing-OBS test skipped),70Python,9Node,vet,vulnerability/typecheck/build/audit,6cross-compilations(nonexecuted), two byte-identical runtime/updater builds, actual-package fresh/5.2upgrade/panel browsers, pinnedDecky3.3.1/default unified install/Desktop updater fixtures. Real OBS30.2.3 authenticated recording/RTMP/audio routing/media/lifecycle passed;13native capture-protocol cases passed. Real OBS game/placeholder/game/unsupported/black output transitions and decoded video+440Hzaudio passed, without implicit restarts or source leaks in the synthetic fixture. Exact commands/platforms/hashes/outcomes are in `audio-game-qualification.json` and adjacent matrices/logs.

Native tests use synthetic Gamescope/game facts and a substituted Flatpak invocation. Actual Deck/SteamOS/Flatpak library loading, Gamescope privacy/game transitions/hardware encoding/controller/performance, physical microphone and Kick sound remain unrun device gates. Fresh GitHub Actions jobs did not start because the account is locked due to a billing issue. Historical fixture failures/fixes are recorded in the qualification JSON; no old receipts qualify this newer source.

## Try on the Deck

Stop streaming and recording. Keep normal Steam open in Desktop Mode. Download the runtime tar.gz, verify its SHA256SUMS, extract all files and run `python3 OBSGod-0.1.0-deck.6/install.py` without sudo. Upgrade in place; do not purge keys/settings. In Setup choose Capture video -> Game only and black/custom-message fallback, leaving a saved key blank to keep it. Then return to Gaming Mode, open an audible game and make a10-second clip; watch it in Videos/OBSGod. Only after checking local picture/sound, test Kick on an unmuted second device, open Steam menus and switch games while observing fallback and continuous output. Game-only filters video; other apps sharing the selected output can still be heard. In-game injected overlays cannot be separated; static games may trigger stale fallback. Unsupported capture stays on fallback.

The published-version updater will not fetch this unpublished checkpoint. Use the full runtime installer. No new release/publication or merge approval is being assumed. Owner device evidence, required reviews/CI and any subsequent release approval remain open; no issue is closed from these tests.
