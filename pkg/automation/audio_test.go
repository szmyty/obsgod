package automation

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

type audioFixture struct {
	mu         sync.Mutex
	visible    bool
	muted      bool
	volume     float64
	tracks     map[string]bool
	monitoring string
	writes     int
}

func (f *audioFixture) server(t *testing.T) *httptest.Server {
	t.Helper()
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
			data := map[string]any{}
			f.mu.Lock()
			switch q.D.Type {
			case "GetInputPropertiesListPropertyItems":
				data["propertyItems"] = []map[string]any{{"itemName": "private-output-description", "itemEnabled": f.visible, "itemValue": "chosen.monitor"}}
			case "GetInputSettings":
				data["inputSettings"] = map[string]any{"device_id": "chosen.monitor"}
			case "SetInputMute":
				f.muted = q.D.Data["inputMuted"].(bool)
				f.writes++
			case "SetInputVolume":
				f.volume = q.D.Data["inputVolumeMul"].(float64)
				f.writes++
			case "SetInputAudioTracks":
				f.tracks = map[string]bool{}
				for key, value := range q.D.Data["inputAudioTracks"].(map[string]any) {
					f.tracks[key] = value.(bool)
				}
				f.writes++
			case "SetInputAudioMonitorType":
				f.monitoring = q.D.Data["monitorType"].(string)
				f.writes++
			case "GetInputMute":
				data["inputMuted"] = f.muted
			case "GetInputVolume":
				data["inputVolumeMul"] = f.volume
			case "GetInputAudioTracks":
				data["inputAudioTracks"] = f.tracks
			case "GetInputAudioMonitorType":
				data["monitorType"] = f.monitoring
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
func TestManagedAudioRepairsPersistedMixerAndVerifiesRouting(t *testing.T) {
	f := &audioFixture{visible: true, muted: true, volume: 0, tracks: map[string]bool{"1": false, "2": true}, monitoring: "OBS_MONITORING_TYPE_MONITOR_ONLY"}
	server := f.server(t)
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	state, err := c.ConfigureAudioInput(context.Background(), "managed audio", "chosen.monitor")
	if err != nil || !state.DeviceAvailable || state.Muted || state.Volume != 1 || !state.Track1 || state.Monitoring != "OBS_MONITORING_TYPE_NONE" {
		t.Fatalf("audio routing not repaired: %+v %v", state, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.tracks["2"] || f.writes != 4 {
		t.Fatal("managed mixer settings were not explicitly repaired")
	}
}
func TestManagedAudioRefusesHostDeviceAbsentFromOBS(t *testing.T) {
	f := &audioFixture{visible: false}
	server := f.server(t)
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	_, err = c.ConfigureAudioInput(context.Background(), "managed audio", "chosen.monitor")
	if err == nil || strings.Contains(err.Error(), "chosen.monitor") || strings.Contains(err.Error(), "private-output") {
		t.Fatal("missing device result is unsafe", err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.writes != 0 {
		t.Fatal("mixer changed despite an unavailable selected device")
	}
}

func TestAudioSignalObservationDistinguishesSignalSilenceAndNoMeter(t *testing.T) {
	for _, test := range []struct {
		name, input, state string
		peak               float64
	}{
		{"signal", "managed audio", "signal", 0.1},
		{"silence", "managed audio", "silent", 0},
		{"other-input", "unrelated private input", "unknown", 0.8},
	} {
		t.Run(test.name, func(t *testing.T) {
			subscription := make(chan int, 1)
			up := websocket.Upgrader{}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				c, err := up.Upgrade(w, r, nil)
				if err != nil {
					return
				}
				defer c.Close()
				_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
				var identify struct {
					D struct {
						Subscriptions int `json:"eventSubscriptions"`
					} `json:"d"`
				}
				if c.ReadJSON(&identify) != nil {
					return
				}
				subscription <- identify.D.Subscriptions
				_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
				for i := 0; i < 4; i++ {
					event := map[string]any{"op": 5, "d": map[string]any{"eventType": "InputVolumeMeters", "eventIntent": 1 << 16, "eventData": map[string]any{"inputs": []map[string]any{{"inputName": test.input, "inputLevelsMul": [][3]float64{{0, test.peak, 0}}}}}}}
					if c.WriteJSON(event) != nil {
						return
					}
					time.Sleep(10 * time.Millisecond)
				}
				_, _, _ = c.ReadMessage()
			}))
			defer server.Close()
			result, err := ObserveAudioSignal(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second}, "managed audio", 80*time.Millisecond)
			if err != nil || result.State != test.state {
				t.Fatalf("wrong signal observation: %+v %v", result, err)
			}
			if <-subscription != 1<<16 {
				t.Fatal("meter connection did not use only the required event subscription")
			}
			encoded, _ := json.Marshal(result)
			if strings.Contains(string(encoded), "private") {
				t.Fatal("unrelated input reached safe signal data")
			}
		})
	}
}
