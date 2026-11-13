//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"os"
	"sort"
	"strings"
	"syscall"
	"unicode/utf8"
)

// MixerDevices returns private, local-UI labels. This is observation only: no
// pactl set-* operation, socket permission change, or system default alteration.
func MixerDevices(ctx context.Context) ([]MixerDevice, map[string]bool, error) {
	return mixerDevices(ctx, audioCommand)
}
func mixerDevices(ctx context.Context, query func(context.Context, ...string) ([]byte, error)) ([]MixerDevice, map[string]bool, error) {
	var info pulseInfo
	data, err := query(ctx, "info")
	if err != nil {
		return nil, nil, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &info) != nil {
		return nil, nil, &audioDiscoveryError{code: "metadata"}
	}
	var sinks []pulseSink
	data, err = query(ctx, "list", "sinks")
	if err != nil {
		return nil, nil, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &sinks) != nil || len(sinks) > 4096 {
		return nil, nil, &audioDiscoveryError{code: "metadata"}
	}
	var sources []struct {
		pulseSource
		Description string `json:"description"`
		ActivePort  string `json:"active_port"`
		Ports       []struct {
			Name         string `json:"name"`
			Availability string `json:"availability"`
		} `json:"ports"`
	}
	data, err = query(ctx, "list", "sources")
	if err != nil {
		return nil, nil, err
	}
	if len(data) > maxAudioMetadata || json.Unmarshal(data, &sources) != nil || len(sources) > 4096 {
		return nil, nil, &audioDiscoveryError{code: "metadata"}
	}
	devices := []MixerDevice{}
	muted := map[string]bool{}
	seen := map[string]bool{}
	for _, source := range sources {
		if !validMixerDeviceID(source.Name) || sourceIsMonitor(source.pulseSource, sinks) {
			continue
		}
		if seen[source.Name] {
			return nil, nil, &audioDiscoveryError{code: "metadata"}
		}
		seen[source.Name] = true
		label := source.Description
		if label == "" || !validMixerText(label, 256) || !utf8.ValidString(label) {
			label = "Microphone input"
		}
		available := true
		for _, port := range source.Ports {
			if port.Name == source.ActivePort && port.Availability == "not available" {
				available = false
			}
		}
		devices = append(devices, MixerDevice{ID: source.Name, Label: label, Default: source.Name == info.DefaultSource, Available: available})
		muted[source.Name] = source.Muted || volumeZero(source.Volume)
	}
	sort.Slice(devices, func(i, j int) bool {
		if devices[i].Default != devices[j].Default {
			return devices[i].Default
		}
		return devices[i].ID < devices[j].ID
	})
	return devices, muted, nil
}
func MixerHardwareInfo() MixerHardware {
	data, _ := os.ReadFile("/sys/devices/virtual/dmi/id/product_name")
	return mixerHardware(string(data))
}
func mixerHardware(product string) MixerHardware {
	switch strings.ToLower(strings.TrimSpace(product)) {
	case "jupiter":
		return MixerHardware{Model: "lcd", Guidance: "Steam Deck LCD may disable its built-in microphone when a 3.5 mm headset is connected. Availability comes from observed audio devices; choose a USB/Bluetooth or available headset microphone when needed"}
	case "galileo":
		return MixerHardware{Model: "oled", Guidance: "Steam Deck OLED supports its built-in microphone with a 3.5 mm headset. Availability comes from observed audio devices; USB/Bluetooth and headset inputs can still change"}
	default:
		return MixerHardware{Model: "unknown", Guidance: "Microphone availability comes from observed audio devices. Check the selected input after connecting or removing a headset; no hardware-specific jack behavior is assumed"}
	}
}

func openMixerFile(path string) (*os.File, error) {
	return os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
}
