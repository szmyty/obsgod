# Advanced managed stream profiles

This describes the Milestone 3 development candidate, not an already published
release. The same profile requests are used by the Decky panel, Desktop setup
and `obsgod deck stream-profiles` JSON command. They configure the isolated
managed OBS profile; the generic `obsgod profile` commands still manage OBS's own
profiles and the generic connection configuration remains separate.

## Choose a starting point

The preset editor offers:

| Preset ID | Output | Video bitrate | Starting encoder |
| --- | --- | --- | --- |
| `small-540p30` | 960×540, 30 FPS | 2500 kbps | VAAPI |
| `balanced-720p30` | 1280×720, 30 FPS | 4500 kbps | VAAPI |
| `smooth-720p60` | 1280×720, 60 FPS | 6000 kbps | VAAPI |

These are unqualified starting points. They do not establish a practical game,
encoder, temperature or battery result on the Deck. Test a local recording,
inspect its picture and sound, and observe the game before broadcasting. Higher
resolution or frame rate may increase load and power use; x264 uses the CPU and
may compete with a game. VAAPI requires an available working hardware encoder.
Provider upload limits and your connection still matter.

Advanced preferences allow 960×540, 1280×720 or 1920×1080 output; 30 or 60 FPS;
1000–8000 kbps; VAAPI or x264; system audio with an optional microphone; and
screen or game-only video. The base scene canvas remains 1280×720, preserving
existing source placement while OBS scales the encoded output. A game-only
video choice does not isolate system audio to a single application.

The portable profile's `microphone` value is the **initial microphone default**.
After live audio preferences are saved, [Live audio & microphone](microphone.md)
governs the current microphone device, enable/mute state and gains. Saving setup
settings, applying a profile or resetting stream defaults preserves those live audio
preferences; an initial default of `false` does not mute an already configured
microphone. OBS is closed during profile apply/reset, so its actual microphone
state is unknown until a fresh observation after reopening.

## Preview, save and apply

All requests use one JSON object on stdin. No credential belongs in an argument,
profile or exported document:

```sh
printf '%s\n' '{"action":"list"}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"preview","preset":"small-540p30"}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"save","name":"portable","preset":"small-540p30"}' | obsgod deck stream-profiles
```

Preview, validation, list and export do not connect to OBS or change output.
Saving/importing/deleting a named profile changes only the profile library.
Applying a profile or resetting output preferences requires managed OBS to be
positively closed: first stop every output, then use **Restart OBS** to close
its idle process. A present/unconfirmed process or listener blocks applying
settings. No profile action starts a stream or stops someone else's output.

```sh
printf '%s\n' '{"action":"apply","name":"portable"}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"reset"}' | obsgod deck stream-profiles
```

Apply/reset preserve the current destination, stream key, local WebSocket
password and idle media/message. The settings/credential binding is updated
together; a partial save fails safely and is repaired through Desktop setup.
The new output preferences take effect on the next explicit Start or local
recording. Reset returns only the portable output preferences to the established
720p30 defaults. It does not remove recordings or named profiles.

## Portable version 1 documents

A saved profile exports as this deliberately small schema:

```json
{
  "version": 1,
  "profile": {
    "version": 1,
    "width": 1280,
    "height": 720,
    "bitrate": 4500,
    "fps": 30,
    "encoder": "vaapi",
    "microphone": false,
    "capture_mode": "game"
  }
}
```

`export` returns this document in the result's `document` field. `import` takes
it in `document` plus a safe `name`. Only the shown tunables are portable:
destination URLs, credentials, private device identifiers, local media paths,
idle text and rights notes are excluded. Unknown fields, unsupported versions,
invalid dimensions/rates, unsafe profile names and trailing JSON are rejected
without echoing unknown values. Existing version 1 managed settings without
width/height retain their exact credential hash and implicit 720p behavior;
applying an explicit profile writes the dimensions into the normal bound settings.

The profile library lives next to `deck.json` as `stream-profiles.json`, under
the user's XDG configuration directory on SteamOS. It supports at most 64 named
profiles and 256 game bindings. New library files are private; nonregular files,
symlinks, unsafe names and files larger than 1 MiB are rejected. Profile names
use 1–64 ASCII letters, digits, periods, underscores or hyphens, beginning with
a letter or digit. Lists are sorted.

## Configuration precedence

For preview, validate, save and apply, effective tunables resolve in this order:

1. Explicit CLI flags, then request `overrides` for fields without a flag.
2. `OBSGOD_DECK_WIDTH`, `OBSGOD_DECK_HEIGHT`, `OBSGOD_DECK_BITRATE`,
   `OBSGOD_DECK_FPS`, `OBSGOD_DECK_ENCODER`, `OBSGOD_DECK_MICROPHONE` and
   `OBSGOD_DECK_CAPTURE_MODE`.
3. The explicitly selected portable profile or preset; otherwise the saved
   named profile, current managed settings, then established defaults.

Explicit profile/preset selection overrides `OBSGOD_DECK_PROFILE`. A named
profile selected by that environment variable takes precedence over an automatic
game binding before a new explicit output. Numeric overrides accept integers;
microphone accepts a boolean; invalid effective values fail without printing
the value. Supplying an explicit override for a field prevents a malformed
lower-priority environment value from blocking that field.

For example, this previews a 60 FPS modification without changing the preset,
current settings or output:

```sh
printf '%s\n' '{"action":"preview","preset":"balanced-720p30","overrides":{"fps":60,"bitrate":6000}}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"preview","preset":"balanced-720p30"}' | obsgod deck stream-profiles --fps=60 --bitrate=6000 --microphone=false
```

Environment overrides are applied before a new explicit cold output; they never
reconfigure an already running output, and status/preview never persist them.
Automatic environment/game-profile selection runs only when both the owned OBS
process is positively absent and its control listener is absent. An explicit
Start with OBS already present uses the current saved preferences; stop all
outputs and close idle OBS first to apply a different automatic selection.
Export and import use the selected document exactly, without environment
injection. Reset intentionally uses the established defaults.

## Per-game selection

```sh
printf '%s\n' '{"action":"bind-game","name":"portable","game_id":"4242"}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"preview","game_id":"4242"}' | obsgod deck stream-profiles
printf '%s\n' '{"action":"unbind-game","game_id":"4242"}' | obsgod deck stream-profiles
```

Binding stores a preference for a numeric Steam game ID; it neither starts OBS
nor applies settings immediately. Only a new explicit cold Start, Test, local
recording or replay action may apply a bound profile, after one running game is
unambiguously identified. Unknown, overlapping/ambiguous, idle or unbound games
leave current preferences unchanged. Once OBS is running, game changes never
rewrite encoder/output settings or restart a stopped broadcast. Close idle OBS
before starting with a different bound output profile; an existing active
stream/recording keeps its current settings. Remove a binding to return that
game to the current manual preferences. Deleting a named profile removes its
bindings without deleting current settings or local media.

The broader real Deck picture/audio, controller and performance matrix remains
an acceptance gate. Local profile validation, native synthetic recording and a
cross-build do not supply those hardware results.
