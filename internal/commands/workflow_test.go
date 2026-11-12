package commands

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/muesli/coral"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
	"github.com/szmyty/obsgod/pkg/automation"
)

func workflowFile(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	body := `{"version":1,"connection":{"password_file":"intentionally-unavailable"},"default_workflow":"studio","workflow_profiles":{"studio":{"starting_scene":"Ready","recording_enabled":true}}}`
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestWorkflowPlanAndDryRunDoNotResolveSecretsOrConnect(t *testing.T) {
	for _, args := range [][]string{{"workflow", "list"}, {"workflow", "plan"}, {"workflow", "apply", "--dry-run"}} {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			cfg := isolatedCommandConfig(t)
			path := workflowFile(t)
			command := NewRoot(&cfg, nil, "")
			var out bytes.Buffer
			command.SetOut(&out)
			command.SetArgs(append([]string{"--config", path}, args...))
			if err := command.Execute(); err != nil {
				t.Fatalf("offline workflow failed: %v", err)
			}
			if !json.Valid(out.Bytes()) || strings.Contains(out.String(), "intentionally-unavailable") {
				t.Fatalf("unsafe/non-JSON plan: %s", out.String())
			}
		})
	}
}

type workflowCommandBackend struct {
	state  automation.WorkflowSnapshot
	closed bool
}

func (f *workflowCommandBackend) WorkflowSnapshot(context.Context) (automation.WorkflowSnapshot, error) {
	return f.state, nil
}
func (f *workflowCommandBackend) SetWorkflowProfile(context.Context, string) error {
	return errors.New("unexpected change")
}
func (f *workflowCommandBackend) SetWorkflowCollection(context.Context, string) error {
	return errors.New("unexpected change")
}
func (f *workflowCommandBackend) SetScene(context.Context, string) error {
	return errors.New("unexpected change")
}
func (f *workflowCommandBackend) StartRecording(context.Context) error {
	f.state.RecordingActive = true
	return nil
}
func (f *workflowCommandBackend) StartWorkflowReplayBuffer(context.Context) error {
	return errors.New("unexpected replay start")
}
func (f *workflowCommandBackend) Close() error { f.closed = true; return nil }

func TestWorkflowCLIRequiresApprovalsBeforeConnectorAndClosesOwnedConnection(t *testing.T) {
	for _, args := range [][]string{{"apply"}, {"apply", "--approve"}, {"apply", "--approve", "--allow-recording"}} {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			cfg := isolatedCommandConfig(t)
			path := workflowFile(t)
			calls := 0
			backend := &workflowCommandBackend{state: automation.WorkflowSnapshot{Profile: "Original", Collection: "Original", Scene: "Ready", Scenes: []string{"Ready"}}}
			command := newWorkflowCommand(&cfg, &path, func(context.Context, config.Config, automation.WorkflowPlan) (automation.WorkflowBackend, error) {
				calls++
				return backend, nil
			})
			var out bytes.Buffer
			command.SetOut(&out)
			command.SetArgs(args)
			err := command.Execute()
			if len(args) < 3 {
				if err == nil || calls != 0 {
					t.Fatal("missing approval still connected")
				}
				return
			}
			if err != nil || calls != 1 || !backend.closed || !backend.state.RecordingActive || !json.Valid(out.Bytes()) {
				t.Fatalf("approved workflow failed: %v %s", err, out.String())
			}
		})
	}
}

func TestVerboseMetadataIsOnStderrAndDoesNotContaminateJSON(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	cfg.Password = "private-credential-marker"
	command := NewRoot(&cfg, nil, "test-build")
	var out, diagnostics bytes.Buffer
	command.SetOut(&out)
	command.SetErr(&diagnostics)
	command.SetArgs([]string{"--verbose", "--no-color", "version", "--json"})
	if err := command.Execute(); err != nil || !json.Valid(out.Bytes()) {
		t.Fatalf("verbose JSON failure: %v %q", err, out.String())
	}
	if !strings.Contains(diagnostics.String(), "stage=independent_configuration") || strings.Contains(diagnostics.String(), "private-credential-marker") || strings.Contains(diagnostics.String(), "\x1b") {
		t.Fatalf("unsafe verbose diagnostics: %q", diagnostics.String())
	}
}

func TestNoColorAndTerminalConventionsHaveObservableBehavior(t *testing.T) {
	t.Setenv("NO_COLOR", "")
	t.Setenv("TERM", "xterm-256color")
	if !strings.Contains(diagnosticPrefix(false, true), "\x1b[") {
		t.Fatal("verbose terminal color missing")
	}
	if strings.Contains(diagnosticPrefix(true, true), "\x1b[") || strings.Contains(diagnosticPrefix(false, false), "\x1b[") {
		t.Fatal("explicit/plain-output color suppression failed")
	}
	t.Setenv("NO_COLOR", "1")
	if strings.Contains(diagnosticPrefix(false, true), "\x1b[") {
		t.Fatal("NO_COLOR ignored")
	}
	t.Setenv("NO_COLOR", "")
	t.Setenv("TERM", "dumb")
	if strings.Contains(diagnosticPrefix(false, true), "\x1b[") {
		t.Fatal("TERM=dumb ignored")
	}
}

func TestReferenceIsOfflineDeterministicAndDoesNotExposeDefaultsFromEnvironment(t *testing.T) {
	var previous string
	for _, host := range []string{"first-private-host", "second-private-host"} {
		cfg := isolatedCommandConfig(t)
		cfg.Host = host
		cfg.Password = "private-credential-marker"
		t.Setenv("OBSGOD_CONFIG", filepath.Join(t.TempDir(), "not-created.json"))
		command := NewRoot(&cfg, nil, "")
		var out bytes.Buffer
		command.SetOut(&out)
		command.SetArgs([]string{"reference"})
		if err := command.Execute(); err != nil {
			t.Fatal(err)
		}
		text := out.String()
		if strings.Contains(text, host) || strings.Contains(text, cfg.Password) || !strings.Contains(text, "## obsgod workflow apply") || !strings.Contains(text, "## obsgod stream status") {
			t.Fatal("reference missing commands or exposing environment defaults")
		}
		if previous != "" && previous != text {
			t.Fatal("reference depends on caller environment")
		}
		previous = text
	}
}

type countdownTestService struct {
	obs.Service
	calls int
}

func (f *countdownTestService) SetLabelText(string, string) error { f.calls++; return nil }

func TestCountdownCancellationStopsBeforeAnyLaterLabelWrites(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	service := &countdownTestService{}
	cancel()
	start := time.Now()
	if err := countdown(ctx, service, "Label", time.Hour); !errors.Is(err, context.Canceled) || service.calls != 0 || time.Since(start) > time.Second {
		t.Fatalf("cancelled countdown kept running: calls=%d err=%v", service.calls, err)
	}
	for _, input := range []string{"-1s", "0s", "25h", "private-credential-marker"} {
		if _, err := parseCountdownDuration(input); err == nil || strings.Contains(err.Error(), "private-credential-marker") {
			t.Fatal("invalid countdown duration accepted or echoed")
		}
	}
}

func TestManagedDoctorAliasBypassesBrokenGenericConfiguration(t *testing.T) {
	cfg := isolatedCommandConfig(t)
	t.Setenv("OBSGOD_CONFIG", filepath.Join(t.TempDir(), "not-created.json"))
	command := NewRoot(&cfg, nil, "")
	called := false
	for _, child := range command.Commands() {
		if child.Name() == "doctor" {
			if !strings.Contains(child.Short, "Steam Deck") {
				t.Fatal("doctor help must distinguish managed diagnostics")
			}
			child.RunE = func(cmd *coral.Command, _ []string) error {
				called = true
				return json.NewEncoder(cmd.OutOrStdout()).Encode(map[string]bool{"ok": true})
			}
		}
	}
	var out bytes.Buffer
	command.SetOut(&out)
	command.SetArgs([]string{"doctor"})
	if err := command.Execute(); err != nil || !called || !json.Valid(out.Bytes()) {
		t.Fatalf("doctor alias blocked by generic config: %v called=%v", err, called)
	}
}
