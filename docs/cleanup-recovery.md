# Cleanup, updates and retained Desktop recovery

The standard Decky ZIP owns its bundled controller. Use Decky's plugin controls
for ordinary replacement and removal; a separately installed Desktop app is
optional. Different app and plugin versions do not by themselves mean either
installation is broken. This contract implements bounded audit issues #101/#102;
actual supported Decky/SteamOS and provider acceptance remains #86.

## Read-only plugin checks

The panel compares published standard plugin versions with the **loaded plugin**,
not an older Desktop app. A candidate requires the same repository's canonical
ZIP, primary build receipt and checksum metadata, matching version, source and
platform. Runtime archives or release-body links alone do not establish a
standard plugin release. These are metadata checks, not a download/install or a
publisher signature. The existing repository and redirect trust boundary stays
unchanged. No verified published standard release is an unavailable update
channel, not permission to install an older paired runtime.

The panel separately reports optional Desktop app inventory. It does not claim
that app is current, require matching versions, or direct a plugin-only user to
a Desktop updater they never installed. Offline/rate-limit/invalid-metadata
results leave installed files and OBS untouched.

## Explicit retained recovery

Current retained installer dependency work uses the native setup policy from
the **verified candidate ZIP**. It does not import an arbitrary installed helper
or keep a second Flatpak mutation implementation. Validated player/session,
fresh known idle output and the same setup/control lease precede dependency
changes. Remote trust, user scope, OBS/add-on branch compatibility, missing-only
installation, cancellation and bounded inherited worker leases follow the
[native dependency contract](dependency-setup.md). Application-only installation
does not perform this dependency transaction. Normal plugin lifecycle startup
still downloads nothing.

The installer holds its installation lease around recovery. An explicit close
of idle managed OBS happens outside the Python control lease, since the Go
close operation acquires that lease itself. Replacement takes the shared lease
and observes idle again. Active, unknown, busy or unmanaged output cannot be
converted to an installation permission.

The updater and installer refuse an ordinary replacement of a newer plugin.
Deliberate recovery binds both exact public versions:
`--recover-plugin-version TARGET --expect-plugin-version CURRENT`. The target
must match the verified candidate; the observed installed plugin must still
match the expected version at subsequent guards. A blanket `--repair` does not
authorize a downgrade. Only a same-version ordinary repair is selected as such.

A downloaded installer must declare the current recovery-policy interface
before it is imported or executed. Historical metadata remains readable, but
an older installer that lacks the new safety boundary cannot be applied by this
updater. Use a reviewed current recovery package or Decky's controls. This does
not make historical archives unsafe test evidence or rewrite their bytes.

Automatic rollback may restore only a verified prior plugin archive matching
the observed pre-replacement plugin version, while the expected candidate is
still installed. An old Desktop archive is not necessarily that preimage.
Otherwise rollback remains unconfirmed; files/settings are preserved and the
result requests deliberate recovery instead of silently installing its old
plugin. A matching version alone does not prove restoration of identical bytes.

## Preview cleanup and preserve coordination

`python3 uninstall.py --dry-run` is read-only inventory. Normal retained-tool
uninstall, reset, wipe and explicit media selections retain their existing
scopes. Wipe now leaves minimal private coordination metadata:
`update.lock`, `install.lock` and `control.lock`, with their containing namespaces.
Preview lists these retained paths. Removing their names while holding old
descriptors would let a second controller acquire a different lock generation.

Removal takes updater, installation and shared control leases in that order.
Pre-existing waiters and new openers use the same inodes, including after partial
deletion and retry. Selected paths/ancestors and held coordination identities
are checked at operation boundaries. Changed previews stop safely and report
completed and remaining selections. Unrelated files, ordinary OBS, other
plugins, shared Flatpaks and unselected media remain outside the deletion scope.

Cleanup suppresses its own sibling-import bytecode writes, and an already
private executable helper is not chmodded merely to run it. Those self-changes
would otherwise invalidate the approved release-tree identity. An already
absent managed process is not restarted. If explicitly closing an idle instance
changes selected runtime state, the old preview is refused and a fresh preview
is required; external changes are not silently accepted as cleanup side effects.

## Durable private export before explicit wipe

The original #82-C4 contract requires recoverable export before a complete wipe.
`--wipe` now plans a unique TAR in the owned private
`XDG_DATA_HOME/obsgod-wipe-exports` sibling namespace (default
`~/.local/share/obsgod-wipe-exports`). `--export PATH` chooses a new private target
for wipe only. The export is never inside a selected deletion tree or plugin
root. Preview is read-only and advertises that the archive contains credentials
and remains after wipe. Existing non-wipe/reset/legacy-retirement semantics stay.

Under the existing update→install→control leases, export streams only the pinned
selection through no-follow descriptors and checks single-link owned files.
Retained lock inodes are excluded; media appears only if separately selected.
Known aliases are manifest metadata, never followed or materialized as TAR links.
The bounded operation checks contents/digests, syncs the private0600 temporary
file, publishes without overwriting, syncs its0700 owned parent and verifies the
named artifact before the first plugin/data removal. Export failure causes no
removal; selected roots, coordination and export identities remain checked at
later operation boundaries. No broad ownership/permission repair is performed.

The archive preserves a private copy of selected data after wipe, including
possible stream keys/control passwords/history. It is not encrypted and must
never enter public diagnostics. `RECOVERY.json` describes entries/hashes and
manual staging; there is no automatic restore, re-created alias or asserted
application rollback. Use a separately verified install artifact, inspect/recover
selected paths in a new private staging directory and deliberately dispose of
the exact export when no longer wanted. A later lost/changed export stops further
removal; the tool does not claim that an artifact it cannot re-observe survived.
See the [user commands](steam-deck.md#private-recovery-export-before-wipe).

To retire only obsolete Desktop app files, preview
`python3 uninstall.py --legacy-app-only --dry-run`. This explicit scope removes
owned app releases, matching aliases and managed launchers while preserving the
active Decky plugin, shared settings/state/cache, media and rollback backups.
It cannot be combined with reset, wipe, purge or media deletion. Apply requires
fresh known idle output and absent managed OBS; close it explicitly through
Decky first if necessary. This operation does not restart OBS or call Decky's
plugin-removal helper.

Legacy writable/removal roots now reject group/other-writable nonsticky
ancestors before writes, locks or deletion. Supported home aliases and trusted
sticky temporary roots remain supported; alias prefixes also need protection.
An old unsafe directory is not repaired with a broad chmod/chown. Inspect and
choose a protected owned path before retrying.

All changes need fresh focused and final exact-source evidence. Linux process,
filesystem, native OBS, browser and pinned-loader fixtures do not establish real
Deck permissions, Flathub transactions, controller behavior or provider receipt.
No release, deployment, migration or spending follows from preparing recovery.
