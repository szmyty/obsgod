# Additional ACT resource feasibility audit

This is a read-only storage feasibility audit after the af7 standalone qualification, not another matrix run. The original refusal and 68 command-row dispositions are unchanged.

Measured root free space: **2,118,672,384 bytes**; supported requirement: **7,544,361,132 bytes**; shortfall: **5,425,688,748 bytes**. Scratch has **9,160,065,024 bytes** free. Preserving its 6GiB reserve permits at most **2,717,614,080 bytes** of root-output relocation.

Read-only VFS/cache-id measurements show the optional official builder occupies **1,487,716,352 bytes** across seven full-copy layers. Even optimistically granting complete builder reclamation and the maximum relocation leaves **1,220,358,316 bytes** missing. Granting the additional unidentified small layer still leaves **1,195,524,268 bytes** missing. Exclusive ownership/staleness and actual reclaim of that optional builder are not established; these are optimistic bounds, not deletion proposals.

The tagless 7d95 image is the required pinned ACT runner. Older native images 9ad9/cbaa/c58 are layer prefixes of the required current 74e native image; removing their names cannot release its shared layers. Capture builder, package-manager images and the reusable ACT tool cache remain required. Unshared BuildKit cache is only about48KB.

Host UID1000 could not traverse Docker root and sudo is absent. The coordinator authorized one bounded diagnostic method: cached tiny Alpine, network disabled, read-only root and two exact read-only Docker metadata binds, all capabilities dropped except DAC_READ_SEARCH when the first no-capability probe proved incomplete. Only du/stat and cache-id/size/parent metadata were read. No profile, environment or ordinary file contents were collected.

No images, volumes, caches, artifacts or outputs were deleted, pruned or relocated; no presets or daemon/source configuration changed. Transient read-only helpers used --rm.

**Conclusion:** no safe capacity plan within the preservation/reserve constraints. Use more root/Docker capacity or an adequately sized free owner-machine runner; retain the original explicit unavailable/full-matrix gate.
