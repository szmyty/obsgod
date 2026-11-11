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
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
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

func TestAuthenticatedInstallConfirmsOnlyExpectedPackageAndRestoresOrder(t *testing.T) {
	input := fixtureZIP(t, nil)
	for _, reject := range []bool{false, true} {
		t.Run(map[bool]string{false: "installed", true: "rejected"}[reject], func(t *testing.T) {
			order := []string{"Alpha", "OBSGod", "Beta"}
			confirmed := false
			finished := make(chan struct{})
			const token = "12345678-1234-1234-1234-123456789012"
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/auth/token" {
					_, _ = w.Write([]byte(token))
					return
				}
				if r.URL.Path != "/ws" || r.URL.Query().Get("auth") != token {
					w.WriteHeader(403)
					return
				}
				conn, err := (&websocket.Upgrader{}).Upgrade(w, r, nil)
				if err != nil {
					return
				}
				defer conn.Close()
				defer close(finished)
				for {
					var call struct {
						Type  int               `json:"type"`
						ID    int64             `json:"id"`
						Route string            `json:"route"`
						Args  []json.RawMessage `json:"args"`
					}
					if conn.ReadJSON(&call) != nil {
						return
					}
					if call.Type == 3 {
						continue
					}
					if call.Type != 0 || call.ID < 1 || call.ID > 1<<53 {
						t.Error("invalid call identity")
						return
					}
					var result any
					switch call.Route {
					case "utilities/settings/get":
						result = order
					case "utilities/install_plugin":
						var artifact, name, version, digest string
						var kind int
						_ = json.Unmarshal(call.Args[0], &artifact)
						_ = json.Unmarshal(call.Args[1], &name)
						_ = json.Unmarshal(call.Args[2], &version)
						_ = json.Unmarshal(call.Args[3], &digest)
						_ = json.Unmarshal(call.Args[4], &kind)
						if artifact != "file://"+filepath.ToSlash(input.ZIPPath) || name != "OBSGod" || version != input.Version || digest != input.SHA256 || kind != 4 {
							t.Error("wrong install request")
							return
						}
						_ = conn.WriteJSON(map[string]any{"type": 5, "event": "loader/add_plugin_install_prompt", "args": []any{"Other", version, "do-not-confirm", digest, 4}})
						_ = conn.WriteJSON(map[string]any{"type": 5, "event": "loader/add_plugin_install_prompt", "args": []any{name, version, "expected-request", digest, 4}})
					case "utilities/confirm_plugin_install":
						var request string
						_ = json.Unmarshal(call.Args[0], &request)
						if request != "expected-request" {
							t.Error("confirmed an unrelated request")
							return
						}
						if reject {
							_ = conn.WriteJSON(map[string]any{"type": -1, "id": call.ID, "error": map[string]any{"message": token + " fixture-secret"}})
							continue
						}
						confirmed = true
						order = []string{"Alpha", "Beta"}
					case "loader/get_plugins":
						result = []installedPlugin{{Name: "OBSGod", Version: input.Version, LoadType: 1}}
					case "utilities/settings/set":
						_ = json.Unmarshal(call.Args[1], &order)
					default:
						t.Error("unexpected route", call.Route)
						return
					}
					_ = conn.WriteJSON(map[string]any{"type": 1, "id": call.ID, "result": result})
				}
			}))
			defer server.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			err := installAt(ctx, input, server.URL)
			<-finished
			if reject {
				if err == nil || strings.Contains(err.Error(), token) || strings.Contains(err.Error(), "fixture-secret") {
					t.Fatal("unsafe or absent rejection", err)
				}
			} else if err != nil || !confirmed || !reflect.DeepEqual(order, []string{"Alpha", "OBSGod", "Beta"}) {
				t.Fatal("installation/order not confirmed", err, confirmed, order)
			}
		})
	}
}
