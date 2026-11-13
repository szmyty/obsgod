# Local GitHub Actions validation

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
the artifact step. Package builds/audits and native containers keep their own
existing execution identities.

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
