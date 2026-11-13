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

func TestMixerPolicyPersistsMuteAndGainOnExplicitSetup(t *testing.T) {
	f := &audioFixture{visible: true, muted: false, volume: 1, tracks: map[string]bool{"1": true}, monitoring: "OBS_MONITORING_TYPE_NONE"}
	server := f.server(t)
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	state, err := c.ConfigureAudioInputPolicy(context.Background(), "managed mic", "chosen.monitor", true, 65)
	if err != nil || !state.Muted || state.Volume != .65 {
		t.Fatalf("saved microphone policy lost: %+v %v", state, err)
	}
	gain := 125.0
	actual, err := c.SetMixerInput(context.Background(), "managed mic", nil, &gain)
	if err != nil || !actual.Muted || actual.GainPercent != 125 {
		t.Fatalf("gain adjustment changed mute or was unconfirmed: %+v %v", actual, err)
	}
	muted := false
	actual, err = c.SetMixerInput(context.Background(), "managed mic", &muted, nil)
	if err != nil || actual.Muted || actual.GainPercent != 125 {
		t.Fatalf("mute adjustment changed gain: %+v %v", actual, err)
	}
}

func TestMixerRejectsAcknowledgedButMissingActualState(t *testing.T) {
	for _, missing := range []string{"GetInputMute", "GetInputVolume"} {
		t.Run(missing, func(t *testing.T) {
			server := mixerProtocolServer(t, func(kind string, data map[string]any) map[string]any {
				switch kind {
				case "GetInputMute":
					if kind != missing {
						return map[string]any{"inputMuted": false}
					}
				case "GetInputVolume":
					if kind != missing {
						return map[string]any{"inputVolumeMul": 1}
					}
				}
				return map[string]any{}
			})
			c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
			if err != nil {
				t.Fatal(err)
			}
			defer c.Close()
			if _, err = c.MixerInput(context.Background(), "owned microphone"); err == nil {
				t.Fatal("zero-valued missing state was accepted as actual OBS evidence")
			}
		})
	}
}

func mixerProtocolServer(t *testing.T, respond func(string, map[string]any) map[string]any) *httptest.Server {
	t.Helper()
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
		var hello any
		if c.ReadJSON(&hello) != nil {
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D struct {
					Kind string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			data := respond(q.D.Kind, q.D.Data)
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Kind, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	return server
}
func TestMixerCreatesMicrophoneDisabledAndVerifiesMuteBeforeCallerEnablesIt(t *testing.T) {
	var mu sync.Mutex
	requests := []string{}
	muted := false
	server := mixerProtocolServer(t, func(kind string, data map[string]any) map[string]any {
		mu.Lock()
		defer mu.Unlock()
		requests = append(requests, kind)
		switch kind {
		case "GetInputList":
			return map[string]any{"inputs": []any{}}
		case "CreateInput":
			if data["sceneItemEnabled"] != false {
				t.Error("new microphone was created audible")
			}
			if data["inputKind"] != "pulse_input_capture" {
				t.Error("unexpected microphone kind")
			}
		case "SetInputMute":
			muted, _ = data["inputMuted"].(bool)
		case "GetInputMute":
			return map[string]any{"inputMuted": muted}
		case "GetInputVolume":
			return map[string]any{"inputVolumeMul": 1}
		}
		return map[string]any{}
	})
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	if err = c.EnsureMutedPulseInput(context.Background(), "owned scene", "owned mic", "private-device"); err != nil {
		t.Fatal(err)
	}
	mu.Lock()
	defer mu.Unlock()
	encoded, _ := json.Marshal(requests)
	if string(encoded) != `["GetInputList","CreateInput","SetInputMute","GetInputMute","GetInputVolume"]` || !muted {
		t.Fatalf("microphone was not safely created and confirmed: %s", encoded)
	}
}
func TestMixerCancellationDoesNotRunUnmuteAfterCancelledGain(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	var mu sync.Mutex
	unmutes := 0
	server := mixerProtocolServer(t, func(kind string, data map[string]any) map[string]any {
		if kind == "SetInputVolume" {
			cancel()
		}
		if kind == "SetInputMute" && data["inputMuted"] == false {
			mu.Lock()
			unmutes++
			mu.Unlock()
		}
		return map[string]any{}
	})
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	muted := false
	gain := 80.0
	if _, err = c.SetMixerInput(ctx, "owned mic", &muted, &gain); err == nil {
		t.Fatal("cancelled mixer mutation succeeded")
	}
	mu.Lock()
	defer mu.Unlock()
	if unmutes != 0 {
		t.Fatal("cancellation still sent an unmute")
	}
}
