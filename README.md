# obsgod

[![Latest Release](https://img.shields.io/github/release/szmyty/obsgod.svg)](https://github.com/szmyty/obsgod/releases)
[![Build Status](https://github.com/szmyty/obsgod/workflows/build/badge.svg)](https://github.com/szmyty/obsgod/actions)
[![Go ReportCard](https://goreportcard.com/badge/szmyty/obsgod)](https://goreportcard.com/report/szmyty/obsgod)
[![GoDoc](https://godoc.org/github.com/golang/gddo?status.svg)](https://pkg.go.dev/github.com/szmyty/obsgod)

obsgod is a command-line remote control for OBS. It requires OBS Studio 28+ with the built-in
[OBS WebSocket v5](https://github.com/obsproject/obs-websocket) support.

## Installation

### Packages & Binaries

Download a binary from the [releases](https://github.com/szmyty/obsgod/releases)
page. Linux (including ARM) binaries are available, as well as Debian and RPM
packages.

### Build From Source

Alternatively you can also build `obsgod` from source. Make sure you have a
working Go environment (Go 1.21 or higher is required). See the
[install instructions](https://golang.org/doc/install.html).

To install obsgod, simply run:

    go install github.com/szmyty/obsgod@latest

## Configuration

All commands support the following flags:

- `--host`: OBS host to connect to (default: `localhost`, env: `OBS_HOST`)
- `--port`: OBS port to connect to (default: `4455`, env: `OBS_PORT`)
- `--password`: OBS WebSocket password (env: `OBS_PASSWORD`)

Environment variables are applied as defaults and can be overridden by CLI flags.

Example using environment variables:

```sh
export OBS_HOST=192.168.1.100
export OBS_PORT=4455
export OBS_PASSWORD=mysecret
obsgod stream status
```

## Architecture

The CLI now uses a small internal package layout to keep command construction, configuration, and OBS integration separate:

- `internal/config`: shared OBS connection settings
- `internal/commands`: CLI command tree and command orchestration
- `internal/obs`: lazy OBS service abstraction over obs-websocket
- `internal/version`: binary naming and version helpers

Dependency flow is `main -> config + obs service -> commands`. The OBS websocket connection is created lazily, so `obsgod --help` and `obsgod --version` work even when OBS is offline. See [`docs/architecture.md`](docs/architecture.md) for package responsibilities and lifecycle details.

## Usage

All commands support the following flags:

- `--host`: which OBS instance to connect to
- `--port`: port to connect to
- `--password`: password used for authentication

### Streams

Change the streaming state:

```
obsgod stream start
obsgod stream stop
obsgod stream toggle
```

Display streaming status:

```
obsgod stream status
```

### Recordings

Change the recording state:

```
obsgod recording start
obsgod recording stop
obsgod recording toggle
```

Pause or resume a recording:

```
obsgod recording pause enable
obsgod recording pause resume
obsgod recording pause toggle
```

Display recording status:

```
obsgod recording status
```

### Scenes

List all scene names:

```
obsgod scene list
```

Show the current scene name:

```
obsgod scene get
```

Switch program to a scene:

```
obsgod scene current <scene>
```

Switch preview to a scene (studio mode must be enabled):

```
obsgod scene preview <scene>
```

Switch program (studio mode disabled) or preview (studio mode enabled) to a scene:

```
obsgod scene switch <scene>
```

### Scene Collections

List all scene collections:

```
obsgod scenecollection list
```

Show the current scene collection:

```
obsgod scenecollection get
```

Switch to a scene collection:

```
obsgod scenecollection set <scenecollection>
```

### Scene Items

List all items of a scene:

```
obsgod sceneitem list <scene>
```

Change the visibility of a scene-item:

```
obsgod sceneitem show <scene> <item>
obsgod sceneitem hide <scene> <item>
obsgod sceneitem toggle <scene> <item>
```

Display the visibility of a scene-item:

```
obsgod sceneitem visible <scene> <item>
```

Center a scene-item horizontally:

```
obsgod sceneitem center <scene> <item>
```

### Labels

Change a text label:

```
obsgod label text <label> <text>
```

Trigger a countdown and continuously update a label with the remaining time:

```
obsgod label countdown <label> <duration>
```

### Sources

List special sources:

```
obsgod source list
```

Toggle mute status of a source:

```
obsgod source toggle-mute <source>
```

### Studio Mode

Enable or disable Studio Mode:

```
obsgod studiomode enable
obsgod studiomode disable
obsgod studiomode toggle
```

Display studio mode status:

```
obsgod studiomode status
```

Transition to program (when the studio mode is enabled):

```
obsgod studiomode transition
```

### Profiles

List all profiles:

```
obsgod profile list
```

Show the current profile:

```
obsgod profile get
```

Switch to a profile:

```
obsgod profile set <profile>
```

### Replay Buffer

Change the replay buffer state:

```
obsgod replaybuffer start
obsgod replaybuffer stop
```

Save the replay buffer:

```
obsgod replaybuffer save
```

Display replay buffer status:

```
obsgod replaybuffer status
```

### Virtual Camera

Change the virtual camera state:

```
obsgod virtualcam start
obsgod virtualcam stop
obsgod virtualcam toggle
```

Display virtual camera status:

```
obsgod virtualcam status
```
