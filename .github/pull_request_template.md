## Problem and resulting behavior

Describe the concrete trigger and before/after behavior. Link the issue and its
criteria if applicable. State which criteria the evidence supports and which
remain open; use issue-closing keywords only when all applicable criteria are
met. Merging a PR alone does not qualify device/owner gates.

## Validation

Record the source revision/dirty state, relevant commands, platform and outcomes.
Distinguish passed, failed, skipped, unavailable and unrun checks. Documentation
and template changes can use lightweight checks from CONTRIBUTING.md; explain
which runtime checks were unnecessary. For runtime/package changes, include the
applicable matrix and local act job/event or direct fallback evidence. Older
receipts do not qualify new source; local checks do not establish hosted CI or
real-device acceptance. Keep real keys, private profiles, wipe-recovery archives
and unreviewed logs out of the PR.

## Compatibility and remaining gates

Describe relevant CLI/configuration/offline/recovery/secret-filtering effects,
or state that the change is documentation/templates only. List remaining device,
hosted CI, review, rights, owner or publication requirements where applicable.
Link updated guides and continuity/release evidence when affected. Candidate
builds and a PR merge do not authorize release publication or deployment.
