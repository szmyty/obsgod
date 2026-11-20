# deckystream pre-migration review checkpoint

Review artifacts from exact source
[772230a32a8fdb237a58b8a637947b31671ad509](https://github.com/szmyty/obsgod/tree/772230a32a8fdb237a58b8a637947b31671ad509).
Never merge this artifact branch into the source branch.

The standard [plugin ZIP](obsgod-decky.zip) is **4,570,722 bytes**, SHA256
`fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a`. Verify [checksums](SHA256SUMS), read
[the owner packet](OWNER-PACKET.md), and follow [the numbered tests](OWNER-TESTS.md).
Package version remains 0.1.0-deck.9 with compatible OBSGod identifiers. Normal
installation and replacement use Decky; dependencies require explicit consent.

The [full runtime TAR](obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz) is optional: it supplies the current reviewed
cleanup helper without requiring Desktop app installation. A plugin ZIP update
cannot update an old Desktop uninstaller. Preview cleanup first; do not wipe to
work around an installation failure.

The complete available run recorded **70 passed command predicates, 2 unavailable,
0 failed**. The ACT runner probe and all six workflows stayed unrun after capacity
refusal; current PR114 dependency/hosted readiness remained unavailable. All three
native OBS fixture groups passed. See [qualification](qualification-summary.json),
[criterion review](criteria-review.json), [public proof](pre-migration-772230a-public-proof.zip)
and [reproduction](REPRODUCE.md). The first failed same-source attempt stays a
separate appendix, with no reused passes. Development history is in its
[separate reviewed archive](development-history-772230a.zip) and [index](development-history-772230a-index.json).

This is a review checkpoint, not a product release, updater offer, deployment,
repository migration, Store submission or complete device/rights/adoption
approval. Your machine/Steam Deck tests remain deferred; actual loader, controller,
headset, provider and independent-new-user observations remain pending.
