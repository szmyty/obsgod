package automation

import (
	"context"
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

type streamProgressFixture struct {
	mu            sync.Mutex
	samples       []StreamStatus
	reads, starts int
	stops         int
}

func (fixture *streamProgressFixture) dial(t *testing.T) *Client {
	t.Helper()
	upgrader := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		conn, err := upgrader.Upgrade(writer, request, nil)
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
			fixture.mu.Lock()
			data := map[string]any{}
			code := 100
			switch query.D.Type {
			case "GetStreamStatus":
				index := fixture.reads
				if index >= len(fixture.samples) {
					index = len(fixture.samples) - 1
				}
				sample := fixture.samples[index]
				fixture.reads++
				data = map[string]any{"outputActive": sample.Active, "outputReconnecting": sample.Reconnecting, "outputBytes": sample.Bytes,
					"outputDuration": sample.Duration, "outputTotalFrames": 0, "outputSkippedFrames": 0}
			case "StartStream":
				fixture.starts++
			case "StopStream":
				fixture.stops++
			default:
				code = 204
			}
			fixture.mu.Unlock()
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": query.D.Type, "requestId": query.D.ID,
				"requestStatus": map[string]any{"result": code == 100, "code": code}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	server.Config.ErrorLog = log.New(io.Discard, "", 0)
	t.Cleanup(server.Close)
	client, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: 200 * time.Millisecond})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client
}

func TestStreamStartUsesFreshActiveEpochInsteadOfStoppedCounters(t *testing.T) {
	fixture := &streamProgressFixture{samples: []StreamStatus{
		{Active: false, Bytes: 1e12, Duration: 1e9}, // OBS retained the prior broadcast's counters.
		{Active: true, Bytes: 0, Duration: 0},
		{Active: true, Bytes: 4096, Duration: 400},
	}}
	client := fixture.dial(t)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	started := time.Now()
	status, err := client.StartStream(ctx)
	if err != nil || !status.Active || status.Bytes != 4096 {
		t.Fatalf("new output used stopped counters as baseline: %+v %v", status, err)
	}
	if elapsed := time.Since(started); elapsed > 1500*time.Millisecond {
		t.Fatal("fresh advancing output waited against the previous broadcast", elapsed)
	}
	fixture.mu.Lock()
	defer fixture.mu.Unlock()
	if fixture.starts != 1 || fixture.stops != 0 || fixture.reads != 3 {
		t.Fatalf("wrong new-output lifecycle: starts=%d stops=%d reads=%d", fixture.starts, fixture.stops, fixture.reads)
	}
}

func TestStreamStartRequiresConsecutiveProgressAfterResetOrReconnection(t *testing.T) {
	active := func(bytes, duration float64) StreamStatus {
		return StreamStatus{Active: true, Bytes: bytes, Duration: duration}
	}
	cases := []struct {
		name    string
		samples []StreamStatus
		reads   int
	}{
		{"already-active-idempotent", []StreamStatus{active(9000, 9000), active(9001, 9400)}, 2},
		{"byte-reset", []StreamStatus{active(9000, 9000), active(10, 9400), active(11, 9800)}, 3},
		{"duration-reset", []StreamStatus{active(9000, 9000), active(10000, 0), active(10001, 400)}, 3},
		{"reconnecting", []StreamStatus{active(9000, 9000), {Active: true, Reconnecting: true, Bytes: 10000, Duration: 9400}, active(12000, 9800), active(12001, 10200)}, 4},
		{"inactive", []StreamStatus{active(9000, 9000), {Active: false, Bytes: 10000, Duration: 9400}, active(12000, 0), active(12001, 400)}, 4},
		{"duration-reset-after-stalled-bytes", []StreamStatus{active(9000, 100), active(9000, 1000), active(10000, 500), active(10001, 900)}, 4},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			fixture := &streamProgressFixture{samples: test.samples}
			client := fixture.dial(t)
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			status, err := client.StartStream(ctx)
			if err != nil || !status.Active || status.Reconnecting {
				t.Fatalf("fresh pair was not confirmed: %+v %v", status, err)
			}
			fixture.mu.Lock()
			defer fixture.mu.Unlock()
			if fixture.starts != 0 || fixture.stops != 0 || fixture.reads != test.reads {
				t.Fatalf("stale pair authorized confirmation or changed existing lifecycle: starts=%d stops=%d reads=%d expected=%d", fixture.starts, fixture.stops, fixture.reads, test.reads)
			}
		})
	}
}

func TestStreamStartNeverConfirmsConstantNonzeroBytesOrStaleRecoveryPairs(t *testing.T) {
	active := func(bytes, duration float64) StreamStatus {
		return StreamStatus{Active: true, Bytes: bytes, Duration: duration}
	}
	cases := []struct {
		name    string
		samples []StreamStatus
		starts  int
	}{
		{"new-output-constant-nonzero", []StreamStatus{{Active: false, Bytes: 0}, active(4096, 400)}, 1},
		{"duration-reset-with-no-new-progress", []StreamStatus{active(9000, 9000), active(10000, 0)}, 0},
		{"reconnecting-then-stale-bytes", []StreamStatus{active(9000, 9000), {Active: true, Reconnecting: true, Bytes: 10000, Duration: 9400}, active(12000, 9800)}, 0},
		{"inactive-then-stale-bytes", []StreamStatus{active(9000, 9000), {Active: false, Bytes: 10000, Duration: 9400}, active(12000, 0)}, 0},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			fixture := &streamProgressFixture{samples: test.samples}
			client := fixture.dial(t)
			ctx, cancel := context.WithTimeout(context.Background(), 950*time.Millisecond)
			defer cancel()
			if _, err := client.StartStream(ctx); !errors.Is(err, context.DeadlineExceeded) {
				t.Fatal("constant/stale output bytes became successful progress", err)
			}
			fixture.mu.Lock()
			defer fixture.mu.Unlock()
			if fixture.starts != test.starts || fixture.stops != 0 {
				t.Fatalf("failed confirmation changed output unexpectedly: starts=%d stops=%d", fixture.starts, fixture.stops)
			}
		})
	}
}
