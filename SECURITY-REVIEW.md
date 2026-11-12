# Independent M2 security and integration review

Read-only review of the M2 mutable integration tree, from baseline `539bb54` through current commits and pending changes. No repository/GitHub edits, commits, account/payment actions, publications or deployments were performed by this reviewer. Exact reviewed file hashes and commands are in `security-review-evidence.json`; this is not qualification of a later source/archive revision.

## Demonstrated findings and disposition

1. **Uninstall mutation before operation locks — found and repaired during this review.** `apply_plan()` removed the Decky plugin before acquiring installer/control locks. A private mocked busy-lock reproducer observed one plugin mutation even though the operation was rejected. The lifecycle owner moved plugin removal inside both locks, after fresh strict idle/process-absent and complete inventory validation. The same reproducer now observes zero mutations; real temporary-filesystem tests cover busy locks and an idle managed OBS process reappearing. No unsafe test touched an actual installed plugin.
2. **Partial settings/key pair — repaired and verified.** Blank saved-key reuse now requires both matching previous server and `SettingsHash` matching previous settings. The old-A-config/new-B-secret partial-write regression cannot rebind B's key to A; explicit key input repairs the pair.
3. **Downloaded-installer imports — repaired and verified.** New install/update/uninstall modules load exact sibling `paths`/product/bridge helpers instead of relying on an old updater's `sys.path` or an unrelated module of the same name. Isolated `-I` import and stale-helper cases are present in owner tests. The immutable published4.1 updater remains fixed to runtime4; this is not represented as a dynamic7 upgrade path.
4. **Malformed modern output status — repaired and verified.** Modern installer/uninstaller checks require explicit `output_known is True`, typed inactive stream/recording and recognized process state. Updater's narrow known-published1–4 legacy interpretation permits only download preflight. The verified new payload performs strict modern status before backups and install/apply; malformed new status is not permission to mutate.
5. **Decky orphan cleanup/retry — repaired and verified.** Fixed-identity `uninstall_existing` allows retry of a verified OBSGod directory after the upstream loader already removed its loaded entry but swallowed filesystem failure. Backend and filesystem absence are checked; another plugin name/path is not accepted. Mutation ownership remains held across frontend timeouts.
6. **Decky adapter data omitted from full wipe — repaired with explicit root scope.** Validated stable `obsgod` settings/data/log directories now appear in wipe inventory; shared parent directories and other plugins remain. Nonstandard Desktop Decky installations need the correct root configured/discovered; the added fail-closed known-root guard is described below.
7. **Unavailable optional OBS outputs — repaired and verified.** Workflow snapshots narrowly classify code604 as unavailable/inactive only for the matching `GetReplayBufferStatus` and `GetVirtualCamStatus` operations. All other request failures remain unknown and block mutation. Explicit attempts to start an unavailable local output still fail, rather than claiming it started.

## Reviewed invariants

- Generic configuration uses explicit tested layering and private credential references. Config/read errors do not echo input data; passwords do not marshal into public configuration or appear in help/completions. Group/other writable configuration and nonprivate password files are rejected. Help/version/reference/completions/managed recovery bypass unrelated broken generic configuration.
- Provider-neutral workflow plans exclude streaming actions. Apply requires invocation-local settings approval and separate requested recording/replay approvals; files/environment cannot supply approval. Context/readiness/delay bounds and cancellation stop later stages. Existing active/unknown outputs block; partial stage results remain explicit, without automatic rollback or output shutdown.
- Decky passes actual user HOME/XDG only to child processes, preserving parent environment. Canonical Desktop/CLI settings stay separate from Decky's persistent adapter runtime-data directory and actual ephemeral XDG runtime.
- Support destinations are fixed canonical HTTPS provider routes generated from owner funding handles. Unconfigured crypto is hidden. Configured receive views show explicit network/full public address and copy/local QR only; they do not hold/sign keys, connect wallets, send payments or contact QR services. Format validation does not claim checksum, ownership or receipt validation.
- Setup and private control actions retain token/origin/host checks and JSON-stdin secret handling. Password rotation requires managed OBS positively absent and the listener closed, updates the isolated pair with rollback, preserves stream key/settings hash and returns awaiting-verification. The read-only test checks authentication challenge and managed identity; it never launches or broadcasts.
- Credential-free support bundles project allowlisted state enums/booleans plus fixed-message diagnostic events, omitting settings, raw messages, server URLs, user idle text, private paths and audio device identifiers.

The delegated receive/control review found no additional concrete defect; its tests and hashes are in `security-receive-control.md`.

## Verification and limits

Independent checks passed: all17 uninstall regression tests; targeted race tests across automation/config/commands covering workflows, approvals, unknown/active states, cancellation, transport, secret-free verbose/reference output and doctor recovery; the direct busy-lock before/after reproducer. Component-owner fixtures and tests support the other listed fixes. Root still needs the final clean exact-source/archive matrix.

Known-root follow-up is resolved for the supported contract: the inventory explicitly displays its Decky root and the `DECKY_HOME` remedy; wipe with an unconfirmed/missing root has a visible pending gate before any CLI/plugin/file mutation. The frontend refuses to remove a loaded plugin unless Python has verified its expected on-disk compatibility directory. Exact-root and orphan retry remain allowed, and the request still cannot specify another plugin name/path. Data outside the reviewed/configured root is not claimed removed.

No new unresolved credential leak, automatic broadcast, payment path or foreign-plugin deletion was found in the reviewed components. Actual Steam Deck/Decky/controller/modal/clipboard/native reconnection, QR wallet scanning/receipt, successful CI/reviews, final brand rights and publication remain separate required evidence. This review does not substitute for those gates.

## Finite final delta review

- Workflow snapshots now inspect raw successful OBS response fields so missing/null `outputActive` and stream `outputReconnecting` cannot become false/known-idle through Go bool zero values. All required fields must be present, non-null booleans before mutation; the existing exact-operation604 optional-output exception remains narrow.
- The native password fixture now applies a settings-only approved workflow to actual authenticated OBS, observes outputs independently, preserves the private credential/settings pair and exports sanitized evidence. Dynamic execution belongs to the final matrix, not this static review.
- The lifecycle known-root guard and exact-root inventory were reread after the owner reported18 Python cases and real pinned Decky protocol checks. No additional concrete defect was found in this finite delta.

Final hash closure is recorded below. No broad checks were repeated for the finite source delta.

## Final source closure

Exact clean locally qualified revision: `0eac1ed9746e6a5999a196777bde5455222f46eb`. Git HEAD and clean working tree were verified directly. Final hashes for all 27 reviewed code files are recorded under `final_review.reviewed_code_hashes` in `security-review-evidence.json`. The only later change among those files was `internal/commands/reference.go`; it was reread and remains static offline help/reference rendering with no user-data, network or mutation path.

The root agent reports the complete available matrix passed freshly at this revision, including actual native OBS generated/manual password rotation and settings-only workflow, actual-package browsers and installer/updater/uninstall transport, and 13 capture protocol cases. The earlier459 run's locator failure was corrected by the one-line browser assertion scope change at this revision and the complete matrix was rerun; no older pass is used here to qualify changed source. This reviewer did not repeat the root matrix or independently assert its device/external coverage.

No unresolved concrete defect remains from this review at the recorded code hashes. This is local source/archive qualification and independent code review only. Actual Deck/provider-viewer evidence, successful required CI, owner/external reviews, final creative/rights/organization decisions and publication/deployment authorizations remain separate gates. No release, deployment, payment or external submission is represented as completed.
