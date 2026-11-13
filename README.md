# Decky Stream

Stream from Steam Deck through a managed OBS Studio instance and a Decky Quick
Access panel. **Milestone 3 streaming features are a development candidate**, with actual Deck,
provider-viewer, required CI and review acceptance still open. The executable,
plugin and storage compatibility IDs remain `obsgod` / `OBSGod`.

- Automatic streaming status, state-driven Start/Stop/Cancel and copyable diagnostics.
- Entire-screen or game-only video, with black/plain-text between-game fallback.
- System audio plus an optional microphone; game-only video does not isolate audio per app.
- Guided Kick, Twitch, YouTube and custom RTMP(S) setup.
- Verified installer/update paths, repair and reviewed uninstall/reset/wipe.
- Optional funding buttons; cryptocurrency controls stay hidden without configured addresses.
- Versioned quality presets and advanced profiles, with portable settings-only export.
- Custom local image/video between-game media, with rights acknowledgement and muted video soundtrack.
- Local recording/replay controls, finalized clip export and explicit storage/cleanup choices.
- Bounded audio recovery and measured stream health; provider/viewer reception remains separate.

## Install and first stream

Follow the [Steam Deck guide](docs/steam-deck.md) in Desktop Mode. Extract the
whole reviewed candidate, run its installer and configure your destination/key
locally. Return to Gaming Mode, make a local clip and verify its picture/sound,
then explicitly start streaming and check a separate viewer.

OBS 28+ includes its WebSocket server. The installer checks compatible OBS and
capture dependencies; no second WebSocket plugin is required. Stock OBS needs
a graphical session. This project manages it in the background; it is not a
headless OBS server.

Use the exact candidate/revision/checksums from the draft PR evidence. An older
[published preview](https://github.com/szmyty/obsgod/releases) does not contain all
current changes. No new release or website deployment is implied by this README.

## CLI and documentation

```sh
obsgod --help
obsgod version --json
obsgod config show --json
obsgod stream status --json
obsgod deck support-bundle > support.json
```

Help/version/completions work offline. OBS commands require the intended OBS
instance; inspection or profile selection does not implicitly broadcast.

- [Configuration, profiles, environment and completions](docs/configuration.md)
- [Advanced stream profiles](docs/advanced-profiles.md), [idle media](docs/idle-media.md),
  [recording/replay](docs/recording-replay.md), [runtime recovery](docs/runtime-resilience.md)
  and [stream health](docs/stream-health.md)
- [Remote OBS commands](docs/cli-usage.md) and [architecture](docs/architecture.md)
- [Destinations and local connection recovery](docs/stream-destinations.md)
- [Support buttons and public wallet configuration](docs/support.md)
- [Support](SUPPORT.md), [security](SECURITY.md) and [qualification](docs/steam-deck-qualification.md)
- [Proposed roadmap](ROADMAP.md), [M2 implementation ledger](docs/milestone-2.md)
- [Identity/migration decisions](docs/identity-migration.md)

## Development

Use the repository-pinned Go 1.27.4, Node 24.19.0 and npm 11.9.0 tools. The
Steam Deck workflow records the package, browser and native OBS checks. Generate
metadata with `python3 scripts/generate-product.py` and
`node scripts/generate-support.mjs`; package only a clean exact source revision.

The reusable remote CLI remains installable with
`go install github.com/szmyty/obsgod@latest`; a Go install alone does not install
the complete managed Steam Deck application. Cross-builds do not establish
support for untested devices or operating systems.

The original CLI MIT license and attribution are retained. OBS/GStreamer are
separate dependencies; review packages include native preferred source and all
bundled dependency notices. This is an independent community project.
