//go:build linux

package commands

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/internal/deck"
)

func executeNativeConfigurationCLI(t *testing.T, ctx context.Context, action, input string) ([]byte, error) {
	t.Helper()
	command := newDeckCommand()
	command.SilenceUsage, command.SilenceErrors = true, true
	var output, diagnostic bytes.Buffer
	command.SetOut(&output)
	command.SetErr(&diagnostic)
	command.SetIn(strings.NewReader(input))
	command.SetArgs([]string{action})
	err := command.ExecuteContext(ctx)
	if strings.Contains(output.String()+diagnostic.String(), "private-native-cli-fixture") {
		t.Fatal("native command exposed the submitted stream key")
	}
	return output.Bytes(), err
}

func TestNativeConfigurationCLIPrivateFirstRunAndPartialMerge(t *testing.T) {
	isolatedDeckAdvancedConfiguration(t)
	t.Setenv("OBSGOD_DECKY_STORAGE_MAP", "")
	data, err := executeNativeConfigurationCLI(t, context.Background(), "configuration", "")
	var view deck.ConfigurationView
	if err != nil || json.Unmarshal(data, &view) != nil || !view.OK || !view.CanConfigure || view.Configured || view.KeyConfigured || view.SchemaVersion != 1 {
		t.Fatal("native first-run view was not editable defaults", string(data), err)
	}
	p, err := deck.UserPaths()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(p.Secrets); !os.IsNotExist(err) {
		t.Fatal("view created a credential store", err)
	}
	data, err = executeNativeConfigurationCLI(t, context.Background(), "configure-fields", `{"server":"rtmps://example.invalid/app","stream_key":"private-native-cli-fixture","capture_mode":"game","microphone":true}`)
	var result deck.Result
	if err != nil || json.Unmarshal(data, &result) != nil || !result.OK || !result.Configured || result.Stream.Active || !result.OutputKnown {
		t.Fatal("native save failed or claimed output", string(data), err)
	}
	_, before, err := deck.Load(p)
	if err != nil {
		t.Fatal(err)
	}
	data, err = executeNativeConfigurationCLI(t, context.Background(), "configure-fields", `{"bitrate":6000}`)
	if err != nil || json.Unmarshal(data, &result) != nil || !result.OK {
		t.Fatal("sparse native merge failed", string(data), err)
	}
	s, secret, err := deck.Load(p)
	if err != nil || s.Bitrate != 6000 || s.CaptureMode != "game" || !s.Microphone || secret.StreamKey != before.StreamKey || secret.OBSPassword != before.OBSPassword {
		t.Fatal("CLI merge reset settings or control authentication", err)
	}
	data, err = executeNativeConfigurationCLI(t, context.Background(), "configuration", "")
	if err != nil || json.Unmarshal(data, &view) != nil || !view.Configured || !view.KeyConfigured || !view.CanConfigure || view.Settings.Bitrate != 6000 || bytes.Contains(data, []byte(secret.OBSPassword)) {
		t.Fatal("native saved view was unavailable or secret-bearing", err)
	}
}

func TestNativeConfigurationCLICancelledSharedLeaseDoesNotSave(t *testing.T) {
	isolatedDeckAdvancedConfiguration(t)
	t.Setenv("OBSGOD_DECKY_STORAGE_MAP", "")
	p, err := deck.UserPaths()
	if err != nil {
		t.Fatal(err)
	}
	unlock, err := deck.Lock(context.Background(), p)
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	started := time.Now()
	data, err := executeNativeConfigurationCLI(t, ctx, "configure-fields", `{"server":"rtmps://example.invalid/app","stream_key":"private-native-cli-fixture"}`)
	var result deck.Result
	if err == nil || json.Unmarshal(data, &result) != nil || result.OK || time.Since(started) > 2*time.Second {
		t.Fatal("cancelled waiting action did not fail promptly", string(data), err)
	}
	if _, err := os.Stat(p.Secrets); !os.IsNotExist(err) {
		t.Fatal("action escaped the shared controller lease", err)
	}
}
