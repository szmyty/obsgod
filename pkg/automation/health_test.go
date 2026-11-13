package automation

import (
	"context"
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

func TestHealthRawFieldsPreserveUnknownAndMeasuredZero(t *testing.T) {
	stats, err := decodeHealthStats([]byte(`{"cpuUsage":0,"activeFps":30,"averageFrameRenderTime":-3,"server":"secret-must-not-escape"}`))
	if err != nil || stats.CPUPercent == nil || *stats.CPUPercent != 0 || stats.FPS == nil || *stats.FPS != 30 || stats.FrameRenderMS != nil || stats.EncodeTotal != nil {
		t.Fatalf("missing metrics became zero or invalid metrics survived: %+v %v", stats, err)
	}
	stream, err := decodeHealthStream([]byte(`{"outputActive":false,"outputBytes":0}`))
	if err != nil || stream.Active == nil || *stream.Active || stream.Bytes == nil || *stream.Bytes != 0 || stream.Reconnecting != nil || stream.DurationMS != nil {
		t.Fatalf("missing stream fields became observed: %+v %v", stream, err)
	}
	encoded, _ := json.Marshal(stats)
	if strings.Contains(string(encoded), "secret") || strings.Contains(string(encoded), "server") {
		t.Fatal("unexpected health field escaped")
	}
	for _, data := range []string{`{"cpuUsage":"secret"}`, `{"cpuUsage":1e999}`, `[` + strings.Repeat(" ", 65536) + `]`} {
		_, err := decodeHealthStats([]byte(data))
		if err == nil || strings.Contains(err.Error(), "secret") {
			t.Fatal("malformed statistics were accepted or leaked", err)
		}
	}
	if _, err := decodeHealthStream([]byte(`{"outputActive":"password"}`)); err == nil || strings.Contains(err.Error(), "password") {
		t.Fatal("malformed stream status leaked", err)
	}
}

func TestHealthObservationProtocolReadOnlyAndSanitizedFailure(t *testing.T) {
	var mu sync.Mutex
	var calls []string
	reject := false
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		_ = conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}})
		var identify map[string]any
		if conn.ReadJSON(&identify) != nil {
			return
		}
		_ = conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var query struct {
				D struct {
					Type string `json:"requestType"`
					ID   string `json:"requestId"`
				} `json:"d"`
			}
			if conn.ReadJSON(&query) != nil {
				return
			}
			mu.Lock()
			calls = append(calls, query.D.Type)
			failed := reject
			mu.Unlock()
			code, comment := 100, ""
			data := map[string]any{}
			switch query.D.Type {
			case "GetStats":
				data = map[string]any{"cpuUsage": 7.5, "activeFps": 30, "outputSkippedFrames": 2, "outputTotalFrames": 90, "renderSkippedFrames": 1, "renderTotalFrames": 90}
			case "GetStreamStatus":
				data = map[string]any{"outputActive": true, "outputReconnecting": false, "outputBytes": 10000, "outputDuration": 3000, "outputSkippedFrames": 0, "outputTotalFrames": 90}
			default:
				code = 204
			}
			if failed {
				code, comment = 600, "secret-stream-key-must-not-escape"
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": query.D.Type, "requestId": query.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code, "comment": comment}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	server.Config.ErrorLog = log.New(io.Discard, "", 0)
	defer server.Close()
	c, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: 300 * time.Millisecond})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	observation, err := c.HealthObservation(context.Background())
	if err != nil || observation.Stream.Active == nil || !*observation.Stream.Active || observation.Stats.CPUPercent == nil || *observation.Stats.CPUPercent != 7.5 || observation.ObservedAt.IsZero() {
		t.Fatalf("protocol data missing: %+v %v", observation, err)
	}
	mu.Lock()
	observedCalls := append([]string{}, calls...)
	reject = true
	mu.Unlock()
	if strings.Join(observedCalls, ",") != "GetStats,GetStreamStatus" {
		t.Fatalf("health made a non-read-only request: %v", observedCalls)
	}
	if _, err := c.HealthObservation(context.Background()); err == nil || strings.Contains(err.Error(), "secret-stream-key") {
		t.Fatal("untrusted server failure leaked", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := c.HealthObservation(ctx); err != context.Canceled {
		t.Fatal("health ignored cancellation", err)
	}
}
