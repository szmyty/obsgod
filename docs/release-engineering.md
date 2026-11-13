# Release engineering and trust boundaries

The supported product candidate is the user-owned Linux amd64 Steam Deck
installation. The generic CLI is also compiled on the operating systems in
`.goreleaser.yml`; a cross-compiled executable is not evidence of a working
installation, OBS integration or supported desktop on those platforms. Native
macOS/Windows and Linux arm64 evidence must remain separate from Linux amd64
checks. Real Deck/Flatpak/Gamescope, controller, hardware and provider-viewer
checks are described in [qualification](steam-deck-qualification.md).

## Build and review a candidate

Use the pinned toolchain and repository commands in
[building](steam-deck-building.md). Commit the complete selected source before
packaging; dirty manifests cannot be qualified or used by the updater. Keep the
source commit, package version and review-only artifact commit distinct.

From the exact, clean revision, package the runtime and updater twice and compare
`SHA256SUMS` and `UPDATER-SHA256SUMS`. Then run:

```sh
python3 scripts/release-audit.py --revision "$(git rev-parse HEAD)" --output dist/supply-chain
cp dist/supply-chain/AUDIT-SHA256SUMS /tmp/obsgod-audit-first
python3 scripts/release-audit.py --revision "$(git rev-parse HEAD)" --output dist/supply-chain
diff -u /tmp/obsgod-audit-first dist/supply-chain/AUDIT-SHA256SUMS
```

The audit works offline using Git objects at the explicit revision and the
already built `dist` files. It parses Go binary metadata with `go version -m`;
it never runs the packaged executable or extracts archive members onto disk.
Its checks include archive path/link/duplicate/expansion safety, every manifest
and outer checksum, matching CLI/capture bytes in the runtime and Decky ZIP,
matching updater source, source text against the selected commit, capture
preferred source/build receipt, Go dependencies against `go.mod`/`go.sum`, and
shipped license/notices/LGPL preferred-source inventory. The exact complete
SDK source and import-only runtime changes are checked against the reviewed
upstream npm archive's lockfile integrity and pinned file hashes. A relabelled manifest,
missing source or conflicting artifact fails the audit.

`capture-build.json` records the actual native builder image ID, compiler,
package versions, source/Dockerfile/library hashes, shared-library requirements
and network-free compilation. Those system libraries, OBS Studio, obs-gstreamer,
Flatpak, Steam/Decky and runtime-supplied React/UI are installed separately; the
SBOM does not claim their binaries are inside our package or qualified by it.

The output contains:

* `sbom.spdx.json`: SPDX 2.3 with SHA256 for actual archives and payload files,
  linked Go modules/standard library, the shipped Decky API/QR implementation,
  and clearly marked locked npm build inputs. `NOASSERTION` is deliberate where
  the tool has not made a legal license conclusion. Complete dependency notices
  are still shipped. Build-input relationships do not mean redistribution.
* `provenance.unsigned.json`: deterministic in-toto/SLSA-shaped **unsigned,
  self-reported** source/material/artifact inventory, actual toolchain and native
  image ID. It makes no authenticated publisher, trusted builder or SLSA level
  claim. Commit time supplies deterministic document time, not a claim about
  when a build or test ran.
* `release-audit.json` and `AUDIT-SHA256SUMS`: selected revision/version/subjects,
  audit outcomes and unresolved qualification/review/publication gates. An
  integrity pass does not change those gates to passed.

These files are review artifacts. Checksums detect byte changes when compared to
a trusted copy; checksums and unsigned provenance do not establish who published
the files. An owner must select the publisher identity and verification policy
before release. GitHub OIDC attestations require an approved hosted publishing
workflow and owner-controlled permission; key-based signatures require an owner
key. No key, signature, identity or successful hosted attestation is invented by
local tooling. Publishing an intentionally unsigned preview must be an explicit
owner decision with its verification limits visible to users.

## Automated checks and review

All workflows use explicit tool/action pins, read-only default permissions,
bounded timeouts and cancellation of superseded work. `build` runs native
Linux/macOS/Windows members; `coverage` records the actual race-enabled Go
coverage summary without inventing a percentage target. Compare the retained
summary and profile to a qualified previous revision when evaluating a change.
`lint` runs full-source formatting, vet and staticcheck 0.8.2 with Go 1.27.4.
It replaces the historical floating golangci action and its PR-only new-issue
filter; it does not claim that legacy mode was executed. The PR dependency
review job checks newly introduced dependencies against GitHub advisories and
does not post comments or write repository contents. That provider API needs
separate hosted evidence; a synthetic act event is not a real dependency review.
The candidate workflow also runs pinned govulncheck and npm audit. Advisory
results are time-dependent; preserve the timestamp, command and source revision.

`goreleaser` pins GoReleaser 2.20.2 and always uses
`release --snapshot --skip=publish,sign --clean` into `dist/snapshot`, keeping its
cleanup separate from immutable review/runtime artifacts. Its configuration downloads
existing modules rather than modifying `go.mod`, strips host paths/build IDs and
retains source/version metadata. Package formats and cross-build targets are
configuration candidates until the corresponding snapshot has passed; they are
not instructions to overwrite system files on a Steam Deck.

No workflow publishes a release/site, deploys, changes protection rules or pays
for hosted capacity. Local [act runs](local-ci.md) do not prove GitHub runner,
artifact service, branch protection, required reviews or publisher behavior.
If hosted CI is blocked by account billing/permissions, record **unavailable**;
do not weaken tests, enable unproven required checks, or call the status green.

## Release, updates and rollback

Before requesting publication approval, prepare one reviewable owner packet:

* Exact clean source and version, changes/compatibility notes, immutable review
  artifact location, checksums/SBOM/unsigned provenance and reproduction receipt.
* Criterion-level command/platform/outcome evidence, actual device/provider
  results, required CI/reviews, limitations and any unrun checks.
* Preferred-source/notices/rights review, selected publisher and destinations,
  signing/unsigned-preview decision, owner actions and concrete approval scope.
* Verified upgrade preserving existing configuration/secrets, explicit uninstall
  inventory and rollback to a known qualified artifact. Do not copy raw private
  profiles into public evidence. Reconfirm startup/stream status and audio after
  rollback; downloading old bytes alone is not recovery proof.

Only the repository owner can authorize an Identity release, product release,
deployment, organization move or another repository change. Approval concerns
the prepared candidate and exact destinations. After publication, verify the
downloaded public bytes against the approved candidate and collect actual
consumer installation/adoption proof before closing release criteria.

The preview has no promised stable support lifetime or response SLA. A future
stable release must name supported hardware/software versions, update policy,
maintainers and security contact. See [security](../SECURITY.md) and
[support](../SUPPORT.md); no imaginary owner commitment is implied here.
