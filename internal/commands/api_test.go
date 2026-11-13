package commands

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/szmyty/obsgod/internal/config"
	api "github.com/szmyty/obsgod/pkg/api/v1"
)

func executePublic(t *testing.T, args ...string) (string, error) {
	t.Helper()
	cfg := config.Config{Host: "127.0.0.1", Port: 1, Password: "private-secret"}
	root := NewRoot(&cfg, nil, "test")
	var out, diagnostics bytes.Buffer
	root.SetOut(&out)
	root.SetErr(&diagnostics)
	root.SetArgs(args)
	e := root.Execute()
	if strings.Contains(out.String()+diagnostics.String(), "private-secret") {
		t.Fatal("private credentials escaped")
	}
	return out.String(), e
}
func TestPublicOfflineDiscoveryIgnoresBrokenConnectionConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad.json")
	if e := os.WriteFile(path, []byte("invalid"), 0600); e != nil {
		t.Fatal(e)
	}
	for _, args := range [][]string{{"--config", path, "api", "capabilities"}, {"--config", path, "creator", "extensions"}} {
		out, e := executePublic(t, args...)
		if e != nil || !json.Valid([]byte(out)) {
			t.Fatalf("offline discovery: %s %v", out, e)
		}
	}
}
func TestPublicUnapprovedOutputReturnsStableJSONBeforeConnect(t *testing.T) {
	for _, args := range [][]string{{"api", "stream", "start"}, {"api", "recording", "start"}, {"api", "replay", "save"}, {"api", "scene", "select", "Live"}} {
		out, e := executePublic(t, args...)
		if e == nil {
			t.Fatal("unapproved action succeeded")
		}
		var r api.Response
		if json.Unmarshal([]byte(out), &r) != nil || r.OK || r.SchemaVersion != 1 || r.Error == nil || r.Error.Code != api.ApprovalRequired {
			t.Fatalf("failure contract: %s %v", out, e)
		}
	}
}
func TestCreatorPlanDoesNotResolveSecretsOrConnect(t *testing.T) {
	path := filepath.Join(t.TempDir(), "creator.json")
	body := `{"schema_version":1,"provider":{"id":"kick","server":"rtmps://private-endpoint.invalid/app"},"workflow":{"obs_profile":"Gaming"},"stop_recording":false,"stop_replay_buffer":false}`
	if e := os.WriteFile(path, []byte(body), 0600); e != nil {
		t.Fatal(e)
	}
	t.Setenv("KICK_STREAM_KEY", "")
	out, e := executePublic(t, "creator", "plan", "--profile", path)
	if e != nil || !json.Valid([]byte(out)) || strings.Contains(out, "private-endpoint") {
		t.Fatalf("offline plan: %s %v", out, e)
	}
	out, e = executePublic(t, "creator", "start", "--profile", path)
	if e == nil || !strings.Contains(out, "approval_required") {
		t.Fatalf("creator approval: %s %v", out, e)
	}
	out, e = executePublic(t, "creator", "start", "--profile", path, "--approve", "--allow-streaming")
	if e == nil || !strings.Contains(out, "invalid_input") {
		t.Fatalf("missing secret resolved after network: %s %v", out, e)
	}
}
