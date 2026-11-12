# Original remote OBS CLI usage

The stable executable remains `obsgod`. See [configuration](configuration.md)
for the development candidate’s layered settings and machine output.

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
