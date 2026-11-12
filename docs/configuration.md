# CLI configuration and scripting

These commands describe the current development candidate. Older preview
packages do not acquire them until upgraded to a matching build.

The `obsgod` command remains compatible while Decky Stream is the working product
name. Product identity is versioned metadata; user connection configuration is
separate. The reusable CLI controls an existing OBS instance without provider
presets or automatic broadcasts. The Steam Deck `deck` commands use their own
managed configuration and do not read this generic connection file.

## Precedence and defaults

Connection values resolve in this order, highest priority first:

1. Explicit `--host`, `--port`, `--password-file` or legacy `--password` flags.
2. `OBSGOD_*` environment variables, with the existing `OBS_*` aliases supported.
3. The selected connection profile in the configuration file.
4. The file's base `connection` values.
5. Built-in defaults: `localhost`, port `4455`, no password.

Within the environment layer, a nonempty `OBSGOD_HOST` or `OBSGOD_PORT` takes
precedence over its legacy alias. Empty host/port variables are ignored. An
explicitly present password variable, including an empty one, overrides file
credential references. An explicit port flag also overrides a malformed
lower-priority environment port. Invalid effective addresses/ports fail before
OBS is contacted; errors do not echo the invalid value.

The CLI does not automatically connect for help, version, shell completion or
configuration inspection. No configuration command starts OBS or changes a
scene, profile, recording or stream.

## File location and versioned schema

Run `obsgod config path` to find the file. It defaults to:

| Platform | Default connection file |
| --- | --- |
| Linux / SteamOS | `${XDG_CONFIG_HOME:-$HOME/.config}/obsgod/config.json` |
| macOS | `$HOME/Library/Application Support/obsgod/config.json` |
| Windows | `%AppData%\obsgod\config.json` |

Linux `XDG_CONFIG_HOME` must be absolute. `--config PATH` overrides
`OBSGOD_CONFIG`; an explicit missing file is an error. A missing default file
keeps legacy environment/default behavior. No file is created implicitly.

Example configuration:

```json
{
  "version": 1,
  "connection": {
    "host": "localhost",
    "port": 4455,
    "password_env": "MY_OBS_PASSWORD"
  },
  "default_profile": "desktop",
  "profiles": {
    "desktop": {},
    "studio": {
      "host": "studio.example",
      "port": 4455,
      "password_file": "studio-password"
    }
  }
}
```

Each connection chooses `password_env` **or** `password_file`. A profile inherits
omitted connection values; its credential reference replaces the base reference.
A file-relative `password_file` resolves beside the configuration file. Explicit
`--password-file` and environment file paths resolve from the current directory.
Paths and values do not expand shell expressions or `~`.

Unknown fields, unsupported schema versions, trailing JSON, unsafe/nonregular
files and configurations larger than 1 MiB are rejected. On Unix, the file must
not be writable by group/other users. There is deliberately
no inline `password` field. Profile names use 1–64 ASCII letters, digits, periods,
underscores or hyphens and begin with a letter/digit. Output lists are sorted.

## Environment reference

| Variable | Meaning | Legacy alias |
| --- | --- | --- |
| `OBSGOD_CONFIG` | Explicit connection-file path | none |
| `OBSGOD_CONNECTION_PROFILE` | Selected named connection profile | none |
| `OBSGOD_HOST` | OBS hostname/IP | `OBS_HOST` |
| `OBSGOD_PORT` | OBS WebSocket port, 1–65535 | `OBS_PORT` |
| `OBSGOD_PASSWORD` | OBS password, including an explicit empty value | `OBS_PASSWORD` |
| `OBSGOD_PASSWORD_FILE` | Private single-line password file | `OBS_PASSWORD_FILE` |

Direct password variables take precedence over password-file environment
variables. File `password_env` can name another environment variable without
putting its contents in configuration. An unset reference fails with a next
step. Prefer a provisioned private file for unattended use; the process
environment can still be visible to sufficiently privileged processes.

On Unix, password files must be regular non-symlink files with no group/other
permissions (`chmod 600 /path/to/obs-password`). On Windows, protect the file
with the user's filesystem ACL; Unix permission bits are not an ACL check.
The file holds one nonempty line, with an optional final newline, up to 16 KiB.
Do not put a real password in a command argument, documentation, committed file
or pasted diagnostic report. The legacy `--password` flag remains available for
compatibility, but command arguments can appear in shell history/process lists.

Configuration output reports only whether a password is configured and its
generic source. It never prints the password, a referenced variable's contents
or the password-file contents. Malformed JSON errors do not quote source data.

## Connection profiles and inspection

```sh
obsgod config profiles
obsgod --connection-profile studio config show --json
obsgod --connection-profile studio config validate --json
obsgod --connection-profile studio stream status --json
obsgod --password-file /private/path/obs-password stream status
```

Connection profiles choose the target connection. The existing `profile list`,
`profile get` and `profile set NAME` commands refer to **OBS's own profiles** and
keep their existing behavior. Selecting a connection profile does not silently
apply OBS settings or start a high-level workflow. Declarative workflow profiles
use the separate explicit `workflow` commands described below.

`config path` works even when the file is malformed. `config profiles` works
with an unavailable selected profile or password file, so it can help recover
a bad selection. `config show` and `config validate` resolve the selected
connection and credential reference without checking OBS connectivity.
`config validate` also accepts the alias `config check`.

For managed Steam Deck installation/OBS/capture diagnostics, use
`obsgod doctor` (equivalently `obsgod deck doctor`); it uses the managed settings
and returns JSON. A broken
generic connection file does not block Deck status, Stop or recovery commands.

## Stable machine output

```sh
obsgod version --json
obsgod config show --json
obsgod config validate --json
obsgod config profiles --json
obsgod stream status --json
obsgod recording status --json
```

These commands emit one JSON result with `schema_version: 1`. Stream and recording
status include `kind`, `active` and an optional `timecode`; recording also includes
`paused`. Configuration output reports `obs_connection: "not_checked"` explicitly.
Consumers should ignore unknown fields for compatible additions.

Status commands retain their concise human-readable output by default.
`--quiet` suppresses successful status output while retaining failure behavior;
it does not mean "exit unsuccessfully when inactive." `--json` and `--quiet`
are mutually exclusive. These are per-command flags, not a promise that every
existing OBS command already implements a JSON mode. Results use stdout; the
executable prints failures on stderr and returns a nonzero exit status. Failed
queries emit no successful JSON and must never be interpreted as stopped.

## Offline shell integration

Generate completions without OBS or valid connection configuration:

```sh
obsgod completion bash > obsgod.bash
obsgod completion zsh > _obsgod
obsgod completion fish > obsgod.fish
```

Install the generated file in your shell's user completion directory, or source
the Bash file from your shell configuration. For Fish the usual user directory
is `~/.config/fish/completions/`; for Zsh put `_obsgod` on `fpath` before `compinit`.
`obsgod --help` and `obsgod COMMAND --help` provide the offline command reference.
`obsgod version` and the existing `--version` include supplied build metadata.

`obsgod reference > obsgod-reference.md` generates a deterministic Markdown
reference from the complete command tree without connecting or loading secrets.
See the checked-in [command reference](cli-reference.md).

## Declarative workflow profiles

Workflow profiles describe existing OBS resources and optional local outputs.
Add `workflow_profiles` to the same version 1 configuration file:

```json
{
  "version": 1,
  "default_workflow": "studio",
  "workflow_profiles": {
    "studio": {
      "obs_profile": "Studio",
      "scene_collection": "Studio",
      "starting_scene": "Starting",
      "live_scene": "Game",
      "recording_enabled": false,
      "replay_buffer_enabled": false,
      "readiness_timeout": "3s",
      "post_start_delay": "0s"
    }
  }
}
```

```sh
obsgod workflow list
obsgod workflow plan studio
obsgod workflow apply studio --dry-run
obsgod workflow apply studio --approve
```

List, plan and dry-run are offline JSON operations. They do not resolve password
references, connect to OBS, switch settings or start output. Selection order is
the explicit name, `OBSGOD_WORKFLOW`, then `default_workflow`.

Apply requires `--approve` for that invocation. A plan with local recording or
replay enabled additionally requires `--allow-recording` or
`--allow-replay-buffer`, respectively. Approvals cannot be supplied by the
configuration file or environment. `false` leaves a local output inactive;
applying a workflow never stops an existing output and **never starts streaming**.
The term `live_scene` names the final program scene, not permission to broadcast.

The CLI first confirms stream, recording, replay and virtual-camera output are
idle. Active or unknown output blocks settings changes. OBS reports unavailable
optional replay/virtual-camera outputs as inactive only for the documented
`InvalidResourceState` (604) status on those two exact read requests; other errors
remain unknown. Requesting an unconfigured replay output still fails at start.
Successful status responses must include explicit boolean output fields; missing
or null fields remain unconfirmed and block workflow changes.

Apply chooses an existing OBS profile, chooses an existing scene collection,
sets the starting scene, waits the optional delay, selects the final scene, then
starts only separately approved local outputs. Each structural stage is checked
before the next change. Existing scenes are checked in the selected collection;
the CLI does not create or import resources. Readiness is bounded to 100ms–30s
(default 3s), and the delay to 0s–10s. Connection readiness and the subsequent
application each have bounded contexts; cancellation stops later stages.

Failures return a JSON result with `ok: false`, `applied` stages, and an
`attempted` stage when its outcome is uncertain. Earlier changes may remain,
especially if a scene is absent after switching collections. Inspect OBS before
retrying: automatic rollback could overwrite another client's work or stop
someone else's recording. State checks are best effort across separate OBS
requests; they do not lock out other OBS clients.

Known optional environment overrides are:

- `OBSGOD_WORKFLOW_OBS_PROFILE`
- `OBSGOD_WORKFLOW_SCENE_COLLECTION`
- `OBSGOD_WORKFLOW_STARTING_SCENE`
- `OBSGOD_WORKFLOW_LIVE_SCENE`
- `OBSGOD_WORKFLOW_RECORDING_ENABLED` (`true`/`false`)
- `OBSGOD_WORKFLOW_REPLAY_BUFFER_ENABLED` (`true`/`false`)
- `OBSGOD_WORKFLOW_READINESS_TIMEOUT`
- `OBSGOD_WORKFLOW_POST_START_DELAY`

Nonempty values override the selected file profile; names, booleans and duration
bounds are validated without echoing invalid data. Unknown file fields such as
`approve` or `start_stream` are rejected. Provider URLs, stream keys, arbitrary
commands and shell expressions are outside this schema.

## Verbose diagnostics and color

`--verbose` writes static command names and execution stages to stderr. It does
not emit arguments, effective hostnames, paths, profile values, credential
sources, protocol payloads or the process environment. JSON stdout remains a
single machine-readable result. Normal human output and errors remain plain.
Verbose diagnostic prefixes may use color on terminal stderr when `TERM` is
set. `--no-color`, nonempty `NO_COLOR`, `TERM=dumb` and redirected output suppress
that color. These flags do not enable an unfiltered WebSocket debug log.

## Troubleshooting

- **Cannot read configuration:** run `config path`; check that the intended
  file exists, is a regular file, and is readable. Correct an explicit stale
  `OBSGOD_CONFIG`, or remove that override to use defaults.
- **Invalid configuration JSON:** compare with version 1 above; use credential
  references, remove unknown fields and keep exactly one JSON object.
- **Unavailable profile:** run `config profiles`, then choose an existing name
  with `--connection-profile` or correct `default_profile`.
- **Missing credential reference:** provision the referenced environment
  variable/private file. Do not paste its value into a support report.
- **Cannot connect:** check OBS's built-in WebSocket server and the separate
  host/port settings. Configuration validation alone does not establish a live
  listener, successful authentication or actual stream output.
