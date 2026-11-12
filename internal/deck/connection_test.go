package deck

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func closedControl(Paths) (string, bool) { return "absent", false }

func configuredControl(t *testing.T) (Paths, Secrets) {
	t.Helper()
	p := testPaths(t)
	s, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	_, secret, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if err := Prepare(p, s, secret); err != nil {
		t.Fatal(err)
	}
	return p, secret
}

func TestControlPasswordChangesOnlyItsManagedPrivatePair(t *testing.T) {
	for _, body := range []string{`{"confirm":true,"password":"owner-entered-fixture"}`, `{"confirm":true,"generate":true}`} {
		t.Run(body, func(t *testing.T) {
			p, oldSecret := configuredControl(t)
			settingsBefore, _ := os.ReadFile(p.Config)
			unrelated := filepath.Join(t.TempDir(), "ordinary-obs-config.json")
			if err := os.WriteFile(unrelated, []byte("ordinary OBS untouched"), 0600); err != nil {
				t.Fatal(err)
			}
			result, err := changeControlPassword(p, strings.NewReader(body), closedControl, writeJSON)
			if err != nil || !result.OK || !result.AwaitingVerification || result.Connected {
				t.Fatal("incorrect rotation or reconnection claim", result, err)
			}
			_, secret, err := Load(p)
			if err != nil || secret.OBSPassword == oldSecret.OBSPassword || secret.StreamKey != oldSecret.StreamKey || secret.SettingsHash != oldSecret.SettingsHash {
				t.Fatal("rotation damaged stream-key/settings binding", err)
			}
			var ws map[string]any
			wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
			if err := readPrivateJSON(wsPath, &ws); err != nil || ws["server_password"] != secret.OBSPassword || ws["auth_required"] != true || ws["server_port"] != float64(4457) {
				t.Fatal("private OBS and CLI password did not synchronize", err)
			}
			settingsAfter, _ := os.ReadFile(p.Config)
			if !bytes.Equal(settingsBefore, settingsAfter) {
				t.Fatal("rotation changed stream settings")
			}
			ordinary, _ := os.ReadFile(unrelated)
			if string(ordinary) != "ordinary OBS untouched" {
				t.Fatal("ordinary OBS changed")
			}
			encoded, _ := json.Marshal(result)
			for _, value := range []string{secret.StreamKey, oldSecret.OBSPassword, secret.OBSPassword} {
				if bytes.Contains(encoded, []byte(value)) {
					t.Fatal("rotation response disclosed credentials")
				}
			}
		})
	}
}

func TestControlPasswordRefusesUnknownRunningAndRacingProcesses(t *testing.T) {
	for _, state := range []string{"running", "unknown", "listener", "raced"} {
		t.Run(state, func(t *testing.T) {
			p, _ := configuredControl(t)
			wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
			beforeSecret, _ := os.ReadFile(p.Secrets)
			beforeWS, _ := os.ReadFile(wsPath)
			calls := 0
			probe := func(Paths) (string, bool) {
				calls++
				if state == "listener" {
					return "absent", true
				}
				if state == "raced" {
					if calls == 1 {
						return "absent", false
					}
					return "running", false
				}
				return state, false
			}
			if _, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), probe, writeJSON); err == nil {
				t.Fatal("changed credentials while output might exist")
			}
			afterSecret, _ := os.ReadFile(p.Secrets)
			afterWS, _ := os.ReadFile(wsPath)
			if !bytes.Equal(beforeSecret, afterSecret) || !bytes.Equal(beforeWS, afterWS) {
				t.Fatal("refused rotation changed a private file")
			}
		})
	}
}

func TestControlPasswordWriteFailureRestoresPreviousPair(t *testing.T) {
	p, _ := configuredControl(t)
	wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
	beforeSecret, _ := os.ReadFile(p.Secrets)
	beforeWS, _ := os.ReadFile(wsPath)
	save := func(path string, value any) error {
		if path == p.Secrets {
			return errors.New("injected private write failure")
		}
		return writeJSON(path, value)
	}
	result, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), closedControl, save)
	if err == nil || result.OK || strings.Contains(err.Error(), "injected") {
		t.Fatal("write failure was not safely reported")
	}
	afterSecret, _ := os.ReadFile(p.Secrets)
	afterWS, _ := os.ReadFile(wsPath)
	if !bytes.Equal(beforeSecret, afterSecret) || !bytes.Equal(beforeWS, afterWS) {
		t.Fatal("failed rotation did not restore the original private pair")
	}
}

func TestControlPasswordBeforeFirstLaunchAndFailedInitialWrite(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(map[bool]string{false: "first-password-change", true: "first-change-fails"}[fail], func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			before, _ := os.ReadFile(p.Secrets)
			save := func(path string, value any) error {
				if fail && path == p.Secrets {
					return errors.New("injected first-change failure")
				}
				return writeJSON(path, value)
			}
			result, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), closedControl, save)
			wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
			if fail {
				after, _ := os.ReadFile(p.Secrets)
				if err == nil || result.OK || !bytes.Equal(before, after) {
					t.Fatal("failed first change damaged saved credentials")
				}
				if _, err := os.Lstat(wsPath); !os.IsNotExist(err) {
					t.Fatal("failed first change left partially configured WebSocket settings")
				}
			} else {
				var ws map[string]any
				_, secret, loadErr := Load(p)
				if err != nil || !result.OK || loadErr != nil || readPrivateJSON(wsPath, &ws) != nil || ws["server_password"] != secret.OBSPassword {
					t.Fatal("password setup before first launch failed", err)
				}
			}
		})
	}
}

func TestControlPasswordRefusesParentSymlinkEscape(t *testing.T) {
	p, _ := configuredControl(t)
	parent := filepath.Join(p.OBSConfig, "obs-studio/plugin_config")
	outside := filepath.Join(t.TempDir(), "ordinary-plugin-config")
	if err := os.Rename(parent, outside); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, parent); err != nil {
		t.Skip("symlinks unavailable")
	}
	target := filepath.Join(outside, "obs-websocket/config.json")
	before, _ := os.ReadFile(target)
	beforeSecret, _ := os.ReadFile(p.Secrets)
	if _, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), closedControl, writeJSON); err == nil {
		t.Fatal("followed a parent link outside managed configuration")
	}
	after, _ := os.ReadFile(target)
	afterSecret, _ := os.ReadFile(p.Secrets)
	if !bytes.Equal(before, after) || !bytes.Equal(beforeSecret, afterSecret) {
		t.Fatal("unsafe parent path changed files")
	}
}

func TestControlPasswordInputAndPrivatePathValidation(t *testing.T) {
	for _, body := range []string{`{}`, `null`, `{"confirm":true,"password":"short"}`, `{"confirm":true,"generate":true,"password":"two-modes-invalid"}`, `{"confirm":true,"generate":true,"unrecognized":"value"}`, `{"confirm":true,"password":"invalid\ncontrol-password"}`, `{"confirm":true,"generate":true}{}`} {
		if _, err := changeControlPassword(testPaths(t), strings.NewReader(body), closedControl, writeJSON); err == nil {
			t.Fatal("invalid credential request accepted")
		}
	}
	p, _ := configuredControl(t)
	wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
	outside := filepath.Join(t.TempDir(), "ordinary-config")
	if err := os.WriteFile(outside, []byte("keep"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(wsPath); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, wsPath); err != nil {
		t.Skip("symlinks unavailable")
	}
	if _, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), closedControl, writeJSON); err == nil {
		t.Fatal("followed managed WebSocket symlink")
	}
	data, _ := os.ReadFile(outside)
	if string(data) != "keep" {
		t.Fatal("changed unrelated symlink target")
	}
}
