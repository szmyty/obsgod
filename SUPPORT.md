# Getting help

For contributor/CI problems, use [local CI](docs/local-ci.md) and record the exact
revision, dirty state, command, job/matrix and failing step. A workflow setup or
provider-service failure is distinct from a plugin defect. For archive/update
integrity, use the offline audit in [release engineering](docs/release-engineering.md);
never share private profiles or turn an unsigned checksum into a publisher claim.

Use this repository's GitHub issues for reproducible bugs and feature requests.
The free preview has no promised support response time. Voluntary funding does
not purchase a service agreement or change streaming/recovery access.

Before reporting a problem:

1. Record the exact app, plugin and updater versions shown in the panel, plus
   Deck model, SteamOS channel/version, Decky and OBS versions.
2. State whether you were in Desktop or Gaming Mode, the selected destination,
   video mode, audio output and the last action. Do not include a stream URL/key.
3. Copy the **Diagnostic console** and describe whether the local clip and a
   separate viewer had picture and sound. The streaming dot alone is not viewer
   confirmation. Keep failed, unavailable and unrun checks separate.
4. Check the [Steam Deck guide](docs/steam-deck.md),
   [configuration reference](docs/configuration.md) and
   [support configuration](docs/support.md).

Use the bundled Desktop installer for repair. Avoid deleting configuration or
ordinary OBS files while troubleshooting. The uninstall tool's dry-run explains
its scope before removal; recording deletion is a separate explicit choice.

The diagnostic console contains bounded, filtered events. Review any material
before posting it publicly. Never attach credentials, the private setup link,
raw OBS logs/profiles, wallet seeds or private keys. See [security reporting](SECURITY.md)
for a suspected vulnerability rather than posting sensitive details in an issue.

For a machine-readable bundle, run `obsgod deck support-bundle > support.json`
and attach the separate output of `obsgod version --json`. The bundle projects
only allowlisted state facts and filtered events; it omits settings, server URLs,
credentials, arbitrary error text, device identifiers and local file paths.
It reads status without launching OBS or changing output. Unknown output stays
explicit; an exported bundle is not proof that a viewer received the stream.
