# deckystream owner packet

This review-only packet uses relative artifact links. The source PR and final
delivery separately pin its immutable artifact commit.

The candidate is package 0.1.0-deck.9 from exact source
`772230a32a8fdb237a58b8a637947b31671ad509`, tree
`f157ea77d16a1f1ce04bf1e47b584f9183c9c359`,648 tracked source files.
[PR114](https://github.com/szmyty/obsgod/pull/114) is stacked after
[PR113](https://github.com/szmyty/obsgod/pull/113). Merge in that order only after
required checks/reviews and fresh protection inspection. The current default is
master at `069db4a`; no move or release is part of this review.

## Current candidate and evidence

Use [the standard ZIP](obsgod-decky.zip), [checksums](SHA256SUMS),
[build receipt](build-receipt.json) and [numbered tests](OWNER-TESTS.md). The
[optional full runtime TAR](obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz) provides
the current cleanup helper. Normal Decky users need not install the Desktop app.
Updating the ZIP does not refresh an old same-version Desktop uninstaller.

Source repairs add verified durable private export before explicit wipe, fix
verified GitHub pagination, add read-only repository/PR readiness evidence and
correct current setup/update/removal guidance. The fresh complete available run
finished with **70 passed command predicates, 2 unavailable and 0 failed**;
[qualification-summary.json](qualification-summary.json) binds source and logs.
Commands include preparation/audit actions and an expected-exit1 negative control;
they are not 70 test suites or ACT jobs.

Application tests: 289 passed, 2 privilege-wrapper skips; tooling 151 passed;
frontend 161 passed in absent/reused modes; branding 33 passed; all 10 packaged browser
flows and all 3 native OBS fixture groups passed. The 20 new export and 35 retained
removal focused tests also passed without skips. Snapshot, repeated generic/NFPM
audits and Linux package smokes passed as standalone commands. Official 0.0.7
CLI assembly compared 33 prepared payload files with network disabled; it does not
prove source compilation or raw CLI ZIP reproducibility.

The supported ACT preflight refused: root 3,629,019,136 bytes available versus
7,544,361,132 required, shortage 3,915,341,996. Scratch 8,686,321,664 versus
6,442,450,944 required. The runner probe and all 6 workflow jobs remain unrun.
Current PR114 observation reports 15 billing refusals,1 push-only skip and 0 steps;
no other failed source job ran. SBOM 404/comparison 403 leave service ingestion
and executed review unconfirmed. No setting is inferred or changed.

The first same-source attempt had 44 passed predicates, 1 unavailable and 1 failed
native-game check after disk pressure; it was incomplete and stays a separate
failed appendix. None of its passes qualify this later run. Direct-file gallery
access was blocked by administrator policy; the same bytes passed loopback
desktop/mobile/download cases.

Standard ZIP: 4,570,722 bytes, SHA256 `fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a`.
Optional current runtime TAR: 12,053,779 bytes, SHA256 `e8d32968573989565dc74eb4e2bd8bd41e97107ebdbd6f57e56e69f565ef1487`.
All 24 payload digests,25 regular TAR members, source revision/dirty=false, matching
plugin ZIP and current cleanup-helper digest were verified. Updating the plugin
cannot replace an old Desktop uninstaller.

The public proof is 683,339 bytes, SHA256
`b3b117bd4527643a1525be87481e8b0bb594939854c9b5126a45d514a9237c43`, with 184 members and no additional redactions.
Original and public main report hashes both equal
`4727b7dbcb5b3a81c024ee0b0738a2b61bcb38c5c1ed5ced9bf3d25157c29c31`.

[Public proof](pre-migration-772230a-public-proof.zip), [criterion review](criteria-review.json)
and [separate development history](development-history-772230a.zip) retain exact
source and evidence boundaries. Provenance is unsigned/self-reported, not an
authenticated publisher, trusted-builder attestation or SLSA level. Linux/browser
fixtures do not prove actual SteamOS/Decky/Flatpak/Gamescope/AMD/controller/
headset/provider operation.

## Ownership, art and destinations

The current public source is szmyty/obsgod, a fork of muesli/obs-cli. Retain MIT
Copyright (c) 2020 Christian Muehlhaeuser plus SDK LGPL/runtime/preferred-source,
capture, QR and DejaVu notices. Namespace/author metadata is not proof of every
asset's legal ownership. Owner selected lowercase deckystream and 01 / aurora. The
38-file kit's unchanged raster has generation provenance; vectors were separately
authored after visual inspection. Exact final licenses/permissions/attribution,
name availability, publisher/legal contact and production adoption remain
proposed-unapproved; no rights transfer/exclusivity/copyright eligibility inferred.
All prior concepts remain preserved.

Identity consumer stays pinned to cfb6c29bd02589a47fc48050ab02e7e0da359719 and its
exact same-commit validator/schema digests. No upstream update or Identity release
is required to use that reviewed pin; local source-contract/kit validation is not
production compiler output or adoption.

Current review/update trust stays exactly szmyty/obsgod. Future slug deckystream
is chosen; exact OWNER/deckystream, admin/authority/create-or-move-or-archive plan
remain unknown. Landing/docs are built offline; public domain/hosting/deployer
remain unknown. No product Flathub distribution is planned; OBS/GStreamer are
dependency Flatpaks. Funding configuration is retained and crypto addresses are
intentionally unset. #51 Store/monetization and #89 authentication research do not
authorize Store contact, paid features, OAuth coding or app registration.

## Next responsible actions

1. Complete exact-source available qualification and independent artifact review,
   with downloadable ZIP, optional current helper TAR, checksums and evidence.
2. When available, owner follows OWNER-TESTS.md: actual #82-C1 loader lifecycle,
   no automatic dependency/OBS/broadcast action, private keys, local clip/audio,
   explicit provider viewer, game-only/idle privacy, mic/headsets/mute intent,
   controller, session, update/rollback/removal preservation. #79's explicit
   keep-open review/device instruction remains. Do not wipe before transition.
3. Preserve 230 original criteria/dependencies. Existing-install success does not
   prove independent/new-user adoption. Keep unsupported native-platform, full
   required matrix, hosted-service, review, rights and adoption gates explicit.
4. Owner supplies exact destination/admin, rights/license/publisher/contact,
   signing or transparent unsigned-preview policy and site/domain choices.
   After current-install tests, prepare exact migration and clean canonical
   new-install retest. #95 requires actual destination dependency graph, both
   manifests and successful real PR comparison/executed review evidence.
5. Prepare exact reviewed tag/version/assets/changelog or site build before
   requesting the specific release/deployment/other-repository approval. No
   generic approval question is needed for current authorized preparation.

[Machine-readable packet](OWNER-PACKET.json) keeps proposed facts and missing
owner decisions explicit. No release, deployment, migration, provider registration,
Store submission/contact, other-repository change or spending occurred.
