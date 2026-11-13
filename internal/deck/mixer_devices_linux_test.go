//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

func TestMixerDevicesDiscoverRealInputsAndActualAvailability(t *testing.T) {
	query := func(_ context.Context, args ...string) ([]byte, error) {
		switch strings.Join(args, " ") {
		case "info":
			return []byte(`{"default_source_name":"usb-input"}`), nil
		case "list sinks":
			return []byte(`[{"name":"speakers","monitor_source":"renamed-loopback"}]`), nil
		case "list sources":
			return []byte(`[
 {"name":"renamed-loopback","description":"Private monitor"},
 {"name":"sneaky-output","monitor_of_sink":3},
 {"name":"usb-input","description":"Private USB microphone","monitor_of_sink":4294967295,"mute":true},
 {"name":"internal-mic","description":"Internal microphone","active_port":"analog-input-mic","ports":[{"name":"analog-input-mic","availability":"not available"}]},
 {"name":"headset-input","description":"Headset microphone","mute":false}
 ]`), nil
		}
		t.Fatal("unexpected query", args)
		return nil, nil
	}
	devices, muted, err := mixerDevices(context.Background(), query)
	if err != nil || len(devices) != 3 {
		t.Fatal("invalid source inventory", devices, err)
	}
	if !devices[0].Default || devices[0].ID != "usb-input" || !muted["usb-input"] {
		t.Fatal("default/system mute observation lost", devices)
	}
	pref := defaultMixerPreferences(DefaultSettings())
	pref.MicrophoneDevice = "internal-mic"
	if selectedMixerDevice(pref, devices) != "" {
		t.Fatal("unavailable jack input could be selected")
	}
	pref.MicrophoneDevice = "lost-input"
	if selectedMixerDevice(pref, devices) != "" {
		t.Fatal("missing explicit input silently fell back to default")
	}
	pref.MicrophoneDevice = "default"
	if selectedMixerDevice(pref, devices) != "usb-input" {
		t.Fatal("default route was not actual input")
	}
	for _, model := range []struct{ product, model string }{{"Jupiter\n", "lcd"}, {"Galileo", "oled"}, {"Steam Deck 2", "unknown"}} {
		hardware := mixerHardware(model.product)
		if hardware.Model != model.model {
			t.Fatal("model guidance incorrect", hardware)
		}
		encoded, _ := json.Marshal(hardware)
		if strings.Contains(string(encoded), "Private") {
			t.Fatal("device label reached hardware guidance")
		}
	}
}
