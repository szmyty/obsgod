# Game-only capture research and implementation basis

Inspected 2026-11-12. Current OBSGod pipeline before this upgrade is stock
`pipewiresrc do-timestamp=true target-object=gamescope ... ! video.` with source
pause/cleanup on Stop. That pipeline makes no per-game selection request.

## Exact upstream sources saved locally

Valve Gamescope master revision **865a71c4048b5137f03b0711bbd80c1d24bc6915**
(committer timestamp2026-11-10). Download URLs/paths are in gamescope-sources.json.
Relevant files live beneath gamescope/. PipeWire master revision
**dba60f1a6e2471ec88d67881e88f04836bd826ec** (2026-11-11), source beneath pipewire/.
OBS33.0.1 revision **65c320b46e1af5c7a555161aea6182cdf7a8c524**, source beneath obs33/.
These downloaded upstream files are research/test inputs, outside the product.

## Actual Gamescope stream selector

`src/pipewire_gamescope.hpp` defines SPA Format properties:

- requested_size = 0x70000, Rectangle.
- gamescope_focus_appid = 0x70001, 64-bit Long.

`src/pipewire.cpp` lines99–155 advertises these fields in BGRx and NV12 formats,
including a non-DMA-BUF variant. lines350–364 parses them into gamescope_info,
and buffer allocation retains this selection with each buffer.

`src/steamcompmgr.cpp`, paint_pipewire, lines3032–3071:

- ID0 follows the compositor's current focus.
- Nonzero ID constructs a synthetic focus for that app ID, independent of the
  Steam UI focus, and rejects a mismatching focus-window app ID.
- A missing target window yields no new frame; it does not automatically draw
  a black frame. A client must manage stale data/background itself.

Lines3112–3143 paint game focus, game override/underlay/decoration windows. The
Steam overlay branch is conditioned on `!ulFocusAppId`; a nonzero app selection
skips it. This cannot remove overlays injected/rendered inside the game buffer.
It is not a blanket guarantee of excluding every game-owned window or overlay.

The private Wayland gamescope-pipewire protocol only advertises a node ID for
main-output capture. It contains no per-game capture request. gamescope-control
has screenshot-type enums (base-plane-only, real layers, full composition,
screen buffer), but those are individual file screenshot requests, not a live
video per-app selector. Do not treat either protocol as a window-capture API.

## Why a guessed GStreamer property is unsafe

Stock PipeWire Gst pipewiresrc has target-object and client/stream-properties,
but gst_caps_to_format_all constructs standard video SPA fields only. There is
no Gamescope focus-appid mapping in the inspected plugin. Setting an invented
string `gamescope.appid` node property does not request Format0x70001.

PipeWire negotiation may reflect an unknown consumer key into the negotiated
Format even when an old producer ignores it. Therefore an app-ID echo alone is
not sufficient evidence of server-side selection. The implemented element first
binds the actual source node and enumerates its **own EnumFormat before linking**,
requiring advertised BGRx selection support for that app ID, then validates the
fixed negotiated echo too. Native test fixtures include a producer that omits
this capability and would otherwise emit blue unrestricted compositor frames.

## OBS XComposite alternative and limits

OBS33 linux-capture.c registers xcomposite_input and xshm_input only when OBS's
backend is X11_EGL; native Wayland OBS does not expose those sources.
`xcomposite-input.c:927` calls one global XOpenDisplay(NULL) at module load. It
has no per-source X server setting. capture_window accepts a numeric XID or
encoded name/class fallback; title matching is unsuitable for a privacy boundary.
Different private game XWayland servers cannot be switched using that one global
connection while keeping OBS running. Forcing XCB also requires actual Flatpak
X11 socket access and recreates the earlier backend/permission risk if guessed.

xshm_input has advanced/server settings per source but captures a whole X root,
not an exact game window, and still requires X11 OBS. It is not the selected
architecture. Generic screenshot polling cannot safely hide Steam frames after
sampling unrestricted capture; it can leak frames between polls.

## Game identity inputs

Gamescope publishes root properties in steamcompmgr.cpp:5600–5652:

- GAMESCOPE_FOCUSED_APP is the INPUT focus app and can change when a menu opens.
- GAMESCOPE_FOCUSED_APP_GFX is the BASE GRAPHICS window app, preferable for
  keeping the game's selection while Steam owns input.
- GAMESCOPE_FOCUSED_WINDOW and GAMESCOPE_FOCUS_DISPLAY identify the base window
  and display, but a display alone is not a game identity.
- GAMESCOPE_FOCUSABLE_APPS contains nonzero app IDs; FOCUSABLE_WINDOWS contains
  [XID, appid, pid] triplets. The inspected enumeration explicitly skips native
  XDG windows, so it is not complete Wayland game discovery.
- STEAM_GAME on a game X window is the authoritative game app ID in Steam mode.
  Steam UI has pseudo-ID769; zero/769 must not be selected as a game.

These are private compositor/version-dependent properties. Prefer actual Steam
running-game identity plus the graphics ID, not arbitrary titles, any process,
node existence or nonblank pixels. Missing/malformed/stale/ambiguous identity
must select the background. A200ms property poll may drive scene transitions,
but server-side app-scoped capture is the actual UI-exclusion boundary.

## Selected bounded implementation

steamdeck/capture/gstobsgodcapture.c implements obsgodgamescopesrc as a live
GstPushSrc. It uses mapped MemFd/MemPtr BGRx buffers via PipeWire0.3, no GPU
DMA-BUF mapping. Validate producer advertisement, requested nonzero ID, fixed
Format echo, dimensions/bounds/stride/offset/corruption; no source buffer passes
before confirmation. Invalid selection/buffer fails closed. Output repeats only
validated selected-game pixels at30fps, then black after default2s without a
fresh frame. Static games may also stop producing commits; frame-age is not
proof of game exit. The host owns game-change/exit/background selection and must
never put an unrestricted screen source beneath the game-only source.

Build uses older Debian bookworm ABI with Gst1.22/PW0.3.65; package source/license
alongside libgstobsgodcapture.so and set GST_PLUGIN_PATH at the correct point
inside OBS's actual Flatpak environment. Actual Flatpak loading remains a gate.

## Development evidence and remaining limits

Native capture fixture agent reported development passes: app4242 red moving,
app4243 green moving, no blue compositor copies; stale-to-black; corrupt chunks;
short data bounded rejection; missing/wrong/zero SPA support and app0/769 refusal.
This is not final artifact qualification. Recompile the frozen portable library
and repeat the fixture against the exact packaged library; retain negative
producer cases that ignore/reflect unknown app-ID selection.

Required actual Deck cases: installed Gamescope capability negotiation, full
screen vs game-only, Steam menu/QAM/notifications over running games, game exit,
launch/change/new XWayland server/native Wayland game, source loss/reconnect,
static frames, fallback custom background, CPU/game FPS and viewer output.
A native server fixture does not prove SteamOS privacy or no-game behavior.

## Flatpak and ABI follow-up

Official OBS33.0.1 finishargs include --filesystem=host and xdg-run/pipewire-0;
runtime org.freedesktop.Platform26.08. Stock permissions expose our release
and Deckybin directories. Flatpak1.16.6 common/flatpak-context.c:2909 exports
g_get_home_dir(), and flatpak-exports.c:1013–1060 recursively resolves symlink
components and exposes real targets with aliases. Thus canonical /var/home/deck
paths are supported under stockhost permission; custom permission overrides
remain a real-device loading gate and must not be silently bypassed.

GStreamer1.26.2 gstregistry.c:1802–1866 scans GST_PLUGIN_PATH_1_0 as an additional
path, then independently scans system/default plugin paths. Leaving
GST_PLUGIN_SYSTEM_PATH(_1_0) untouched preserves standardplugins.

Bookwormbuilder usesGst1.22/PW0.3.65 stable ABIs and originallyreportedmaxGLIBC2.14
requiredsymbol. Rebuild finalsource and recordupdatedELF requirements; noclaim
actualFlatpakload. Gamescope3.16.1 alreadydefines0x70001 appselection, but actual
produceradvertisement+negotiationremainsmandatory ratherthanversionguess.

Sources:
- https://github.com/obsproject/obs-studio/blob/65c320b46e1af5c7a555161aea6182cdf7a8c524/build-aux/com.obsproject.Studio.json
- https://github.com/flatpak/flatpak/blob/1.16.6/common/flatpak-context.c#L2909
- https://github.com/flatpak/flatpak/blob/1.16.6/common/flatpak-exports.c#L1013
- https://github.com/GStreamer/gstreamer/blob/1.26.2/subprojects/gstreamer/gst/gstregistry.c#L1802
- https://github.com/ValveSoftware/gamescope/blob/3.16.1/src/pipewire_gamescope.hpp
