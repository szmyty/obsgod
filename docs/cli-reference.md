# obsgod command reference

Generated from the current command tree. Built-in defaults are shown; use `config show` for effective settings. Commands marked JSON keep that format. Other commands retain their existing human output.

## obsgod

obsgod is a command-line remote control for OBS

```text
obsgod [flags]
```

```sh
  obsgod version
  obsgod config show --json
  obsgod stream status --json
```

```text
      --config string               OBS connection config file (env: OBSGOD_CONFIG; default: XDG obsgod/config.json)
      --connection-profile string   Named connection profile (env: OBSGOD_CONNECTION_PROFILE)
  -h, --help                        help for obsgod
      --host string                 OBS host (env: OBSGOD_HOST or legacy OBS_HOST) (default "localhost")
      --no-color                    Disable optional terminal color in verbose diagnostics (also respects NO_COLOR/TERM)
      --password string             OBS password; prefer --password-file or OBS_PASSWORD to avoid shell history
      --password-file string        Private single-line OBS password file; avoids secret command arguments
  -p, --port uint32                 OBS port (env: OBSGOD_PORT or legacy OBS_PORT) (default 4455)
      --verbose                     Write credential-free command/stage diagnostics to stderr
```

## obsgod completion

Generate offline shell completions to stdout

```text
obsgod completion [bash|zsh|fish]
```

## obsgod config

Inspect and validate connection configuration without starting OBS

```text
obsgod config
```

## obsgod config path

Print the configured file location, even if its contents are invalid

```text
obsgod config path
```

## obsgod config profiles

List available connection profiles; this does not change OBS profiles

```text
obsgod config profiles [flags]
```

```text
      --json   Print versioned profile names
```

## obsgod config show

Show resolved configuration with credentials redacted (no OBS connection)

```text
obsgod config show [flags]
```

```text
      --json   Print versioned redacted JSON
```

## obsgod config validate

Check the selected configuration and credential reference without connecting

```text
obsgod config validate [flags]
```

Aliases: check.

```text
      --json   Print versioned redacted JSON
```

## obsgod deck

Manage the optional Steam Deck streaming preview (JSON output)

```text
obsgod deck
```

## obsgod deck change-obs-password

Change or generate the local control password from JSON stdin while OBS is closed

```text
obsgod deck change-obs-password
```

## obsgod deck clear-logs

Clear local filtered diagnostic history

```text
obsgod deck clear-logs
```

## obsgod deck configure

Save settings and key from JSON stdin, never argv

```text
obsgod deck configure
```

## obsgod deck connection-info

Read credential-free local OBS connection details

```text
obsgod deck connection-info
```

## obsgod deck doctor

Diagnose installation, capture and OBS

```text
obsgod deck doctor
```

## obsgod deck open-obs

Open the isolated OBS window visibly for Desktop recovery without starting output

```text
obsgod deck open-obs
```

## obsgod deck restart

Close idle managed OBS to apply saved settings

```text
obsgod deck restart
```

## obsgod deck set-capture-mode

Choose screen or game video for the next explicit output (JSON stdin)

```text
obsgod deck set-capture-mode
```

## obsgod deck start

Capture Gaming Mode and wait for real stream output

```text
obsgod deck start
```

## obsgod deck status

Read live output state without starting OBS

```text
obsgod deck status
```

## obsgod deck stop

Stop streaming and confirm it stopped

```text
obsgod deck stop
```

## obsgod deck support-bundle

Export filtered diagnostic facts without credentials, URLs or private paths

```text
obsgod deck support-bundle
```

## obsgod deck test-connection

Authenticate and read managed OBS without launching or broadcasting

```text
obsgod deck test-connection
```

## obsgod deck test-recording

Save a ten-second local clip without broadcasting

```text
obsgod deck test-recording
```

## obsgod doctor

Diagnose managed Steam Deck installation, OBS and capture (JSON)

```text
obsgod doctor
```

## obsgod help

Help about any command

```text
obsgod help [command]
```

## obsgod label

manage text labels

```text
obsgod label
```

## obsgod label countdown

Update a text label with a cancellable duration countdown (for example 30s)

```text
obsgod label countdown SOURCE DURATION
```

```sh
  obsgod label countdown Countdown 30s
```

## obsgod label text

Changes a text label

```text
obsgod label text SOURCE TEXT...
```

## obsgod profile

manage profiles

```text
obsgod profile
```

## obsgod profile get

Get the current profile

```text
obsgod profile get
```

## obsgod profile list

List all profiles

```text
obsgod profile list
```

## obsgod profile set

Set the current profile

```text
obsgod profile set NAME...
```

## obsgod recording

manage recordings

```text
obsgod recording
```

## obsgod recording pause

manage paused state

```text
obsgod recording pause
```

## obsgod recording pause enable

Pause recording

```text
obsgod recording pause enable
```

## obsgod recording pause resume

Resume recording

```text
obsgod recording pause resume
```

## obsgod recording pause toggle

Pause/resume recording

```text
obsgod recording pause toggle
```

## obsgod recording start

Starts recording

```text
obsgod recording start
```

## obsgod recording status

Reports recording status

```text
obsgod recording status [flags]
```

```text
      --json    Print versioned recording status JSON
      --quiet   Suppress successful status output; errors still fail
```

## obsgod recording stop

Stops recording

```text
obsgod recording stop
```

## obsgod recording toggle

Toggle recording

```text
obsgod recording toggle
```

## obsgod reference

Generate a deterministic offline Markdown command reference

```text
obsgod reference [flags]
```

```text
  -h, --help   help for reference
```

## obsgod replaybuffer

manage replay buffer

```text
obsgod replaybuffer
```

Aliases: replay-buffer.

## obsgod replaybuffer save

Saves replay buffer

```text
obsgod replaybuffer save
```

## obsgod replaybuffer start

Starts replay buffer

```text
obsgod replaybuffer start
```

## obsgod replaybuffer status

Reports replay buffer status

```text
obsgod replaybuffer status
```

## obsgod replaybuffer stop

Stops replay buffer

```text
obsgod replaybuffer stop
```

## obsgod scene

manage scenes

```text
obsgod scene
```

```sh
  obsgod scene list
  obsgod scene set Game
```

## obsgod scene current

Switch program to a different scene

```text
obsgod scene current NAME...
```

Aliases: set.

## obsgod scene get

Get the current scene

```text
obsgod scene get
```

## obsgod scene list

List all scene names

```text
obsgod scene list
```

## obsgod scene preview

Switch preview to a different scene (studio mode must be enabled)

```text
obsgod scene preview NAME...
```

## obsgod scene switch

Switch program or preview in studio mode to a different scene

```text
obsgod scene switch NAME...
```

## obsgod scenecollection

manage scene collections

```text
obsgod scenecollection
```

Aliases: scene-collection.

## obsgod scenecollection get

Get the current scene collection

```text
obsgod scenecollection get
```

## obsgod scenecollection list

List all scene collections

```text
obsgod scenecollection list
```

## obsgod scenecollection set

Set the current scene collection

```text
obsgod scenecollection set NAME...
```

## obsgod sceneitem

manage scene items

```text
obsgod sceneitem
```

Aliases: scene-item.

## obsgod sceneitem center

Horizontally centers a scene-item

```text
obsgod sceneitem center SCENE ITEM...
```

## obsgod sceneitem hide

Hides a scene-item

```text
obsgod sceneitem hide SCENE ITEM...
```

## obsgod sceneitem list

Lists all items of a scene

```text
obsgod sceneitem list SCENE
```

## obsgod sceneitem show

Makes a scene-item visible

```text
obsgod sceneitem show SCENE ITEM...
```

## obsgod sceneitem toggle

Toggles visibility of a scene-item

```text
obsgod sceneitem toggle SCENE ITEM...
```

## obsgod sceneitem visible

Show visibility status of a scene-item

```text
obsgod sceneitem visible SCENE ITEM...
```

## obsgod source

manage sources

```text
obsgod source
```

## obsgod source list

Lists all sources

```text
obsgod source list
```

## obsgod source toggle-mute

Toggles mute

```text
obsgod source toggle-mute NAME...
```

## obsgod stream

manage streams

```text
obsgod stream
```

## obsgod stream start

Starts streaming

```text
obsgod stream start
```

## obsgod stream status

Reports streaming status

```text
obsgod stream status [flags]
```

```text
      --json    Print versioned stream status JSON
      --quiet   Suppress successful status output; errors still fail
```

## obsgod stream stop

Stops streaming

```text
obsgod stream stop
```

## obsgod stream toggle

Toggle streaming

```text
obsgod stream toggle
```

## obsgod studiomode

manage studio mode

```text
obsgod studiomode
```

Aliases: studio-mode.

## obsgod studiomode disable

Disables the studio mode

```text
obsgod studiomode disable
```

## obsgod studiomode enable

Enables the studio mode

```text
obsgod studiomode enable
```

## obsgod studiomode status

Reports studio mode status

```text
obsgod studiomode status
```

## obsgod studiomode toggle

Toggles the studio mode (enable/disable)

```text
obsgod studiomode toggle
```

## obsgod studiomode transition

Transition to program

```text
obsgod studiomode transition
```

## obsgod version

Print build version without connecting to OBS

```text
obsgod version [flags]
```

```text
      --json   Print versioned build JSON
```

## obsgod virtualcam

manage virtual camera

```text
obsgod virtualcam
```

Aliases: virtual-camera.

## obsgod virtualcam start

Starts virtual camera

```text
obsgod virtualcam start
```

## obsgod virtualcam status

Reports virtual camera status

```text
obsgod virtualcam status
```

## obsgod virtualcam stop

Stops virtual camera

```text
obsgod virtualcam stop
```

## obsgod virtualcam toggle

Toggle virtual camera status

```text
obsgod virtualcam toggle
```

## obsgod workflow

Plan or explicitly apply provider-neutral OBS settings; never starts streaming

```text
obsgod workflow
```

## obsgod workflow apply

Apply reviewed settings to confirmed idle OBS; explicit approvals required

```text
obsgod workflow apply [NAME] [flags]
```

```text
      --allow-recording       Also approve local recording when requested by this workflow
      --allow-replay-buffer   Also approve local replay-buffer capture when requested
      --approve               Approve the reviewed settings changes for this invocation
      --dry-run               Show the plan offline without connecting or applying
```

## obsgod workflow list

List declarative workflow profiles without connecting to OBS

```text
obsgod workflow list
```

## obsgod workflow plan

Show resolved workflow intent offline; applies no changes

```text
obsgod workflow plan [NAME]
```
