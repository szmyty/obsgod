# Microphone and stream mixer

The Steam Deck has a built-in microphone. Decky Stream can mix an available
microphone with system/game audio in its managed OBS instance. Headset, USB and
Bluetooth inputs appear when the system exposes them. Bluetooth routing and
hardware behavior need a local clip test on the actual device.

Use **Audio controls** in the Decky panel or Desktop setup. Enable the microphone,
choose an observed input, check its meter, and explicitly unmute when ready.
Changing the input or enabling it starts muted unless an explicit unmute was
included. A saved preference and a confirmed OBS mute state are shown separately;
an unavailable control connection means actual mute is unknown.

These controls change OBS stream/recording audio. They leave the system volume,
default input and system mute unchanged. System mute can prevent an unmuted OBS
source from receiving sound. Game-only video does not imply per-application audio.
Listen to a saved local clip with headphones before broadcasting.

## Device changes and Steam Deck models

Actual source availability drives the UI. A vanished selected microphone remains
muted/unconfirmed, rather than silently switching to an unmuted input. Following
the system default also latches mute after a detected route change; check and
unmute explicitly after connecting or disconnecting a device.

Valve documents that the LCD model's built-in microphone is unavailable when the
3.5 mm jack is occupied. The OLED model supports its built-in mic with wired
headphones. Model detection is guidance: it does not prove jack state, headset
microphone availability or a Bluetooth route. Use the observed device list and
local test instead of relying on the model name alone.

Sources: [Valve technical specifications](https://www.steamdeck.com/en/tech)
and [Steam Deck audio troubleshooting](https://help.steampowered.com/en/faqs/view/4C18-08B5-DEC9-3AF4).

## Hold to talk

Optional hold-to-talk uses a short private lease while the panel control is held.
It is a focused panel action, not a global Steam/controller chord. Release,
focus loss, panel unload and lease expiry request mute without stopping a stream.
If OBS control disappears, the app cannot guarantee physical mute and shows that
uncertainty. The initial press requires an available, explicitly armed input.
Keep using ordinary mute until the actual controller/device acceptance passes.

## Configuration and compatibility

Non-secret preferences live in private `mixer.json` in the managed XDG config
store. Once created, this versioned mixer preference takes precedence over the
legacy profile's microphone boolean for managed audio behavior. Existing profile
settings and credential binding hashes are preserved. Stream keys and OBS
passwords are never part of this file. Private input identifiers/labels stay in
the local device UI; support exports project allowlisted state only.

```sh
printf '%s\n' '{"action":"devices"}' | obsgod deck mixer
printf '%s\n' '{"action":"configure","preferences":{"microphone_enabled":true,"microphone_muted":true}}' | obsgod deck mixer
printf '%s\n' '{"action":"configure","preferences":{"microphone_muted":true}}' | obsgod deck mixer
```

Use [device acceptance](m3-device-acceptance.md) and the
[completion review checklist](completion-review.md) for LCD/OLED, wired/USB/
Bluetooth, system-mute, sleep/resume, local recording and remote-viewer proof.
Local fixtures cannot establish those hardware outcomes.
