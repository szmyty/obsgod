# Decision records

This practical Ego Hygiene documentation bootstrap records current choices and
separates them from owner decisions still pending. It does not claim compliance
with every evolving framework document or start a standards migration.

| Record | Status | Scope |
| --- | --- | --- |
| [0001: managed local control](docs/decisions/0001-managed-local-control.md) | Existing behavior, documented | Isolated graphical OBS, confirmed state and capture privacy |
| [0002: product identity](docs/decisions/0002-product-identity.md) | Working name accepted; repository slug selected; final identity/migration proposed | Decky Stream display, intended `deckystream` repository, preserved compatibility identifiers |
| [0003: core and creator](docs/decisions/0003-core-and-creator-boundary.md) | Existing separation documented; companion repository proposed | Provider-neutral core, optional orchestration |

“Existing behavior, documented” records source; it is not a new owner approval
or qualification receipt. “Accepted” needs a recorded owner/applicable authority
decision. “Proposed” remains proposed until that decision is recorded. Independent
preparation can proceed under current authorization without settling an open choice.

Record changes to durable external contracts, ownership/dependency direction,
privacy/safety, destructive recovery or support claims. Explain context, choice,
relevant alternatives, consequences and evidence. Routine fixes need no ceremonial
ADR. Update [architecture](ARCHITECTURE.md), [vocabulary](ONTOLOGY.md), feature
docs and continuity when inaccurate. Code/merge alone cannot accept a proposal.

## Runtime ownership and shutdown (#96–#100)

The owner authorized these bounded correctness repairs and the existing PR
merges. Capture changes now recheck current managed ownership/output under the
shared control lease; microphone scene policy derives from saved mixer intent.

Native qualification exposed the ten-second local test's existing long lease.
That initiating command retains recording ownership and drives the same guarded
capture helper while it waits; detached observers still yield. Short-lived tick
connections preserve the finalizer's connection at timer expiry. Fresh managed
ownership gates final/deferred Stop. This avoids releasing the lease and later
stopping a replacement recording, without weakening the native fixture.

Canonical raw recording flags prevent generated defaults from authorizing
output changes. A lost SDK response boundary invalidates the owned API
connection, including through workflow wrappers, without retrying mutations.

The supported loader's five-second termination deadline requires a four-second
best-effort adapter drain rather than serial long waits. Commands use registered
permission and kernel parent-death protection in a fresh helper, avoiding unsafe
`preexec_fn` in the threaded loader. Frozen Decky uses validated system Python
instead of its `PluginLoader` executable. Independently leased dependency workers
retain their recovery policy. Ordinary OBS is not killed as a command child;
unknown output remains unknown. See the [runtime contract](docs/runtime-correctness.md)
for limits and the actual-device gate. These source choices do not accept any
previously proposed product/identity ADR or authorize publication/migration.

## Cleanup and recovery (#101–#102)

The owner authorized the next cleanup/recovery batch after runtime completion.
Keep coordination lock inodes and minimal namespaces through deletion, rather
than creating multiple generations of one logical lease. Retained helpers use
protected ancestry and preview/held-identity checks; obsolete-app retirement
preserves the independently installed Decky plugin and shared stores.

The loaded plugin is the primary update identity. Optional Desktop versions do
not require repairing a pair. Legacy dependency recovery reuses the candidate's
verified native policy; unsafe historical installers cannot bypass it. Deliberate
replacement binds exact target/current versions, and automatic rollback needs
the verified preimage version rather than any older Desktop archive. See
[the contract](docs/cleanup-recovery.md). These choices do not authorize a new
publisher, release, transfer, deployment, paid resource or another-repository
change, and do not accept a proposed identity/companion ADR.

## Bounded settings and complete readback (#103)

The owner authorized the next bounded audit batch. Capture-mode edits use a
short Go mutation context, its existing separate status observation, and a
Python operation budget that includes preflight, spawn, cleanup and readback
under the UI timer. Backend ownership survives caller disconnect; an unreaped
command remains pending rather than becoming a completed failure with late
execution authority. Start/Stop, microphone leases and generic API behavior
retain their separate semantics.

Configuration readiness requires mandatory fields and consistent gates instead
of synthesized permission. Preserve Go's settings version in the public
projection and share plain Go-produced/malformed JSON test data across clients.
Documented legacy dimensions and presence-only nested connection observations
remain supported. There is no schema generator or new validation dependency.
Read [the contract](docs/settings-boundary.md). These repairs do not accept a
proposed identity/companion ADR or authorize publication/migration/spending.

## Native destination setup (#79)

Owner-authorized manual-key setup now uses the normal Decky panel and existing
Go configuration writer. Destination guides remain presentation only; the
actual server and private key binding determine the saved destination. Sparse
edits merge under the shared control lock so unedited advanced state is retained.
There is one canonical XDG credential store, no frontend secret readback, and no
provider OAuth or account API dependency. A changed server or explicitly changed
account/event requires a new key. Saving requires confirmed closed/idle managed
OBS; closing an idle instance is a separate explicit confirmation. This preserves
offline operation, legacy configuration and explicit broadcast authorization.
See [the contract and user journey](docs/native-configuration.md); implementation
and local evidence do not establish actual controller/provider acceptance.

## Primary build and constrained local qualification (#104)

The owner authorized this bounded next batch after merging #109/#110. The
maintained candidate must execute the documented primary builder, not infer its
health from a compatibility builder sharing helpers. Both full primary outputs
are independently inspected and compared, then their actual ZIP feeds existing
checks. Root ACT setup drops to the non-root checkout owner for primary work;
private build paths and the existing Docker socket group are explicit.

The opt-in constrained local profile measures real host/daemon capacity and
uses a fresh serial matrix session. Known resource shortfalls stop before
workflow execution. Separate private root/owner compiler caches avoid ownership
repair; only their post-consumer contents can be cleaned, with exact receipts.
Module caches, artifacts, evidence and existing presets remain intact. Failed or
interrupted attempts retain their own outcome instead of inheriting a later
pass. See [local CI](docs/local-ci.md). No product permission, proposed ADR,
release/publisher, deployment, migration or spending decision is changed.
