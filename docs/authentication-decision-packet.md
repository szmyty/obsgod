# Proposed provider authentication decision packet

Status: **PROPOSED — owner design discussion and selection pending** under
[#89](https://github.com/szmyty/obsgod/issues/89). Research refreshed **2026-11-20 UTC**.
This specifies optional future work; it accepts no ADR and implements no login.
Manual server/key streaming and its device qualification remain independent.

The [existing feasibility guide](authentication-options.md) remains the short
entry point. The [current retrieval manifest](evidence/authentication-sources.json)
records exact URLs, timestamps, statuses and digests. The unchanged
[2026-11-14 manifest](evidence/authentication-sources-20261114.json) is historical.
Raw documentation bodies remain private; no provider account, client registration,
credential, phone/Deck or live-ingest test was used. No provider contact, public
service, hosting, deployment, payment or authentication code is authorized here.

## Proposed recommendation, awaiting owner selection

1. Keep current manual server/key entry fully supported, including offline configured operation. Logging in, saving credentials, checking readiness, disconnecting or recovery never starts broadcasting.
2. If optional login is selected, implement **Twitch public-client Device Code Grant first**, with the provider's verification URI rendered as a QR plus visible user code. This requires no shared client secret, Deck callback, phone-to-Deck connection or hosted broker. Registering the actual application remains an owner action after its owner/name is selected.
3. Keep **Kick on manual-key entry** until there is an owner-selected confidential-client strategy or documented provider public/native support. Current documentation does not justify a shared secret in the plugin or a secretless/device login. A hosted broker is a separate owned service with privacy, availability, maintenance and cost decisions; none is provisioned or selected here.

Provider token exchange belongs above the generic OBS layer. Generic OBS control
continues to receive its private ingest configuration; OAuth semantics do not
become requirements of reusable OBS control.

## Current provider findings

| Concern | Twitch | Kick |
|---|---|---|
| Registration | Owner developer account, verified email and 2FA; application-specific public client ID. Select public client type for the device flow. | Account plus 2FA, developer application, client ID/secret and registered redirect URI. |
| Supported candidate | Public Device Code Grant, explicitly intended for standalone consoles/devices. Public clients need no client secret and cannot assume the same secretless support for other Twitch grants. | Authorization code plus PKCE S256 and `state`; code exchange **and refresh explicitly require `client_secret`**. No device grant/public-native exception found in the retrieved OAuth guide and complete linked index. This is a bounded documentation finding, not a claim about all future support. |
| Authorization/token endpoints | `POST https://id.twitch.tv/oauth2/device`; `POST https://id.twitch.tv/oauth2/token` with device grant URN, client ID, scopes and private device code. | `GET https://id.kick.com/oauth/authorize`; `POST https://id.kick.com/oauth/token` with authorization code, verifier, exact redirect, client ID and confidential secret. |
| Key retrieval | User token with `channel:read:stream_key`; `GET https://api.twitch.tv/helix/streams/key`, broadcaster ID matching token user ID and matching Client-Id. An app token is insufficient. A 403 can mean further streaming eligibility steps. | Scope catalogue names `streamkey:read`; `GET https://api.kick.com/public/v1/channels` without filters returns current authenticated channel, schema contains `stream.url`/`stream.key`. Operation security lists `channel:read` and separately allows app access. A public app-token response does not establish private key visibility. Minimum user-scope combination, owner-only visibility and nonempty values remain unrun. |
| Validation/refresh | `GET https://id.twitch.tv/oauth2/validate` at startup and hourly while maintaining a session; verify client ID, scopes and user ID. Public-device refresh needs no secret, consumes the old refresh token and returns its replacement. Serialize refresh. | `POST https://id.kick.com/oauth/token/introspect` returns active/client/type/scope/expiry metadata. Refresh requests need the confidential secret and return both tokens. There is no documented Twitch-like hourly requirement in the retrieved guide. |
| Disconnect/revoke | `POST https://id.twitch.tv/oauth2/revoke` documents access-token revocation with client ID. Do not claim this automatically resets the ingest key or revokes every related refresh token; account connection removal is separate. | `POST https://id.kick.com/oauth/revoke`, optional `token_hint_type` for access/refresh; docs show a token query parameter. A future client must avoid logging request URLs and verify exact supported request behavior without exposing tokens. |

OBS still receives an ingest URL and stream key internally. OAuth obtains permission to fetch credentials; an OAuth token is not the OBS ingest key.

## Twitch lifecycle details to specify before coding

- Keep `device_code` private in the backend. Present only the returned provider verification URI and user code. Twitch's sample verification URI includes the user code in a `device-code` query field; that is distinct from the private `device_code` returned to the polling client. Validate the URI's HTTPS/provider origin; do not construct arbitrary links from backend errors. A QR of the provider-returned URI is an app presentation choice, not a separate grant.
- Bind every pending request to its initiating local session and generation. Display expiry/countdown, cancel and retry. Cancel stops polling and rejects late success; it does not silently unlink the existing account or change its stream destination. Use returned expiry/interval, not hard-coded sample numbers. Close/restart should discard an unapproved request; token persistence is a separate completed transition.
- Twitch documents HTTP 400 with `message: authorization_pending`, then `message: invalid device code` after consumption, and `message: Invalid refresh token` after a refresh token is reused. A parser must not assume every response uses RFC 8628's `error` field. RFC 8628 describes pending, slowdown, denial and expiry behavior; those are standards-based design/test cases, not freshly observed Twitch responses. Respect retry/backoff, stop on terminal responses and never poll indefinitely. Unknown or malformed responses yield a bounded safe failure.
- The device guide says access tokens last four hours and public refresh tokens are one-use with a 30-day inactive expiry. The general refresh page says public refresh tokens expire 30 days after generation and retains an older auth-code-only introductory sentence despite its explicit public-client secret exception. Preserve this discrepancy as a documentation limitation: use returned expiry values and safe reauthorization instead of promising exact refresh longevity. Validate actual registered public-client behavior later.
- After authorization, validate exact client/user/scopes, retrieve the matching broadcaster key, and show the account identity for confirmation. Neither consent success nor a nonempty key establishes streaming eligibility/provider reception. Handle 401, missing scope, account mismatch, 403 eligibility and empty key distinctly without echoing raw provider payloads.

## QR and phone tradeoffs

| Journey | What it solves | What remains |
|---|---|---|
| Twitch device QR | Phone logs into Twitch and approves the Deck's pending provider request; no LAN/callback service required. | Owner registration and actual public-client/account/phone tests; proper polling, expiry and account confirmation. |
| Current local setup page, optionally represented by QR | Easier text entry only if the browser can securely reach the Deck's setup service. | Phone localhost is the phone. A QR does not make the loopback-only current page reachable or create OAuth. An unauthenticated LAN configuration server is not an acceptable shortcut. |
| Kick authorize link opened on Deck | Can return to a registered Deck loopback callback in that same environment; official guide recommends `localhost` and documents a `127.0.0.1` redirect workaround. | Still needs PKCE/state and confidential client-secret strategy. The workaround is not evidence that any new redirect registration will be accepted. |
| Kick authorize QR opened on phone | Moves provider sign-in to a convenient keyboard. | Registered callback is followed on the phone. A phone loopback callback reaches the phone, not the Deck. Requires a separately designed reachable callback/pairing mechanism plus confidential-client ownership. QR alone does not solve either constraint. |
| User-created Kick developer credentials | Avoids distributing one shared project secret. | Much worse onboarding; every user registers/maintains an app and secret. Device storage protects against accidental disclosure, not a device owner extracting a distributed secret. Still not selected. |
| Project-operated Kick broker | Can keep a confidential secret on an owned server and pair phone consent to Deck. | Owner/domain/provider application, authenticated expiring one-use pairing, retention/security/incident response, uptime and costs. No service, account, spend or public endpoint is created automatically. |

## Proposed private state and recovery contract

This is a design proposal, not a new accepted ADR or storage migration. Reuse the current backend-owned private XDG settings/secrets authority and existing destination/account binding rather than creating a competing Decky/browser credential store. Owner-only directories/files, checked paths and atomic writes remain required. Filesystem permissions limit other users, not compromise of the same account. An OS keyring can be assessed later; do not assume an unlocked Desktop keyring exists in Gaming Mode or make it an undocumented install dependency.

- Public UI/status: provider, linked account label/ID as appropriate, granted-scope summary, readiness, expiry/reauthentication state and bounded public error code. No access/refresh token, private device code, stream key, client secret, raw OAuth URL payload or authorization header in UI readback, clipboard diagnostics, command arguments, environment dumps, logs, receipts or support exports.
- Private per-provider/account record: client ID/config identity, verified account ID, granted scopes, access token and expiry, refresh token, rotation/generation value and key/destination binding. A secret is never a source-controlled branding/config default. Tokens and fetched stream keys retain distinct purposes; managed OBS WebSocket password stays separate.
- One backend authority serializes refresh across processes, rechecks generation after locking, atomically saves the replacement access/refresh pair and prevents a stale response overwriting a newer account/rotation. Handle a crash between remote refresh and durable replacement by requiring reauthorization when needed; one-use refresh does not offer a guaranteed retry. Never persist credentials in temporary world-readable files.
- Authorization state and observed output state are separate. Expired/revoked login blocks new API operations and presents reauthorization; it must not silently stop an existing OBS output, start another one, substitute a different account/key or discard a manually configured working destination. Active/unknown output continues to gate account/destination changes using existing safe confirmation behavior.
- Account switch stages and confirms the new verified identity/key binding before replacement. Denial/cancel/failure leaves old settings intact. A destination/account change cannot silently reuse a key from the former account. Keep manual entry available and clearly label whether the stored destination came from manual configuration or an explicitly linked account.
- Disconnect distinguishes local credential removal, provider token revocation, account-connection removal and ingest-key reset. State exactly what succeeded. Offline revocation cannot be called successful: local removal and pending remote action must be honest. Deleting tokens is not proof that a separately saved OBS ingest key became invalid.

## Proposed lifecycle and failure matrix

These are design transitions for discussion, not new accepted API states. Every
row keeps observed OBS output state separate from account authorization.

| Condition | Proposed response | Credential/destination and output effect |
|---|---|---|
| No linked account | Offer manual entry and optional selected-provider login. | Existing manual configuration works; no implicit output. |
| Device authorization pending | Show provider QR/code, expiry and Cancel; bounded polling at returned interval. | Pending private code remains backend-only; saved account/key unchanged. |
| Denied, expired, cancelled or malformed authorization | Stop that request, show a public bounded reason and explicit Retry; discard late completion. | Preserve prior account/destination; no key replacement or broadcast. |
| Token pair received | Validate client, scopes and account, then retrieve matching user key and confirm identity. | Stage privately; successful consent alone is not ready-to-stream evidence. |
| Missing scope, account mismatch, key-read 401/403 or empty key | Explain reauthorization, account or eligibility action without raw response/secret disclosure. | Do not bind a public/app-token response or wrong-account key to the destination. |
| Linked and validated | Expose nonsecret identity/readiness; perform required session validation. | Only explicit existing Start can broadcast. |
| Expired access token or API 401 | Serialize one refresh, verify generation and atomically save replacement pair; bound retries. | No stale account/token overwrite; no automatic Start/Stop. |
| Refresh race, reused token, revocation or crash before replacement persistence | Reject stale work and request reauthorization when recovery cannot safely succeed. | Do not loop/replay indefinitely or fall back to another account's key. |
| Network loss/offline | Report unknown remote account validity, pause/back off API work and keep manual/local operation available. | Do not pretend revocation/validation passed or destroy an existing configured destination. |
| Account switch while active/unknown output | Apply existing safe destination-change guards; cancel leaves prior account intact. | No mid-stream silent destination replacement, key reuse or implicit restart. |
| Explicit Disconnect | Distinguish local removal, successful remote revocation and remaining owner actions. | Preserve unrelated settings/media; ingest-key reset and stopping output are separate explicit actions. |

## Future evidence and exact owner actions

All provider/account/device cases below remain unrun and do not block this documentation research. Record exact candidate/source revision, provider app/client type, scopes, device/phone OS/browser/network and redacted results.

1. Owner chooses whether to add Twitch-only optional login first; chooses developer-app owner/name and intended distribution. Owner registers Twitch public app with 2FA and supplies the nonsecret client ID. No shared project secret is needed for that selected public grant.
2. Test real Deck + phone authorization: QR/code match, correct account consent, accepted/denied/expired/cancelled/retried flow, returned interval/rate limiting, stale success after cancel/restart and account mismatch. A phone need not share the Deck's LAN for provider device approval.
3. Confirm `channel:read:stream_key`, matching broadcaster ID, missing scope/401/403 eligibility, key retrieval and UI/log/clipboard redaction. Deliberate Start plus separate provider viewer verifies ingest only after setup; authorization alone is not live proof.
4. Exercise token validation, serialized concurrent refresh, rotation/crash/restart, revoked/reset credentials, account switch, private permissions/unsafe-path refusal and offline manual/local-recording fallback. Verify no setup/login/recovery action starts output or implicitly stops a preexisting stream.
5. For Kick, owner first selects manual-only, user-owned developer credentials, or a separately owned broker/public-native option. The API scope/key-visibility test then uses an explicitly authorized owner app/account; do not probe other accounts, silently register apps, contact the provider, or deploy a service as research.
6. Discuss/select the final design with the owner, record the decision and remaining provider limitations, then prepare separately reviewable implementation issues. Research completion is not a successful authentication, device, account-eligibility or ingest test.

## Sources retrieved now

Twelve public provider pages and two standards documents returned HTTP 200. Two optional Kick FAQ/changelog `.md` reads returned HTTP 403 and are retained as unavailable; no access control workaround was attempted. Provider docs constrain supported provider behavior; RFC guidance is a design baseline, not proof that every provider implements every response.

- [Twitch device flow](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow)
- [Twitch registration](https://dev.twitch.tv/docs/authentication/register-app/)
- [Twitch stream key endpoint](https://dev.twitch.tv/docs/api/reference/streams/#get-stream-key)
- [Twitch validation](https://dev.twitch.tv/docs/authentication/validate-tokens/), [refresh](https://dev.twitch.tv/docs/authentication/refresh-tokens/), [revocation](https://dev.twitch.tv/docs/authentication/revoke-tokens/)
- [Twitch ingest URL/key](https://dev.twitch.tv/docs/video-broadcast/#broadcast-urls-and-stream-keys)
- [Kick OAuth, refresh, introspection and revoke](https://docs.kick.com/getting-started/generating-tokens-oauth2-flow)
- [Kick app setup](https://docs.kick.com/getting-started/kick-apps-setup), [scopes](https://docs.kick.com/getting-started/scopes), [channels](https://docs.kick.com/apis/channels), [official index](https://docs.kick.com/llms.txt)
- [RFC 8628 device authorization](https://www.rfc-editor.org/rfc/rfc8628.txt), [RFC 8252 native applications and distributed secrets](https://www.rfc-editor.org/rfc/rfc8252.txt)
