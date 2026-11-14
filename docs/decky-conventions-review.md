# Decky convention review

Verified against live official sources on 2026-11-14 UTC and product source
`bd1d48835e235e790e1899281fbd0836cd130867`. This is a technical comparison and
proposed simplification, not an implemented architecture change, Store admission
or new Steam Deck qualification. The owner wants the Steam Deck plugin to be the
shipping focus; generic other-platform CLI packages need not drive its delivery.

## Verdict

The plugin runtime already uses the current Decky stack. Native Go helpers and
an external OBS Flatpak are appropriate. The main complication is the paired
Desktop app/installer/updater and incomplete standalone plugin onboarding.

| Area | Current source | Finding |
| --- | --- | --- |
| Frontend | `@decky/api`1.1.3, `@decky/ui`4.11.0, `callable`, `definePlugin` and native panel components | Matches the current template's SDK generation. No obsolete `decky-frontend-lib` dependency. |
| Backend | Async Python `Plugin` with lifecycle hooks; `api_version:1`, empty flags | Standard supported shape with ordinary user privileges. A Go rewrite or root flag is unnecessary. |
| Native payload | ZIP already contains `bin/obsgod` and `bin/libgstobsgodcapture.so` | Bundled native helpers are supported; the plugin does not need a separately installed CLI just to find its executable. |
| Build/layout | Plugin source nested under `steamdeck/decky`, custom Rollup and packager | More custom than root manifests, official preset and Decky CLI backend packaging. Nesting works for direct packaging but is not the default Store build root. |
| Rollup/runtime | Replaceable API module with Steam/Decky React/UI globals | The globals are also used by the official preset. The custom module boundary was intentional license/source handling, not obsolete SDK usage. Review obligations before replacing it with the stock preset. |
| Onboarding | Desktop setup assets ship only in the paired runtime archive | Installing the Decky ZIP alone does not provide the current complete first-run setup journey. This is the clearest usability gap. |
| Installation/update | External helper authenticates local Decky and executes installation code in Steam's tab; paired app/plugin version synchronization | Carefully checked but version-sensitive internal integration. Decky-managed plugin installation/replacement avoids this extra maintenance surface. |
| Storage | Uses supplied Decky user/plugin context; shared Desktop/CLI secrets/settings use XDG | Deliberate shared-app design, but not the recommended default for Decky-only state. Prefer provided settings/data/log directories for plugin-owned files; preserve existing keys and appropriate OBS/media locations. |

Source: [frontend](../steamdeck/decky/src/index.tsx),
[backend](../steamdeck/decky/main.py),
[build](../steamdeck/decky/rollup.config.js),
[package payload](../scripts/package-deck.py),
[installation helper](../internal/deckyinstall/install.go).

## Recommended next batch, before final full qualification

1. Make one standard Decky plugin package the primary install/update unit. Keep
   the existing Go/native payload bundled, and align source/build orchestration
   with the official template and Decky CLI rather than creating another app.
2. Complete first-run setup in the plugin package: detect OBS/extension, guide
   installation through Discover/Flatpak, configure privately and make an audible
   local clip. An optional Desktop browser setup can remain for easier typing,
   without requiring a separately installed application.
3. Let Decky own plugin replacement and uninstall. Review the existing direct
   updater boundary rather than having two managers replace the same files.
   Store distribution is preferred by Decky; manual ZIP is documented for
   development/sideloading and is discouraged for general users by current safety
   guidance. Packaging conformity does not itself obtain a Store listing.
4. Use Decky's supplied settings, persistent data and log paths for Decky-owned
   state. Reconcile this with the earlier shared XDG requirement through an
   explicit compatibility migration; never silently split credentials or move
   recordings. The OBS Flatpak keeps its appropriate native configuration paths.
5. Keep Steam Deck/SteamOS as the product test/support target. Existing generic
   CLI packaging remains optional source capability; it is not the Deck install
   method. Preserve the old criteria with the owner's actual scope disposition.

These are proposals for the owner's upcoming batches. Implementing them changes
source and must precede the final full matrix if selected. The current paused
logo/full-test/migration sequence is not treated as permission to perform a
major installer/storage rewrite during this verification request.

The Go executable runs on SteamOS, while the capture `.so` is loaded by OBS inside
Flatpak. Preserve each consumer's ABI qualification; do not blindly build every
native component against one host toolchain. No read-only SteamOS unlock or host
package installation is needed for the intended product journey.

## Sources and example

- [Official template](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/90d0780e882a17f5714fc6de044c645f22608290/README.md): root manifests, optional Python/native backend, `backend/src` → `backend/out` → packaged `bin/`, pnpm9 and standard ZIP structure.
- [Native build options](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/90d0780e882a17f5714fc6de044c645f22608290/backend/Dockerfile): Go/Rust toolchain examples.
- [Environment paths](https://github.com/SteamDeckHomebrew/wiki/blob/ec9d4cf8b07cdc7bc7706fd118d68a272f653cb4/plugin-dev/env-vars.md) and [loader helper](https://github.com/SteamDeckHomebrew/decky-loader/blob/ffd103b9c1a4ce5bf305e7c0998eda6e05457dad/backend/decky_loader/plugin/imports/decky.py): recommended settings/runtime/log locations and user context. Persistent Decky runtime data is not ephemeral `XDG_RUNTIME_DIR`.
- [Official Rollup preset](https://github.com/SteamDeckHomebrew/rollup-preset-decky/blob/5e861bcdfd6072bd98c4b9e403f547b35c31502e/src/index.js): current globals/build behavior.
- [Decky management](https://github.com/SteamDeckHomebrew/decky-loader/blob/ffd103b9c1a4ce5bf305e7c0998eda6e05457dad/README.md), [Store guidance](https://github.com/SteamDeckHomebrew/wiki/blob/ec9d4cf8b07cdc7bc7706fd118d68a272f653cb4/user-guide/plugin-store.md) and [safety guidance](https://github.com/SteamDeckHomebrew/wiki/blob/ec9d4cf8b07cdc7bc7706fd118d68a272f653cb4/user-guide/plugin-safety.md): update/uninstall/channel boundaries. Decky removal does not automatically erase every external file a plugin created.
- [Decky Syncthing](https://github.com/theCapypara/steamdeck-decky-syncthing/blob/464fd7ca05ee0bea8daa8d5d125dfc672cf08942/README.md) and [its backend](https://github.com/theCapypara/steamdeck-decky-syncthing/blob/464fd7ca05ee0bea8daa8d5d125dfc672cf08942/main.py): an actual Store example combining a Discover/Flatpak dependency, in-plugin setup and a bundled native helper. This is a pattern comparison, not endorsement of every implementation detail.

[Immutable source URLs and SHA-256 values](evidence/decky-conventions-sources.json)
retain the lookup record. Older wiki package-manager/API examples can be stale;
the current template and actual loader source were checked together. No runtime
files were changed and no final test matrix was run for this review.
