package commands

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/internal/config"
	api "github.com/szmyty/obsgod/pkg/api/v1"
)

func TestPublicProfileListKeepsJSONShapeWithOnlyProfileRead(t *testing.T) {
	for _, names := range [][]string{{"Gaming Profile", "Second", "Gaming Profile"}, {}} {
		requestType := make(chan string, 2)
		closed := make(chan struct{})
		upgrader := websocket.Upgrader{}
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			conn, err := upgrader.Upgrade(w, r, nil)
			if err != nil {
				return
			}
			defer conn.Close()
			defer close(closed)
			if conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}}) != nil {
				return
			}
			var identify any
			if conn.ReadJSON(&identify) != nil || conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
				return
			}
			var request struct {
				D struct {
					Type string `json:"requestType"`
					ID   string `json:"requestId"`
				} `json:"d"`
			}
			if conn.ReadJSON(&request) != nil {
				return
			}
			requestType <- request.D.Type
			code := 204
			if request.D.Type == "GetProfileList" {
				code = 100
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": request.D.Type, "requestId": request.D.ID,
				"requestStatus": map[string]any{"result": code == 100, "code": code},
				"responseData":  map[string]any{"currentProfileName": "Gaming Profile", "profiles": names}}}) != nil {
				return
			}
			// The command owns this client. Any subsequent request or leaked
			// connection prevents the close observation below from succeeding.
			var next any
			if conn.ReadJSON(&next) == nil {
				requestType <- "unexpected second request"
			}
		}))
		defer server.Close()
		cfg := config.Default()
		command := newAPICommand(&cfg, new(string), func(ctx context.Context, _ config.Config) (*api.Client, error) {
			return api.Connect(ctx, api.Connection{Address: strings.TrimPrefix(server.URL, "http://")})
		})
		var out bytes.Buffer
		command.SetOut(&out)
		command.SetArgs([]string{"profile", "list"})
		if err := command.Execute(); err != nil {
			t.Fatal(err)
		}
		wantNames := `["Gaming Profile","Second","Gaming Profile"]`
		if len(names) == 0 {
			wantNames = `[]`
		}
		want := `{"schema_version":1,"ok":true,"operation":"snapshot","result":` + wantNames + "}\n"
		if out.String() != want {
			t.Fatalf("profile-list JSON changed: got %q want %q", out.String(), want)
		}
		if got := <-requestType; got != "GetProfileList" {
			t.Fatalf("profile list queried unrelated output: %s", got)
		}
		select {
		case <-closed:
		case <-time.After(time.Second):
			t.Fatal("profile-list command did not release its connection")
		}
		select {
		case got := <-requestType:
			t.Fatalf("profile list sent another request: %s", got)
		default:
		}
	}
}
