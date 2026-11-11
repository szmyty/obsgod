# Roadmap 1 draft candidate — 0.1.0-deck.5

This is a **review artifact**, not a published release or a claim of Steam Deck acceptance.
Source: `2287ed4c2f3fcc9b8ec42bbd68ac531063b5d578`.
Review: https://github.com/szmyty/obsgod/pull/31 (stack #26–#31, foundation #15).

For the candidate device test, download `obsgod-deck_0.1.0-deck.5_linux_amd64.tar.gz`, extract the entire archive in Desktop Mode and open `Install OBSGod.desktop`. Leave your current installation in place. The unified installer should preserve settings/key/media and replace only OBSGod's app/plugin after verifying Decky, dependencies and idle output. Keep normal Steam running in Desktop Mode for Decky's existing frontend connection. If Decky is missing, follow its official instructions and rerun; no silent privileged installation occurs. Read the included STEAM-DECK.md before broadcasting.

The standalone updater is included for future published-runtime updates. It checks official releases; **it cannot install this unpublished candidate from this review branch**. Use the complete candidate installer for the device test. The Check for updates button may show published runtime4 while this candidate is5; it must not downgrade.

Cloud checks: 56 Go cases passed (one optional read-only test skipped), 56 Python and8 panel cases passed; vet/vulnerability scan, typecheck/build/audit, repeated identical packages, actual Desktop/browser/ZIP, real pinned Decky transport + unified installer + updater fixture and real native OBS media/lifecycle checks passed. Cross-builds are compile-only. Exact commands, source, artifact hashes and limitations are in roadmap1-qualification.json; logs are under evidence/.

Real SteamOS/Flatpak/Gamescope/no-game Steam UI/VAAPI/audio/controller/session/performance and actual Kick viewer/adoption remain unverified. No real keys or external broadcasts were used. GitHub Actions jobs did not start because GitHub reports an account billing lock; their failed/cancelled results are not code-test passes.

No merges, issue closures, release publication or deployments were performed. Owner review, required device evidence and restored CI remain gates. Roadmap2 idle assets/password settings and the broader product backlog are untouched.

SHA256SUMS covers the runtime package; UPDATER-SHA256SUMS covers the updater. CANDIDATE-SHA256SUMS covers this complete review bundle. HTTPS/repository/source/checksum verification is not code signing.
