# Settings actions and readback

This is the bounded #103 contract. It preserves explicit Start, private
key/settings binding, offline use and the existing v0/public OBS API. Settings
operations do not authorize a broadcast. Implementation and Linux fixtures do
not qualify SteamOS, controller behavior, Flatpak OBS33 or provider playback.

## Complete capture-mode operation

The panel's capture-mode RPC keeps a 15-second deadline. The backend owns the
operation through caller disconnect and repeated identical requests; a lost
frontend promise does not cancel a process it no longer observes. The operation
now has these smaller budgets:

| Boundary | Budget | Included work |
| --- | --- | --- |
| Go mutation | 3 seconds | Shared control-lock wait, input, idle checks, previous observer lease and final cancellation check before writing |
| Go post-action observation | 2 seconds | Independent conservative status, including after cancellation |
| Python preflight | 2.5 seconds | Spawn attachment and canonical idle observation |
| Python command | 5.5 seconds | Spawn attachment, complete Go action and its post-action observation |
| Python fresh readback | 2.5 seconds | A new status query; no extra wait for an older shared query |
| Python owned cleanup | 0.4 seconds per phase | Bounded signal/kill/reap and pipe cleanup; an attached late guard receives no execution permission |
| Frontend capture RPC | 15 seconds | Covers the complete backend path; expiry is unconfirmed, never success |

The three Python phases plus all three cleanup allowances total 11.7 seconds.
These are cancellation/cleanup budgets, not a hard real-time operating-system
guarantee. The complete path is tested, rather than only the mutation timer.
If an operating-system condition prevents reaping a signalled command, the
backend retains the same visible pending operation until exit; it does not
acknowledge completed failure while leaving execution authority behind.
Start, Stop, microphone leases and the existing shutdown contract keep their
separate policies. A small frontend helper centralizes request timers; it does
not make a timed-out JavaScript promise cancel its RPC.

Capture preflight requires canonical known stream/recording/replay facts from
the bundled CLI. An absent media object is not an idle default. Stop latches
cancellation and interrupts the owned capture command; queued or cancelled
commands recheck their context after input, lease acquisition and the final
observation before committing settings. Once a bound settings pair is committed,
failed readback reports an unconfirmed save instead of undoing that pair.

Readback uses the existing snapshot ordering, so an older query cannot replace
the new result. Success requires both the command acknowledgement and a fresh
matching saved capture mode. Unknown output still leaves Stop/recovery
available; no action acknowledgement can turn the streaming indicator green.

## Complete configuration view

`deck configuration` remains schema version1 and returns no stream key or OBS
password. Python explicitly projects named public fields, now retaining the
already-existing Go `settings.version` field. Both Python and JavaScript require:

- Top-level schema version, boolean success/configuration/output/readiness
  flags, settings object, connection object and public message.
- Settings version1, server, bitrate, frame rate, encoder and microphone
  members with their supported types/ranges.
- Every fixed connection member emitted by Go: success, loopback host,
  managed port, authentication/credential/connection/ownership flags, process,
  output knowledge, state and public message. `awaiting_verification` is optional.

Capture mode may be omitted or empty in legacy settings and normalizes to
screen. Paired dimensions may both be omitted or zero and normalize to 1280x720;
partial pairs and unsupported dimensions are invalid. JSON numbers must be
finite mathematical integers in range: `1` and `1.0` have the same meaning,
while booleans, fractions and nonfinite values are rejected. Server projection
rejects credentials, query/fragment, control characters and malformed Unicode;
ordinary Unicode and `@` in a URL path remain valid.

Missing members or contradictory readiness disable configuration and close
actions instead of deriving permission from defaults. The two actions are
mutually exclusive and need successful known top-level readiness. Editing needs
confirmed closed local output. Closing needs the observed running managed
instance; configuration/key availability alone does not establish it.

The nested connection is a presence observation, while top-level readiness also
uses authenticated runtime status. A legitimate running-idle view can therefore
have top-level output knowledge and a close action alongside nested unknown
connection state. First-run defaults, missing stream keys with retained control
credentials, and unavailable output/settings are distinct supported states.
A failed read-only connection test does not erase an independently confirmed
closed process. These cases are preserved by the shared corpus.

All supported bundled runtime status producers emit `output_known`. The old
preview-fixture fallback is removed from controls and health; an absent value
cannot enable output or create a green streaming indicator. This does not
change the generic CLI/API compatibility surface or the retained Desktop data.

## Regression checks

The shared JSON corpus in `steamdeck/tests/fixtures/configuration-contract.json`
contains actual Go serialization with synthetic observations and explicit
malformed mutations. A Linux Go test binds producer output to the corpus;
Python and JavaScript consume the same cases. It is plain test data, not a
schema generator or a new validation dependency.

Run the repository-supported suites and the isolated fixed-port process case:

```sh
go test -race ./...
go test -race -count=1 -tags=deck_process ./internal/commands -run '^TestCaptureModeCommandProcess'
python3 -m unittest discover -s steamdeck/tests -p 'test_*.py' -v
npm --prefix steamdeck/decky test
```

The tagged real CLI case runs separately because the deck package's simulated
OBS listener also owns port4457. Assertions, signals and time limits are retained.
The candidate workflow additionally runs the unchanged packaged Python adapter
and Go executable under real independent file locks:

```sh
python3 steamdeck/tests/packaged-settings-boundary.py dist/obsgod-decky.zip --revision QUALIFIED_FULL_COMMIT --output /new/private/evidence
```

That check holds the shared control lock past the full UI budget and then
releases it to detect late writes. It also covers near-deadline success, caller
disconnect, Stop, repeated edits and observer-lease contention. Private fixture
credentials stay out of arguments and receipts. Final exact source/artifacts,
commands/platforms/outcomes and limitations belong in the qualification record;
an older passing receipt does not qualify a new build.
