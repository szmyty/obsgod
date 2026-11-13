# Decky Stream identity source — preparation only

This is a manually authored `identity.project/v1` consumer source, following Ego
Hygiene Identity's supported authoring path. `decky-stream` is the intended stable
brand ID and **Decky Stream** is the user's selected display name. The actual
repository remains `szmyty/obsgod`; the organization and transfer are undecided.

The governance arrays are deliberately empty. Nothing in `candidates/` is an
approved source. Empty token layers reserve the structure without inventing an
organization, an inherited palette or an override approval. Product UI and its
existing native Decky icon retain their reviewed baseline.

`toolchain.lock.json` pins the inspected upstream main implementation. That pin is
an additive, unreleased implementation, **not published Identity v1.0.0**. It is
needed for the current nullable optional-guidance authoring contract. The exact
validator and schemas may be downloaded from the immutable URLs in that lock;
verify their SHA-256 values before executing the validator. The validator uses
Python's standard library and does not install dependencies:

```sh
python3 /path/to/verified/validate_identity.py --repository-root . --format json --snapshot
```

Source-contract validity does not approve artwork, establish rights, or establish
generated Identity output conformance. `scripts/generate-brand-kit.py` is a local
**draft-kit preparer**, not Identity's compiler. See [review packet](../docs/branding-review.md)
for its exact outputs, checks, tool pins and approval gates. No Identity release,
environment snapshot, project release or public site is published by these commands.
