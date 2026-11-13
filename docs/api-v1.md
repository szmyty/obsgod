# Public OBS API and JSON contract

`github.com/szmyty/obsgod/pkg/api/v1` is the reusable, provider-independent Go
boundary. An importing application can connect, query, start and stop OBS without
running the executable. The module path remains compatible with existing users;
the Decky Stream display name does not authorize a repository/module migration.

This is a **v1 contract candidate at the reviewed source revision**, not a
published stable v1 release. Pin the exact reviewed commit until a qualified
release is approved. The namespace, software release, OBS WebSocket version and
installed plugin version are separate identities.

## Connection and lifecycle

```go
import (
    "context"
    "os"
    "time"
    obs "github.com/szmyty/obsgod/pkg/api/v1"
)

ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
defer cancel()
client, err := obs.Connect(ctx, obs.Connection{
    Address: "localhost:4455",
    Password: os.Getenv("OBS_PASSWORD"),
})
if err != nil { return err }
defer client.Close()
state, err := client.StartStream(ctx, obs.Approval{Streaming: true})
// Check err before consuming state. state describes OBS transmission only.
```

The [buildable example](../examples/api-client/main.go) also queries and stops
the output. Connecting never starts OBS, configures a destination or broadcasts.
Use an existing OBS 28+ with its bundled WebSocket server and matching private
password. Managed Steam Deck startup remains `obsgod deck`, which owns its
isolated graphical OBS; this public connection does not assume process ownership.

Every network operation accepts a context. Connection attempts default to 3s;
an operation, including time waiting for the client's operation lease, defaults
to 15s. Connection timeout is at most 30s; operation timeout at most 2min. A
shorter caller deadline wins. Public operations serialize on one client.

Cancellation while waiting for another operation leaves that operation alone.
Cancellation after acquiring the connection closes it, preventing an unfinished
transport request from racing the next mutation. `Close` is idempotent and may
interrupt a running request. After interrupted mutation, reconnect and inspect:
OBS may have applied it before the reply was lost. There is no automatic retry,
output rollback or assumption of idleness.

## Typed operations and approvals

| Operation | Contract |
| --- | --- |
| `Snapshot`, `StreamStatus` | Typed output/configuration observations; no mutation |
| `StartStream`, `StopStream` | Require `Streaming`; shared adapter confirms fresh advancing bytes on Start and inactive state on Stop |
| `StartRecording`, `StopRecording` | Require `Recording`; preserve media and confirm recording/finalized output through shared adapter |
| `StartReplayBuffer`, `StopReplayBuffer`, `SaveReplay` | Require `ReplayBuffer`; save waits for a new finalized path |
| `SetVirtualCamera` | Requires `VirtualCamera`; confirm observed target state |
| `SelectProfile`, `SelectCollection` | Require `Settings`; only existing names and confirmed idle outputs |
| `SelectScene` | Requires `Settings`; existing scene, observed readback; intentional live scene changes are allowed |
| `SceneItems`, `SetSceneItemEnabled` | Typed item IDs/names/visibility; changes require `Settings` and confirm readback |
| `ConfigureService` | Generic custom RTMP(S), requires `Settings` and idle stream/recording/replay/camera; private readback confirms destination and key |
| `VerifyService` | Compare desired private RTMP settings without changes or returning the configured key |
| `ApplyWorkflow` | Versioned OBS intent; `Settings` plus requested recording/replay approvals; never starts streaming |
| `Discover` | Offline operation/capability contract, not a probe of installed OBS plugins |

Approval is a separate invocation-scoped value, excluded from JSON. A profile,
environment variable, previous approval or successful connection cannot authorize
a later invocation. Stopping outputs is also an explicit action. The managed
Deck command/UI have their own existing invocation boundary.

Snapshot reads are sequential and can race another OBS client; they are not a
transaction or exclusive ownership of OBS. Failed/missing/malformed output flags
return an error and no usable snapshot. Never convert a failed observation into
`active=false`. Profile/collection/scene names are OBS identifiers, not shell
commands. Scene item IDs apply to the current OBS scene/collection.

`provider_reception` remains `unknown`. Advancing OBS bytes do not prove audible
video at a viewer, capture privacy, SteamOS session continuity or provider account
acceptance. A generic remote OBS client does not reproduce managed Deck capture
validation; use the managed workflow for that responsibility.

## JSON interoperability

The new `obsgod api` family uses this same facade and writes one JSON result to
stdout. `--json` is accepted and always enabled. Build metadata/help/completions
and capability discovery remain offline. Verbose metadata/diagnostics use stderr.

```sh
obsgod api capabilities
obsgod api snapshot
obsgod api profile list
obsgod api scene-items list 'Game'
obsgod api stream start --approve
obsgod api stream stop --approve
obsgod api replay save --approve
obsgod api workflow gaming --approve --allow-recording --allow-replay-buffer
```

Results use `schema_version:1`, `ok`, `operation`, and `result` or `error`.
Snapshot itself has a versioned typed schema. Workflow failures retain their
partial stage result; the error remains separately classified. A failure is not
an empty successful result. Parsing/unknown-command/help errors are conventional
CLI usage diagnostics; commands that run provide the JSON result contract.

Exit status preserves **0 success / 1 failure**, including cancellation, matching
the existing executable. Classify failures by JSON `error.code`, not text or a
new incompatible exit-code taxonomy. Go callers use `errors.As(err, *api.Error)`
and `errors.Is(err, context.Canceled/DeadlineExceeded)`. Fixed codes are:
`invalid_input`, `approval_required`, `authentication`, `unavailable`, `timeout`,
`cancelled`, `conflict`, `obs_request`, `internal`. `obs_code` optionally contains
the numeric protocol status; free-form server comments are excluded.

Credentials are accepted privately in memory; `Connection.Password` and the
entire `RTMPService` omit them from JSON/formatting. Errors do not retain arbitrary
underlying errors, endpoints or server response bodies. Caller code remains
responsible for not logging individual secret fields. Configuration diagnostics
and usage should use the documented [private references](configuration.md).

## Compatibility and migration

The dependency is `CLI api -> pkg/api/v1 -> pkg/automation -> pinned goobs -> OBS`.
The optional [creator layer](creator-workflows.md) consumes the public API and
owns provider meaning. No Kick/Twitch/YouTube account behavior belongs here.

Existing legacy `stream`, `recording`, `profile`, `scene`, and related commands
retain their original `internal/obs` service, flags, success acknowledgement and
human/JSON outputs. Legacy failures now use the same safe domain error projection
and silence transport logging. This intentionally does **not** claim every old
command has been migrated to the new context/approval/confirmed-output contract.
Existing `workflow` and managed `deck` contracts also remain compatible.

New importing applications and automation should use `pkg/api/v1` / `obsgod api`.
Complete legacy migration requires a separately reviewed deprecation plan;
silently changing a v0 command's success/approval semantics would break scripts.
The full #9 CLI migration criterion therefore remains a reconciliation item.

Once a qualified v1 contract is accepted, additive optional fields/operations
may extend schema1; consumers must tolerate unknown JSON fields. Removal,
changed field meaning, new required fields, approval relaxation or different
exit semantics requires a reviewed major package/schema boundary and migration
notes. `pkg/automation` is the shared implementation layer, not the newly
promised independent public domain contract. No deprecation/removal date is
invented by adding the facade.

Local protocol/fake tests cover the import boundary, advancing/idempotent
streaming, unknown-state rejection, redaction, cancellation ownership, creator
ordering/partial failures and offline CLI JSON. Exact final revision/matrix is
recorded by the completion campaign. These tests do not replace Steam Deck,
provider viewer, required review, hosted CI or publication qualification.
