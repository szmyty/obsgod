# Configure a destination in Gaming Mode

Issue [#79](https://github.com/szmyty/obsgod/issues/79) adds **Stream destination**
to the normal Decky panel. The plugin package includes this form; a separately
installed Desktop application is not required. Provider login and phone/QR
authorization remain research in #89.

Choose the Kick guide, enter your own Stream URL and separate stream key from
the creator dashboard, and select **Save destination & settings**. Twitch,
YouTube and custom RTMP(S) guides use the same local configuration path. A guide
is help text, not a provider account or security policy. Kick has no invented
shared ingest URL; copy the URL for your account. RTMPS encrypts transport; RTMP
remains available for existing local/offline workflows.

Select a field with the controller; **STEAM + X** opens the Steam keyboard.
Normal typing and paste work in the fields. **Paste stream key** requests
clipboard access; if Steam denies it, use the keyboard's paste control or a
physical keyboard. Clipboard contents do not automatically synchronize between
Desktop and Gaming Mode. Keys start masked. Show/Hide affects only an unsaved
draft. Saved keys are never returned to the frontend, and drafts clear on Save,
destination changes and panel removal.

Leave the key blank to retain the existing key for that same saved destination.
Changing servers requires a new key. For a different account or event using the
same server, enable **Different account or event on the same server** and enter
its new key. Changing the destination guide also clears the draft and requires
a replacement; the guide itself is not persisted in configuration.

Save is allowed only after the backend positively observes managed OBS closed
and every output idle. If the managed instance is running but idle, select
**Close managed OBS to edit settings…** and confirm. This closes only the managed
instance and does not reopen it. Streaming, recording, replay or unknown output
state blocks this operation. Stop output first and wait for a fresh observation.
Dependency setup or another control operation also blocks changes. Missing
dependencies alone do not prevent saving settings offline.

Optional quality controls edit bitrate, frame rate, resolution, H.264 encoder,
capture mode and the initial microphone default. Unedited advanced preferences,
between-game media/rights and live microphone/mute/gain preferences stay intact.
The default 720p/30fps/4500kbps hardware-encoder values are starting points, not
a measured performance claim. Game-only video does not isolate system audio.

**Local OBS connection** shows only nonsecret control details.
**Test local OBS connection** authenticates an already running managed instance;
it never launches OBS, contacts a provider or starts a recording/broadcast.
Changing or generating its password requires managed OBS closed and explicit
confirmation. That password is separate from the stream key and from optional
local browser setup authorization; none is read back or copied to diagnostics.

Saving does not broadcast. Make a local test clip, inspect picture and sound,
then explicitly select Start streaming and verify reception from another device.
Actual controller/Steam keyboard and provider reception remain owner Deck tests.

The included optional browser setup still supports advanced configuration in
Desktop Mode. Run the bundled `bin/obsgod deck setup` from the installed plugin
directory and use the private loopback URL it prints. Keep its authorization
token private; do not expose it to a LAN or install a second copy of the app.
See [package contents](decky-package.md) and [configuration](configuration.md).

## Implementation contract

`deck configuration` projects a credential-free, versioned view from the existing
XDG settings/secrets binding and current process/output observations. It does not
create settings, launch OBS or change output. `deck configure-fields` accepts one
bounded JSON object on stdin, merges only explicit editable fields under the
existing shared control lock, rechecks safe state and calls the existing Go
Configure writer. Legacy `deck configure` and CLI/file/environment precedence
remain intact. No second credential store or provider field is introduced.

Decky's Python adapter validates scalar fields, passes sensitive values through
stdin rather than argv/environment, serializes mutations with existing control
actions and dependency jobs, and projects only named public readback fields.
Concurrent reads are coalesced and invalidated around mutations. The frontend
expires readiness, ignores obsolete reads and clears sensitive drafts on errors,
completion or modal dismissal. Stale UI state cannot authorize backend writes.

The existing `deck restart` command supplies the explicit close-idle-OBS action;
despite its compatibility name, it does not relaunch OBS. Configuration writes
and this close action have a ten-second context/lock budget. Connection testing
and public settings reads are bounded separately. A timeout is an unconfirmed
outcome: refresh and inspect state before retrying.

Readback now requires complete schema-v1 settings/connection members and
consistent readiness flags; defaults never grant editing or closing permission.
The public projection retains Go's settings version. Legacy omitted/zero
dimensions and presence-only nested connection observations remain supported.
The separate quick capture-mode action includes its complete command, cleanup
and fresh readback below the panel's deadline. See the
[settings boundary and shared-corpus checks](settings-boundary.md).
