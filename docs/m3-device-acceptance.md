# Candidate 8 Steam Deck acceptance

These are **unrun device checks**, not passing receipts. Use the exact reviewed
candidate/revision/checksum. Preserve settings/media with the in-place installer;
stop streaming, recording and replay and close managed OBS before an old-version
upgrade. Keep the normal Steam client open in Desktop Mode and Decky installed.

Record Steam Deck model, SteamOS channel/version, Decky version, OBS Flatpak
version, GStreamer addon version and candidate/source revision. Save a redacted
support bundle and representative clips. Do not publish keys, OBS passwords or
the private setup link. Source and native Linux/browser evidence do not substitute
for this device record.

| Case | Required observation |
| --- | --- |
| Upgrade/rollback/removal | Existing key/settings, ordinary OBS, unrelated Decky plugins and media survive; active/unknown stream/record/replay blocks update/removal. Verify the paired app/plugin version and a reviewed rollback. |
| Local clip and provider | Moving video plus audible system audio; opt-in microphone works without a monitor becoming the microphone. An explicit live stream has picture and sound on a separate provider viewer. |
| Profiles | Preview/apply/reset/import/export agree across Desktop/CLI/panel. Validate 540p30/720p30/720p60 starting presets under named games and selected encoder; record stream picture, audio, game FPS, CPU/GPU/power/battery and thermal tradeoffs. Do not call a preset hardware-qualified from a Linux software-encoder result. |
| Game-only/idle media | No game, game A, exit, game B, ambiguous/unsupported capture and Steam menu changes preserve game-only privacy. Own/permitted local image and looping muted video appear as selected; missing media uses black; system/mic policy and an already-started stream continue. |
| Audio/session recovery | Named headset, Bluetooth, microphone and default-output changes preserve gain/mute/tracks/monitoring and audible output. Test sleep/wake, connection loss, supported game/native/Wayland capture and bounded recovery/escalation. Retry never launches stopped output. |
| Recording/replay/clips | Controller focus reaches Start/Stop/Save/Cancel. Confirm replay/record/stream coexistence, moving/audible finalized files, new replay paths, preserved partial clips, XDG/custom/SD-card permission handling, reserve-limit finalization, interrupted-file recovery, exclusive export and exact-preview cleanup. Never fill the actual device disk to zero. |
| Health | Current bitrate/frame loss/load/audio/capture observations stay readable, expire to unknown and distinguish OBS output from viewer reception. Exercise network degradation, encoder overload and device/capture loss; recommendations do not alter quality automatically. |
| Stop/restart/offline | Repeated starts and stops stay truthful; games, restored devices and reconnects do not restart stopped broadcasting. Existing local config/recording works offline. Observe menu/controller/session performance and recovery limits. |

Add dated criterion-level observations to #47, #24, #48, #49 and #50, including
failed/skipped/unsupported cases. Preserve #24's #10/#17/#21 dependencies. Do not
close a hardware acceptance criterion from a source merge. The separate M2
provider/adoption, CI, identity and publication gates remain open. #51 is excluded.
