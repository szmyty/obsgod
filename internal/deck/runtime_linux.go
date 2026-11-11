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
	for _, p := range ownedProcesses("steam") {
		b, e := os.ReadFile(filepath.Join(p, "environ"))
		if e != nil {
			continue
		}
		for _, s := range strings.Split(string(b), "\x00") {
			k, v, ok := strings.Cut(s, "=")
			if ok && sessionKeys[k] {
				m[k] = v
			}
		}
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

func managedProcesses(p Paths) []int {
	var result []int
	for _, proc := range ownedProcesses("obs") {
		b, e := os.ReadFile(filepath.Join(proc, "environ"))
		if e != nil {
			continue
		}
		for _, v := range strings.Split(string(b), "\x00") {
			if v == "XDG_CONFIG_HOME="+p.OBSConfig {
				id, _ := strconv.Atoi(filepath.Base(proc))
				result = append(result, id)
			}
		}
	}
	return result
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
		if _, e := commandOutput(ctx, "flatpak", "info", "--user", id); e != nil {
			return errors.New("install OBS and its GStreamer capture plugin using OBSGod Desktop setup")
		}
	}
	return nil
}

func gamescopeReady(ctx context.Context) bool {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	b, e := commandOutput(ctx, "pw-dump")
	if e != nil || len(b) > 16*1024*1024 {
		return false
	}
	var nodes []struct {
		Info struct {
			Props map[string]any `json:"props"`
		} `json:"info"`
	}
	if json.Unmarshal(b, &nodes) != nil {
		return false
	}
	for _, n := range nodes {
		if n.Info.Props["node.name"] == "gamescope" {
			return true
		}
	}
	return false
}

func launchOBS(p Paths) (<-chan int, error) {
	if e := privateDir(p.OBSConfig); e != nil {
		return nil, e
	}
	cmd := exec.Command("flatpak", "run", "--user", "--env=XDG_CONFIG_HOME="+p.OBSConfig, "--env=QT_QPA_PLATFORM=xcb", "com.obsproject.Studio", "--profile", "OBSGod", "--collection", "OBSGod", "--multi", "--minimize-to-tray", "--disable-shutdown-check", "--disable-missing-files-check")
	cmd.Env = sessionEnvironment()
	hasDisplay := false
	for _, variable := range cmd.Env {
		if strings.HasPrefix(variable, "DISPLAY=") && variable != "DISPLAY=" {
			hasDisplay = true
		}
	}
	if !hasDisplay {
		logEvent(p, "session.no-display")
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
	for _, pid := range managedProcesses(p) {
		if e := syscall.Kill(pid, syscall.SIGTERM); e != nil && e != syscall.ESRCH {
			return errors.New("could not stop the managed OBS process")
		}
	}
	for len(managedProcesses(p)) > 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(200 * time.Millisecond):
		}
	}
	return nil
}

func privateUmask() { syscall.Umask(0077) }
