package deck

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestSupportProjectionNeverExportsUntrustedFields(t *testing.T) {
	private := "private-fixture-never-export"
	r := Result{State: private, Message: private, RecordingPath: private,
		Settings: &Settings{Server: "rtmps://" + private, IdleText: private},
		Mixer: &MixerSnapshot{Devices: []MixerDevice{{ID: private, Label: private}},
			Preferences: MixerPreferences{MicrophoneDevice: private}, Notice: MixerNotice{Message: private}},
		Connection: private, Process: private, Capture: private, Game: private, Frames: private}
	data, err := json.Marshal(supportStatus(r))
	if err != nil || strings.Contains(string(data), private) || strings.Contains(string(data), "server") || strings.Contains(string(data), "message") {
		t.Fatal("untrusted state or private fields reached the support projection", err)
	}
	if !strings.Contains(string(data), `"output_known":false`) || !strings.Contains(string(data), `"state":"unknown"`) {
		t.Fatal("unconfirmed output was not represented explicitly")
	}
	r.State, r.OutputKnown, r.Stream.Active = "streaming", true, true
	projected := supportStatus(r)
	if projected.State != "streaming" || !projected.Streaming || !projected.OutputKnown {
		t.Fatal("support projection lost actual output facts")
	}
}
