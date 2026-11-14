# 0003: provider-neutral core and optional creator orchestration

Status: **Existing separation documented; separate companion repository proposed**.
Original #9/#13/#14 criteria remain intact. Current authorization permits
preparation here, without settling separate-project ownership or authorizing
another repository's changes.

Owner disposition on 2026-11-14 UTC: defer the separate companion and provider
OAuth work while finishing the Steam Deck product. This is a scope deferral,
not acceptance of the proposed companion project or proof that its original
criteria were implemented. Retain the existing compatible creator/RTMP adapter;
the future companion and OAuth criteria move to the focused future backlog.

## Context and choice

The core owns reusable typed OBS control, cancellation/time budgets, observation
and local workflows. A versioned facade can hide pinned transport types/errors
while a compatibility adapter preserves legacy commands. API and product-release
stability are distinct. Provider presets are RTMP(S) configuration, not account
APIs/OAuth. Creator actions/content distribution belong above the core and remain
optional, using private secret references rather than keys in argv/logs.

Recording/replay supplies local media; publishing/scheduling/monetizing it is a
distinct action with its own permission and failure contract.

The current implementation supplies `pkg/api/v1` and `obsgod api`, plus the
optional `pkg/creator/v1` consumer and `obsgod creator`. The creator adapter
connects to existing OBS and leaves it running. It resolves environment-backed
RTMP provider configuration; it performs no provider-account API action. Legacy
`internal/obs` commands retain their existing contract rather than silently
changing their outputs; fully sharing the new facade remains a partial #9
criterion. The facade/creator contracts need fresh final-source qualification.

## Proposed companion disposition

#13 originally requires a dedicated `streamgod` repository/project. An in-repo
creator adapter can validate the boundary but cannot silently satisfy that
criterion. The owner must choose an approved companion destination, accept an
explicit scope amendment, or retain the criterion in the consolidated checklist.

Multiple presets do not establish simultaneous multistream. First specify local
outputs versus remote-relay ownership, provider limits, partial-start/stop,
costs and failure recovery. #51 separately holds monetization/Store research;
this record does not perform it.

See [architecture](../../ARCHITECTURE.md), [configuration](../configuration.md)
and [destinations](../stream-destinations.md).
