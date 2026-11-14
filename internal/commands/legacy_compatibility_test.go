package commands

import (
	"bytes"
	"context"
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
	"github.com/szmyty/obsgod/internal/obs"
)

type legacyCLIRequest struct {
	Type string
	Data map[string]any
}

func legacyCLIFixture(t *testing.T, response func(legacyCLIRequest) (map[string]any, int)) (config.Config, func() []legacyCLIRequest, <-chan struct{}) {
	t.Helper()
	var mu sync.Mutex
	var requests []legacyCLIRequest
	var clients []*websocket.Conn
	closed := make(chan struct{}, 8)
	upgrader := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		mu.Lock()
		clients = append(clients, conn)
		mu.Unlock()
		defer func() { _ = conn.Close(); closed <- struct{}{} }()
		if conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.2"}}) != nil {
			return
		}
		var identify any
		if conn.ReadJSON(&identify) != nil || conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
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
			req := legacyCLIRequest{wire.D.Type, wire.D.Data}
			mu.Lock()
			requests = append(requests, req)
			mu.Unlock()
			data, code := response(req)
			if code == 0 {
				continue
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": wire.D.Type, "requestId": wire.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code, "comment": "private-stream-key-marker"}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(func() {
		mu.Lock()
		for _, conn := range clients {
			_ = conn.Close()
		}
		mu.Unlock()
		server.Close()
	})
	host, port, err := net.SplitHostPort(strings.TrimPrefix(server.URL, "http://"))
	if err != nil {
		t.Fatal(err)
	}
	number, _ := strconv.Atoi(port)
	return config.Config{Host: host, Port: uint32(number)}, func() []legacyCLIRequest {
		mu.Lock()
		defer mu.Unlock()
		return append([]legacyCLIRequest{}, requests...)
	}, closed
}

func TestLegacyCLIProfileAndStatusOutputSurvivesFacadeMigration(t *testing.T) {
	cases := []struct {
		name     string
		args     []string
		request  string
		response map[string]any
		want     string
	}{
		{"profile order and duplicates", []string{"profile", "list"}, "GetProfileList", map[string]any{"currentProfileName": "Game Profile", "profiles": []string{"Second", "Game Profile", "Second", ""}}, "Second\nGame Profile\nSecond\n\n"},
		{"empty list", []string{"profile", "list"}, "GetProfileList", map[string]any{"currentProfileName": "", "profiles": []string{}}, ""},
		{"current profile", []string{"profile", "get"}, "GetProfileList", map[string]any{"currentProfileName": "Game Profile", "profiles": []string{"Game Profile"}}, "Game Profile\n"},
		{"stream text", []string{"stream", "status"}, "GetStreamStatus", map[string]any{"outputActive": true, "outputTimecode": "12:34:56.789"}, "Streaming: true\nTimecode: 12:34:56.789\n"},
		{"stream JSON", []string{"stream", "status", "--json"}, "GetStreamStatus", map[string]any{"outputActive": true, "outputTimecode": "12:34:56.789"}, "{\"schema_version\":1,\"kind\":\"stream\",\"active\":true,\"timecode\":\"12:34:56.789\"}\n"},
		{"recording JSON", []string{"recording", "status", "--json"}, "GetRecordStatus", map[string]any{"outputActive": true, "outputPaused": true, "outputTimecode": "00:11:22.333"}, "{\"schema_version\":1,\"kind\":\"recording\",\"active\":true,\"paused\":true,\"timecode\":\"00:11:22.333\"}\n"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			base := isolatedCommandConfig(t)
			cfg, requests, closed := legacyCLIFixture(t, func(r legacyCLIRequest) (map[string]any, int) {
				if r.Type == tc.request {
					return tc.response, 100
				}
				return nil, 204
			})
			base.Host, base.Port = cfg.Host, cfg.Port
			var dials atomic.Int32
			service := obs.NewServiceWithDialer(&base, "test", func(address string, options ...goobs.Option) (*goobs.Client, error) {
				dials.Add(1)
				return goobs.New(address, options...)
			})
			t.Cleanup(func() { _ = service.Close() })
			command := NewRoot(&base, service, "test")
			var out, stderr bytes.Buffer
			command.SetOut(&out)
			command.SetErr(&stderr)
			command.SetArgs(tc.args)
			if dials.Load() != 0 {
				t.Fatal("command construction dialed OBS")
			}
			if err := command.ExecuteContext(context.Background()); err != nil {
				t.Fatalf("command failed: %v stderr=%s", err, stderr.String())
			}
			if out.String() != tc.want {
				t.Fatalf("legacy stdout changed: got %q want %q", out.String(), tc.want)
			}
			got := requests()
			if len(got) != 1 || got[0].Type != tc.request || dials.Load() != 1 {
				t.Fatalf("narrow read changed: requests=%+v dials=%d", got, dials.Load())
			}
			if err := service.Close(); err != nil {
				t.Fatal(err)
			}
			select {
			case <-closed:
			case <-time.After(time.Second):
				t.Fatal("command service did not release OBS")
			}
		})
	}
}

func TestLegacyCLICompositeActionsPreserveObservationOrder(t *testing.T) {
	cases := []struct {
		name  string
		args  []string
		state map[string]any
		want  []string
	}{
		{"scene switch in studio", []string{"scene", "switch", "Game", "Scene"}, map[string]any{"studioModeEnabled": true}, []string{"GetStudioModeEnabled", "SetCurrentPreviewScene"}},
		{"scene switch in program", []string{"scene", "switch", "Game", "Scene"}, map[string]any{"studioModeEnabled": false}, []string{"GetStudioModeEnabled", "SetCurrentProgramScene"}},
		{"pause toggle resume", []string{"recording", "pause", "toggle"}, map[string]any{"outputActive": true, "outputPaused": true, "outputTimecode": "00:00:01.000"}, []string{"GetRecordStatus", "ResumeRecord"}},
		{"pause toggle pause", []string{"recording", "pause", "toggle"}, map[string]any{"outputActive": true, "outputPaused": false, "outputTimecode": "00:00:01.000"}, []string{"GetRecordStatus", "PauseRecord"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			base := isolatedCommandConfig(t)
			cfg, requests, _ := legacyCLIFixture(t, func(r legacyCLIRequest) (map[string]any, int) {
				if r.Type == tc.want[0] {
					return tc.state, 100
				}
				if r.Type == tc.want[1] {
					return map[string]any{}, 100
				}
				return nil, 204
			})
			base.Host, base.Port = cfg.Host, cfg.Port
			service := obs.NewService(&base, "test")
			t.Cleanup(func() { _ = service.Close() })
			command := NewRoot(&base, service, "test")
			var out bytes.Buffer
			command.SetOut(&out)
			command.SetArgs(tc.args)
			if err := command.Execute(); err != nil {
				t.Fatal(err)
			}
			var types []string
			for _, r := range requests() {
				types = append(types, r.Type)
			}
			if !reflect.DeepEqual(types, tc.want) || out.Len() != 0 {
				t.Fatalf("composite changed: requests=%v want=%v output=%q", types, tc.want, out.String())
			}
			if strings.HasPrefix(tc.name, "scene") && requests()[1].Data["sceneName"] != "Game Scene" {
				t.Fatal("scene argument joining changed")
			}
		})
	}
}

func TestLegacyCLIFailedObservationHasNoSuccessfulStdout(t *testing.T) {
	base := isolatedCommandConfig(t)
	cfg, requests, _ := legacyCLIFixture(t, func(legacyCLIRequest) (map[string]any, int) { return nil, 600 })
	base.Host, base.Port = cfg.Host, cfg.Port
	service := obs.NewService(&base, "test")
	t.Cleanup(func() { _ = service.Close() })
	command := NewRoot(&base, service, "test")
	var out bytes.Buffer
	command.SetOut(&out)
	command.SetArgs([]string{"profile", "get"})
	err := command.Execute()
	if err == nil || out.Len() != 0 || strings.Contains(err.Error(), "private-stream-key-marker") {
		t.Fatalf("failed read became output or leaked: out=%q err=%v", out.String(), err)
	}
	if len(requests()) != 1 {
		t.Fatalf("unexpected fallback requests: %+v", requests())
	}
}

func TestLegacyCLIExecuteContextCancelsItsAcquiredOBSRequest(t *testing.T) {
	base := isolatedCommandConfig(t)
	entered := make(chan struct{}, 1)
	cfg, _, closed := legacyCLIFixture(t, func(legacyCLIRequest) (map[string]any, int) { entered <- struct{}{}; return nil, 0 })
	base.Host, base.Port = cfg.Host, cfg.Port
	service := obs.NewService(&base, "test")
	t.Cleanup(func() { _ = service.Close() })
	command := NewRoot(&base, service, "test")
	var out bytes.Buffer
	command.SetOut(&out)
	command.SetArgs([]string{"profile", "list"})
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- command.ExecuteContext(ctx) }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("profile request not acquired")
	}
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("lost command cancellation: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("CLI cancellation did not interrupt OBS request")
	}
	if out.Len() != 0 {
		t.Fatalf("cancelled profile read printed successful names: %q", out.String())
	}
	select {
	case <-closed:
	case <-time.After(time.Second):
		t.Fatal("CLI cancellation retained OBS transport")
	}
}
