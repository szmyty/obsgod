package automation

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
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
	mu             sync.Mutex
	active         bool
	bytes          float64
	starts, stops  int
	rejectSettings bool
	hangStatus     bool
	authed         bool
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
	if strings.Contains(e.Error(), "incorrect") {
		t.Fatal("password echoed")
	}
}
