# Stream health

The health check reads the managed OBS instance on this device. It never starts
OBS, starts or stops a broadcast, contacts a streaming provider, changes quality
settings or uploads telemetry. A failed check means **unknown**, not stopped.
Use the normal Stop action if output needs to stop.

The check takes two bounded observations about 350 milliseconds apart and reports
their observation time, sample length and expiration time. A report expires after
eight seconds. A client must discard an expired result or visibly mark it stale;
refreshing cannot turn an unavailable observation into a measured zero.

| Observation | Meaning and limit |
| --- | --- |
| Bitrate | Decimal kilobits per second from the increase in OBS stream bytes over the local sample interval. It includes the encoded output, so it is not exactly the configured video bitrate. |
| Stream dropped frames | Percentage of stream-output frames OBS dropped during this sample. It is a signal to inspect upload stability, not a diagnosis of an ISP or provider. |
| Encoding skipped frames | Percentage of OBS output-thread frames skipped during this sample. Inspect encoder and game load before changing settings. |
| Rendering missed frames | Percentage of OBS render-thread frames missed during this sample. Inspect game/scene load and selected FPS. |
| CPU, FPS, render time, memory | The numeric statistics OBS exposes for itself. These are not a whole-system CPU, GPU or battery measurement. |
| Available recording space | OBS's observation at its current recording location, not a guarantee that a long recording will fit. |
| Audio and capture | Short local observations. Silence can be legitimate; visible pixels do not prove the intended game or an audience received them. |
| Reconnecting | OBS's current reconnect flag. This interface does not supply a trustworthy total reconnect count. |
| GPU and provider reception | Unknown. OBS statistics do not establish viewer picture, sound or network delivery. |

Missing fields, an output restart, a counter decrease, an invalid value or an
insufficient frame/sample interval leave the affected rate unknown. Stopped
output has no current streaming bitrate. Incomplete observation does not reset
the stream state or hide a possibly active broadcast.

Advice describes the observation: reconnecting or nonadvancing bytes, frame
loss, high OBS CPU, low rendering FPS, muted/unavailable audio, unconfirmed
capture or less than 1 GiB at OBS's recording location. It never changes encoder,
resolution, FPS, bitrate, microphone policy or system volume automatically.
Make quality changes only through the idle-only settings/profile workflow.

All report fields are allowlisted numeric values, fixed status values or fixed
advice. They omit server URLs, stream keys, device names, game titles, custom
messages and media paths, so the report is suitable for the redacted support
bundle. No background collection or external analytics service is required.

The protocol and counter tests cover missing/zero values, degradation, stalls,
reconnection, resets, stale/future samples and redaction. Native Linux OBS can
exercise the real stats interface; it does not qualify SteamOS, Gamescope, OBS33,
AMD/Deck performance, Bluetooth, controllers or viewer reception. Those hardware
and provider checks remain acceptance gates, including adverse upload/load tests.
