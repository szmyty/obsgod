//go:build linux

package deck

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/pkg/automation"
)

// Keep source audio and independent output states observable while reusing the
// capture protocol fixture. Video maintenance must issue no audio/output writes.
type microphoneVideoFixture struct {
	*videoFixture
	recording, replay bool
	muted             bool
	gain              float64
}

func newMicrophoneVideoFixture(t *testing.T, muted bool) *microphoneVideoFixture {
	t.Helper()
	f := &microphoneVideoFixture{videoFixture: newVideoFixture(t), muted: muted, gain: 0.73}
	f.inputs[MicAudio] = &videoInput{kind: "pulse_input_capture", settings: map[string]any{"device_id": "fixture-mic"}}
	for _, scene := range []string{LiveScene, IdleScene, GameScene} {
		f.next++
		f.scenes[scene][MicAudio] = &videoItem{id: f.next, enabled: true}
	}
	return f
}

func (f *microphoneVideoFixture) client(t *testing.T) (*automation.Client, func(context.Context, Secrets) (*automation.Client, error)) {
	t.Helper()
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
		var identify any
		if c.ReadJSON(&identify) != nil {
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D fixtureRequest `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			f.requests = append(f.requests, q.D)
			data := f.handle(q.D)
			switch q.D.Type {
			case "GetRecordStatus":
				data["outputActive"] = f.recording
			case "GetReplayBufferStatus":
				data["outputActive"] = f.replay
			case "SetInputMute":
				if q.D.Data["inputName"] == MicAudio {
					f.muted, _ = q.D.Data["inputMuted"].(bool)
				}
			case "SetInputVolume":
				if q.D.Data["inputName"] == MicAudio {
					f.gain, _ = q.D.Data["inputVolumeMul"].(float64)
				}
			}
			f.mu.Unlock()
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	dial := func(ctx context.Context, _ Secrets) (*automation.Client, error) {
		return automation.Connect(ctx, automation.Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	}
	c, err := dial(context.Background(), Secrets{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c, dial
}

func (f *microphoneVideoFixture) assertAudioUntouched(t *testing.T, muted bool) {
	t.Helper()
	if f.muted != muted || f.gain != 0.73 || f.inputs[MicAudio].settings["device_id"] != "fixture-mic" {
		t.Errorf("video maintenance changed source audio: muted=%v gain=%v settings=%v", f.muted, f.gain, f.inputs[MicAudio].settings)
	}
	for _, q := range f.requests {
		switch q.Type {
		case "StartStream", "StopStream", "StartRecord", "StopRecord", "StartReplayBuffer", "StopReplayBuffer", "SaveReplayBuffer":
			t.Errorf("video maintenance changed output through %s", q.Type)
		case "SetInputMute", "ToggleInputMute", "SetInputVolume", "SetInputAudioTracks", "SetInputAudioMonitorType":
			t.Errorf("video maintenance changed audio through %s", q.Type)
		case "SetInputSettings", "CreateInput":
			if q.Data["inputName"] == MicAudio || q.Data["inputName"] == GameAudio {
				t.Errorf("video maintenance rewrote audio through %s", q.Type)
			}
		}
	}
}

func TestCaptureWatchPreservesEffectiveMixerMicrophoneThroughGameAndIdle(t *testing.T) {
	for _, policy := range []struct {
		name                   string
		legacy, enabled, muted bool
		pushToTalk             bool
	}{
		{name: "mixer-enabled", enabled: true},
		{name: "explicitly-muted", enabled: true, muted: true},
		{name: "push-to-talk", enabled: true, pushToTalk: true},
		{name: "mixer-disabled-overrides-legacy", legacy: true, muted: true},
	} {
		for _, output := range []struct {
			name                      string
			stream, recording, replay bool
		}{
			{name: "stream", stream: true},
			{name: "recording", recording: true},
			{name: "replay", replay: true},
			{name: "all", stream: true, recording: true, replay: true},
		} {
			t.Run(policy.name+"/"+output.name, func(t *testing.T) {
				muted := policy.muted || policy.pushToTalk
				f := newMicrophoneVideoFixture(t, muted)
				f.active, f.recording, f.replay = output.stream, output.recording, output.replay
				_, dial := f.client(t)
				p := testPaths(t)
				s := DefaultSettings()
				s.CaptureMode, s.Microphone = "game", policy.legacy
				pref := defaultMixerPreferences(s)
				pref.MicrophoneEnabled, pref.MicrophoneMuted, pref.PushToTalk = policy.enabled, policy.muted, policy.pushToTalk
				pref.MicrophoneDevice, pref.MicrophoneGainPercent, pref.GameGainPercent = "fixture-mic", 73, 61
				if err := writeJSON(mixerPreferencesPath(p), pref); err != nil {
					t.Fatal(err)
				}
				before, err := os.ReadFile(mixerPreferencesPath(p))
				if err != nil {
					t.Fatal(err)
				}
				identities := []uint32{42, 42, 0, 43, 43, 0}
				wantScenes := []string{IdleScene, GameScene, IdleScene, IdleScene, GameScene, IdleScene}
				index := 0
				ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
				defer cancel()
				err = watchCaptureWith(ctx, p, captureWatchDeps{
					load:    func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil },
					connect: dial,
					discover: func(context.Context) GameIdentity {
						if index > 0 {
							f.mu.Lock()
							if f.scene != wantScenes[index-1] {
								t.Errorf("cycle %d scene=%q want %q", index, f.scene, wantScenes[index-1])
							}
							for _, scene := range []string{IdleScene, GameScene} {
								// Game scene membership is applied with the first usable target.
								if scene == GameScene && index < 2 && !policy.enabled {
									continue
								}
								if f.scenes[scene][MicAudio].enabled != policy.enabled {
									t.Errorf("cycle %d %s microphone membership=%v want %v", index, scene, f.scenes[scene][MicAudio].enabled, policy.enabled)
								}
							}
							f.assertAudioUntouched(t, muted)
							f.mu.Unlock()
						}
						if index == len(identities) {
							cancel()
							return GameIdentity{State: "idle"}
						}
						id := identities[index]
						index++
						if id == 0 {
							return GameIdentity{State: "idle"}
						}
						return GameIdentity{AppID: id, State: "running"}
					},
					interval: time.Millisecond,
				})
				if !errors.Is(err, context.Canceled) || index != len(identities) {
					t.Fatalf("observer exit=%v completed cycles=%d", err, index)
				}
				after, err := os.ReadFile(mixerPreferencesPath(p))
				if err != nil || string(before) != string(after) {
					t.Fatalf("video maintenance rewrote mixer preferences: %v", err)
				}
				f.mu.Lock()
				defer f.mu.Unlock()
				f.assertAudioUntouched(t, muted)
				if f.active != output.stream || f.recording != output.recording || f.replay != output.replay {
					t.Fatal("video maintenance changed independent outputs")
				}
			})
		}
	}
}

func TestCaptureWatchRefreshesMixerMicrophonePolicyForCachedGame(t *testing.T) {
	f := newMicrophoneVideoFixture(t, true)
	_, dial := f.client(t)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	pref := defaultMixerPreferences(s)
	pref.MicrophoneEnabled, pref.MicrophoneMuted = true, true
	if err := writeJSON(mixerPreferencesPath(p), pref); err != nil {
		t.Fatal(err)
	}
	policies := []bool{true, true, false, false, true, true}
	index := 0
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	err := watchCaptureWith(ctx, p, captureWatchDeps{
		load:    func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil },
		connect: dial,
		discover: func(context.Context) GameIdentity {
			if index > 0 {
				f.mu.Lock()
				for _, scene := range []string{IdleScene, GameScene} {
					if f.scenes[scene][MicAudio].enabled != policies[index-1] {
						t.Errorf("cycle %d %s microphone membership=%v want %v", index, scene, f.scenes[scene][MicAudio].enabled, policies[index-1])
					}
				}
				f.assertAudioUntouched(t, true)
				f.mu.Unlock()
			}
			if index == len(policies) {
				cancel()
				return GameIdentity{State: "idle"}
			}
			pref.MicrophoneEnabled = policies[index]
			if err := writeJSON(mixerPreferencesPath(p), pref); err != nil {
				t.Error(err)
				cancel()
			}
			index++
			return GameIdentity{AppID: 42, State: "running"}
		},
		interval: time.Millisecond,
	})
	if !errors.Is(err, context.Canceled) || index != len(policies) {
		t.Fatalf("observer exit=%v completed cycles=%d", err, index)
	}
}

func TestEnsureVideoResolvesEffectiveMicrophoneBeforeMutatingOBS(t *testing.T) {
	for _, mode := range []string{"game", "screen"} {
		t.Run(mode, func(t *testing.T) {
			f := newMicrophoneVideoFixture(t, true)
			c, _ := f.client(t)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = mode
			pref := defaultMixerPreferences(s)
			pref.MicrophoneEnabled, pref.MicrophoneMuted = true, true
			if err := writeJSON(mixerPreferencesPath(p), pref); err != nil {
				t.Fatal(err)
			}
			if err := ensureVideoForGame(context.Background(), c, p, s, GameIdentity{AppID: 42, State: "running"}); err != nil {
				t.Fatal(err)
			}
			f.mu.Lock()
			for _, scene := range []string{IdleScene, f.scene} {
				if !f.scenes[scene][MicAudio].enabled {
					t.Errorf("mixer-enabled microphone disabled in %s", scene)
				}
			}
			f.assertAudioUntouched(t, true)
			f.requests = nil
			f.mu.Unlock()
			if err := os.WriteFile(mixerPreferencesPath(p), []byte("invalid"), 0600); err != nil {
				t.Fatal(err)
			}
			if err := ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err == nil {
				t.Fatal("unreadable effective microphone policy was accepted")
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			if len(f.requests) != 0 {
				t.Fatalf("OBS was changed before effective microphone policy was known: %v", f.requests)
			}
			f.assertAudioUntouched(t, true)
		})
	}
}

func TestEffectiveVideoSettingsUsesLegacyOnlyWithoutMixerPreferences(t *testing.T) {
	for _, enabled := range []bool{false, true} {
		s := DefaultSettings()
		s.Microphone = enabled
		got, err := effectiveVideoSettings(testPaths(t), s)
		if err != nil || !reflect.DeepEqual(got, s) {
			t.Fatalf("legacy microphone=%v video policy=%+v err=%v", enabled, got, err)
		}
	}
}
