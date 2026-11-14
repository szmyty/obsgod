# Follow-up qualification — 2026-11-13 America/New_York

All required available local checks passed at exact clean source
`4699235e9e925b76ca492d5a00a375ed37fb338e`, tree
`3c09ea82d85ddcdf47c347afa44961f7b1b6956e` (401 source files). Execution timestamps
are UTC on 2026-11-14. This later documentation does not relabel those bytes.
Overall product acceptance remains **partial**.

[Machine-readable evidence](../docs/evidence/qualification-4699235.json),
[immutable review checkpoint](https://github.com/szmyty/obsgod/tree/eb92598f3a4a0dc426749c290bacfe7251452909),
[full qualification](https://github.com/szmyty/obsgod/blob/eb92598f3a4a0dc426749c290bacfe7251452909/qualification.json),
[compact raw evidence](https://raw.githubusercontent.com/szmyty/obsgod/eb92598f3a4a0dc426749c290bacfe7251452909/evidence.zip),
and [checksum-verifying Desktop install](../docs/current-review-install.md).
Evidence ZIP SHA256:
`22e9088a6d2f6a75f0323dbe61b508203f96dd864c418736f050bb8581e1d775`.
Its 253 text members include raw logs/receipts, source manifest, normalized
matrices, native/browser inventories, generic audits, supplemental phases and
the hash/size index. No recordings, executable packages or caches are in that ZIP.

## Changes qualified

- #69 fixes #68 in both workflow and nested packaging: frontend commands run as
  the real checkout owner, with private environment and safe-path/output checks.
  Existing unsafe/foreign output is preserved; production root guards remain.
- #70 supplies complete target-selected Go notices, source-bound generic archive
  inspections, SPDX/unsigned provenance and a Linux user-prefix smoke. NFPM and
  native cross-platform qualification remain separate.
- #71 adds one narrow typed profile read, preserving the new-family CLI JSON
  while avoiding unrelated OBS queries. Legacy Service/Dialer stays unchanged;
  its full migration remains explicit [engineering work](../docs/legacy-api-migration.md).
- #72 records [both #51 research journeys](../docs/research-51.md), 40 pinned
  sources, 14 criterion mappings, recommendations and owner questions. Research
  delivery does not adopt its recommendations or establish revenue/Store admission.

## Exact-source results

| Check | Result and scope |
| --- | --- |
| ACT | Both full six-job sequences plus actual-reference PR static passed: 13 passes. Snapshot ran first in the first sequence to test the new integration early. |
| Frontend ownership | Both immediate normal-host typecheck/test/build sets passed as UID/GID1000, first from absent output and then reused output; every frontend output remained owner-writable, with no repair. |
| Fresh Go | `go test -race -count=1 -json ./...`: 219 top-level / 399 pass events, zero failures; one optional existing-OBS read-only test skipped. Compilation caches may be reused; test execution was uncached. |
| Candidate checks, each run | 127 application Python, 50 tooling, 30 Node; typecheck/build/audit, static/security checks, 8 browser harnesses and 3 real Linux OBS harnesses passed. |
| Coverage | 58.1% in both runs. ACT's cached package observations stay labeled; fresh Go proof is separate. |
| Reproducibility | All 14 Deck product/audit hashes, all 20 generic archive hashes and all 42 generic audit-sidecar hashes matched across independent runs. |
| Generic install | Both actual Linux amd64 user-prefix extraction/version/config/API smokes passed as UID1000. Other platforms were audited/cross-built, not executed natively. |
| Legacy delivery | Actual pinned Decky3.3.1 transport/installer/updater fixtures passed for legacy4 plus dynamic6 bootstrap and legacy6→current; actual browser upgrade paths from4/6 passed. |
| CLI/completions | Current binary version/source, private XDG path, capabilities, creator plan/extensions, Bash/Zsh syntax, generated reference and API-client example passed. Fish 3.6.0 container syntax/dynamic completion passed; host Fish remains unavailable. |
| Dependency review | Unavailable: actual raw exit1/failed at verified base575e4e2/head4699235; comparison API 403. The synthetic read-only event is not hosted PR review. |
| Hosted CI | Unavailable: 9 runs, 15 jobs, zero executed steps; actual account billing-lock annotations. macOS capacity notice is separate. |
| Physical target/viewer/adoption | Unrun. Linux OBS30.2.3/synthetic media/device/browser/protocol proof does not qualify Deck/OBS 33/Flatpak/Gamescope/AMD/headsets/controller or external viewers. |

The two snapshots were independently built and verified identical before storage
deduplication. Only repeat-retained copies of 20 already-identical external
archives were atomically hardlinked to their first copies; both paths, hashes
and original job evidence remain intact. The separate regenerable host Go cache
was inventoried and cleared during native checks. Neither action changed source,
active test inputs, modules, toolchains, images, runtime artifacts or storage
guards. The native 1024 MiB/browser 2048 MiB guards remained unchanged. The historical
root-owned ignored frontend backup retained its exact mode/owner/content hashes.

## Criterion disposition and owner packet

All five #68 criteria have fresh source/identity/path/fixture/raw-result evidence
in the machine-readable mapping. Both full pipelines and both actual post-CI host
rebuilds establish the reported repair; a source merge alone is not that proof.
All 14 current #51 research criteria have separately readable deliverables and
explicit unknowns. Recommendation: finish the free direct core, retain optional
verified voluntary support, and defer paid/Store implementation until demand,
capacity and truthful policy clarification justify it. No offer/vendor/price,
wallet, account or external contact was selected or performed.

All 19 new review files were independently downloaded and matched, including
runtime/updater inventories and full 401-file source. Runtime SHA256:
`b4222fb703aa198a7ea200721afbc06dcb86dec56e8c1bebd77f5bb614aad53d`.
This is a manual checkpoint at artifact commit
`eb92598f3a4a0dc426749c290bacfe7251452909`, not a release/latest-updater offer.
The older 1a/d0a review artifact remains unchanged. Existing source/license/
rights distinctions and unapproved creative status are preserved; unsigned
inventories do not authenticate a publisher.

#46 remains the implementation/acceptance ledger. Next owner action: install
this exact review build on the Deck, return platform versions and an audible
moving local clip, then complete device/viewer/preservation acceptance. Resolve
GitHub billing/Dependency graph access independently. Wider legacy CLI migration,
NFPM/native support and companion/ecosystem implementation remain real work;
organization/creative/rights/publisher/destination and any release/deployment/
Store actions require their existing concrete decisions. No missing criterion is
silently completed. No product release, deployment, environment snapshot,
other-repository write or spending occurred.
