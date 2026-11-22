# Fresh deckystream repository: owner-run preparation

The owner moved testing after repository creation. #117 is merged in
[PR #118](https://github.com/szmyty/obsgod/pull/118) at `8523207`. This runbook
prepares the fresh snapshot requested under #87; it is not an executed migration.
Recommended destination: **`egohygiene/deckystream`**. That is the assistant's
recommendation after the owner asked for advice, not a fabricated owner decision.
The exact `--destination` in an owner-run apply is the explicit selection.

## What is ready, and what is still a fact

- The selected aurora kit, readable README/docs, five funding links, source
  notices, memorial and original criterion ledger are already present.
- [Brand adoption packet](migration-brand-packet.md) records the existing assets
  and the pending released Identity version and artwork license decisions.
- The migration tool can prepare a tracked-source snapshot without copying or
  deleting the working `.git` directory. It refuses dirty input, an ambiguous
  source revision, unsafe output paths and an existing destination repository.
- An explicit staged canonical transition changes only the five named project/
  updater metadata files in the new snapshot. The current checkout remains
  `szmyty/obsgod`. Installed IDs, credentials, XDG paths, Go module/import path,
  historical URLs and artwork rights are preserved. Read the generated diff.
- Fresh source is not a fresh binary qualification. Build the destination's
  exact candidate before the [finalization session](finalization-checklist.md).

## Local preparation: no GitHub writes

Use a clean checkout and replace the source SHA with the exact merged revision
being reviewed. The selected destination must be a real explicit owner, never
`OWNER`, a wildcard or an arbitrary URL. These commands require Python 3.12+,
Git and, for authenticated inspection/apply, an already authenticated GitHub CLI.
Do not put a token in the command or diagnostic output.

```sh
python3 scripts/prepare-fresh-repository.py \
  --source /absolute/path/to/obsgod \
  --source-sha FULL_40_CHARACTER_MERGED_SHA \
  --destination egohygiene/deckystream \
  --stage-canonical-identity
```

Default execution prints a deterministic offline plan. To retain its files,
choose a nonexistent directory under an existing private owned parent with
`--output /absolute/private/new-plan`. Original `source.tar`, staged
`snapshot.tar`, canonical-change review and criterion/history sidecars have
different purposes; do not describe the original archive as the staged snapshot.
Add `--inspect-destination` for read-only authenticated source/owner/destination
checks. A 404 alone is not proof of authority to create a repository.

## Exact source and portable history

After preparation commits are merged, refresh the public tracker export against
that same default-branch SHA. The exporter reads only public GitHub data and
checks the default revision before and after capture:

```sh
python3 scripts/export-project-history.py \
  --repository szmyty/obsgod \
  --purpose retirement-backup --carry-forward \
  --output /absolute/private/public-history.json \
  --carry-forward-output /absolute/private/original-criteria.json
```

The purpose label does not mean retirement happened. All original criteria,
dependency prose and public tracker bodies are carried as history, not current
acceptance. The source tar and tracker export do not retain release binaries,
attachments or Git history. Preserve those separately before later retirement.

## Owner-run creation

The apply uses the reviewed exact source and matching tracker backup. It stages
the named canonical identity changes, creates an independent public repository
and pushes one new root commit on `main`. It does not overwrite a repository,
force push, publish a release, deploy a site, archive/delete the source or close
issues. Source rules and branch protection are not bypassed.

```sh
python3 scripts/prepare-fresh-repository.py \
  --source /absolute/path/to/obsgod \
  --source-sha FULL_40_CHARACTER_MERGED_SHA \
  --destination egohygiene/deckystream \
  --stage-canonical-identity \
  --history-backup /absolute/private/public-history.json \
  --output /absolute/private/new-apply \
  --apply
```

The first commit requests `[skip ci]` to avoid the known account-billing refusal;
existing workflow files remain. Skipped or unstarted jobs are not passes. Inspect
actual destination settings/rules after creation; the script's permission check
is not evidence of dependency graph, advisory review or successful hosted jobs.

If creation/push/verification fails, retain the local receipt and both source and
partial destination. A network failure may leave a completed remote operation;
the tool records attempted/unknown state and never deletes remotely to retry.
Inspect before deciding how to resume. Existing destination refusal is deliberate.

## Two fresh issues, using real returned numbers

After the destination is verified, create the finalization issue from
`docs/finalization-checklist.md`, and carry optional login research separately
from `docs/auth-research-carry-forward.md`. GitHub assigns the new numbers; old
**#89** is an origin reference, not a promised future issue number. Record the
actual links in `docs/history/fresh-repository-carry-forward.json` and link the
old open issues before administrative consolidation. Superseded is not passed.

The finalization issue covers the remainders of #46/#79/#82/#83/#85/#86/#87/#88/
#95 and the intact original ledger. The preserved closed research history does
not silently authorize Store submission, paid features or OAuth implementation.

## Release, then retirement

Run local qualification and the owner Deck/provider fix loop on the real new
candidate. Prepare the exact tag, artifacts, notices, changelog and remaining
exceptions before release approval/execution. Then refresh the history and
preserve the old release/artifact bytes and any remaining consumer dependencies.

Copying source into `szmyty/archive` without `.git` is not a complete GitHub
backup. Deleting `szmyty/obsgod` breaks its original issue, release and immutable
download URLs and may affect the retained Go module path. Prefer read-only
archival while those links are needed. Neither option is bundled into creation.
