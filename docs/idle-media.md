# Local between-game media

Game-only capture can show black, a plain message, a PNG/JPEG image or a looping
MP4/WebM video while no usable, unambiguous game capture is available. It keeps
an explicitly started output running; importing media, detecting a game or
recovering a connection never starts streaming or recording.

Use Desktop setup's idle-media controls to choose a style and enter an absolute
local source path. Confirm that you own or have permission to broadcast the
asset, and optionally enter its attribution/rights note. This acknowledgement
records your choice; the application cannot establish third-party rights.
An asset's licence may require attribution in the picture or stream description;
the stored note is not automatically drawn over your stream.

Import copies the file into the managed OBS configuration with a content-hash
filename. The original file is preserved and its path is not retained in normal
configuration or diagnostics. Reinstall/update keeps that owned copy. Explicit
owned-configuration wipe removes it; it never deletes the source you imported.

Limits:

- Images: PNG or JPEG, at most 16 MiB, 8192 pixels per side and 32 megapixels.
- Videos: local MP4 or WebM containers, at most 256 MiB. Container-header
  validation is not a guarantee that every codec is available in installed OBS.
- Symlinks, non-regular files, URLs, playlists and arbitrary config-supplied
  media paths are refused. Files remain local and work offline.
- All imported video soundtracks are muted before the source becomes visible.
  Your selected system-output/microphone policy stays in effect. Game-only is
  a video privacy choice, not per-application audio isolation.
- The base canvas remains 1280×720. Media fits inside that canvas without
  stretching; transparent or unused areas show black.

Edit media only after streaming, recording and replay buffering are confirmed
idle. A missing, changed or unsupported asset yields black, without selecting
whole-screen capture or interrupting an existing output. Repair the asset in
Desktop setup. Selecting black or a message preserves the imported asset so it
can be selected again later; it does not erase media.

A new game needs two consistent observer samples before its picture replaces
idle media. Disappearance or ambiguity returns to idle immediately. When the
observer loses its verified managed control connection, status becomes unknown;
it stops after its bounded retry budget. It never launches another OBS instance,
restarts a stopped broadcast or substitutes whole-screen video.

For CLI automation, send one JSON object on standard input:

```sh
obsgod deck set-idle-media <<'JSON'
{"idle_style":"image","source":"/home/deck/Pictures/my-banner.png","rights_acknowledged":true,"attribution":"My original artwork"}
JSON

obsgod deck set-idle-media <<'JSON'
{"idle_style":"placeholder","idle_text":"Be right back"}
JSON
```

This saves local preferences for the next explicit Start or recording. It does
not require a provider secret argument. Basic modes are `black` and
`placeholder`; imported modes are `image` and `video`. Omit `source` to reuse the
currently saved compatible import. Profile exports intentionally omit media
identifiers, local paths and private attribution notes.

Automated qualification includes strict import/rights/path cases, initial video
mute ordering, privacy whitelists, game debounce and a native OBS fixture with
real image/video playback, local RTMP, decoded moving frames and selected audio.
The native test must actually pass at the claimed candidate revision. Synthetic
Linux evidence does not establish Steam Deck/Flatpak/Gamescope or controller
acceptance; those remain device gates under #24.
