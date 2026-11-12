# Actual Flatpak CLI verification

Executed 2026-11-12 in a disposable `obsgod-obs-smoke:local` Docker container.
Official Debian package: Flatpak **1.16.6** (`1.16.6-1~deb13u3`). The host and
product source were not changed. Docker inherited its configured proxy, and
the public environment proxy CA was mounted read-only for APT TLS verification.
No OBS binary/runtime was downloaded or run; no Steam Deck claim is established.

The complete executed scripts are `run.sh` and `probe.sh`. The top-level
`outcome.json`, help output, exit-status files and `docker-run.log` contain the
last attempt. `attempt1/` and `attempt2/` preserve earlier fixture construction
and installation attempts.

## Observed with the actual Flatpak binary

1. `flatpak info --user --show-version com.obsproject.Studio` exited **1** and
   printed `error: Unknown option --show-version`.
2. `flatpak info --help` lists **--show-ref**, but no --show-version option.
3. `flatpak info --user --show-ref com.obsproject.Studio` accepts the flag and
   exits 1 because this disposable user has no such installed app.
4. `flatpak list --user --app --columns=ref,version` accepts all flags and exits
   **0**, with empty stdout for an empty user installation.
5. `flatpak list --help` documents both the `ref` and `version` columns.

## Installed metadata attempt and limit

A tiny synthetic local app named `com.obsproject.Studio` was created solely to
test metadata output. Its appstream XML declares version33.0.1 and its dummy
executable prints that it is a fixture, not OBS. `flatpak build-finish` and
`flatpak build-export` succeeded offline. Installation used a disposable unsigned
local-file remote and `--user --no-deps --no-related`; no remote runtime or OBS
payload was downloaded. Installation failed with
`Could not connect: No such file or directory`, including under a fresh
`dbus-run-session`. The installed-row formatting is therefore **unavailable in
this runtime**, rather than a passed real-OBS33 metadata test. Attempts were
stopped after this bounded investigation.

## Ref formatting verified by the matching upstream source

The 1.16.6 source uses different forms in these commands:

- [info implementation](https://github.com/flatpak/flatpak/blob/1.16.6/app/flatpak-builtins-info.c#L335)
  prints `flatpak_decomposed_get_ref(ref)`, the full ref:
  `app/com.obsproject.Studio/x86_64/stable`.
- [list implementation](https://github.com/flatpak/flatpak/blob/1.16.6/app/flatpak-builtins-list.c)
  assigns `partial_ref = flatpak_decomposed_get_pref(ref)` and prints that value
  for its `ref` column.
- [get_pref definition](https://github.com/flatpak/flatpak/blob/1.16.6/common/flatpak-ref-utils.c#L1222)
  returns `&ref->data[ref->id_offset]`, omitting the `app/` kind prefix:
  `com.obsproject.Studio/x86_64/stable`.

The parser must remove only the literal `app/` prefix from the show-ref result
before matching the list ref, or explicitly support both canonical forms. It
must not match arbitrary app IDs or choose a different branch/architecture.
Matching [table-printer source](https://github.com/flatpak/flatpak/blob/1.16.6/app/flatpak-table-printer.c#L706) uses raw cell text separated by `\t` outside fancy/TTY output. These source facts support focused non-TTY parser fixtures; a real nonempty installed row remains unavailable in this container.
