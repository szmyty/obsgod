# Reproduce the af7 review candidate

This review-only checkpoint contains the [standard plugin ZIP](obsgod-decky.zip), [SHA256SUMS](SHA256SUMS), [build receipt](build-receipt.json), [qualification summary](qualification-summary.json) and [reviewed public proof](aurora-af7-public-proof.zip). The commands below build/test exact source; they do not install on the Steam Deck or publish a release.

Source: `https://github.com/szmyty/obsgod`, exact commit **af7a20fdd0c62404e9b11d540fb605368e269380**, tree `d6149d9ec670cffcc30db355262aa688382b5e7e`. Candidate package **0.1.0-deck.9**. Primary ZIP SHA256 **4deece2bcaba6440c168d5cb7b1bc585e346d6b2f06655a1672c0d9638afeab8**, **4,570,728 bytes**. Source inventory contains 617 files. Matching bytes prove reproduction, not real Deck/provider acceptance.

## Host selection

Owner's actual OS/architecture remains **TBD**. The complete current local matrix uses a Linux machine, Docker's local Unix socket, native Linux fixture containers and user-owned source. Use a suitable free **Linux x86_64** machine/VM for the sequence below. Confirm Python 3.12+, Go 1.27.4, Node 24.19.0 and npm 11.9.0; retain package/proxy/CA presets. Current tool pins are in `docs/steam-deck-building.md` and source scripts. No unverified general curl installer is supplied here.

If the host is Windows, WSL2 with a supported Linux distribution and working Docker integration may supply that environment; keep source/state/scratch in the Linux filesystem and verify the actual local socket from WSL. Native Windows execution is a separate unrun gate. If the host is macOS, use a suitable Linux x86_64 VM/free Linux runner for this exact sequence; Docker Desktop alone does not turn macOS into the documented Linux host/socket. On Apple Silicon, do not relabel emulated x86_64 containers as native ARM acceptance. Do not assume Docker/WSL/VM is installed or buy anything.

The supported matrix preflight refused in Cloud: at measurement root 2,597,666,816 bytes available versus 7,544,361,132 required; shortage 4,946,694,316 bytes (~4.61GiB). Scratch 9,153,650,688 available versus 6,442,450,944 required. VFS reserves twice the cached pinned runner size. The budget is conservative, not a guaranteed peak. Use a fresh preflight; do not delete unrelated caches/receipts or weaken thresholds to obtain a pass.

## Inspect and acquire source

Use an existing clean isolated checkout if one already exists. Do not reset a working checkout or overwrite local changes. For a fresh clone only:

```bash
git clone https://github.com/szmyty/obsgod.git deckystream-af7-source
cd deckystream-af7-source
git checkout --detach af7a20fdd0c62404e9b11d540fb605368e269380
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain
id
uname -srm
python3 --version
go version
node --version
npm --version
docker version
docker info --format '{{json .Driver}}'
```

Expected clean status; owner must be non-root. Stop and diagnose a tool/socket/version failure; do not change permissions/ownership recursively or map non-Linux runner labels to Linux. No secret environment dumps are needed.

## Complete supported six-job local matrix

Run serially from that exact source. Use a private new state/scratch under the invoking user's home, outside the checkout. Docker must see the scratch at the same absolute path. Commands use actual repository options; `install` installs only the pinned ACT client into its user prefix, not OBS or system packages.

```bash
umask 077
deckystream_check_root=$(mktemp -d "$HOME/deckystream-af7-checks.XXXXXX")
mkdir -m 700 "$deckystream_check_root/state" "$deckystream_check_root/scratch"
python3 scripts/local-ci.py install
docker pull ghcr.io/catthehacker/ubuntu:act-24.04@sha256:19619a010b204f44c5340bff7d39b68551109fe6a56a53f75201ea91e05d4270
python3 scripts/local-ci.py preflight \
  --state "$deckystream_check_root/state" \
  --scratch "$deckystream_check_root/scratch"
```

Continue only if preflight succeeds:

```bash
python3 scripts/local-ci.py prepare-actions --state "$deckystream_check_root/state"
python3 scripts/local-ci.py list --state "$deckystream_check_root/state"
python3 scripts/local-ci.py dry-run --state "$deckystream_check_root/state"
python3 scripts/local-ci.py matrix \
  --state "$deckystream_check_root/state" \
  --scratch "$deckystream_check_root/scratch"
```

This runs **lint, build, coverage, snapshot, docs, candidate** serially. Keep its new session path and actual exit code; a refusal is unavailable and later jobs remain unrun. An interruption/failure is not resumed as success. Do not run native fixtures concurrently. The launcher preserves network/package trust and caches, keeps tokens out of ACT, and disables implicit secret files. Raw logs stay private.

After the matrix attempt, this fresh private state must contain exactly one session. Read that actual path, then generate the integrity-checked report:

```bash
deckystream_session=$(python3 - "$deckystream_check_root/state/sessions" <<'PY'
import pathlib,sys
sessions=[p for p in pathlib.Path(sys.argv[1]).iterdir() if p.is_dir()]
assert len(sessions)==1, 'Use the actual session printed by this matrix attempt; do not guess'
print(sessions[0].resolve())
PY
)
python3 scripts/local-ci-report.py \
  --state "$deckystream_session" \
  --revision af7a20fdd0c62404e9b11d540fb605368e269380 \
  --output "$deckystream_check_root/report"
```

The report verifies actual receipts/log hashes; preserve its real exit and any incomplete/refused disposition. Six local exit0 workflow receipts do not prove hosted GitHub service/native macOS/Windows/Steam Deck/provider/adoption. If an early preflight refused and no matrix session exists, keep that refusal; do not invent a report session.

## Direct primary reproduction

After the pinned development dependencies are available (`go mod download` and `npm --prefix steamdeck/decky ci --ignore-scripts`), the maintained primary helper builds the complete source twice without replacing frontend output or installing anything:

```bash
umask 077
deckystream_primary_root=$(mktemp -d "$HOME/deckystream-af7-primary.XXXXXX")
python3 scripts/qualify-decky-build.py \
  --revision af7a20fdd0c62404e9b11d540fb605368e269380 \
  --output "$deckystream_primary_root/primary"
```

Accept only a passed `qualification.json` for exact clean source/tools and its `second/obsgod-decky.zip`. Compare SHA256 to the exact 4deece2… above and preserve both complete logs/receipts. The two original primary builds did not invoke optional official CLI verification. A separate af7 check then passed all33 prepared payload files with the unmodified official0.0.7 CLI and pinned default builder, network disabled. That check assembles already compiled bytes; it does not perform source compilation or prove raw CLI ZIP reproducibility. To repeat it, `--verify-cli` requires the separately verified official0.0.7 executable, documented in the [source package guide](https://github.com/szmyty/obsgod/tree/af7a20fdd0c62404e9b11d540fb605368e269380/docs/decky-package.md).

For raw downloaded ZIP integrity, using Python3 on a host with the ZIP in the current directory:

```bash
python3 - <<'PY'
import hashlib,json,pathlib,zipfile
p=pathlib.Path('obsgod-decky.zip')
assert p.stat().st_size == 4570728
assert hashlib.sha256(p.read_bytes()).hexdigest() == '4deece2bcaba6440c168d5cb7b1bc585e346d6b2f06655a1672c0d9638afeab8'
with zipfile.ZipFile(p) as z:
    m=json.loads(z.read('obsgod/manifest.json'))
assert m['revision'] == 'af7a20fdd0c62404e9b11d540fb605368e269380'
assert m['dirty'] is False
assert m['version'] == '0.1.0-deck.9'
assert m['format'] == 'decky-plugin'
assert m['platform'] == 'linux/amd64'
print('Verified exact af7 ZIP; no package member was executed')
PY
```

## Record and preserve evidence

Retain exact source/tree, host OS/arch, Docker storage/image pins, tools, commands, exit outcomes, counts, hashes, capacity receipts, artifacts and failures. Distinguish **passed/failed/skipped/unavailable/unrun**. Review raw logs for credentials/private data before sharing. The current exact head's hosted 10 runs/16 jobs had 15 billing refusals, 1 push-only dependency-review skip and 0 steps; no non-billing executed source failure was found. No workflow retry is needed to rediscover that account block.

The artifact branch is a review checkpoint, not a release/tag, deployment, updater offer or supported-device claim. Existing historical469 installation URLs/hashes remain unchanged. Later source changes require affected checks rerun. Owner-machine/actual Deck tests, real supported-loader lifecycle, provider viewer, required CI/reviews/rights and final independent/new-user adoption remain explicit gates.

The exact public main receipt inside the proof is `standalone/available-checks.json`, SHA256 `9cc1a2f369fa7fa2be3e54056cb4dd7b9ea0fafdd25c3d559b8b965aa7061e59`; original and public bytes are identical, with zero additional redactions. The separate `qualification-summary.json` SHA256 is `ea422d3d2d0dde4ecd822706f4a9fddbccdd1a0b01084ee7f585dcfd3276d45a`; only its metadata path alias was corrected. Canonical source, main receipt and ZIP bytes were not changed by that metadata correction. See [OWNER-TESTS.md](OWNER-TESTS.md) for actual owner-machine/Deck acceptance.
