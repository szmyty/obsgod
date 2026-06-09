# Architecture Notes

`obsgod` now separates CLI wiring from OBS integration so commands can be built and inspected without requiring a live OBS instance.

## Package Responsibilities

- `main.go` wires dependencies and executes the root command.
- `internal/config` provides the shared OBS connection model populated from environment defaults and CLI flags.
- `internal/commands` builds the CLI tree and contains command-specific orchestration.
- `internal/obs` exposes the OBS service abstraction and owns the websocket connection lifecycle.
- `internal/version` centralizes application naming and version formatting.

## Dependency Flow

`main` creates a `config.Config`, passes it to `obs.NewService`, and injects that service into `commands.NewRoot`.
The root command binds persistent flags directly onto the shared config model, so operational commands read the latest CLI values when they first call the OBS service.
The OBS service establishes the websocket connection lazily on the first command that needs it and reuses that connection for the remainder of the process.

## Connection Lifecycle

Help and version execution paths never call the OBS service, so they succeed even when OBS is unavailable.
Operational commands connect on demand and return contextual errors such as the target OBS address when a connection fails.
