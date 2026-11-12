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
apply OBS settings or start a high-level workflow. Automatic workflow profiles
remain separate work under issue #11; they are not implied by connection reuse.

`config path` works even when the file is malformed. `config profiles` works
with an unavailable selected profile or password file, so it can help recover
a bad selection. `config show` and `config validate` resolve the selected
connection and credential reference without checking OBS connectivity.
`config validate` also accepts the alias `config check`.

For managed Steam Deck installation/OBS/capture diagnostics, use
`obsgod deck doctor`; it uses the managed settings and returns JSON. A broken
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
