# Security reporting

The [release engineering guide](docs/release-engineering.md) describes pinned
checks, source/SBOM/provenance verification, update/rollback review and the
unsigned-publisher trust boundary. Local integrity or act results do not replace
required hosted review/CI or actual Steam Deck evidence. A stable support window
and publisher/signing policy require an explicit owner decision before a stable
release.

Decky Stream is currently a development preview. The reviewed source and exact
artifact revision determine what was checked; a passing older preview does not
qualify a newer candidate. Supported device/version evidence remains recorded
in the release qualification packet, with unavailable checks left explicit.

For suspected vulnerabilities, use GitHub's **Report a vulnerability** option
on this repository if available. If a private reporting option is unavailable,
open a minimal issue requesting a private contact channel before sharing an
exploit or sensitive details. No separate private reporting service or response
time is promised. Never post a stream key, OBS password, private setup URL,
wallet seed/private key, raw OBS configuration or unfiltered logs.

The local core requires no payment or cloud account. Support links open only
after an explicit action. Cryptocurrency support displays public receiving
addresses; the plugin does not hold keys, connect a wallet or sign transactions.
Source, dependency notices, checksums and the preferred native capture source
ship with review candidates. Checksums establish byte integrity, not independent
publisher identity or a code signature.

Security updates, support terms and publication remain owner decisions. Do not
describe a preview as a supported stable release before its required review,
CI and device gates pass.
