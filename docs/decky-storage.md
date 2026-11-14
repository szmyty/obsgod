# Decky storage and existing OBSGod data

The current compatible plugin uses Decky's supplied settings, persistent runtime
data and log directories for plugin-owned metadata. These paths are supplied by
the loader; no fixed `/home/deck` location is assumed. The persistent runtime
data directory is not the ephemeral `XDG_RUNTIME_DIR` containing session sockets.

## One retained managed store

Current Desktop/CLI users already have canonical XDG settings, private stream-key
and OBS-password binding, managed state, media index, diagnostics and
`control.lock`. This upgrade deliberately retains that shared store. Moving only
the adapter's credentials or changing its lock path would split the CLI and
plugin into competing controllers.

| Data | Current location/behavior |
| --- | --- |
| Managed settings and secrets | Existing `${XDG_CONFIG_HOME:-$HOME/.config}/obsgod` |
| Managed state, locks, watcher/mic/media records and diagnostics | Existing `${XDG_STATE_HOME:-$HOME/.local/state}/obsgod` |
| Adapter map and migration receipt | Supplied Decky settings directory, private `storage-v1/` |
| Dependency jobs and fixed public progress | Supplied Decky persistent runtime directory, private `jobs/dependencies/` |
| Adapter/loader log destination | Supplied Decky log directory; no raw credentials or subprocess output |
| Managed OBS profile | Existing private configuration inside the OBS Flatpak's native config root |
| Recordings/imported media | Existing selected Videos/media paths; no implicit move |

The private versioned map asserts the exact already-derived shared paths and
current UID/home. It does not override them. Both Python and Go reject altered
paths, unsafe ownership/modes, symlinks, malformed/oversized maps and mismatched
contexts. The original XDG data/cache roots remain in child environments so
Flatpak sees the same player installation; neither is replaced with plugin data.
Existing directory ancestors must also resist replacement by other users:
group/other-writable nonsticky parents are refused, while trusted sticky
directories such as `/tmp` remain supported. The Linux control lock applies this
check even for older CLI clients without a storage map, preventing two lock
inodes after a state-directory rename.

## Repeat, repair and rollback

The first complete loader context records `retained-shared-xdg`; no secret bytes
are copied and no controller lock is moved. Repeated initialization checks the
same map. A missing receipt can be repaired from a still-matching map, while
different roots require deliberate recovery rather than a second store.

The bounded rollback helper removes only matching private map/receipt metadata.
Settings, secrets, state/control-lock inode, OBS configuration and recordings
remain. It is not a reset or wipe. Removal/reset/wipe and later installed-ID or
publisher migration remain their separately scoped workflows.

Absent or partial older loader context retains the existing child environment
without creating new adapter metadata. Managed commands remain compatible;
native dependency installation requires complete validated loader context and
the actual non-root player session. A context error never grants installation.

## Evidence boundaries

Focused fixtures cover repeat/repair/rollback, synthetic credential binding,
custom XDG roots, unsafe paths, actual UID checks and unchanged shared lock
identity. A real Python-produced map is consumed by the newly built Go CLI;
altered pointers are rejected before another state namespace is created.
These checks do not qualify actual SteamOS loader permissions, storage devices
or a new publisher. [Dependency setup](dependency-setup.md) uses this shared
control lease and the supplied job directory.
