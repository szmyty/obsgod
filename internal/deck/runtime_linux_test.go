//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

func TestLaunchUsesSessionBackendAndOnlyManagedConfiguration(t *testing.T) {
	p := testPaths(t)
	args := strings.Join(obsLaunchArgs(p), " ")
	for _, forbidden := range []string{"QT_QPA_PLATFORM", "--safe-mode", "--disable-shutdown-check", "--startstreaming", "--startrecording"} {
		if strings.Contains(args, forbidden) {
			t.Fatalf("unsupported or unsafe launch argument: %s", forbidden)
		}
	}
	if !strings.Contains(args, "--env=XDG_CONFIG_HOME="+p.OBSConfig) || !strings.Contains(args, "--profile OBSGod --collection OBSGod") {
		t.Fatal("launch escapes managed configuration", args)
	}
	if !graphicalSession([]string{"WAYLAND_DISPLAY=wayland-0"}) || !graphicalSession([]string{"DISPLAY=:1"}) {
		t.Fatal("valid X11/Wayland session rejected")
	}
	if graphicalSession([]string{"DISPLAY=", "WAYLAND_DISPLAY=", "PATH=/bin"}) {
		t.Fatal("missing display accepted")
	}
}

func TestRecoveryMarkersAreDetectedWithoutDeletion(t *testing.T) {
	for _, name := range []string{"safe_mode", ".sentinel/run_fixture"} {
		t.Run(name, func(t *testing.T) {
			p := testPaths(t)
			path := filepath.Join(p.OBSConfig, "obs-studio", name)
			if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, []byte("crash-evidence"), 0600); err != nil {
				t.Fatal(err)
			}
			if !recoveryMarkerPresent(p) {
				t.Fatal("recovery marker missed")
			}
			data, err := os.ReadFile(path)
			if err != nil || string(data) != "crash-evidence" {
				t.Fatal("recovery evidence changed", err)
			}
		})
	}
}

func startManagedFixture(t *testing.T, rejectAuth bool, recording bool, active bool) {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:"+Port)
	if err != nil {
		t.Skip("fixture OBS port is occupied")
	}
	upgrader := websocket.Upgrader{}
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.6.3"}})
		var identify any
		if c.ReadJSON(&identify) != nil {
			return
		}
		if rejectAuth {
			_ = c.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(4009, "never-echo-server-secret"), time.Now().Add(time.Second))
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D struct {
					Type string `json:"requestType"`
					ID   string `json:"requestId"`
				} `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			data := map[string]any{}
			switch q.D.Type {
			case "GetVersion":
				data = map[string]any{"obsVersion": "33.0.1", "obsWebSocketVersion": "5.6.3"}
			case "GetProfileList":
				data = map[string]any{"currentProfileName": "OBSGod"}
			case "GetSceneCollectionList":
				data = map[string]any{"currentSceneCollectionName": "OBSGod"}
			case "GetCurrentProgramScene":
				data = map[string]any{"sceneName": LiveScene}
			case "GetRecordStatus":
				data = map[string]any{"outputActive": recording}
			case "GetStreamStatus":
				data = map[string]any{"outputActive": active, "outputBytes": 4096}
			case "GetSourceScreenshot":
				data = map[string]any{"imageData": "not-an-image"}
			}
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
				return
			}
		}
	})}
	go func() { _ = server.Serve(listener) }()
	t.Cleanup(func() { _ = server.Close() })
}

func TestStatusKeepsRecordingAndCaptureIndependentOfStreaming(t *testing.T) {
	startManagedFixture(t, false, true, false)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	result := Status(context.Background(), p)
	if !result.OutputKnown || !result.Recording || result.Stream.Active || !result.Connected || result.State != "stopped" {
		t.Fatalf("independent snapshot missing: %+v", result)
	}
	if result.Game != "unknown" || result.Frames != "blank" {
		t.Fatalf("guessed game presence or frame health: %+v", result)
	}
	if result.Runtime == nil || result.Runtime.WebSocketVersion != "5.6.3" {
		t.Fatal("WebSocket version missing")
	}
}

func TestReadyAuthenticationFailureDoesNotLaunchAnotherOBS(t *testing.T) {
	startManagedFixture(t, true, false, false)
	p := testPaths(t)
	s, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	_, secret, _ := Load(p)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	_, err = ready(ctx, p, s, secret)
	if err == nil || !strings.Contains(err.Error(), "authentication failed") || strings.Contains(err.Error(), "never-echo") {
		t.Fatalf("incorrect authentication result: %v", err)
	}
	b, _ := json.Marshal(ReadDiagnostics(p))
	if strings.Contains(string(b), "Launching OBS") || !strings.Contains(string(b), "rejected the managed WebSocket password") {
		t.Fatal("authentication handling lost stage", string(b))
	}
}

func TestNoGameRecordingStillAttemptsOBSReadinessBeforeCapture(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	bin := t.TempDir()
	marker := filepath.Join(bin, "launch-attempted")
	flatpak := "#!/bin/sh\nif [ \"$1\" = info ]; then exit 0; fi\n: > '" + marker + "'\nexit 42\n"
	if err := os.WriteFile(filepath.Join(bin, "flatpak"), []byte(flatpak), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(bin, "pw-dump"), []byte("#!/bin/sh\necho '[]'\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin)
	t.Setenv("DISPLAY", ":99")
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_, err := TestRecording(ctx, p)
	if err == nil || !strings.Contains(err.Error(), "OBS exited before") {
		t.Fatalf("capture blocked OBS lifecycle: %v", err)
	}
	if _, err := os.Stat(marker); err != nil {
		t.Fatal("OBS launch never attempted", err)
	}
}

func TestStartupBudgetIsIndependentAndCancellationIsPreserved(t *testing.T) {
	p := testPaths(t)
	s, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	_, secret, _ := Load(p)
	bin := t.TempDir()
	// A detached long-running launch is intentionally a fixture. Cleanup it via
	// its pid file so a timeout never leaves a test process behind.
	pidfile := filepath.Join(bin, "pid")
	script := "#!/bin/sh\necho $$ > '" + pidfile + "'\nexec /bin/sleep 10\n"
	if err := os.WriteFile(filepath.Join(bin, "flatpak"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin)
	t.Setenv("DISPLAY", ":99")
	defer func() {
		data, _ := os.ReadFile(pidfile)
		if len(data) > 0 {
			if process, err := os.FindProcess(func() int { n, _ := strconv.Atoi(strings.TrimSpace(string(data))); return n }()); err == nil {
				_ = process.Kill()
			}
		}
	}()
	start := time.Now()
	_, err = readyWithin(context.Background(), p, s, secret, 150*time.Millisecond)
	if err == nil || !strings.Contains(err.Error(), "startup limit") || time.Since(start) > time.Second {
		t.Fatalf("startup limit ignored: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err = readyWithin(ctx, p, s, secret, time.Second)
	if err != context.Canceled {
		t.Fatalf("cancellation was replaced: %v", err)
	}
}
