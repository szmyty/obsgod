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

OBS 33.0.1 and the OBS 28 boundary are accepted. A valid version below 28 gets an
accurate compatibility error including that version. Query failures and absent,
empty, malformed or duplicated metadata get a version-detection error. The
installer never launches OBS or starts output to perform this metadata check.

Regression cases cover current/boundary/old versions, unrelated applications,
multiple branches, failed commands and incomplete metadata. The full installer
transport fixture now rejects unsupported Flatpak arguments. Actual CLI checks
use a disposable official Debian Flatpak installation separately from product
artifacts; actual Steam Deck/Discover behavior still requires the owner's retry.

Official Flatpak references:

- [1.16.1 info options](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-builtins-info.c#L54)
- [List columns](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-builtins-list.c#L56)
- [Non-TTY tab output](https://github.com/flatpak/flatpak/blob/1.16.1/app/flatpak-table-printer.c#L687)

Candidate `0.1.0-deck.5.1` uses the repository's normal packager, matching
CLI/Decky/updater versions and a fresh exact source/manifest. It is a review
artifact, not a published release. Its qualification records must distinguish
fresh checks from unchanged-source context. No credentials, ordinary OBS
profiles, other plugins, Roadmap 2 work or broader product scope are changed.
