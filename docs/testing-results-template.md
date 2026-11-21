# Our testing session record

Use this alongside the [testing booklet](testing-booklet.md). Keep the working
record private. We will fill it together; unknown details remain unknown until
observed. No device test has passed merely because this template exists.

## Session identity

- Date/time and local timezone:
- Candidate source revision, ZIP SHA256 and version: copy from the active booklet candidate card.
- Deck model (LCD/OLED):
- SteamOS version/channel:
- Steam version:
- Decky version/channel:
- OBS user Flatpak version/ref and GStreamer details:
- Game and connection type:
- Actual microphone/headsets available:
- Saved settings/media preserved and rollback candidate, if available:

## One checkpoint at a time

```text
Step:
Result: PASS / FAIL / SKIPPED / UNAVAILABLE / UNRUN
What I expected:
What I saw or heard:
Exact visible error, if any:
```

A page with several actions needs separate observations. For example, a clip
saved, a playable moving file, audible system sound and audible microphone are
separate facts. A green dot and a working provider viewer are also separate.

## Running journal

| Step / detailed case | Exact candidate | Result | Observation / reason | Next action |
| --- | --- | --- | --- | --- |
| Not started | Not yet recorded | UNRUN | No device observation recorded | Begin booklet step 1.1 |

If hardware is missing or a branch was deliberately omitted, record that reason
rather than filling in a pass. Actual loader lifecycle remains pending until its
installation, reload/reconnect, replacement and removal observations are complete.

## If we find a problem

Record the failed step, last confirmed stream/recording/replay state and filtered
console text before changing sessions. Share only what is needed for diagnosis;
keys, passwords, private setup tokens, raw settings/backups and wipe-export TARs
stay private. A private clip or cropped photo can help when requested.

I will record the repair, its checks, the replacement candidate and the steps to
repeat. Keep earlier rows tied to their original build; do not carry their passes
forward automatically. Current owner testing does not establish independent
new-user adoption or acceptance of untested hardware/platforms.
