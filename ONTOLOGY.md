# Domain vocabulary

Use these terms consistently in the CLI, setup, Decky panel, tests and evidence.
The [architecture](ARCHITECTURE.md) defines responsibilities; feature guides give
concrete fields and commands.

| Term | Meaning |
| --- | --- |
| Decky Stream | Owner-selected working display name; not a compatibility-ID migration. |
| `obsgod` / `OBSGod` | Existing CLI/module/storage namespace and Decky identity. Future `decky-stream` migration is explicit. |
| Generic connection | Configured endpoint for an existing OBS; does not imply runtime ownership. |
| Managed OBS | Isolated graphical OBS instance controlled by the Deck integration; ordinary OBS remains separate. |
| Control connection | Authenticated WebSocket. Reachable listener, frontend readiness and streaming are distinct. |
| Setup authorization | Local page token/origin checks; distinct from OBS password and destination key. |
| Connection profile | Named generic CLI connection/configuration overlay. |
| OBS profile | OBS's native output/service settings collection. |
| Stream quality profile | Managed resolution/FPS/bitrate/encoder/audio settings; not an account or connection profile. |
| Desired state | Requested setting/action, possibly pending or rejected. |
| Observed state | Current OBS/runtime fact with observation context, not request acknowledgement. |
| Pending / busy | An operation is running; controls respect its scope and confirmed output state. |
| Unknown / stale | Failed observation or data from an earlier connection/output epoch; cannot prove idle or successful Start. |
| Ready | Operation-specific evidence. Streaming requires valid capture and fresh advancing bytes, not just a socket. |
| Streaming | OBS reports active output with current transmission evidence; not provider viewer proof. |
| Viewer proof | Separate receiver confirms expected picture and audible audio for the exact candidate/destination. |
| Recording | Local output with independent lifecycle and finalized file. |
| Replay buffer / save | Bounded output and explicit save; success needs a newly finalized observed file. |
| Clip / media entry | Validated indexed recording/replay item with path/provenance, not an arbitrary Videos file. |
| Retention preview | Exact eligible owned deletion set; later changed/unsafe files are not covered. |
| Game-only capture | Verified app-filtered video, not per-app audio or automatic desktop fallback. |
| Screen capture | Explicit supported whole-display selection, including visible UI. |
| Idle scene | Intentional black/text/local-media output without usable game frames; does not authorize broadcasting. |
| Imported media | Private validated hashed local copy with rights acknowledgement, not a license grant. |
| System audio | Configured desktop/game source or monitor; may include other applications. |
| Microphone | Input source whose availability can change with headset/device/session routing. Hardware existence is not availability. |
| Stream mixer | OBS-source gain/mute/device preferences; must not alter system volume or other applications. |
| Push-to-talk lease | Short-lived held-control permission to unmute; missing renewal releases safely. Adapter controls remain subject to qualification. |
| Recovery | Bounded restoration of selected runtime/sources; no authority to broadcast, erase settings or own unrelated output. |
| Provider preset | RTMP(S) guidance/validation, not OAuth or provider account integration. |
| Destination | RTMP(S) server and separate private key; changes respect current output state. |
| OBS core | Reusable provider-neutral control and workflows. |
| Creator / StreamGod | Optional orchestration above the core. Separate-repository disposition remains an owner choice. |
| Compatibility adapter | Retains older command/output behavior beside a new versioned facade. |
| API version | Documented operations/types/errors/JSON/lifecycle contract, not a published stable product release. |
| Candidate | Exact source/artifact bytes prepared for review; distinct from release/installed runtime. |
| Qualification receipt | Revision-bound commands/platform/outcomes: passed, failed, skipped, unavailable or unrun. |
| Adoption proof | Actual consumer's candidate install/configure/local-audio/viewer/update/recovery/uninstall journey. |
| Owner gate | Missing fact, permission, creative/account action or target test with a named concrete next action. |
| Superseded / consolidated | Transfers intact remaining criteria/dependencies to a linked checklist; does not mean passed. |

See [configuration](docs/configuration.md) and
[release readiness](docs/release-readiness.md) for exact contracts and evidence.
