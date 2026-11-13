# CLI consistency audit

This source audit covers the current command tree, including the completion campaign.
It is separate from real-device acceptance. Canonical command names, legacy OBS
environment variables and existing human result formats remain compatible.

| Surface | Audited behavior |
| --- | --- |
| `config`, `version`, `completion`, `reference` | Offline help, versioned config/build JSON, shell generation and Markdown reference; credential values excluded. |
| `workflow` | Explicit plan/dry-run/apply; settings and local outputs have separate approvals; no broadcast action. |
| `api` | Versioned public-facade JSON; typed safe errors, operation contexts/serialization and explicit output/settings approvals. Discovery remains offline. |
| `creator` | Optional public-API consumer; offline reviewed plan/extensions, existing-OBS start/status/stop, environment-backed private RTMP credentials and partial-stage evidence. |
| `stream`, `recording` | Existing start/stop/toggle; status has per-command JSON/quiet and unknown-query failure instead of false inactive results. |
| `profile`, `scenecollection`, `scene` | Existing OBS nouns and operations retained; name arguments documented; `scene set` aliases `scene current`. |
| `sceneitem`, `source` | Scene/item/source arguments checked before requests; readable query output goes through the command writer; spaced names/text handled consistently. |
| `replaybuffer`, `virtualcam`, `studiomode` | Existing local controls/status remain; no-argument operations reject stray arguments. |
| `label` | Text joins all supplied words; countdown uses duration units, positive bounds, a stopped ticker and command-context cancellation. |
| `deck` | Existing managed-runtime JSON and credential-free diagnostics remain independent of generic connection configuration; output-state and recovery gates retained. |
| `doctor` | Top-level entrypoint reuses managed `deck doctor`, preserving context, bounded diagnostics and JSON; help explicitly distinguishes it from remote OBS configuration checks. |

Readable result output now consistently uses the configured command stdout
writer. Result JSON is intentional on documented high-value surfaces; commands
without a JSON option keep their human format. Quiet is a status option, not a
global suppression of safety failures. Executable errors use stderr/nonzero
status. Verbose metadata stays on stderr and excludes values supplied by users.

Hyphenated aliases improve discovery without removing canonical names:
`scene-collection`, `scene-item`, `replay-buffer`, `virtual-camera`, `studio-mode`.
Commands that consume names explain quoting/multiple-word behavior in their
usage. All runnable commands have explicit positional validation.

The offline [generated reference](cli-reference.md) comes from `obsgod reference`;
its built-in defaults are independent of environment values, and no generated
date makes it drift between builds. Help/completion/reference tests use missing
configuration and fail-on-connect services. Plain/JSON output, credential
redaction, color conventions, explicit workflow approval, active/unknown output,
partial failure and cancellation are covered by focused protocol/CLI tests.

The executable's signal context reaches workflows and countdown loops. Existing
single-request legacy service operations retain their transport behavior;
context-aware automation owns the new bounded multi-stage workflow. New `api`
and `creator` commands consume the versioned public API; legacy requests retain
their compatible acknowledgement behavior with safe error projection rather
than claiming complete #9 migration. See [the API contract](api-v1.md) and
[creator boundaries](creator-workflows.md). This audit
does not establish whole-platform support, actual viewer output, Store admission,
successful hosted CI or completion of the broader governance issue.
