# Roadmap 1 execution record

The owner approved implementation on 2026-11-11 after reviewing
[Roadmap 1 / #8](https://github.com/szmyty/obsgod/issues/8). Changes remain draft
until owner review; do not merge, close acceptance issues, or publish a release
from an implementation checkpoint. Roadmap 2 and the deferred product roadmap
remain outside this campaign.

## Inspected starting point

| Item | Exact revision / identity |
| --- | --- |
| `master` | `d0268d13381b463f5950d202917f437a6288a3e4` |
| Existing draft PR #15 | `0eb8324c2b1f23fea069570eded1cd0c75d99274` |
| Published preview 4 runtime/plugin source | `55c03dd4160e6f6b517e778cf99a755801eb0a28` |
| Preview 4 immutable artifact commit | `64039036e0ef8d0fa0e9242cf6abf8cf2583a606` |
| Preview 4 archive SHA256 | `c584c04ed3c79a01f1b846adc4f8bbe86c8132a4bca2cf6ba60cc557eba39ce1` |
| Preview 4 Decky ZIP SHA256 | `3eec780691c0d9d62ba286bfe946ae64ceda2124339e1e2f9314fb89ac8cae54` |
| Separate updater source | `0eb8324c2b1f23fea069570eded1cd0c75d99274` |
| Separate updater artifact commit | `d310e18da03ff324707ccb7e3ab3fb1c148b6800` |
| Separate updater ZIP SHA256 | `4d33ea8594deba08a98d243ce3a901e071b713fdf354ef4ce979dba97375ead5` |

Re-read the live issues, PRs, releases, refs and rulesets before changing code.
There was one open draft PR (#15); all 18 reconciled issues remained open.
Branch metadata reported `master` unprotected and the repository ruleset list
was empty. The checkout was clean. No AGENTS.md was present in the checkout or
its parents. Git access, authenticated GitHub API access, command execution and
Docker access succeeded in the existing cloud environment. Preserve its proxy,
CA trust, unrestricted network policy and existing package/tool presets.

The published previews have no native GitHub release assets: their release
bodies point to immutable artifacts in this repository. Update discovery must
account for that format, and must distinguish runtime releases from the newer
updater-only release. Those historical hashes establish provenance only; they
do not qualify any changed source.

The owner's actual Deck still times out before OBS's control connection is
ready, including with a game open. The automated plugin update also failed
with an over-specific Big Picture hint. Neither cause is established. OBS
absent after changing sessions does not prove it never launched. Actual device
versions and a full redacted failure export are still unavailable.

## Reviewable PR sequence

Keep #15 as the preserved preview foundation against `master`. Do not rewrite
its published source history or merge the artifact-only orphan branches.
Create stacked draft PR checkpoints with explicit bases:

1. #16: this provenance, scope and execution record, based on #15.
2. #10 / #21: bounded managed startup/readiness, diagnostics and capture facts.
3. #17 / #18: live state, safe controls and confirmed-transition notifications.
4. #19: unified app/plugin installation and actual Decky protocol recovery.
5. #20: maintained updater, trusted version discovery and update UI.
6. #22: final integration repairs, packaging, documentation and qualification.

Each PR describes its own final behavior, relevant evidence and remaining
acceptance. The stack is a review mechanism, not a new hard dependency on the
broader API/CLI/governance/v1/StreamGod backlog. Small integration repairs can
land on the appropriate later draft without relabeling older receipts.

## Qualification and preservation

Use the tools pinned in [the build guide](steam-deck-building.md): Go 1.27.4,
Node 24.19.0, npm 11.9.0, Python 3.12+ and Playwright 1.62.0. Keep Go/Node/npm
development tools out of the end-user installation.

Preserve CLI/offline operation, explicit broadcast authorization, authenticated
local control, private credentials and redacted logs, isolated OBS profiles,
nonblank output gates, safe cancellation, existing settings/media/history,
unrelated plugins, deterministic packages and safe recovery. Stock OBS needs a
graphical rendering context; hidden/background operation does not imply a true
headless OBS build. OBS 28+ bundles obs-websocket; verify the installed component
and generated authentication rather than installing a duplicate blindly.

Run relevant tests during each change. At the final exact source revision run
the full applicable Go/race/vet/vulnerability, Python installer/backend,
TypeScript/Node/build/audit, actual-package browser, repeated package and native
OBS recording/local-RTMP/failure matrix. Record exact commands, versions, source
and artifact hashes, and passed/failed/skipped/unavailable/unrun outcomes.
Cross-builds are compilation evidence, not executed platform qualification.

Real SteamOS/Flatpak/Gamescope/VAAPI/audio/controller/session behavior and a Kick
viewer receiving picture and sound remain required device evidence. No-game
capture is a Roadmap 1 criterion; an unavailable/blank platform feed remains a
blocker rather than being silently deferred to the Roadmap 2 custom banner.
No cloud fixture or published preview substitutes for that evidence. Missing
required device/CI/review evidence prevents closure. Prepare a concrete candidate
and instructions; publication is a separate reviewed action.
