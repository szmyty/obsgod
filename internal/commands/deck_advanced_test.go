package commands

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/andreykaipov/goobs"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/deck"
	"github.com/szmyty/obsgod/internal/obs"
)

func isolatedDeckAdvancedConfiguration(t *testing.T) {
	t.Helper()
	_ = isolatedCommandConfig(t)
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("XDG_STATE_HOME", filepath.Join(home, "state"))
	t.Setenv("XDG_VIDEOS_DIR", "")
	t.Setenv("OBSGOD_CONFIG", filepath.Join(home, "missing-generic-config.json"))
	for _, key := range []string{"PROFILE", "WIDTH", "HEIGHT", "BITRATE", "FPS", "ENCODER", "CAPTURE_MODE", "MICROPHONE"} {
		name := "OBSGOD_DECK_" + key
		t.Setenv(name, "")
		if key == "MICROPHONE" {
			if err := os.Unsetenv(name); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func executeDeckProfileCLI(t *testing.T, input string, flags ...string) (deck.StreamProfileResult, string, error) {
	t.Helper()
	cfg := config.Config{Host: "localhost", Port: 4455}
	var dials int
	service := obs.NewServiceWithDialer(&cfg, "", func(string, ...goobs.Option) (*goobs.Client, error) {
		dials++
		return nil, errors.New("unexpected generic OBS connection")
	})
	command := NewRoot(&cfg, service, "")
	var output, diagnostic bytes.Buffer
	command.SetIn(strings.NewReader(input))
	command.SetOut(&output)
	command.SetErr(&diagnostic)
	command.SetArgs(append([]string{"deck", "stream-profiles"}, flags...))
	err := command.Execute()
	if dials != 0 {
		t.Fatal("managed profile command used generic OBS connection", dials)
	}
	var result deck.StreamProfileResult
	if err == nil && json.Unmarshal(output.Bytes(), &result) != nil {
		t.Fatal("successful profile CLI did not return one JSON object", output.String())
	}
	if err == nil {
		decoder := json.NewDecoder(bytes.NewReader(output.Bytes()))
		var first, extra any
		if decodeErr := decoder.Decode(&first); decodeErr != nil {
			t.Fatal(decodeErr)
		}
		if decodeErr := decoder.Decode(&extra); decodeErr != io.EOF {
			t.Fatal("profile command emitted trailing output", decodeErr)
		}
	}
	return result, output.String() + diagnostic.String(), err
}

func TestDeckProfileCLIFlagsOverrideJSONAndMalformedEnvironment(t *testing.T) {
	isolatedDeckAdvancedConfiguration(t)
	t.Setenv("OBSGOD_DECK_FPS", "malformed-lower-layer")
	t.Setenv("OBSGOD_DECK_MICROPHONE", "true")
	t.Setenv("OBSGOD_DECK_ENCODER", "x264")
	result, output, err := executeDeckProfileCLI(t, `{"action":"preview","preset":"balanced-720p30","overrides":{"bitrate":6000,"microphone":true}}`, "--width=960", "--height=540", "--bitrate=3500", "--fps=60", "--encoder=vaapi", "--capture-mode=game", "--microphone=false")
	if err != nil || !result.OK || result.Profile == nil {
		t.Fatal(result, output, err)
	}
	profile := result.Profile
	if profile.Width != 960 || profile.Height != 540 || profile.Bitrate != 3500 || profile.FPS != 60 || profile.Encoder != "vaapi" || profile.CaptureMode != "game" || profile.Microphone {
		t.Fatal("flags did not override request/environment", profile)
	}
	if strings.Contains(output, "malformed-lower-layer") {
		t.Fatal("ignored invalid lower layer was disclosed")
	}
	if _, err := os.Stat(filepath.Join(os.Getenv("XDG_CONFIG_HOME"), "obsgod", "deck.json")); !os.IsNotExist(err) {
		t.Fatal("preview modified managed settings")
	}
}

func TestDeckProfileCLIUnchangedBooleanFlagDoesNotOverrideEnvironment(t *testing.T) {
	isolatedDeckAdvancedConfiguration(t)
	t.Setenv("OBSGOD_DECK_MICROPHONE", "true")
	result, output, err := executeDeckProfileCLI(t, `{"action":"preview","preset":"balanced-720p30"}`)
	if err != nil || !result.OK || result.Profile == nil || !result.Profile.Microphone {
		t.Fatal("implicit false flag default overrode environment", result, output, err)
	}
	disabled, output, err := executeDeckProfileCLI(t, `{"action":"preview","preset":"balanced-720p30"}`, "--microphone=false")
	if err != nil || !disabled.OK || disabled.Profile == nil || disabled.Profile.Microphone {
		t.Fatal("explicit false flag failed to override environment", disabled, output, err)
	}
}

func TestDeckProfileCLIRejectsInvalidFlagsAndUnknownOrMultipleJSON(t *testing.T) {
	cases := []struct {
		name, input string
		flags       []string
	}{
		{"unknown flag", `{"action":"preview"}`, []string{"--not-a-profile-flag=1"}},
		{"invalid integer", `{"action":"preview"}`, []string{"--fps=not-an-int"}},
		{"invalid effective fps", `{"action":"preview"}`, []string{"--fps=120"}},
		{"invalid effective capture", `{"action":"preview"}`, []string{"--capture-mode=guess"}},
		{"unknown field with flag", `{"action":"preview","stream_key":"private-request-marker"}`, []string{"--fps=30"}},
		{"unknown field without flag", `{"action":"preview","stream_key":"private-request-marker"}`, nil},
		{"double JSON with flag", `{"action":"save","name":"must-not-save"}{}`, []string{"--fps=30"}},
		{"double JSON without flag", `{"action":"save","name":"must-not-save"}{}`, nil},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			isolatedDeckAdvancedConfiguration(t)
			result, output, err := executeDeckProfileCLI(t, test.input, test.flags...)
			if err == nil || result.OK {
				t.Fatal("invalid CLI request succeeded", result, output)
			}
			if strings.Contains(output, "private-request-marker") {
				t.Fatal("unknown JSON value was echoed", output)
			}
			if _, statErr := os.Stat(filepath.Join(os.Getenv("XDG_CONFIG_HOME"), "obsgod", "stream-profiles.json")); !os.IsNotExist(statErr) {
				t.Fatal("invalid request saved profile state")
			}
		})
	}
}

func TestDeckProfileCLIExportIsPortableAndDoesNotResolveCredentials(t *testing.T) {
	isolatedDeckAdvancedConfiguration(t)
	// Missing generic configuration and credentials must not block portable
	// profiles; no managed OBS credentials or setup are provisioned in this home.
	t.Setenv("OBSGOD_PASSWORD", "private-generic-password-marker")
	saved, output, err := executeDeckProfileCLI(t, `{"action":"save","name":"portable","preset":"small-540p30"}`)
	if err != nil || !saved.OK {
		t.Fatal(saved, output, err)
	}
	exported, output, err := executeDeckProfileCLI(t, `{"action":"export","name":"portable"}`)
	if err != nil || !exported.OK || exported.Document == nil || exported.Document.Version != 1 || exported.Document.Profile.Width != 960 {
		t.Fatal(exported, output, err)
	}
	for _, private := range []string{"private-generic-password-marker", "stream_key", "obs_password", "password_file", "server", os.Getenv("HOME")} {
		if strings.Contains(output, private) {
			t.Fatal("portable CLI export disclosed local/credential material", private)
		}
	}
	t.Setenv("OBSGOD_DECK_FPS", "invalid-export-must-ignore")
	exported, output, err = executeDeckProfileCLI(t, `{"action":"export","name":"portable"}`)
	if err != nil || exported.Document == nil || exported.Document.Profile.FPS != 30 {
		t.Fatal("environment unexpectedly changed exported profile", exported, output, err)
	}
}
