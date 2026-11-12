# Apply the managed OBS configuration inside the sandbox

The owner's Gaming Mode photo shows a Start request, dependency checks, a launch
request and a 20-second readiness wait ending with no local control listener.
It does not identify a crash, authentication error or successful capture.

A source-level launcher defect was found while investigating: Flatpak applies
CLI environment values before preparing its application environment, then resets
`XDG_CONFIG_HOME` to the ordinary application configuration. The old
`flatpak run --env=XDG_CONFIG_HOME=...` placement therefore cannot guarantee OBS
reads the private configuration and enabled WebSocket settings we prepared.
The owner's effective-path probe is still pending; the photo alone does not
prove this is the only cause of the reported timeout.

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
