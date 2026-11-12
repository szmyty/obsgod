//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
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
	if !strings.Contains(args, "--command=/usr/bin/env com.obsproject.Studio XDG_CONFIG_HOME="+p.OBSConfig+" GST_PLUGIN_PATH_1_0=") || !strings.Contains(args, "--profile OBSGod --collection OBSGod") {
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

type fixtureRequest struct {
	Type string         `json:"requestType"`
	ID   string         `json:"requestId"`
	Data map[string]any `json:"requestData"`
}

func startManagedFixture(t *testing.T, rejectAuth bool, recording bool, active bool, program ...string) <-chan fixtureRequest {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:"+Port)
	if err != nil {
		t.Skip("fixture OBS port is occupied")
	}
	requests := make(chan fixtureRequest, 128)
	scene := LiveScene
	if len(program) > 0 {
		scene = program[0]
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
				D fixtureRequest `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			requests <- q.D
			data := map[string]any{}
			switch q.D.Type {
			case "GetVersion":
				data = map[string]any{"obsVersion": "33.0.1", "obsWebSocketVersion": "5.6.3"}
			case "GetProfileList":
				data = map[string]any{"currentProfileName": "OBSGod"}
			case "GetSceneCollectionList":
				data = map[string]any{"currentSceneCollectionName": "OBSGod"}
			case "GetCurrentProgramScene":
				data = map[string]any{"sceneName": scene}
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
	return requests
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

func fixtureDependencies(t *testing.T) {
	t.Helper()
	bin := t.TempDir()
	if err := os.WriteFile(filepath.Join(bin, "flatpak"), []byte("#!/bin/sh\nexit 0\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin)
}

func drainRequests(requests <-chan fixtureRequest) []fixtureRequest {
	var result []fixtureRequest
	for len(requests) > 0 {
		result = append(result, <-requests)
	}
	return result
}

func TestStartDoesNotReconfigureAnExistingLocalRecording(t *testing.T) {
	requests := startManagedFixture(t, false, true, false)
	fixtureDependencies(t)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	_, err := Start(context.Background(), p)
	if err == nil || !strings.Contains(err.Error(), "recording is already active") {
		t.Fatalf("recording was not protected: %v", err)
	}
	for _, request := range drainRequests(requests) {
		switch request.Type {
		case "SetCurrentProgramScene", "SetInputSettings", "StartStream", "StopStream":
			t.Fatalf("changed existing recording through %s", request.Type)
		}
	}
}

func TestRepeatedStartFailurePreservesTheExistingStream(t *testing.T) {
	requests := startManagedFixture(t, false, false, true)
	fixtureDependencies(t)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 250*time.Millisecond)
	defer cancel()
	_, err := Start(ctx, p)
	if err == nil || !strings.Contains(err.Error(), "existing stream") {
		t.Fatalf("preexisting output failure missing: %v", err)
	}
	for _, request := range drainRequests(requests) {
		switch request.Type {
		case "StopStream", "SetCurrentProgramScene", "SetInputSettings":
			t.Fatalf("failed repeated Start changed existing output through %s", request.Type)
		}
	}
}

func TestCaptureCleanupPreservesRecordingOrUnknownOutput(t *testing.T) {
	requests := startManagedFixture(t, false, true, false)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	_, secret, _ := Load(p)
	c, err := connect(context.Background(), secret, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	haltCaptureIfIdle(context.Background(), c)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	haltCaptureIfIdle(ctx, c)
	for _, request := range drainRequests(requests) {
		if request.Type == "SetCurrentProgramScene" || request.Type == "SetInputSettings" {
			t.Fatalf("unsafe capture cleanup through %s", request.Type)
		}
	}
}

func TestFrameHealthUsesTheCurrentProgramScene(t *testing.T) {
	requests := startManagedFixture(t, false, false, true, IdleScene)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	result := Status(context.Background(), p)
	if !result.Stream.Active || result.Frames != "blank" {
		t.Fatalf("incorrect output/frame facts: %+v", result)
	}
	seen := false
	for _, request := range drainRequests(requests) {
		if request.Type == "GetSourceScreenshot" {
			seen = true
			if request.Data["sourceName"] != IdleScene {
				t.Fatalf("sampled an unused scene: %+v", request.Data)
			}
		}
	}
	if !seen {
		t.Fatal("program output was not sampled")
	}
}

func TestUnreadableOwnedOBSIsNotConfirmedAbsent(t *testing.T) {
	p := testPaths(t)
	root := t.TempDir()
	inaccessible := filepath.Join(root, "42")
	if err := os.MkdirAll(filepath.Join(inaccessible, "environ"), 0700); err != nil {
		t.Fatal(err)
	}
	managed, unidentified := inspectOBSProcesses(p, []string{inaccessible})
	if len(managed) != 0 || !unidentified {
		t.Fatal("unreadable owned OBS was treated as absent")
	}
	ordinary := filepath.Join(root, "43")
	if err := os.MkdirAll(ordinary, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(ordinary, "environ"), []byte("XDG_CONFIG_HOME=/ordinary/obs\x00"), 0600); err != nil {
		t.Fatal(err)
	}
	managed, unidentified = inspectOBSProcesses(p, []string{ordinary})
	if len(managed) != 0 || unidentified {
		t.Fatal("known ordinary OBS was treated as managed or unknown")
	}
}

func TestVisibleRecoveryPreservesSafetyAndRefusesDuplicateOBS(t *testing.T) {
	p := testPaths(t)
	s, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	_, secret, _ := Load(p)
	if err := prepare(p, s, secret, true); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"global.ini", "user.ini"} {
		data, err := os.ReadFile(filepath.Join(p.OBSConfig, "obs-studio", name))
		if err != nil || !strings.Contains(string(data), "SysTrayWhenStarted=false") {
			t.Fatal("recovery preparation still hides OBS", err)
		}
	}
	startManagedFixture(t, false, false, false)
	fixtureDependencies(t)
	_, err = OpenOBS(context.Background(), p)
	if err == nil || !strings.Contains(err.Error(), "already present") {
		t.Fatalf("duplicate recovery launch was allowed: %v", err)
	}
}

func TestOnlyConfirmedTerminalOBSProcessesAreIgnored(t *testing.T) {
	for _, state := range []string{"Z", "X", "R", "S", "T", ""} {
		t.Run("state_"+state, func(t *testing.T) {
			p := testPaths(t)
			proc := filepath.Join(t.TempDir(), "42")
			// A directory reproduces an unreadable environ without relying on root
			// privileges or proc mount policy. State is the independent kernel fact.
			if err := os.MkdirAll(filepath.Join(proc, "environ"), 0700); err != nil {
				t.Fatal(err)
			}
			if state != "" {
				if err := os.WriteFile(filepath.Join(proc, "status"), []byte("Name:\tobs\nState:\t"+state+" (fixture)\n"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			managed, unidentified := inspectOBSProcesses(p, []string{proc})
			terminal := state == "Z" || state == "X"
			if len(managed) != 0 || unidentified == terminal {
				t.Fatalf("incorrect terminal/live handling for %q: %v unknown=%v", state, managed, unidentified)
			}
		})
	}
}

func TestRealZombieDoesNotPreventConfirmedOBSAbsence(t *testing.T) {
	cmd := exec.Command("/bin/sh", "-c", "exit 0")
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer cmd.Wait()
	proc := filepath.Join("/proc", strconv.Itoa(cmd.Process.Pid))
	deadline := time.Now().Add(time.Second)
	for !processExited(proc) && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if !processExited(proc) {
		t.Fatal("test process never reached terminal state before being reaped")
	}
	managed, unidentified := inspectOBSProcesses(testPaths(t), []string{proc})
	if len(managed) != 0 || unidentified {
		t.Fatalf("zombie was treated as running or unknown: %v %v", managed, unidentified)
	}
}

func TestManagedShutdownWaitsForKnownProcessAfterDiscoveryChanges(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("Python helper unavailable")
	}
	p := testPaths(t)
	marker := filepath.Join(t.TempDir(), "ready")
	script := `import ctypes, os, signal, sys, time
libc = ctypes.CDLL(None)
libc.prctl(15, b"obs", 0, 0, 0)
def stop(sig, frame):
    libc.prctl(15, b"stopping", 0, 0, 0)
    libc.prctl(4, 0, 0, 0, 0)
    time.sleep(0.25)
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
open(sys.argv[1], "w").write("ready")
while True: signal.pause()
`
	cmd := exec.Command(python, "-c", script, marker)
	cmd.Env = append(os.Environ(), "XDG_CONFIG_HOME="+p.OBSConfig)
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = cmd.Process.Kill(); _ = cmd.Wait() }()
	deadline := time.Now().Add(time.Second)
	for {
		if _, err := os.Stat(marker); err == nil {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("shutdown helper did not become ready")
		}
		time.Sleep(5 * time.Millisecond)
	}
	if len(managedProcesses(p)) != 1 {
		t.Fatal("known managed helper was not identified")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	start := time.Now()
	if err := stopManagedOBS(ctx, p); err != nil {
		t.Fatal(err)
	}
	if time.Since(start) < 200*time.Millisecond {
		t.Fatal("claimed shutdown while a known process was still alive")
	}
	if !processExited(filepath.Join("/proc", strconv.Itoa(cmd.Process.Pid))) {
		t.Fatal("helper exit was not confirmed")
	}
}

func TestFlatpakResetCannotEscapeManagedConfiguration(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("Python fixture unavailable")
	}
	for _, visible := range []bool{false, true} {
		name := "background"
		if visible {
			name = "visible_recovery"
		}
		t.Run(name, func(t *testing.T) {
			p := testPaths(t)
			p.OBSConfig = filepath.Join(filepath.Dir(p.OBSConfig), "managed config with spaces")
			ordinary := filepath.Join(t.TempDir(), "ordinary config with spaces")
			marker := filepath.Join(ordinary, "obs-studio", "user.ini")
			if err := os.MkdirAll(filepath.Dir(marker), 0700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(marker, []byte("ordinary OBS settings must survive"), 0600); err != nil {
				t.Fatal(err)
			}
			settings, err := Configure(p, strings.NewReader(fixtureSettings))
			if err != nil {
				t.Fatal(err)
			}
			_, secret, err := Load(p)
			if err != nil {
				t.Fatal(err)
			}
			if err := prepare(p, settings, secret, visible); err != nil {
				t.Fatal(err)
			}
			bin := t.TempDir()
			report := filepath.Join(t.TempDir(), "observed.json")
			// Model Flatpak's real ordering: parse requested environment, then reset
			// XDG_CONFIG_HOME to the app's normal directory before executing command.
			flatpak := "#!" + python + "\n" + `import os, sys
args = sys.argv[1:]
command = "obs"
while args:
    value = args.pop(0)
    if value == "com.obsproject.Studio": break
    if value in ("run", "--user"): continue
    if value.startswith("--command="): command = value.split("=", 1)[1]
    elif value.startswith("--env="):
        key, value = value[6:].split("=", 1)
        os.environ[key] = value
    else: raise SystemExit("unsupported fixture Flatpak argument")
os.environ["XDG_CONFIG_HOME"] = ` + strconv.Quote(ordinary) + `
os.execvp(command, [command] + args)
`
			// The stand-in OBS makes a config write just as OBS startup does. It must
			// land in the private directory, never the ordinary OBS configuration.
			obs := "#!" + python + "\n" + `import json, os, pathlib, sys
config = pathlib.Path(os.environ["XDG_CONFIG_HOME"])
(config / "obs-studio/user.ini").write_text("private OBS runtime write")
with (config / "obs-studio/plugin_config/obs-websocket/config.json").open() as stream:
    ws = json.load(stream)
report = {"config": str(config), "args": sys.argv[1:], "websocket_ready": ws.get("server_enabled") is True and ws.get("auth_required") is True and ws.get("server_port") == 4457 and len(ws.get("server_password", "")) == 64}
pathlib.Path(` + strconv.Quote(report) + `).write_text(json.dumps(report))
`
			for executable, source := range map[string]string{"flatpak": flatpak, "obs": obs} {
				if err := os.WriteFile(filepath.Join(bin, executable), []byte(source), 0700); err != nil {
					t.Fatal(err)
				}
			}
			t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
			t.Setenv("DISPLAY", ":99")
			var exited <-chan int
			if visible {
				exited, err = launchVisibleOBS(p)
			} else {
				exited, err = launchOBS(p)
			}
			if err != nil {
				t.Fatal(err)
			}
			select {
			case code := <-exited:
				if code != 0 {
					t.Fatalf("sandbox launch exited %d instead of reaching private configuration", code)
				}
			case <-time.After(3 * time.Second):
				t.Fatal("sandbox launch fixture did not finish")
			}
			var observed struct {
				Config         string   `json:"config"`
				Args           []string `json:"args"`
				WebSocketReady bool     `json:"websocket_ready"`
			}
			data, err := os.ReadFile(report)
			if err != nil {
				t.Fatal(err)
			}
			if err := json.Unmarshal(data, &observed); err != nil {
				t.Fatal(err)
			}
			if observed.Config != p.OBSConfig || !observed.WebSocketReady {
				t.Fatalf("OBS did not receive prepared private configuration: %+v", observed)
			}
			expected := []string{"--profile", "OBSGod", "--collection", "OBSGod", "--multi"}
			if !visible {
				expected = append(expected, "--minimize-to-tray")
			}
			expected = append(expected, "--disable-missing-files-check")
			if !reflect.DeepEqual(observed.Args, expected) {
				t.Fatalf("OBS flags changed: got %v want %v", observed.Args, expected)
			}
			data, err = os.ReadFile(marker)
			if err != nil || string(data) != "ordinary OBS settings must survive" {
				t.Fatal("ordinary OBS configuration was modified", err)
			}
		})
	}
}
