# Milestone 2 implementation

The owner authorized implementation after reviewing the roadmap and support
design. **Decky Stream** is the working display name. The organization and final
brand remain undecided. Read [the roadmap](../ROADMAP.md) and live parent
[#23](https://github.com/szmyty/obsgod/issues/23) for all original criteria.

## Identity and compatibility

`product.json` is the versioned display-metadata source. Run
`python3 scripts/generate-product.py`, or `--check` to detect drift. Product
identity is build metadata; environment variables configure individual installs.
The existing CLI `obsgod`, Decky ID `OBSGod`, plugin directory `obsgod`, storage
namespace, managed OBS profile and immutable update repository are retained.
Changing a display title does not authorize changing those compatibility IDs.

The approved support direction is a bottom section of accessible icon-and-label
buttons generated from repository funding configuration. The five common owner
destinations are GitHub Sponsors, Buy Me a Coffee, Ko-fi, Open Collective and
thanks.dev. Patreon is excluded pending the recorded broken-link conflict.
Optional Bitcoin/Ethereum/Solana receive panels remain hidden without valid
owner-supplied public receiving addresses and explicit networks. Local QR/copy
actions need no wallet custody, private keys or transaction signing.

## Batches

1. Product metadata, Decky environment/path integration and CLI/XDG configuration.
2. Support UI, controller-first streaming UI and provider/password setup.
3. Installation/update repair and complete owned-data uninstall/reset/wipe.
4. Documentation/landing preview, migration/release/support packets and final
   exact-source qualification.

Each batch is checked and checkpointed in reviewable draft PRs. Source-changing
repairs precede final candidate qualification. A package is not called qualified
by receipts from a different revision.

Current stack starts with [#52](https://github.com/szmyty/obsgod/pull/52), then
[#53](https://github.com/szmyty/obsgod/pull/53),
[#54](https://github.com/szmyty/obsgod/pull/54), and
[#55](https://github.com/szmyty/obsgod/pull/55), followed by CLI/workflow and
documentation/qualification drafts. Review/merge in dependency order; these
drafts do not close original criteria. The exact final source/artifact matrix
will be attached here after source freeze, distinguishing unavailable device/
CI checks from passed local checks.

## Remaining owner and external gates

Organization/repository transfer and final Identity asset approval await owner
facts. Release publication, site deployment, other-repository submission and
spending retain their separate approvals. Missing actual Deck audio/capture/
privacy/controller/session/performance/provider-viewer evidence and successful
required CI/reviews remain acceptance gates. Store eligibility is unresolved;
the direct channel can be prepared independently, with honest provenance.

No issue is closed merely from a code merge or a synthetic fixture. The prior
preview6 artifact remains immutable; this implementation requires a new exact
candidate and fresh evidence.
