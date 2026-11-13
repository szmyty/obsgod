package automation

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

type rebindAudioFixture struct {
	mu       sync.Mutex
	device   string
	kind     string
	visible  bool
	retain   bool
	writes   []string
	settings map[string]any
}

func (f *rebindAudioFixture) server(t *testing.T) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		up := websocket.Upgrader{}
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
		var identify any
		if c.ReadJSON(&identify) != nil {
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D struct {
					Type string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			data := map[string]any{}
			switch q.D.Type {
			case "GetInputSettings":
				data["inputKind"] = f.kind
				data["inputSettings"] = map[string]any{"device_id": f.device, "other-setting": "preserve"}
			case "GetInputPropertiesListPropertyItems":
				data["propertyItems"] = []map[string]any{{"itemEnabled": f.visible, "itemValue": "private-new-device", "itemName": "private-device-description"}}
			case "SetInputSettings":
				f.writes = append(f.writes, q.D.Type)
				f.settings = q.D.Data
				if f.retain {
					f.device = q.D.Data["inputSettings"].(map[string]any)["device_id"].(string)
				}
			default:
				// No mixer, scene, system-volume or output setter belongs here.
				f.writes = append(f.writes, q.D.Type)
			}
			f.mu.Unlock()
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	return server
}

func TestAudioHotplugRebindChangesOnlyExistingInputDevice(t *testing.T) {
	f := &rebindAudioFixture{device: "previous-device", kind: "pulse_output_capture", visible: true, retain: true}
	server := f.server(t)
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	changed, err := c.RebindAudioInput(context.Background(), "owned audio", "pulse_output_capture", "private-new-device")
	if err != nil || !changed {
		t.Fatalf("rebind failed: changed=%v err=%v", changed, err)
	}
	// Repeating the observation does not keep resetting or unmuting the mixer.
	changed, err = c.RebindAudioInput(context.Background(), "owned audio", "pulse_output_capture", "private-new-device")
	if err != nil || changed {
		t.Fatalf("unchanged device was rewritten: %v %v", changed, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.writes) != 1 || f.writes[0] != "SetInputSettings" || f.settings["overlay"] != true {
		t.Fatalf("unexpected changes during recovery: %v %+v", f.writes, f.settings)
	}
	settings := f.settings["inputSettings"].(map[string]any)
	if len(settings) != 1 || settings["device_id"] != "private-new-device" {
		t.Fatalf("recovery changed more than selected device: %+v", settings)
	}
}

func TestAudioHotplugRebindFailsClosedAndRedactsDeviceMetadata(t *testing.T) {
	for _, test := range []struct {
		name, kind string
		visible    bool
		retain     bool
		writes     int
	}{
		{"missing-in-OBS", "pulse_output_capture", false, true, 0},
		{"wrong-kind", "gstreamer-source", true, true, 0},
		{"unknown-kind", "", true, true, 0},
		{"not-retained", "pulse_output_capture", true, false, 1},
	} {
		t.Run(test.name, func(t *testing.T) {
			f := &rebindAudioFixture{device: "previous-device", kind: test.kind, visible: test.visible, retain: test.retain}
			server := f.server(t)
			c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
			if err != nil {
				t.Fatal(err)
			}
			defer c.Close()
			_, err = c.RebindAudioInput(context.Background(), "owned audio", "pulse_output_capture", "private-new-device")
			if err == nil || strings.Contains(err.Error(), "private-") {
				t.Fatalf("unconfirmed/private recovery error: %v", err)
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			if len(f.writes) != test.writes {
				t.Fatalf("unexpected setter count: %v", f.writes)
			}
		})
	}
}

func TestAudioHotplugRefusesMonitorAsMicrophoneBeforeOBSRequest(t *testing.T) {
	c := &Client{}
	if _, err := c.RebindAudioInput(context.Background(), "owned mic", "pulse_input_capture", "speakers.monitor"); err == nil {
		t.Fatal("output monitor was allowed as microphone")
	}
}
