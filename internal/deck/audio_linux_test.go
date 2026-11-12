//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func audioFixtureQuery(overrides map[string]string) func(context.Context, ...string) ([]byte, error) {
	fixtures := map[string]string{
		"info":             `{"default_sink_name":"speakers","default_source_name":"microphone","server_string":"private-server-do-not-export"}`,
		"list sinks":       `[{"index":1,"name":"speakers","monitor_source":"speakers.monitor","mute":false,"volume":{"front-left":{"value":65536}}},{"index":2,"name":"headphones","monitor_source":"headphones.monitor","mute":false}]`,
		"list sources":     `[{"name":"speakers.monitor","monitor_source":"speakers","mute":false},{"name":"headphones.monitor","monitor_source":"headphones","mute":false},{"name":"microphone","monitor_source":"n/a","mute":false}]`,
		"list sink-inputs": `[]`,
	}
	for name, value := range overrides {
		fixtures[name] = value
	}
	return func(ctx context.Context, args ...string) ([]byte, error) {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		return []byte(fixtures[strings.Join(args, " ")]), nil
	}
}

func TestAudioDiscoveryUsesActualMonitorAndKeepsMicrophoneOptIn(t *testing.T) {
	for _, microphone := range []bool{false, true} {
		route, err := discoverAudio(context.Background(), microphone, audioFixtureQuery(nil), func(int) bool { return false })
		if err != nil || route.OutputMonitor != "speakers.monitor" || (route.MicrophoneDevice != "") != microphone {
			t.Fatalf("wrong route: %+v %v", route, err)
		}
		if route.RouteReason != "default_output" || route.OutputMuted {
			t.Fatalf("incorrect routing facts: %+v", route)
		}
	}
}

func TestAudioDiscoveryPrefersOnlyOneOwnedGameOutput(t *testing.T) {
	for _, test := range []struct{ name, inputs, monitor, reason string }{
		{"one-game", `[{"sink":2,"properties":{"application.process.id":"123"}}]`, "headphones.monitor", "active_game_output"},
		{"same-game-multiple-streams", `[{"sink":2,"properties":{"application.process.id":"123"}},{"sink":2,"properties":{"application.process.id":"123"}}]`, "headphones.monitor", "active_game_output"},
		{"paused-game", `[{"sink":2,"corked":true,"properties":{"application.process.id":"123"}}]`, "speakers.monitor", "default_output"},
		{"unknown-owner", `[{"sink":2,"properties":{"application.process.id":"456"}}]`, "speakers.monitor", "default_output"},
		{"ambiguous", `[{"sink":1,"properties":{"application.process.id":"123"}},{"sink":2,"properties":{"application.process.id":"124"}}]`, "speakers.monitor", "ambiguous_game_output"},
	} {
		t.Run(test.name, func(t *testing.T) {
			route, err := discoverAudio(context.Background(), false, audioFixtureQuery(map[string]string{"list sink-inputs": test.inputs}), func(pid int) bool { return pid == 123 || pid == 124 })
			if err != nil || route.OutputMonitor != test.monitor || route.RouteReason != test.reason {
				t.Fatalf("unexpected route: %+v %v", route, err)
			}
		})
	}
}

func TestAudioDiscoveryReresolvesChangedDefaultAndRefusesMissingMonitor(t *testing.T) {
	route, err := discoverAudio(context.Background(), false, audioFixtureQuery(map[string]string{"info": `{"default_sink_name":"headphones","default_source_name":"microphone"}`}), func(int) bool { return false })
	if err != nil || route.OutputMonitor != "headphones.monitor" {
		t.Fatalf("new default was not resolved: %+v %v", route, err)
	}
	_, err = discoverAudio(context.Background(), false, audioFixtureQuery(map[string]string{"list sources": `[]`}), func(int) bool { return false })
	if err == nil {
		t.Fatal("missing selected monitor accepted")
	}
}

func TestAudioDiscoveryRefusesLoopbackAsMicrophoneAndReportsMute(t *testing.T) {
	_, err := discoverAudio(context.Background(), true, audioFixtureQuery(map[string]string{"info": `{"default_sink_name":"speakers","default_source_name":"speakers.monitor"}`}), func(int) bool { return false })
	if err == nil || !strings.Contains(err.Error(), "microphone") {
		t.Fatal("monitor was accepted as microphone", err)
	}
	route, err := discoverAudio(context.Background(), false, audioFixtureQuery(map[string]string{"list sinks": `[{"index":1,"name":"speakers","monitor_source":"speakers.monitor","mute":false,"volume":{"left":{"value":0},"right":{"value":0}}}]`}), func(int) bool { return false })
	if err != nil || !route.OutputMuted || safeAudioStatus(route, nil).State != "muted" {
		t.Fatalf("zero system volume was hidden: %+v %v", route, err)
	}
}

func TestAudioDiagnosticsExcludePrivateDeviceAndServerData(t *testing.T) {
	route := AudioRouting{OutputMonitor: "private-device-id", MicrophoneDevice: "private-mic-id", RouteReason: "default_output"}
	status := safeAudioStatus(route, errors.New("private-server-do-not-export"))
	encoded, err := json.Marshal([]any{route, status})
	if err != nil || strings.Contains(string(encoded), "private-") {
		t.Fatalf("private metadata reached diagnostics: %s %v", encoded, err)
	}
	_, err = discoverAudio(context.Background(), false, audioFixtureQuery(map[string]string{"info": `private-server-do-not-export`}), func(int) bool { return false })
	if err == nil || strings.Contains(err.Error(), "private-") {
		t.Fatal("raw pactl metadata reached error", err)
	}
}

func TestAudioCommandIsBoundedAndDoesNotExposeSubprocessOutput(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("Python fixture unavailable")
	}
	bin := t.TempDir()
	executable := filepath.Join(bin, "pactl")
	if err := os.WriteFile(executable, []byte("#!"+python+"\nimport sys\nsys.stderr.write('private-audio-error')\nsys.stdout.write('x' * (3 * 1024 * 1024))\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	_, err = audioCommand(context.Background(), "info")
	if err == nil || !strings.Contains(err.Error(), "size limit") || strings.Contains(err.Error(), "private-") {
		t.Fatal("metadata limit not safe", err)
	}
	if err := os.WriteFile(executable, []byte("#!/bin/sh\nexec /bin/sleep 2\n"), 0700); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	start := time.Now()
	_, err = audioCommand(ctx, "info")
	if !errors.Is(err, context.DeadlineExceeded) || time.Since(start) > 500*time.Millisecond {
		t.Fatal("audio query ignored cancellation", err)
	}
}

func TestAudioGameSelectionRequiresOwnedTaggedLiveProcess(t *testing.T) {
	cmd := exec.Command("/bin/sleep", "2")
	for _, entry := range os.Environ() {
		if !strings.HasPrefix(entry, "SteamAppId=") && !strings.HasPrefix(entry, "SteamGameId=") {
			cmd.Env = append(cmd.Env, entry)
		}
	}
	cmd.Env = append(cmd.Env, "SteamAppId=424242")
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = cmd.Process.Kill(); _ = cmd.Wait() }()
	// Start does not guarantee that the child's exec environment is already
	// visible through /proc. Wait for the same owned/tagged/live predicate used
	// in production; do not relax its conservative checks during publication.
	deadline := time.Now().Add(time.Second)
	for !ownedSteamAudioProcess(cmd.Process.Pid) && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if !ownedSteamAudioProcess(cmd.Process.Pid) {
		t.Fatal("owned live Steam-tagged process was not identified")
	}
	if ownedSteamAudioProcess(-1) {
		t.Fatal("invalid process was selected")
	}
}

func TestAudioDiscoveryDoesNotReportReadyAfterCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	base := audioFixtureQuery(nil)
	query := func(ctx context.Context, args ...string) ([]byte, error) {
		if strings.Join(args, " ") == "list sink-inputs" {
			cancel()
			return nil, context.Canceled
		}
		return base(ctx, args...)
	}
	_, err := discoverAudio(ctx, false, query, func(int) bool { return false })
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("cancelled discovery reported ready: %v", err)
	}
}
