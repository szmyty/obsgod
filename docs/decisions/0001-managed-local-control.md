# 0001: managed local control and output safety

Status: **Existing behavior, documented**. This records the implemented local
design and owner's no-silent-broadcast/privacy requirements; it does not certify
hardware or approve publication.

## Context and choice

Desktop and Decky need the same output state, lifecycle guards and private
configuration. They invoke `obsgod deck` through JSON. Go owns protocol/control,
serialized operations and bounded readiness; adapters do not duplicate WebSocket
logic. Managed OBS is a graphical user Flatpak with isolated configuration and
its built-in authenticated WebSocket. Ordinary OBS profiles/processes remain
separate; normal operation does not disable SteamOS read-only protection.

Start needs valid rendered capture and fresh advancing bytes. Requests alone
cannot turn the indicator green. Recording/replay, reconnect, idle and recovery
do not authorize broadcasting. Cleanup affects only newly started output;
destructive changes need observed safe state. Game-only uses verified app capture
or intentional idle, never silent screen fallback.

## Consequences and evidence

One control boundary keeps adapters small and assertions testable. Stock OBS
still needs a supported graphical/session environment. Native/protocol fixtures
cannot prove SteamOS/Flatpak/Gamescope behavior. Viewer audio/video, controller,
sleep/session/performance and device install/recovery remain target evidence.
See [device checklist](../m3-device-acceptance.md) and
[architecture](../../ARCHITECTURE.md).
