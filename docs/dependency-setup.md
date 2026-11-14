# Consented dependency setup

Frozen Decky backends launch the existing leased worker with validated system
Python, rather than treating `PluginLoader` as an interpreter. The
[runtime contract](runtime-correctness.md) explains environment isolation and
bounded lifecycle behavior; setup's inherited leases/recovery remain intact.

The Decky backend's `DependencySetup` observes dependencies with local Flatpak
queries. Construction and plugin startup do not download or launch anything.
Install requires the literal boolean `true`; Later leaves setup pending. OBS
installation, managed OBS launch, its authenticated control connection and active
streaming remain separate facts. This module never invokes OBS or broadcasts.

The backend owns the asynchronous operation, not the panel. `start()` reserves
kernel leases and returns an operation ID promptly; slow preflight and Flatpak
commands run in the job. Panel polling recovers its stage and the last 32 fixed,
sanitized progress events. Closing the panel does not cancel setup. Explicit
Cancel stops the owned process group, then checks installed refs again. Backend
unload similarly records interruption. Retry installs only missing compatible
refs and never deletes Flatpak's cache or shared dependencies.

Setup checks the actual non-root UID, account home, private user runtime and
Unix session-bus socket/peer UID before invoking Flatpak. It retains the player's
original user installation paths. System-only dependencies cause an actionable
scope gate rather than a duplicate user install. Existing user OBS resolves to
its active ref and installed AppStream version; versions below 28 are rejected
for manual update. OBS extension metadata selects compatible GStreamer branches,
and the installed extension must identify that OBS ref in `ExtensionOf`.

An existing user remote called `flathub` must use the expected HTTPS Flathub
repository URL with verification enabled. An unrelated, disabled or unverified
remote is not overwritten. With consent, a missing remote is added using the
official HTTPS `.flatpakrepo` definition, then checked again before installation.
Commands use argv without a shell, `--user`, exact dependency refs and normal
Flatpak verification; there is no system unlock or second WebSocket plugin.

The private receipt and setup lock live below the supplied Decky jobs directory.
Production integration also supplies the canonical managed `control.lock` and an
async preflight returning `True` only when output is confirmed idle. That shared
lease is acquired before preflight and held until final observation, preventing
a legacy CLI Start from racing the dependency transaction. A time-bounded worker
inherits the kernel leases: abruptly killing the backend cannot make an owned
Flatpak process look safe to duplicate. A replacement backend reports the busy
job until the worker exits, then records interruption and observes actual refs.
It does not kill a process from a saved bare PID.

Local observations have an eight-second aggregate budget, plus bounded child
termination; install work has a separate 20-minute budget and a final bounded
observation. Public progress contains fixed messages, never raw Flatpak output.
Bounded output is classified into actionable network, disk, permission, trust,
busy and timeout failures. Private receipt input is validated before display.

Focused checks:

```sh
python3 -m unittest discover -s steamdeck/tests -p test_dependency_setup.py -v
```

The tests execute real fake-Flatpak subprocesses and a real owned Unix socket,
including cancellation/partial install/retry, backend reload, abrupt parent
termination, shared control leases, scope/branch/version/remote rejection,
privacy and large output. A root test runner drops to a real unprivileged UID
for those fixtures. They do not establish actual SteamOS D-Bus/Flatpak,
Flathub transactions, Gaming Mode, OBS launch, controller or provider acceptance.
Those device checks remain unrun until exercised on the candidate Steam Deck.
