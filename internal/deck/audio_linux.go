//go:build linux

package deck

import (
	"bytes"
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
	"unicode"
	"unicode/utf8"
)

const maxAudioMetadata = 2 * 1024 * 1024

var errAudioMetadataLimit = errors.New("audio metadata limit")

type audioOutput struct {
	buffer   bytes.Buffer
	exceeded bool
}

func (b *audioOutput) Write(data []byte) (int, error) {
	remaining := maxAudioMetadata - b.buffer.Len()
	if len(data) > remaining {
		n, _ := b.buffer.Write(data[:remaining])
		b.exceeded = true
		return n, errAudioMetadataLimit
	}
	return b.buffer.Write(data)
}

func audioCommand(ctx context.Context, args ...string) ([]byte, error) {
	if _, err := exec.LookPath("pactl"); err != nil {
		return nil, &audioDiscoveryError{code: "missing-tool"}
	}
	ctx, cancel := context.WithTimeout(ctx, time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, "pactl", append([]string{"--format=json"}, args...)...)
	command.Env = sessionEnvironment()
	command.Stdin = nil
	command.Stderr = io.Discard
	var output audioOutput
	command.Stdout = &output
	err := command.Run()
	if output.exceeded {
		return nil, &audioDiscoveryError{code: "limit"}
	}
	if err != nil {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, &audioDiscoveryError{code: "query"}
	}
	return output.buffer.Bytes(), nil
}

type pulseVolume struct {
	Value uint64 `json:"value"`
}
type pulseSink struct {
	Index   uint64                 `json:"index"`
	Name    string                 `json:"name"`
	Monitor string                 `json:"monitor_source"`
	Muted   bool                   `json:"mute"`
	Volume  map[string]pulseVolume `json:"volume"`
}
type pulseSource struct {
	Name      string                 `json:"name"`
	MonitorOf string                 `json:"monitor_source"`
	Muted     bool                   `json:"mute"`
	Volume    map[string]pulseVolume `json:"volume"`
}
type pulseInput struct {
	Corked     bool           `json:"corked"`
	Sink       uint64         `json:"sink"`
	Properties map[string]any `json:"properties"`
}
type pulseInfo struct {
	DefaultSink   string `json:"default_sink_name"`
	DefaultSource string `json:"default_source_name"`
}

func validAudioID(value string) bool {
	if value == "" || len(value) > 1024 || !utf8.ValidString(value) {
		return false
	}
	for _, r := range value {
		if unicode.IsControl(r) {
			return false
		}
	}
	return true
}
func volumeZero(volume map[string]pulseVolume) bool {
	if len(volume) == 0 {
		return false
	}
	for _, channel := range volume {
		if channel.Value > 0 {
			return false
		}
	}
	return true
}

// DiscoverAudio resolves the current Steam session's actual output monitor.
// An unambiguous owned Steam-tagged game's output wins; otherwise use the
// current default output. It never changes system routing, sockets or volume.
func DiscoverAudio(ctx context.Context, microphone bool) (AudioRouting, error) {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	return discoverAudio(ctx, microphone, audioCommand, ownedSteamAudioProcess)
}

func discoverAudio(ctx context.Context, microphone bool, query func(context.Context, ...string) ([]byte, error), gameProcess func(int) bool) (AudioRouting, error) {
	route := AudioRouting{MicrophoneRequested: microphone, RouteReason: "default_output"}
	var info pulseInfo
	data, err := query(ctx, "info")
	if err != nil {
		return route, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &info) != nil || !validAudioID(info.DefaultSink) {
		return route, &audioDiscoveryError{code: "metadata"}
	}
	var sinks []pulseSink
	data, err = query(ctx, "list", "sinks")
	if err != nil {
		return route, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &sinks) != nil || len(sinks) > 4096 {
		return route, &audioDiscoveryError{code: "metadata"}
	}
	var sources []pulseSource
	data, err = query(ctx, "list", "sources")
	if err != nil {
		return route, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &sources) != nil || len(sources) > 4096 {
		return route, &audioDiscoveryError{code: "metadata"}
	}
	var selected *pulseSink
	for i := range sinks {
		if sinks[i].Name == info.DefaultSink {
			if selected != nil {
				return route, &audioDiscoveryError{code: "metadata"}
			}
			selected = &sinks[i]
		}
	}
	// An optional sink-input query improves routing for games explicitly routed
	// away from the default. Query failure leaves the proven default route intact.
	if data, err = query(ctx, "list", "sink-inputs"); err == nil && len(data) <= maxAudioMetadata {
		var playing []pulseInput
		if json.Unmarshal(data, &playing) == nil && len(playing) <= 4096 {
			gameSinks := map[uint64]bool{}
			checked := map[int]bool{}
			for _, input := range playing {
				if input.Corked {
					continue
				}
				if err := ctx.Err(); err != nil {
					return route, err
				}
				value, ok := input.Properties["application.process.id"].(string)
				if !ok {
					continue
				}
				pid, err := strconv.Atoi(value)
				if err == nil && pid > 0 {
					owned, known := checked[pid]
					if !known {
						if len(checked) >= 64 {
							continue
						}
						owned = gameProcess(pid)
						checked[pid] = owned
					}
					if owned {
						gameSinks[input.Sink] = true
					}
				}
			}
			if len(gameSinks) == 1 {
				for i := range sinks {
					if gameSinks[sinks[i].Index] {
						selected = &sinks[i]
						route.RouteReason = "active_game_output"
					}
				}
			} else if len(gameSinks) > 1 {
				route.RouteReason = "ambiguous_game_output"
			}
		}
	}
	if err := ctx.Err(); err != nil {
		return route, err
	}
	if selected == nil || !validAudioID(selected.Monitor) {
		return route, &audioDiscoveryError{code: "output"}
	}
	var monitor *pulseSource
	for i := range sources {
		if sources[i].Name == selected.Monitor {
			if monitor != nil {
				return route, &audioDiscoveryError{code: "metadata"}
			}
			monitor = &sources[i]
		}
	}
	if monitor == nil {
		return route, &audioDiscoveryError{code: "output"}
	}
	route.OutputMonitor = selected.Monitor
	route.OutputMuted = selected.Muted || monitor.Muted || volumeZero(selected.Volume) || volumeZero(monitor.Volume)
	if microphone {
		for _, source := range sources {
			if source.Name != info.DefaultSource {
				continue
			}
			if !validAudioID(source.Name) || strings.HasSuffix(source.Name, ".monitor") || (source.MonitorOf != "" && source.MonitorOf != "n/a") {
				return route, &audioDiscoveryError{code: "microphone"}
			}
			if route.MicrophoneDevice != "" {
				return route, &audioDiscoveryError{code: "metadata"}
			}
			route.MicrophoneDevice = source.Name
			route.MicrophoneMuted = source.Muted || volumeZero(source.Volume)
		}
		if route.MicrophoneDevice == "" {
			return route, &audioDiscoveryError{code: "microphone"}
		}
	}
	return route, nil
}

func ownedSteamAudioProcess(pid int) bool {
	proc := filepath.Join("/proc", strconv.Itoa(pid))
	info, err := os.Stat(proc)
	if err != nil {
		return false
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(stat.Uid) != os.Getuid() || processExited(proc) {
		return false
	}
	file, err := os.Open(filepath.Join(proc, "environ"))
	if err != nil {
		return false
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, 128*1024+1))
	if err != nil || len(data) > 128*1024 {
		return false
	}
	for _, entry := range strings.Split(string(data), "\x00") {
		key, value, ok := strings.Cut(entry, "=")
		if !ok || (key != "SteamAppId" && key != "SteamGameId") {
			continue
		}
		id, err := strconv.ParseUint(value, 10, 64)
		if err == nil && id > 0 && id != 769 {
			return true
		}
	}
	return false
}
