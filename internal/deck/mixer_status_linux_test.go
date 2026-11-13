//go:build linux

package deck

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func TestStatusReconcilesCachedMixerWithManagedConnection(t *testing.T) {
	for _, scenario := range []string{"offline", "wrong-profile", "managed"} {
		t.Run(scenario, func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			_, secret, err := Load(p)
			if err != nil {
				t.Fatal(err)
			}
			var requests <-chan fixtureRequest
			if scenario == "wrong-profile" {
				requests = startControlFixture(t, secret.OBSPassword, true, true, false)
			}
			if scenario == "managed" {
				requests = startManagedFixture(t, false, false, false)
			}
			if scenario == "offline" {
				if process, listener := presence(p); process != "absent" || listener {
					t.Fatalf("offline fixture is not isolated: %s listener=%t", process, listener)
				}
			}
			pref := defaultMixerPreferences(DefaultSettings())
			pref.MicrophoneEnabled = true
			pref.MicrophoneMuted = true
			pref.MicrophoneDevice = "private-selected-input"
			pref.MicrophoneGainPercent = 65
			pref.GameGainPercent = 75
			if err = writeJSON(mixerPreferencesPath(p), pref); err != nil {
				t.Fatal(err)
			}
			now := time.Now().UTC()
			expiry := now.Add(1200 * time.Millisecond)
			micPeak, gamePeak := -12.0, -6.0
			cached := MixerSnapshot{SchemaVersion: 1, Known: true, State: "ready", Message: "Previously observed managed mixer", ObservedAt: now, ExpiresAt: now.Add(4 * time.Second), Preferences: pref,
				Microphone: MixerInput{Known: true, Available: true, Muted: true, GainPercent: 65, Signal: "signal", PeakDBFS: &micPeak}, Game: MixerInput{Known: true, Available: true, GainPercent: 75, Signal: "signal", PeakDBFS: &gamePeak},
				Devices: []MixerDevice{{ID: "private-selected-input", Label: "Private local headset", Available: true}}, Hardware: MixerHardwareInfo(), Talking: true, TalkExpiresAt: &expiry}
			if err = writeJSON(mixerCachePath(p), cached); err != nil {
				t.Fatal(err)
			}
			before := map[string][]byte{}
			for _, path := range []string{p.Config, p.Secrets, mixerPreferencesPath(p), mixerCachePath(p)} {
				before[path], err = os.ReadFile(path)
				if err != nil {
					t.Fatal(err)
				}
			}
			// A status reconciliation must never turn the cheap cache into a Pulse query.
			bin := t.TempDir()
			pulseMarker := filepath.Join(bin, "pulse-was-queried")
			quote := "'" + strings.ReplaceAll(pulseMarker, "'", "'\"'\"'") + "'"
			if err = os.WriteFile(filepath.Join(bin, "pactl"), []byte("#!/bin/sh\n: > "+quote+"\nexit 23\n"), 0700); err != nil {
				t.Fatal(err)
			}
			t.Setenv("PATH", bin)
			result := Status(context.Background(), p)
			if result.Mixer == nil {
				t.Fatal("saved mixer preferences disappeared")
			}
			actual := result.Mixer
			if !reflect.DeepEqual(actual.Preferences, pref) || !reflect.DeepEqual(actual.Devices, cached.Devices) || !actual.ObservedAt.Equal(cached.ObservedAt) || !actual.ExpiresAt.Equal(cached.ExpiresAt) {
				t.Fatal("connection reconciliation changed saved preferences, local labels or cache age", actual)
			}
			if scenario == "managed" {
				if !result.OutputKnown || !result.Connected || result.Runtime == nil || !actual.Known || actual.State != "ready" || !actual.Microphone.Known || !actual.Game.Known || !actual.Talking || actual.TalkExpiresAt == nil || actual.Microphone.PeakDBFS == nil || actual.Game.PeakDBFS == nil {
					t.Fatal("verified managed connection discarded its fresh bounded mixer observation", result)
				}
			} else {
				wantState := "unknown"
				if scenario == "offline" {
					wantState = "offline"
					if !result.OutputKnown || result.Connected {
						t.Fatal("offline output state was not confirmed stopped", result)
					}
				} else if result.OutputKnown || result.Runtime != nil {
					t.Fatal("ordinary profile ownership was accepted", result)
				}
				if actual.Known || actual.State != wantState || actual.Microphone.Known || actual.Game.Known || actual.Microphone.Available || actual.Game.Available || actual.Microphone.Signal != "unknown" || actual.Game.Signal != "unknown" || actual.Microphone.PeakDBFS != nil || actual.Game.PeakDBFS != nil || actual.Talking || actual.TalkExpiresAt != nil {
					t.Fatal("cached mixer contradicted current control/ownership evidence", actual)
				}
			}
			if _, err = os.Stat(pulseMarker); !os.IsNotExist(err) {
				t.Fatal("main status queried Pulse instead of using its cache")
			}
			count := 0
			for requests != nil && len(requests) > 0 {
				request := <-requests
				count++
				switch request.Type {
				case "GetVersion", "GetProfileList", "GetSceneCollectionList", "GetCurrentProgramScene", "GetRecordStatus", "GetStreamStatus", "GetReplayBufferStatus":
				default:
					t.Fatal("cache reconciliation added an OBS mixer query or mutation", request.Type)
				}
			}
			limit := 13
			if scenario == "wrong-profile" {
				limit = 5
			}
			if count > limit {
				t.Fatalf("status exceeded its existing runtime/stream/media request budget: %d > %d", count, limit)
			}
			for path, previous := range before {
				current, readErr := os.ReadFile(path)
				if readErr != nil || !bytes.Equal(previous, current) {
					t.Fatal("status reconciliation changed persistent mixer, settings or credential bytes", path, readErr)
				}
			}
			if _, _, err = Load(p); err != nil {
				t.Fatal("status invalidated the legacy settings/credential binding", err)
			}
		})
	}
}
