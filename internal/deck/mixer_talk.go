package deck

import (
	"context"
	"crypto/subtle"
	"errors"
	"os"
	"path/filepath"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

const mixerTalkLease = 1200 * time.Millisecond
const mixerTalkInterval = 100 * time.Millisecond

type talkLease struct {
	Token     string    `json:"token"`
	IssuedAt  time.Time `json:"issued_at"`
	ExpiresAt time.Time `json:"expires_at"`
}

func mixerLeasePaths(p Paths) Paths                 { p.State = filepath.Join(p.State, "mixer-talk"); return p }
func mixerWatchPaths(p Paths) Paths                 { p.State = filepath.Join(p.State, "mixer-watch"); return p }
func talkLeasePath(p Paths) string                  { return filepath.Join(mixerLeasePaths(p).State, "lease.json") }
func writeTalkLease(p Paths, lease talkLease) error { return writeJSON(talkLeasePath(p), lease) }
func readTalkLease(p Paths) (talkLease, bool) {
	var lease talkLease
	if readMixerJSON(talkLeasePath(p), 2048, &lease) != nil {
		return lease, false
	}
	return lease, validTalkLease(lease, time.Now())
}
func validTalkLease(lease talkLease, now time.Time) bool {
	if len(lease.Token) != 48 || lease.IssuedAt.IsZero() || lease.ExpiresAt.IsZero() || lease.IssuedAt.After(now.Add(time.Second)) {
		return false
	}
	for _, r := range lease.Token {
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f')) {
			return false
		}
	}
	return lease.ExpiresAt.After(now) && lease.ExpiresAt.Sub(lease.IssuedAt) <= mixerTalkLease && lease.ExpiresAt.Sub(now) <= mixerTalkLease
}
func sameTalkToken(a, b string) bool {
	return len(a) == 48 && len(b) == 48 && subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
func talkLock(ctx context.Context, p Paths) (func(), error) {
	ctx, cancel := context.WithTimeout(ctx, 350*time.Millisecond)
	defer cancel()
	unlock, err := Lock(ctx, mixerLeasePaths(p))
	if err != nil {
		return nil, errors.New("microphone lease is busy; hold-to-talk remains muted or will expire")
	}
	return unlock, nil
}

func openMixerControl(ctx context.Context, p Paths) (*automation.Client, error) {
	secret, err := loadCredentials(p)
	if err != nil {
		return nil, errors.New("managed OBS credentials are unavailable")
	}
	c, err := connect(ctx, secret, 300*time.Millisecond)
	if err != nil {
		return nil, errors.New("managed OBS control is unavailable; microphone state is unconfirmed")
	}
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		_ = c.Close()
		return nil, errUnmanaged
	}
	return c, nil
}
func muteTalkInput(ctx context.Context, p Paths) error {
	if process, listener := presence(p); process == "absent" && !listener {
		return nil
	}
	c, err := openMixerControl(ctx, p)
	if err != nil {
		return err
	}
	defer c.Close()
	return c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture")
}
func mixerTalkStart(ctx context.Context, p Paths, token string) (MixerResult, error) {
	ctx, cancel := context.WithTimeout(ctx, 1700*time.Millisecond)
	defer cancel()
	unlock, err := talkLock(ctx, p)
	if err != nil {
		return MixerResult{}, err
	}
	defer unlock()
	pref, err := MixerSettings(p, mixerLegacySettings(p))
	if err != nil {
		return MixerResult{}, err
	}
	if !pref.MicrophoneEnabled || !pref.PushToTalk || pref.MicrophoneMuted {
		return MixerResult{}, errors.New("enable and explicitly arm microphone hold-to-talk first")
	}
	prior, valid := readTalkLease(p)
	if token != "" {
		if !valid || !sameTalkToken(prior.Token, token) {
			return MixerResult{}, errors.New("hold-to-talk lease expired; release and press again")
		}
		if !mixerGuardianAlive(p) {
			// Refuse extension when the independent owner is stale or dead. Only this
			// failure path attempts bounded safety mute; the healthy renewal stays a
			// private file/proc check with no OBS, Pulse or full status query.
			prior.ExpiresAt = time.Now().UTC()
			_ = writeTalkLease(p, prior)
			cleanupCtx, done := context.WithTimeout(ctx, 500*time.Millisecond)
			muteErr := muteTalkInput(cleanupCtx, p)
			done()
			if muteErr == nil {
				_ = writeTalkLease(p, talkLease{})
				return MixerResult{}, errors.New("microphone privacy observer stopped; stream microphone mute confirmed, release and press again")
			}
			noteMixer(p, "control-unconfirmed", prior.Token)
			return MixerResult{}, errors.New("microphone privacy observer stopped and mute is unconfirmed; inspect managed OBS")
		}
		// Renewal deliberately performs no OBS/status/meter/device query. The
		// existing independent guardian already owns privacy cleanup.
		now := time.Now().UTC()
		prior.IssuedAt = now
		prior.ExpiresAt = now.Add(mixerTalkLease)
		if err = writeTalkLease(p, prior); err != nil {
			return MixerResult{}, err
		}
		return MixerResult{OK: true, Message: "Hold-to-talk lease renewed", TalkToken: prior.Token, LeaseMS: int(mixerTalkLease / time.Millisecond), TalkExpiresAt: &prior.ExpiresAt}, nil
	}
	if valid {
		return MixerResult{}, errors.New("a hold-to-talk press is already active; release it before starting another")
	}
	devices, systemMuted, err := MixerDevices(ctx)
	device := selectedMixerDevice(pref, devices)
	if err != nil || device == "" {
		return MixerResult{}, errors.New("selected microphone is unavailable; hold-to-talk stayed muted")
	}
	if systemMuted[device] {
		return MixerResult{}, errors.New("the selected input is muted in SteamOS; stream controls do not change system settings")
	}
	c, err := openMixerControl(ctx, p)
	if err != nil {
		return MixerResult{}, err
	}
	defer c.Close()
	actual, err := c.AudioInputDevice(ctx, MicAudio, "pulse_input_capture")
	if err != nil || actual != device {
		return MixerResult{}, errors.New("microphone route changed; refresh the mixer and choose the intended input before talking")
	}
	// Establish mute and a private guardian before granting any unmute.
	if err = c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture"); err != nil {
		return MixerResult{}, err
	}
	token, err = newTalkToken()
	if err != nil {
		return MixerResult{}, err
	}
	now := time.Now().UTC()
	lease := talkLease{Token: token, IssuedAt: now, ExpiresAt: now.Add(mixerTalkLease)}
	if err = writeTalkLease(p, lease); err != nil {
		return MixerResult{}, err
	}
	if err = StartMixerWatch(p); err != nil {
		_ = writeTalkLease(p, talkLease{})
		return MixerResult{}, err
	}
	if _, valid = readTalkLease(p); !valid {
		_ = writeTalkLease(p, talkLease{})
		return MixerResult{}, errors.New("hold-to-talk setup exceeded its safety deadline; press again")
	}
	unmuted := false
	if _, err = c.SetMixerInput(ctx, MicAudio, &unmuted, nil); err != nil {
		lease.ExpiresAt = time.Now().UTC()
		_ = writeTalkLease(p, lease)
		return MixerResult{}, err
	}
	return MixerResult{OK: true, Message: "Stream microphone is active while held", TalkToken: token, LeaseMS: int(mixerTalkLease / time.Millisecond), TalkExpiresAt: &lease.ExpiresAt}, nil
}
func mixerTalkRelease(ctx context.Context, p Paths, token string, cancelAll bool) (MixerResult, error) {
	ctx, cancel := context.WithTimeout(ctx, 900*time.Millisecond)
	defer cancel()
	unlock, err := talkLock(ctx, p)
	if err != nil {
		return MixerResult{}, err
	}
	defer unlock()
	var lease talkLease
	leaseErr := readMixerJSON(talkLeasePath(p), 2048, &lease)
	if cancelAll && leaseErr == nil && lease.Token == "" {
		return MixerResult{OK: true, Message: "No hold-to-talk lease is active"}, nil
	}
	if cancelAll && os.IsNotExist(leaseErr) {
		return MixerResult{OK: true, Message: "No hold-to-talk lease is active"}, nil
	}
	if !cancelAll && lease.Token == "" && len(token) == 48 {
		return MixerResult{OK: true, Message: "Hold-to-talk is already ended"}, nil
	}
	if !cancelAll && !sameTalkToken(lease.Token, token) {
		return MixerResult{}, errors.New("hold-to-talk release does not own the active lease")
	}
	if lease.Token == "" && !cancelAll {
		return MixerResult{OK: true, Message: "Hold-to-talk is already ended"}, nil
	}
	// Keep an expired token until actual mute is confirmed. The detached guardian
	// can retry cleanup if this RPC loses its connection or the backend unloads.
	if lease.Token != "" {
		lease.ExpiresAt = time.Now().UTC()
		if err = writeTalkLease(p, lease); err != nil {
			return MixerResult{}, err
		}
	}
	process, listener := presence(p)
	if process == "absent" && !listener {
		_ = writeTalkLease(p, talkLease{})
		return MixerResult{OK: true, Message: "OBS is offline; hold-to-talk ended"}, nil
	}
	if err = muteTalkInput(ctx, p); err != nil {
		noteMixer(p, "control-unconfirmed", "")
		return MixerResult{}, errors.New("hold-to-talk ended, but OBS mute could not be confirmed; inspect managed OBS")
	}
	if err = writeTalkLease(p, talkLease{}); err != nil {
		return MixerResult{}, err
	}
	return MixerResult{OK: true, Message: "Stream microphone mute confirmed"}, nil
}

type mixerWatchRecord struct {
	PID      int       `json:"pid"`
	Watching bool      `json:"watching"`
	Updated  time.Time `json:"updated"`
}

func mixerWatchRecordPath(p Paths) string {
	return filepath.Join(mixerWatchPaths(p).State, "status.json")
}
func readMixerWatchRecord(p Paths) (mixerWatchRecord, bool) {
	var r mixerWatchRecord
	err := readMixerJSON(mixerWatchRecordPath(p), 2048, &r)
	age := time.Since(r.Updated)
	return r, err == nil && r.Watching && r.PID > 0 && age >= -time.Second && age < 500*time.Millisecond
}

// watchMixerWith uses a monotonic local deadline as well as bounded wall-clock
// leases. Clock changes cannot turn one heartbeat into an unlimited hot mic.
func watchMixerWith(ctx context.Context, p Paths, mute func(context.Context, Paths) error, pid int, interval time.Duration) error {
	lockCtx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
	unlock, err := Lock(lockCtx, mixerWatchPaths(p))
	cancel()
	if err != nil {
		return nil
	}
	defer unlock()
	update := func(watching bool) {
		_ = writeJSON(mixerWatchRecordPath(p), mixerWatchRecord{PID: pid, Watching: watching, Updated: time.Now().UTC()})
	}
	update(true)
	defer update(false)
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	var lastExpiry time.Time
	var localDeadline time.Time
	cleanup := func() error {
		cleanupCtx, done := context.WithTimeout(context.Background(), 650*time.Millisecond)
		defer done()
		return mute(cleanupCtx, p)
	}
	for {
		lockCtx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		leaseUnlock, lockErr := Lock(lockCtx, mixerLeasePaths(p))
		cancel()
		if lockErr == nil {
			var lease talkLease
			leaseErr := readMixerJSON(talkLeasePath(p), 2048, &lease)
			valid := leaseErr == nil && validTalkLease(lease, time.Now())
			if leaseErr == nil && lease.Token == "" {
				finishMixerWatch(update, leaseUnlock)
				return nil
			} // Explicit control already took responsibility for cleanup.
			now := time.Now()
			if valid && !lease.ExpiresAt.Equal(lastExpiry) {
				lastExpiry = lease.ExpiresAt
				localDeadline = now.Add(min(mixerTalkLease, lease.ExpiresAt.Sub(now)))
			}
			if !valid || localDeadline.IsZero() || !now.Before(localDeadline) || ctx.Err() != nil {
				err = cleanup()
				if err == nil {
					_ = writeTalkLease(p, talkLease{})
					noteMixer(p, "talk-expired", lease.Token)
					finishMixerWatch(update, leaseUnlock)
					return nil
				}
				noteMixer(p, "control-unconfirmed", lease.Token)
				if ctx.Err() != nil {
					finishMixerWatch(update, leaseUnlock)
					return ctx.Err()
				}
			}
			leaseUnlock()
		}
		update(true)
		select {
		case <-ctx.Done():
			// Re-enter the lease critical section to retire readiness before another
			// press can start; shutdown cleanup must not race a replacement lease.
			continue
		case <-ticker.C:
		}
	}
}

// A new press must never accept an exiting guardian's fresh readiness record.
// Both writes happen before releasing the lease lock that a press must acquire.
func finishMixerWatch(update func(bool), unlock func()) { update(false); unlock() }
