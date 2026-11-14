# Runtime correctness checkpoint

Owner-authorized repairs [#96–#100](https://github.com/szmyty/obsgod/pull/106)
preserve the current OBSGod installation and public/legacy control surfaces.
They do not complete the later cleanup, settings, artwork or device-test stages.

## Observations and capture ownership

Video setup and game/idle transitions resolve microphone enablement from the
saved mixer policy, including installations whose older microphone default was
false. This does not change mute, gain, push-to-talk or output track preferences.
Game-only video still cannot silently fall back to whole-screen capture.

The capture observer performs bounded game discovery outside the shared control
lease. Before changing OBS it acquires a short lease, reloads current settings
and credentials, and rechecks the managed profile, collection and output state.
Explicit controls can therefore take priority; a stale discovery result cannot
authorize changes after Stop, an ownership switch or a capture-mode change.
The startup handshake is read-only: confirmed managed active output establishes
observer readiness, while capture/frame health remains unknown until measured.

The ten-second local test retains its initiating control lease through recording
and finalization. During that bounded wait the parent drives game/idle capture
through the same guarded mutation helper under its existing lease; the detached
observer yields. Releasing the lease and later stopping an unidentifiable
replacement recording would break output ownership. The unchanged native game
fixture exposed this interaction during qualification and must pass the repair.

Recording transitions and runtime snapshots require a canonical boolean
`outputActive` from the raw OBS response. Public recording status also requires
a canonical boolean `outputPaused`. Missing, null, wrongly typed or only
case-insensitive aliases cannot become a known false value. Unknown preflight
does not authorize Start/Stop; unknown finalization does not return a saved path.
Legacy ACK-only recording commands keep their existing contract.

## A lost response requires a new connection

An SDK response timeout, lost request/response correlation or disconnect makes
the owned public API connection unusable. It is closed before releasing the
operation lease, and later calls fail before dispatch. Reconnect and observe OBS
before deciding whether to retry: closing a socket does not undo a request OBS
may already have applied. Workflow/profile/collection operations preserve this
safe failure identity without retaining raw server text. Numeric OBS rejections
remain `obs_request` errors and do not poison an otherwise healthy connection.

## Decky shutdown and helper processes

The pinned supported loader gives its backend five seconds to stop. The adapter
latches closing/cancellation and signals its exact owned command processes
before its first await. One four-second budget covers concurrent dependency
closure, microphone talk cancellation, Stop/status and task draining. It then
escalates only its own command children. If an interrupted command held the
shared control lease, a fresh bounded Stop/status follows its termination.
Incomplete observations remain unknown; shutdown cannot promise stopped output
when OBS is unreachable.

Each CLI child first waits in a stdlib guard for explicit permission after the
adapter has attached and registered ownership. Linux parent-death supervision
also kills that child if the backend dies abruptly. A late attachment receives
no execution permission and is reaped; its bookkeeping may outlive the hook's
bounded acknowledgement. Ordinary OBS, unrelated processes and dependency
workers are not killed as process groups. Existing dependency workers retain
their inherited shared leases and bounded recovery policy. Configuration/read
RPCs and update futures are cancelled/drained; a cancelled read-only update
thread may finish without holding backend shutdown or changing OBS.

Decky's packaged `PluginLoader` is not a Python interpreter. Frozen backends
use the validated root-owned system `/usr/bin/python3` for guard and dependency
helpers, with isolated Python flags and restored original library environment.
Source execution retains its Python executable. There is no downloaded Python
runtime or SteamOS system modification; Python 3.9+ remains required.

Lifecycle hooks are best effort and cannot veto normal Decky replacement,
reload or removal. A crash can bypass them. The guard prevents an owned command
from continuing after backend death, but cannot roll back an OBS action already
applied. Inspect OBS if shutdown reports unknown output before leaving it
unattended. Actual supported Decky/SteamOS/Flatpak/OBS 33/controller/headset and
provider execution remains unrun until the owner test in #86; faithful process,
protocol and native Linux fixtures do not supply that evidence.
