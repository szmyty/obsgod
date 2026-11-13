# Optional creator workflows

`obsgod creator plan|start|status|stop` and `pkg/creator/v1` implement a bounded
local orchestration layer above [the public OBS API](api-v1.md). They use an
existing OBS connection, leave OBS running, and never contact account APIs,
install software, launch dashboards, upload media or execute profile commands.

The owner authorized preparation in this repository. The original #13 dedicated
StreamGod repository/product choice remains pending; this implementation does
not create that repository or establish the complete Steam Deck companion MVP.
The installed managed `deck` workflow remains the one-command graphical OBS
launch/capture path. Do not send a generic creator command to a managed or
ordinary OBS endpoint without intentionally selecting its private credentials.

## Review and run

Start from [the non-secret example](../examples/creator/gaming.json). Replace
its example ingest server with the exact RTMP(S) server supplied by the selected
provider account. Select existing OBS profiles, collections and scenes. The
example host is intentionally unusable; it cannot accidentally broadcast.

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/obsgod"
cp examples/creator/gaming.json "${XDG_CONFIG_HOME:-$HOME/.config}/obsgod/creator.json"
# Edit creator.json, then review without reading keys or connecting:
obsgod creator plan

# Enter a key privately; it is never a flag or committed configuration value.
read -rsp 'Kick stream key: ' KICK_STREAM_KEY; echo
export KICK_STREAM_KEY
obsgod creator start --approve --allow-streaming --allow-recording --allow-replay-buffer
obsgod creator status
obsgod creator stop --approve --allow-streaming --allow-recording --allow-replay-buffer
unset KICK_STREAM_KEY
```

Generic OBS credentials continue to follow the existing flags > environment >
selected connection profile > base config > defaults contract. Prefer a private
password-file/reference; never put a destination key in `--password`. Creator
profile location is explicit `--profile PATH`, then `OBSGOD_CREATOR_PROFILE`,
then the user XDG config directory's `obsgod/creator.json` (platform config
directory elsewhere). Relative `XDG_CONFIG_HOME` is rejected. A separate profile
file per workflow is supported; profile selection does not persist hidden state.

The version1 profile decoder rejects unknown fields, future schema versions,
trailing documents, malformed values and input above 64 KiB. Profiles contain
non-secret intent, a provider ID, an ingest server and an optional **environment
variable name** (`key_env`). Direct `key`, password or arbitrary subprocess/hook
fields are rejected. Approvals are flags supplied for the current invocation,
never file/environment properties.

| Provider transport adapter | Default private key source |
| --- | --- |
| `kick` | `KICK_STREAM_KEY` |
| `twitch` | `TWITCH_STREAM_KEY` |
| `youtube` | `YOUTUBE_STREAM_KEY` |
| `custom` | `OBSGOD_STREAM_KEY` |

These are RTMP transport adapters, not OAuth/account integrations or proof that
each provider accepted a broadcast. A custom provider can implement the public
`Provider` interface without changing OBS core. Its `Resolve` returns an in-memory
private `api.RTMPService`; the coordinator sanitizes its errors and validates the
result. API authentication, categories, titles, channel URLs and platform terms
remain adapter-owner responsibilities before such features are implemented.

## Start, stop and recovery semantics

Start validates profile/credentials/approvals before connecting. It observes
outputs, applies existing profile/collection/starting scene while idle, configures
and privately confirms the destination, starts approved local replay/recording,
then starts streaming and confirms fresh advancing OBS bytes. An optional
`readiness_delay` (0–30s) follows confirmation before the live scene. If omitted,
the compatible workflow `post_start_delay` is used after stream confirmation.
Final observation must confirm the requested outputs. Start/stop have a 2min
overall bound, in addition to API request deadlines and a shorter caller deadline.

An already-active Start verifies the private destination, requested profile/
collection and requested local outputs, then confirms stream progress. It does
not silently reconfigure a different broadcast. Active conflicting or partially
configured local outputs require inspection; there is no automatic takeover.

Stop can switch to the reviewed ending scene, confirms the stream stopped, and
stops recording/replay only when the respective profile policy **and** invocation
approval request it. It preserves files and leaves OBS running. A policy of false
intentionally leaves that local output active; Stop still reports it accurately.
Stopping does not require resolving the provider key, so unavailable provider
credentials cannot trap a running broadcast.

Commands report fixed lifecycle events (`stage`, `outcome`) and a typed final
snapshot, or sanitized failure with all completed stages retained. A later failure
does not blindly stop already-started outputs or erase recordings. Reconnect,
inspect the current output and perform an explicitly approved Stop/recovery action.
Cancellation may occur after OBS applied a request; cancellation is not rollback.
`provider_reception` remains `unknown`, including on successful Start.

## Extension and multi-platform strategy

`creator extensions` discovers the local provider/event/content boundaries
offline. External consumers may react to completed lifecycle results. No
executable plugin loading, background integration, secret-sharing hook or
arbitrary subprocess mechanism is enabled by configuration.

| Optional creator module | Explicit boundary |
| --- | --- |
| Starting/Live/BRB/Ending | Existing scene selection through approved API; BRB can use `api scene select` |
| Chat/dashboard, Discord, music | Separate opt-in consumer; owns credentials, network, retries and user consent |
| Clip tags/archive metadata | External local consumer of confirmed replay/recording results; never treats an acknowledged save as finalized |
| Crop/highlight/transcript/export/optional AI | Separate post-stream process using explicitly selected finalized local media; no automatic uploads/deletions |

The implemented strategy is **one OBS stream output, one ingest destination**.
Different provider presets do not create multiple direct outputs. A user-chosen
restream routing server can use `custom`; its accounts, downstream platforms,
costs, terms and viewer health remain outside this local controller.

Before simultaneous outputs are added, choose routing vs an explicit additional
OBS output capability. Preserve isolated per-provider credentials, start order,
per-destination health, metadata contracts and teardown ownership. No automatic
failover may expose a key to another provider or duplicate a public broadcast.
A partial downstream outage must report degraded destinations and preserve
healthy outputs unless the user explicitly chooses all-or-nothing behavior.
An OBS disconnect means downstream state is unknown, not all streams stopped.
Metadata failure must not manufacture a streaming failure/success; treat it as
its own result. Retries must be bounded and reconcile observed state first.

## Remaining original acceptance

- #9: complete legacy CLI migration/deprecation and qualified public-contract acceptance.
- #11: real new-user/Steam Deck, required CI/review and product/governance acceptance.
- #13: owner decides companion repository/lifecycle; actual one-command managed
  launch and SteamOS session/readiness proof, Kick viewer acceptance and device docs.
- #14: real Kick proof, provider API/metadata choices and independent-provider
  acceptance; focused ecosystem follow-up work belongs in the final consolidated
  checklist pending repository/product decisions. Local RTMP/schema tests are
  narrower evidence and do not complete that ecosystem ledger.

Keep these gates in the post-review consolidation. #51 monetization and Decky
Store research remain separate; no result here answers those journeys.
