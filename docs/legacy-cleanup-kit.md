# Current legacy-cleanup helper

Normal plugin installation/update/removal belongs to Decky. This optional
maintainer-reviewed helper is for explicitly retiring old OBSGod Desktop files
or planning a separate reset/wipe after the current-install transition succeeds.
It is not another required application or a migration performed on your behalf.

## Use verified current source

The standard Decky ZIP deliberately does not install the optional Desktop
uninstaller. Updating that plugin cannot upgrade a retained old Desktop launcher.
Use the **full runtime archive from the same exact candidate in your review
packet** as the helper kit. The existing packager already supplies `uninstall.py`,
its sibling bridge/paths/product modules, the matching Go observer, source,
manifest and notices. No second cleanup/removal policy is implemented.

The [current review packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md)
binds the helper to exact source `772230a32a8fdb237a58b8a637947b31671ad509`.
Its [runtime TAR](https://raw.githubusercontent.com/szmyty/obsgod/430cc391cb63f080214aacc279e5c04b1092c7a5/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz)
is 12,053,779 bytes, SHA256
`e8d32968573989565dc74eb4e2bd8bd41e97107ebdbd6f57e56e69f565ef1487`;
verify the [checksums](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/SHA256SUMS)
and [source/evidence limits](pre-migration-qualified-checkpoint.md).
Do not substitute the historical `4699235` installer or assume an installed same-version
script has the new private-export behavior. Version `0.1.0-deck.9` alone does not
identify the source.

Download the candidate's named runtime TAR and checksum from its pinned review
artifact commit. Verify SHA256 and manifest/source revision, then extract only
into a new private staging directory. **Do not run `install.py` or a Desktop
launcher merely to preview cleanup.** From that extracted runtime folder:

```sh
python3 -B uninstall.py --legacy-app-only --dry-run
```

This performs read-only file inventory; it does not contact OBS/Decky, install,
launch or stream. Keep the inventory private and inspect every selected path.
For a nonstandard Decky root, use the actual verified `DECKY_HOME`/context;
unknown roots remain unresolved rather than guessed.

## Deliberate legacy retirement later

After the current plugin install/test succeeds, stop stream/record/replay and
confirm fresh idle. Explicitly close managed OBS through Decky. Retain the prior
verified install artifact and private settings/media backup; `--legacy-app-only`
keeps rollback backups and shared data. A fresh preview must still match.
Only when you intend to retire those listed old Desktop files:

```sh
python3 -B uninstall.py --legacy-app-only
```

It prompts for the displayed scope, preserves the Decky plugin, canonical
settings/secrets/state/cache/media, backups, ordinary OBS/shared Flatpaks and other
plugins, and refuses running/unknown managed state. It does not restart OBS or
remove the plugin. No actual retirement is performed during development tests.

## Reset and wipe are separate

Neither is part of ordinary legacy retirement. `--reset` retains the app/plugin
and uses its existing explicit owned-settings scope. `--wipe` first creates a
verified durable private recovery TAR outside removal roots; `--export PATH`
selects a new target in a dedicated private folder. The credential-containing
TAR intentionally survives wipe. Existing/unsafe targets or export failure stop
before the first removal. See the [exact wipe/export commands and recovery
limits](steam-deck.md#private-recovery-export-before-wipe).

Recovery is deliberate: verify the export, stage in a new private directory,
inspect `RECOVERY.json`, reinstall a separately verified package and recover only
selected owned data while output is stopped. Never extract over HOME or infer an
automatic restore. Keep exports out of public support material and dispose of
the exact archive deliberately when it is no longer needed. Device permission,
loader lifecycle and actual old→new retirement/restore success remain #86/#87
observations; fixtures and packaged dry-run evidence do not supply them.
