# OBSGod installer 5.1: corrected Flatpak version detection

Review candidate0.1.0-deck.5.1. Source: f43e5b53b473c35dfe3facec114d28cbeff6c35d.
PR: https://github.com/szmyty/obsgod/pull/32. This is not a published release.

The previous installer incorrectly used unsupported `flatpak info --show-version` and called its failure OBS below28. The fix uses supported info --show-ref and list --columns=ref,version, normalizes the kind prefix and matches the exact user application/architecture/branch. OBS33.0.1 is accepted by regression tests; unavailable/malformed version metadata is reported separately from a confirmed old version. Actual Flatpak1.16.6 rejects the old flag and accepts the corrected command surfaces. Nonempty installed-row format is confirmed from matching upstream source and fixtures; synthetic metadata export succeeded, but full synthetic installation was unavailable due to service connection setup. No real Deck success is claimed.

Download the complete obsgod-deck_0.1.0-deck.5.1_linux_amd64.tar.gz, extract it in Desktop Mode and run Install OBSGod.desktop (or python3 install.py). Keep normal Steam open and stop streaming/recording first. Leave the old installation in place; the supported installer replaces the app/plugin, preserves key/settings/media/history and retains rollback copies. The earlier false-version error occurred before app/plugin replacement. No second WebSocket plugin is needed for OBS28+.

The standalone updater follows published releases and cannot fetch this unpublished review candidate. Use the full installer above for the owner retry.

Fresh exact-source checks passed: Go56(1optionalread-onlyskip), Python60, Node8, vet/vulnerabilityscan, typecheck/build/audit, repeatedbyte-identicalruntime/updaterpackages, actualarchivebrowserfresh+preview4upgrade, actualZIPpanel, isolatedpinnedDeckyfrontend/router/installer+realunifiedinstaller+DesktopupdaterunderHTTPSfixtures, nativeOBS30.2.3/WebSocket5.5.2/GStreamer1.26.2moving720p/audio/localRTMP/repeatedlifecycle/failurecleanup/confirmedshutdown. LinuxARM64/WindowsAMD64/macOSARM64compiledonly. Evidence and exact commands/limits are in installer-flatpak-qualification.json and evidence/.

Actual Steam Deck/Flatpak/Gamescope/VAAPI/audio/controller/session/Kick/adoption remains unverified. Current CI jobs did not start because GitHub reports an account billing lock. Milestone1 was administrativelyclosedbyowner; its unsatisfiedacceptanceissuesremainopen. No release/deployment/spending or additional merge was performed for this repair.
