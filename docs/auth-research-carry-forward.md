# Research optional Twitch/Kick login and phone QR setup

Issue-body template for the actual new repository. Origin:
[szmyty/obsgod#89](https://github.com/szmyty/obsgod/issues/89); preserve its full
body/criteria in the portable history. Use the real new issue number after
creation. No OAuth or provider application has been implemented by migration.

Manual stream-key setup remains supported and independent of this research.
The [existing decision packet](authentication-decision-packet.md) proposes
Twitch public-client device authorization/QR, while Kick remains manual-key
pending a supported public/confidential-client approach. Recheck official
provider endpoints, scopes, ownership and current terms before a design decision.

- [ ] Reconcile every original szmyty/obsgod#89 criterion and retained szmyty/obsgod#14/#40 auth intent.
- [ ] Verify Twitch device expiry/deny/cancel/polling, stream-key authorization
  and account/registration ownership without assuming a browser session.
- [ ] Resolve actual Kick PKCE/client-secret and key-access requirements; do not
  embed a shared confidential secret or invent a supported device flow.
- [ ] Compare provider QR, local setup-page QR and callback/pairing approaches,
  private token storage/refresh/revocation, offline fallback and any broker cost.
- [ ] Discuss/select the design with the owner before authentication coding,
  registration, external hosting, spending or actual account/Deck/phone flows.

OBS still needs the provider's ingest server/key internally. Research and a QR
diagram are not successful authentication, account permission or live-ingest proof.
