package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestMixerPreferencesPreserveLegacyCredentialBinding(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(strings.Replace(fixtureSettings, `"microphone":false`, `"microphone":true`, 1))); err != nil {
		t.Fatal(err)
	}
	beforeConfig, _ := os.ReadFile(p.Config)
	beforeSecret, _ := os.ReadFile(p.Secrets)
	legacy, _, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	pref, err := MixerSettings(p, legacy)
	if err != nil || !pref.MicrophoneEnabled || pref.MicrophoneDevice != "default" || pref.GameGainPercent != 100 {
		t.Fatalf("legacy policy did not migrate safely: %+v %v", pref, err)
	}
	pref.MicrophoneEnabled = false
	pref.MicrophoneMuted = true
	pref.MicrophoneGainPercent = 75
	if err = writeJSON(mixerPreferencesPath(p), pref); err != nil {
		t.Fatal(err)
	}
	afterConfig, _ := os.ReadFile(p.Config)
	afterSecret, _ := os.ReadFile(p.Secrets)
	if !bytes.Equal(beforeConfig, afterConfig) || !bytes.Equal(beforeSecret, afterSecret) {
		t.Fatal("mixer changed legacy credential-bound files")
	}
	if _, _, err = Load(p); err != nil {
		t.Fatal("mixer invalidated stream credentials", err)
	}
	pref, err = MixerSettings(p, legacy)
	if err != nil || pref.MicrophoneEnabled || !pref.MicrophoneMuted || pref.MicrophoneGainPercent != 75 {
		t.Fatal("separate mixer preferences did not persist", err)
	}
	info, _ := os.Stat(mixerPreferencesPath(p))
	if info.Mode().Perm() != 0600 {
		t.Fatal("mixer preferences are not private")
	}
}
func TestMixerRejectsUnsafePreferencesAndRequests(t *testing.T) {
	pref := defaultMixerPreferences(DefaultSettings())
	for _, change := range []func(*MixerPreferences){func(p *MixerPreferences) { p.Version = 2 }, func(p *MixerPreferences) { p.GameGainPercent = 201 }, func(p *MixerPreferences) { p.MicrophoneGainPercent = -1 }, func(p *MixerPreferences) { p.MicrophoneDevice = "speaker.monitor" }, func(p *MixerPreferences) { p.MicrophoneDevice = "private\nsource" }} {
		bad := pref
		change(&bad)
		if bad.Validate() == nil {
			t.Fatal("invalid mixer preference accepted", bad)
		}
	}
	for _, raw := range []string{`{"action":"configure","unknown":1}`, `{"action":"status"} {}`, strings.Repeat("x", 16385)} {
		if _, err := decodeMixerRequest(strings.NewReader(raw)); err == nil {
			t.Fatal("unsafe mixer request accepted")
		}
	}
}
func TestMixerCacheExpiresActualEvidenceAndNoticeRedactsIdentity(t *testing.T) {
	p := testPaths(t)
	r := blankMixer(p)
	r.Known = true
	r.State = "ready"
	r.Microphone.Known = true
	r.Game.Known = true
	r.ExpiresAt = time.Now().Add(-time.Second)
	if err := writeJSON(mixerCachePath(p), r); err != nil {
		t.Fatal(err)
	}
	cached := ReadMixerSnapshot(p)
	if cached.Known || cached.Microphone.Known || cached.Game.Known || cached.State != "unknown" {
		t.Fatal("stale audio was presented as observed", cached)
	}
	noteMixer(p, "microphone-lost", "private-user-headset-id")
	first := readMixerNotice(p)
	noteMixer(p, "microphone-lost", "private-user-headset-id")
	second := readMixerNotice(p)
	if first.Revision != second.Revision || first.Code != "microphone-lost" {
		t.Fatal("same loss produced duplicate notice")
	}
	raw, _ := os.ReadFile(mixerNoticePath(p))
	if strings.Contains(string(raw), "private-user") {
		t.Fatal("device identifier leaked into support-safe notice")
	}
}
func TestTalkLeaseBoundsAndFastRenewalWithoutOBS(t *testing.T) {
	p := testPaths(t)
	pref := defaultMixerPreferences(DefaultSettings())
	pref.MicrophoneEnabled = true
	pref.PushToTalk = true
	pref.MicrophoneMuted = false
	if err := writeJSON(mixerPreferencesPath(p), pref); err != nil {
		t.Fatal(err)
	}
	token, _ := newTalkToken()
	now := time.Now().UTC()
	lease := talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(mixerTalkLease)}
	if err := writeTalkLease(p, lease); err != nil {
		t.Fatal(err)
	}
	_ = writeJSON(mixerWatchRecordPath(p), mixerWatchRecord{PID: os.Getpid(), Watching: true, Updated: time.Now().UTC()})
	start := time.Now()
	r, err := MixerAction(context.Background(), p, strings.NewReader(`{"action":"talk-start","token":"`+token+`"}`))
	if err != nil || !r.OK || r.LeaseMS != 1200 || r.TalkToken != token || r.TalkExpiresAt == nil || !r.TalkExpiresAt.After(start) || r.TalkExpiresAt.Sub(start) > mixerTalkLease+100*time.Millisecond {
		t.Fatal("renewal required unavailable OBS", r, err)
	}
	if time.Since(start) > 300*time.Millisecond {
		t.Fatal("heartbeat unexpectedly performed slow work")
	}
	for _, bad := range []talkLease{{Token: token, IssuedAt: now, ExpiresAt: now.Add(2 * time.Second)}, {Token: token, IssuedAt: now, ExpiresAt: now.Add(-time.Millisecond)}, {Token: token, IssuedAt: now.Add(time.Minute), ExpiresAt: now.Add(time.Minute + mixerTalkLease)}} {
		if validTalkLease(bad, now) {
			t.Fatal("unbounded or stale lease accepted")
		}
	}
	badToken := strings.Repeat("a", 48)
	if badToken == token {
		badToken = strings.Repeat("b", 48)
	}
	if _, err = MixerAction(context.Background(), p, strings.NewReader(`{"action":"talk-start","token":"`+badToken+`"}`)); err == nil {
		t.Fatal("another press could renew an owned lease")
	}
}
func TestTalkGuardianExpiresMutedWithoutNormalControlLease(t *testing.T) {
	p := testPaths(t)
	normalUnlock, err := Lock(context.Background(), p)
	if err != nil {
		t.Fatal(err)
	}
	defer normalUnlock()
	token, _ := newTalkToken()
	now := time.Now().UTC()
	if err = writeTalkLease(p, talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(40 * time.Millisecond)}); err != nil {
		t.Fatal(err)
	}
	var mutes atomic.Int32
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err = watchMixerWith(ctx, p, func(context.Context, Paths) error { mutes.Add(1); return nil }, os.Getpid(), 5*time.Millisecond); err != nil {
		t.Fatal(err)
	}
	if mutes.Load() != 1 {
		t.Fatal("lease guardian did not mute exactly once", mutes.Load())
	}
	lease, valid := readTalkLease(p)
	if valid || lease.Token != "" {
		t.Fatal("expired lease remained active")
	}
	if notice := readMixerNotice(p); notice.Code != "talk-expired" {
		t.Fatal("expiry lacked safe notice", notice)
	}
}
func TestTalkGuardianRetainsUnconfirmedLeaseAndDoesNotClaimMute(t *testing.T) {
	p := testPaths(t)
	token, _ := newTalkToken()
	now := time.Now().UTC()
	_ = writeTalkLease(p, talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(-time.Millisecond)})
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Millisecond)
	defer cancel()
	var mutes atomic.Int32
	err := watchMixerWith(ctx, p, func(context.Context, Paths) error { mutes.Add(1); return errors.New("private connection details") }, os.Getpid(), time.Millisecond)
	if err == nil || mutes.Load() == 0 {
		t.Fatal("failed cleanup did not remain explicit")
	}
	lease, _ := readTalkLease(p)
	if lease.Token == "" {
		t.Fatal("unconfirmed cleanup erased recovery lease")
	}
	notice := readMixerNotice(p)
	encoded, _ := json.Marshal(notice)
	if notice.Code != "control-unconfirmed" || strings.Contains(string(encoded), "private") {
		t.Fatal("control loss was falsely confirmed or leaked", notice)
	}
}
func TestTalkGuardianFailsMutedOnUnreadableLeaseAndReload(t *testing.T) {
	for _, kind := range []string{"corrupt", "reload"} {
		t.Run(kind, func(t *testing.T) {
			p := testPaths(t)
			token, _ := newTalkToken()
			now := time.Now().UTC()
			_ = writeTalkLease(p, talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(mixerTalkLease)})
			if kind == "corrupt" {
				_ = os.WriteFile(talkLeasePath(p), []byte("invalid"), 0600)
			}
			ctx, cancel := context.WithCancel(context.Background())
			if kind == "reload" {
				cancel()
			}
			defer cancel()
			var mutes atomic.Int32
			err := watchMixerWith(ctx, p, func(context.Context, Paths) error { mutes.Add(1); return nil }, os.Getpid(), time.Millisecond)
			if kind != "reload" && err != nil {
				t.Fatal(err)
			}
			if mutes.Load() < 1 {
				t.Fatal("reload/corrupt lease did not attempt mute")
			}
		})
	}
}
func TestMixerPrivateFilesRefuseSymlinks(t *testing.T) {
	p := testPaths(t)
	if err := privateDir(filepath.Dir(mixerPreferencesPath(p))); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(t.TempDir(), "other.json")
	_ = os.WriteFile(target, []byte(`{}`), 0600)
	if err := os.Symlink(target, mixerPreferencesPath(p)); err != nil {
		t.Fatal(err)
	}
	if _, err := MixerSettings(p, DefaultSettings()); err == nil {
		t.Fatal("mixer followed symlink")
	}
}

func TestMixerHoldToTalkRequiresExplicitArmButNeverConfiguresHotMic(t *testing.T) {
	pref := defaultMixerPreferences(DefaultSettings())
	enabled := true
	disabled := false
	next, err := patchMixerPreferences(pref, mixerPatch{MicrophoneEnabled: &enabled})
	if err != nil || !next.MicrophoneMuted {
		t.Fatal("microphone enable did not start muted", next, err)
	}
	pref = next
	next, err = patchMixerPreferences(pref, mixerPatch{PushToTalk: &enabled})
	if err != nil || !next.MicrophoneMuted || !next.PushToTalk {
		t.Fatal("PTT enable did not start disarmed", next, err)
	}
	pref = next
	next, err = patchMixerPreferences(pref, mixerPatch{MicrophoneMuted: &disabled})
	if err != nil || next.MicrophoneMuted || !next.PushToTalk {
		t.Fatal("explicit PTT arm could not persist permission", next, err)
	}
	// Actual configure uses MicrophoneMuted || PushToTalk, so armed PTT remains
	// physically muted until a verified bounded lease permits one unmute.
	if !(next.MicrophoneMuted || next.PushToTalk) {
		t.Fatal("armed idle PTT could configure an unmuted input")
	}
	next, err = patchMixerPreferences(next, mixerPatch{MicrophoneEnabled: &disabled})
	if err != nil || !next.MicrophoneMuted {
		t.Fatal("disable lost fail-muted preference", next, err)
	}
}

func TestTalkGuardianRetiresReadinessBeforeReplacementLease(t *testing.T) {
	p := testPaths(t)
	oldUnlock, err := Lock(context.Background(), mixerLeasePaths(p))
	if err != nil {
		t.Fatal(err)
	}
	_ = writeJSON(mixerWatchRecordPath(p), mixerWatchRecord{PID: os.Getpid(), Watching: true, Updated: time.Now().UTC()})
	replacement := make(chan bool, 1)
	started := make(chan struct{})
	go func() {
		close(started)
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		unlock, err := Lock(ctx, mixerLeasePaths(p))
		if err != nil {
			replacement <- false
			return
		}
		defer unlock()
		// This is the next press's critical section. The old guardian may still
		// hold its lifetime lock, but it must already have withdrawn readiness.
		_, fresh := readMixerWatchRecord(p)
		token, _ := newTalkToken()
		now := time.Now().UTC()
		_ = writeTalkLease(p, talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(mixerTalkLease)})
		_, valid := readTalkLease(p)
		replacement <- !fresh && valid
	}()
	<-started
	finishMixerWatch(func(watching bool) {
		_ = writeJSON(mixerWatchRecordPath(p), mixerWatchRecord{PID: os.Getpid(), Watching: watching, Updated: time.Now().UTC()})
	}, oldUnlock)
	if !<-replacement {
		t.Fatal("replacement press accepted an exiting guardian's fresh readiness")
	}
}
func TestTalkCancelWithNoLeasePreservesOrdinaryMicrophone(t *testing.T) {
	p := testPaths(t)
	pref := defaultMixerPreferences(DefaultSettings())
	pref.MicrophoneEnabled = true
	pref.MicrophoneMuted = false
	_ = writeJSON(mixerPreferencesPath(p), pref)
	// An ordinary microphone has no talk capability. Teardown is a no-op and
	// succeeds without any OBS control query, even when credentials are absent.
	r, err := MixerAction(context.Background(), p, strings.NewReader(`{"action":"talk-cancel"}`))
	if err != nil || !r.OK {
		t.Fatal("ordinary microphone cancellation tried OBS mutation", r, err)
	}
	_ = writeTalkLease(p, talkLease{})
	r, err = MixerAction(context.Background(), p, strings.NewReader(`{"action":"talk-cancel"}`))
	if err != nil || !r.OK {
		t.Fatal("ended lease cancellation tried OBS mutation", r, err)
	}
	after, _ := MixerSettings(p, DefaultSettings())
	if after.MicrophoneMuted || !after.MicrophoneEnabled {
		t.Fatal("teardown changed ordinary microphone consent")
	}
}

func TestTalkRenewRefusesDeadOrStaleGuardian(t *testing.T) {
	for _, kind := range []string{"missing", "dead", "stale"} {
		t.Run(kind, func(t *testing.T) {
			p := testPaths(t)
			pref := defaultMixerPreferences(DefaultSettings())
			pref.MicrophoneEnabled = true
			pref.PushToTalk = true
			pref.MicrophoneMuted = false
			_ = writeJSON(mixerPreferencesPath(p), pref)
			token, _ := newTalkToken()
			now := time.Now().UTC()
			_ = writeTalkLease(p, talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(mixerTalkLease)})
			record := mixerWatchRecord{PID: os.Getpid(), Watching: true, Updated: now}
			if kind == "dead" {
				record.PID = 2147483647
			}
			if kind == "stale" {
				record.Updated = now.Add(-time.Second)
			}
			if kind != "missing" {
				_ = writeJSON(mixerWatchRecordPath(p), record)
			}
			if _, err := MixerAction(context.Background(), p, strings.NewReader(`{"action":"talk-start","token":"`+token+`"}`)); err == nil {
				t.Fatal("unguarded talk lease renewed")
			}
			_, valid := readTalkLease(p)
			if valid {
				t.Fatal("dead/stale guardian retained an active hot-mic lease")
			}
		})
	}
}
