# Contributing

Read [continuity](CONTINUITY.md), [roadmap](ROADMAP.md) and any scoped instructions
before changing source. Preserve v0 compatibility, user-owned/offline operation,
approval and recovery behavior, safe paths, deterministic outputs and secret
filtering. Keep the current public source/package name until the separately
reviewed Decky Stream migration is approved. Avoid embedding a new organization,
wallet, publisher identity or permissions that the owner has not supplied.

Use the pinned tools and supported commands in
[Steam Deck building](docs/steam-deck-building.md). Run focused checks while
implementing and the complete appropriate qualification matrix at the final
source revision. [Local CI](docs/local-ci.md) runs the existing workflows using a
checksum-pinned act client and records unsupported platforms/services explicitly.
Go changes must pass formatting, vet and staticcheck 0.8.2 as well as their tests.
Security fixes need credential-redaction/cancellation/path tests where relevant;
do not use real provider credentials or broadcast to a real service in fixtures.

Keep changes bounded and reviewable, push draft checkpoints, update continuation
notes, and provide exact commands, revisions, platform, outcomes and limitations.
Old passing receipts do not qualify a new source revision. A PR merge alone does
not satisfy an issue's acceptance criteria. Proposed ADRs remain proposed until
the documented decision process accepts them.

Release automation creates review artifacts and non-publishing snapshots only.
See [release engineering](docs/release-engineering.md) before changing packaging,
licensing, preferred source, checksums, update or publishing behavior. Publication,
deployment, another repository change, paid resources and owner identity/rights
decisions require owner authorization. Do all independent preparation first.

Report product problems through [support](SUPPORT.md), and security problems
through [security](SECURITY.md). Share a redacted reproduction, not a raw private
profile. Contributions retain their applicable source and dependency licenses;
preserve third-party attribution and preferred-source material.
