package automation_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	api "github.com/szmyty/obsgod/pkg/api/v1"
	"github.com/szmyty/obsgod/pkg/automation"
)

// recordingProtocolFixture keeps StopRecord's ACK separate from actual muxer
// shutdown, and can corrupt exactly one lifecycle observation after that ACK.
type recordingProtocolFixture struct {
	mu                       sync.Mutex
	active                   bool
	reads, starts, stops     int
	stopReads, finalizeAfter int
	malformedAt              int
	malformedField           string
	omitField                bool
	malformedValue           any
	omitPaused               bool
	rawRecord                json.RawMessage
	requests                 []string
}

func (f *recordingProtocolFixture) address(t *testing.T) string {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := (&websocket.Upgrader{}).Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		_ = conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
		var identify any
		if conn.ReadJSON(&identify) != nil {
			return
		}
		_ = conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D struct {
					Type string `json:"requestType"`
					ID   string `json:"requestId"`
				} `json:"d"`
			}
			if conn.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			f.requests = append(f.requests, q.D.Type)
			data := map[string]any{}
			code := 100
			switch q.D.Type {
			case "GetVersion":
				data = map[string]any{"obsVersion": "33.0.1", "obsWebSocketVersion": "5.5.0"}
			case "GetProfileList":
				data = map[string]any{"currentProfileName": "Fixture", "profiles": []string{"Fixture"}}
			case "GetSceneCollectionList":
				data = map[string]any{"currentSceneCollectionName": "Fixture", "sceneCollections": []string{"Fixture"}}
			case "GetCurrentProgramScene":
				data["sceneName"] = "Fixture"
			case "GetRecordStatus":
				f.reads++
				if f.stops > 0 {
					f.stopReads++
					if f.finalizeAfter > 0 && f.stopReads >= f.finalizeAfter {
						f.active = false
					}
				}
				data = map[string]any{"outputActive": f.active, "outputPaused": false, "outputBytes": 4096, "outputDuration": 1000}
				if f.omitPaused {
					delete(data, "outputPaused")
				}
				if f.reads == f.malformedAt {
					if f.omitField {
						delete(data, f.malformedField)
					} else {
						data[f.malformedField] = f.malformedValue
					}
				}
			case "StartRecord":
				f.starts++
				f.active = true
			case "StopRecord":
				f.stops++
				data["outputPath"] = "/fixture/preserved-recording.mkv"
			default:
				code = 204
			}
			var responseData any = data
			if q.D.Type == "GetRecordStatus" && f.rawRecord != nil {
				responseData = f.rawRecord
			}
			f.mu.Unlock()
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code}, "responseData": responseData}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	return strings.TrimPrefix(server.URL, "http://")
}

func (f *recordingProtocolFixture) dial(t *testing.T) *automation.Client {
	t.Helper()
	c, err := automation.Connect(context.Background(), automation.Config{Address: f.address(t), Timeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c
}

var malformedRecordingFlags = []struct {
	name  string
	omit  bool
	value any
}{
	{name: "omitted", omit: true},
	{name: "null"},
	{name: "string", value: "private-server-value"},
	{name: "number", value: 0},
	{name: "object", value: map[string]any{}},
	{name: "array", value: []bool{false}},
}

func TestRecordingLifecycleRejectsUnknownActive(t *testing.T) {
	for _, phase := range []struct {
		name          string
		read          int
		active        bool
		starts, stops int
	}{
		{name: "runtime", read: 1, active: true},
		{name: "start-preflight", read: 1},
		{name: "start-confirmation", read: 2, starts: 1},
		{name: "stop-preflight", read: 1, active: true},
		{name: "stop-finalization", read: 2, active: true, stops: 1},
	} {
		for _, flag := range malformedRecordingFlags {
			t.Run(phase.name+"/"+flag.name, func(t *testing.T) {
				f := &recordingProtocolFixture{active: phase.active, malformedAt: phase.read, malformedField: "outputActive", omitField: flag.omit, malformedValue: flag.value}
				c := f.dial(t)
				ctx, cancel := context.WithTimeout(context.Background(), time.Second)
				defer cancel()
				var err error
				var path string
				switch phase.name {
				case "runtime":
					_, err = c.RuntimeStatus(ctx)
				case "start-preflight", "start-confirmation":
					err = c.StartRecording(ctx)
				default:
					path, err = c.StopRecording(ctx)
				}
				var request *automation.RequestError
				if !errors.As(err, &request) || request.Operation != "GetRecordStatus" || request.Code != 0 || path != "" {
					t.Fatalf("unknown recording observation became success: path=%q err=%v", path, err)
				}
				if strings.Contains(err.Error(), "private-server-value") {
					t.Fatal("raw response escaped through recording diagnostic")
				}
				f.mu.Lock()
				defer f.mu.Unlock()
				if f.starts != phase.starts || f.stops != phase.stops || f.reads != phase.read {
					t.Fatalf("unexpected lifecycle requests: starts=%d stops=%d reads=%d", f.starts, f.stops, f.reads)
				}
				if phase.stops > 0 && !f.active {
					t.Fatal("fixture did not preserve active recording after StopRecord ACK")
				}
			})
		}
	}
}

func TestRecordingStatusRequiresKnownPaused(t *testing.T) {
	for _, method := range []string{"recording", "api", "media", "configure-media"} {
		for _, flag := range malformedRecordingFlags {
			t.Run(method+"/"+flag.name, func(t *testing.T) {
				f := &recordingProtocolFixture{malformedAt: 1, malformedField: "outputPaused", omitField: flag.omit, malformedValue: flag.value}
				c := f.dial(t)
				var err error
				switch method {
				case "recording":
					_, err = c.RecordingStatus(context.Background())
				case "api":
					_, err = c.APIRecordingStatus(context.Background())
				case "media":
					_, err = c.MediaStatus(context.Background())
				default:
					err = c.ConfigureMediaProfile(context.Background(), "/fixture/recordings", 60, 256)
				}
				if err == nil {
					t.Fatal("unknown paused state became known false")
				}
				f.mu.Lock()
				defer f.mu.Unlock()
				if len(f.requests) != 1 || f.requests[0] != "GetRecordStatus" {
					t.Fatalf("unknown media observation authorized subsequent requests: %v", f.requests)
				}
			})
		}
	}
}

func TestPublicRecordingLifecycleValidatesEveryObservation(t *testing.T) {
	for _, phase := range []struct {
		name          string
		read          int
		active        bool
		starts, stops int
	}{
		{name: "start-public-preflight", read: 1},
		{name: "start-backend-preflight", read: 2},
		{name: "start-confirmation", read: 3, starts: 1},
		{name: "stop-public-preflight", read: 1, active: true},
		{name: "stop-backend-preflight", read: 2, active: true},
		{name: "stop-finalization", read: 3, active: true, stops: 1},
	} {
		for _, flag := range malformedRecordingFlags {
			t.Run(phase.name+"/"+flag.name, func(t *testing.T) {
				f := &recordingProtocolFixture{active: phase.active, malformedAt: phase.read, malformedField: "outputActive", omitField: flag.omit, malformedValue: flag.value}
				c, err := api.Connect(context.Background(), api.Connection{Address: f.address(t)})
				if err != nil {
					t.Fatal(err)
				}
				t.Cleanup(func() { _ = c.Close() })
				var path string
				if strings.HasPrefix(phase.name, "start") {
					err = c.StartRecording(context.Background(), api.Approval{Recording: true})
				} else {
					path, err = c.StopRecording(context.Background(), api.Approval{Recording: true})
				}
				var failure *api.Error
				if !errors.As(err, &failure) || failure.Code != api.OBSRequest || path != "" {
					t.Fatalf("public recording reported unknown state as success: path=%q err=%v", path, err)
				}
				f.mu.Lock()
				defer f.mu.Unlock()
				if f.starts != phase.starts || f.stops != phase.stops || f.reads != phase.read {
					t.Fatalf("unexpected public lifecycle requests: starts=%d stops=%d reads=%d", f.starts, f.stops, f.reads)
				}
			})
		}
	}
}

func TestRecordingLifecyclePreservesDelayedShutdownAndIndependentOutputs(t *testing.T) {
	f := &recordingProtocolFixture{omitPaused: true, finalizeAfter: 3}
	c := f.dial(t)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if _, err := c.RuntimeStatus(ctx); err != nil {
		t.Fatal("runtime requires only the active flag it exposes:", err)
	}
	if err := c.StartRecording(ctx); err != nil {
		t.Fatal(err)
	}
	if err := c.StartRecording(ctx); err != nil {
		t.Fatal("repeated Start did not preserve existing recording:", err)
	}
	path, err := c.StopRecording(ctx)
	if err != nil || path != "/fixture/preserved-recording.mkv" {
		t.Fatalf("valid delayed stop failed: path=%q err=%v", path, err)
	}
	if path, err = c.StopRecording(ctx); err != nil || path != "" {
		t.Fatalf("known idle stop was not idempotent: path=%q err=%v", path, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.active || f.starts != 1 || f.stops != 1 || f.stopReads < 3 {
		t.Fatalf("recording returned without observed shutdown: active=%v starts=%d stops=%d polls=%d", f.active, f.starts, f.stops, f.stopReads)
	}
	for _, request := range f.requests {
		if strings.Contains(request, "Stream") || strings.Contains(request, "Replay") {
			t.Fatal("recording changed independent output:", request)
		}
	}
}

func TestLegacyRecordingStillReturnsRequestAcknowledgement(t *testing.T) {
	f := &recordingProtocolFixture{malformedAt: 1, malformedField: "outputActive", omitField: true}
	c := f.dial(t)
	for _, operation := range []automation.LegacyOperation{automation.LegacyStartRecording, automation.LegacyStopRecording} {
		if _, err := c.Legacy(context.Background(), automation.LegacyRequest{Operation: operation}); err != nil {
			t.Fatal(err)
		}
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.reads != 0 || f.starts != 1 || f.stops != 1 || !f.active {
		t.Fatalf("legacy ACK semantics changed: reads=%d starts=%d stops=%d active=%v", f.reads, f.starts, f.stops, f.active)
	}
}

func TestRecordingObservationsUseValidatedCanonicalFlags(t *testing.T) {
	// Generated structs accept these later case-insensitive aliases. Lifecycle
	// decisions and exposed flags must consume the exact validated keys instead.
	raw := json.RawMessage(`{"outputActive":true,"OUTPUTACTIVE":false,"outputPaused":true,"OUTPUTPAUSED":false,"outputBytes":4096}`)
	for _, method := range []string{"runtime", "status", "api", "start", "stop"} {
		t.Run(method, func(t *testing.T) {
			f := &recordingProtocolFixture{active: true, rawRecord: raw}
			c := f.dial(t)
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			switch method {
			case "runtime":
				state, err := c.RuntimeStatus(ctx)
				if err != nil || !state.Recording {
					t.Fatalf("canonical active flag was overwritten: state=%+v err=%v", state, err)
				}
			case "status", "api":
				var state automation.RecordingStatus
				var err error
				if method == "status" {
					state, err = c.RecordingStatus(ctx)
				} else {
					state, err = c.APIRecordingStatus(ctx)
				}
				if err != nil || !state.Active || !state.Paused {
					t.Fatalf("canonical recording flags were overwritten: state=%+v err=%v", state, err)
				}
			case "start":
				if err := c.StartRecording(ctx); err != nil {
					t.Fatal(err)
				}
			case "stop":
				stopCtx, stopCancel := context.WithTimeout(ctx, 30*time.Millisecond)
				defer stopCancel()
				path, err := c.StopRecording(stopCtx)
				if !errors.Is(err, context.DeadlineExceeded) || path != "" {
					t.Fatalf("case alias falsely confirmed inactive muxer: path=%q err=%v", path, err)
				}
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			if f.starts != 0 || (method == "stop" && f.stops != 1) {
				t.Fatalf("canonical active flag did not drive preflight: starts=%d stops=%d", f.starts, f.stops)
			}
		})
	}
}
