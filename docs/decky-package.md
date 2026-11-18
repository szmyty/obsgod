# Standard Decky package

The primary install unit is **`obsgod-decky.zip`**. It is one ordinary Decky
plugin, with the current compatible `obsgod` folder/package identity and `OBSGod`
plugin name. No repository migration, Store submission or release publication
is performed by the build. `deckystream` is the planned future repository name,
not the current update destination.

The ZIP contains the panel, Python backend and its sibling modules, the Go CLI
in `bin/obsgod`, native capture library, optional local browser setup and its
assets, notices, and the LGPL SDK's separate runtime module and preferred source.
OBS Studio and the matching GStreamer extension remain separately installed,
user-scoped Flatpaks. They are not embedded in the ZIP. Running the plugin needs
neither a root/debug plugin flag nor an unlocked SteamOS system partition.
The user starts a local test or broadcast explicitly; installing is not consent
to stream.

## Source build

Use [the supported development setup](steam-deck-building.md): Go **1.27.4**,
Node **24.19.0**, npm **11.9.0**, Python **3.12+**, the committed npm lockfile,
and Docker for the existing pinned native-capture builder. Run the primary
package build as the non-root checkout owner, including when using act. The
maintained repeat helper below drops an ACT root process to that owner while
retaining a daemon-visible private build context. Preserve configured
package registries, proxy settings and certificate bundles. The system `go`
command must actually be the pinned Go compiler. The tools are build requirements,
not packages Steam Deck users must install.

From a clean checkout, after installing the documented development dependencies:

```sh
python3 scripts/package-decky.py --version 0.1.0-deck.9 \
  --output "$PWD/dist/decky-candidate-1"
```

Create the existing parent directory first if necessary. The output argument is
an absolute **new directory**, under a directory owned by the build user. The
builder refuses existing output paths, links and traversal; it never removes an
old candidate. Output ancestors must be owned by the build user or root and
protected against replacement by other users; writable shared ancestors require
the sticky bit (as on `/tmp`). The build compiles into private temporary directories without
replacing the checkout's frontend output. `--allow-dirty` is only for unqualified
development builds and marks the manifest/receipt as dirty. A different source
revision cannot be supplied to relabel the checkout.

The outputs are the directly installable ZIP, `SHA256SUMS`, and a
`build-receipt.json` containing the revision, dirty status, actual tool pins,
archive hash, platform and explicit unrun device checks. `manifest.json` inside
the ZIP records every payload file's checksum. Repeating from identical source,
tools and native builder must produce identical canonical ZIP bytes. Build
receipts that include an optional raw CLI ZIP hash may differ, as described below.

For maintained primary-build qualification, invoke the complete primary entry
point twice through the owner wrapper:

```sh
candidate_parent=$(mktemp -d)
python3 scripts/qualify-decky-build.py --revision "$(git rev-parse HEAD)" \
  --output "$candidate_parent/primary"
```

The existing parent must belong to the checkout owner and be protected against
other users replacing its contents; an ordinary 0755 runner temp parent is
accepted. The new output and its context/cache directories remain private 0700.
Output must be new and outside the checkout. Inside ACT, use the launcher's owned,
daemon-visible attempt directory instead of a container-only `/tmp` path. The
helper gives both builds a private HOME and TMPDIR under that output. Its root
wrapper drops supplementary groups and adds only the existing local Docker
socket group before running the entire qualification as the checkout owner.
It never changes checkout or socket permissions or bypasses the primary root
guard. The short browser-fixture `run-user-tests.py` context remains separate.

`qualification.json` records each complete primary command, private log hash,
source/tool/manifest checks and literal canonical ZIP comparison. Only a passed
receipt exposes `second/obsgod-decky.zip` as the accepted artifact; any primary
entry failure fails the helper before a later candidate is accepted. Existing
outputs remain intact. The optional `--verify-cli` argument forwards the pinned
assembly check to each primary build, with the same limits described below.

For the supported local scratch profile, compiler and module caches use separate
owner-private `go-build-user-UID` and `go-mod-user-UID` directories under
`OBSGOD_LOCAL_SCRATCH`; otherwise they stay under the private output context.
Module caches, package/proxy/CA presets and prior artifacts are preserved. This
helper deletes no cache. Any opted-in compiler-cache cleanup belongs to the
documented local-CI policy after its consumers finish. Keep context/cache trees
and raw logs private; select the ZIP and reviewed receipts explicitly when
sharing artifacts. Passing local primary assembly does not establish device,
provider, hosted CI or publication acceptance.

The older `scripts/package-deck.py` remains a compatibility builder for the
paired Desktop archive/updater and their existing checks. It uses the same
complete plugin payload. A separate Desktop archive is no longer required to
obtain our plugin's browser setup files. Decky-managed replacement and removal
are the primary plugin lifecycle; a legacy installer is not an additional
requirement for the standard ZIP.

## Official Decky CLI verification

The supported source entry point above prepares a conventional plugin root;
the [official CLI 0.0.7](https://github.com/SteamDeckHomebrew/cli/tree/0.0.7)
can additionally assemble that root and verify its complete packaged payload.
The architecture follows the [current official template](https://github.com/SteamDeckHomebrew/decky-plugin-template/tree/90d0780e882a17f5714fc6de044c645f22608290):
root manifests/Python modules, `dist/`, bundled runtime `bin/`, and extra
license/source/assets carried through the CLI's flattened `defaults/` mechanism.
The project keeps its nested source tree instead of moving the whole repository.

For this optional check, download the official Linux x86-64 CLI asset explicitly:

```text
https://github.com/SteamDeckHomebrew/cli/releases/download/0.0.7/decky-linux-x86_64
SHA256: 0d0f8c127cd3dba12b75f771c786194ca9f4f771b4787ae24de8b1af45af4294
```

The hash is our recorded pin of the downloaded official release asset, not an
upstream signature or independent publisher attestation. The build verifies it
before execution. It does not automatically fetch or install a CLI binary.

```sh
python3 scripts/package-decky.py --version 0.1.0-deck.9 \
  --output "$PWD/dist/decky-candidate-cli" \
  --verify-cli /absolute/path/to/decky-0.0.7
```

The unmodified CLI is invoked as:

```text
decky-0.0.7 plugin build --output-path <private>/official \
  --tmp-output-path <private>/cli-tmp \
  --output-filename-source directory <private>/obsgod
```

CLI 0.0.7 hardcodes `ghcr.io/steamdeckhomebrew/builder:latest`. The helper's
temporary, bounded Docker adapter substitutes **only that image invocation**
with the pinned inspected image:

```text
ghcr.io/steamdeckhomebrew/builder@sha256:e2616e391f3ae9a46c4cf906b1091220c2506e7fb1301e16a2a72409efbce7c5
```

It runs the container as the ordinary build user, with container networking
disabled, and never retags the daemon's images. This builder contains Node
26.12.1/pnpm 12.14.0. It validates and assembles **already compiled payload
bytes** with an empty dependency lockfile; it does not replace the authoritative
Node 24/npm 11 source compilation or perform a second dependency installation.
The archive's small `build/verify.mjs` and pnpm lockfile describe this prepared
payload check. They are not a standalone source checkout/build system.

The default builder excludes nested `src/` directories when copying its output.
To preserve the SDK's complete, untouched preferred source through that default
flow, `source/decky-api/SOURCE.tar.gz` contains its original `package.json` and
`src/` tree. Extraction/rebuild instructions accompany it. No custom container
entrypoint, patched CLI or modified SDK source is needed.

The helper compares every unpacked official ZIP file and byte against the
canonical package, rejects duplicate or unexpected paths, and records the
outcome. CLI raw ZIPs use current timestamps and are **not** claimed reproducible.
Our canonical ZIP fixes ordering, timestamps, permissions and compression;
repeatability concerns that ZIP. CLI chmods its bind roots, so it is only given
private disposable staging directories, never the checkout or output directory.

## Native and license boundaries

The Go CLI is a static Linux amd64 executable for SteamOS. The GStreamer capture
`.so` is consumed **inside the OBS Flatpak**, so its existing separately pinned
Debian ABI build and receipt are retained. It is not rebuilt with the CLI's
frontend image or assumed compatible merely because the host executable runs.
`CAPTURE-SOURCE.tar.gz`, SDK notices and full applicable licenses accompany it.

`dist/decky-api.js` stays a separate, replaceable LGPL-2.1 module with its
TypeScript preferred source in `source/decky-api/`. Custom Rollup preserves this
boundary and Steam's supplied React/Decky UI globals. Tool/template alignment is
not permission to inline the LGPL module into the application bundle.

## Installation and remaining qualification

An approved test ZIP can be installed using Decky's own plugin installation
interface. Decky owns replacement of the plugin folder. Manual ZIP installation
is a development/sideload route, not a claim that the plugin has a Store listing.
The existing trusted release path remains `szmyty/obsgod`; builds do not publish
or redirect updates. These scripts have no publication or deployment side effects.

Build/schema/CLI equality and unpacked backend checks do not prove installation,
OBS startup, capture/audio, suspend/resume, or streaming behavior on a Steam Deck.
The current revision still needs the campaign's full matrix and owner device
checks before acceptance. Missing device/platform/CI/review evidence remains a
closure gate, and a local dirty build is never a release qualification receipt.
