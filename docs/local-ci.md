# Local GitHub Actions validation

## Useful local confidence while hosted billing is unavailable

The owner cannot fund hosted Actions. Billing does not prevent standalone local
tests, builds, security scans, package checks or actual Steam Deck observations.
Use those results, pinned to the final source, for the concrete release decision
while identifying any unavailable hosted/platform/service checks separately.
Required branch protections still apply; no standalone check is a hosted pass.

The 2026-11-22 metadata-only constrained preflight at exact source `f4561aa`
needed 7,544,361,132 root/Docker bytes and observed 3,110,805,504: a shortfall of
4,433,555,628 bytes (about 4.1 GiB). Separate scratch passed its budget. Docker
works with the cached runner, but all six ACT jobs/probe remained unrun; no
images/caches were deleted. A capable free workspace can run the maintained
matrix without changing its checks. This is a dated measurement, not a promise
of current capacity or a passing final-source run.

For a constrained machine, run the existing Go/race/vet/static/security, Python,
frontend, generator, package and browser commands directly where their actual
requirements are available; see [building](steam-deck-building.md). Set PATH to
the pinned toolchain first: in this Cloud workspace bare `/usr/bin/go` is not
the project Go tool. Keep compiler/temp output in private suitable directories
and preserve current package/network presets. Record each command's real result.
Native OBS containers still need enough Docker storage; do not bypass the
preflight or relabel their absence. Actual Graph/advisory review and real Deck/
provider evidence remain distinct tasks in [finalization](finalization-checklist.md).

## Maintained ACT route

Issue #61 uses the existing workflows with act 0.2.97, not a substitute workflow
that silently omits checks. Linux containers do not emulate native macOS,
Windows, Steam Deck/Flatpak/Gamescope, controller/AMD hardware, hosted GitHub
services or a real provider viewer.

The standalone client pin was selected after inspecting Realm PR #64 at
`11a56cec78e437f26a2d25cdd48dfa79b92765b4` and Reflector PR #266 at
`90c8bc984b9b9ccac493bf1f58a90ee595eaf187` as read-only references. They are draft
candidates, not installed dependencies or published prerequisites. This
repository's launcher is independently maintained. Its Linux amd64 act archive
SHA256 is `67b4976a56f33ea7870b798912e738ec44eef38e7578ae7b532f2def1c73a5ad`;
arm64 is pinned in the script. The published checksum was verified before local
installation. The Ubuntu 24.04 runner is digest-pinned in `.actrc`, including
both upstream amd64 and arm64 variants.

## Organization conventions and retained reports

The repository follows the current Ego Hygiene structured-output convention:
`.actrc` enables `--json`, cleanup and the existing digest-pinned Ubuntu24 runner.
The project launcher continues to select explicit state/cache/action-source paths,
Docker socket, bridge-reachable artifact service and inherited CA/proxy trust.
Those runtime bindings are necessary for nested native tests in Cloud.

Read-only references inspected for this alignment:

- [egohygiene/egohygiene `.actrc`](https://github.com/egohygiene/egohygiene/blob/060d15a790db9329cb226ecef1f0ae4112a11f3c/.actrc), source `060d15a790db9329cb226ecef1f0ae4112a11f3c`, file SHA256 `fdb2974b919c31d93578d19caef847362f8a290cf08c910eb8f1a6d6f78664f8`.
- [egohygiene/reflector `.actrc`](https://github.com/egohygiene/reflector/blob/23f164cf898e092b62bbdddaf7616c4823208f9b/.actrc), source `23f164cf898e092b62bbdddaf7616c4823208f9b`, file SHA256 `b30f5abf09400884f7d0b41cb8e7b1b16251cf012e67299c41e210a743d1273e`.

The root organization example also shows repository-relative action/cache paths
and a moving runner tag. Reflector uses the exact reviewed digest retained here.
The launcher provides the portable directory/cache intent through `--state` and
explicit flags; it does not replace pinned tools or clear existing settings.
No other repository or user-level `.actrc` is modified.

The [2026-11-13 audit](../audits/local-act-2026-11-13.md) retains two complete
local sequences and reports at exact source cf12abe6. It also demonstrates
[#68](https://github.com/szmyty/obsgod/issues/68): ACT can create root-owned
generated frontend output that blocks a later normal-user build. The repair uses
`scripts/frontend-command.py` for workflow checks and nested package builds.
Qualification includes ACT followed by normal-user typecheck/test/build with
both absent and reused generated output. Keep that development postcondition
separate from passing workflow jobs; never repair it by recursively changing
checkout ownership or disabling production root guards.

Keep logs private while running jobs. Build a consolidated report for one exact
source revision after execution:

```sh
python3 scripts/local-ci-report.py \
  --state /absolute/private/local-ci-state \
  --revision FULL_40_CHARACTER_SOURCE_SHA \
  --output /absolute/private/local-ci-report
```

The report command verifies each receipt/log digest before summarizing results,
reads structured ACT messages and legacy text, and writes `report.json` plus
`report.md`. It preserves raw exit outcomes, source/configuration pins, command/
event/matrix context, observed test results, attempts and explicit missing-platform
or provider evidence. A failed integrity check is not converted into a passing
workflow report. `local_result` covers the six supported jobs; `overall_result`
remains partial while separate provider/platform/target gates are open. Exit0
means verified clean local-job completion, not full hosted/device acceptance. A different revision's receipt cannot qualify the selected one.

Failed runs are grouped into actionable findings with their evidence and failed
step. Diagnostic error text from successful negative-control tests does not become
a new defect. Reports do not create GitHub issues, contact services or publish
artifacts. Review and sanitize logs before sharing; no generic filter establishes
that all third-party text is safe. The maintainer then checks the live issue graph:
link existing #46 blockers, and create a focused issue only for a new actionable
finding, with exact reproduction, expected/observed behavior and acceptance.
#51 remains independent monetization/Store research. Local reports do not qualify
actual Steam Deck/hosted CI/provider-viewer/adoption or authorize release/deploy.

## Setup and explicit entry points

Run from a checked-out repository with Python 3.12, a working local Docker socket,
adequate free disk (the runner, native fixture images and archives are large),
and the current cloud proxy/combined CA intact:

```sh
python3 scripts/local-ci.py install
docker pull ghcr.io/catthehacker/ubuntu:act-24.04@sha256:19619a010b204f44c5340bff7d39b68551109fe6a56a53f75201ea91e05d4270
python3 scripts/local-ci.py prepare-actions
python3 scripts/local-ci.py list
python3 scripts/local-ci.py dry-run
python3 scripts/local-ci.py build
python3 scripts/local-ci.py coverage
python3 scripts/local-ci.py lint
python3 scripts/local-ci.py snapshot
python3 scripts/local-ci.py docs
python3 scripts/local-ci.py candidate
```

For an existing user-owned client, add `--act /absolute/path/to/act`; the launcher
verifies its exact version. `--state /absolute/private/path` relocates caches and
evidence (default ignored `.local-ci/`). The installer only writes to its
user-owned tool prefix. It verifies the archive hash before writing the binary;
it does not modify shell profiles, system packages, network policy, Docker
configuration, account billing or a remote repository.

Project `.actrc` contains only reviewed image, pull and cleanup defaults. act may
also read its user-level configuration; inspect that file when behavior differs.
Explicit launcher flags take precedence for workspace/socket/CA/cache/evidence
paths. It disables implicit `.env`, `.secrets` and `.input` files. Tokens are not
copied from the host. The launcher binds the actual checkout at its absolute path
so nested Docker mounts can see the same files on the managed daemon. It always
selects that local socket, retains existing registry/proxy settings, supplies a
read-only trusted CA mount and resolves the existing proxy hostname in the inner
container. TLS verification remains enabled; the bridge network is retained.
The artifact/cache service uses the host's discovered bridge-reachable interface
address for both binding and advertisement. Only that exact local address is
appended to both existing no-proxy lists, preserving every existing entry. The
receipt records the address. Action-generated GitHub artifact URLs are synthetic
under act; verify the locally retained bytes rather than treating those links as
hosted GitHub delivery.
The shared state `tmp` directory is mounted at the same absolute path on both
sides, and `TMPDIR`/`OBSGOD_ACT_TEMP` select it for nested-Docker inputs/outputs.
This avoids treating act's container-only `/tmp` as a daemon-visible host path.
Go test and tooling-unit-test steps explicitly set
`TMPDIR: ${{ runner.temp }}` instead. ACT executes
these checks as root, whereas the shared workspace ancestry belongs to the checkout user;
production storage guards correctly reject that foreign ownership. Runner-local
temporary directories give fixtures the actual test process's trusted owner.
The override is limited to Go checks in build/coverage/candidate and the
candidate installer/backend/panel checks;
native builders and nested Docker inputs keep the daemon-visible shared path.
Normal-user host tests remain separate evidence of the production user context.
Native builders receive the existing proxy build arguments by name and the
mounted combined CA as a BuildKit secret; credentials are not copied into images.
APT receives only a read-only `Acquire::https::CaInfo` snippet pointing at the
same combined bundle. The snippet/hash are recorded in the receipt. Preset
repositories, proxies, registries and TLS verification remain intact; package
post-install scripts can still update the ordinary OS certificate bundle.

act starts actions and dependency installation as root. Production installers
correctly refuse root, so `scripts/run-user-tests.py` runs installer/unit/browser
fixtures with the checkout owner's actual non-root UID/GID (or the unprivileged
65534 fallback), cleared supplementary groups when dropping root, and a private
owned temporary HOME/TMPDIR. It never changes checkout ownership or disables
production guards. Hosted non-root runners keep their identity. Browser binaries
use the shared readable `PLAYWRIGHT_BROWSERS_PATH`; screenshot/site outputs go to
an explicitly owned evidence directory outside the checkout and are retained by
the artifact step. Frontend typecheck/test/build also use the actual non-root
checkout owner through `scripts/frontend-command.py`, including the frontend
builds nested inside package-deck. That fixed-command helper uses private
HOME/TMPDIR and refuses a root-owned checkout, symlink/foreign directories or
unsafe existing frontend output. It never deletes output or changes checkout
ownership/permissions. Preserve incompatible old output before deliberate
recovery. Tool/dependency installation, Go/native package work, audits and native
containers retain their existing identities; no blanket checkout chown occurs.
The helper's private `/tmp/ogt-*` path stays short enough for Chromium's actual
Unix sockets. It does not replace the outer daemon-visible build TMPDIR or the
persistent browser cache/evidence paths.

The initial act setup-go clone failed because act's embedded go-git transport
could not consume the runtime's injected Git authentication. `prepare-actions`
therefore verifies each exact pinned commit using the working GitHub HTTPS API,
downloads the same commit's codeload archive and records its tree ID, archive
SHA256 and every file/link. Subsequent runs verify that cache and pass explicit
`--local-repository` mappings to act. This changes acquisition, not action code
or workflow steps. Source cache receipts remain with local evidence. No token is
invented, printed, stored in tracked files or substituted into Git configuration.

## Matrix and evidence boundaries

| Workflow/job | Local selection | Evidence still required |
| --- | --- | --- |
| build/build | Ubuntu 24.04, pinned Go, build/tests | Native macOS 15 and Windows 2025; Linux arm64 runtime if claimed |
| coverage/coverage | Go race/coverage profile + summary | Hosted artifact delivery and revision-to-revision review |
| lint/golangci | Full formatting/vet/staticcheck | Historical golangci-only-new mode is replaced, not a pass claim |
| lint/dependency-review | PR-only GitHub advisory comparison | Real base/head PR and hosted dependency graph/API; synthetic events cannot prove it |
| goreleaser/goreleaser | Pinned snapshot, publish/sign disabled | Native execution/support per produced target; owner publication/signing decisions |
| docs-preview/build-preview | Metadata/site/unit checks + local artifact service | Hosted artifact delivery; no deployment is performed |
| steam-deck/candidate | Go/Python/Node/security; two packages/audits; browser + native nested Docker | Actual Deck/OBS33/Flatpak/Gamescope/input/controller/audio/provider/performance and required hosted reviews/CI |

`lint --pull-request` runs the same static job under the reviewed synthetic PR
event fixture. Its base/head are placeholders, not a fabricated GitHub review.
The normal selected `-j golangci` does not execute the provider-only
`dependency-review` job. Account for that explicitly in the ledger. Native
platform jobs must run on their real platforms; do not map their labels to Linux.

Run jobs serially. Native OBS, transport and browser fixtures share resources
and must not race with another qualification process. Run the final retained
sequence again from the exact final clean source; dirty development runs prove
only the captured working tree. The launcher records HEAD/dirty/diff hash,
workflow hashes, image/client/action pins, command, exit code and reviewed-log
hash in timestamped JSON/log pairs. Logs remain private until reviewed; redacting
URL passwords is a precaution, not proof that arbitrary third-party output is
safe to publish. Never run with real stream keys, OBS passwords or private user
profiles.

The local artifact service retains outputs under the state path. An upload action
passing locally qualifies that local path only. If it fails, record the failing
step and retain independently verified output hashes; do not turn an upload
failure or skipped test into workflow success. Add a per-job ledger with revision,
event/matrix, result (**passed**, **failed**, **partial**, **unavailable**,
**not applicable**), counts, sanitized evidence and the smallest next action.
Keep first and final runs distinguishable. Direct repository commands are useful
fallback evidence when an act step is unavailable; label their source and limits.

## Constrained runner preflight and serial matrix (#104)

Use the supported profile when the local runner needs a bounded capacity check
and private compiler-cache policy. It requires an explicit absolute scratch
base outside the checkout, owned by the invoking user with mode0700. The local
Docker daemon must see that same path. Existing caches, tools, artifacts and
receipts are not relocated or pruned by this profile.

```sh
python3 scripts/local-ci.py preflight \
  --state /absolute/private/local-ci-state \
  --scratch /absolute/private/local-ci-scratch
python3 scripts/local-ci.py matrix \
  --act /absolute/path/to/act \
  --state /absolute/private/local-ci-state \
  --scratch /absolute/private/local-ci-scratch
```

Both commands select the constrained profile. A single existing job can opt in
with `--profile constrained --scratch /absolute/private/local-ci-scratch`.
Legacy single-job calls retain their existing behavior when no profile is given.
The current pinned runner image must already be cached; the probe uses
`--pull=never`, the managed local socket and no network. It verifies owner
read/write access across the actual Docker bind and measures host and daemon
filesystems. Metadata-only checks run before allocating even the cached probe.
The base requirements are **4GiB free for root/workspace** and **6GiB free for
scratch**, or **10GiB free** when shared. The VFS Docker driver additionally
reserves **twice the cached runner image Size** for its container-copy allocation;
the receipt records the actual driver, image size, allowance and combined budget.
An early shortage leaves the Docker probe and workflows unrun. Other drivers add
zero copy allowance and retain the actual allocation/read/write probe after host
checks pass. A refusal records required, available and missing bytes and exits3
before downloading actions or running a workflow. These conservative floors are
a preflight policy, not a promise that arbitrary future workloads fit. Required recording reserves and
all tests remain unchanged. A failed probe is unavailable evidence, not a pass.

`matrix` creates a new `state/sessions/<unique-id>` and a matching private
scratch session. Six jobs run serially: lint, build, coverage, snapshot, docs,
candidate. Every job has a fresh temp/cache tree; repeated settings tests cannot
reuse a previous evidence directory. The matrix stops on failure or capacity
refusal and records later members as unrun. Success requires six genuine
clean-source exit0 receipts, matching action/revision/tree and log hashes, and
unchanged source. It does not infer success from the child process exit alone.

Pass the printed session path, rather than the persistent state root, to the
existing report command. An interrupted session remains incomplete and is never
silently resumed or converted into completion; a retry gets its own session.
Old sessions, failed receipts and evidence remain intact. The report still
requires authentic completed checksums and retains its separate external gates.

Constrained Go jobs disable setup-go's automatic compiler-cache restoration.
Root workflow Go and the non-root primary builder use different named caches
under that job's private scratch directory. At an explicit workflow boundary
**after all Go consumers finish**, `scripts/local-ci-resources.py` runs the
pinned toolchain's `go clean -cache` for only those exact caches. It rejects
unexpected paths, links, mounts and active Go consumers, and records cache
bytes/hashes, disk availability, command and exit before/after. The workflow
receipt binds that policy receipt's hash. Module caches, source, toolchains,
release outputs, artifact-service data and evidence are retained. Docs has no
Go consumers and needs no compiler-cache cleanup. There is no global Docker
prune, host-cache mutation, paid runner or change to network/package presets.

The candidate invokes `scripts/qualify-decky-build.py` through the full primary
entry twice, as the actual non-root checkout owner. Its new daemon-visible
output contains private context, logs, both builds and `qualification.json`.
The original primary ZIP feeds packaged browser/settings tests. Compatibility
archives must contain identical plugin bytes; the audit staging uses the primary
ZIP, and native fixtures verify their Go/capture binaries match it. Ordinary
plugin installation gains no paired-application or root requirement.
