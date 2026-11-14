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
| `Profiles` | Narrow typed profile inventory (`current`, `profiles`) from one `GetProfileList` request; preserves names/order, returns an independent non-null list, and does not read unrelated output state |
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
| `Legacy(ctx, LegacyRequest, Approval)` | Go-only typed allowlist for 39 existing v0 operations; mutation success means request acknowledgement, with the matching per-invocation approval; normal v1 confirmed-state methods are unchanged |

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

`obsgod api profile list` uses the narrow `Profiles` read. Its existing response
remains `operation:"snapshot"` with a name-array result; the Go method also returns
the current profile name. This avoids making profile listing depend on unrelated
stream/recording/replay/camera/scene queries. `profile.list` is an additive offline
capability identifier for the public read. Missing, null or wrongly typed inventory
fields fail rather than becoming an empty successful observation.

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

Both CLI families now use the facade:

- `CLI api -> pkg/api/v1 -> pkg/automation -> pinned goobs -> OBS`.
- `Legacy CLI -> internal/obs -> pkg/api/v1.Client.Legacy -> pkg/automation -> pinned goobs -> OBS`.

The optional [creator layer](creator-workflows.md) also consumes the public API
and owns provider meaning. Separate companion/OAuth work is explicitly deferred;
no provider account behavior enters this OBS boundary.

`Client.Legacy` is a Go-only compatibility entry point for 39 allowlisted v0
operations. Independent `LegacyRequest`, `LegacyResult`, `LegacyOutputStatus`,
`LegacySpecialSources` and `LegacyItemVisibility` types carry the documented
inputs/results without exposing `goobs`, arbitrary OBS request names or raw
protocol JSON. Unknown operations fail before reaching the backend. This method
is not a new `obsgod api legacy` command or part of that family's JSON discovery
surface. Prefer the normal typed v1 methods for new integrations.

Existing legacy `stream`, `recording`, `profile`, `scene`, and related commands
keep their names, flags, output shapes and ACK-only mutation semantics. In
particular, status retains the exact OBS timecode, narrow list reads do not add
unrelated snapshot queries, and composite scene/item operations preserve request
order and partial-action behavior. Successful legacy mutation acknowledges the
request; it does not promise the confirmed output/readback of normal v1 methods.
The existing `workflow` and managed `deck` contracts remain compatible.

Each legacy mutating verb supplies only its matching invocation-scoped approval
(`Streaming`, `Recording`, `ReplayBuffer`, `VirtualCamera` or `Settings`). Reads
need none. Context carries cancellation, not approval. Previous calls cannot
supply later authority, and this compatibility method does not relax approval or
observation requirements on `StartStream`, `SelectProfile` or other normal v1
operations. Legacy errors use the same safe domain projection and suppressed
transport logging.

`internal/obs` resolves configuration before acquiring one lazily cached facade.
Its injected dialer and User-Agent cross a private `internal/obstransport` seam;
public constructors/models do not expose a raw protocol client. The command
context reaches every legacy request, with 10-second legacy connection and
operation budgets and a shorter caller deadline taking precedence. A cancelled
waiter cannot close another acquired operation; acquired cancellation closes and
invalidates its connection. Later work may acquire a new connection, but no
interrupted mutation is automatically retried. Physical socket close is attempted
promptly and once, while SDK Disconnect cleanup completes in the background.
`Close` does not join every transport goroutine or establish idle OBS output;
an unconfirmed shutdown is an explicit safe error.

[The migration contract](legacy-api-migration.md) separates current integration,
regression sources and remaining acceptance from its preserved historical gap
map. No v0 removal/deprecation date or stable-v1 acceptance is introduced. The
full original #9 criteria still require their own reconciliation and final-source
qualification; implementation alone does not close #46.

Once a qualified v1 contract is accepted, additive optional fields/operations
may extend schema1; consumers must tolerate unknown JSON fields. Removal,
changed field meaning, new required fields, approval relaxation or different
exit semantics requires a reviewed major package/schema boundary and migration
notes. `pkg/automation` is the shared implementation layer, not the newly
promised independent public domain contract. No deprecation/removal date is
invented by adding the facade.

Local protocol/fake tests cover the import boundary, advancing/idempotent
streaming, unknown-state rejection, redaction, cancellation ownership, creator
ordering/partial failures and offline CLI JSON. Compatibility regressions also
exercise legacy ACKs/output/order, exact approvals, lazy private transport and
command cancellation. Focused checks are not the complete final-source matrix;
that matrix remains pending in the completion campaign. These tests do not replace Steam Deck,
provider viewer, required review, hosted CI or publication qualification.
