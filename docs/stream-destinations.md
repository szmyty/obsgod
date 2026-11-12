# Stream destinations and local OBS recovery

Decky Stream controls a private managed OBS instance. Destination guides support
Kick, Twitch, YouTube and custom RTMP(S); they do not add OAuth, create accounts,
claim viewer acceptance or broadcast automatically. The local core can use a
local RTMP endpoint without a new service account.

## Destination setup

1. Stop streaming and recording, then close idle managed OBS in Desktop Setup.
2. Select a destination guide. Selecting a guide changes its help only; it never
   overwrites a server URL or an entered key.
3. Copy the intended account/event server URL and its separate stream key into
   the local form. Prefer the provider's RTMPS transport where supplied. Do not
   append a key, user information, query parameters or credentials to the server.
4. Save. An unchanged server with a valid settings/credential binding can preserve
   its saved key when the key field is blank. **A different server requires an explicit key for that destination**;
   a previously saved key is never automatically reused for a new server.
5. Make a local clip, then explicitly start the broadcast and verify picture and
   sound from another device at the intended destination. OBS output bytes and
   a green local status do not prove that viewers can see or hear the stream.

| Destination | Account and event preparation | Server selection |
| --- | --- | --- |
| Kick | Use Creator Dashboard → Channel → Stream URL and Key; set the stream title and category. | Copy your own dashboard URL. No account-specific URL is guessed. |
| Twitch | Use the Creator Dashboard's stream settings and primary stream key. | The explicit **Use recommended server** action offers the secure default from Twitch's public ingest list. You may paste another official ingest. |
| YouTube | Enable live streaming and select/create the intended event in Live Control Room. Check whether the event requires a separate Go Live confirmation. | Use the lock icon in Stream settings to copy that event's RTMPS URL and key. No event-specific URL is guessed. |
| Custom RTMP(S) | Follow the destination's instructions. Plain RTMP remains supported for local/offline workflows. | Paste the server and key separately. |

## Local connection and password recovery

The managed local control endpoint is `127.0.0.1:4457`. Its generated password
is separate from the stream key. The legacy `OBSGod` plugin/profile/storage IDs
remain compatibility identities; ordinary OBS configuration is separate.

- **Refresh connection details** reports public endpoint/process facts without
  returning any password. **Test connection** reads the server's password
  challenge, authenticates using the stored local password and verifies the
  managed profile/collection/output. It refuses an authentication-disabled or
  unrelated listener. It never launches OBS or changes an output.
- To change a password, first use **Close idle OBS / apply settings**. If an
  authentication mismatch prevents safe managed shutdown, inspect and close the
  managed window yourself. Active, recording, unknown or occupied-control-port
  instances cannot have their credentials changed.
- Confirm the local password update, then either enter a new 12–128 byte
  password without control characters or generate a private random password.
  Both private managed WebSocket settings and CLI credentials are synchronized;
  a failed credential write restores the previous WebSocket settings. Unsafe
  file links and directory links are refused.
- A saved change is reported as **awaiting verification**. Open managed OBS,
  then use **Test connection** to verify reconnection. A file write alone is not
  an OBS/device success receipt. Changing a password does not start broadcasting.
- A partially unreadable or corrupt stream/credential store must be repaired in
  Desktop setup first. Do not delete ordinary OBS configuration, shared sockets
  or recovery markers to work around a control failure.

The CLI exposes the same local operations as JSON:

```sh
obsgod deck connection-info
obsgod deck test-connection
```

`obsgod deck change-obs-password` reads exactly one confirmed request from stdin;
it does not accept a password argument. Prefer the local Desktop form for manual
passwords so secrets stay out of shell history. Automatic generation can be
requested without exposing a secret:

```sh
printf '%s' '{"confirm":true,"generate":true}' | obsgod deck change-obs-password
```

No reveal endpoint was added. Entered fields are masked and stored credentials
are absent from ordinary connection details, diagnostics and console copies.

## Documentation provenance and remaining evidence

Official sources checked 2026-11-12:

- [Kick setup guide](https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com):
  response SHA256 `678187243336c6f9af82abe1bfaf333554d82845515de0500bb46a91109114b3`.
- [Twitch broadcast documentation](https://dev.twitch.tv/docs/video-broadcast/):
  response SHA256 `6b83ae193098f03f168b997facccb2ec2e435a966941a65b3ff08313fcf113a2`.
- [Twitch public ingest list](https://ingest.twitch.tv/ingests): secure default
  `rtmps://ingest.global-contribute.live-video.net/app/{stream_key}`; the preset
  strips `/{stream_key}` and sends the key through OBS's separate private field.
  Response SHA256 `c9db1a5636ab6ef189f74c31d8271beb94fa3e7fed908f49c94193673cb0ad42`.
- [YouTube RTMPS instructions](https://support.google.com/youtube/answer/10364924?hl=en):
  response SHA256 `3255dd9143ac9df33b59562b8bdafeab9814e19bb7fb492e2a001ead4c48f702`.

Sources can change; an account's current dashboard remains authoritative.
Actual Steam Deck password rotation/reconnection and separate-device audio/video
at each provider remain unrun until an authorized owner/tester records exact
versions, revision, artifacts and results. Protocol fixtures and cloud tests do
not close those criteria.
