# Local recording, replay and clips

The panel's **Record locally**, **Stop recording**, **Start replay buffer**,
**Save replay** and **Stop replay buffer** actions operate on the managed OBS
profile. They never start a broadcast. OBS confirms each output state; a request
or a toast alone is not success. Recording, replay and an already running stream
can coexist. Starting another local output preserves the current scene and audio
routing. Focusable panel actions are the controller shortcuts for this candidate;
no global Steam button chord is intercepted or claimed as qualified.

**Cancel recording** finalizes and preserves the partial MKV. It does not delete
it. Stopping recording does not stop replay or streaming; stopping streaming does
not stop local recording/replay. Stopping replay discards frames still in its
memory buffer; use **Save replay** first to keep them. Already saved clips remain.
Save waits for a new finalized file rather than returning a previous replay path.

## Storage and recovery

Defaults: the XDG Videos directory's `OBSGod` child, a 60-second replay buffer
limited to 256 MiB, and a 1 GiB free-space reserve. Without a user-dirs preference,
the directory remains `~/Videos/OBSGod`. XDG preferences are parsed as data,
without a shell. Existing installations keep compatibility IDs and credentials.

Desktop Setup exposes an absolute local directory, 15–120 replay seconds,
64–512 MiB replay memory and a 256–65536 MiB free-space reserve. Buffer limits are
bounds, not a promise that every clip reaches the requested duration. Encoder,
resolution, motion and memory affect the result. Confirm all outputs idle before
changing these preferences. Newly started local outputs recheck write access
and available space. Symbolic-link paths are refused; choose the real directory.
The Flatpak still needs access to a selected external/removable directory. A
host write probe does not establish Flatpak permission; an OBS failure remains
an error and should be repaired through Desktop permissions or a different path.

The owned active-output observer finalizes local recording and stops replay
when observed free space falls below the configured reserve. It preserves saved
media and leaves streaming alone. This is a bounded safety margin, not a disk
quota or a guarantee against another program consuming the disk between checks.
Unknown/unreadable storage does not become a false ready state. An unreachable
OBS output remains unknown; inspect its window before leaving it unattended.

Finalized files returned by managed OBS are indexed privately under the XDG
state directory. The library separates them from unindexed `DeckyStream-*.mkv` / `Replay DeckyStream-*.mkv`
files that may still be active or may have survived an interruption. Unindexed,
changed, empty or symbolic-link files are preserved and are never eligible for
automatic cleanup. After confirming output is idle, inspect interrupted MKV in
Desktop Mode; OBS's **File → Remux Recordings** can produce another container
without deleting the original. A file appearing in the folder is not proof of
moving video or audible audio.

Export copies a finalized unchanged clip into an explicit real directory and
refuses to overwrite an existing file. The original remains. Retention defaults
to zero: keep every clip. A chosen age only prepares a manual cleanup preview.
Deletion requires a second explicit confirmation containing the exact previewed
clip IDs, with all outputs idle. Changed clips, unrelated files and interrupted
recordings are excluded. There is no background retention deletion.

Uninstall preserves media unless the separate owned-media deletion action is
explicitly chosen. A custom/shared recording or export directory is not an
application-owned tree to wipe recursively. Export needed clips and retain
external media before explicitly wiping the private index/configuration.

## CLI examples

The same local preferences and output controls are available through JSON stdin:

```sh
printf '%s\n' '{"action":"status"}' | obsgod deck media
printf '%s\n' '{"action":"record-start"}' | obsgod deck media
printf '%s\n' '{"action":"record-stop"}' | obsgod deck media
printf '%s\n' '{"action":"replay-start"}' | obsgod deck media
printf '%s\n' '{"action":"replay-save"}' | obsgod deck media
printf '%s\n' '{"action":"replay-stop"}' | obsgod deck media
printf '%s\n' '{"action":"list"}' | obsgod deck media
printf '%s\n' '{"action":"prune","older_than_days":30}' | obsgod deck media
```

Use an ID from the library to export, or the IDs from a fresh cleanup preview to
confirm deletion. Export and deletion accept only unchanged indexed finalized
files. No secret values belong in these requests. Stored preferences are
version 1 in `$XDG_CONFIG_HOME/obsgod/recording.json` (usual fallback
`~/.config/obsgod/recording.json`); they contain no stream key or OBS password.

## Qualification boundary

Protocol tests cover delayed replay confirmation, stale-save rejection,
malformed/unknown output state and local-only profile mutation. Runtime tests
cover coexistence, failed-start cleanup, cancel preservation, unsafe paths,
XDG preferences, exclusive export and exact-preview cleanup. The disposable
native OBS harness decodes real recorded/replay video and audio, checks moving
frames, exercises output coexistence and crosses a configured reserve with a
small filler file without exhausting the disk. Its results belong to their exact
recorded source revision. They do not establish Steam Deck/SteamOS, Flatpak,
OBS 33, Gamescope/VAAPI, controller, provider reception or performance evidence.
Those acceptance gates remain open until measured on the declared devices.
