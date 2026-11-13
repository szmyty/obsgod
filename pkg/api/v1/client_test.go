package v1

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/pkg/automation"
)

type fixture struct {
	starts        atomic.Int32
	stops         atomic.Int32
	active        bool
	bytes         float64
	unknown       bool
	reject        bool
	hang          bool
	server        string
	key           string
	camera        bool
	malformedItem bool
}

func (f *fixture) connect(t *testing.T) *Client {
	t.Helper()
	up := websocket.Upgrader{}
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, e := up.Upgrade(w, r, nil)
		if e != nil {
			return
		}
		defer c.Close()
		if c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}}) != nil {
			return
		}
		var identify any
		if c.ReadJSON(&identify) != nil {
			return
		}
		if c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
			return
		}
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
			code := 100
			switch q.D.Type {
			case "GetStreamStatus":
				if f.hang {
					continue
				}
				if f.active {
					f.bytes += 1024
				}
				data = map[string]any{"outputActive": f.active, "outputReconnecting": false, "outputBytes": f.bytes, "outputDuration": 1000}
				if f.unknown {
					delete(data, "outputActive")
				}
			case "StartStream":
				f.starts.Add(1)
				f.active = true
			case "StopStream":
				f.stops.Add(1)
				f.active = false
			case "GetRecordStatus":
				data = map[string]any{"outputActive": false, "outputPaused": false}
			case "GetReplayBufferStatus":
				data = map[string]any{"outputActive": false}
			case "GetVirtualCamStatus":
				data = map[string]any{"outputActive": f.camera}
			case "StartVirtualCam":
				f.camera = true
			case "StopVirtualCam":
				f.camera = false
			case "GetProfileList":
				data = map[string]any{"currentProfileName": "Gaming", "profiles": []string{"Gaming"}}
			case "GetSceneCollectionList":
				data = map[string]any{"currentSceneCollectionName": "Games", "sceneCollections": []string{"Games"}}
			case "GetSceneList":
				data = map[string]any{"currentProgramSceneName": "Live", "scenes": []any{map[string]any{"sceneName": "Live"}}}
			case "SetStreamServiceSettings":
				if f.reject {
					code = 600
				} else {
					settings, _ := q.D.Data["streamServiceSettings"].(map[string]any)
					f.server, _ = settings["server"].(string)
					f.key, _ = settings["key"].(string)
				}
			case "GetStreamServiceSettings":
				data = map[string]any{"streamServiceType": "rtmp_custom", "streamServiceSettings": map[string]any{"server": f.server, "key": f.key}}
			case "GetSceneItemList":
				item := map[string]any{"sceneItemId": 1, "sourceName": "Game", "sceneItemEnabled": false}
				if f.malformedItem {
					delete(item, "sceneItemEnabled")
				}
				data = map[string]any{"sceneItems": []any{item}}
			default:
				code = 204
			}
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code, "comment": "server-echo-secret-key"}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(s.Close)
	c, e := Connect(context.Background(), Connection{Address: strings.TrimPrefix(s.URL, "http://"), OperationTimeout: 2 * time.Second})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c
}
func TestImportableConfirmedStreamLifecycle(t *testing.T) {
	f := &fixture{}
	c := f.connect(t)
	ctx := context.Background()
	a := Approval{Streaming: true}
	if _, e := c.StartStream(ctx, Approval{}); e == nil {
		t.Fatal("unapproved start accepted")
	}
	if f.starts.Load() != 0 {
		t.Fatal("unapproved command reached OBS")
	}
	for range 2 {
		s, e := c.StartStream(ctx, a)
		if e != nil || !s.Active || s.Reconnecting || s.Bytes <= 0 {
			t.Fatalf("start: %+v %v", s, e)
		}
	}
	state, e := c.Snapshot(ctx)
	if e != nil || state.Profile != "Gaming" || !state.Stream.Active || state.ProviderReception != "unknown" {
		t.Fatalf("snapshot: %+v %v", state, e)
	}
	for range 2 {
		s, e := c.StopStream(ctx, a)
		if e != nil || s.Active {
			t.Fatalf("stop: %+v %v", s, e)
		}
	}
	if f.starts.Load() != 1 || f.stops.Load() != 1 {
		t.Fatal("idempotent operations duplicated output commands")
	}
	if e = c.Close(); e != nil {
		t.Fatal(e)
	}
	if e = c.Close(); e != nil {
		t.Fatal(e)
	}
	if _, e = c.StreamStatus(ctx); e == nil {
		t.Fatal("closed client reused")
	}
}
func TestUnknownOutputCannotAuthorizeMutation(t *testing.T) {
	f := &fixture{unknown: true}
	c := f.connect(t)
	if _, e := c.StartStream(context.Background(), Approval{Streaming: true}); e == nil {
		t.Fatal("unknown output accepted")
	}
	if e := c.ConfigureService(context.Background(), RTMPService{Server: "rtmps://example.invalid/app", Key: "key"}, Approval{Settings: true}); e == nil {
		t.Fatal("unknown output allowed service mutation")
	}
	if f.starts.Load() != 0 {
		t.Fatal("unknown state started stream")
	}
}
func TestRequestFailureRedactsServerAndInputs(t *testing.T) {
	f := &fixture{reject: true}
	c := f.connect(t)
	e := c.ConfigureService(context.Background(), RTMPService{Server: "rtmps://private-endpoint.invalid/app", Key: "server-echo-secret-key"}, Approval{Settings: true})
	var failure *Error
	if !errors.As(e, &failure) || failure.Code != OBSRequest || failure.OBSCode != 600 {
		t.Fatalf("typed failure: %v", e)
	}
	b, _ := json.Marshal(NewResponse("service.configure-rtmp", nil, e))
	for _, value := range []string{string(b), fmt.Sprintf("%+v %#v", e, e)} {
		if strings.Contains(value, "server-echo-secret-key") || strings.Contains(value, "private-endpoint") {
			t.Fatal("secret escaped")
		}
	}
}
func TestCancellationClosesAcquiredConnection(t *testing.T) {
	f := &fixture{hang: true}
	c := f.connect(t)
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	defer cancel()
	_, e := c.StreamStatus(ctx)
	if !errors.Is(e, context.DeadlineExceeded) {
		t.Fatalf("cancellation identity lost: %v", e)
	}
	if !c.closed.Load() {
		t.Fatal("timed-out transport was reusable")
	}
}

type blockingBackend struct {
	backend
	entered chan struct{}
	release chan struct{}
	closes  atomic.Int32
}

func (b *blockingBackend) StreamStatus(ctx context.Context) (automation.StreamStatus, error) {
	close(b.entered)
	select {
	case <-b.release:
		return automation.StreamStatus{}, nil
	case <-ctx.Done():
		return automation.StreamStatus{}, ctx.Err()
	}
}
func (b *blockingBackend) Close() error { b.closes.Add(1); return nil }
func TestWaitingCancellationDoesNotInterruptOwner(t *testing.T) {
	b := &blockingBackend{entered: make(chan struct{}), release: make(chan struct{})}
	c := newClient(b, time.Second)
	defer c.Close()
	done := make(chan error, 1)
	go func() { _, e := c.StreamStatus(context.Background()); done <- e }()
	<-b.entered
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	_, e := c.StreamStatus(ctx)
	if !errors.Is(e, context.DeadlineExceeded) || b.closes.Load() != 0 {
		t.Fatal("waiting cancellation interrupted owned operation")
	}
	close(b.release)
	if e = <-done; e != nil {
		t.Fatal(e)
	}
}
func TestSecretFormattingAndDomainErrorContract(t *testing.T) {
	c := Connection{Address: "localhost:4455", Password: "private-password"}
	s := RTMPService{Server: "rtmps://private.invalid/key", Key: "private-password"}
	for _, value := range []any{c, s} {
		b, _ := json.Marshal(value)
		printed := fmt.Sprintf("%v %+v %#v", value, value, value)
		if strings.Contains(string(b), "private") || strings.Contains(printed, "private") {
			t.Fatal("secret formatting escaped")
		}
	}
	e := Failure("secret-operation", errors.New("private-password"))
	if e.Operation != "request" || strings.Contains(e.Error(), "private") {
		t.Fatal("arbitrary failure escaped")
	}
	if ExitCode(nil) != 0 || ExitCode(e) != 1 {
		t.Fatal("exit code compatibility")
	}
	if _, e := Connect(context.Background(), Connection{Address: "bad-private-secret"}); e == nil || strings.Contains(e.Error(), "bad-private") {
		t.Fatal("invalid endpoint escaped")
	}
}

func TestServiceReadbackAndVirtualCameraConfirmation(t *testing.T) {
	f := &fixture{}
	c := f.connect(t)
	ctx := context.Background()
	s := RTMPService{Server: "rtmps://example.invalid/app", Key: "private-service-key"}
	if e := c.ConfigureService(ctx, s, Approval{Settings: true}); e != nil {
		t.Fatal(e)
	}
	if e := c.VerifyService(ctx, s); e != nil {
		t.Fatal(e)
	}
	s.Key = "different-key"
	e := c.VerifyService(ctx, s)
	var failure *Error
	if !errors.As(e, &failure) || failure.Code != Conflict {
		t.Fatalf("wrong destination not conflict: %v", e)
	}
	for range 2 {
		if e = c.SetVirtualCamera(ctx, true, Approval{VirtualCamera: true}); e != nil {
			t.Fatal(e)
		}
	}
	state, e := c.Snapshot(ctx)
	if e != nil || !state.VirtualCameraActive {
		t.Fatalf("camera observation: %+v %v", state, e)
	}
	if e = c.ConfigureService(ctx, s, Approval{Settings: true}); !errors.As(e, &failure) || failure.Code != Conflict {
		t.Fatalf("active camera allowed settings: %v", e)
	}
	if e = c.SetVirtualCamera(ctx, false, Approval{VirtualCamera: true}); e != nil {
		t.Fatal(e)
	}
}
func TestMalformedSceneItemDoesNotBecomeConfirmedHidden(t *testing.T) {
	f := &fixture{malformedItem: true}
	c := f.connect(t)
	if _, e := c.SceneItems(context.Background(), "Live"); e == nil {
		t.Fatal("unknown scene visibility became false")
	}
}

type failedBackend struct {
	backend
	value  automation.StreamStatus
	err    error
	closes atomic.Int32
}

func (b *failedBackend) StreamStatus(context.Context) (automation.StreamStatus, error) {
	return b.value, b.err
}
func (b *failedBackend) Close() error { b.closes.Add(1); return nil }
func TestInnerDeadlineClosesConnectionAndMetricsStayJSONSafe(t *testing.T) {
	b := &failedBackend{err: context.DeadlineExceeded}
	c := newClient(b, time.Second)
	_, e := c.StreamStatus(context.Background())
	if !errors.Is(e, context.DeadlineExceeded) || b.closes.Load() != 1 {
		t.Fatalf("inner deadline reused transport: %v", e)
	}
	b = &failedBackend{value: automation.StreamStatus{Bytes: math.NaN()}}
	c = newClient(b, time.Second)
	defer c.Close()
	_, e = c.StreamStatus(context.Background())
	if e == nil {
		t.Fatal("nonfinite metrics escaped typed JSON")
	}
	response, err := json.Marshal(NewResponse("snapshot", nil, e))
	if err != nil || !json.Valid(response) {
		t.Fatalf("failure JSON invalid: %s %v", response, err)
	}
}
