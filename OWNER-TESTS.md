# Owner review checklist —772230a preparation

This review-only checkpoint is package **0.1.0-deck.9**, source
**772230a32a8fdb237a58b8a637947b31671ad509**, tree **f157ea77d16a1f1ce04bf1e47b584f9183c9c359**; 648 tracked files.
The [standard ZIP](obsgod-decky.zip) is **4,570,722 bytes**, SHA256
**fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a**. Verify [checksums](SHA256SUMS),
[build receipt](build-receipt.json) and [reproduction](REPRODUCE.md) before using
the immutable artifact URL supplied with this packet.

The fresh complete available run has 70 passed command predicates, 2 unavailable
and 0 failed. ACT probe/six workflows are unrun after measured capacity refusal;
current PR114 dependency/hosted services remain unavailable. All 3 native OBS
fixture groups passed; that is not a Steam Deck result. The first failed 772
attempt remains separate, with no reused passes. Actual loader/controller/
headset/provider/adoption acceptance stays pending. See [qualification](qualification-summary.json)
and [public proof](pre-migration-772230a-public-proof.zip) for exact outcomes.

The normal product is the 33-file Decky ZIP. The [optional current runtime TAR](obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz)
supplies the reviewed cleanup helper; users need not install its Desktop app for
normal plugin operation. No release, deployment, Store installation, migration
or automatic updater offer is claimed.

For each numbered case, record **PASS / FAIL / SKIPPED / UNAVAILABLE / UNRUN**,
exact behavior/date and candidate hash. A screenshot alone does not prove every
part of a compound case. On a failure, retain the exact stage and filtered console
text, then stop dependent actions and repair/retest without bypassing guards or
silently switching capture modes. Never send a stream key, OBS password, private
setup token, wipe-export TAR or raw private logs.

## Owner machine first

1. Record OS/architecture and local/free environment capabilities. Follow [REPRODUCE.md](REPRODUCE.md): clean exact source, pinned tools, working actual Docker socket, measured preflight and full supported matrix. If unavailable, preserve the measured refusal and all later jobs as unrun. Native Windows/macOS/non-x86_64 runtime checks remain separate; a Linux VM/WSL run proves that environment only.
2. Verify ZIP size/SHA/source/version by the Python verification in [REPRODUCE.md](REPRODUCE.md). If reproducing, retain the two complete primary builds, matching canonical ZIP and receipt. The candidate's recorded preferred-source snapshot, licenses, manifests, unsigned audit and candidate checks are review evidence, not authenticated release signing.

## Prepare the Steam Deck

3. Record LCD/OLED model, SteamOS version/channel, Steam version, Decky version/channel, current plugin version/source if known, user OBS Flatpak version/ref and GStreamer extension ref/branch. Note actual audio devices/headsets, game names and connection type. LCD/OLED is context, never an assumed microphone availability result.
4. Preserve the current install/settings/key/media and ordinary OBS profiles. Stop streaming, recording and replay; wait for fresh confirmed idle. Do not wipe old OBSGod or shared dependencies before testing this current compatible identity. Keep a reviewed prior install/candidate for rollback. Do not publish private backup material. Open Decky's own plugin-installation controls and use the verified standard ZIP through its supported file/URL sideload flow; use the same-directory [verified ZIP](obsgod-decky.zip). If your Decky version requests a URL, use that file’s raw download URL from this exact checkpoint; a GitHub blob/HTML page is not a plugin ZIP URL. No full legacy Desktop archive is required. If the loader cannot consume the supplied URL/file, report its exact UI/version instead of manually replacing folders or enabling root/debug flags.

## Loader lifecycle and dependency consent

5. **#82-C1 actual loader lifecycle:** verify normal plugin install/load, sidebar entry/icon, frontend opening and backend readiness on the actual supported Decky. Close/reopen the panel, reload/restart through Decky's supported controls and observe fresh state/reconnection. Record load/unload/reload errors, time to readiness and whether state stays truthful. It must run without root/debug flags. Pinned RPC/router/browser fixtures are not a substitute for this real lifecycle.
6. Merely install/load/open the plugin: confirm **no dependency download, OBS launch, local recording or broadcast** occurs. If missing dependencies are observed, choose **Later** and reopen: setup remains pending, actionable and safe; local settings can be saved offline. If dependencies already exist, record present/ready and mark missing-dependency cases unrun on this device. Do not uninstall shared Flatpaks to force a test.
7. With explicit consent, choose dependency **Install**. Observe bounded progress, close/reopen panel and confirm the same job continues. If reasonably safe to test, explicitly **Cancel**, wait for actual stop/installed-ref observation and retry only missing refs. Interrupted/network/disk/permission errors must remain actionable; no repeated jobs, shared-cache deletion or false ready. Do not deliberately fill the device disk or break its remote. Confirm OBS28+ built-in obs-websocket and matching GStreamer extension; no second WebSocket plugin/system unlock. System-only Flatpaks must yield the documented scope guidance rather than duplicate silently.

## Native private destination setup

8. In **Stream destination**, choose the provider guide (Kick for the existing account), enter the account's stream URL and separate key with controller/STEAM+X or paste, then **Save destination & settings**. Confirm key starts masked, saved key is never returned, draft clears on save/panel exit/destination change, and console/copy/support results contain no key. Blank key retains the same saved destination's secret; changed server/guide/account requires a replacement. A guide is not OAuth/login. Desktop browser setup remains optional; do not treat unavailable clipboard synchronization between modes as a key failure.
9. Save must not broadcast. With managed OBS running but idle, settings stay locked until **Close managed OBS to edit settings…** is explicitly confirmed; this closes only managed OBS and does not reopen it. Streaming/recording/replay/unknown states block it. **Test local OBS connection** authenticates only an already running instance, never launches/streams. OBS control password is distinct from stream key/browser token; no password readback. Do not change credentials without the UI's explicit safe-state confirmation.

## Local picture, audio and controller

10. Use **Make 10-second test clip** before broadcasting. Inspect the finalized file in `Videos/OBSGod` (or configured location) for moving video and audible system audio. Game-only with no game can intentionally record the between-game screen; a game is not universally required. Entire screen requires usable screen frames. The stream indicator must not turn green merely because a local clip saved. Do not mistake a success notification for actual playable media.
11. Verify automatic status updates with the panel left open, plus manual **Refresh status**. Observed OBS sending output drives green/red/unknown text and actions; no required manual refresh to learn state. Idle Stop is disabled; repeated actions do not duplicate effects/toasts. Test panel close/reopen, temporary connection loss/recovery and stale status: unknown must not authorize mutations. **Diagnostic console**, Copy and Clear stay readable/controller reachable, bounded and sanitized; copy contents using a private destination before switching sessions.
12. Check all key controls using actual Deck buttons/touch/Steam keyboard, focus/scroll/modal confirm/cancel/back. Inspect subtle aurora icon/wordmark, text contrast and small-screen legibility; decorative gradient cannot stand for live state. Review gallery assets separately from the panel. No controller result is inferred from the Chromium harness.

## Explicit provider stream and game privacy

13. Explicitly select **Start streaming** only when ready. On a separate device/provider viewer confirm the account, moving picture, system audio and expected delay. Green means OBS output sending, not proof of viewer reception. Explicit Stop ends actual output; repeated Stop does nothing; game launch/reconnect/device recovery never restarts stopped broadcasting. Capture filtered errors from a failure; never paste the key.
14. While every output is confirmed stopped, select **Switch to game only**. Test no game → game A → Steam menus → game exit → game B and incompatible/ambiguous capture. Correct game frames or intentional idle/black/selected permitted between-game media must appear; **never silent entire-screen fallback**. Leave an explicitly started stream running across safe game transitions and confirm viewer privacy. Missing local media falls back to black. Ordinary system audio can include other apps; game-only video does not promise per-app audio.
15. Stop all outputs, select **Switch to entire screen** and explicitly start a local clip/stream. Confirm intended screen/menu visibility. Stop again before changing modes. Blocked/unknown state cannot authorize a mode change. No game-only privacy claim applies to entire-screen mode.

## Microphone, headsets and session recovery

16. Microphone is opt-in. Enumerate actual input availability before enabling; select the intended input and explicitly unmute. Test built-in mic with no headset, then the actual 3.5mm/USB/Bluetooth headset(s) available. On LCD, 3.5mm insertion may affect the built-in input: record observed missing/available/active input and actionable status, not a hardcoded model assumption. Never choose a monitor as microphone or assume every headset has one.
17. Verify stream-only system/mic gain, mute, input level and recorded/provider audio. Changing devices starts mic muted and preserves explicit user mute intent; unplug/replug/default-output change must not secretly unmute. Test **Hold here to talk** with actual controller press/release, focus loss, panel close and interruption: the lease expires/release mutes; reconnect never grants talking indefinitely. Confirm ordinary OBS/other apps' audio are unaffected. If a headset/platform cannot be tested, mark it unavailable/unrun.
18. Stop deliberate output first where practical; test sleep/wake/session switch/network loss and recovery without risking accidental broadcasting. Unknown state stays visible and cannot authorize restart/update/removal. Recovery may re-establish control, never start stopped output. Desktop/Gaming session changes may terminate managed GUI processes; record actual behavior rather than assuming continuity.

## Recording, replay, storage and safety

19. Exercise available record/replay start/stop/save controls and stream coexistence on this exact candidate. Play finalized moving/audible files, confirm replay paths/partial files, exclusive exports, selected XDG/custom/SD-card locations and permissions. Confirm low-reserve refusal/finalization using a safe available test volume/fixture; **never fill actual device disk to zero**. Missing/denied path remains recoverable, no traversal/unrelated file removal. Check existing media remains intact.
20. Review quality presets/encoder and health/bitrate/drop/load/audio/capture status under named games. Record game FPS/CPU/GPU/power/battery/thermal tradeoffs; 720p30/4500kbps is a starting default, not a qualified performance promise. Stale metrics become unknown. No automatic quality mutation or provider reception claim from local health alone.

## Update, rollback, removal and preservation

21. **Check for updates** is read-only; this review checkpoint must not appear as a newly published updater offer. Ordinary plugin replacement uses Decky after positively idle state. Same package version can contain different source; compare exact revision/hash, not just 0.1.0-deck.9. Observe replacement/reopen/backend lifecycle and retained config/keys/media/plugin storage. An absent/mismatched optional legacy Desktop app must not force pair repair. Preserve ordinary OBS, unrelated Decky plugins and shared Flatpaks.
22. With a reviewed prior verified ZIP and all outputs stopped/known idle, perform a deliberate Decky rollback only if needed/safe; record exact before/after revisions, fresh state and preservation. Active/recording/replay/unknown output must block unsafe update/recovery/removal actions where managed by the plugin. Do not bypass a refusal by deleting folders.
23. If testing removal, choose explicit plugin-only/default-preserve scope using supported Decky controls after known idle and backup; verify data/media/ordinary OBS/shared dependencies/unrelated plugins survive. Do not select full data wipe just to make a test pass. A future requested clean OBSGod→deckystream migration wipe is a separate planned, explicit operation after acceptance—not this checkpoint's default.

## Optional current cleanup helper and late recovery

These cases do not authorize a wipe or make one necessary for normal installation.
Source fixtures already exercise 20 new export checks and 35 retained removal checks;
actual device/recovery observations remain distinct from those software results.

23a. If inspecting old Desktop files, obtain the **full runtime TAR from this exact
review artifact commit**, verify its checksum and `manifest.json` revision772230a,
and extract into a new private staging folder. Do not install or launch the
Desktop app merely to preview cleanup. A plugin-only ZIP update cannot update an
old retained Desktop uninstaller, even at the same package version. From the new
verified runtime folder run `python3 -B uninstall.py --legacy-app-only --dry-run`;
inspect the inventory privately. This preview does not contact OBS/Decky, mutate
selected files or start a stream. For a nonstandard Decky root, use its actual
verified context; do not guess a path.

23b. Deliberate legacy Desktop retirement is **later**, after the current plugin
transition succeeds, a separately verified prior install/private backup is retained,
all stream/record/replay outputs are stopped and fresh state is known idle. Only
if intended, use that same current helper with `--legacy-app-only` and review the
confirmation. Confirm the Decky plugin, canonical data/media/backups, ordinary
OBS, shared Flatpaks and other plugins survive. No retirement result is prefilled.

23c. Full data wipe and recovery are separate owner choices, not this checklist's
default. Never wipe to work around an error. If later explicitly chosen, use the
current reviewed helper, preview the exact selected scope and choose a new
private export target outside removal roots (`--wipe --export PATH`). The helper
must create, verify and durably publish its recovery TAR **before the first
selected deletion**; unsafe/existing/export-failure targets must refuse. The TAR
contains credentials, is not encrypted and intentionally survives wipe; keep it
private and outside support uploads. Existing media is selected only by the
explicit media option. Do not force a real device disk or permission failure just
to exercise a guard. Recovery is deliberate private staging and inspection, then a
separately verified reinstall and selected owned-data restoration while output
stays stopped; never extract over HOME or assume automatic restore. Keep skipped,
unavailable and unrun observations honest, and dispose of the exact export only
when it is no longer wanted.

## Report and next loop

24. #79 remains open under its dated owner/device-review direction; fixture or browser passes do not silently remove that gate. Return the numbered results, exact candidate hash, platform versions, failed stage/message, filtered console/support bundle and selected private clips/viewer observations. No independent/new-user adoption is claimed from this owner's existing install. Every demonstrated defect becomes a bounded repair, affected-source recheck and new exact candidate. #86 remains open until its actual criteria pass; missing loader/hardware/platform/review/CI/rights/adoption evidence stays visible.
25. After current-identity acceptance, choose exact `OWNER/deckystream`, publisher/legal contact/assets/license/signing-or-unsigned-preview and approved move/archive plan. Prepare final notes/artifacts before requesting exact release/deployment/other-repo approval. Enable dependency graph on the actual public destination (#95), verify real manifests/PR comparison and clean new canonical installation. This future step is not authorized by downloading/testing this review ZIP. OAuth/phone login and Decky Store/monetization remain their separate research journeys.

The [owner packet](OWNER-PACKET.md) records source/rights/destination facts. The [criterion review](criteria-review.json) is distinct from the frozen [104-bullet inventory](https://github.com/szmyty/obsgod/blob/772230a32a8fdb237a58b8a637947b31671ad509/docs/evidence/aurora-remaining-acceptance.json). No case in this checklist is marked passed until an actual observation is recorded.
