package automation

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

type fakeOBS struct {
	mu              sync.Mutex
	active          bool
	bytes           float64
	starts, stops   int
	rejectSettings  bool
	hangStatus      bool
	authed          bool
	recording       bool
	recordStopping  bool
	recordStops     int
	recordStopPolls int
}

func (f *fakeOBS) server(t *testing.T) *httptest.Server {
	t.Helper()
	up := websocket.Upgrader{}
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, e := up.Upgrade(w, r, nil)
		if e != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0", "authentication": map[string]any{"challenge": "challenge", "salt": "salt"}}})
		var identify struct {
			Op int `json:"op"`
			D  struct {
				Authentication string `json:"authentication"`
			} `json:"d"`
		}
		if c.ReadJSON(&identify) != nil {
			return
		}
		a := sha256.Sum256([]byte("private-password" + "salt"))
		b := sha256.Sum256([]byte(base64.StdEncoding.EncodeToString(a[:]) + "challenge"))
		if identify.Op != 1 || identify.D.Authentication != base64.StdEncoding.EncodeToString(b[:]) {
			_ = c.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(4009, "Authentication failed"), time.Now().Add(time.Second))
			return
		}
		f.mu.Lock()
		f.authed = true
		f.mu.Unlock()
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				Op int `json:"op"`
				D  struct {
					Type string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			code := 100
			comment := ""
			data := map[string]any{}
			switch q.D.Type {
			case "GetStreamStatus":
				if f.hangStatus {
					f.mu.Unlock()
					continue
				}
				if f.active {
					f.bytes += 4096
				}
				data = map[string]any{"outputActive": f.active, "outputReconnecting": false, "outputBytes": f.bytes, "outputDuration": 1000, "outputTotalFrames": 30, "outputSkippedFrames": 0}
			case "StartStream":
				f.starts++
				f.active = true
			case "StopStream":
				f.stops++
				f.active = false
			case "GetRecordStatus":
				if f.recordStopping {
					if f.recordStopPolls > 0 {
						f.recordStopPolls--
					} else {
						f.recording = false
					}
				}
				data = map[string]any{"outputActive": f.recording, "outputBytes": 4096}
			case "StopRecord":
				f.recordStops++
				f.recordStopping = true
				data = map[string]any{"outputPath": "/fixture/finalized-recording.mkv"}

			case "SetStreamServiceSettings":
				if f.rejectSettings {
					code = 600
					comment = "server echoed stream-key-must-not-escape"
				}
			default:
				code = 204
			}
			f.mu.Unlock()
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code, "comment": comment}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	s.Config.ErrorLog = log.New(io.Discard, "", 0)
	t.Cleanup(s.Close)
	return s
}
func dialFixture(t *testing.T, f *fakeOBS) *Client {
	t.Helper()
	s := f.server(t)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	c, e := Connect(ctx, Config{Address: strings.TrimPrefix(s.URL, "http://"), Password: "private-password", Timeout: 200 * time.Millisecond})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c
}

func TestAuthenticatedIdempotentStreamLifecycle(t *testing.T) {
	f := &fakeOBS{}
	c := dialFixture(t, f)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	for i := 0; i < 2; i++ {
		s, e := c.StartStream(ctx)
		if e != nil || !s.Active || s.Bytes <= 0 {
			t.Fatalf("start: %+v %v", s, e)
		}
	}
	for i := 0; i < 2; i++ {
		s, e := c.StopStream(ctx)
		if e != nil || s.Active {
			t.Fatalf("stop: %+v %v", s, e)
		}
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if !f.authed || f.starts != 1 || f.stops != 1 {
		t.Fatalf("wrong lifecycle auth=%v starts=%d stops=%d", f.authed, f.starts, f.stops)
	}
}

func TestServerErrorsCannotEchoCredentials(t *testing.T) {
	t.Setenv("GOOBS_LOG", "TRACE")
	c := dialFixture(t, &fakeOBS{rejectSettings: true})
	e := c.ConfigureRTMP(context.Background(), "rtmps://example.invalid/app", "stream-key-must-not-escape")
	if e == nil || strings.Contains(e.Error(), "stream-key-must-not-escape") {
		t.Fatalf("unsafe error: %v", e)
	}
	b, _ := json.Marshal(e.Error())
	if strings.Contains(string(b), "private-password") {
		t.Fatal("password leaked")
	}
}

func TestCancellationAndAuthenticationFailure(t *testing.T) {
	c := dialFixture(t, &fakeOBS{hangStatus: true})
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	start := time.Now()
	if _, e := c.StreamStatus(ctx); e != context.DeadlineExceeded {
		t.Fatalf("expected cancellation, got %v", e)
	}
	if time.Since(start) > 150*time.Millisecond {
		t.Fatal("request ignored cancellation")
	}
	f := &fakeOBS{}
	s := f.server(t)
	bad, e := Connect(context.Background(), Config{Address: strings.TrimPrefix(s.URL, "http://"), Password: "incorrect", Timeout: 100 * time.Millisecond})
	if bad != nil || e == nil {
		t.Fatal("incorrect authentication accepted")
	}
	var connectionError *ConnectionError
	if !errors.As(e, &connectionError) || connectionError.Kind != "authentication" {
		t.Fatalf("authentication stage missing: %v", e)
	}
	if strings.Contains(e.Error(), "incorrect") {
		t.Fatal("password echoed")
	}
}

func TestSilentAuthenticationIsBoundedAndClosesTheTransport(t *testing.T) {
	closed := make(chan struct{})
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		// Deliberately never send Hello. The client must bound authentication,
		// release this upgraded socket and avoid retaining the transport on failure.
		_, _, _ = conn.ReadMessage()
		close(closed)
	}))
	defer server.Close()
	start := time.Now()
	client, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Password: "do-not-echo-this", Timeout: 60 * time.Millisecond})
	var connectionError *ConnectionError
	if client != nil || !errors.As(err, &connectionError) || connectionError.Kind != "timeout" {
		t.Fatalf("incorrect timeout classification: %v", err)
	}
	if time.Since(start) > 300*time.Millisecond {
		t.Fatal("connection timeout did not bound authentication")
	}
	if strings.Contains(err.Error(), "do-not-echo-this") {
		t.Fatal("connection error disclosed password")
	}
	select {
	case <-closed:
	case <-time.After(time.Second):
		t.Fatal("failed authentication retained transport")
	}
}

func TestConnectionCancellationClosesAnUpgradedTransport(t *testing.T) {
	ready, closed := make(chan struct{}), make(chan struct{})
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		close(ready)
		_, _, _ = conn.ReadMessage()
		close(closed)
	}))
	defer server.Close()
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() {
		_, err := Connect(ctx, Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
		result <- err
	}()
	<-ready
	cancel()
	if err := <-result; err != context.Canceled {
		t.Fatalf("cancellation not preserved: %v", err)
	}
	select {
	case <-closed:
	case <-time.After(time.Second):
		t.Fatal("cancelled connection retained transport")
	}
}

func TestStopRecordingWaitsForConfirmedMuxerShutdown(t *testing.T) {
	f := &fakeOBS{recording: true, recordStopPolls: 3}
	c := dialFixture(t, f)
	start := time.Now()
	path, err := c.StopRecording(context.Background())
	if err != nil || path != "/fixture/finalized-recording.mkv" {
		t.Fatalf("recording shutdown failed: %q %v", path, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.recording || f.recordStops != 1 {
		t.Fatalf("returned before recording stopped: active=%v stops=%d", f.recording, f.recordStops)
	}
	if time.Since(start) < 250*time.Millisecond {
		t.Fatal("returned on StopRecord acknowledgement without waiting for inactive output")
	}
}

func TestStopRecordingCannotClaimSuccessWhenShutdownIsUnconfirmed(t *testing.T) {
	f := &fakeOBS{recording: true, recordStopPolls: 1000}
	c := dialFixture(t, f)
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Millisecond)
	defer cancel()
	path, err := c.StopRecording(ctx)
	if !errors.Is(err, context.DeadlineExceeded) || path != "" {
		t.Fatalf("unconfirmed recording reported success: %q %v", path, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if !f.recording || f.recordStops != 1 {
		t.Fatal("fixture did not exercise asynchronous recording shutdown")
	}
}

func TestConnectionTimeoutClassificationDoesNotDependOnTimerScheduling(t *testing.T) {
	deadline := time.Now()
	// A generic library error arriving at the deadline must be a timeout even
	// before the attempt context's timer goroutine has set Err. No free-form
	// error text is parsed or exposed to make that decision.
	err := errors.New("untrusted-server-data-must-not-affect-classification")
	for _, completedAt := range []time.Time{deadline, deadline.Add(time.Microsecond)} {
		if kind := connectionFailureKind(err, nil, deadline, completedAt); kind != "timeout" {
			t.Fatalf("expired attempt classified as %q", kind)
		}
	}
	if kind := connectionFailureKind(err, nil, deadline, deadline.Add(-time.Microsecond)); kind != "transport" {
		t.Fatalf("early generic failure misclassified as %q", kind)
	}
	if kind := connectionFailureKind(context.DeadlineExceeded, nil, deadline, deadline.Add(-time.Second)); kind != "timeout" {
		t.Fatalf("wrapped context timeout misclassified as %q", kind)
	}
}
