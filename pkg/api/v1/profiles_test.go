package v1

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/pkg/automation"
)

func profileConnection(t *testing.T, response map[string]any, code int) (*Client, func() []string) {
	t.Helper()
	var mu sync.Mutex
	var requests []string
	upgrader := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		if conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}}) != nil {
			return
		}
		var identify any
		if conn.ReadJSON(&identify) != nil || conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
			return
		}
		for {
			var request struct {
				D struct {
					Type string `json:"requestType"`
					ID   string `json:"requestId"`
				} `json:"d"`
			}
			if conn.ReadJSON(&request) != nil {
				return
			}
			mu.Lock()
			requests = append(requests, request.D.Type)
			mu.Unlock()
			status := code
			if request.D.Type != "GetProfileList" {
				status = 204 // Every unrelated output/configuration request fails.
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": request.D.Type, "requestId": request.D.ID,
				"requestStatus": map[string]any{"result": status == 100, "code": status, "comment": "private-profile-response-secret"}, "responseData": response}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	client, err := Connect(context.Background(), Connection{Address: strings.TrimPrefix(server.URL, "http://"), OperationTimeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client, func() []string {
		mu.Lock()
		defer mu.Unlock()
		return append([]string{}, requests...)
	}
}

func TestProfileInventoryIsOneNarrowReadWithOriginalOrder(t *testing.T) {
	want := []string{"Gaming Profile", "", "Second", "Gaming Profile"}
	client, requests := profileConnection(t, map[string]any{"currentProfileName": "Gaming Profile", "profiles": want}, 100)
	got, err := client.Profiles(context.Background())
	if err != nil || got.Current != "Gaming Profile" || !reflect.DeepEqual(got.Profiles, want) {
		t.Fatalf("profile inventory changed: %+v %v", got, err)
	}
	if !reflect.DeepEqual(requests(), []string{"GetProfileList"}) {
		t.Fatalf("profile-only read queried unrelated state: %v", requests())
	}
}

func TestProfileInventoryRejectsMissingNullAndCoercedFields(t *testing.T) {
	for name, response := range map[string]map[string]any{
		"missing current": {"profiles": []string{}},
		"null current":    {"currentProfileName": nil, "profiles": []string{}},
		"coerced current": {"currentProfileName": 1, "profiles": []string{}},
		"missing names":   {"currentProfileName": "Gaming"},
		"null names":      {"currentProfileName": "Gaming", "profiles": nil},
		"coerced name":    {"currentProfileName": "Gaming", "profiles": []any{1}},
		"null name":       {"currentProfileName": "Gaming", "profiles": []any{nil}},
	} {
		t.Run(name, func(t *testing.T) {
			client, _ := profileConnection(t, response, 100)
			value, err := client.Profiles(context.Background())
			var domain *Error
			if !errors.As(err, &domain) || domain.Code != OBSRequest || value.Current != "" || value.Profiles != nil {
				t.Fatalf("malformed profile response became usable: %+v %v", value, err)
			}
		})
	}
}

func TestProfileRequestFailureHasOnlySafeDomainDetails(t *testing.T) {
	client, _ := profileConnection(t, map[string]any{}, 600)
	_, err := client.Profiles(context.Background())
	var domain *Error
	if !errors.As(err, &domain) || domain.Code != OBSRequest || domain.OBSCode != 600 || domain.Operation != "profile.list" {
		t.Fatalf("wrong profile error: %v", err)
	}
	if strings.Contains(err.Error(), "private-profile-response-secret") {
		t.Fatal("server comment escaped")
	}
}

type profileBackend struct {
	backend
	value   automation.ProfileInventory
	entered chan struct{}
	reads   atomic.Int32
	closes  atomic.Int32
}

func (b *profileBackend) ProfileInventory(ctx context.Context) (automation.ProfileInventory, error) {
	b.reads.Add(1)
	if b.entered != nil {
		close(b.entered)
		<-ctx.Done()
		return automation.ProfileInventory{}, ctx.Err()
	}
	return b.value, nil
}
func (b *profileBackend) Close() error { b.closes.Add(1); return nil }

func TestProfileInventoryOwnsReturnedSliceAndNormalizesEmptyList(t *testing.T) {
	b := &profileBackend{value: automation.ProfileInventory{Current: "Gaming", Profiles: []string{"Gaming", "Other"}}}
	client := newClient(b, time.Second)
	defer client.Close()
	value, err := client.Profiles(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	value.Profiles[0] = "changed by caller"
	if b.value.Profiles[0] != "Gaming" {
		t.Fatal("caller mutated backend inventory storage")
	}
	b.value = automation.ProfileInventory{}
	empty, err := client.Profiles(context.Background())
	encoded, encodeErr := json.Marshal(empty)
	if err != nil || encodeErr != nil || string(encoded) != `{"current":"","profiles":[]}` {
		t.Fatalf("empty inventory is not stable JSON: %s %v %v", encoded, err, encodeErr)
	}
}

func TestProfileCancellationInvalidatesOnlyAcquiredConnection(t *testing.T) {
	b := &profileBackend{entered: make(chan struct{})}
	client := newClient(b, time.Second)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { _, err := client.Profiles(ctx); done <- err }()
	<-b.entered
	cancel()
	if err := <-done; !errors.Is(err, context.Canceled) || b.closes.Load() != 1 {
		t.Fatalf("cancelled profile read retained connection: %v closes=%d", err, b.closes.Load())
	}
	if _, err := client.Profiles(context.Background()); err == nil || b.reads.Load() != 1 {
		t.Fatal("cancelled connection was reused")
	}
	_ = client.Close()
	if b.closes.Load() != 1 {
		t.Fatal("connection closed more than once")
	}

	b = &profileBackend{}
	client = newClient(b, time.Second)
	ctx, cancel = context.WithCancel(context.Background())
	cancel()
	if _, err := client.Profiles(ctx); !errors.Is(err, context.Canceled) || b.reads.Load() != 0 || b.closes.Load() != 0 {
		t.Fatalf("pre-cancelled profile read contacted OBS or closed another owner: %v", err)
	}
	_ = client.Close()
}
