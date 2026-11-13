package automation

import (
	"context"
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

func TestStreamUnknownFlagsCannotAuthorizeLifecycle(t *testing.T) {
	cases := []struct {
		name string
		data map[string]any
	}{
		{"empty", map[string]any{}},
		{"missing-active", map[string]any{"outputReconnecting": false}},
		{"missing-reconnecting", map[string]any{"outputActive": false}},
		{"null-active", map[string]any{"outputActive": nil, "outputReconnecting": false}},
		{"null-reconnecting", map[string]any{"outputActive": true, "outputReconnecting": nil}},
		{"string-active", map[string]any{"outputActive": "true", "outputReconnecting": false}},
		{"number-active", map[string]any{"outputActive": 0, "outputReconnecting": false}},
		{"object-active", map[string]any{"outputActive": map[string]any{}, "outputReconnecting": false}},
		{"string-reconnecting", map[string]any{"outputActive": true, "outputReconnecting": "false"}},
		{"number-reconnecting", map[string]any{"outputActive": false, "outputReconnecting": 0}},
		{"object-reconnecting", map[string]any{"outputActive": true, "outputReconnecting": map[string]any{}}},
	}
	for _, fixture := range cases {
		t.Run(fixture.name, func(t *testing.T) {
			var mu sync.Mutex
			var calls []string
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
					mu.Lock()
					calls = append(calls, query.D.Type)
					mu.Unlock()
					data := map[string]any{}
					if query.D.Type == "GetStreamStatus" {
						for key, value := range fixture.data {
							data[key] = value
						}
						data["private-echo"] = "stream-key-must-not-escape"
					}
					if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": query.D.Type, "requestId": query.D.ID,
						"requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
						return
					}
				}
			}))
			server.Config.ErrorLog = log.New(io.Discard, "", 0)
			defer server.Close()
			client, err := Connect(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: 200 * time.Millisecond})
			if err != nil {
				t.Fatal(err)
			}
			defer client.Close()
			for _, operation := range []struct {
				name string
				call func(context.Context) (StreamStatus, error)
			}{{"status", client.StreamStatus}, {"start", client.StartStream}, {"stop", client.StopStream}} {
				ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
				_, err := operation.call(ctx)
				cancel()
				if err == nil {
					t.Errorf("%s accepted malformed output flags as confirmed state", operation.name)
				} else if strings.Contains(err.Error(), "stream-key-must-not-escape") || strings.Contains(err.Error(), "private-echo") {
					t.Errorf("%s exposed untrusted response data", operation.name)
				}
			}
			mu.Lock()
			observedCalls := append([]string{}, calls...)
			mu.Unlock()
			if strings.Join(observedCalls, ",") != "GetStreamStatus,GetStreamStatus,GetStreamStatus" {
				t.Fatalf("unknown stream status caused lifecycle requests: %v", observedCalls)
			}
		})
	}
}
