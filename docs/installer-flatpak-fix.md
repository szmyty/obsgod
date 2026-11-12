# Flatpak OBS version detection repair

The first Roadmap 1 device installation stopped after confirming Decky readiness:
the installer reported OBS 28+ was required while Discover displayed OBS 33.0.1.

The installer invoked `flatpak info --show-version`, which Flatpak does not
support. It treated the nonzero command result as an incompatible OBS version.
The earlier unit and integration fixtures incorrectly accepted the invented
option. The error occurs before app/plugin replacement; dependency installation
may have occurred, but existing app/plugin activation and credentials remain.

The repair resolves the user application with
`flatpak info --user --show-ref com.obsproject.Studio`, then reads
`flatpak list --user --app --columns=ref,version`. Captured non-TTY output is
tab-separated. Matching the exact ref avoids another application's version,
another branch, or a Discover system installation being mistaken for the OBS
instance launched with `--user`.

The info command includes the `app/` kind prefix; the list ref column normally
omits it. Normalize only that prefix before comparing the full application,
architecture and branch; do not compare only the application name.

OBS 33.0.1 and the OBS 28 boundary are accepted. A valid version below 28 gets an
accurate compatibility error including that version. Query failures and absent,
empty, malformed or duplicated metadata get a version-detection error. The
installer never launches OBS or starts output to perform this metadata check.

Regression cases cover current/boundary/old versions, unrelated applications,
multiple branches, failed commands and incomplete metadata. The full installer
transport fixture now rejects unsupported Flatpak arguments. Actual CLI checks
use a disposable official Debian Flatpak installation separately from product
artifacts; actual Steam Deck/Discover behavior still requires the owner's retry.

## Prepared candidate and evidence

Draft [PR #32](https://github.com/szmyty/obsgod/pull/32) contains the repair.
Candidate `0.1.0-deck.5.1` was built from exact source
`f43e5b53b473c35dfe3facec114d28cbeff6c35d`. Its immutable review artifact commit is
`afec6263fc43369917cd54b80a58055d5c00f0e6`:

- [Complete corrected installer](https://raw.githubusercontent.com/szmyty/obsgod/afec6263fc43369917cd54b80a58055d5c00f0e6/obsgod-deck_0.1.0-deck.5.1_linux_amd64.tar.gz)
- [Fresh exact-source qualification](https://raw.githubusercontent.com/szmyty/obsgod/afec6263fc43369917cd54b80a58055d5c00f0e6/installer-flatpak-qualification.json)
- [Checksums](https://raw.githubusercontent.com/szmyty/obsgod/afec6263fc43369917cd54b80a58055d5c00f0e6/CANDIDATE-SHA256SUMS)

Runtime archive SHA256:
`dd86c830b260d765101d9819e95170c64e8980caaf60f54ebe9a120a4b6b1b5e`.
All seven core public files, every internal runtime payload hash and the public
fixed installer/plugin version were downloaded and verified.

At that source: 56 Go cases passed (one optional existing-OBS test skipped),
60 Python and eight Node cases passed, along with vet/vulnerability scan,
typecheck/build/audit, repeated identical packages, actual package browsers,
isolated pinned Decky/unified-installer/Desktop-updater fixtures and native OBS
media/lifecycle/shutdown. Three targets compiled only. Real Flatpak 1.16.6
reproduced the unsupported flag and accepted the corrected CLI surfaces; matching
upstream source confirms row formatting. Synthetic metadata export succeeded but
installation could not connect to its service, so a real nonempty installed row
was not exercised. Actual owner-device retry and CI remain acceptance gates;
current GitHub jobs did not start because of the account billing lock.

Keep the existing installation and run the complete installer again. No separate
uninstall, password reset or second WebSocket plugin is needed. Later
evidence-only documentation commits do not relabel the qualified candidate.

Official Flatpak references:

- [1.16.1 info options](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-builtins-info.c#L54)
- [List columns](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-builtins-list.c#L56)
- [Non-TTY tab output](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-table-printer.c#L687)

Candidate `0.1.0-deck.5.1` uses the repository's normal packager, matching
CLI/Decky/updater versions and a fresh exact source/manifest. It is a review
artifact, not a published release. Its qualification records must distinguish
fresh checks from unchanged-source context. No credentials, ordinary OBS
profiles, other plugins, Roadmap 2 work or broader product scope are changed.
