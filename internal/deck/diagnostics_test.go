//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func TestDiagnosticsAreBoundedPrivateAndExcludeUntrustedErrors(t *testing.T) {
	p := testPaths(t)
	for i := 0; i < diagnosticLimit+5; i++ {
		logEvent(p, "obs.waiting")
	}
	RecordOutcome(p, errors.New("rtmps://secret.example.invalid/stream-key-never-log"), false)
	RecordOutcome(p, &automation.RequestError{Operation: "secret-never-log", Code: 601}, false)
	entries := ReadDiagnostics(p)
	if len(entries) != diagnosticLimit || !strings.Contains(entries[len(entries)-2].Message, "601") {
		t.Fatalf("bounded log or numeric request error missing: %+v", entries)
	}
	path := filepath.Join(diagnosticPaths(p).State, "events.json")
	data, err := os.ReadFile(path)
	if err != nil || strings.Contains(string(data), "secret") {
		t.Fatal("private input reached the event store", err)
	}
	info, err := os.Stat(path)
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("event store is not private")
	}
	if err := ClearDiagnostics(context.Background(), p); err != nil || len(ReadDiagnostics(p)) != 0 {
		t.Fatal("clear did not persist", err)
	}
}

func TestDiagnosticsCanBeReadAndClearedDuringAnOperation(t *testing.T) {
	p := testPaths(t)
	unlock, err := Lock(context.Background(), p)
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	logEvent(p, "obs.waiting")
	if len(ReadDiagnostics(p)) != 1 {
		t.Fatal("progress was blocked by the active operation")
	}
	if err := ClearDiagnostics(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	logEvent(p, "obs.ready")
	if len(ReadDiagnostics(p)) != 1 {
		t.Fatal("progress did not resume after clearing")
	}
}

func TestDiagnosticsDoNotFollowSymlinksOrDisplayUnknownRecords(t *testing.T) {
	p := testPaths(t)
	logEvent(p, "obs.waiting")
	path := filepath.Join(diagnosticPaths(p).State, "events.json")
	data, _ := json.Marshal([]map[string]any{{"time": time.Now(), "code": "secret-never-display", "message": "secret-never-display"}})
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	if len(ReadDiagnostics(p)) != 0 {
		t.Fatal("displayed an unknown log event")
	}
	outside := filepath.Join(t.TempDir(), "outside")
	_ = os.WriteFile(outside, []byte("untouched"), 0600)
	_ = os.Remove(path)
	if err := os.Symlink(outside, path); err != nil {
		t.Fatal(err)
	}
	logEvent(p, "obs.ready")
	if err := ClearDiagnostics(context.Background(), p); err == nil {
		t.Fatal("clear accepted a symlink")
	}
	data, _ = os.ReadFile(outside)
	if string(data) != "untouched" || len(ReadDiagnostics(p)) != 0 {
		t.Fatal("followed a diagnostic symlink")
	}
}

func TestEarlyOBSExitIsReportedBeforeStartupTimeout(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	s, secret, _ := Load(p)
	bin := t.TempDir()
	if err := os.WriteFile(filepath.Join(bin, "flatpak"), []byte("#!/bin/sh\nexit 42\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin)
	t.Setenv("DISPLAY", ":99")
	ctx, cancel := context.WithTimeout(context.Background(), 4*time.Second)
	defer cancel()
	_, err := ready(ctx, p, s, secret)
	if err == nil || !strings.Contains(err.Error(), "OBS exited before") {
		t.Fatal("early launch failure was not identified", err)
	}
	entries, _ := json.Marshal(ReadDiagnostics(p))
	if !strings.Contains(string(entries), "Exit code 42") {
		t.Fatal("early exit code not retained", string(entries))
	}
}
