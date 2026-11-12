# Offline landing and documentation preview

Milestone 2 / [#43](https://github.com/szmyty/obsgod/issues/43). The working name
is Decky Stream; final organization, Identity artwork, domain and hosting are
pending. This is a neutral provisional design, not accepted final branding.
It publishes nothing and offers no unqualified new binary download.

## Build and inspect

Use the repository's pinned Node 24.19.0 when checking generated support input.
The site builder itself requires only Python 3.12 and its standard library:

    node scripts/generate-support.mjs --check
    python3 scripts/build-site.py
    python3 scripts/build-site.py --check
    python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/site

Open http://127.0.0.1:8765/ locally. Stop the server with Ctrl+C. The files in
dist/site contain only local HTML/CSS/JavaScript and work over this loopback
server without an external network. Direct file opening depends on browser
policy; managed Chromium blocks file:// navigation here, so it is not qualified.
External source/support links still require connectivity; clipboard support
depends on browser context, with selectable addresses as a fallback.

The builder reads:

- product.json for the display name and canonical source repository.
- Hand-authored HTML under site/content/, page metadata in site/pages.json,
  one layout template, and local CSS/JavaScript assets.
- The exact generated steamdeck/decky/src/support-data.mjs manifest, parsed as
  JSON without evaluating JavaScript. Its source of truth is
  .github/FUNDING.yml and public receiving-address metadata in support.json.

There is no Markdown parser, remote theme, analytics, external font, runtime
funding fetch or remote QR service. No secrets/configuration/qualification logs
are copied into the output. Wallet destinations are hidden while unconfigured.
The shared UI's QR workflow remains in the plugin; this static preview displays
configured public addresses and offers a copy action.

site-manifest.json records source revision/dirty status, input hashes and exact
output hashes. No current timestamp enters generated output, so unchanged
inputs/revision/status produce identical bytes. The builder validates all local
links and anchors, HTTPS syntax for external navigation, local-only assets, an
explicit document language, one main landmark and one h1 per page. It escapes
metadata and refuses stale output during --check, unrelated existing output
files and symlink destinations. External link availability is separate from the
offline syntax check; configured funding handles do not prove payout readiness.

## Content and review boundaries

Eight pages cover landing, installation/first audible clip, destinations,
CLI/config/XDG/capture/audio, updates/repair, uninstall/reset/wipe, troubleshooting
and privacy/security/support. They distinguish M2 source commands from older
installed previews and link the exact source and current qualification status.

Maintained checks use the same builder and real browser output:

    python3 -B site/tests/test_build.py
    python3 -B site/tests/browser.py --browser /usr/bin/chromium

The first runs deterministic and unsafe-input/output cases; the second checks
all eight pages at five mobile/Deck/desktop viewports and writes screenshots and
a structured report under dist/site-tests. Both accept an --output directory.

Review at least mobile portrait, Deck-sized 1280×800/800×1280 and desktop
viewports, with keyboard focus, zoom, long text and no external requests.
Browser viewport checks do not establish Steam Deck/controller acceptance.

The Documentation preview workflow only checks/builds and uploads a seven-day
GitHub Actions artifact with read-only repository permissions. It does not
deploy, change Pages settings, create a domain/account or publish a release.
CI execution remains subject to the account's current billing/access state.

## Concrete publication gate

Before any site publication, the owner must select the organization/final name,
approve the Identity consumer assets/rights, choose the canonical domain and
hosting/account, approve exact site/release revisions and artifact destinations,
and supply any final public support/contact facts. Actual qualified product
media and release-specific download hashes replace the present workflow
illustration/source-only path only after that evidence exists. No fabricated
testimonials, user/revenue counts, store admission or affiliation are included.
