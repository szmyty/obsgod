package commands

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/andreykaipov/goobs"
	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
)

func TestHelpDoesNotConnectToOBS(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("unexpected connection")
	})

	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "")
	cmd.SetArgs([]string{"--help"})
	cmd.SetOut(&bytes.Buffer{})
	cmd.SetErr(&bytes.Buffer{})

	if err := cmd.Execute(); err != nil {
		t.Fatalf("expected help to succeed without OBS, got %v", err)
	}
	if dialCount != 0 {
		t.Fatalf("expected help to avoid OBS connection, got %d dial attempts", dialCount)
	}
}

func isolatedCommandConfig(t *testing.T) config.Config {
	t.Helper()
	t.Setenv("XDG_CONFIG_HOME", t.TempDir())
	for _, name := range []string{"OBS_HOST", "OBS_PORT", "OBS_PASSWORD", "OBS_PASSWORD_FILE", "OBSGOD_HOST", "OBSGOD_PORT", "OBSGOD_PASSWORD", "OBSGOD_PASSWORD_FILE", "OBSGOD_CONFIG", "OBSGOD_CONNECTION_PROFILE"} {
		t.Setenv(name, "")
		if name == "OBS_PASSWORD" || name == "OBSGOD_PASSWORD" {
			if err := os.Unsetenv(name); err != nil {
				t.Fatal(err)
			}
		}
	}
	return config.Config{Host: "localhost", Port: 4455}
}

func TestOfflineCommandsIgnoreBrokenConnectionConfiguration(t *testing.T) {
	for _, args := range [][]string{{"--help"}, {"--version"}, {"version", "--json"}, {"completion", "bash"}, {"completion", "zsh"}, {"completion", "fish"}, {"__complete", "stream", ""}, {"__completeNoDesc", "stream", ""}, {"config", "path"}} {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			cfg := isolatedCommandConfig(t)
			t.Setenv("OBSGOD_CONFIG", filepath.Join(t.TempDir(), "not-created.json"))
			t.Setenv("OBS_PASSWORD", "private-credential-marker")
			var dialCount int
			service := obs.NewServiceWithDialer(&cfg, "test-build", func(string, ...goobs.Option) (*goobs.Client, error) {
				dialCount++
				return nil, errors.New("unexpected dial")
			})
			command := NewRoot(&cfg, service, "test-build")
			var out bytes.Buffer
			command.SetOut(&out)
			command.SetArgs(args)
			if err := command.Execute(); err != nil || dialCount != 0 || out.Len() == 0 {
				t.Fatalf("offline command should work: error=%v dials=%d output=%q", err, dialCount, out.String())
			}
			if strings.Contains(out.String(), "private-credential-marker") {
				t.Fatal("offline output/completions leaked password")
			}
		})
	}
}

func TestGenericCLIResolvesLayersBeforeLazyConnection(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(`{"version":1,"connection":{"host":"file.example","port":4456},"profiles":{"studio":{"host":"profile.example"}}}`), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("OBSGOD_HOST", "environment.example")
	var address string
	service := obs.NewServiceWithDialer(&cfg, "", func(actual string, _ ...goobs.Option) (*goobs.Client, error) {
		address = actual
		return nil, errors.New("modeled offline connection")
	})
	command := NewRoot(&cfg, service, "")
	command.SetArgs([]string{"--config", path, "--connection-profile", "studio", "--host", "flag.example", "stream", "start"})
	if err := command.Execute(); err == nil || address != "flag.example:4456" {
		t.Fatalf("resolved config did not reach lazy service: address=%q error=%v", address, err)
	}
}

func TestConfigShowRedactsAndNeverConnects(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	t.Setenv("OBSGOD_PASSWORD", "private-credential-marker")
	var count int
	service := obs.NewServiceWithDialer(&cfg, "", func(string, ...goobs.Option) (*goobs.Client, error) {
		count++
		return nil, errors.New("unexpected dial")
	})
	command := NewRoot(&cfg, service, "")
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{"config", "show", "--json"})
	if err := command.Execute(); err != nil || count != 0 {
		t.Fatalf("config show must be local: %v dials=%d", err, count)
	}
	var value config.Public
	if err := json.Unmarshal(output.Bytes(), &value); err != nil || value.SchemaVersion != 1 || !value.PasswordConfigured || value.PasswordSource != "environment" || value.OBSConnection != "not_checked" {
		t.Fatalf("invalid redacted configuration result: %s %v", output.String(), err)
	}
	if strings.Contains(output.String(), "private-credential-marker") {
		t.Fatal("config show leaked credential")
	}
}

func TestDeckCommandsRemainIndependentOfGenericConfiguration(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	t.Setenv("OBSGOD_CONFIG", filepath.Join(t.TempDir(), "not-created.json"))
	command := NewRoot(&cfg, nil, "")
	var called bool
	for _, child := range command.Commands() {
		if child.Name() == "deck" {
			child.AddCommand(&coral.Command{Use: "test-isolation", RunE: func(*coral.Command, []string) error {
				called = true
				return nil
			}})
		}
	}
	command.SetArgs([]string{"deck", "test-isolation"})
	if err := command.Execute(); err != nil || !called {
		t.Fatalf("generic configuration blocked managed recovery: called=%t error=%v", called, err)
	}
}

type statusTestService struct {
	obs.Service
	status obs.OutputStatus
	err    error
	calls  int
}

func (s *statusTestService) GetStreamStatus() (obs.OutputStatus, error) {
	s.calls++
	return s.status, s.err
}

func (s *statusTestService) GetRecordingStatus() (obs.OutputStatus, error) {
	s.calls++
	return s.status, s.err
}

func TestHighValueStatusJSONAndQuiet(t *testing.T) {
	for _, kind := range []string{"stream", "recording"} {
		for _, mode := range []string{"--json", "--quiet"} {
			t.Run(kind+" "+mode, func(t *testing.T) {
				cfg := isolatedCommandConfig(t)
				service := &statusTestService{status: obs.OutputStatus{Active: true, Paused: kind == "recording", Timecode: "00:01:02.000"}}
				command := NewRoot(&cfg, service, "")
				var output bytes.Buffer
				command.SetOut(&output)
				command.SetArgs([]string{kind, "status", mode})
				if err := command.Execute(); err != nil || service.calls != 1 {
					t.Fatalf("status query failed: %v calls=%d", err, service.calls)
				}
				if mode == "--quiet" {
					if output.Len() != 0 {
						t.Fatal("quiet status printed output")
					}
					return
				}
				var payload struct {
					SchemaVersion int    `json:"schema_version"`
					Kind          string `json:"kind"`
					Active        bool   `json:"active"`
					Timecode      string `json:"timecode"`
				}
				if err := json.Unmarshal(output.Bytes(), &payload); err != nil || payload.SchemaVersion != 1 || payload.Kind != kind || !payload.Active || payload.Timecode != service.status.Timecode {
					t.Fatalf("unexpected JSON status: %q %v", output.String(), err)
				}
			})
		}
	}
}

func TestUnknownStatusNeverProducesSuccessfulJSON(t *testing.T) {
	for _, kind := range []string{"stream", "recording"} {
		t.Run(kind, func(t *testing.T) {
			cfg := isolatedCommandConfig(t)
			service := &statusTestService{err: errors.New("OBS unavailable")}
			command := NewRoot(&cfg, service, "")
			var output bytes.Buffer
			command.SetOut(&output)
			command.SetArgs([]string{kind, "status", "--json"})
			if err := command.Execute(); err == nil || output.Len() != 0 {
				t.Fatalf("unavailable status must fail with no successful JSON: %q %v", output.String(), err)
			}
		})
	}
}

func TestVersionCommandBuildMetadataJSON(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	command := NewRoot(&cfg, nil, "1.2.3 (revision)")
	var output bytes.Buffer
	command.SetOut(&output)
	command.SetArgs([]string{"version", "--json"})
	if err := command.Execute(); err != nil || !strings.Contains(output.String(), `"version":"1.2.3 (revision)"`) {
		t.Fatalf("version metadata missing: %q %v", output.String(), err)
	}
}

func TestVersionDoesNotConnectToOBS(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "1.2.3", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("unexpected connection")
	})

	stdout := &bytes.Buffer{}
	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "1.2.3")
	cmd.SetArgs([]string{"--version"})
	cmd.SetOut(stdout)
	cmd.SetErr(&bytes.Buffer{})

	if err := cmd.Execute(); err != nil {
		t.Fatalf("expected version to succeed without OBS, got %v", err)
	}
	if dialCount != 0 {
		t.Fatalf("expected version to avoid OBS connection, got %d dial attempts", dialCount)
	}
	if !strings.Contains(stdout.String(), "1.2.3") {
		t.Fatalf("expected version output to include build version, got %q", stdout.String())
	}
}

func TestHelpNeverPrintsConfiguredPassword(t *testing.T) {
	cfg := config.Config{Host: "127.0.0.1", Port: 4455, Password: "secret-that-must-stay-private"}
	service := obs.NewService(&cfg, "")
	cmd := NewRoot(&cfg, service, "")
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetArgs([]string{"--help"})
	if err := cmd.Execute(); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out.String(), cfg.Password) {
		t.Fatal("help leaked configured password")
	}
}

func TestOperationalCommandConnectsLazily(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("boom")
	})

	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "")
	cmd.SetArgs([]string{"stream", "start"})
	cmd.SetOut(&bytes.Buffer{})
	cmd.SetErr(&bytes.Buffer{})

	err := cmd.Execute()
	if err == nil {
		t.Fatal("expected stream start to attempt OBS connection")
	}
	if dialCount != 1 {
		t.Fatalf("expected one OBS connection attempt, got %d", dialCount)
	}
	if !strings.Contains(err.Error(), "connect to OBS at 127.0.0.1:1") {
		t.Fatalf("expected contextual connection error, got %v", err)
	}
}
