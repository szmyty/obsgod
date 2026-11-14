# Generic Linux packages

NFPM `.deb`, `.rpm` and `.apk` packages contain the generic static Go CLI, not
the paired Steam Deck runtime. They do not install OBS, Decky, capture libraries,
services or provider integrations. Installing a package never broadcasts.

The existing source-clean, non-publishing GoReleaser snapshot now includes
`/usr/bin/obsgod` and seven files under `/usr/share/doc/obsgod`: project LICENSE,
README, CHANGELOG, complete Go notices, selected-module catalog, generic CLI
guide and `SOURCE.json`. The latter binds the application revision and immutable
preferred-source URL; module source checksums and full licenses stay in the
notice catalog. No separately linked native or Decky source is redistributed in
these packages. This is separate from the Deck runtime's source obligations.

Package readers use the Python standard library. They inspect bounded Debian ar
and gzip/tar, RPM headers and gzip/cpio, and APK gzip/tar streams without
extracting or executing a payload. Exact paths, root ownership, normal modes,
metadata architecture/version, internal digests, source/notices, binary VCS
metadata and linked modules are checked. Unexpected scripts, hooks, triggers,
links, devices, capabilities, privileged modes, duplicate/traversal paths and
oversized expansion fail closed. RPM buildhost and package mtime are fixed for
reproducibility, not claims about an authenticated builder.

## Complete static matrix

From clean committed source and the pinned tools:

```sh
goreleaser release --snapshot --skip=publish,sign --clean
python3 scripts/nfpm-release.py audit --revision "$(git rev-parse HEAD)" \
  --artifacts dist/snapshot --output dist/snapshot/nfpm-supply-chain
```

The full audit requires all 15 packages: five existing Linux architectures times
three formats. Artifact-specific SPDX 2.3 and unsigned provenance, exact payload
hashes, selected source and explicit limitations are retained in `SUMMARY.json`
and `AUDIT-SHA256SUMS`. Running the audit twice must give identical bytes.
The original 20 tar/zip audit remains separate and unchanged in scope.

For a focused development check, use a **new output directory** rather than
cleaning or overwriting previous artifacts:

```sh
python3 scripts/nfpm-release.py focused --goreleaser /path/to/pinned/goreleaser \
  --output /absolute/new/nfpm-focused
python3 scripts/nfpm-release.py audit --revision "$(git rev-parse HEAD)" \
  --target linux-amd64 --artifacts /absolute/new/nfpm-focused \
  --output /absolute/new/nfpm-focused-audit
```

This derives the existing configuration with only the output path, selected
Linux amd64 target and private notice-staging paths changed. Existing ignored
catalogs from root-owned ACT runs are preserved without chown or deletion.
Package documentation has explicit 0644 modes and commit-time mtimes, independent
of the invoking process's umask. It still uses the real GoReleaser/NFPM package path,
clean VCS metadata and source-bound documentation. A focused three-package pass
is not the complete 15-package matrix or final qualification.

## Disposable package-manager execution

The workflow explicitly pulls digest-pinned Debian, Fedora and Alpine images,
then disables container networking. The smoke helper refuses mutable image tags
and package hashes/payloads that differ from the selected successful audit:

```sh
python3 scripts/nfpm-release.py smoke --artifacts /absolute/nfpm-artifacts \
  --audit /absolute/nfpm-audit/SUMMARY.json --output /absolute/new/smoke-results
```

It installs through each actual package manager, checks every installed file,
executes version/help/config-path/API-capabilities as UID/GID65534, repeats the
installation and removes/purges the package. Temporary settings/media sentinels
must survive. Only a disposable container's filesystem changes; packages are
mounted read-only and ordinary host installations/configuration are untouched.
The installed CLI is trusted selected-source code: do not execute arbitrary
downloads merely because an untrusted sidecar calls them safe.

For cross-revision replacement/upgrade, add `--previous-audit` with an independently
successful older NFPM audit, and copy its selected package files beside the current
packages before smoke. Both source revisions/hashes remain in the receipt.
No supplied older audit means that path is explicitly **unrun**; reinstalling the
same version must not be described as a cross-version upgrade. Snapshot Git-SHA
versions are not chronological; the receipt records replacement and the actual
package-manager commands rather than assuming an upward version ordering.

The retained `linux-package-smoke.json` is Linux amd64 package lifecycle and
offline CLI evidence only. Native ARM/386, actual OBS/Steam Deck, other operating
systems, hosted CI, publisher authentication, stable release claims and release
approval retain their original independent gates. The final full matrix is run
after source/artwork freeze, as requested by the owner.
