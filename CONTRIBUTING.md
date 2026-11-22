# Contributing

Start with the [README](README.md) and choose the area below. Documentation fixes,
reproducible bugs, tests and bounded code changes are useful contributions. Search
existing issues before opening a duplicate; explain the problem and expected
behavior in a pull request. An issue is not a prerequisite for a small fix.

## Find the right starting point

| Area | Read first | Source and tests |
| --- | --- | --- |
| Documentation | [User guide](docs/steam-deck.md), [help](SUPPORT.md), and the guide you are changing | Root `*.md`, `docs/`; the offline website lives in `site/` |
| CLI and reusable OBS control | [CLI usage](docs/cli-usage.md), [configuration](docs/configuration.md), [architecture](ARCHITECTURE.md) | `main.go`, `internal/commands`, `internal/config`, `internal/obs`, `pkg/api/v1`, `pkg/automation`; Go tests sit beside source |
| Steam Deck / Decky | [Building](docs/steam-deck-building.md), [standard package](docs/decky-package.md), and the relevant feature guide | `internal/deck`, `steamdeck/decky/main.py` and sibling Python modules, `steamdeck/decky/src`; tests in `steamdeck/tests` and `steamdeck/decky/tests` |

The generic CLI remains supported independently of the managed Deck integration.
The command/package/storage names remain `obsgod` / `OBSGod`; the source preview
uses the selected aurora artwork and `deckystream` display name. A documentation
or display-name change does not migrate installations or update destinations.

Before behavior changes, read [repository instructions](AGENTS.md),
[architecture](ARCHITECTURE.md) and applicable security/feature guides. Use
[roadmap](ROADMAP.md) for scope and [continuity](CONTINUITY.md) when picking up
active work. Preserve v0 compatibility, user-owned/offline operation, explicit
broadcast approval, recovery, safe paths, deterministic outputs and secret
filtering. Generic OBS control stays in the reusable layer; Deck/provider/UI
behavior belongs above it. Explain substantial contract or safety changes in the
proposal or pull request. Do not introduce an organization, wallet, publisher identity or
permissions that the owner has not supplied.

## Set up and check your change

Use the pinned tools and supported commands in
[Steam Deck building](docs/steam-deck-building.md): Go **1.27.4**, Node
**24.19.0**, npm **11.9.0**, Python **3.12+**, and staticcheck **0.8.2** for Go
linting. Install only the tools relevant to your change; a documentation fix does
not require building a plugin, and the CLI does not require the Decky frontend.
Preserve the committed lockfiles and configured package/proxy/certificate setup.

- **Documentation and templates:** run `git diff --check`, inspect rendered
  Markdown and verify changed links. Parse changed YAML forms and check their
  field IDs, required fields and credential warnings. For website changes, use
  `python3 scripts/build-site.py`, `python3 scripts/build-site.py --check` and
  `python3 -B site/tests/test_build.py`.
- **Go / CLI:** run `go mod download`, format changed Go files with `gofmt`, then
  run `go test -race ./...`, `go vet ./...` and `staticcheck ./...`. Install the
  pinned linter with `go install honnef.co/go/tools/cmd/staticcheck@v0.8.2` if
  needed. `go run . --help` and `go run . version --json` are offline entry checks.
- **Decky frontend:** run `npm --prefix steamdeck/decky ci --ignore-scripts`,
  `npm --prefix steamdeck/decky run typecheck`, `npm --prefix steamdeck/decky test`
  and `npm --prefix steamdeck/decky run build` as the non-root checkout owner.
- **Deck backend / Python:** run
  `python3 -m unittest discover -s steamdeck/tests -p 'test_*.py' -v`; changes to
  packaging/scripts also use
  `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`.

Use focused checks while implementing. Runtime/package candidates need the full
applicable matrix in the building guide at the final source revision, including
browser/native checks where relevant. [Local CI](docs/local-ci.md) runs the
existing workflows with a checksum-pinned act client; local/mock/cross-build
results do not prove hosted CI, real Steam Deck or provider-viewer acceptance.
Security fixes need credential-redaction/cancellation/path tests where relevant.
Use fixture credentials; do not broadcast tests to a real service.

## Send a reviewable contribution

Keep changes bounded. Explain the trigger, resulting behavior and compatibility
effects. Provide relevant commands, source revision/dirty state, platform,
outcomes and limitations; distinguish passed, failed, skipped, unavailable and
unrun checks. For documentation-only changes, say so and record the lightweight
checks. Old receipts do not qualify new source, and a PR merge alone does not
satisfy an issue's acceptance criteria. Keep unmet criteria and their next action
visible. Update canonical guides when contracts change; update continuation
notes when handing off active work. Proposed ADRs remain proposed until accepted.

Release automation creates review artifacts and non-publishing snapshots only.
See [release engineering](docs/release-engineering.md) before changing packaging,
licensing, preferred source, checksums, update or publishing behavior. Publication,
deployment, another repository change, paid resources and owner identity/rights
decisions require owner authorization. Do all independent preparation first.

Report product problems through [support](SUPPORT.md), and security problems
through [security](SECURITY.md). Choose the Steam Deck bug, CLI/automation bug or
feature-request form as appropriate. Review diagnostics before sharing; never
post stream keys, OBS passwords, private setup links, raw private profiles/logs
or wipe-recovery archives. No payment, donation or streaming-provider account is
required to contribute. Contributions retain their applicable source and
dependency licenses; preserve attribution and preferred-source material.
