# Decky Stream 0.1.0-deck.7 — draft candidate notes

**Unpublished development candidate.** This file prepares release notes for
owner review; it is not a release announcement or a supported-device claim.
Exact source, artifact hashes and available qualification outcomes are recorded
in the [Milestone 2 ledger](https://github.com/szmyty/obsgod/blob/0eac1ed9746e6a5999a196777bde5455222f46eb/docs/milestone-2.md) and
[publisher packet](OWNER-PACKET.md) after the source is frozen.

The frozen source is `0eac1ed9746e6a5999a196777bde5455222f46eb`; all available
local checks passed. Runtime SHA256:
`4205e4725fd432ea99a59fe8c1a78f0f7b29c7ddbd6c79e3cf4afd8c2c67c9c3`.
See the [full exact-source qualification](qualification.json).

## Changes

- Decky Stream working display name from one versioned metadata source, retaining
  existing OBSGod loader/CLI/storage/update identities.
- Feature-detected Decky plugin/user environment paths and metadata, without
  changing the service's global HOME. Shared Desktop/CLI managed settings remain
  in one canonical XDG store; Decky's persistent runtime-data directory is not
  ephemeral XDG runtime storage.
- Layered CLI configuration, private password references, connection and
  explicit automation workflow profiles, offline version/help/completions and
  command reference, actionable diagnostics and intentional machine output.
- Clearer state-driven Quick Access controls, observed audio/capture facts,
  progressive help and filtered copyable diagnostics.
- Guided Kick, Twitch, YouTube and custom RTMP(S) setup, with saved key/server
  binding protected through partial-write recovery.
- Local connection information/test and idle-only OBS password change/reset,
  followed by explicit authentication verification.
- Guided installation, XDG app-data resolution, disk/path checks, same-version
  repair and maintained updater compatibility.
- Reviewed uninstall/reset/owned-data wipe, supported fixed-plugin removal,
  dry-run/JSON/noninteractive options and separate recording selection.
- Five optional funding buttons plus configuration-ready Bitcoin/Ethereum/Solana
  receive dialogs using local QR/copy. All receiving addresses remain null and
  hidden until the owner configures and verifies them.
- Offline static landing/documentation preview and security/support guidance.

## Compatibility and upgrade

The executable remains `obsgod`; installed plugin name/directory, namespaces,
managed OBS profiles and historical download identities remain compatible.
Existing legacy app-data locations are retained when XDG changes rather than
silently moving keys/data. Conflicting installations fail with a recovery step.

The old published preview4.1 updater is permanently pinned to runtime4 and
cannot fetch this candidate. Download the current reviewed full installer or
updater. The maintained dynamic preview6 updater is a distinct compatibility
path; its original bytes must remain unchanged during qualification. A current
updater check cannot discover an unpublished release.

OBS 28+ includes its WebSocket server. Do not install a second WebSocket plugin.
Use the normal graphical session; managed OBS is not a headless server. Entire
screen includes menus. Game-only selects video, while system audio may include
other apps. Rich image/video scenes and advanced stream-editing UI remain M3.

## Remaining gates and known limits

Actual Steam Deck/SteamOS/Flatpak/Gamescope/controller/session/performance,
audible separate provider viewers, required CI and review evidence remain gates.
Cloud native OBS and protocol fixtures do not supply those receipts. GitHub
Actions has been billing-locked; any fresh failed/unstarted jobs are recorded
separately from local test outcomes.

Final organization, creative/rights-approved Identity assets, hosting/domain,
release/site approval, Store eligibility/submission and real funding/wallet
readiness remain owner or external decisions. No listing, payment receipt,
new-user adoption, new release or deployment is claimed. Cross-builds compile
only; untested operating systems are not newly supported.
