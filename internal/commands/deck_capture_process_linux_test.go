//go:build linux && deck_process

package commands

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"os/signal"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/internal/deck"
)

// Run this tagged regression serially after the default package matrix: its
// real CLI observes fixed port 4457, also used by internal/deck OBS fixtures.
// Re-exec exercises contexts, signals and cross-process flock without OBS.
func TestCaptureModeCommandProcess(t *testing.T) {
	if os.Getenv("OBSGOD_TEST_CAPTURE_COMMAND") != "1" {
		return
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	command := newDeckCommand()
	command.SilenceUsage, command.SilenceErrors = true, true
	command.SetOut(os.Stdout)
	command.SetErr(os.Stderr)
	command.SetIn(os.Stdin)
	command.SetArgs([]string{os.Getenv("OBSGOD_TEST_CAPTURE_ACTION")})
	if command.ExecuteContext(ctx) != nil {
		os.Exit(1)
	}
	os.Exit(0)
}

func captureCommandProcess(t *testing.T, action string) (*exec.Cmd, *bytes.Buffer) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	t.Cleanup(cancel)
	command := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestCaptureModeCommandProcess$")
	command.Env = append(os.Environ(), "OBSGOD_TEST_CAPTURE_COMMAND=1", "OBSGOD_TEST_CAPTURE_ACTION="+action)
	command.Stdin = strings.NewReader(`{"capture_mode":"game"}`)
	output := new(bytes.Buffer)
	command.Stdout, command.Stderr = output, output
	return command, output
}

func captureCommandPair(t *testing.T, p deck.Paths) [2][]byte {
	t.Helper()
	var pair [2][]byte
	for i, path := range []string{p.Config, p.Secrets} {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		pair[i] = data
	}
	return pair
}

func TestCaptureModeCommandProcessDeadlineAndSignalCannotLeaveALateWrite(t *testing.T) {
	for _, interrupt := range []bool{false, true} {
		name := "action deadline"
		if interrupt {
			name = "caller interrupt"
		}
		t.Run(name, func(t *testing.T) {
			isolatedDeckAdvancedConfiguration(t)
			t.Setenv("OBSGOD_DECKY_STORAGE_MAP", "")
			p, err := deck.UserPaths()
			if err != nil {
				t.Fatal(err)
			}
			if _, err := deck.Configure(p, strings.NewReader(`{"server":"rtmps://example.invalid/app","stream_key":"private-capture-process-fixture"}`)); err != nil {
				t.Fatal(err)
			}
			before := captureCommandPair(t, p)
			unlock, err := deck.Lock(context.Background(), p)
			if err != nil {
				t.Fatal(err)
			}
			t.Cleanup(func() {
				if unlock != nil {
					unlock()
				}
			})
			command, output := captureCommandProcess(t, "set-capture-mode")
			started := time.Now()
			if err := command.Start(); err != nil {
				t.Fatal(err)
			}
			t.Cleanup(func() {
				if command.ProcessState == nil {
					_ = command.Process.Kill()
					_ = command.Wait()
				}
			})
			if interrupt {
				// The request event is written before waiting for the shared lease.
				deadline := time.Now().Add(2 * time.Second)
				for len(deck.ReadDiagnostics(p)) == 0 && time.Now().Before(deadline) {
					time.Sleep(10 * time.Millisecond)
				}
				if len(deck.ReadDiagnostics(p)) == 0 {
					t.Fatal("child did not reach its control request")
				}
				if err := command.Process.Signal(os.Interrupt); err != nil {
					t.Fatal(err)
				}
			}
			waitErr := command.Wait()
			var result deck.Result
			if waitErr == nil || json.Unmarshal(output.Bytes(), &result) != nil || result.OK || !result.OutputKnown || time.Since(started) > 5500*time.Millisecond {
				t.Fatal("waiting CLI did not return a bounded truthful failure", output.String(), waitErr)
			}
			// Keep the lease held until after the child has exited, then release it.
			// A stale request must never resume and write when that lease is freed.
			unlock()
			unlock = nil
			if !reflect.DeepEqual(before, captureCommandPair(t, p)) {
				t.Fatal("cancelled or expired child changed the settings/credential pair")
			}
			for _, action := range []string{"set-capture-mode", "stop"} {
				fresh, freshOutput := captureCommandProcess(t, action)
				if err := fresh.Run(); err != nil || json.Unmarshal(freshOutput.Bytes(), &result) != nil || !result.OK || result.Stream.Active {
					t.Fatal("fresh explicit edit or Stop remained blocked after cancellation", action, freshOutput.String(), err)
				}
			}
			settings, secret, err := deck.Load(p)
			if err != nil || settings.CaptureMode != "game" || secret.StreamKey != "private-capture-process-fixture" || bytes.Contains(output.Bytes(), []byte(secret.StreamKey)) || bytes.Contains(output.Bytes(), []byte(secret.OBSPassword)) {
				t.Fatal("fresh capture edit lost its binding or exposed credentials", err)
			}
		})
	}
}
