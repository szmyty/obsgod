package deck

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode"

	"github.com/gorilla/websocket"
)

// ConnectionDetails contains only public local-control facts. Passwords and
// service keys must never become part of connection diagnostics or copy output.
type ConnectionDetails struct {
	OK                   bool   `json:"ok"`
	Host                 string `json:"host"`
	Port                 string `json:"port"`
	Authentication       bool   `json:"authentication_required"`
	CredentialsAvailable bool   `json:"credentials_available"`
	Connected            bool   `json:"connected"`
	Managed              bool   `json:"managed"`
	Process              string `json:"process"`
	OutputKnown          bool   `json:"output_known"`
	State                string `json:"state"`
	AwaitingVerification bool   `json:"awaiting_verification,omitempty"`
	Message              string `json:"message"`
}

func controlDetails(p Paths) ConnectionDetails {
	process, listener := presence(p)
	_, err := loadCredentials(p)
	r := ConnectionDetails{OK: true, Host: "127.0.0.1", Port: Port, Authentication: true, CredentialsAvailable: err == nil, Process: process, State: "unknown"}
	if process == "absent" && !listener {
		r.State, r.OutputKnown = "stopped", true
		r.Message = "Managed OBS is closed. The authenticated local control connection will be available after opening managed OBS"
	} else {
		r.Message = "OBS or its control port is present. Test the authenticated connection before assuming output is stopped"
	}
	return r
}

// ControlConnectionInfo does not launch OBS or query any streaming provider.
func ControlConnectionInfo(p Paths) ConnectionDetails { return controlDetails(p) }

// TestControlConnection authenticates and reads managed identity/output only.
// It never launches an instance, changes settings or starts an output.
func TestControlConnection(ctx context.Context, p Paths) ConnectionDetails {
	r := controlDetails(p)
	secret, err := loadCredentials(p)
	if err != nil {
		r.OK, r.Message = false, "Managed OBS credentials are unavailable. Complete Desktop setup first"
		return r
	}
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	c, err := connect(ctx, secret, time.Second)
	if err != nil {
		r.OK = false
		switch connectionKind(err) {
		case "authentication":
			r.Message = "The local listener rejected the managed password. Close managed OBS manually, then change or reset its password here; do not disable authentication"
		case "refused":
			r.Message = "The local OBS control listener is unavailable. Open the managed OBS window, then test again. This test does not launch OBS"
		default:
			r.Message = "The local control connection did not become authenticated. Inspect the managed OBS window and retry"
		}
		return r
	}
	defer c.Close()
	// goobs also connects when authentication is disabled. Verify that the
	// listener actually advertises a password challenge before claiming success.
	requiresPassword, probeErr := controlPasswordChallenge(ctx)
	if probeErr != nil || !requiresPassword {
		r.OK, r.OutputKnown = false, false
		r.Message = "The listener's password authentication could not be verified. Close managed OBS and reset its local password; do not use an unauthenticated control server"
		return r
	}
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		r.OK, r.OutputKnown = false, false
		r.Message = "The listener did not verify as the managed OBS profile and collection. Its settings were not changed"
		return r
	}
	stream, err := c.StreamStatus(ctx)
	if err != nil {
		r.OK, r.OutputKnown = false, false
		r.Message = "Authentication succeeded but output state could not be read. Use Stop and inspect OBS before changing settings"
		return r
	}
	r.Connected, r.Managed, r.OutputKnown, r.Process, r.State = true, true, true, "running", "stopped"
	if stream.Active {
		r.State = "streaming"
	} else if runtime.Recording {
		r.State = "recording"
	}
	r.Message = "Authenticated connection to the managed OBS profile verified. This test did not start a stream or recording"
	return r
}

func controlPasswordChallenge(ctx context.Context) (bool, error) {
	dialer := websocket.Dialer{HandshakeTimeout: time.Second}
	c, _, err := dialer.DialContext(ctx, "ws://127.0.0.1:"+Port, nil)
	if err != nil {
		return false, err
	}
	defer c.Close()
	stop := context.AfterFunc(ctx, func() { _ = c.Close() })
	defer stop()
	c.SetReadLimit(16384)
	deadline := time.Now().Add(time.Second)
	if limit, ok := ctx.Deadline(); ok && limit.Before(deadline) {
		deadline = limit
	}
	if err := c.SetReadDeadline(deadline); err != nil {
		return false, err
	}
	var hello struct {
		Op int `json:"op"`
		D  struct {
			Authentication *struct {
				Challenge string `json:"challenge"`
				Salt      string `json:"salt"`
			} `json:"authentication"`
		} `json:"d"`
	}
	if err := c.ReadJSON(&hello); err != nil || hello.Op != 0 {
		return false, errors.New("invalid local control greeting")
	}
	return hello.D.Authentication != nil && hello.D.Authentication.Challenge != "" && hello.D.Authentication.Salt != "", nil
}

// ChangeControlPassword changes both private files only while managed OBS and
// its port are positively absent. The caller holds the shared operation lock.
// Reconnection is a separate explicit read-only test after opening managed OBS.
func ChangeControlPassword(p Paths, input io.Reader) (ConnectionDetails, error) {
	return changeControlPassword(p, input, presence, writeJSON)
}

func changeControlPassword(p Paths, input io.Reader, probe func(Paths) (string, bool), save func(string, any) error) (ConnectionDetails, error) {
	r := ConnectionDetails{Host: "127.0.0.1", Port: Port, Authentication: true, State: "unknown"}
	request := struct {
		Password string `json:"password"`
		Generate bool   `json:"generate"`
		Confirm  bool   `json:"confirm"`
	}{}
	decoder := json.NewDecoder(io.LimitReader(input, 4097))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&request); err != nil {
		return r, errors.New("invalid local password request")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF || !request.Confirm || request.Generate == (request.Password != "") {
		return r, errors.New("confirm the password change and choose either a new password or automatic generation")
	}
	if request.Generate {
		value := make([]byte, 32)
		if _, err := rand.Read(value); err != nil {
			return r, errors.New("could not generate a local password")
		}
		request.Password = hex.EncodeToString(value)
	}
	if len(request.Password) < 12 || len(request.Password) > 128 || strings.IndexFunc(request.Password, unicode.IsControl) >= 0 {
		return r, errors.New("use a local password of 12–128 bytes without control characters")
	}
	if process, listener := probe(p); process != "absent" || listener {
		return r, errors.New("close managed OBS before changing its password; active, recording or unconfirmed instances cannot be changed")
	}
	wsPath := filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")
	if !controlParentsSafe(p.Secrets) || !controlParentsSafe(wsPath) {
		return r, errors.New("managed credential directories must be real absolute directories; links are refused")
	}
	_, secret, err := Load(p)
	if err != nil {
		return r, errors.New("complete or repair Desktop stream setup before changing the local control password")
	}
	var oldWS []byte
	wsExisted := false
	if info, err := os.Lstat(wsPath); err == nil {
		if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
			return r, errors.New("managed WebSocket settings must be a private regular file; links are refused")
		}
		oldWS, err = os.ReadFile(wsPath)
		if err != nil {
			return r, errors.New("could not read private managed WebSocket settings")
		}
		wsExisted = true
	} else if !os.IsNotExist(err) {
		return r, errors.New("could not inspect managed WebSocket settings")
	}
	ws := map[string]any{}
	if wsExisted && (json.Unmarshal(oldWS, &ws) != nil || ws == nil) {
		return r, errors.New("managed WebSocket settings are invalid; inspect managed OBS before changing credentials")
	}
	ws["server_enabled"], ws["server_port"], ws["auth_required"], ws["server_password"] = true, 4457, true, request.Password
	ws["alerts_enabled"], ws["first_load"] = false, false
	// Recheck immediately before the first write; other application launches do
	// not participate in our operation lock.
	if process, listener := probe(p); process != "absent" || listener {
		return r, errors.New("OBS appeared during password setup; close it and retry")
	}
	if err := save(wsPath, ws); err != nil {
		return r, errors.New("could not save private managed WebSocket settings; the saved password was not changed")
	}
	secret.OBSPassword = request.Password
	if err := save(p.Secrets, secret); err != nil {
		var restoreErr error
		if wsExisted {
			restoreErr = atomicWrite(wsPath, oldWS)
		} else {
			restoreErr = os.Remove(wsPath)
		}
		if restoreErr != nil {
			return r, errors.New("password update and recovery could not be completed. Keep managed OBS closed and repair Desktop setup before starting output")
		}
		return r, errors.New("password update failed; the previous managed WebSocket settings and credentials were preserved")
	}
	r.OK, r.CredentialsAvailable, r.OutputKnown, r.Process, r.State, r.AwaitingVerification = true, true, true, "absent", "stopped", true
	r.Message = "Local control password saved privately for managed OBS. Open managed OBS and use Test connection to verify reconnection; nothing was broadcast"
	return r, nil
}

func controlParentsSafe(path string) bool {
	if !filepath.IsAbs(path) {
		return false
	}
	for dir := filepath.Dir(path); ; dir = filepath.Dir(dir) {
		if info, err := os.Lstat(dir); err == nil {
			if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
				return false
			}
		} else if !os.IsNotExist(err) {
			return false
		}
		if dir == filepath.Dir(dir) {
			return true
		}
	}
}
