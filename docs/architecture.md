# Architecture Notes

`obsgod` now separates CLI wiring from OBS integration so commands can be built and inspected without requiring a live OBS instance.

## Package Responsibilities

- `main.go` wires dependencies and executes the root command.
- `internal/config` provides the shared OBS connection model populated from environment defaults and CLI flags.
- `internal/commands` builds the CLI tree and contains command-specific orchestration.
- `internal/obs` exposes the OBS service abstraction and owns the websocket connection lifecycle.
- `internal/version` centralizes application naming and version formatting.
- `pkg/automation` exposes experimental context-aware OBS operations through the
  pinned goobs adapter. Free-form server errors are reduced to safe protocol codes.
- `internal/deck` owns the optional Linux Flatpak runtime, private XDG settings,
  serialized lifecycle commands and rendered-capture/stream readiness checks.
- `steamdeck` contains the user installer, authenticated loopback setup page and
  unprivileged Decky adapter. Both interfaces invoke `obsgod deck` over JSON.

The Steam Deck adapter uses a generic RTMP(S) server/key contract. It does not
perform Kick API or creator-account orchestration. The future StreamGod boundary
in #9/#13 remains open; this preview does not declare a stable public Go API.
Legacy OBS commands keep their existing connection configuration and behavior.

See [Steam Deck installation](steam-deck.md) and [build/qualification](steam-deck-building.md).

## Dependency Flow

`main` creates a `config.Config`, passes it to `obs.NewService`, and injects that service into `commands.NewRoot`.
The root command binds persistent flags directly onto the shared config model, so operational commands read the latest CLI values when they first call the OBS service.
The OBS service establishes the websocket connection lazily on the first command that needs it and reuses that connection for the remainder of the process.

## Connection Lifecycle

Help and version execution paths never call the OBS service, so they succeed even when OBS is unavailable.
Operational commands connect on demand and return contextual errors such as the target OBS address when a connection fails.
