//go:build linux

package deck

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"net"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

func startControlFixture(t *testing.T, password string, authentication, wrongProfile, active bool) <-chan fixtureRequest {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:"+Port)
	if err != nil {
		t.Skip("fixture OBS port is occupied")
	}
	requests := make(chan fixtureRequest, 128)
	upgrader := websocket.Upgrader{}
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		data := map[string]any{"rpcVersion": 1, "obsWebSocketVersion": "5.6.3"}
		const salt, challenge = "control-fixture-salt", "control-fixture-challenge"
		if authentication {
			data["authentication"] = map[string]string{"salt": salt, "challenge": challenge}
		}
		_ = c.WriteJSON(map[string]any{"op": 0, "d": data})
		var identify struct {
			D struct {
				Authentication string `json:"authentication"`
			} `json:"d"`
		}
		if c.ReadJSON(&identify) != nil {
			return
		} // Greeting-only probe sends no identify.
		secret := sha256.Sum256([]byte(password + salt))
		answer := sha256.Sum256([]byte(base64.StdEncoding.EncodeToString(secret[:]) + challenge))
		if authentication && identify.D.Authentication != base64.StdEncoding.EncodeToString(answer[:]) {
			_ = c.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(4009, "never-echo-server-secret"), time.Now().Add(time.Second))
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D fixtureRequest `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			requests <- q.D
			response := map[string]any{}
			switch q.D.Type {
			case "GetVersion":
				response = map[string]any{"obsVersion": "33.0.1", "obsWebSocketVersion": "5.6.3"}
			case "GetProfileList":
				profile := "OBSGod"
				if wrongProfile {
					profile = "ordinary OBS"
				}
				response = map[string]any{"currentProfileName": profile}
			case "GetSceneCollectionList":
				response = map[string]any{"currentSceneCollectionName": "OBSGod"}
			case "GetCurrentProgramScene":
				response = map[string]any{"sceneName": LiveScene}
			case "GetRecordStatus":
				response = map[string]any{"outputActive": false}
			case "GetStreamStatus":
				response = map[string]any{"outputActive": active, "outputReconnecting": false, "outputBytes": 4096}
			}
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": response}}) != nil {
				return
			}
		}
	})}
	go func() { _ = server.Serve(listener) }()
	t.Cleanup(func() { _ = server.Close() })
	return requests
}

func TestControlConnectionTestAuthenticatesWithoutChangingOutput(t *testing.T) {
	p, secret := configuredControl(t)
	requests := startControlFixture(t, secret.OBSPassword, true, false, true)
	result := TestControlConnection(context.Background(), p)
	if !result.OK || !result.Connected || !result.Managed || !result.OutputKnown || result.State != "streaming" {
		t.Fatal("live managed output not reported truthfully", result)
	}
	for len(requests) > 0 {
		request := <-requests
		if !strings.HasPrefix(request.Type, "Get") {
			t.Fatal("connection test attempted mutating operation", request.Type)
		}
	}
	data, _ := json.Marshal(result)
	if strings.Contains(string(data), secret.OBSPassword) || strings.Contains(string(data), secret.StreamKey) {
		t.Fatal("connection test returned a secret")
	}
}

func TestControlConnectionTestClassifiesAuthenticationFailure(t *testing.T) {
	p, secret := configuredControl(t)
	startControlFixture(t, "another-local-password", true, false, false)
	result := TestControlConnection(context.Background(), p)
	data, _ := json.Marshal(result)
	if result.OK || result.OutputKnown || !strings.Contains(result.Message, "rejected") || strings.Contains(string(data), "never-echo-server-secret") || strings.Contains(string(data), secret.OBSPassword) {
		t.Fatal("authentication failure unsafe or misleading", result)
	}
}

func TestControlConnectionRefusesDisabledAuthAndOrdinaryProfile(t *testing.T) {
	for _, wrongProfile := range []bool{false, true} {
		t.Run(map[bool]string{false: "authentication-disabled", true: "ordinary-profile"}[wrongProfile], func(t *testing.T) {
			p, secret := configuredControl(t)
			startControlFixture(t, secret.OBSPassword, wrongProfile, wrongProfile, false)
			result := TestControlConnection(context.Background(), p)
			if result.OK || result.OutputKnown || result.Managed {
				t.Fatal("unsecured or ordinary OBS falsely verified", result)
			}
		})
	}
}

func TestControlPasswordChangeReconnectsWithOnlyNewPassword(t *testing.T) {
	p, old := configuredControl(t)
	if _, err := changeControlPassword(p, strings.NewReader(`{"confirm":true,"generate":true}`), closedControl, writeJSON); err != nil {
		t.Fatal(err)
	}
	_, secret, err := Load(p)
	if err != nil || secret.OBSPassword == old.OBSPassword {
		t.Fatal("new password unavailable", err)
	}
	startControlFixture(t, secret.OBSPassword, true, false, false)
	result := TestControlConnection(context.Background(), p)
	if !result.OK || !result.Connected || result.State != "stopped" {
		t.Fatal("new synchronized password did not reconnect", result)
	}
}
