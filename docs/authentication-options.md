# Provider authentication options

Research status: official documentation rechecked **2026-11-20 UTC**. This is a
separate, proposed authentication follow-up after the current implementation
campaign. It preserves the deferred intent of [#14](https://github.com/szmyty/obsgod/issues/14)
and [#40](https://github.com/szmyty/obsgod/issues/40), which were consolidated into
[#46](https://github.com/szmyty/obsgod/issues/46). It implements no authentication
and does not claim a successful provider account, phone, or Steam Deck test.
The bounded follow-up is [#89](https://github.com/szmyty/obsgod/issues/89).
Official-document URLs, timestamps, retrieval statuses and content digests are retained in
[the source manifest](evidence/authentication-sources.json); those digests bind
the cached documents, not a successful API or account test.
The unchanged [2026-11-14 manifest](evidence/authentication-sources-20261114.json)
is retained as history. The [proposed decision packet](authentication-decision-packet.md)
adds lifecycle/error handling, storage/account switching, phone tradeoffs and the
owner evidence plan. Its recommendation is Twitch public-device login first and
manual-key Kick until a confidential-client strategy or documented public/native
support is selected. **Design discussion and selection remain pending the owner**;
this research authorizes no authentication coding or public service.

OAuth can remove **manual stream-key entry**. OBS still needs the provider's
ingest URL and stream key to broadcast: Twitch documents the key in its RTMP
broadcast URL, and Kick's OBS setup requires both values. An API access token
is not a substitute ingest credential. See [Twitch broadcast URLs](https://dev.twitch.tv/docs/video-broadcast/#broadcast-urls-and-stream-keys)
and [Kick's streaming instructions](https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com).

## Twitch: documented device flow fits a Deck and phone

Twitch documents Device Code Grant for standalone devices, including consoles.
Its **public client** can obtain and refresh tokens without a client secret;
this is the appropriate candidate for a distributed plugin. The documented
authorization-code flow requires a client secret, so it should not be assumed
to offer the same secretless native-app route. Source: [Twitch OAuth flows](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow).

The proposed sequence is:

1. The owner registers a Twitch application and records its public client ID.
   Twitch's registration guide requires a verified developer account and 2FA;
   client IDs may be public, client secrets must remain confidential.
   [Registration prerequisites](https://dev.twitch.tv/docs/authentication/register-app/).
2. Decky Stream requests `channel:read:stream_key` through
   `POST https://id.twitch.tv/oauth2/device`. Display the returned `user_code`
   and make a QR code from the provider-returned `verification_uri`. The phone
   signs in and consents on Twitch; the Deck polls
   `POST https://id.twitch.tv/oauth2/token` with the device grant and respects
   the provider's interval and expiration. Keep `device_code`, tokens, and keys
   out of the QR, diagnostics, and public UI. Encoding that verification URL as
   a QR is the proposed presentation.
   [Device authorization and token endpoints](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow).
3. With the resulting user token, request
   `GET https://api.twitch.tv/helix/streams/key?broadcaster_id=<authorized-user-id>`.
   The user ID must match the token; the endpoint requires
   `channel:read:stream_key`. An app access token is insufficient. A `403` can
   mean the account must complete further streaming prerequisites, so account
   authorization alone is not proof of readiness.
   [Get Stream Key](https://dev.twitch.tv/docs/api/reference/streams/#get-stream-key).

The eventual implementation must handle token refresh, denial, expiration,
revocation, cancellation and account switching. Twitch requires validation at
startup and hourly while an OAuth session is maintained. Its public-device-flow
refresh tokens are single-use, so concurrent refresh must be serialized and the
replacement token saved safely.
[Token validation](https://dev.twitch.tv/docs/authentication/validate-tokens/),
[device-flow lifecycle](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow).
The [general refresh page](https://dev.twitch.tv/docs/authentication/refresh-tokens/)
describes public-token expiry as 30 days after generation; the device guide says
30 days inactive. It also retains older auth-code-only prose despite an explicit
public-client secret exception. Use returned expiry values, fail safely into
reauthorization and verify actual registered-client behavior later. Twitch's
documented pending response is HTTP 400 with a `message` field; generic RFC error
handling alone does not establish provider compatibility.

## Kick: key access exists; native secretless login needs resolution

Kick's app setup requires an account, 2FA, a registered application and a redirect
URL. It issues a client ID and client secret.
[App setup](https://docs.kick.com/getting-started/kick-apps-setup).

The documented user flow is **authorization code with PKCE S256**:
`GET https://id.kick.com/oauth/authorize`, then
`POST https://id.kick.com/oauth/token`. Authorization requires `state` and a
code challenge; code exchange requires the matching verifier **and
`client_secret`**. Refresh also requires that secret. PKCE does not remove the
documented secret requirement. No device grant was documented in the official
OAuth guide or documentation index retrieved on the research date; this is a
documentation finding, not proof that Kick can never support it.
[OAuth endpoints and requirements](https://docs.kick.com/getting-started/generating-tokens-oauth2-flow),
[documentation index](https://docs.kick.com/llms.txt).

Kick documents `streamkey:read` for the user's stream URL and key. Its
`GET https://api.kick.com/public/v1/channels` endpoint can return the authenticated
user's channel when called without filters; the response schema includes
`stream.url` and `stream.key`. The operation lists `channel:read`, while the scope
catalogue separately lists `streamkey:read`, and the page says returned data
depends on granted scopes. A later authorized account test must establish the
required scope combination, owner-only visibility and actual nonempty values;
do not infer key access from an app token's access to public channel data.
[Scopes](https://docs.kick.com/getting-started/scopes),
[Channels API and response schema](https://docs.kick.com/apis/channels).

A shared confidential secret shipped inside a downloadable plugin cannot remain
confidential. The research decision must therefore compare provider-confirmed
public/native support, an explicitly owned confidential token broker, or
user-supplied developer-app credentials. Retain manual-key setup as the fallback.
No broker, hosting, paid service, app registration or production credentials are
authorized or created by this document.

## QR codes represent different journeys

- **Provider device authorization:** Twitch's returned verification URL ties the
  phone's approval to the Deck's pending device request. The phone does not need
  to connect to the Deck's localhost or share its LAN.
- **A local setup-page QR:** opens a page where the user configures the Deck. It
  does not grant provider permissions or remove stream-key entry by itself.
- **Authorization-code login opened on a phone:** still needs a registered,
  reachable callback and a secure way to deliver the result to the initiating
  Deck. Phone `localhost` refers to the phone. Adding a QR to Kick's authorize
  URL alone does not supply a device flow, protect a client secret, or solve that
  return journey. Any pairing/session design requires its own review.

## Separate research mini-roadmap

1. **Provider feasibility and ownership:** record intended scopes, client types,
   registration owners and account prerequisites. Resolve Kick's public-client
   and secret requirements with authoritative evidence; identify any remaining
   question explicitly. Produce a Twitch/Kick go/no-go recommendation.
2. **Choose the phone journey:** specify Twitch device authorization and compare
   viable Kick callbacks/pairing approaches. Document QR contents, expiry,
   cancellation, account confirmation and fallback. Compare any broker's
   ownership, privacy, availability and costs before selecting or deploying it.
3. **Specify private state and recovery:** define backend-only credential storage,
   redaction, atomic token refresh, disconnect/revocation, key rotation and safe
   account switching. Preserve offline OBS/local recording and manual-key setup.
   Logging in or recovering credentials must never start a broadcast.
4. **Prepare an executable evidence plan:** cover real Deck plus phone approval,
   denied/expired/cancelled requests, missing scopes, ineligible accounts,
   reconnect/restart, refresh races, revoked/reset credentials and network loss.
   Require a deliberate Start before any future live ingest test. Record exact
   revisions, account/platform conditions and redacted outcomes; mocks cannot
   establish provider acceptance.
5. **Close research with an implementation packet:** selected design, unresolved
   provider gates, owner actions, test plan and separately reviewable work items.
   Authentication coding, provider registration and production-service changes
   remain future work. Main implementation and its hardware qualification do
   not depend on completing this optional login research.

Evidence currently **passed:** retrieval and comparison of twelve official
provider pages and two OAuth standards documents (HTTP 200). Two optional Kick
FAQ/changelog Markdown reads returned HTTP 403 and remain **unavailable**; no
access-control workaround was attempted. **Unrun:** provider authorization, registered-client behavior,
stream-key retrieval, phone callbacks/device approval, refresh/revoke behavior,
Steam Deck integration and live ingest. No successful end-to-end authentication
or account eligibility is claimed.
