//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

var sessionKeys = map[string]bool{"DISPLAY": true, "WAYLAND_DISPLAY": true, "XAUTHORITY": true, "DBUS_SESSION_BUS_ADDRESS": true, "XDG_RUNTIME_DIR": true, "XDG_CURRENT_DESKTOP": true, "PULSE_SERVER": true}

func sessionEnvironment() []string {
	m := map[string]string{}
	for _, k := range []string{"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_CURRENT_DESKTOP", "PULSE_SERVER", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE"} {
		if v := os.Getenv(k); v != "" {
			m[k] = v
		}
	}
	// Decky's service can retain Desktop Mode environment. The current Steam
	// process is authoritative for the graphical session; import only this list.
	processes := ownedProcesses("steam")
	sort.Slice(processes, func(i, j int) bool {
		a, _ := strconv.Atoi(filepath.Base(processes[i]))
		b, _ := strconv.Atoi(filepath.Base(processes[j]))
		return a > b
	})
	for _, p := range processes {
		b, e := os.ReadFile(filepath.Join(p, "environ"))
		if e != nil {
			continue
		}
		// A current Steam session replaces stale graphical/session values, including
		// keys absent from its environment; do not combine Desktop Wayland with a
		// different Gaming Mode X11 session.
		for k := range sessionKeys {
			delete(m, k)
		}
		for _, s := range strings.Split(string(b), "\x00") {
			k, v, ok := strings.Cut(s, "=")
			if ok && sessionKeys[k] {
				m[k] = v
			}
		}
		break
	}
	if m["XDG_RUNTIME_DIR"] == "" {
		m["XDG_RUNTIME_DIR"] = "/run/user/" + strconv.Itoa(os.Getuid())
	}
	if m["DBUS_SESSION_BUS_ADDRESS"] == "" {
		m["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + m["XDG_RUNTIME_DIR"] + "/bus"
	}
	result := make([]string, 0, len(m))
	for k, v := range m {
		result = append(result, k+"="+v)
	}
	return result
}

func ownedProcesses(comm string) []string {
	var result []string
	paths, _ := filepath.Glob("/proc/[0-9]*")
	for _, p := range paths {
		i, e := os.Stat(p)
		if e != nil {
			continue
		}
		st, ok := i.Sys().(*syscall.Stat_t)
		if !ok || int(st.Uid) != os.Getuid() {
			continue
		}
		b, e := os.ReadFile(filepath.Join(p, "comm"))
		if e == nil && strings.TrimSpace(string(b)) == comm {
			result = append(result, p)
		}
	}
	return result
}

// A zombie has no executable image or output sockets, but remains in /proc
// until its parent reaps it. Its environ may be unreadable. Ignore only a
// positively identified terminal state; unreadable live processes stay unknown.
func processExited(proc string) bool {
	data, err := os.ReadFile(filepath.Join(proc, "status"))
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "State:") {
			fields := strings.Fields(strings.TrimPrefix(line, "State:"))
			return len(fields) > 0 && (fields[0] == "Z" || fields[0] == "X")
		}
	}
	return false
}

func inspectOBSProcesses(p Paths, processes []string) ([]int, bool) {
	var result []int
	unidentified := false
	for _, proc := range processes {
		if processExited(proc) {
			continue
		}
		b, err := os.ReadFile(filepath.Join(proc, "environ"))
		if err != nil {
			if !os.IsNotExist(err) && !processExited(proc) {
				unidentified = true
			}
			continue
		}
		for _, value := range strings.Split(string(b), "\x00") {
			if value == "XDG_CONFIG_HOME="+p.OBSConfig {
				id, err := strconv.Atoi(filepath.Base(proc))
				if err == nil && id > 0 {
					result = append(result, id)
				}
			}
		}
	}
	return result, unidentified
}

func managedProcesses(p Paths) []int {
	processes, _ := inspectOBSProcesses(p, ownedProcesses("obs"))
	return processes
}

func obsProcessState(p Paths) string {
	processes, unidentified := inspectOBSProcesses(p, ownedProcesses("obs"))
	if len(processes) > 0 {
		return "running"
	}
	if unidentified {
		return "unknown"
	}
	return "absent"
}

func commandOutput(ctx context.Context, name string, args ...string) ([]byte, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Env = sessionEnvironment()
	cmd.Stderr = io.Discard
	return cmd.Output()
}

func checkDependencies(ctx context.Context) error {
	if _, e := exec.LookPath("flatpak"); e != nil {
		return errors.New("Flatpak is missing; use OBSGod on SteamOS or install Flatpak first")
	}
	for _, id := range []string{"com.obsproject.Studio", "com.obsproject.Studio.Plugin.Gstreamer"} {
		dependencyCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
		_, err := commandOutput(dependencyCtx, "flatpak", "info", "--user", id)
		cancel()
		if err != nil {
			return errors.New("install OBS and its GStreamer capture plugin using OBSGod Desktop setup")
		}
	}
	return nil
}

func captureAvailability(ctx context.Context) string {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	b, e := commandOutput(ctx, "pw-dump")
	if e != nil || len(b) > 16*1024*1024 {
		return "unknown"
	}
	var nodes []struct {
		Info struct {
			Props map[string]any `json:"props"`
		} `json:"info"`
	}
	if json.Unmarshal(b, &nodes) != nil {
		return "unknown"
	}
	for _, n := range nodes {
		if n.Info.Props["node.name"] == "gamescope" {
			return "available"
		}
	}
	return "unavailable"
}

func gamescopeReady(ctx context.Context) bool { return captureAvailability(ctx) == "available" }

// OBS 28+ bundles WebSocket v5. Do not use Safe Mode: it disables WebSockets
// and the third-party GStreamer capture source. Let Qt choose its backend from
// the current session; forcing xcb conflicts with Flatpak's fallback-x11 when
// a Wayland socket is available.
func obsLaunchArgs(p Paths) []string {
	// Flatpak resets XDG_CONFIG_HOME after applying its --env overrides.
	// Apply this non-secret path inside the sandbox, after that reset, so OBS
	// reads only its prepared private profile and WebSocket configuration. env
	// execs OBS directly; no shell interpolation or automatic output is involved.
	return []string{"run", "--user", "--command=/usr/bin/env", "com.obsproject.Studio", "XDG_CONFIG_HOME=" + p.OBSConfig, "obs", "--profile", "OBSGod", "--collection", "OBSGod", "--multi", "--minimize-to-tray", "--disable-missing-files-check"}
}

func graphicalSession(env []string) bool {
	for _, variable := range env {
		if (strings.HasPrefix(variable, "DISPLAY=") && variable != "DISPLAY=") || (strings.HasPrefix(variable, "WAYLAND_DISPLAY=") && variable != "WAYLAND_DISPLAY=") {
			return true
		}
	}
	return false
}

func recoveryMarkerPresent(p Paths) bool {
	// Only detect; never delete OBS crash evidence or bypass its recovery choice.
	if info, err := os.Lstat(filepath.Join(p.OBSConfig, "obs-studio/safe_mode")); err == nil && info.Mode().IsRegular() {
		return true
	}
	paths, _ := filepath.Glob(filepath.Join(p.OBSConfig, "obs-studio/.sentinel/run_*"))
	for _, path := range paths {
		if info, err := os.Lstat(path); err == nil && info.Mode().IsRegular() {
			return true
		}
	}
	return false
}

func launchOBS(p Paths) (<-chan int, error)        { return launchOBSWindow(p, false) }
func launchVisibleOBS(p Paths) (<-chan int, error) { return launchOBSWindow(p, true) }
func launchOBSWindow(p Paths, visible bool) (<-chan int, error) {
	if e := privateDir(p.OBSConfig); e != nil {
		return nil, e
	}
	args := obsLaunchArgs(p)
	if visible {
		filtered := args[:0]
		for _, arg := range args {
			if arg != "--minimize-to-tray" {
				filtered = append(filtered, arg)
			}
		}
		args = filtered
	}
	cmd := exec.Command("flatpak", args...)
	cmd.Env = sessionEnvironment()
	if !graphicalSession(cmd.Env) {
		logEvent(p, "session.no-display")
		return nil, errors.New("no graphical display is available for the current Steam session; restart Gaming Mode or open the managed OBS instance in Desktop Mode")
	}

	cmd.Stdin = nil
	output, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		return nil, errors.New("could not prepare the OBS launch")
	}
	defer output.Close()
	// A real inherited descriptor survives this short-lived CLI. A Go writer
	// would create pipes that disappear when the CLI exits, breaking OBS later.
	cmd.Stdout = output
	cmd.Stderr = output
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if e := cmd.Start(); e != nil {
		return nil, errors.New("OBS launch failed; open OBSGod Desktop setup and check dependencies")
	}
	// Observe early Flatpak/OBS failures instead of waiting 75 seconds for a
	// connection that cannot appear. No pipes keep this CLI attached to OBS.
	exited := make(chan int, 1)
	go func() {
		_ = cmd.Wait()
		exited <- cmd.ProcessState.ExitCode()
	}()
	return exited, nil
}

func stopManagedOBS(ctx context.Context, p Paths) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	processes := managedProcesses(p)
	for _, pid := range processes {
		if err := syscall.Kill(pid, syscall.SIGTERM); err != nil && err != syscall.ESRCH {
			return errors.New("could not stop the managed OBS process")
		}
	}
	for {
		// Keep observing the already-identified children even if a live process
		// briefly loses readable environ/comm during shutdown. Never signal an
		// unknown process or infer exit from disappearance from discovery alone.
		pending := false
		for _, pid := range processes {
			proc := filepath.Join("/proc", strconv.Itoa(pid))
			if _, err := os.Stat(proc); os.IsNotExist(err) {
				continue
			}
			if !processExited(proc) {
				pending = true
			}
		}
		process, listener := presence(p)
		if !pending && process == "absent" && !listener {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(100 * time.Millisecond):
		}
	}
}

func privateUmask() { syscall.Umask(0077) }
