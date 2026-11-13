# Audio and session recovery

After an explicit stream, local test, recording or replay start, a bounded local
observer follows verified default/game audio devices. It changes only the existing
OBS input's device selection. User mute, gain, track routing, monitoring and system
volume are preserved. An output monitor is never chosen as a microphone.

The observer confirms the managed profile, scene collection and active output
before changing a route, and rechecks under the same control lease used by manual
actions. Unknown observations permit no route mutation. Three failed cycles, with
bounded backoff, stop automatic recovery and expose an escalation message.
Connection restoration never launches OBS or starts/restarts broadcasting.

**Retry bounded audio/capture recovery** in the panel (or `obsgod deck
retry-recovery`) explicitly reattaches observation to already-active output.
For game-only video, the independent capture observer keeps the selected idle
screen on unsupported/ambiguous capture; it never substitutes the entire display.
If state is unknown, inspect managed OBS or use the separate output Stop controls.

The same observer checks the configured free-space reserve for local output.
Crossing it finalizes an active recording and stops unsaved replay buffering.
Saved media remains on disk, and a broadcast is not stopped by this storage limit.
The reserve and its behavior are visible in Desktop storage settings; no automatic
retention deletion is enabled. Do not leave an unverified recording unattended.

Native Linux fixtures can exercise real PulseAudio route changes and OBS mixer
preservation. Actual Steam Deck headset/Bluetooth, sleep/wake, SteamOS session,
Flatpak/OBS33, controller, AMD load/battery and game/Wayland behavior still need
versioned device evidence. A successful cross-build is not such evidence.
