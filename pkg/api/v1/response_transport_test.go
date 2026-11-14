package v1

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/pkg/automation"
)

type responseTransportFixture struct {
	requests atomic.Int32
	closed   chan struct{}
	reply    chan struct{}
	release  sync.Once
	server   *httptest.Server
}

func newResponseTransportFixture(t *testing.T, mode string) *responseTransportFixture {
	t.Helper()
	f := &responseTransportFixture{closed: make(chan struct{}), reply: make(chan struct{})}
	f.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := (&websocket.Upgrader{}).Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer close(f.closed)
		defer conn.Close()
		if conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.5.0"}}) != nil {
			return
		}
		var identify any
		if conn.ReadJSON(&identify) != nil {
			return
		}
		if conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}}) != nil {
			return
		}
		for {
			var request struct {
				Op int `json:"op"`
				D  struct {
					Type string         `json:"requestType"`
					ID   string         `json:"requestId"`
					Data map[string]any `json:"requestData"`
				} `json:"d"`
			}
			if conn.ReadJSON(&request) != nil {
				return
			}
			count := f.requests.Add(1)
			code := 100
			if count == 1 {
				switch mode {
				case "late":
					<-f.reply
				case "wrong-id":
					request.D.ID = "private-server-key-and-endpoint (600)"
				case "reject":
					code = 600
				}
			}
			if request.Op != 6 || (request.D.Type != "StartStream" && request.D.Type != "StopStream" && request.D.Type != "GetStreamStatus") || len(request.D.Data) != 0 {
				t.Errorf("legacy/API request format changed: %+v", request)
			}
			if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": request.D.Type, "requestId": request.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code, "comment": "private-server-key-and-endpoint: timeout waiting for response from server (777)"}, "responseData": map[string]any{}}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(f.server.Close)
	t.Cleanup(f.releaseReply)
	return f
}

func (f *responseTransportFixture) releaseReply() { f.release.Do(func() { close(f.reply) }) }

func (f *responseTransportFixture) connect(t *testing.T) *Client {
	t.Helper()
	client, err := Connect(context.Background(), Connection{Address: strings.TrimPrefix(f.server.URL, "http://"), Password: "private-control-password", ConnectTimeout: 80 * time.Millisecond, OperationTimeout: time.Second})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client
}

func assertSafeResponseFailure(t *testing.T, err error, code ErrorCode) {
	t.Helper()
	var failure *Error
	if !errors.As(err, &failure) || failure.Code != code || failure.OBSCode != 0 {
		t.Fatalf("unsafe/misclassified response failure: %v", err)
	}
	response, marshalErr := json.Marshal(NewResponse("stream.start", nil, err))
	if marshalErr != nil {
		t.Fatal(marshalErr)
	}
	for _, output := range []string{fmt.Sprintf("%v %+v %#v", err, err, err), string(response)} {
		for _, private := range []string{"private-", "127.0.0.1", "(600)", "(777)"} {
			if strings.Contains(output, private) {
				t.Fatal("raw endpoint, credentials, server comment or ID escaped")
			}
		}
	}
}

func TestSDKResponseInterruptionInvalidatesBeforeNextRequest(t *testing.T) {
	for _, tc := range []struct {
		name     string
		mode     string
		read     bool
		workflow string
		code     ErrorCode
	}{
		{name: "delayed legacy mutation acknowledgement", mode: "late", code: Timeout},
		{name: "delayed public observation", mode: "late", read: true, code: Timeout},
		{name: "delayed workflow observation", mode: "late", workflow: "apply", code: Timeout},
		{name: "delayed profile workflow observation", mode: "late", workflow: "profile", code: Timeout},
		{name: "delayed collection workflow observation", mode: "late", workflow: "collection", code: Timeout},
		{name: "lost response correlation", mode: "wrong-id", code: Unavailable},
	} {
		t.Run(tc.name, func(t *testing.T) {
			fixture := newResponseTransportFixture(t, tc.mode)
			client := fixture.connect(t)
			// The reply is withheld until after the SDK budget. Fixture cleanup
			// also releases it when an assertion fails.
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			var err error
			switch tc.workflow {
			case "apply":
				_, err = client.ApplyWorkflow(ctx, WorkflowPlan{}, Approval{Settings: true})
			case "profile":
				err = client.SelectProfile(ctx, "Fixture", Approval{Settings: true})
			case "collection":
				err = client.SelectCollection(ctx, "Fixture", Approval{Settings: true})
			default:
				if tc.read {
					_, err = client.StreamStatus(ctx)
				} else {
					_, err = client.Legacy(ctx, LegacyRequest{Operation: LegacyStartStream}, Approval{Streaming: true})
				}
			}
			assertSafeResponseFailure(t, err, tc.code)
			if ctx.Err() != nil {
				t.Fatal("caller deadline caused fixture failure instead of SDK response failure")
			}
			if tc.code == Timeout && !errors.Is(err, context.DeadlineExceeded) {
				t.Fatal("safe timeout identity was lost")
			}
			if !client.Closed() {
				t.Fatal("interrupted connection remains reusable")
			}
			_, err = client.Legacy(context.Background(), LegacyRequest{Operation: LegacyStopStream}, Approval{Streaming: true})
			assertSafeResponseFailure(t, err, Unavailable)
			if fixture.requests.Load() != 1 {
				t.Fatal("subsequent mutation reached poisoned connection")
			}
			if err := client.Close(); err != nil {
				t.Fatal(err)
			}
			fixture.releaseReply()
			select {
			case <-fixture.closed:
			case <-time.After(time.Second):
				t.Fatal("invalidated connection retained its physical socket")
			}
			if fixture.requests.Load() != 1 {
				t.Fatal("late response allowed a later request to reach OBS")
			}
		})
	}
}

func TestNumericOBSRejectionKeepsLegacyConnectionHealthy(t *testing.T) {
	fixture := newResponseTransportFixture(t, "reject")
	client := fixture.connect(t)
	_, err := client.Legacy(context.Background(), LegacyRequest{Operation: LegacyStartStream}, Approval{Streaming: true})
	var failure *Error
	if !errors.As(err, &failure) || failure.Code != OBSRequest || failure.OBSCode != 600 || client.Closed() {
		t.Fatalf("numeric rejection poisoned connection or lost status: %v closed=%v", err, client.Closed())
	}
	if strings.Contains(fmt.Sprintf("%v %+v %#v", err, err, err), "private-") {
		t.Fatal("server rejection comment escaped")
	}
	// v0 mutation success still requires only the ACK, with no status polling.
	if _, err = client.Legacy(context.Background(), LegacyRequest{Operation: LegacyStopStream}, Approval{Streaming: true}); err != nil || client.Closed() || fixture.requests.Load() != 2 {
		t.Fatalf("healthy legacy ACK failed: %v closed=%v requests=%d", err, client.Closed(), fixture.requests.Load())
	}
}

func TestResponseBoundaryFailureClosesBackendOnce(t *testing.T) {
	b := &failedBackend{err: &automation.ResponseError{}}
	client := newClient(b, time.Second)
	_, err := client.StreamStatus(context.Background())
	assertSafeResponseFailure(t, err, Unavailable)
	if !client.Closed() || b.closes.Load() != 1 {
		t.Fatal("response boundary failure did not own shutdown")
	}
	if err := client.Close(); err != nil || b.closes.Load() != 1 {
		t.Fatal("response failure shutdown was repeated")
	}
}
