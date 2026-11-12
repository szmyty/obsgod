# Independent capture/audio/packaging review

Reviewed source checkpoint 3afac40fe54710231eef38187d4a2b139126616e; C file SHA256 1cefd90dc7a306ac993366fa0e18573202e6ba4a13590999065c3c80018a6c5d. Read-only review; no C/product edits or new native executions during this review. Source owner remains merge_stack_audit; final packaged-library/native validation is separate.

## Actionable finding sent to source owner and root

In registry_global, a later matching Video/Source sets ambiguous but overwrites producer_id/version. Ambiguous is checked only in the first discovery result. The advertised proxy may therefore belong to the first producer while the stream still AUTOCONNECTs by mutable original target name with PW_ID_ANY; later duplicate/removal is not consistently tied to that first validated producer. This is a concrete unsafe state transition in the source. No compositor pixel leakage exploit was executed.

Recommended bounded repair: retain the first validated identity/serial; fail_locked on another matching identity including while active; target the validated serial or otherwise verify stream linkage. Extend fixture coverage to late duplicate/replacement. Owner was notified before freeze.

## Copy/format/teardown observations

No additional obvious copy OOB or lock-order defect found. Width/height are positive and capped at4096; packed BGRx size capped64MiB. Row/extent arithmetic uses64-bit, positive stride must cover each row, chunk offset+size is checked against plane maxsize and only MemFd/MemPtr mappings are copied. Destination allocation matches packed row*height. Format failure clears retained data; stop broadcasts flushing before acquiring the PipeWire loop lock and joins/destroys the loop before GMutex/GCond destruction.

App ID0/769 and >uint32 are rejected. Producer advertisement is checked before stream creation; negotiated exact ID/allowed duplicate None choice values and BGRx/geometry are checked. Producer removal/core failure triggers failed state. Stale frames become black rather than compositor data. EMPTY and nonmodifier-advertisement guards were already added by the C owner; their new negative tests are owned by native_capture_validation.

These observations are code review, not a memory-safety proof or real Gamescope/SteamOS qualification. Native tests must exercise the actual portable packaged .so, not only a host rebuild.

## Packaging/install observations

The package builds against pinned-base bookworm stable ABIs and records actual compiler/package/image identities. The .so is adjacent to both CLI copies; MIT preferred source and notices are included. Runtime/install exact-schema additions require both source and binary, while historical archives remain accepted. Existing staged releases, verified plugin-before-app activation, settings/key/media preservation, old release rollback and safe paths are retained. No new packaging/install blocker found.

## Small audio cache follow-up

ensureAudio saves ready route metadata before final MuteOtherAudio. If that last API operation fails it returns an error but does not invalidate the ready receipt; new output is still blocked correctly. Root was told this can leave an overconfident cached audio caption after a failed operation. Consider marking unavailable/unknown in that branch. readAudioStatus also has no explicit future-timestamp rejection, but no demonstrated runtime fault was claimed or broader hardening requested.

Meter messages qualify signal at OBS input rather than claiming viewer reception. Actual Deck silence cause and new native/Deck audio validation remain separate from metadata-only proof.
