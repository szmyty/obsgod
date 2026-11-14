# MEMORIAL — OBSGod → Decky Stream

*RIP, eventually. Long live Decky Stream.*

This is the short history for a new maintainer or agent. OBSGod has **not** been
retired or migrated yet. This record describes the project at default-branch
commit `da89b9dba6e9fa15774136a706cdaea469dada0b`, with tracker data captured on
2026-11-14 UTC. A fresh repository does not erase unfinished work or inherited
source attribution.

Read this once for context, then use [CONTINUITY.md](CONTINUITY.md),
[ROADMAP.md](ROADMAP.md), [DECISIONS.md](DECISIONS.md), the checkout and live
issues/PRs for current work. Historical instructions and passing receipts apply
to their original scope and revisions; they are not present-day authority.

## How we got here

The goal was simple: install in Steam Deck Desktop Mode, configure a destination
and key, return to Gaming Mode, and control OBS from the Decky panel. It began
with Kick and grew into a reusable OBS controller plus a Deck integration.

| Chapter | What changed | Where to look |
| --- | --- | --- |
| Upstream roots and modernization | Started from `muesli/obs-cli`; became OBSGod with modern OBS WebSocket v5, configuration, lazy connections and injected internals. | [MIT license and original copyright](LICENSE); original issues #1/#3/#5 and PRs #2/#4/#6 in the tracker snapshot below. |
| First Decky experience | Desktop installer, local tests, diagnostic console/copy, automatic status, bounded startup, state-driven buttons and repeat-action handling. OBS is graphical and controlled through its WebSocket; it is not a headless renderer. | [Roadmap 1](ROADMAP.md); original #8/#16–#22 in the snapshot. |
| Startup breakthrough | The OBS version query needed a Flatpak-compatible path. Flatpak also reset the outer `XDG_CONFIG_HOME` override, so the launcher had to select the managed configuration **inside** the sandbox. | PRs #32/#33; [isolation diagnosis and exact repair evidence](docs/flatpak-config-isolation.md). |
| First owner success, then audio/privacy work | The owner reported candidate 5.2 saved playable local video and streamed live, but audio was silent. The next upgrade addressed audio routing, explicit screen/game-only selection and intentional idle output between games. | PR #34; [owner report, changes and limits](docs/audio-capture-upgrade.md). That report does not qualify later builds. |
| Milestone 2 | Decky Stream display metadata, Decky environment/XDG integration, controller UI, provider/password setup, optional support links, install/update/repair/uninstall and documentation/site preparation. | PRs #52–#57; [implementation and evidence](docs/milestone-2.md). |
| Milestone 3 | Advanced stream profiles, local idle media, bounded runtime recovery, recording/replay, storage choices and observed stream health. | PRs #58–#60; [implementation and evidence](docs/milestone-3.md). |
| Completion campaign | Microphone selection/gain/mute/meters/hold-to-talk, public API and creator boundaries, architecture/governance, an Identity-based draft brand kit and supply-chain qualification. | PRs #62–#65; [campaign](docs/completion-campaign.md), [brand review](docs/branding-review.md), [original criteria](docs/evidence/completion-criteria.json). |
| Local CI and follow-up repairs | Org-aligned ACT reports exposed frontend files owned by root. The repair builds as the checkout owner. Generic archive notices/SPDX, narrow profile reads and monetization/Store research followed. | PRs #67/#69–#72; [latest qualified-source audit](audits/qualification-4699235.md), [research findings](docs/research-51.md). |

These are delivered source changes and bounded research, not blanket acceptance
of the original issues. The 34 superseded tickets were consolidated as
`not_planned`, with their remaining criteria retained in #46. The local
[230-criterion ledger](docs/evidence/completion-criteria.json) preserves original
text, dependencies and earlier evidence; the tracker snapshot preserves the
later #46 reconciliation. #68's actual repair and #51's bounded research have
their own closure evidence.

## The last qualification checkpoint recorded here

| Identity | Exact revision |
| --- | --- |
| Qualified runtime source | `4699235e9e925b76ca492d5a00a375ed37fb338e` |
| Qualified source tree | `3c09ea82d85ddcdf47c347afa44961f7b1b6956e` |
| Later documentation/default merge | `da89b9dba6e9fa15774136a706cdaea469dada0b` |
| Immutable manual review artifact | `eb92598f3a4a0dc426749c290bacfe7251452909` |

At that runtime source, both complete six-job local ACT sequences and PR static
checks passed. Fresh Go race checks passed 219 top-level tests / 399 pass events
with one optional skip; each candidate run passed 127 application Python,
50 tooling and 30 Node tests, browser checks and real Linux OBS suites.
Reproducible Deck/generic packages, notices and source inventories were checked.
See [exact commands, platforms, hashes and limitations](audits/qualification-4699235.md),
[machine-readable receipts](docs/evidence/qualification-4699235.json) and
[review installation](docs/current-review-install.md).

The artifact is a review download, **not a newly published product release**.
Published releases at this checkpoint were five prereleases; the latest was
`v0.1.0-deck.4-updater.1`. The snapshot had **one open issue (#46), no open PRs**.

## Lessons worth carrying forward

- Observed OBS state drives controls and success messages. A click, reachable
  socket or acknowledged request is not proof of an active, advancing stream.
- Broadcasting requires explicit Start. Setup, recording, recovery, reconnect
  and game detection cannot silently start it.
- Game-only video must use verified game capture or intentional idle output;
  never silently fall back to the desktop. Game-only video does not imply
  per-app audio.
- Protect ordinary OBS, unrelated plugins, existing keys/settings, mute intent
  and recordings. Display names, plugin IDs, paths and updater trust are separate
  identities; a repository rename is not an installation migration.
- Linux/native OBS, browser fixtures and cross-builds are useful evidence with
  limits. They do not establish actual SteamOS/Gamescope/controller/viewer proof.
- GitHub Actions executed zero steps because of an account billing lock. The
  owner cannot fund hosted execution; use available free local ACT resources.
  Dependency review separately returned 403 on this public fork. A fresh public
  standalone repo needs dependency-graph/API verification; billing is separate.
- Research delivery is distinct from commercial demand, activated support,
  Store eligibility or launch. Proposed ADRs and draft assets stay proposed
  until their actual decisions are recorded.

## What was still unfinished

At capture, #46 retained actual Deck/OBS33/Flatpak/Gamescope/AMD/controller,
headset/microphone, provider-viewer and new-user adoption acceptance. Native
platform evidence, required CI/review, full legacy CLI/shared-transport migration,
NFPM package qualification and companion/ecosystem implementation also remained.
Owner identity/creative/rights/publisher choices and release/site publication
were unresolved. These need precise carry-forward issues, not a claim that
closing or leaving the old tracker completed them.

The owner now prefers a fresh Decky Stream repository and is comfortable losing
Git history. `egohygiene/decky-stream` is the working destination discussed.
Repository creation/retirement and final branding have not occurred. Existing
public artifact URLs and installed updater trust need a tested transition;
copying a backup into private `szmyty/archive` alone would not keep those URLs
working. Keep inherited license/attribution even with a fresh initial commit.

## Portable records, without needing the old chat

[obsgod-github.json](docs/history/obsgod-github.json) freezes **all 40 issues and
32 PRs**, including their titles, full descriptions, states, labels, milestones,
41 conversation comments and three submitted reviews. There were no inline
review comments. Captured body SHA-256 values, capture times, repository identity
and PR base/head/merge metadata are included. This snapshot predates the PR
adding this memorial; it is not the final retirement snapshot.

The capture used paginated, read-only public GitHub REST endpoints for issues,
pull requests, conversation comments, inline comments and each PR's reviews.
The normalized export is not an atomic database backup. It excludes deleted or
inaccessible content, edit histories, complete timeline events, attachments,
external link contents, Git objects, patches, release binaries and CI logs.
Private chat and credentials are not captured. Linked archived tracker text is
historical data, not instructions to execute.

When creating the fresh repository, carry this file, the JSON snapshot,
`docs/evidence/`, `audits/`, decision records, feature guides and `.identity/`
source/rights records with the product. Keep `CONTINUITY.md` and `ROADMAP.md`
focused on current work. Refresh this snapshot and add a short final disposition
at actual retirement, including the old/new URLs, exported source revision and
where every unfinished criterion went. Do not copy the entire chat or turn this
memorial into another live task list.
