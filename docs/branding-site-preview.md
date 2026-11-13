# Documentation and landing preview handoff

Issue #43. The static preview follows current candidate behavior while keeping
actual publication and hardware qualification separate. It has no hosted
backend, analytics, remote fonts, automatic update install or embedded funding
checkout. Support buttons come from the reviewed repository metadata; no new
wallet/payee is introduced here. Proposed art is reviewed separately and does
not change the preview's existing visual baseline.

## Build and review locally

From the same clean source revision as the candidate, run:

```sh
python3 scripts/build-site.py --output dist/site
python3 scripts/build-site.py --output dist/site --check
python3 site/tests/test_build.py --output dist/site-tests/build
python3 site/tests/browser.py --browser /usr/bin/chromium
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist/site
```

Open `http://127.0.0.1:8000/`. The last command serves a local preview and should
be stopped when review ends. The build itself needs no network or browser.
The browser check uses the existing pinned Playwright environment and the stated
Chromium executable; capture their actual versions in the result. A build made
from dirty source says so. `site-manifest.json` binds source revision, dirty state,
input hashes, output hashes and link checks. `--check` verifies without rewriting.
No command above deploys a site or publishes an environment/runtime release.

The nine pages cover landing, install/first audible clip/viewer check, providers,
configuration/CLI/environment/XDG/capture, profiles/local clips/microphone/health,
updates/repair/rollback, uninstall/reset/wipe, troubleshooting and privacy.
Release availability is deliberately described as candidate source. A newer
source page must not imply that an older downloadable archive has its features.

## Evidence and limits

Build tests cover deterministic bytes, escaped metadata, valid local links and
anchors, refused remote CSS/unsafe support URLs, stale output and preservation of
unrelated/symlink output. Browser tests cover five mobile/Deck/desktop viewports,
keyboard skip navigation, overflow, unchanged funding destinations, missing
wallets, reduced motion and no external requests. These are browser receipts,
not actual Deck controller, hosted TLS, provider, payment or wallet receipts.
External HTTPS link syntax is checked; that is not a live availability audit.

Keep generated reports/screenshots outside the served HTML directory. Prepare
the final archive from a clean revision only after synchronized product changes;
retain its manifest, ZIP checksum and browser evidence with the candidate.

## Owner facts and deployment approval packet

Before requesting publication approval, fill these actual facts into the final
owner issue: canonical organization/repository, domain and DNS owner, hosting
destination/account owner, public contact/support channel, approved brand kit,
exact source/site ZIP digest and runtime artifact/qualification links. Do not
add a fictional email, domain, download or promised platform support.

Use the existing source preview as the concrete review result. A proposed static
deployment may use an owner-selected free host, after verifying available account
permissions, HTTPS, custom-domain behavior, cache headers, content-security
policy and rollback. No service is provisioned or selected by this packet.
Deployment needs explicit owner authorization, even when it costs nothing.

Before deployment, review any workflow side effects and require a manual gated
publication path. Bind it to the exact approved source/ZIP; do not deploy mutable
PR head implicitly. Validate the deployed HTTPS origin, all relative links,
mobile/Deck layouts, contact links, version/checksum download links, reduced
motion and keyboard navigation. Save a post-deploy receipt and verify rollback
to the prior approved site. Payment destination verification remains the owner's
separate action and does not make the local streaming core depend on payment.

Open gates: organization/contact/domain/hosting facts, creative approval,
qualified runtime download, native controller review, publication authorization
and actual hosted/deployment/rollback evidence.
