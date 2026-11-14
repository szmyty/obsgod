# Decky package, storage and dependency setup checkpoint

Issues [#76](https://github.com/szmyty/obsgod/issues/76),
[#77](https://github.com/szmyty/obsgod/issues/77) and
[#78](https://github.com/szmyty/obsgod/issues/78) are implemented in draft
[#90](https://github.com/szmyty/obsgod/pull/90), after #73 → #74 → #75.
They remain open for review and their recorded acceptance limits. Nothing was
merged, published, deployed or migrated by this batch.

**Qualified batch source:** `7e539ca8bcf237e3da1d0c42c5045ea44d638973`.
Later evidence documents do not relabel the artifact or inherit qualification
for future source changes. This is focused integration evidence, not the final
campaign matrix in #85 or actual Steam Deck acceptance in #86.

## Result

- A [primary standard Decky builder](decky-package.md) produces one complete
  compatible `obsgod-decky.zip`, without requiring the paired Desktop app.
  The ZIP includes backend modules, Go/native helpers, panel, optional private
  browser setup, notices and deterministic preferred SDK/native source archives.
- [Decky-owned metadata/jobs/log paths](decky-storage.md) surround one retained
  canonical XDG settings/secrets/state/control-lock store. There is no secret
  copy, OBS profile move or media relocation, and older CLI clients share the
  same managed control namespace.
- [Dependency setup](dependency-setup.md) has native Install/Later consent,
  background progress, cancellation/retry and panel/backend recovery. It checks
  actual UID/session, scope, active refs/extension metadata and Flathub identity.
  Setup never launches OBS or broadcasts; it cannot race a legacy Start through
  the shared control lease. New Start/local-test actions require fresh dependency
  readiness, while explicit Stop remains based on observed output state.

Native destination/key editing, selected aurora artwork and broader UI polish
remain #79–#81. The normal Decky replacement/removal consolidation is #82.
The optional included browser setup is usable for private configuration; it does
not invoke the legacy paired installer or start broadcasting in plugin mode.

## Exact artifact and tools

Two independent clean builds produced identical canonical ZIP bytes:

```text
Version: 0.1.0-deck.9
Platform: linux/amd64
Source: 7e539ca8bcf237e3da1d0c42c5045ea44d638973
SHA256: 80b956ea208b465626640a8ad432185aca5455192c367bd50e38d6608f90830c
Payload: 33 files, source manifest marked dirty=false
```

Local artifacts are retained at
`/workspace/.obsgod-tools/decky-native-candidate-3/` and `-4/`.
They are review builds, not a published release or an instruction to replace the
owner's installed version before the planned test packet.

Host source tools: Go1.27.4, Node24.19.0, npm11.9.0, Python3.12.14,
Docker28.4.0, Playwright1.62.0 and Chromium151.0.7922.173 on Linux x86_64.
The native capture ABI uses the separately pinned Debian builder/receipt; its
`.so` SHA256 is `a954d1a6a86e2bfe1e01f97c7e6bc71438a311d7fa311f55c0c86592c2e89f68`.
Compilation is not evidence of loading it in the owner's OBS Flatpak.

The unmodified pinned official Decky CLI0.0.7 and default digest-pinned builder
assembled the prepared plugin with container networking disabled and matched all
33 files byte-for-byte. That is assembly verification of host-compiled bytes,
not a claim that the upstream builder compiled the frontend/native source.
The official raw ZIP's timestamps remain nondeterministic; reproducibility here
is the canonical ZIP produced by this repository's builder.

## Checks at that source

| Check | Outcome |
| --- | --- |
| Go race/count1, `./internal/deck ./internal/commands` | Passed: 156 top-level tests / 268 pass events; one root-only negative case skipped under actual UID1000 |
| Go vet, same packages | Passed |
| Full `steamdeck/tests/test_*.py` discovery | 171 discovered: 170 passed, one root-only wrapper skipped; actual non-root dependency fixtures executed |
| Node frontend tests | 37 passed |
| Frontend typecheck/build | Passed; actual clean package built |
| Packaging / release audit / frontend ownership | 9 / 16 / 6 passed |
| Four actual-ZIP browser suites | Dependency setup (six cases), existing panel, microphone and advanced controls passed |
| Actual packaged Go and optional setup HTTP | Version/source and setup-state execution passed; authenticated/unauthenticated routes behaved correctly; zero OBS/Flatpak boundary commands |
| Python map → actual packaged Go | Passed; changed state pointer rejected without another controller directory |
| Independent canonical builds | Identical ZIP SHA256; matching clean source snapshots |
| Actual official CLI/default builder | All33 files matched |
| Hosted candidate workflow | Unavailable: failed before any steps due to the account billing lock |
| Actual Steam Deck / Flathub / controller / viewer | Unrun |
| Final campaign local ACT/native/platform/security matrix | Unrun here; remains #85 |

The CLI's actual `deck status` returned `configured=false`, state `setup` in a
synthetic HOME. It did not connect to a real provider or create a live stream.
Dependency tests use real subprocesses implementing a fake Flatpak protocol and
an actual owned Unix socket; they do not substitute for SteamOS/Flathub proof.

Exact commands, platform/tool details, log hashes, all 20 issue criteria and
limitations are in [the machine-readable report](evidence/decky-foundation-7e539ca.json).
[Raw receipts](evidence/decky-foundation-7e539ca.zip) contain 24 files and have
SHA256 `a938845484d15a26393d740998aaed1f266dad5a14564b2a3966ffc7da79c254`.

## Demonstrated repairs and review

1. The default Decky builder excludes nested `src/` directories. Packaging the
   untouched SDK tree in deterministic `SOURCE.tar.gz` preserves LGPL preferred
   source and uses the actual default builder without a custom entrypoint.
2. Go's Flatpak child environment dropped the player's XDG data/cache roots.
   It now retains those roots rather than looking in another user installation.
3. A writable nonsticky ancestor allowed replacement of private output/state
   directories. Review reproduced two control-lock inodes while the first lease
   was held. Python/Go/job/build checks now reject that namespace; legacy Go
   Lock enforces it even without the map. Trusted sticky parents still pass.
4. The new browser harness initially expected the wrong existing Stop label,
   followed by an invalid test-selector regex. The corrected harness passes;
   this is a test repair, not a claimed product-state fix.

Agent review and fixture proof are recorded as such; they are not a fabricated
GitHub human review. Earlier480c477 artifacts and their passing/failing receipts
remain historical and are superseded for this batch by the corrected source.

## Remaining acceptance

Keep current IDs, update trust and all original #46 criteria/dependencies.
Actual Decky UI installation, real per-user Flathub transactions and session-bus
behavior, OBS Flatpak capture/audio/controller/suspend/runtime/viewer behavior
remain unrun. Required review/hosted/platform/rights/publisher/adoption gates
remain explicit. The fresh candidate job recorded zero steps and the annotation
“The job was not started because your account is locked due to a billing issue.”
No paid execution or manual retry was requested.

Continue #79–#85 before asking the owner to run the full numbered Deck tests;
fix the reported problems in #86. Prepare the exact migration independently,
but execute #87 only after that current-install test/fix loop and destination
authority; #88 then tests the real new installation. OAuth remains separate
research #89. This checkpoint does not close any original acceptance issue.
