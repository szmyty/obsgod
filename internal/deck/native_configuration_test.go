package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/szmyty/obsgod/pkg/automation"
)

func configurationStopped() Result {
	return Result{OK: true, State: "stopped", Process: "absent", OutputKnown: true, Media: &MediaSnapshot{Known: true}}
}

func configurationProbe(state Result) func(context.Context, Paths) Result {
	return func(context.Context, Paths) Result { return state }
}

func configurationLocal(process string) func(Paths) ConnectionDetails {
	return func(Paths) ConnectionDetails {
		return ConnectionDetails{OK: true, Host: "127.0.0.1", Port: Port, Authentication: true, Process: process, OutputKnown: process == "absent", State: "stopped"}
	}
}

func configurationPair(t *testing.T, p Paths) [2][]byte {
	t.Helper()
	var pair [2][]byte
	for index, path := range []string{p.Config, p.Secrets} {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		pair[index] = data
	}
	return pair
}

func TestNativeConfigurationFirstRunIsReadOnlyAndHasNoInventedKey(t *testing.T) {
	p := testPaths(t)
	view := readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("absent"))
	if !view.OK || view.SchemaVersion != 1 || view.Configured || view.KeyConfigured || !view.CanConfigure || view.CanClose || !view.OutputKnown || view.Settings != DefaultSettings() {
		t.Fatal("first-run defaults or availability are wrong", view)
	}
	for _, path := range []string{p.Config, p.Secrets, p.State, p.OBSConfig, p.Videos} {
		if _, err := os.Lstat(path); !os.IsNotExist(err) {
			t.Fatal("read created first-run state", path, err)
		}
	}
}

func TestNativeConfigurationReadViewDoesNotReadBackSecrets(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	_, secret, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	before := configurationPair(t, p)
	view := readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("absent"))
	data, err := json.Marshal(view)
	if err != nil || !view.OK || !view.Configured || !view.KeyConfigured || view.Settings.Server != "rtmps://example.invalid/app" {
		t.Fatal("saved view unavailable", view, err)
	}
	for _, private := range []string{secret.StreamKey, secret.OBSPassword, secret.SettingsHash, "stream_key", "obs_password", "settings_hash"} {
		if bytes.Contains(data, []byte(private)) {
			t.Fatal("configuration view disclosed secret data")
		}
	}
	if !reflect.DeepEqual(before, configurationPair(t, p)) {
		t.Fatal("configuration read rewrote saved pair")
	}
	if err := os.Remove(p.Secrets); err != nil {
		t.Fatal(err)
	}
	view = readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("absent"))
	if !view.OK || view.Configured || view.KeyConfigured || !view.CanConfigure || view.Settings.Server != "rtmps://example.invalid/app" {
		t.Fatal("missing key discarded repairable saved settings", view)
	}
}

func TestNativeConfigurationPartialEditPreservesAdvancedSettingsAndPassword(t *testing.T) {
	p := testPaths(t)
	input := strings.TrimSuffix(fixtureSettings, "}") + `,"capture_mode":"game","idle_style":"image","idle_text":"Between games","width":960,"height":540,"idle_media":"` + strings.Repeat("a", 64) + `.png","idle_media_rights":"Owner-created image; retained attribution"}`
	before, err := Configure(p, strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	_, secret, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	after, err := configureFields(context.Background(), p, strings.NewReader(`{"bitrate":6000,"fps":60,"microphone":true}`), configurationProbe(configurationStopped()))
	if err != nil {
		t.Fatal(err)
	}
	want := before
	want.Bitrate, want.FPS, want.Microphone = 6000, 60, true
	loaded, changed, err := Load(p)
	if err != nil || after != want || loaded != want || changed.StreamKey != secret.StreamKey || changed.OBSPassword != secret.OBSPassword || changed.SettingsHash != settingsHash(want) || changed.SettingsHash == secret.SettingsHash {
		t.Fatal("limited merge lost advanced settings or credential binding", err)
	}
	if _, err := os.Lstat(p.OBSConfig); !os.IsNotExist(err) {
		t.Fatal("saving settings prepared or launched managed OBS", err)
	}
}

func TestNativeConfigurationDestinationAndExplicitReplacement(t *testing.T) {
	cases := []struct {
		name, request, key, server string
		wantOK                     bool
	}{
		{"same server omitted", `{"bitrate":6000}`, "fixture-never-real", "rtmps://example.invalid/app", true},
		{"same server blank", `{"stream_key":""}`, "fixture-never-real", "rtmps://example.invalid/app", true},
		{"new destination omitted", `{"server":"rtmps://other.invalid/app"}`, "", "", false},
		{"new destination blank", `{"server":"rtmps://other.invalid/app","stream_key":""}`, "", "", false},
		{"same destination replace omitted", `{"replace_key":true}`, "", "", false},
		{"same destination replace blank", `{"replace_key":true,"stream_key":""}`, "", "", false},
		{"replace account key", `{"replace_key":true,"stream_key":"new-private-fixture"}`, "new-private-fixture", "rtmps://example.invalid/app", true},
		{"new destination explicit", `{"server":"rtmps://other.invalid/app","stream_key":"other-private-fixture"}`, "other-private-fixture", "rtmps://other.invalid/app", true},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			before := configurationPair(t, p)
			_, original, _ := Load(p)
			_, err := configureFields(context.Background(), p, strings.NewReader(test.request), configurationProbe(configurationStopped()))
			if (err == nil) != test.wantOK {
				t.Fatal("unexpected save outcome", err)
			}
			if !test.wantOK {
				if !reflect.DeepEqual(before, configurationPair(t, p)) {
					t.Fatal("refusal changed credentials/settings")
				}
				return
			}
			s, secret, err := Load(p)
			if err != nil || s.Server != test.server || secret.StreamKey != test.key || secret.OBSPassword != original.OBSPassword || secret.SettingsHash != settingsHash(s) {
				t.Fatal("saved destination/key/password binding is wrong", err)
			}
		})
	}
}

func TestNativeConfigurationNewKeyRepairsBindingWithoutDiscardingPreferences(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	var altered Settings
	if err := readJSON(p.Config, &altered); err != nil {
		t.Fatal(err)
	}
	altered.Bitrate = 6000
	if err := writeJSON(p.Config, altered); err != nil {
		t.Fatal(err)
	}
	before := configurationPair(t, p)
	view := readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("absent"))
	if !view.OK || view.Configured || view.KeyConfigured || view.Settings.Bitrate != 6000 || !view.CanConfigure {
		t.Fatal("binding repair view lost saved preferences", view)
	}
	if _, err := configureFields(context.Background(), p, strings.NewReader(`{"fps":60}`), configurationProbe(configurationStopped())); err == nil || !reflect.DeepEqual(before, configurationPair(t, p)) {
		t.Fatal("blank key silently repaired mismatched binding")
	}
	if _, err := configureFields(context.Background(), p, strings.NewReader(`{"stream_key":"owner-reentered-fixture"}`), configurationProbe(configurationStopped())); err != nil {
		t.Fatal("explicit key could not repair binding", err)
	}
	s, secret, err := Load(p)
	if err != nil || s.Bitrate != 6000 || secret.StreamKey != "owner-reentered-fixture" {
		t.Fatal("binding repair lost preferences", err)
	}
}

func TestNativeConfigurationRejectsMalformedOrOutOfRangeFieldsWithoutWrites(t *testing.T) {
	inputs := []string{"", `{}`, `[]`, `null`, `{"bitrate":null}`, `{"bitrate":{}}`, `{"fps":[]}`, `{"fps":30.5}`, `{"fps":"30"}`, `{"microphone":"false"}`, `{"bitrate":6000,"bitrate":4500}`, `{"stream_key":"private-echo-marker","provider":"kick"}`, `{"fps":30} {}`, `{"width":1280}`, `{"height":720}`, `{"width":0,"height":720}`, `{"width":4000,"height":2000}`, `{"bitrate":999}`, `{"bitrate":8001}`, `{"fps":120}`, `{"encoder":"unknown"}`, `{"capture_mode":"guess"}`, `{"server":"https://example.invalid"}`, `{"server":"rtmps://user:private-echo-marker@example.invalid"}`, `{"stream_key":"private-echo-marker\t"}`, `{"stream_key":"   "}`, `{"stream_key":"` + strings.Repeat("x", 4097) + `"}`, `{"server":"` + strings.Repeat("x", 4097) + `"}`, strings.Repeat(" ", 16385)}
	for index, input := range inputs {
		p := testPaths(t)
		if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
			t.Fatal(err)
		}
		before := configurationPair(t, p)
		probes := 0
		_, err := configureFields(context.Background(), p, strings.NewReader(input), func(context.Context, Paths) Result { probes++; return configurationStopped() })
		if err == nil || strings.Contains(err.Error(), "private-echo-marker") || !reflect.DeepEqual(before, configurationPair(t, p)) || probes != 0 {
			t.Fatal("invalid input was accepted, disclosed, observed or changed state", index, err, probes)
		}
	}
}

func TestNativeConfigurationFirstSaveAndPairedResolution(t *testing.T) {
	p := testPaths(t)
	_, err := configureFields(context.Background(), p, strings.NewReader(`{"server":"rtmps://example.invalid/app","stream_key":"first-private-fixture","width":1920,"height":1080}`), configurationProbe(configurationStopped()))
	if err != nil {
		t.Fatal(err)
	}
	s, secret, err := Load(p)
	if err != nil || s.Width != 1920 || s.Height != 1080 || s.Bitrate != 4500 || secret.StreamKey != "first-private-fixture" || len(secret.OBSPassword) != 64 {
		t.Fatal("first save failed to reuse defaults and generate private control authentication", err)
	}
}

func TestNativeConfigurationRequiresPositiveClosedOutputState(t *testing.T) {
	cases := map[string]func(*Result){
		"failed":            func(s *Result) { s.OK = false },
		"unknown output":    func(s *Result) { s.OutputKnown = false },
		"active stream":     func(s *Result) { s.Stream.Active = true },
		"reconnecting":      func(s *Result) { s.Stream.Reconnecting = true },
		"recording":         func(s *Result) { s.Recording = true },
		"runtime recording": func(s *Result) { s.Runtime = &automation.RuntimeStatus{Recording: true} },
		"media recording":   func(s *Result) { s.Media.Recording.Active = true },
		"paused recording":  func(s *Result) { s.Media.Recording.Paused = true },
		"replay":            func(s *Result) { s.Media.ReplayActive = true },
		"media unknown":     func(s *Result) { s.Media.Known = false },
		"media absent":      func(s *Result) { s.Media = nil },
		"connected":         func(s *Result) { s.Connected = true },
		"running":           func(s *Result) { s.Process = "running" },
		"process unknown":   func(s *Result) { s.Process = "unknown" },
		"state unknown":     func(s *Result) { s.State = "unknown" },
	}
	for name, alter := range cases {
		t.Run(name, func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			before := configurationPair(t, p)
			state := configurationStopped()
			alter(&state)
			if _, err := configureFields(context.Background(), p, strings.NewReader(`{"bitrate":6000}`), configurationProbe(state)); err == nil || !reflect.DeepEqual(before, configurationPair(t, p)) {
				t.Fatal("unconfirmed or active output authorized a settings write")
			}
			view := readConfiguration(context.Background(), p, configurationProbe(state), configurationLocal(state.Process))
			if view.CanConfigure || view.CanClose {
				t.Fatal("unsafe state enabled mutation", view)
			}
		})
	}
}

func TestNativeConfigurationRechecksStateAndCancellationBeforeWriting(t *testing.T) {
	for _, cancelAfterFirst := range []bool{false, true} {
		p := testPaths(t)
		if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
			t.Fatal(err)
		}
		before := configurationPair(t, p)
		ctx, cancel := context.WithCancel(context.Background())
		calls := 0
		_, err := configureFields(ctx, p, strings.NewReader(`{"bitrate":6000}`), func(context.Context, Paths) Result {
			calls++
			state := configurationStopped()
			if cancelAfterFirst {
				cancel()
			} else if calls > 1 {
				state.Process = "unknown"
			}
			return state
		})
		cancel()
		if err == nil || !reflect.DeepEqual(before, configurationPair(t, p)) {
			t.Fatal("state change or cancellation permitted a write")
		}
	}
}

func TestNativeConfigurationCancellationDuringFinalObservationPreservesSavedPair(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	before := configurationPair(t, p)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	calls := 0
	_, err := configureFields(ctx, p, strings.NewReader(`{"bitrate":6000}`), func(context.Context, Paths) Result {
		calls++
		if calls == 2 {
			cancel()
		}
		return configurationStopped()
	})
	if err == nil || calls != 2 || !reflect.DeepEqual(before, configurationPair(t, p)) {
		t.Fatal("cancellation in the final closed-state observation permitted a write", err, calls)
	}
}

func TestNativeConfigurationInvalidSavedSettingsCannotAuthorizeClose(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p.Config, []byte("{invalid saved settings}"), 0600); err != nil {
		t.Fatal(err)
	}
	before := configurationPair(t, p)
	state := configurationStopped()
	state.Process, state.Connected = "running", true
	state.Runtime = &automation.RuntimeStatus{Profile: "OBSGod", Collection: "OBSGod"}
	view := readConfiguration(context.Background(), p, configurationProbe(state), configurationLocal("running"))
	if view.OK || view.CanConfigure || view.CanClose || !reflect.DeepEqual(before, configurationPair(t, p)) {
		t.Fatal("invalid settings granted a configuration action despite known idle output", view)
	}
}

func TestNativeConfigurationCloseRequiresIdleAuthenticatedManagedOBS(t *testing.T) {
	p := testPaths(t)
	state := configurationStopped()
	state.Process, state.Connected = "running", true
	state.Runtime = &automation.RuntimeStatus{Profile: "OBSGod", Collection: "OBSGod"}
	view := readConfiguration(context.Background(), p, configurationProbe(state), configurationLocal("running"))
	if !view.CanClose || view.CanConfigure {
		t.Fatal("positive idle managed OBS cannot be explicitly closed", view)
	}
	for _, alter := range []func(*Result){
		func(s *Result) { s.Runtime = nil },
		func(s *Result) { s.Runtime.Profile = "ordinary OBS" },
		func(s *Result) { s.Runtime.Collection = "other" },
		func(s *Result) { s.Media.ReplayActive = true },
		func(s *Result) { s.Media.Known = false },
		func(s *Result) { s.Stream.Reconnecting = true },
	} {
		state = configurationStopped()
		state.Process, state.Connected = "running", true
		state.Runtime = &automation.RuntimeStatus{Profile: "OBSGod", Collection: "OBSGod"}
		alter(&state)
		view = readConfiguration(context.Background(), p, configurationProbe(state), configurationLocal("running"))
		if view.CanClose || view.CanConfigure {
			t.Fatal("unknown, active or foreign OBS enabled mutation", view)
		}
	}
	view = readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("unknown"))
	if view.CanConfigure || view.OutputKnown {
		t.Fatal("later presence uncertainty left earlier closed status authoritative", view)
	}
}

func TestNativeConfigurationRefusesUnsafeExistingFilesWithoutProbingOrWriting(t *testing.T) {
	for _, kind := range []string{"malformed", "unknown saved field", "public secret", "symlink settings", "hardlink secret", "unsafe ancestor"} {
		t.Run(kind, func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			switch kind {
			case "malformed":
				if err := os.WriteFile(p.Config, []byte("{"), 0600); err != nil {
					t.Fatal(err)
				}
			case "unknown saved field":
				data, err := os.ReadFile(p.Config)
				if err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(p.Config, append(bytes.TrimSuffix(bytes.TrimSpace(data), []byte("}")), []byte(`,"future-setting":true}`)...), 0600); err != nil {
					t.Fatal(err)
				}
			case "public secret":
				if err := os.Chmod(p.Secrets, 0644); err != nil {
					t.Fatal(err)
				}
			case "symlink settings":
				target := p.Config + ".original"
				if err := os.Rename(p.Config, target); err != nil {
					t.Fatal(err)
				}
				if err := os.Symlink(target, p.Config); err != nil {
					t.Fatal(err)
				}
			case "hardlink secret":
				if err := os.Link(p.Secrets, p.Secrets+".alias"); err != nil {
					t.Fatal(err)
				}
			case "unsafe ancestor":
				if err := os.Chmod(filepath.Dir(filepath.Dir(p.Config)), 0777); err != nil {
					t.Fatal(err)
				}
			}
			before := configurationPair(t, p)
			view := readConfiguration(context.Background(), p, configurationProbe(configurationStopped()), configurationLocal("absent"))
			if view.OK || view.Configured || view.KeyConfigured || view.CanConfigure || view.CanClose {
				t.Fatal("unsafe saved configuration was exposed as writable", view)
			}
			if _, err := configureFields(context.Background(), p, strings.NewReader(`{"bitrate":6000}`), configurationProbe(configurationStopped())); err == nil || !reflect.DeepEqual(before, configurationPair(t, p)) {
				t.Fatal("unsafe file was changed")
			}
		})
	}
}
