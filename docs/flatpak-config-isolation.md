# Apply the managed OBS configuration inside the sandbox

The owner's Gaming Mode photo shows a Start request, dependency checks, a launch
request and a 20-second readiness wait ending with no local control listener.
It does not identify a crash, authentication error or successful capture.

A source-level launcher defect was found while investigating: Flatpak applies
CLI environment values before preparing its application environment, then resets
`XDG_CONFIG_HOME` to the ordinary application configuration. The old
`flatpak run --env=XDG_CONFIG_HOME=...` placement therefore cannot guarantee OBS
reads the private configuration and enabled WebSocket settings we prepared.
The owner's read-only probe confirmed this on the actual Deck: requesting
`$HOME/.var/app/com.obsproject.Studio/config/obsgod` through the old CLI override
returned `$HOME/.var/app/com.obsproject.Studio/config`. This proves the old
configuration selection was wrong; an actual retry is still needed to determine
whether any other launch or capture problem remains.

The fix uses `flatpak run --command=/usr/bin/env` and supplies the managed
`XDG_CONFIG_HOME` assignment to `env` inside the sandbox before `obs` executes.
It introduces no shell, credentials in arguments or automatic output. Background
and visible recovery launches retain the same OBS flags. Ordinary OBS settings
must remain unchanged.

Executable regression fixtures reproduce Flatpak's post-option environment
reset, then execute both launch helpers and inspect the effective configuration.
The native harness models that reset too, while still running real OBS,
authenticated WebSockets, capture/encoding and output checks. It also checks that
ordinary OBS configuration was untouched. These are separately labeled evidence,
not a substitute for the actual Deck retry.

Upstream Flatpak references:

- [1.16.1: CLI environment application](https://github.com/flatpak/flatpak/blob/1.16.1/common/flatpak-run.c#L3218)
- [Later environment setup](https://github.com/flatpak/flatpak/blob/1.16.1/common/flatpak-run.c#L3417)
- [Application environment reset](https://github.com/flatpak/flatpak/blob/1.16.1/common/flatpak-context.c#L3287)
- [XDG_CONFIG_HOME assignment](https://github.com/flatpak/flatpak/blob/1.16.1/common/flatpak-context.c#L3176)

The same order was inspected in Flatpak 1.14.10. No crash markers, ordinary OBS
profiles or user credentials are deleted to work around the failure.

Saved console history survives mode changes even when the clipboard does not.
To read it in Desktop Mode without starting OBS or exposing settings:

```sh
~/.local/bin/obsgod deck status 2>/dev/null | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin).get("diagnostics", []), indent=2))'
```

Do not infer the Gaming Mode process outcome from Desktop status after switching
sessions, and do not request raw credentials/configuration or raw OBS logs.

## Qualified repair candidate

Draft [PR #33](https://github.com/szmyty/obsgod/pull/33) builds on draft
[PR #32](https://github.com/szmyty/obsgod/pull/32), the separate supported-Flatpak
version-query repair. Candidate `0.1.0-deck.5.2` was built and qualified from exact
source `e10383598a01b7bfab946735d4187a458a5177e5`.
The immutable review artifact commit is
`414480b8cdc23f0eb5e0ea209f45f98adcddaebd` on
`artifacts/deck5-config-isolation`. This orphan artifact branch is a download and
evidence checkpoint; never merge it into source. Neither PR is merged and no
release or tag was published for this repair.

[Exact commands, platforms, outcomes and artifact hashes](https://raw.githubusercontent.com/szmyty/obsgod/414480b8cdc23f0eb5e0ea209f45f98adcddaebd/config-isolation-qualification.json)
are accompanied by the logs under `evidence/` in that commit. All seven core
files were downloaded again from the public immutable URLs; their sizes and
hashes matched. Runtime/updater internal payload hashes, source/version metadata
and plugin archive identity also matched. Fresh checks passed:
59 Go cases with race detection (one optional existing-OBS case skipped), 60
Python and 8 Node cases; vet/vulnerability/typecheck/audit; deterministic runtime
and updater packages; actual-package Desktop setup/5.1 upgrade/panel browser
checks; pinned Decky 3.3.1 frontend/backend/router/installer and updater fixtures;
and native OBS media, authentication and lifecycle checks. The native run uses
real OBS 30.2.3/WebSocket 5.5.2/GStreamer 1.26.2/PipeWire/PulseAudio and software
H264/AAC with a modeled Flatpak environment reset and substituted Gamescope feed.
It authenticated with the private configuration, recorded moving video/audio,
streamed to local RTMP, exercised failure cleanup and confirmed shutdown, and
left ordinary OBS configuration unchanged. It does not qualify actual SteamOS,
Flatpak launch, Gamescope, VAAPI, controller/session performance or Kick reception.
Linux arm64, Windows amd64 and macOS arm64 builds compiled; they were not executed.
The qualification JSON's package entries with a null test represent Go packages
without test files, not additional skipped test cases.

Fresh GitHub jobs for this exact source did not start: GitHub reported an account
billing lock. Local checks passed separately; CI execution remains unavailable.
An earlier qualification attempt at `fb8358cf9ad9eead188a589302269b82a5f82d9c`
failed when seeding an older unified install before its Decky fixture existed.
The test setup now seeds that previous app explicitly in app-only mode, while
separately seeding its plugin and testing the full new default installer; final
receipts above belong to `e10383598a01b7bfab946735d4187a458a5177e5` only.

The owner's probe also emitted a PulseAudio symlink warning before successfully
printing the effective path. Keep it as audio follow-up evidence; no socket is
deleted and no audio repair is claimed. Actual corrected Deck startup, a local
moving-picture/audio clip and subsequent Kick viewer reception remain unrun.
Saved settings, stream key, recordings and rollback copies must be preserved by
an in-place upgrade. Use the complete 5.2 installer for this review candidate;
the existing release updater follows published versions and will not fetch an
unpublished artifact branch.

Runtime download:
[obsgod-deck_0.1.0-deck.5.2_linux_amd64.tar.gz](https://raw.githubusercontent.com/szmyty/obsgod/414480b8cdc23f0eb5e0ea209f45f98adcddaebd/obsgod-deck_0.1.0-deck.5.2_linux_amd64.tar.gz)

SHA-256: `fc543b789e2faa491556b4cb0efc7a1fe66ebc397408765997ba13d5177279d9`.
