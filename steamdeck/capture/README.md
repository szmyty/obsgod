# App-scoped Gamescope capture element

`libgstobsgodcapture.so` provides `obsgodgamescopesrc` for OBSGod's separately
installed obs-gstreamer input. It uses the existing PipeWire client API and
Gamescope's actual private SPA Format extension, not a guessed node property.

```sh
make OUTPUT=/absolute/output/libgstobsgodcapture.so
GST_PLUGIN_PATH=/absolute/output gst-inspect-1.0 obsgodgamescopesrc
GST_PLUGIN_PATH=/absolute/output gst-launch-1.0 \
  obsgodgamescopesrc app-id=4242 target-object=gamescope ! videoconvert ! fakesink
```

Build dependencies: GStreamer 1.0 base/video and PipeWire 0.3 development headers.
The packaging builder targets Debian bookworm's older glibc/GStreamer/PipeWire
ABI; it must be validated inside the actual installed OBS Flatpak too. Developer
tools are not end-user dependencies. The native library and this preferred
source/license must accompany redistribution. `THIRD_PARTY_NOTICES.md` retains
PipeWire/SPA header notices, GStreamer/GLib interface notices and the full
LGPL-2.1 text, with exact matching Debian SDK source descriptors. These notices
are included both in the preferred-source archive and the package's root
third-party notices. Replace/rebuild compatible dynamic libraries and the plugin
as described there; no code-signing restriction is imposed on this library.

## Selection and failure contract

- `app-id`: required unsigned game ID, 1 through UINT32_MAX. Zero and Steam's
  UI pseudo-ID769 are rejected. Changing the ID requires a new source pipeline.
- `target-object`: PipeWire node name/serial, default `gamescope`.
- `stale-ms`: default2000, range250–10000. A source frame older than this becomes
  black; frame age is not proof of game exit. A genuinely static game can also
  have no new commits and become black under this conservative policy.
- Output: validated BGRx frames at30fps; no cursor injection, no root-screen
  capture and no automatic unrestricted fallback. Gamescope may still include
  game-owned decorations/override windows or overlays already rendered inside
  a game surface. Do not promise removal of injected in-game overlays.

Before linking, the element inspects the producer node's own EnumFormat and
requires an advertised non-modifier BGRx app-ID parameter that permits the selected ID. A
negotiated echo alone is insufficient: PipeWire may reflect an unknown client
key even when an older compositor ignores it. Missing advertisement therefore
fails before any consumer stream is created. App selection advertised only on a
DMA-BUF/modifier format does not qualify the separate CPU/MemFd variant used
here. Ambiguous source names are refused.

The element requests SPA Format key `0x70001` as a64-bit Long containing the
nonzero game ID, plus requested size1280x720 (`0x70000`). A format must explicitly
echo the same ID and BGRx dimensions within4096x4096. Missing/wrong ID, unsupported
format, invalid mapping/stride/offset/size or a changed invalid format aborts
capture. No source buffer is emitted before this confirmation. Only mapped
MemFd/MemPtr CPU buffers are accepted; DMA-BUF is not guessed or mapped as RAM.
Frames are copied before returning PipeWire buffers. Corrupted renegotiation
frames are dropped. Latest-frame storage is bounded; old queues are not replayed.

The host owns game selection, fallback scene and stream authorization. Its
game-only scene must contain only this source plus the selected safe background,
never the unrestricted Gamescope source underneath it. On game exit/change or
unknown identity it should show the background while RTMP remains active. Steam
UI exclusion must come from the compositor's nonzero app filter, not a200ms
poll that can hide a full-screen source too late.

## Inspected server contract

Valve Gamescope revision `865a71c4048b5137f03b0711bbd80c1d24bc6915`:

- `src/pipewire_gamescope.hpp`: defines `SPA_FORMAT_VIDEO_gamescope_focus_appid`
  (`0x70001`) and parses it as a Long.
- `src/pipewire.cpp`: advertises the field, supports BGRx and a non-DMA-BUF
  format, and retains the selected ID with allocated buffers.
- `src/steamcompmgr.cpp`, `paint_pipewire`: nonzero ID selects that application's
  focus independently of Steam UI, rejects mismatches and omits the Steam
  overlay branch. Missing target windows produce no new game frame.

These are private version-dependent compositor capabilities. Format negotiation
tests and a synthetic app-scoped PipeWire server can verify client guards, but
do not qualify actual SteamOS/Gamescope privacy, game changes, Flatpak plugin
loading, CPU cost, graphics/color behavior or viewer output. Those require a
real Deck test on its recorded versions. Older servers without this extension
must stay on the background and report unsupported game-only capture.

## Flatpak loading and library contract

The official OBS33.0.1 manifest at revision
`65c320b46e1af5c7a555161aea6182cdf7a8c524` uses
`org.freedesktop.Platform//26.08` and grants `--filesystem=host` plus access to
the user's PipeWire socket. Stock permissions expose the installed OBSGod
release directory and the unprivileged Decky plugin's bin directory. Flatpak's
home export implementation resolves symlink components and exports the real
target too, so a `/home/deck` alias for `/var/home/deck` does not by itself hide
the canonical executable directory. Custom user filesystem restrictions can
still deny loading; report that as unavailable rather than widening permissions.
No automatic extra filesystem grants are required or applied.

Set `GST_PLUGIN_PATH_1_0` inside the sandbox after Flatpak's environment setup,
pointing to the verified library directory. GStreamer scans this additional path
before its independently configured system/default plugin directories. Do not
set or clear `GST_PLUGIN_SYSTEM_PATH_1_0` or PulseAudio routing variables as a
side effect. The native library links stable `libgstreamer-1.0.so.0`,
`libgstbase-1.0.so.0`, `libgstvideo-1.0.so.0`, `libpipewire-0.3.so.0` and GLib.
The portable builder records exact compiler/package/ELF symbol requirements;
an older build ABI plus a passing newer native host does not replace actual
loading/negotiation inside the owner's installed OBS Flatpak.

The Gamescope3.16.1 header already declares the app-ID SPA extension, but do not
infer capability solely from a version string. Probe the installed producer's
advertisement and validated negotiation every time. Missing or denied support
keeps game-only mode on its safe background.
