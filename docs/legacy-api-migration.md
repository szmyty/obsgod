# Legacy CLI migration contract

## Current implementation

At source `4ea56460958f57e9bc014504e630c4d18394aa27`, all 39 legacy request
operations use the shared application/API boundary:

`internal/commands -> internal/obs -> pkg/api/v1.Client.Legacy -> pkg/automation -> pinned goobs -> OBS`

The original **9.AC2** requirement in [#46](https://github.com/szmyty/obsgod/issues/46)
is “CLI commands use the same underlying application/API implementation.” This
integration supplies that source wiring with a compatibility adapter; it does
not accept every original #9 criterion, publish stable v1 or replace final-source
qualification. The intact [original criteria and dependencies](evidence/completion-criteria.json)
remain preserved. Separate companion/OAuth work is deferred, not implemented.

### What stays compatible

The service retains existing command names/aliases, configuration precedence,
argument joining, quiet/JSON behavior and successful output formatting. Mutation
success retains the v0 request-ACK meaning rather than silently adopting the
normal v1 methods' observed-completion contract. Exact OBS status timecodes,
list order/duplicates/empty lists, requested item order, studio-mode branching,
centering transform behavior and first-error/partial-action behavior remain
compatibility responsibilities. Countdown orchestration stays in the CLI.

`api.Client.Legacy` accepts only typed `LegacyRequest`/`LegacyResult` models and
39 documented `LegacyOperation` values. There is no arbitrary protocol request,
raw JSON payload, public `goobs` constructor/model or new `obsgod api legacy`
JSON command. Unknown operations fail before backend execution. Normal public
v1 methods retain their existing approvals and stronger observation/readback.

| Legacy group | Shared compatibility behavior |
| --- | --- |
| Stream and recording | ACK start/stop/toggle/pause/resume; narrow status with original active/paused/timecode projection. |
| Profiles, collections and scenes | Narrow inventories/current-name reads and ACK setters; preview/studio selection stays explicit. |
| Scene items and labels | Requested item order, visibility and partial-action behavior; horizontal center preserves other transform fields; text/countdown formatting stays compatible. |
| Replay and virtual camera | Existing ACK controls and narrow active-state reads, without adding finalized-path/readback waits. |
| Special sources and studio mode | Original Desktop/Mic slot labels, mute toggle, studio read/set/transition and composite ordering. |

### Approval, context and connection ownership

The explicit legacy verb is the existing CLI intent boundary. Each service call
maps only that action to the matching invocation-scoped public approval;
read-only calls supply none. Approval is neither stored nor carried by context.
The compatibility entry point cannot authorize an unrelated operation or weaken
normal v1 approval requirements.

The service resolves configuration before one lazy facade acquisition, caches
that facade while usable, and retains the injected dialer/User-Agent through
private `internal/obstransport` construction metadata. It does not open a second
independent connection for profile reads or expose protocol types through the
public API. Close/cancellation invalidates the acquired cached connection;
subsequent independent work may reconnect, without retrying an interrupted
mutation. Help/version/completions and documented offline paths remain offline.

The command context now reaches every legacy network request. Legacy connection
and operation budgets are 10 seconds; a shorter command deadline wins. Cancelling
a waiter cannot close another operation's acquired connection. Acquired
cancellation attempts owned physical socket shutdown promptly and once, so that
connection cannot be reused while a request is unwinding. SDK Disconnect cleanup
finishes in the background; this is not a claim that `Close` joins every
transport goroutine. Failed shutdown remains an explicit safe error, and neither
cancellation nor socket close proves that OBS rejected an action or is idle.
Inspect OBS state before any recovery/retry.

### Regression sources and qualification still due

- [Legacy service protocol compatibility](../internal/obs/service_compatibility_test.go):
  authenticated lazy connection, ACK-only mutations, narrow reads, exact values,
  ordering/partial failures, transform retention and cancellation ownership.
- [Legacy CLI compatibility](../internal/commands/legacy_compatibility_test.go):
  original human/JSON output, composite request order, failed-read stdout and
  `ExecuteContext` cancellation through the acquired physical transport.
- [Public compatibility facade](../pkg/api/v1/legacy_test.go): exact per-call
  approvals, unknown-operation rejection, independent request/result storage,
  safe errors and waiting-versus-acquired cancellation.
- [Physical transport cleanup](../pkg/automation/transport_close_test.go):
  once-only socket close, safe shutdown failure and bounded SDK cleanup completion.
- Existing [CLI contracts](../internal/commands/root_test.go),
  [workflow/countdown contracts](../internal/commands/workflow_test.go),
  [legacy redaction](../internal/obs/service_redaction_test.go),
  [profile facade](../pkg/api/v1/profiles_test.go) and
  [facade lifecycle/approval tests](../pkg/api/v1/client_test.go) remain relevant.

Focused regression/race/vet checks are preparation, not the complete final-source
qualification matrix. Record exact revisions, commands and outcomes in the
campaign evidence after source-changing work is finished. The final available
matrix, required reviews and applicable target/provider/publication acceptance
remain separate; older source4699235 receipts do not qualify this integration.
Retain original dependencies and reconcile each #9 criterion on its own evidence.

## Historical implementation map

The following record is preserved from before the compatibility integration.
Its “missing”, “next slice”, “unchanged” and “remaining” statements describe the
inspected historical source, **not the current wiring**. It explains why a
separate ACK compatibility surface was needed instead of replacing legacy calls
with stronger v1 operations.

<details>
<summary>Original gap map and preparation contract (historical)</summary>

# Legacy CLI migration contract

This is the implementation map for the remaining **9.AC2** requirement in
[#46](https://github.com/szmyty/obsgod/issues/46): “CLI commands use the same
underlying application/API implementation.” It describes source inspected at
`575e4e278599a94bbeeef334531cc60fb6714115`; it does not claim the migration or
new qualification is complete. The intact [original criteria and dependencies](evidence/completion-criteria.json)
remain authoritative. No new hard dependency, deprecation date or removal is added.

This change implements a narrow typed `pkg/api/v1.Client.Profiles` read and uses
it in the **new** `obsgod api profile list` command. Both send one profile-list
request without unrelated output queries. The existing JSON operation/result
shape is retained. Legacy `profile list/get`, its service and injected dialer
remain unchanged; this is partial preparation for their later integration.

The current wiring is `main.go → internal/commands → internal/obs.Service →
goobs` for legacy commands, and `internal/commands/api.go → pkg/api/v1 →
pkg/automation → goobs` for the new API family. The public facade's
[documented contract](api-v1.md) is already context-aware and approval-scoped.
Sharing that implementation requires compatibility adapters, not replacing
legacy command output with the API JSON envelope.

## Preserve the command boundary

- Keep existing command names, aliases, argument joining, flags, configuration
  precedence and output shapes. Most successful legacy mutations print nothing
  and acknowledge the OBS reply; they do not promise observed completion.
- Legacy mutating verbs have no `--approve` flag. Their explicit invocation is
  the existing intent boundary. An adapter must map only that requested action
  to an invocation-scoped public approval; it cannot persist approvals, authorize
  unrelated output changes or weaken approvals for importing API clients.
- `stream status` and `recording status` retain their schema1
  `kind`/`active`/optional `timecode` JSON, recording `paused`, human labels and
  `--quiet` behavior. `--json` plus `--quiet` fails before querying. The v1
  response envelope and numeric duration are not replacements for that contract.
- Preserve list ordering, duplicate names, empty lists and exact successful
  text formatting. OBS names remain data, never shell commands. Each failed
  observation remains failure, not a successful inactive/empty result.
- Resolve configuration before the first connection. Help, version, completions,
  reference and documented offline configuration/plan commands stay offline,
  including with a broken connection file. Keep credential-free errors, the
  contextual legacy connection prefix and the executable's 0/1 exit contract.

## Complete command and service map

All public `internal/obs.Service` operations are covered below. `Close` is a
lifecycle operation; the private scene-item-ID helper is an implementation detail.
“Gap” means code or compatibility tests are still required, not missing scope
that can be closed by this document.

| Legacy command / service operations | Current v1 counterpart | Migration gap |
| --- | --- | --- |
| `stream start/stop/toggle`; `StartStream`, `StopStream`, `ToggleStream` | `StartStream`, `StopStream`, `Approval.Streaming` | Facade confirms advancing transmission/inactive state; legacy accepts a single request ACK. No facade toggle. Retain legacy acknowledgement semantics through an explicit compatibility path; do not silently add waiting or observation-based toggle races. |
| `stream status`; `GetStreamStatus` | `StreamStatus` | Public `StreamState` lacks the original OBS `OutputTimecode`. Preserve exact timecode rather than reconstructing it from duration. |
| `recording start/stop/toggle`; `StartRecording`, `StopRecording`, `ToggleRecording` | `StartRecording`, `StopRecording`, `Approval.Recording` | Facade checks state/idempotency and Stop returns a finalized path; legacy returns ACK without a path. No facade toggle. |
| `recording pause enable/resume/toggle`; `PauseRecording`, `ResumeRecording`, `GetRecordingStatus` | Snapshot contains `RecordingState.Paused` | No facade pause/resume methods. Legacy pause-toggle first reads status, rejects inactive recording, then invokes one pause/resume request. Preserve that ordering and error behavior. |
| `recording status`; `GetRecordingStatus` | `Snapshot().Recording` | Add a narrow read plus exact OBS timecode; Snapshot adds unrelated output/configuration queries and failure conditions. |
| `profile list/get`; `ListProfiles`, `GetCurrentProfile` | `Profiles` returns typed names/current profile | The narrow public read is implemented. Legacy integration still needs the connection-ownership refactor below; both legacy operations currently use exactly one `GetProfileList` request. Do not substitute the broad Snapshot or ignore the existing injected dialer. |
| `profile set`; `SetCurrentProfile` | `SelectProfile`, `Approval.Settings` | Facade validates name/existence, requires known idle outputs and confirms workflow state; legacy issues one setter request and returns ACK. Preserve the legacy surface separately from the stronger public selection contract. |
| `scenecollection list/get/set`; `ListSceneCollections`, `GetCurrentSceneCollection`, `SetCurrentSceneCollection` | `Snapshot().Collections/Collection`, `SelectCollection` | Narrow collection inventory is missing. Setter has the same ACK versus idle/readback distinction as profile selection. |
| `scene list/get/current`; `ListScenes`, `GetCurrentScene`, `SetCurrentScene` | `Snapshot().Scenes/Scene`, `SelectScene` | Narrow scene list/current reads are missing; current getter uses `GetCurrentProgramScene`, not the full snapshot. Setter adds existence/readback checks in v1. |
| `scene preview/switch`; `SetPreviewScene`, `IsStudioModeEnabled`, `SetCurrentScene` | Program-only `SelectScene` | No preview or studio-mode read. `switch` must preserve its studio query followed by either preview or program selection; it is not always program selection. |
| `sceneitem list`; `ListSceneItems` | `SceneItems` | Legacy returns source names in OBS order; facade returns IDs/names/enabled flags and requires valid enabled/ID fields in that same response. This stricter observation contract can reject malformed responses that the old names-only projection accepted. Preserve valid-response formatting without weakening public unknown-state checks. |
| `sceneitem show/hide/toggle/visible`; `SetSceneItemVisible`, `ToggleSceneItem`, `GetSceneItemVisibility` | `SceneItems`, `SetSceneItemEnabled`, `Approval.Settings` | Legacy uses names, resolves IDs and processes requested items sequentially; toggle reads each enabled flag. Facade accepts numeric IDs and confirms readback. Preserve argument order, first-error/partial-action behavior and `name: true/false` output. |
| `sceneitem center`; `CenterSceneItem` | None | Add independent transform/video models and horizontal-centering operation. Existing code changes X to half base width while retaining the other returned transform fields; do not turn this into a new fit/scale algorithm. |
| `label text/countdown`; `SetLabelText` | None | Add typed text-overlay operation. Countdown remains CLI timing/orchestration and must stop scheduling writes after cancellation; its format and argument parsing stay compatible. |
| `replaybuffer start/stop/save/status`; `StartReplayBuffer`, `StopReplayBuffer`, `SaveReplayBuffer`, `GetReplayBufferActive` | `StartReplayBuffer`, `StopReplayBuffer`, `SaveReplay`, snapshot flag, `Approval.ReplayBuffer` | No narrow public status method. Facade save waits for a finalized path; legacy save only acknowledges the request. Preserve `Replay Buffer active: <bool>` text. |
| `virtualcam start/stop/toggle/status`; `StartVirtualCam`, `StopVirtualCam`, `ToggleVirtualCam`, `GetVirtualCamActive` | `SetVirtualCamera`, snapshot flag, `Approval.VirtualCamera` | No narrow status or toggle. Facade setter confirms state; legacy sends ACK-only protocol operations. Preserve `Virtual camera: <bool>` text. |
| `source list/toggle-mute`; `GetSpecialSources`, `ToggleMute` | None | Add independent special-input/mute operations. Legacy list is the five special Desktop/Mic slots with fixed labels, not every OBS input; preserve that distinction. |
| `studiomode enable/disable/toggle/status/transition`; `SetStudioModeEnabled`, `IsStudioModeEnabled`, `TriggerStudioModeTransition` | None | Add typed studio read/set/transition operations. Toggle reads then sets; transition is a separate explicit action. Preserve `Studio Mode: <bool>` text. |
| Service `Close` and first-use connection | `Connect`, `Client.Close` | Legacy constructs lazily and caches one client; facade Connect is explicit. A partial migration needs one clear connection owner, lazy acquisition and idempotent cleanup; it must not leak a second independently cached transport. |

## Prepared read and next bounded integration slice

The public profile-inventory model and context-aware read are implemented in the
shared adapter/facade, with malformed-state checks, copied output storage and the
existing facade cancellation lifecycle. The new API-family CLI consumes this
read. The next legacy slice remains **`profile list` and `profile get`**, leaving
every mutation unchanged: the compatibility service will project the typed values
into its unchanged `[]string`/`string` surface after transport ownership is shared.
This avoids output approvals, ACK/readback changes and unrelated snapshot queries.

The exact remaining technical boundary is that public `api.Connect` owns an
`automation.Connect` transport, while legacy `NewServiceWithDialer` owns its
injected `goobs` dialer and cached client. There is currently no internal adoption
interface between them. Opening a separate facade connection for legacy profile
reads would bypass that injected dialer and split lifecycle ownership; exposing
raw `goobs` through the public v1 constructor would weaken the independent public
boundary. Neither shortcut is taken. Refactor the private transport ownership
first, keeping the public models independent and the existing dialer behavior.

Before wiring that slice, make connection ownership explicit in the compatibility
adapter: resolve configuration before lazy facade acquisition; close each owned
transport exactly once, including errors/cancellation; do not reuse a connection
after an acquired operation is cancelled. Existing direct legacy methods must
still work during incremental migration. This lifecycle repair is implementation
work, not a reason to invent a new owner decision or block independent preparation.

Required regression cases for that slice:

1. The legacy list prints each returned name once with its existing newline and
   order, including spaces, duplicates and an empty list; get prints only the
   current name and newline. Neither prints a schema envelope or diagnostics on
   successful stdout.
2. Each invocation sends only the expected profile-list read after one lazy
   authenticated connection. It must work when unrelated streaming/recording/
   replay/scene reads are unsupported or fail. Help/offline paths send no request.
3. CLI flag/environment/profile/file resolution reaches that first connection
   unchanged. Existing connection-prefix and credential-redaction tests continue
   to pass; a failed profile read emits no successful names/current value.
4. A pre-cancelled request never dials. An acquired request deadline/cancellation
   closes its owned connection and does not race or reuse it; waiting-operation
   cancellation does not close another operation's connection. Close is idempotent.
5. Existing v1 approval, unknown-state, confirmed-stream and safe-error tests stay
   intact, and unchanged legacy mutations remain ACK-only with the same intent
   boundary. No provider or managed-process behavior enters the reusable core.

The current legacy interface does not carry contexts into network operations;
the CLI's signal context presently reaches countdown scheduling, not every
legacy request. Public v1 does carry contexts and invalidates an acquired
connection on cancellation. Threading command context through compatibility
adapters is therefore real migration work. Do not describe all legacy network
requests as already cancellable.

## Evidence and completion

Existing regression sources include [CLI contracts](../internal/commands/root_test.go),
[workflow/countdown contracts](../internal/commands/workflow_test.go),
[legacy redaction](../internal/obs/service_redaction_test.go), and
[facade lifecycle/approval tests](../pkg/api/v1/client_test.go). They are a starting
baseline, not a passing receipt for unimplemented adapters.

The new [profile facade tests](../pkg/api/v1/profiles_test.go) exercise the actual
WebSocket response boundary, a single narrow request, order/duplicates, malformed
fields, safe errors, detached output storage and cancellation ownership. The
[new-family CLI test](../internal/commands/api_profiles_test.go) verifies the
unchanged JSON shape, empty list, absence of unrelated requests and connection
release. These do not claim that the legacy service has been migrated.

After each bounded group, record exact source, commands, request/output/approval
compatibility and outcomes. Keep the full legacy-command migration and any
remaining deprecation decision visible under 9.AC2 until implemented and tested.
Other #9 criteria remain in the original ledger; this mapping neither reopens
superseded #9 nor closes #46. API contract acceptance, actual target/provider,
hosted CI and publication evidence keep their existing independent disposition.

</details>
