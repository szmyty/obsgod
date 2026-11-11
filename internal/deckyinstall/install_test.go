package deckyinstall

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fixtureZIP(t *testing.T, change func(map[string]string)) Input {
	t.Helper()
	files := map[string]string{"obsgod/plugin.json": `{"name":"OBSGod","flags":[],"api_version":1}`, "obsgod/package.json": `{"name":"obsgod","version":"0.1.0-test","type":"module"}`, "obsgod/bin/obsgod": "fixture executable", "obsgod/main.py": "fixture backend", "obsgod/dist/index.js": "fixture frontend"}
	if change != nil {
		change(files)
	}
	var data bytes.Buffer
	archive := zip.NewWriter(&data)
	for name, value := range files {
		file, err := archive.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = file.Write([]byte(value))
	}
	if err := archive.Close(); err != nil {
		t.Fatal(err)
	}
	directory := filepath.Join(t.TempDir(), "folder with spaces")
	_ = os.MkdirAll(directory, 0700)
	name := filepath.Join(directory, "plugin.zip")
	if err := os.WriteFile(name, data.Bytes(), 0600); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(data.Bytes())
	return Input{ZIPPath: name, SHA256: hex.EncodeToString(digest[:]), Version: "0.1.0-test"}
}

func TestInvalidArchivesNeverReachDecky(t *testing.T) {
	for name, change := range map[string]func(map[string]string){
		"traversal": func(files map[string]string) { files["obsgod/../../other-plugin/main.py"] = "do not install" },
		"root flag": func(files map[string]string) {
			files["obsgod/plugin.json"] = `{"name":"OBSGod","flags":["root"],"api_version":1}`
		},
		"other plugin": func(files map[string]string) {
			files["obsgod/plugin.json"] = `{"name":"Other","flags":[],"api_version":1}`
		},
		"remote binary": func(files map[string]string) {
			files["obsgod/package.json"] = `{"name":"obsgod","version":"0.1.0-test","type":"module","remote_binary":[{"url":"https://example.invalid"}]}`
		},
		"wrong version": func(files map[string]string) {
			files["obsgod/package.json"] = `{"name":"obsgod","version":"0.0.0","type":"module"}`
		},
	} {
		t.Run(name, func(t *testing.T) {
			input := fixtureZIP(t, change)
			if _, err := validate(input); err == nil {
				t.Fatal("accepted unsafe archive")
			}
		})
	}
	input := fixtureZIP(t, nil)
	input.SHA256 = strings.Repeat("0", 64)
	if _, err := validate(input); err == nil {
		t.Fatal("accepted bad checksum")
	}
	input = fixtureZIP(t, nil)
	_ = os.Chmod(input.ZIPPath, 0644)
	if _, err := validate(input); err == nil {
		t.Fatal("accepted public ZIP")
	}
	_ = os.Chmod(input.ZIPPath, 0600)
	link := filepath.Join(filepath.Dir(input.ZIPPath), "link.zip")
	_ = os.Symlink(input.ZIPPath, link)
	input.ZIPPath = link
	if _, err := validate(input); err == nil {
		t.Fatal("accepted ZIP symlink")
	}
}

func TestAuthenticatedFrontendTransportNeverOpensSecondWebSocket(t *testing.T) {
	input := fixtureZIP(t, nil)
	for _, reject := range []bool{false, true} {
		t.Run(map[bool]string{false: "installed", true: "rejected"}[reject], func(t *testing.T) {
			calls := 0
			const token = "12345678-1234-1234-1234-123456789012"
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/auth/token" {
					_, _ = w.Write([]byte(token))
					return
				}
				if r.URL.Path != "/methods/execute_in_tab" || r.Method != "POST" || r.Header.Get("X-Decky-Auth") != token {
					t.Errorf("unexpected transport %s %s", r.Method, r.URL.Path)
					w.WriteHeader(403)
					return
				}
				var request struct {
					Tab   string `json:"tab"`
					Async bool   `json:"run_async"`
					Code  string `json:"code"`
				}
				if json.NewDecoder(r.Body).Decode(&request) != nil || !request.Async || strings.Contains(request.Code, "__OBSGOD_REQUEST__") || !strings.Contains(request.Code, `"version":"`+input.Version+`"`) {
					t.Error("invalid scoped frontend request")
				}
				calls++
				if calls == 1 {
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "result": map[string]any{"success": false, "result": token + " fixture-secret"}})
					return
				}
				if request.Tab != "Steam Shared Context presented by Valve™" {
					t.Error("did not try a known shared context")
				}
				value := map[string]any{"ok": true, "decky_version": "v3.3.1", "frontend_connected": true, "version": input.Version}
				if reject {
					value = map[string]any{"ok": false, "code": "install-unconfirmed", "raw": token + " fixture-secret"}
				}
				serialized, _ := json.Marshal(value)
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "result": map[string]any{"success": true, "result": string(serialized)}})
			}))
			defer server.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			err := installAt(ctx, input, server.URL)
			if reject {
				if err == nil || strings.Contains(err.Error(), token) || strings.Contains(err.Error(), "fixture-secret") || strings.Contains(err.Error(), "Big Picture") {
					t.Fatal("unsafe/absent rejection", err)
				}
			} else if err != nil {
				t.Fatal(err)
			}
			if calls != 2 {
				t.Fatal("unexpected call count", calls)
			}
		})
	}
}

func TestProbeAndInvalidOperation(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.Path == "/auth/token" {
			_, _ = w.Write([]byte("12345678-1234-1234-1234-123456789012"))
			return
		}
		value := `{"ok":true,"decky_version":"v3.3.1","frontend_connected":true}`
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "result": map[string]any{"success": true, "result": value}})
	}))
	defer server.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	report, err := runAt(ctx, Input{Operation: "probe"}, server.URL)
	if err != nil || report.DeckyVersion != "v3.3.1" || !report.FrontendConnected || report.Version != "" {
		t.Fatal(report, err)
	}
	for _, input := range []Input{{Operation: "other"}, {Operation: "probe", ZIPPath: "/must-not-read"}} {
		if _, err := runAt(ctx, input, server.URL); err == nil {
			t.Fatal("accepted invalid operation")
		}
	}
	if calls != 2 {
		t.Fatal("invalid input reached Decky", calls)
	}
}

func TestMissingFrontendAndAuthenticationErrorsAreActionableAndRedacted(t *testing.T) {
	for _, badToken := range []bool{false, true} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path == "/auth/token" {
				if badToken {
					_, _ = w.Write([]byte("unsafe fixture-secret"))
				} else {
					_, _ = w.Write([]byte("12345678-1234-1234-1234-123456789012"))
				}
				return
			}
			_, _ = w.Write([]byte(`{"success":true,"result":{"success":false,"result":"fixture-secret"}}`))
		}))
		_, err := runAt(context.Background(), Input{Operation: "probe"}, server.URL)
		server.Close()
		if err == nil || strings.Contains(err.Error(), "fixture-secret") || strings.Contains(err.Error(), "Big Picture") {
			t.Fatal(err)
		}
	}
}

func TestFrontendInstallerBehavior(t *testing.T) {
	node, err := exec.LookPath("node")
	if err != nil {
		t.Skip("Node is required to execute the shared-frontend behavior fixture")
	}
	script, err := os.ReadFile("frontend-install.test.cjs")
	if err != nil {
		t.Fatal(err)
	}
	for _, mode := range []string{"install", "reject", "missing-prompt", "no-frontend", "probe", "confirm-timeout", "confirm-timeout-reject"} {
		command := exec.Command(node, "--input-type=commonjs", "-e", string(script))
		request, _ := json.Marshal(Input{Operation: map[bool]string{true: "probe", false: "install"}[mode == "probe"], ZIPPath: "/home/deck/space and %20/plugin.zip", SHA256: strings.Repeat("a", 64), Version: "0.1.0-test"})
		command.Stdin = strings.NewReader(strings.Replace(frontendScript, "__OBSGOD_REQUEST__", string(request), 1))
		command.Env = append(os.Environ(), "OBSGOD_TRANSPORT_TEST_MODE="+mode)
		output, err := command.CombinedOutput()
		if err != nil {
			t.Fatalf("%s: %v %s", mode, err, output)
		}
	}
}
