# Changelog

This file describes source changes. An entry does not imply a published release,
completed device qualification, successful hosted CI or production support.

## Unreleased completion preview

* Add an offline release auditor for actual runtime/Decky/updater bytes, source
  and preferred-source correspondence, deterministic SPDX inventory and unsigned
  provenance. Preserve explicit review/device/publisher/publication gates.
* Pin CI actions and Go/static-analysis/release tools; retain native platform
  members, race/coverage artifacts and PR dependency review. Snapshot builds keep
  publishing and signing disabled.
* Add a checksum-pinned local act launcher, digest-pinned Ubuntu runner mapping,
  verified pinned-action source cache and local evidence/artifact retention.
* Document contribution, security, support, release/rollback and local validation
  boundaries. The intended Decky Stream name remains subject to a coordinated
  product/storage/publisher migration; existing install compatibility is retained.

The complete candidate's feature changes, exact revision, qualification results
and remaining owner/device checklist are recorded in the current
[continuity notes](CONTINUITY.md) and [roadmap](ROADMAP.md). The final source and
artifact identities must be recorded there before asking for release approval.

## Candidate 8 source history

The previous reviewed source candidate was
`bf72ca4ae028f78895eadee6d3874734a1cccd05`, with review-only artifact commit
`9ad051ecbb41df92c723a54bdfb6aaaeb1097898` and follow-up evidence at
`250b29b437c14429a3049f3f0206bd6f16e0253d`. These historical receipts qualify
their recorded revisions only. See [release history](https://github.com/szmyty/obsgod/releases)
for what the owner actually published; this changelog does not rename or replace
those immutable artifacts.
