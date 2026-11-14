package obs

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"net"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/andreykaipov/goobs"
	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/internal/config"
)

type compatibilityRequest struct {
	Connection int
	Type       string
	Data       map[string]any
}

type compatibilityFixture struct {
	server   *httptest.Server
	cfg      config.Config
	mu       sync.Mutex
	requests []compatibilityRequest
	clients  []*websocket.Conn
	agents   []string
	opened   atomic.Int32
	closed   chan int
}

// Responses are deliberately narrow. Any unplanned observation fails, so these
// tests distinguish the legacy ACK contract from v1 confirmed-state workflows.
func newCompatibilityFixture(t *testing.T, respond func(compatibilityRequest) (map[string]any, int)) *compatibilityFixture {
	t.Helper()
	f := &compatibilityFixture{closed: make(chan int, 32)}
	upgrader := websocket.Upgrader{}
	f.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		id := int(f.opened.Add(1))
		f.mu.Lock()
		f.clients = append(f.clients, conn)
		f.agents = append(f.agents, r.Header.Get("User-Agent"))
		f.mu.Unlock()
		defer func() { _ = conn.Close(); f.closed <- id }()
		if conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{
			"rpcVersion": 1, "obsWebSocketVersion": "5.5.2",
			"authentication": map[string]any{"salt": "compat-salt", "challenge": "compat-challenge"},
		}}) != nil {
			return
		}
		var identify struct {
			D struct {
				Authentication string `json:"authentication"`
			} `json:"d"`
		}
		if conn.ReadJSON(&identify) != nil {
			return
		}
		secret := sha256.Sum256([]byte("compat-password" + "compat-salt"))
		auth := sha256.Sum256([]byte(base64.StdEncoding.EncodeToString(secret[:]) + "compat-challenge"))
		if identify.D.Authentication != base64.StdEncoding.EncodeToString(auth[:]) {
			_ = conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(4009, "authentication failed"))
			return
		}
		if conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
			return
		}
		for {
			var wire struct {
				D struct {
					Type string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if conn.ReadJSON(&wire) != nil {
				return
			}
			req := compatibilityRequest{Connection: id, Type: wire.D.Type, Data: wire.D.Data}
			f.mu.Lock()
			f.requests = append(f.requests, req)
			f.mu.Unlock()
			data, code := respond(req)
			if code == 0 { // Keep reading so cancellation can be observed as close.
				continue
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{
				"requestType": wire.D.Type, "requestId": wire.D.ID,
				"requestStatus": map[string]any{"result": code == 100, "code": code, "comment": "private-server-comment"},
				"responseData":  data,
			}}) != nil {
				return
			}
		}
	}))
	host, port, err := net.SplitHostPort(strings.TrimPrefix(f.server.URL, "http://"))
	if err != nil {
		t.Fatal(err)
	}
	number, _ := strconv.Atoi(port)
	f.cfg = config.Config{Host: host, Port: uint32(number), Password: "compat-password"}
	t.Cleanup(func() {
		f.mu.Lock()
		for _, conn := range f.clients {
			_ = conn.Close()
		}
		f.mu.Unlock()
		f.server.Close()
	})
	return f
}

func (f *compatibilityFixture) snapshot() []compatibilityRequest {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]compatibilityRequest{}, f.requests...)
}

func (f *compatibilityFixture) service(t *testing.T) Service {
	t.Helper()
	s := NewServiceWithDialer(&f.cfg, "compat-build", goobs.New)
	t.Cleanup(func() { _ = s.Close() })
	if f.opened.Load() != 0 {
		t.Fatal("service construction contacted OBS")
	}
	return s
}

func TestCompatibilityLegacyMutationsRemainAcknowledgementOnly(t *testing.T) {
	cases := []struct {
		name    string
		request string
		data    map[string]any
		invoke  func(Service) error
	}{
		{"stream start", "StartStream", nil, func(s Service) error { return s.StartStream() }},
		{"stream stop", "StopStream", nil, func(s Service) error { return s.StopStream() }},
		{"stream toggle", "ToggleStream", nil, func(s Service) error { return s.ToggleStream() }},
		{"record start", "StartRecord", nil, func(s Service) error { return s.StartRecording() }},
		{"record stop", "StopRecord", nil, func(s Service) error { return s.StopRecording() }},
		{"record toggle", "ToggleRecord", nil, func(s Service) error { return s.ToggleRecording() }},
		{"record pause", "PauseRecord", nil, func(s Service) error { return s.PauseRecording() }},
		{"record resume", "ResumeRecord", nil, func(s Service) error { return s.ResumeRecording() }},
		{"program scene", "SetCurrentProgramScene", map[string]any{"sceneName": "Game Scene"}, func(s Service) error { return s.SetCurrentScene("Game Scene") }},
		{"preview scene", "SetCurrentPreviewScene", map[string]any{"sceneName": "Game Scene"}, func(s Service) error { return s.SetPreviewScene("Game Scene") }},
		{"collection", "SetCurrentSceneCollection", map[string]any{"sceneCollectionName": "Gaming Collection"}, func(s Service) error { return s.SetCurrentSceneCollection("Gaming Collection") }},
		{"profile", "SetCurrentProfile", map[string]any{"profileName": "Gaming Profile"}, func(s Service) error { return s.SetCurrentProfile("Gaming Profile") }},
		{"label", "SetInputSettings", map[string]any{"inputName": "Score Label", "inputSettings": map[string]any{"text": "10 : 2"}, "overlay": true}, func(s Service) error { return s.SetLabelText("Score Label", "10 : 2") }},
		{"replay start", "StartReplayBuffer", nil, func(s Service) error { return s.StartReplayBuffer() }},
		{"replay stop", "StopReplayBuffer", nil, func(s Service) error { return s.StopReplayBuffer() }},
		{"replay save", "SaveReplayBuffer", nil, func(s Service) error { return s.SaveReplayBuffer() }},
		{"virtual start", "StartVirtualCam", nil, func(s Service) error { return s.StartVirtualCam() }},
		{"virtual stop", "StopVirtualCam", nil, func(s Service) error { return s.StopVirtualCam() }},
		{"virtual toggle", "ToggleVirtualCam", nil, func(s Service) error { return s.ToggleVirtualCam() }},
		{"mute", "ToggleInputMute", map[string]any{"inputName": "Mic Source"}, func(s Service) error { return s.ToggleMute("Mic Source") }},
		{"studio", "SetStudioModeEnabled", map[string]any{"studioModeEnabled": true}, func(s Service) error { return s.SetStudioModeEnabled(true) }},
		{"transition", "TriggerStudioModeTransition", nil, func(s Service) error { return s.TriggerStudioModeTransition() }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
				if r.Type == tc.request {
					return map[string]any{}, 100
				}
				return nil, 204
			})
			s := f.service(t)
			if err := tc.invoke(s); err != nil {
				t.Fatalf("legacy ACK failed: %v", err)
			}
			requests := f.snapshot()
			if len(requests) != 1 || requests[0].Type != tc.request {
				t.Fatalf("ACK path added observations: %+v", requests)
			}
			if tc.data != nil && !reflect.DeepEqual(requests[0].Data, tc.data) {
				t.Fatalf("request data changed: got %+v want %+v", requests[0].Data, tc.data)
			}
			f.mu.Lock()
			agents := append([]string{}, f.agents...)
			f.mu.Unlock()
			if !reflect.DeepEqual(agents, []string{"obsgod/compat-build"}) {
				t.Fatalf("legacy user agent changed: %v", agents)
			}
		})
	}
}

func TestCompatibilityLegacyNarrowReadsPreserveValuesAndOrder(t *testing.T) {
	cases := []struct {
		name, request string
		response      map[string]any
		invoke        func(Service) (any, error)
		want          any
	}{
		{"profiles", "GetProfileList", map[string]any{"currentProfileName": "Game Profile", "profiles": []string{"Second", "Game Profile", "Second", ""}}, func(s Service) (any, error) { return s.ListProfiles() }, []string{"Second", "Game Profile", "Second", ""}},
		{"empty profiles", "GetProfileList", map[string]any{"currentProfileName": "", "profiles": []string{}}, func(s Service) (any, error) { return s.ListProfiles() }, []string{}},
		{"current profile", "GetProfileList", map[string]any{"currentProfileName": "Game Profile", "profiles": []string{"Game Profile"}}, func(s Service) (any, error) { return s.GetCurrentProfile() }, "Game Profile"},
		{"stream status", "GetStreamStatus", map[string]any{"outputActive": true, "outputTimecode": "12:34:56.789"}, func(s Service) (any, error) { return s.GetStreamStatus() }, OutputStatus{Active: true, Timecode: "12:34:56.789"}},
		{"recording status", "GetRecordStatus", map[string]any{"outputActive": true, "outputPaused": true, "outputTimecode": "00:11:22.333"}, func(s Service) (any, error) { return s.GetRecordingStatus() }, OutputStatus{Active: true, Paused: true, Timecode: "00:11:22.333"}},
		{"scenes", "GetSceneList", map[string]any{"scenes": []map[string]any{{"sceneName": "Second"}, {"sceneName": "First"}, {"sceneName": "Second"}}}, func(s Service) (any, error) { return s.ListScenes() }, []string{"Second", "First", "Second"}},
		{"current scene", "GetCurrentProgramScene", map[string]any{"sceneName": "Live Scene"}, func(s Service) (any, error) { return s.GetCurrentScene() }, "Live Scene"},
		{"collections", "GetSceneCollectionList", map[string]any{"currentSceneCollectionName": "Collection A", "sceneCollections": []string{"Collection B", "Collection A"}}, func(s Service) (any, error) { return s.ListSceneCollections() }, []string{"Collection B", "Collection A"}},
		{"current collection", "GetSceneCollectionList", map[string]any{"currentSceneCollectionName": "Collection A", "sceneCollections": []string{"Collection A"}}, func(s Service) (any, error) { return s.GetCurrentSceneCollection() }, "Collection A"},
		{"replay status", "GetReplayBufferStatus", map[string]any{"outputActive": true}, func(s Service) (any, error) { return s.GetReplayBufferActive() }, true},
		{"virtual status", "GetVirtualCamStatus", map[string]any{"outputActive": false}, func(s Service) (any, error) { return s.GetVirtualCamActive() }, false},
		{"special sources", "GetSpecialInputs", map[string]any{"desktop1": "Desktop", "desktop2": "Second Desktop", "mic1": "Built-in", "mic2": "USB", "mic3": "Bluetooth"}, func(s Service) (any, error) { return s.GetSpecialSources() }, SpecialSources{Desktop1: "Desktop", Desktop2: "Second Desktop", Mic1: "Built-in", Mic2: "USB", Mic3: "Bluetooth"}},
		{"studio status", "GetStudioModeEnabled", map[string]any{"studioModeEnabled": true}, func(s Service) (any, error) { return s.IsStudioModeEnabled() }, true},
		{"item names", "GetSceneItemList", map[string]any{"sceneItems": []map[string]any{{"sourceName": "B"}, {"sourceName": "A"}, {"sourceName": "B"}}}, func(s Service) (any, error) { return s.ListSceneItems("Game") }, []string{"B", "A", "B"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
				if r.Type == tc.request {
					return tc.response, 100
				}
				return nil, 204
			})
			value, err := tc.invoke(f.service(t))
			if err != nil || !reflect.DeepEqual(value, tc.want) {
				t.Fatalf("narrow result changed: got %#v want %#v error=%v", value, tc.want, err)
			}
			if requests := f.snapshot(); len(requests) != 1 || requests[0].Type != tc.request {
				t.Fatalf("unrelated state was queried: %+v", requests)
			}
		})
	}
}

func TestCompatibilitySceneItemOrderAndPartialFailure(t *testing.T) {
	for _, toggle := range []bool{false, true} {
		t.Run(strconv.FormatBool(toggle), func(t *testing.T) {
			f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
				switch r.Type {
				case "GetSceneItemId":
					if r.Data["sourceName"] == "missing" {
						return nil, 600
					}
					return map[string]any{"sceneItemId": 7}, 100
				case "GetSceneItemEnabled":
					return map[string]any{"sceneItemEnabled": true}, 100
				case "SetSceneItemEnabled":
					return map[string]any{}, 100
				default:
					return nil, 204
				}
			})
			s := f.service(t)
			var err error
			if toggle {
				err = s.ToggleSceneItem("Game", "First", "missing", "Never")
			} else {
				err = s.SetSceneItemVisible(false, "Game", "First", "missing", "Never")
			}
			if err == nil || strings.Contains(err.Error(), "private-server-comment") {
				t.Fatalf("first failure must be safe: %v", err)
			}
			want := []string{"GetSceneItemId", "SetSceneItemEnabled", "GetSceneItemId"}
			if toggle {
				want = []string{"GetSceneItemId", "GetSceneItemEnabled", "GetSceneItemId", "SetSceneItemEnabled", "GetSceneItemId"}
			}
			requests := f.snapshot()
			got := make([]string, 0, len(requests))
			for _, r := range requests {
				got = append(got, r.Type)
				if r.Data["sourceName"] == "Never" {
					t.Fatal("continued after first failure")
				}
			}
			if !reflect.DeepEqual(got, want) {
				t.Fatalf("request/partial action ordering changed: %v want %v", got, want)
			}
			for _, r := range requests {
				if r.Type == "SetSceneItemEnabled" && r.Data["sceneItemEnabled"] != false {
					t.Fatal("requested visibility changed")
				}
			}
		})
	}
}

func TestCompatibilityCenterRetainsTransformExceptHorizontalPosition(t *testing.T) {
	wantTransform := map[string]any{"positionX": float64(960), "positionY": float64(47), "scaleX": 1.25, "scaleY": 0.75, "rotation": float64(19), "alignment": float64(5), "cropLeft": float64(3), "cropRight": float64(4), "cropTop": float64(5), "cropBottom": float64(6), "boundsType": "OBS_BOUNDS_NONE", "boundsAlignment": float64(0), "boundsWidth": float64(640), "boundsHeight": float64(480)}
	f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
		switch r.Type {
		case "GetSceneItemId":
			return map[string]any{"sceneItemId": 9}, 100
		case "GetSceneItemTransform":
			value := map[string]any{}
			for k, v := range wantTransform {
				value[k] = v
			}
			value["positionX"] = float64(21)
			return map[string]any{"sceneItemTransform": value}, 100
		case "GetVideoSettings":
			return map[string]any{"baseWidth": 1920, "baseHeight": 1080, "outputWidth": 1280, "outputHeight": 720, "fpsNumerator": 60, "fpsDenominator": 1}, 100
		case "SetSceneItemTransform":
			return map[string]any{}, 100
		default:
			return nil, 204
		}
	})
	if err := f.service(t).CenterSceneItem("Game", "Camera"); err != nil {
		t.Fatal(err)
	}
	requests := f.snapshot()
	var gotTypes []string
	for _, r := range requests {
		gotTypes = append(gotTypes, r.Type)
	}
	if !reflect.DeepEqual(gotTypes, []string{"GetSceneItemId", "GetSceneItemTransform", "GetVideoSettings", "SetSceneItemTransform"}) {
		t.Fatalf("center ordering changed: %v", gotTypes)
	}
	transform, ok := requests[3].Data["sceneItemTransform"].(map[string]any)
	if !ok {
		t.Fatal("missing transform")
	}
	for key, want := range wantTransform {
		if transform[key] != want {
			t.Fatalf("centering altered %s: got %#v want %#v", key, transform[key], want)
		}
	}
}

func TestCompatibilityVisibilityKeepsRequestedNamesAndOrder(t *testing.T) {
	f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
		switch r.Type {
		case "GetSceneItemId":
			if r.Data["sourceName"] == "Overlay" {
				return map[string]any{"sceneItemId": 9}, 100
			}
			return map[string]any{"sceneItemId": 7}, 100
		case "GetSceneItemEnabled":
			return map[string]any{"sceneItemEnabled": r.Data["sceneItemId"] == float64(7)}, 100
		default:
			return nil, 204
		}
	})
	got, err := f.service(t).GetSceneItemVisibility("Game", "Overlay", "Camera", "Overlay")
	want := []ItemVisibility{{Name: "Overlay", Visible: false}, {Name: "Camera", Visible: true}, {Name: "Overlay", Visible: false}}
	if err != nil || !reflect.DeepEqual(got, want) {
		t.Fatalf("visibility result order changed: got %+v want %+v err=%v", got, want, err)
	}
	requests := f.snapshot()
	var types []string
	for _, r := range requests {
		types = append(types, r.Type)
	}
	if !reflect.DeepEqual(types, []string{"GetSceneItemId", "GetSceneItemEnabled", "GetSceneItemId", "GetSceneItemEnabled", "GetSceneItemId", "GetSceneItemEnabled"}) {
		t.Fatalf("visibility query order changed: %v", types)
	}
}

func bindCompatibilityContext(t *testing.T, s Service, ctx context.Context) {
	t.Helper()
	binder, ok := s.(interface{ SetContext(context.Context) })
	if !ok {
		t.Fatal("legacy service cannot receive command cancellation")
	}
	binder.SetContext(ctx)
}

func TestCompatibilityPreCancelledInvocationDoesNotDial(t *testing.T) {
	var dials atomic.Int32
	s := NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 4455}, "", func(string, ...goobs.Option) (*goobs.Client, error) {
		dials.Add(1)
		return nil, errors.New("unexpected dial")
	})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	bindCompatibilityContext(t, s, ctx)
	_, err := s.ListProfiles()
	if !errors.Is(err, context.Canceled) || dials.Load() != 0 {
		t.Fatalf("cancelled invocation dialed: err=%v dials=%d", err, dials.Load())
	}
	_ = s.Close()
}

func TestCompatibilityCancellationClosesAcquiredTransportAndNeverReusesIt(t *testing.T) {
	entered := make(chan struct{}, 1)
	f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
		if r.Connection == 1 {
			entered <- struct{}{}
			return nil, 0
		}
		return map[string]any{"currentProfileName": "New", "profiles": []string{"New"}}, 100
	})
	s := f.service(t)
	ctx, cancel := context.WithCancel(context.Background())
	bindCompatibilityContext(t, s, ctx)
	done := make(chan error, 1)
	go func() { _, err := s.ListProfiles(); done <- err }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("request not acquired")
	}
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("lost cancellation: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled request did not return promptly")
	}
	select {
	case id := <-f.closed:
		if id != 1 {
			t.Fatalf("closed wrong transport: %d", id)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled connection remained open")
	}
	bindCompatibilityContext(t, s, context.Background())
	_, _ = s.ListProfiles() // Reconnect or reject; the cancelled socket must not be reused.
	for _, r := range f.snapshot()[1:] {
		if r.Connection == 1 {
			t.Fatal("cancelled transport reused")
		}
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatalf("close not idempotent: %v", err)
	}
}

func TestCompatibilityWaitingCancellationDoesNotCloseAnotherInvocation(t *testing.T) {
	entered, release := make(chan struct{}), make(chan struct{})
	var once sync.Once
	f := newCompatibilityFixture(t, func(r compatibilityRequest) (map[string]any, int) {
		once.Do(func() { close(entered) })
		<-release
		return map[string]any{"currentProfileName": "Game", "profiles": []string{"Game"}}, 100
	})
	s := f.service(t)
	bindCompatibilityContext(t, s, context.Background())
	var releaseOnce sync.Once
	releaseRequest := func() { releaseOnce.Do(func() { close(release) }) }
	t.Cleanup(releaseRequest)
	first := make(chan error, 1)
	go func() { _, err := s.ListProfiles(); first <- err }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("first request not acquired")
	}
	ctx, cancel := context.WithCancel(context.Background())
	bindCompatibilityContext(t, s, ctx)
	waiter := make(chan error, 1)
	go func() { _, err := s.ListProfiles(); waiter <- err }()
	cancel()
	select {
	case err := <-waiter:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("waiter lost cancellation: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled waiter did not return")
	}
	releaseRequest()
	select {
	case err := <-first:
		if err != nil {
			t.Fatalf("waiter cancellation broke acquired owner: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("first request failed to finish")
	}
	if requests := f.snapshot(); len(requests) != 1 {
		t.Fatalf("cancelled waiter sent requests: %+v", requests)
	}
}
