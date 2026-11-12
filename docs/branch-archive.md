# Branch consolidation record

Checked 2026-11-12. User authorized merging all open PRs in dependency order and
removing nonprimary branches. No force push, protection bypass, release or
deployment was performed.

## Merged pull requests

| Order | PR | Original head | Merge commit |
| --- | --- | --- | --- |
| 1 | [#32](https://github.com/szmyty/obsgod/pull/32) | `40b58fe912137fada49e2a14a3a7603457fe8b78` | `e62cb8ab1f88f8354fcc7f46e8f4f486c52d2122` |
| 2 | [#33](https://github.com/szmyty/obsgod/pull/33) | `c6f8455704168aad6b83910677fe72871aa0fbe8` | `01a1fcccca7d41fcf9988d6b05ef7a05eb73ede5` |
| 3 | [#34](https://github.com/szmyty/obsgod/pull/34) | `5f2e1816285c55e3e1d879998d3fc46bba7ce5a7` | `cc5e5b6b6d4c18c54b1040722924c6b68e5c4ccd` |

PRs #33 and #34 were retargeted to the default branch after their predecessors
merged. The final merged tree at `cc5e5b6b6d4c18c54b1040722924c6b68e5c4ccd`
was identical to PR34 head `5f2e1816285c55e3e1d879998d3fc46bba7ce5a7`.
Fresh merged-tree checks passed: Go race tests 94 pass events/64 top-level,
Python 70 and Node 9; one optional existing-OBS Go test skipped. These checks do
not replace the exact [preview6 qualification](audio-capture-upgrade.md) or
supply the missing actual Deck/CI acceptance. Fresh CI jobs executed zero steps
because of the GitHub account billing lock.

## Default branch gate

The only remaining remote and local branch is `master`. Renaming it to `main`
through GitHub returned HTTP 403, `Resource not accessible by integration`.
The smallest owner action is to rename `master` to `main` on the repository
**Branches** page. Do not create a duplicate source branch or bypass permissions.
The candidate workflow now accepts both names.

After the owner rename, refresh an existing checkout with:

```sh
git fetch origin --prune
git branch -m master main
git branch --set-upstream-to=origin/main main
git remote set-head origin -a
```

## Archived exact branch tips

All 22 nonprimary remote branch tips were verified against lightweight archive
tags before deletion. Thirteen existing local branches were likewise removed
after verification. Archive tags are recovery references, not release tags.
The orphan artifact histories remain reachable so immutable SHA download links
continue to resolve. They must never be merged into source. The unmerged legacy
branches were archived, not declared accepted or silently merged.

To inspect one without recreating a branch:

```sh
git fetch origin --tags
git show archive/2026-11-12/codex/deck-audio-capture-modes
```

| Deleted branch | Exact tip | Archive tag |
| --- | --- | --- | --- |
| `artifacts/deck5-config-isolation` | `414480b8cdc23f0eb5e0ea209f45f98adcddaebd` | `archive/2026-11-12/artifacts/deck5-config-isolation` |
| `artifacts/deck5-flatpak-fix` | `afec6263fc43369917cd54b80a58055d5c00f0e6` | `archive/2026-11-12/artifacts/deck5-flatpak-fix` |
| `artifacts/deck6-audio-game` | `71143dce72654bae2ad76ebe382dd810990c2c85` | `archive/2026-11-12/artifacts/deck6-audio-game` |
| `artifacts/roadmap1-deck5-review` | `1fbf92ff36eea77bee0f3da186e99d856c80774e` | `archive/2026-11-12/artifacts/roadmap1-deck5-review` |
| `codex/deck-audio-capture-modes` | `5f2e1816285c55e3e1d879998d3fc46bba7ce5a7` | `archive/2026-11-12/codex/deck-audio-capture-modes` |
| `codex/fix-flatpak-config-isolation` | `c6f8455704168aad6b83910677fe72871aa0fbe8` | `archive/2026-11-12/codex/fix-flatpak-config-isolation` |
| `codex/fix-flatpak-version-probe` | `40b58fe912137fada49e2a14a3a7603457fe8b78` | `archive/2026-11-12/codex/fix-flatpak-version-probe` |
| `codex/roadmap1-installer` | `eed194086173426ed11db8923471fa82a404541e` | `archive/2026-11-12/codex/roadmap1-installer` |
| `codex/roadmap1-plan` | `8bda5f066bb3f4767f4ac217d17500f0da8269ab` | `archive/2026-11-12/codex/roadmap1-plan` |
| `codex/roadmap1-qualification` | `86de54abe98614f40287b37b5a33055a515fa501` | `archive/2026-11-12/codex/roadmap1-qualification` |
| `codex/roadmap1-runtime` | `e7ffc3a732ee9a35355f503761788768a18f1b23` | `archive/2026-11-12/codex/roadmap1-runtime` |
| `codex/roadmap1-state` | `34a87dd1e2c4648b18c8f0972a8c894dafea31b2` | `archive/2026-11-12/codex/roadmap1-state` |
| `codex/roadmap1-updater` | `d82c8f26e9bf552ad884e06d8b902de4f52db7b0` | `archive/2026-11-12/codex/roadmap1-updater` |
| `codex/steam-deck-streaming` | `0eb8324c2b1f23fea069570eded1cd0c75d99274` | `archive/2026-11-12/codex/steam-deck-streaming` |
| `dependabot/github_actions/actions/setup-go-4` | `dc0a22483250fa70c4ec99693538cbf49265fae2` | `archive/2026-11-12/dependabot/github_actions/actions/setup-go-4` |
| `feat/bootstrap-audit` | `50d5b9902f6b66158bd94039fc2bb812cd5e9d81` | `archive/2026-11-12/feat/bootstrap-audit` |
| `man-pages` | `f0659919fef2f7314c4b729102da0c9755b485c7` | `archive/2026-11-12/man-pages` |
| `release-artifacts/v0.1.0-deck.1` | `1120f75bb623c8ec54ba7f357b488c16c4e79eb1` | `archive/2026-11-12/release-artifacts/v0.1.0-deck.1` |
| `release-artifacts/v0.1.0-deck.2` | `5159564aa8f0ba494412c14a9e0e443e808cdbb0` | `archive/2026-11-12/release-artifacts/v0.1.0-deck.2` |
| `release-artifacts/v0.1.0-deck.3` | `6082fe686c4eb474b9f8850d777e6bbc7544ce3c` | `archive/2026-11-12/release-artifacts/v0.1.0-deck.3` |
| `release-artifacts/v0.1.0-deck.4-updater.1` | `d310e18da03ff324707ccb7e3ab3fb1c148b6800` | `archive/2026-11-12/release-artifacts/v0.1.0-deck.4-updater.1` |
| `release-artifacts/v0.1.0-deck.4` | `64039036e0ef8d0fa0e9242cf6abf8cf2583a606` | `archive/2026-11-12/release-artifacts/v0.1.0-deck.4` |

No GitHub release was published by creating these archive references. Existing
release/download identities and the preview6 artifact hash were preserved.
