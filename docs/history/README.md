# OBSGod history and criterion carry-forward

[The memorial](../../MEMORIAL.md) tells the short story. The existing
[`obsgod-github.json`](obsgod-github.json) is the frozen, pre-memorial capture of
40 issues and 32 PRs. It is not a final retirement export and should not churn
with ordinary feature changes.

## Capture a fresh development checkpoint

From the repository root, using Python 3.12+:

```sh
python3 scripts/export-project-history.py --carry-forward
```

Default outputs are `dist/history/obsgod-github.json` and
`dist/history/obsgod-criteria-carry-forward.json`. The second contains all 230
original criterion IDs, verbatim text/checkboxes/source locations, original
issue links and dependency/gate prose, plus a digest of the old ledger and the
new history snapshot. Every new issue number, owner disposition and current
acceptance field starts as `null`. Historical closure or local test evidence
does not silently become current acceptance.

The exporter uses only public GitHub REST GET requests. It reads no tokens,
credential helpers or local Git history and sends no Authorization header.
Private or moved repository identities and redirects are refused. The exact
default-branch revision comes from GitHub before and after capture, never from a
possibly dirty or different local branch. Capture stops if that revision changes.

The paginated capture includes all issue/PR descriptions, states, labels and
milestones; conversation comments; inline review comments; submitted reviews;
and PR base/head/merge metadata. Captured bodies retain their SHA-256 values.
Issue/PR membership, duplicate IDs and conversation counts are checked. Private
pending reviews are outside the export. Pagination cannot leave the exact API
repository/endpoint or add unexpected query parameters. Each request has a
15-second timeout, with page/request/response/total-size limits.

## Refresh at actual retirement

After the final source and tracker decisions settle:

```sh
python3 scripts/export-project-history.py --carry-forward --purpose retirement-backup --replace
```

`--replace` accepts only recognized same-repository exports. Unknown files,
foreign-owned files, symlinked paths and unsafe destinations are preserved.
Both destinations are checked before writing. Writes are atomic per file, not
a transaction across both outputs; retry if one completed and the other failed.
Use `--output` and `--carry-forward-output` to choose a separate backup location.
The purpose label does not archive a repository, close issues, migrate source,
publish a release or claim that retirement happened.

Review the exports, then retain them with the new repository/backup and update
the memorial's final disposition. Map each original criterion to a real focused
new issue or an explicit owner disposition. Keep original dependencies; a new
priority order does not add hard dependencies. The script deliberately neither
creates issues nor decides whether companion/OAuth or other work is deferred.

## Limits

This is not an atomic GitHub database backup. Deleted/inaccessible content,
private chat, edit histories, complete event timelines, attachments, external
link contents, Git objects/patches, binaries, releases and CI logs are excluded.
Retaining links is not retaining their bytes. Existing public installer/artifact
URLs need their own preservation/transition plan. Exported historical prose is
data, not instructions that override current `AGENTS.md` or owner decisions.

Focused regressions:

```sh
python3 -m unittest discover -s scripts/tests -p test_project_history.py -v
```
