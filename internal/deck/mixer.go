package deck

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type MixerPreferences struct {
	Version               int     `json:"version"`
	MicrophoneEnabled     bool    `json:"microphone_enabled"`
	MicrophoneDevice      string  `json:"microphone_device"`
	MicrophoneMuted       bool    `json:"microphone_muted"`
	MicrophoneGainPercent float64 `json:"microphone_gain_percent"`
	GameGainPercent       float64 `json:"game_gain_percent"`
	PushToTalk            bool    `json:"push_to_talk"`
}
type MixerDevice struct {
	ID        string `json:"id"`
	Label     string `json:"label"`
	Default   bool   `json:"default"`
	Available bool   `json:"available"`
}
type MixerInput struct {
	Known       bool     `json:"known"`
	Available   bool     `json:"available"`
	Muted       bool     `json:"muted"`
	GainPercent float64  `json:"gain_percent"`
	SystemMuted bool     `json:"system_muted"`
	Signal      string   `json:"signal"`
	PeakDBFS    *float64 `json:"peak_dbfs"`
}
type MixerHardware struct {
	Model    string `json:"model"`
	Guidance string `json:"guidance"`
}
type MixerNotice struct {
	Code     string `json:"code"`
	Message  string `json:"message"`
	Revision string `json:"revision"`
}
type MixerSnapshot struct {
	SchemaVersion int              `json:"schema_version"`
	Known         bool             `json:"known"`
	State         string           `json:"state"`
	Message       string           `json:"message"`
	ObservedAt    time.Time        `json:"observed_at"`
	ExpiresAt     time.Time        `json:"expires_at"`
	Preferences   MixerPreferences `json:"preferences"`
	Microphone    MixerInput       `json:"microphone"`
	Game          MixerInput       `json:"game"`
	Devices       []MixerDevice    `json:"devices"`
	Hardware      MixerHardware    `json:"hardware"`
	Notice        MixerNotice      `json:"notice"`
	Talking       bool             `json:"talking"`
	TalkExpiresAt *time.Time       `json:"talk_expires_at,omitempty"`
}
type MixerResult struct {
	OK            bool           `json:"ok"`
	Message       string         `json:"message"`
	Mixer         *MixerSnapshot `json:"mixer,omitempty"`
	TalkToken     string         `json:"talk_token,omitempty"`
	LeaseMS       int            `json:"lease_ms,omitempty"`
	TalkExpiresAt *time.Time     `json:"talk_expires_at,omitempty"`
}

func mixerPreferencesPath(p Paths) string { return filepath.Join(filepath.Dir(p.Config), "mixer.json") }
func mixerCachePath(p Paths) string       { return filepath.Join(p.State, "mixer-status.json") }
func mixerNoticePath(p Paths) string      { return filepath.Join(p.State, "mixer-notice.json") }
func mixerLegacySettings(p Paths) Settings {
	s, _, err := Load(p)
	if err != nil {
		return DefaultSettings()
	}
	return s
}
func defaultMixerPreferences(s Settings) MixerPreferences {
	return MixerPreferences{Version: 1, MicrophoneEnabled: s.Microphone, MicrophoneDevice: "default", MicrophoneGainPercent: 100, GameGainPercent: 100}
}
func (pref MixerPreferences) Validate() error {
	if pref.Version != 1 {
		return errors.New("unsupported mixer preferences version")
	}
	if pref.MicrophoneDevice != "default" && !validMixerDeviceID(pref.MicrophoneDevice) {
		return errors.New("choose a microphone from the observed device list")
	}
	for _, gain := range []float64{pref.MicrophoneGainPercent, pref.GameGainPercent} {
		if math.IsNaN(gain) || math.IsInf(gain, 0) || gain < 0 || gain > 200 {
			return errors.New("audio gain must be 0–200 percent")
		}
	}
	return nil
}
func validMixerDeviceID(id string) bool {
	return validMixerText(id, 1024) && strings.TrimSpace(id) != "" && !strings.HasSuffix(id, ".monitor")
}
func validMixerText(value string, limit int) bool {
	if len(value) > limit {
		return false
	}
	for _, r := range value {
		if r < 32 || r == 127 {
			return false
		}
	}
	return true
}
func readMixerJSON(path string, limit int64, out any) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > limit {
		return errors.New("private mixer file is unsafe or too large")
	}
	file, err := openMixerFile(path)
	if err != nil {
		return err
	}
	defer file.Close()
	opened, statErr := file.Stat()
	if statErr != nil || !opened.Mode().IsRegular() || opened.Mode().Perm()&0077 != 0 || opened.Size() > limit || !os.SameFile(info, opened) {
		return errors.New("private mixer file changed during observation")
	}
	decoder := json.NewDecoder(io.LimitReader(file, limit+1))
	decoder.DisallowUnknownFields()
	if decoder.Decode(out) != nil {
		return errors.New("private mixer file is invalid")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return errors.New("private mixer file must contain one object")
	}
	return nil
}
func MixerSettings(p Paths, s Settings) (MixerPreferences, error) {
	pref := defaultMixerPreferences(s)
	err := readMixerJSON(mixerPreferencesPath(p), 8192, &pref)
	if os.IsNotExist(err) {
		return pref, nil
	}
	if err != nil {
		return pref, errors.New("mixer preferences could not be read; repair them in Desktop Setup")
	}
	return pref, pref.Validate()
}
func blankMixer(p Paths) MixerSnapshot {
	now := time.Now().UTC()
	pref, err := MixerSettings(p, mixerLegacySettings(p))
	r := MixerSnapshot{SchemaVersion: 1, State: "unknown", Message: "Current OBS mixer state is unconfirmed", ObservedAt: now, ExpiresAt: now.Add(4 * time.Second), Preferences: pref, Devices: []MixerDevice{}, Hardware: MixerHardwareInfo(), Microphone: MixerInput{Signal: "unknown"}, Game: MixerInput{Signal: "unknown"}, Notice: readMixerNotice(p)}
	if err != nil {
		r.Message = err.Error()
	}
	return r
}
func mixerNoticeMessage(code string) string {
	switch code {
	case "microphone-lost":
		return "The selected microphone became unavailable. Stream microphone is muted; choose a microphone and explicitly unmute when ready"
	case "microphone-changed":
		return "The microphone route changed. Stream microphone remains muted until you explicitly unmute it"
	case "system-microphone-muted":
		return "The selected microphone is muted in SteamOS. Stream controls do not change system microphone settings"
	case "talk-expired":
		return "Hold-to-talk ended and the stream microphone was muted"
	case "control-unconfirmed":
		return "OBS microphone control is unconfirmed. Inspect managed OBS; mute could not be verified"
	default:
		return "Microphone state is available in the local mixer"
	}
}

type mixerNoticeRecord struct {
	Code        string `json:"code"`
	Revision    string `json:"revision"`
	Fingerprint string `json:"fingerprint"`
}

func readMixerNotice(p Paths) MixerNotice {
	var record mixerNoticeRecord
	if readMixerJSON(mixerNoticePath(p), 2048, &record) != nil {
		return MixerNotice{}
	}
	switch record.Code {
	case "microphone-lost", "microphone-changed", "system-microphone-muted", "talk-expired", "control-unconfirmed":
	default:
		return MixerNotice{}
	}
	return MixerNotice{Code: record.Code, Message: mixerNoticeMessage(record.Code), Revision: record.Revision}
}
func noteMixer(p Paths, code, identity string) {
	sum := sha256.Sum256([]byte(code + "\x00" + identity))
	fingerprint := hex.EncodeToString(sum[:])
	var prior mixerNoticeRecord
	if readMixerJSON(mixerNoticePath(p), 2048, &prior) == nil && prior.Fingerprint == fingerprint {
		return
	}
	if err := writeJSON(mixerNoticePath(p), mixerNoticeRecord{Code: code, Revision: time.Now().UTC().Format(time.RFC3339Nano), Fingerprint: fingerprint}); err == nil {
		logEvent(p, "mixer."+code)
	}
}
func latchMixerMute(p Paths, pref MixerPreferences, code string) MixerPreferences {
	pref.MicrophoneMuted = true
	_ = writeJSON(mixerPreferencesPath(p), pref)
	noteMixer(p, code, pref.MicrophoneDevice)
	return pref
}

// ReadMixerSnapshot serves cached observations to high-frequency main status.
// Dedicated MixerStatus performs real OBS/device/meter queries. Stale is unknown.
func ReadMixerSnapshot(p Paths) MixerSnapshot {
	var r MixerSnapshot
	if readMixerJSON(mixerCachePath(p), 128*1024, &r) != nil {
		return blankMixer(p)
	}
	now := time.Now()
	if r.SchemaVersion != 1 || r.ObservedAt.After(now.Add(time.Second)) || !r.ExpiresAt.After(now) || r.Preferences.Validate() != nil {
		r.Known = false
		r.State = "unknown"
		r.Microphone.Known = false
		r.Game.Known = false
		r.Microphone.Signal = "unknown"
		r.Game.Signal = "unknown"
		r.Message = "Mixer observations expired; refresh microphone status before relying on them"
	}
	r.Hardware = MixerHardwareInfo()
	r.Notice = readMixerNotice(p)
	return r
}

func MixerStatus(ctx context.Context, p Paths) MixerSnapshot {
	r := blankMixer(p)
	ctx, cancel := context.WithTimeout(ctx, 2200*time.Millisecond)
	defer cancel()
	devices, systemMuted, err := MixerDevices(ctx)
	if err == nil {
		r.Devices = devices
		r.Microphone.Available = selectedMixerDevice(r.Preferences, devices) != ""
		if id := selectedMixerDevice(r.Preferences, devices); id != "" {
			r.Microphone.SystemMuted = systemMuted[id]
		}
	}
	process, listener := presence(p)
	if process == "absent" && !listener {
		r.State = "offline"
		r.Message = "OBS is offline; saved mixer preferences apply to the next explicit output"
		_ = writeJSON(mixerCachePath(p), r)
		return r
	}
	secret, err := loadCredentials(p)
	if err != nil {
		return r
	}
	c, err := connect(ctx, secret, 350*time.Millisecond)
	if err != nil {
		return r
	}
	defer c.Close()
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return r
	}
	game, gameErr := c.MixerInput(ctx, GameAudio)
	if gameErr == nil {
		r.Game.Known = true
		r.Game.Available = true
		r.Game.Muted = game.Muted
		r.Game.GainPercent = game.GainPercent
	}
	mic, micErr := c.MixerInput(ctx, MicAudio)
	if micErr == nil {
		r.Microphone.Known = true
		r.Microphone.Muted = mic.Muted
		r.Microphone.GainPercent = mic.GainPercent
	}
	if r.Preferences.MicrophoneEnabled && micErr == nil {
		selected := selectedMixerDevice(r.Preferences, r.Devices)
		actual, routeErr := c.AudioInputDevice(ctx, MicAudio, "pulse_input_capture")
		if selected == "" || actual != selected {
			r.Microphone.Available = false
		}
		if routeErr != nil {
			r.Microphone.Known = false
			micErr = errors.New("microphone route is unconfirmed")
		}
	}
	lease, valid := readTalkLease(p)
	if valid {
		r.Talking = true
		expiry := lease.ExpiresAt
		r.TalkExpiresAt = &expiry
	}
	r.Known = gameErr == nil && (micErr == nil || !r.Preferences.MicrophoneEnabled)
	if r.Known {
		r.State = "ready"
		r.Message = "Observed OBS source mixer; SteamOS defaults and system volume are unchanged"
	}
	stream, _ := c.StreamStatus(ctx)
	media, _ := c.MediaStatus(ctx)
	if stream.Active || media.Recording.Active || media.ReplayActive {
		for _, item := range []struct {
			name   string
			target *MixerInput
		}{{GameAudio, &r.Game}, {MicAudio, &r.Microphone}} {
			if !item.target.Known || item.target.Muted {
				continue
			}
			meterCtx, done := context.WithTimeout(ctx, 200*time.Millisecond)
			meter, e := automation.ObserveAudioSignal(meterCtx, automation.Config{Address: "127.0.0.1:" + Port, Password: secret.OBSPassword, Timeout: 150 * time.Millisecond}, item.name, 120*time.Millisecond)
			done()
			if e == nil {
				item.target.Signal = meter.State
				if meter.Peak > 0 {
					db := 20 * math.Log10(meter.Peak)
					item.target.PeakDBFS = &db
				}
			}
		}
	}
	r.Notice = readMixerNotice(p)
	_ = writeJSON(mixerCachePath(p), r)
	return r
}

// discoverMixerAudio preserves explicit device choice. A missing microphone is
// a fail-muted microphone state, not permission to choose a different input.
func discoverMixerAudio(ctx context.Context, p Paths, s Settings) (AudioRouting, error) {
	pref, err := MixerSettings(p, s)
	if err != nil {
		return AudioRouting{}, err
	}
	route, err := DiscoverAudio(ctx, false)
	if err != nil {
		return route, err
	}
	route.MicrophoneRequested = pref.MicrophoneEnabled
	route.MicrophoneStreamMuted = pref.MicrophoneMuted || pref.PushToTalk
	if !pref.MicrophoneEnabled {
		return route, nil
	}
	devices, systemMuted, err := MixerDevices(ctx)
	if err != nil {
		return route, err
	}
	route.MicrophoneDevice = selectedMixerDevice(pref, devices)
	if route.MicrophoneDevice == "" {
		route.MicrophoneMuted = true
		return route, nil
	}
	route.MicrophoneMuted = systemMuted[route.MicrophoneDevice]
	return route, nil
}
func selectedMixerDevice(pref MixerPreferences, devices []MixerDevice) string {
	for _, device := range devices {
		if device.Available && ((pref.MicrophoneDevice == "default" && device.Default) || device.ID == pref.MicrophoneDevice) {
			return device.ID
		}
	}
	return ""
}

type MixerRequest struct {
	Action      string          `json:"action"`
	Token       string          `json:"token,omitempty"`
	Preferences json.RawMessage `json:"preferences,omitempty"`
}
type mixerPatch struct {
	Version               *int     `json:"version,omitempty"`
	MicrophoneEnabled     *bool    `json:"microphone_enabled,omitempty"`
	MicrophoneDevice      *string  `json:"microphone_device,omitempty"`
	MicrophoneMuted       *bool    `json:"microphone_muted,omitempty"`
	MicrophoneGainPercent *float64 `json:"microphone_gain_percent,omitempty"`
	GameGainPercent       *float64 `json:"game_gain_percent,omitempty"`
	PushToTalk            *bool    `json:"push_to_talk,omitempty"`
}

func decodeMixerRequest(reader io.Reader) (MixerRequest, error) {
	var input MixerRequest
	b, e := io.ReadAll(io.LimitReader(reader, 16385))
	if e != nil || len(b) > 16384 {
		return input, errors.New("mixer request is too large")
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.DisallowUnknownFields()
	if d.Decode(&input) != nil {
		return input, errors.New("invalid mixer JSON")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return input, errors.New("mixer requires exactly one JSON object")
	}
	return input, nil
}

// MixerAction's configure branch requires the normal control lease held by its
// CLI caller. Talk operations own their short independent lease, so heartbeats
// never wait behind a long output startup or a slow status/meter query.
func MixerAction(ctx context.Context, p Paths, reader io.Reader) (MixerResult, error) {
	input, err := decodeMixerRequest(reader)
	if err != nil {
		return MixerResult{}, err
	}
	switch input.Action {
	case "status", "devices":
		r := MixerStatus(ctx, p)
		return MixerResult{OK: true, Message: r.Message, Mixer: &r}, nil
	case "talk-start":
		return mixerTalkStart(ctx, p, input.Token)
	case "talk-release":
		return mixerTalkRelease(ctx, p, input.Token, false)
	case "talk-cancel":
		return mixerTalkRelease(ctx, p, "", true)
	case "configure":
		return configureMixer(ctx, p, input.Preferences)
	default:
		return MixerResult{}, errors.New("choose status, devices, configure, talk-start, talk-release or talk-cancel")
	}
}
func patchMixerPreferences(pref MixerPreferences, patch mixerPatch) (MixerPreferences, error) {
	old := pref
	if patch.Version != nil {
		pref.Version = *patch.Version
	}
	if patch.MicrophoneEnabled != nil {
		pref.MicrophoneEnabled = *patch.MicrophoneEnabled
	}
	if patch.MicrophoneDevice != nil {
		pref.MicrophoneDevice = *patch.MicrophoneDevice
	}
	if patch.MicrophoneMuted != nil {
		pref.MicrophoneMuted = *patch.MicrophoneMuted
	}
	if patch.MicrophoneGainPercent != nil {
		pref.MicrophoneGainPercent = *patch.MicrophoneGainPercent
	}
	if patch.GameGainPercent != nil {
		pref.GameGainPercent = *patch.GameGainPercent
	}
	if patch.PushToTalk != nil {
		pref.PushToTalk = *patch.PushToTalk
	}
	if (pref.MicrophoneDevice != old.MicrophoneDevice || (pref.MicrophoneEnabled && !old.MicrophoneEnabled)) && patch.MicrophoneMuted == nil {
		pref.MicrophoneMuted = true
	}
	if (!old.PushToTalk && pref.PushToTalk && patch.MicrophoneMuted == nil) || !pref.MicrophoneEnabled {
		pref.MicrophoneMuted = true
	}
	if err := pref.Validate(); err != nil {
		return pref, err
	}
	return pref, nil
}

func configureMixer(ctx context.Context, p Paths, raw json.RawMessage) (MixerResult, error) {
	pref, err := MixerSettings(p, mixerLegacySettings(p))
	if err != nil {
		return MixerResult{}, err
	}
	var patch mixerPatch
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if d.Decode(&patch) != nil {
		return MixerResult{}, errors.New("send a partial mixer preferences object")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return MixerResult{}, errors.New("preferences must contain one object")
	}
	pref, err = patchMixerPreferences(pref, patch)
	if err != nil {
		return MixerResult{}, err
	}
	devices, _, deviceErr := MixerDevices(ctx)
	if pref.MicrophoneEnabled && pref.MicrophoneDevice != "default" && (deviceErr != nil || selectedMixerDevice(pref, devices) == "") {
		return MixerResult{}, errors.New("selected microphone is unavailable; refresh devices and choose an observed microphone")
	}
	process, listener := presence(p)
	if process == "unknown" {
		return MixerResult{}, errors.New("managed OBS ownership is unknown; mixer preferences were not changed")
	}
	var c *automation.Client
	if process != "absent" || listener {
		secret, e := loadCredentials(p)
		if e != nil {
			return MixerResult{}, e
		}
		c, e = connect(ctx, secret, 500*time.Millisecond)
		if e != nil {
			return MixerResult{}, e
		}
		defer c.Close()
		runtime, e := c.RuntimeStatus(ctx)
		if e != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
			return MixerResult{}, errUnmanaged
		}
	}
	leaseCtx, done := context.WithTimeout(ctx, 300*time.Millisecond)
	unlock, err := Lock(leaseCtx, mixerLeasePaths(p))
	done()
	if err != nil {
		return MixerResult{}, errors.New("a short microphone operation is busy; retry")
	}
	defer unlock()
	if c != nil {
		if err = c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture"); err != nil {
			return MixerResult{}, err
		}
	}
	if err = writeTalkLease(p, talkLease{}); err != nil {
		return MixerResult{}, err
	}
	// Persist fail-closed state before any unmute. A partial failure leaves an
	// explicit saved preference plus unknown actual state; never a success toast.
	if err = writeJSON(mixerPreferencesPath(p), pref); err != nil {
		return MixerResult{}, err
	}
	if c != nil {
		if err = applyMixer(ctx, c, p, pref, true); err != nil {
			cleanupCtx, cleanupDone := context.WithTimeout(context.Background(), 650*time.Millisecond)
			_ = c.MuteInputIfPresent(cleanupCtx, MicAudio, "pulse_input_capture")
			cleanupDone()
			noteMixer(p, "control-unconfirmed", "")
			return MixerResult{}, err
		}
	}
	r := MixerStatus(ctx, p)
	return MixerResult{OK: true, Message: "Stream mixer preferences saved and any connected OBS source changes confirmed; system volume was unchanged", Mixer: &r}, nil
}

func applyMixer(ctx context.Context, c *automation.Client, p Paths, pref MixerPreferences, createMicrophone bool) error {
	if _, err := c.SetMixerInput(ctx, GameAudio, nil, &pref.GameGainPercent); err != nil {
		return err
	}
	if !pref.MicrophoneEnabled {
		return c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture")
	}
	devices, _, err := MixerDevices(ctx)
	if err != nil {
		return err
	}
	device := selectedMixerDevice(pref, devices)
	if device == "" {
		if err = c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture"); err != nil {
			return err
		}
		latchMixerMute(p, pref, "microphone-lost")
		return nil
	}
	if createMicrophone {
		if err = c.EnsureMutedPulseInput(ctx, LiveScene, MicAudio, device); err != nil {
			return err
		}
		for _, scene := range []string{LiveScene, GameScene, IdleScene} {
			if err = c.EnsureSceneItem(ctx, scene, MicAudio); err != nil {
				return err
			}
			if err = c.SetSceneItemEnabledIfPresent(ctx, scene, MicAudio, true); err != nil {
				return err
			}
		}
		_, err = c.ConfigureAudioInputPolicy(ctx, MicAudio, device, pref.MicrophoneMuted || pref.PushToTalk, pref.MicrophoneGainPercent)
		return err
	}
	_, err = c.SetMixerInput(ctx, MicAudio, &pref.MicrophoneMuted, &pref.MicrophoneGainPercent)
	return err
}

// token is an ephemeral local lease capability, never an OBS credential.
func newTalkToken() (string, error) {
	var b [24]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}
