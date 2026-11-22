# Documentation

Start with the task you want to complete. The project is a development preview;
the current public display name is **deckystream**, while executable, plugin and
storage compatibility names remain `obsgod` / `OBSGod`.

## Steam Deck users

| Task | Guide |
| --- | --- |
| Install the standard plugin and configure OBS | [Steam Deck guide](steam-deck.md), [first-run dependencies](dependency-setup.md) |
| Identify the exact review download | [Current candidate and checksums](pre-migration-qualified-checkpoint.md) |
| Work through the prepared device checks | [Testing booklet](testing-booklet.md), [printable PDF](testing-booklet.pdf), [results template](testing-results-template.md) |
| Set a destination or recover the OBS password | [Destinations and control recovery](stream-destinations.md) |
| Choose microphone/headset and quality settings | [Microphone controls](microphone.md), [quality profiles](advanced-profiles.md) |
| Choose between-game media or save local clips | [Idle media](idle-media.md), [recording and replay](recording-replay.md) |
| Diagnose output or recover safely | [Stream health](stream-health.md), [runtime recovery](runtime-resilience.md), [support](../SUPPORT.md) |
| Update, remove or inspect legacy files | [Updates and recovery](steam-deck.md#updates-and-recovery), [uninstall/reset/wipe](steam-deck.md#uninstall-reset-and-wipe), [legacy cleanup kit](legacy-cleanup-kit.md) |

The current setup uses one standard **`obsgod-decky.zip`** through Decky's plugin
installation controls. OBS Studio and capture dependencies are a consented
first-run setup. Desktop Setup is optional; installing a separate Desktop
application is not required for the standard plugin. A GitHub source ZIP is not
the installable plugin ZIP. See the [package contract](decky-package.md).

The pinned candidate is source
`772230a32a8fdb237a58b8a637947b31671ad509`, carried by immutable artifact
[`430cc391`](https://github.com/szmyty/obsgod/tree/430cc391cb63f080214aacc279e5c04b1092c7a5).
Use its [owner packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md),
[standard ZIP](https://raw.githubusercontent.com/szmyty/obsgod/430cc391cb63f080214aacc279e5c04b1092c7a5/obsgod-decky.zip)
and [checksums](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/SHA256SUMS)
together. It is a review download, not a release or automatic update offer.
Local qualification does not establish Steam Deck/provider acceptance or hosted
CI execution. The booklet records prepared checks, not passed device tests.
Use the [roadmap](../ROADMAP.md) and [continuity](../CONTINUITY.md) for the owner's
current migration and testing sequence.

## Generic OBS CLI and automation

| Task | Guide |
| --- | --- |
| Control an existing OBS instance | [CLI usage](cli-usage.md), [generated command reference](cli-reference.md) |
| Configure connections, environment and completions | [Configuration](configuration.md) |
| Build reusable integrations | [Versioned public API](api-v1.md), [creator workflows](creator-workflows.md) |
| Inspect generic distribution and packaging | [CLI archive contract](generic-cli-distribution.md), [native packages](generic-packaging.md) |

The generic `obsgod` CLI controls an existing OBS instance. Installing it alone
does not install the managed Steam Deck application, OBS or Decky. New automation
should use the versioned public API; compatible CLI commands remain documented.

## Contributors and architecture

Start with [contributing](../CONTRIBUTING.md), [repository instructions](../AGENTS.md)
and [current work](../CONTINUITY.md). Use the pinned toolchain in the build guide.

| Task | Guide |
| --- | --- |
| Understand ownership and dependency boundaries | [Architecture](../ARCHITECTURE.md), [vocabulary](../ONTOLOGY.md), [decisions](../DECISIONS.md) |
| Build and validate the plugin | [Steam Deck building](steam-deck-building.md), [standard package](decky-package.md), [local CI](local-ci.md) |
| Change configuration, storage or lifecycle behavior | [Native configuration](native-configuration.md), [Decky storage](decky-storage.md), [runtime correctness](runtime-correctness.md), [cleanup and recovery](cleanup-recovery.md) |
| Prepare release or migration work | [Owner-run fresh repository](fresh-repository-runbook.md), [brand adoption packet](migration-brand-packet.md), [finalization checklist](finalization-checklist.md), [release engineering](release-engineering.md) |
| Find active priorities | [Roadmap](../ROADMAP.md), [implementation roadmap](implementation-roadmap.md) |
| Report a defect or vulnerability | [Support](../SUPPORT.md), [security reporting](../SECURITY.md) |

## Evidence and history

- [Current exact-source checkpoint](pre-migration-qualified-checkpoint.md) and
  [pre-test readiness](pretest-readiness.md) separate available local results,
  unavailable CI and unrun device/service gates. Later documentation does not
  relabel the pinned candidate.
- [Qualification guide](steam-deck-qualification.md) explains evidence boundaries;
  [the original criterion ledger](evidence/completion-criteria.json) preserves
  acceptance requirements and dependencies.
- [Project memorial](../MEMORIAL.md) gives the OBSGod history;
  [history capture and carry-forward](history/README.md) explains the portable
  tracker archive and its limits.
- [Early Steam Deck implementation](steam-deck-development.md),
  [4699235 Desktop review installer](current-review-install.md) and
  [1a/d0a completion review installer](candidate-9-install.md) are retained
  historical records. Their commands, source revisions and checksums apply to
  those older packages; use the current Steam Deck guide for standard ZIP setup.
