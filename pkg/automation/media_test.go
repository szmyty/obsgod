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

type mediaProtocolFixture struct {
	mu                               sync.Mutex
	record, replay                   bool
	malformedRecord, malformedReplay any
	replayUnavailable                bool
	requests                         []string
	starts, stops, saves, savePolls  int
	pendingStart, pendingStop        bool
	replayPolls                      int
	savedPath                        string
	pendingSave                      bool
}

func (f *mediaProtocolFixture) dial(t *testing.T) *Client {
	t.Helper()
	upgrader := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, e := upgrader.Upgrade(w, r, nil)
		if e != nil {
			return
		}
		defer conn.Close()
		_ = conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}})
		var identify any
		if conn.ReadJSON(&identify) != nil {
			return
		}
		_ = conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				Op int `json:"op"`
				D  struct {
					Type string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if conn.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			f.requests = append(f.requests, q.D.Type)
			code := 100
			data := map[string]any{}
			switch q.D.Type {
			case "GetRecordStatus":
				if f.malformedRecord != nil {
					data["outputActive"] = f.malformedRecord
				} else {
					data["outputActive"] = f.record
				}
				data["outputBytes"] = 4096
				data["outputPaused"] = false
				data["outputDuration"] = 1000
			case "GetReplayBufferStatus":
				f.replayPolls++
				if f.pendingStart && f.replayPolls >= 3 {
					f.replay = true
					f.pendingStart = false
				}
				if f.pendingStop && f.replayPolls >= 3 {
					f.replay = false
					f.pendingStop = false
				}
				if f.replayUnavailable {
					code = 604
				} else if f.malformedReplay != nil {
					data["outputActive"] = f.malformedReplay
				} else {
					data["outputActive"] = f.replay
				}
			case "StartReplayBuffer":
				f.starts++
				f.replayPolls = 0
				f.pendingStart = true
			case "StopReplayBuffer":
				f.stops++
				f.replayPolls = 0
				f.pendingStop = true
			case "GetLastReplayBufferReplay":
				if f.pendingSave {
					f.savePolls++
					if f.savePolls >= 3 {
						f.savedPath = "/fixture/new-replay.mkv"
						f.pendingSave = false
					}
				}
				data["savedReplayPath"] = f.savedPath
			case "SaveReplayBuffer":
				f.saves++
				f.pendingSave = true
				f.savePolls = 0
			case "SetRecordDirectory", "SetProfileParameter":
			default:
				code = 204
			}
			f.mu.Unlock()
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	client, e := Connect(ctx, Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client
}
func TestReplayLifecycleWaitsAndNeverBroadcasts(t *testing.T) {
	fixture := &mediaProtocolFixture{savedPath: "/fixture/old-replay.mkv"}
	client := fixture.dial(t)
	ctx, cancel := context.WithTimeout(context.Background(), 4*time.Second)
	defer cancel()
	if e := client.StartReplay(ctx); e != nil {
		t.Fatal(e)
	}
	if e := client.StartReplay(ctx); e != nil {
		t.Fatal(e)
	}
	path, e := client.SaveReplay(ctx)
	if e != nil || path != "/fixture/new-replay.mkv" {
		t.Fatal(path, e)
	}
	if e = client.StopReplay(ctx); e != nil {
		t.Fatal(e)
	}
	if e = client.StopReplay(ctx); e != nil {
		t.Fatal(e)
	}
	fixture.mu.Lock()
	defer fixture.mu.Unlock()
	if fixture.starts != 1 || fixture.stops != 1 || fixture.saves != 1 || fixture.savePolls < 3 {
		t.Fatalf("lifecycle not confirmed/idempotent: %+v", fixture)
	}
	for _, request := range fixture.requests {
		if strings.Contains(request, "Stream") {
			t.Fatal("local replay touched a stream operation", request)
		}
	}
}
func TestReplaySaveRequiresActiveBuffer(t *testing.T) {
	fixture := &mediaProtocolFixture{}
	client := fixture.dial(t)
	if _, e := client.SaveReplay(context.Background()); e == nil {
		t.Fatal("saved an inactive buffer")
	}
	fixture.mu.Lock()
	defer fixture.mu.Unlock()
	if fixture.saves != 0 {
		t.Fatal("requested save of inactive buffer")
	}
}
func TestMediaStatusRejectsMalformedSuccessfulBools(t *testing.T) {
	for _, kind := range []string{"record", "replay"} {
		for _, value := range []any{"false", float64(0), json.RawMessage(`null`)} {
			t.Run(kind+"-"+stringMustMarshal(value), func(t *testing.T) {
				f := &mediaProtocolFixture{}
				if kind == "record" {
					f.malformedRecord = value
				} else {
					f.malformedReplay = value
				}
				c := f.dial(t)
				if _, e := c.MediaStatus(context.Background()); e == nil {
					t.Fatal("malformed state became confirmed idle")
				}
			})
		}
	}
}
func stringMustMarshal(v any) string { b, _ := json.Marshal(v); return string(b) }
func TestUnavailableUnconfiguredReplayIsNotActive(t *testing.T) {
	f := &mediaProtocolFixture{replayUnavailable: true}
	c := f.dial(t)
	active, e := c.ReplayActive(context.Background())
	if e != nil || active {
		t.Fatal(active, e)
	}
}
func TestMediaProfileMutationRefusesActiveLocalOutput(t *testing.T) {
	for _, record := range []bool{false, true} {
		f := &mediaProtocolFixture{record: record, replay: !record}
		c := f.dial(t)
		if e := c.ConfigureMediaProfile(context.Background(), "/fixture/recordings", 60, 256); e == nil {
			t.Fatal("changed active output preferences")
		}
		f.mu.Lock()
		for _, q := range f.requests {
			if strings.HasPrefix(q, "Set") {
				t.Fatal("mutated settings", q)
			}
		}
		f.mu.Unlock()
	}
}
func TestMediaProfileOnlyChangesLocalSettings(t *testing.T) {
	f := &mediaProtocolFixture{}
	c := f.dial(t)
	if e := c.ConfigureMediaProfile(context.Background(), "/fixture/recordings", 60, 256); e != nil {
		t.Fatal(e)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, q := range f.requests {
		if strings.Contains(q, "Stream") || strings.Contains(q, "Input") || strings.Contains(q, "Scene") {
			t.Fatal("changed unrelated output settings", q)
		}
	}
}
