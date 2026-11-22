# deckystream: our step-by-step testing booklet

> **Sequence update, 2026-11-22:** The owner now plans to migrate the repository
> before the hands-on test session. Follow the [active roadmap](../ROADMAP.md#active-journey-polish-prepare-migrate-then-test).
> This booklet retains the exact current-identity `772230a` / `430cc391` reference
> and reusable test cases. Before testing the migrated installation, bind its
> actual new candidate/downloads in the finalization checklist; these older
> receipts do not qualify a new repository or build. No device case has passed yet.

We will use this together in chat. **Do one small step, report what happened,
then wait for the next step.** We can pause between any two steps.

Our first session ends with a local clip that we have actually watched and heard.
Public streaming, interruption tests and removal come in later sessions. Nothing
in this booklet is already marked passed.

The exact test download is on the [candidate card](#candidate-card). The display
name is **deckystream**; an existing Decky entry, folder or saved clip may still
say **OBSGod**. Keep your existing settings and recordings.

For each checkpoint, reply in this short form:

> Step 4.2 — PASS / FAIL / SKIPPED / UNAVAILABLE / UNRUN  
> What I saw or heard: …

**PASS** needs the expected observation. **FAIL** means we tried it and saw a
problem. **SKIPPED** means deliberately omitted; **UNAVAILABLE** means a named
prerequisite was missing; **UNRUN** means not attempted. We will record the build,
versions and outcome in our session notes.

---

## Page 1 — Meet the Deck; change nothing yet

**1.1 — First instruction when we start:** In Gaming Mode, press **•••**.
Tell me whether Decky's plug icon is visible. Then pause.

**1.2 — Inspect:** If Decky is there, open the existing plugin and report its name,
visible status and version if shown. Leave Start and installation controls alone.
If Decky or the plugin is missing, tell me; we will choose the next setup step.

**1.3 — Record:** We will gather LCD/OLED model, SteamOS version/channel, Steam
version, Decky version/channel, OBS version and dependency details, a game with
sound, and the microphone/headsets actually available. Missing details stay
unknown until we inspect them. These versions belong in the final session record.

**Expected:** We know what is installed and whether streaming, recording and
replay are each confirmed stopped. A red streaming dot alone does not describe
recording or replay. Report duplicate plugin entries or conflicting status.

**Pause if:** Anything is live, busy, stale or unknown. We will inspect it before
replacing files or changing protected settings.

---

## Page 2 — Install the verified compatible plugin

**2.1 — Prepare:** Keep the current settings/media and a reviewed, verified prior
ZIP if one is available for rollback. We will confirm all three outputs are
stopped and the status is fresh before replacement.

**2.2 — Download and verify:** Use the standard **plugin ZIP** on the candidate
card, not GitHub's source-code ZIP or a historical installer. We will compare its
checksum together before installation. A short Desktop checksum command is in
the candidate card; tell me if the file has a different name or location.

**2.3 — Replace through Decky:** Open Decky's supported plugin installation
controls and select the verified ZIP, or paste its exact raw ZIP URL. Decky's
labels vary by version, so we will match your screen. Preserve existing data.

**Expected:** One intended plugin entry opens, your saved destination remains
private, and simply loading the plugin does not download dependencies, launch
OBS, record or broadcast. This is part of the actual loader test, not the entire
install/update/uninstall lifecycle.

**Pause if:** The ZIP cannot be installed through your loader's supported controls,
settings disappear, or the panel reports a failure. Send the exact label/error;
we will not work around it by deleting folders or copying files as root.

---

## Page 3 — Dependencies, then private settings

**3.1 — Inspect Dependency setup.** If OBS/GStreamer are already installed and
compatible, keep them. Missing-dependency tests stay UNRUN on this installation.
**Show dependency details** exposes the panel's current observations.

If dependencies are missing, we will first choose **Later**, reopen the panel and
confirm setup remains pending without an automatic download. Then, when agreed,
choose **Install dependencies…** and review its confirmation. Observe progress;
closing and reopening the panel should show the same job.

We may exercise **Cancel dependency setup** and **Review and retry setup** when
that is safe and a missing dependency really exists. Wait for the actual job to
finish/cancel before retrying. Keep existing shared dependencies installed. OBS
28+ includes its WebSocket plugin; a second WebSocket download is unnecessary.

**3.2 — Inspect Stream destination.** Choose **Configure stream destination** or
**Edit saved destination**. For the current Kick account, enter its server URL and
separate key privately. **STEAM + X** opens the keyboard; **Paste stream key** is
available. A provider guide is guidance, not account login.

If managed OBS is running idle and editing is locked, we will separately review
**Close managed OBS to edit settings…**. Active or unknown output is a stop point.
Keep the same account's saved key by leaving it blank when that is what the UI
instructs. A changed destination/account needs its own new key.

**3.3 — Choose Save destination & settings.**

**Expected:** Saved destination is shown privately; the saved key is never read
back. Draft secrets clear on save/hiding settings/panel exit. Saving starts no
recording or stream. Keep initial quality/capture choices unchanged unless we
explicitly choose a change together.

**Pause if:** Setup fails, the key appears in diagnostics, a protected edit remains
locked, or anything starts unexpectedly. Share the result label, never the key,
full private setup address or an unredacted configuration screenshot.

---

## Page 4 — First moving, audible local clip

**4.1 — Prepare:** Confirm the displayed capture mode and all outputs stopped.
For moving game footage in **Game only**, open a game with known picture and
sound. A game is not universally required: no game can intentionally produce the
between-game screen. That proves idle behavior, not moving game capture.

**4.2 — Choose Make 10-second test clip once.** Let the operation finish. Watch
its state and saved-file result. This action never broadcasts; the streaming dot
stays stopped rather than becoming green just because a clip saved.

**4.3 — Play the new file.** Use the actual saved path/name, with the documented
fallback **Videos/OBSGod**. **Browse saved clips** can help identify it. A saved
notification alone is not a playback result. After the clip has finalized and
all outputs are confirmed stopped, we can switch to Desktop Mode, open the file
in Dolphin and play it. Return to Gaming Mode and observe fresh status afterward.

**Expected:** This request produced a playable new file with moving intended
picture and audible game/system sound. Record picture and audio separately.

**Pause if:** It times out, the file is missing/unplayable, or picture/sound is
wrong. Copy the filtered console before switching sessions; switching sessions
may end OBS and hide the original failure. We will fix the failed part before
using public streaming as the next test.

---

## Page 5 — Status, controls and the console

**5.1 — Observe:** Leave the panel open, then close/reopen it. Status should update
automatically. Use **Refresh status** once to check manual resynchronization.
When streaming is confirmed stopped, **Stop streaming** is disabled; unknown
state may instead offer **Stop streaming / recover** and needs inspection.

**5.2 — Navigate:** Use the Deck buttons, touch, scrolling and Steam keyboard.
Check focus, back/cancel and small-screen readability. The aurora logo is
decorative; the separate text/dot reports observed output.

**5.3 — Inspect Diagnostic console.** Try **Copy console log** and paste only its
filtered text into a private note or this chat. If copying fails, report that and
use selectable text or a carefully cropped photo. Copy before changing sessions;
the clipboard may not carry across modes. Clearing the console is a separate,
optional action after useful evidence is retained.

When managed OBS is already running and idle, we can separately exercise
**Test local OBS connection**. It should authenticate that existing instance,
without launching OBS or starting output. Leave it UNRUN when that situation
is not available.

**Expected:** Observed state drives the controls and transition messages; an
acknowledgement or repeated click does not manufacture a streaming success.

**Pause if:** Status stays stale, controls contradict it, or copy/keyboard/focus
prevents normal operation. Tell me the exact control and last visible state.

---

## Page 6 — Game-only privacy, locally first

**6.1 — Stop every output and wait for fresh confirmation.** Confirm **Game only**
is selected; otherwise choose **Switch to game only**. We can choose
**Use black between-game screen** or
**Use saved between-game message** without importing new artwork.

**6.2 — Check short local recordings:** no game → game A → Steam menus → game
exit → game B. We will stage these one at a time and watch the saved results.
Expected footage is the intended game or the intentional between-game screen.
Ambiguous, missing or incompatible game capture must not become the entire screen.

**6.3 — Compare screen mode only if wanted.** After stopping all outputs, select
**Entire screen** using **Switch to entire screen** if needed, then make another
local clip. Menus and other visible
screen content are intentionally included in that mode. Stop again afterward.

**Expected:** Game-only keeps Steam menus out of its app-filtered video. System
audio may still include other applications; game-only video is not per-app audio
isolation. No-game black/idle output is an intentional fallback, not moving-video
proof. Imported media is a later optional test.

**Pause if:** Any private menu/desktop appears unexpectedly in game-only output,
or a mode changes while protected output is active/unknown. Stop the test and
retain a private example; public streaming waits for the privacy check.

---

## Page 7 — Microphone and the headsets you own

**7.1 — Inspect Live audio & microphone.** Identify the intended input before
enabling it. **Enable microphone capture · starts muted**, **Microphone input**,
**Unmute microphone on stream** and **Mute microphone on stream** are the relevant
controls. We will explicitly choose each action, enabling capture only if it is
not already enabled. Headphones do not necessarily
contain a microphone. LCD/OLED is context; actual available inputs decide.

**7.2 — Record a short local sample.** For changes during capture, use the separate
**Start local recording**, then **Stop & save recording** controls. The ten-second
test has its own busy operation. In the local recording we can say a short phrase,
unmute, mute and confirm the difference by playback. Adjust gains deliberately
with **Apply audio levels**; captured stream levels should not change SteamOS
volume or game-chat audio.

**7.3 — Try one available headset at a time.** Stop outputs first for a routing
change, select the intended observed input, then explicitly unmute. Record built-in,
3.5 mm, USB or Bluetooth outcomes only for hardware actually available. A new
selected device starts muted and must preserve your deliberate mute preference.

If hold-to-talk is not already enabled, we can choose **Enable hold-to-talk ·
starts muted**, then **Arm hold-to-talk** and **Hold here to talk** in a controlled
local recording. Hold/release A while that
control has focus; repeat focus loss and panel close. It is not a global shortcut.

**Expected:** The recording proves microphone sound and mute behavior. Release,
focus loss or lease expiry should request mute. If OBS control is lost, mute is
unconfirmed: stop output or inspect OBS with me before assuming silence.

Finish this page with the microphone muted and every local output confirmed
stopped.

**Pause if:** The wrong input is selected, routing goes silent, mute is not
confirmed or an unplug/replug secretly unmutes. Keep unavailable hardware marked
UNAVAILABLE or UNRUN; do not infer it from the model name.

---

## Page 8 — Deliberately go live, with a separate viewer

We start this page only after the local picture, sound and privacy checks pass
and you explicitly choose to broadcast. Prepare a phone/other viewer on the
intended Kick channel. Keep viewer audio out of the Deck's capture path to avoid
feedback. Other providers can be separate named tests.

**8.1 — Choose Start streaming once.** Observe the status without repeated clicks.
**Cancel operation** is the preparation control if we deliberately cancel a start.

**8.2 — Verify from the other device:** correct account, moving picture, system
audio and microphone/mute as intended. Green means OBS is sending output; it does
not prove the provider/viewer receives it. Record actual delay rather than
expecting instant playback.

**8.3 — Choose Stop streaming / recover once.** Confirm OBS stops sending and the provider
ends its live output after any normal viewer delay. Stopped state disables another
ordinary Stop. If we deliberately check repeated Stop, it must create no new effect
or duplicate success notification. A later game launch/reconnect must not restart
broadcasting.

After a successful short stream, we can explicitly plan a second stream across
safe game transitions to confirm viewer-side between-game privacy.

**Pause if:** Output or stopping is unknown. Use the offered recovery path and
inspect OBS/channel with me; do not repeatedly Start, replace the plugin or assume
a failed control request means the broadcast ended.

---

## Page 9 — Extra media, quality and safe session checks

These are separate later checkpoints after the first local baseline. Any live
coexistence test needs its own explicit **Start streaming**; offline or local
checks do not require a public stream.

**9.1 — Recording/replay:** Exercise **Start local recording**, **Stop & save
recording**, **Start replay buffer**, **Save replay clip**, **Stop replay buffer**
and **Browse saved clips**. Check each new finalized file and actual storage path.
Streaming, recording and replay have separate lifecycles; stopping one need not
stop the others. Keep existing media. Storage/SD-card/low-reserve checks use safe
available conditions; never fill the actual Deck disk to zero.

**9.2 — Quality/media/health:** Review **Open stream profiles**, **Preview selected
preset**, settings-only export and **Measure current stream health**. Applying a
profile or between-game media needs the prescribed stopped/closed state. We will
save the current choices first and make one deliberate change. Custom images or
videos need your permission to use them; idle-video sound stays muted. Measure
actual game performance and stale/unknown health rather than assuming a preset
is a tested performance promise.

**9.3 — Recovery:** After explicitly stopping output, inspect ordinary offline
reopening, sleep/wake, session switching and reconnect behavior one at a time.
Saved configuration should survive. Recovery can regain control; it cannot start
a stopped broadcast. Desktop/Gaming transitions may end managed OBS. Live-loss
checks, if wanted, get their own controlled plan after the baseline.

**Pause if:** Any stopped output restarts, a path is wrong, media is lost or state
becomes unknown. We will not create disk, permission or hard-power failures to
force a test case.

---

## Page 10 — Later loader update, rollback and removal

This is a separate session after the working baseline, with private backups,
a verified candidate and fresh stopped stream/record/replay state.

**10.1 — Read-only update check:** **Check for updates** should not replace files
or interrupt output. This manual review build is not an automatic updater offer.
A matching version string can still contain different source; retain exact hashes.

**10.2 — Supported lifecycle:** We will separately observe ordinary Decky
replacement, close/reopen, supported reload/restart and fresh backend reconnection.
An explicit later plugin-only uninstall/reinstall checks unload/removal and data
preservation. Opening the panel alone does not complete #82-C1. Report duplicate
entries or conflicting controller behavior; ordinary OBS and shared helper
processes are not proof of a duplicate OBSGod controller.

**10.3 — Rollback only when needed and reviewed:** We choose a verified compatible
prior ZIP, record before/after source and use Decky's supported controls. A retained
Desktop app is optional and need not match the plugin's version.

**Expected:** Saved destination/settings/media, ordinary OBS, other plugins and
shared OBS/GStreamer installations survive the chosen preserve-data operation.

**Pause if:** Output is active/unknown, a guard refuses, a loader control is missing
or unrelated data changes. Keep the refusal; do not bypass it with folder deletion.
**Full wipe and legacy Desktop retirement are outside this ordinary test session.**

---

## If any step fails

Stop dependent steps and tell me the step ID, expected result, actual result and
visible error. Keep the relevant filtered console text in the same Gaming Mode
session. Share the installed candidate/version and a cropped photo or private
clip only when useful. Stream keys, OBS passwords, private setup tokens, raw
configuration/backups and credential-containing wipe archives stay private.

I will triage the evidence, fix a demonstrated defect, run affected checks and
supply a new exact candidate when source changes. We will repeat the failed and
affected steps. Earlier passes stay tied to their own build. Your existing-install
report is not independent/new-user adoption evidence.

## Candidate card

This card binds the current existing review download. If a replacement candidate
is supplied, we will update the card and record which steps need repeating before
continuing. Use the exact link, not the repository's latest prerelease button.

| Item | Current review build |
| --- | --- |
| Source | [`772230a`](https://github.com/szmyty/obsgod/tree/772230a32a8fdb237a58b8a637947b31671ad509) |
| Package version | `0.1.0-deck.9` |
| Standard ZIP | [obsgod-decky.zip](https://raw.githubusercontent.com/szmyty/obsgod/430cc391cb63f080214aacc279e5c04b1092c7a5/obsgod-decky.zip) |
| ZIP size | 4,570,722 bytes |
| Checksums | [SHA256SUMS](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/SHA256SUMS) |
| Full evidence and limits | [Owner packet](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-PACKET.md) |

Full source revision: `772230a32a8fdb237a58b8a637947b31671ad509`.

ZIP SHA256:

```text
fa206d93fcca0dd32b6dbebd1a641c40177f6a0acd7e635f68307a3bd2745e8a
```

For the default Desktop Downloads filename, this read-only command prints the
ZIP checksum without executing it:

```bash
sha256sum "$HOME/Downloads/obsgod-decky.zip"
```

If that file is elsewhere or the command is unavailable, report that and wait for
one suitable next instruction. No maintainer toolchain is needed on the Deck.

This source's completed available software checks are not actual Deck results.
Remaining ACT/hosted/service checks, rights, independent adoption and later
migration/publication decisions are tracked separately. None is silently checked
off by reading or following this booklet. Newer source merge/documentation
revisions are not relabeled as this exact packaged candidate.

## Coverage and later work

The [full acceptance checklist](https://github.com/szmyty/obsgod/blob/430cc391cb63f080214aacc279e5c04b1092c7a5/OWNER-TESTS.md)
remains the detailed record. This shorter booklet supplies the order for our
conversation; a compound acceptance case passes only after all its parts are
observed.

| Existing case | Where we work through it |
| --- | --- |
| 1 — free machine/CI qualification | Maintainer evidence, separate from Steam Deck instructions |
| 2 — exact ZIP verification | Page 2 and candidate card |
| 3–4 — device record, preservation and standard installation | Pages 1–2 |
| 5 — actual supported-loader lifecycle | Pages 2 and 10; complete lifecycle remains pending until all parts are observed |
| 6–7 — no init download, dependency consent/cancel/retry | Pages 2–3; missing-dependency branch remains UNRUN when already installed |
| 8–9 — private destination and already-running local control | Pages 3 and 5 |
| 10 — playable moving/audible local clip | Page 4 |
| 11–12 — observed status, console, controller and branding | Page 5, with observations throughout |
| 13 — actual separate provider viewer | Page 8 |
| 14–15 — game-only/entire-screen privacy | Pages 6 and 8 |
| 16–18 — mic/headsets, mute/talk and session recovery | Pages 7 and 9 |
| 19–20 — media/storage, profiles and measured health | Page 9 |
| 21–23 — update, safe rollback, default-preserve removal | Page 10 |
| 23a — current cleanup-helper preview | Separate [verified helper guide](legacy-cleanup-kit.md); optional, preview only |
| 23b–23c — legacy retirement, explicit wipe and recovery | Separate later owner choices, not a workaround or ordinary test prerequisite |
| 24 — honest results and repair/rebuild/retest | Every checkpoint and “If any step fails” |
| 25 — migration, destination services and new-install/adoption/v1 | Owner now plans migration before the session; bind the new candidate and carry these cases into finalization. See the [active roadmap](../ROADMAP.md). |

A private wipe-export TAR contains credentials, is not encrypted and intentionally
survives wipe. It is never a support upload. No actual retirement, wipe, restore,
new-repository migration, provider login, release, deployment or purchase is part
of the default booklet sequence. Optional OAuth/QR login stays separate research.
