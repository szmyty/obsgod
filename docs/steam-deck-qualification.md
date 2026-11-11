# Steam Deck preview qualification

Qualification is in progress. The final release notes identify the exact source
revision and artifact checksums. Do not use an earlier passing check as evidence
for later source. The preview remains separate from a stable v1 release.

## Required evidence

- Go unit/protocol tests, race detection, vet and reachable-vulnerability scan.
- Desktop setup HTTP security and installer safety checks.
- Decky typecheck/build, status-indicator tests and browser rendering checks.
- Reproducible package checksums and a clean-home install from the actual archive.
- Real Linux OBS with synthetic PipeWire video/audio, local recording, local RTMP,
  repeated start/stop, frame dimensions and audio content.
- Real SteamOS / AMD VAAPI / controller / Kick viewer acceptance, explicitly
  unavailable in the cloud runtime and retained under #10.

No user stream key, live provider account or paid resource is used by cloud tests.
