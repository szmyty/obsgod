//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"flag"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/szmyty/obsgod/pkg/automation"
)

var updateConfigurationCorpus = flag.Bool("update-configuration-corpus", false, "Refresh the shared public configuration wire fixtures")

type configurationContractCase struct {
	Name              string          `json:"name"`
	Input             json.RawMessage `json:"input"`
	Valid             bool            `json:"valid"`
	CanConfigure      bool            `json:"can_configure"`
	CanClose          bool            `json:"can_close"`
	CanChangePassword bool            `json:"can_change_password"`
	Producer          string          `json:"producer,omitempty"`
}

// This corpus is actual Go serialization with synthetic process observations,
// not a claim that these cases ran on SteamOS or against a provider. Python and
// JS consume the same bytes, including malformed mutations of the wire shape.
func TestConfigurationSharedWireCorpus(t *testing.T) {
	local := func(process string, credentials bool) func(Paths) ConnectionDetails {
		return func(Paths) ConnectionDetails {
			state := "unknown"
			if process == "absent" {
				state = "stopped"
			}
			return ConnectionDetails{OK: true, Host: "127.0.0.1", Port: Port,
				Authentication: true, CredentialsAvailable: credentials, Process: process,
				OutputKnown: process == "absent", State: state,
				Message: "Local control observation"}
		}
	}
	var cases []configurationContractCase
	add := func(name string, p Paths, state Result, credentials, edit, close, password bool) {
		t.Helper()
		view := readConfiguration(context.Background(), p, configurationProbe(state), local(state.Process, credentials))
		if view.CanConfigure != edit || view.CanClose != close {
			t.Fatalf("%s: unexpected Go readiness", name)
		}
		body, err := json.Marshal(view)
		if err != nil {
			t.Fatal(err)
		}
		for _, forbidden := range []string{"stream_key", "obs_password", "settings_hash"} {
			if strings.Contains(string(body), forbidden) {
				t.Fatalf("%s: private field in public wire fixture", name)
			}
		}
		cases = append(cases, configurationContractCase{Name: name, Input: body, Valid: true,
			CanConfigure: edit, CanClose: close, CanChangePassword: password,
			Producer: "readConfiguration/json.Marshal; synthetic observation"})
	}
	add("first-run", testPaths(t), configurationStopped(), false, true, false, false)
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	add("configured-legacy-omitted-dimensions", p, configurationStopped(), true, true, false, true)
	modern := strings.TrimSuffix(fixtureSettings, "}") + `,"capture_mode":"game","width":1920,"height":1080}`
	if _, err := Configure(p, strings.NewReader(modern)); err != nil {
		t.Fatal(err)
	}
	add("configured-closed", p, configurationStopped(), true, true, false, true)
	running := configurationStopped()
	running.Process, running.Connected = "running", true
	running.Runtime = &automation.RuntimeStatus{Profile: "OBSGod", Collection: "OBSGod"}
	add("running-idle-presence-only-connection", p, running, true, false, true, false)
	running.State, running.Stream.Active = "streaming", true
	add("streaming", p, running, true, false, false, false)
	unknown := Result{OK: false, State: "unknown", Process: "unknown", OutputKnown: false}
	add("output-unavailable", p, unknown, true, false, false, false)
	if err := os.WriteFile(p.Config, []byte("{malformed"), 0o600); err != nil {
		t.Fatal(err)
	}
	running.State, running.Stream.Active = "stopped", false
	add("settings-unavailable-running-idle", p, running, true, false, false, false)
	add("settings-unavailable-closed", p, configurationStopped(), true, false, false, false)
	if _, err := Configure(p, strings.NewReader(modern)); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(p.Secrets); err != nil {
		t.Fatal(err)
	}
	add("saved-settings-without-credentials", p, configurationStopped(), false, true, false, false)
	if _, err := Configure(p, strings.NewReader(modern)); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(p.Secrets)
	if err != nil {
		t.Fatal(err)
	}
	var secret Secrets
	if err := json.Unmarshal(data, &secret); err != nil {
		t.Fatal(err)
	}
	secret.StreamKey = ""
	data, err = json.Marshal(secret)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p.Secrets, data, 0o600); err != nil {
		t.Fatal(err)
	}
	add("unconfigured-control-credentials-closed", p, configurationStopped(), true, true, false, false)
	add("unconfigured-control-credentials-running-idle", p, running, true, false, true, false)
	unicodeServer := strings.Replace(modern, "rtmps://example.invalid/app", "rtmps://example.invalid/app/café/🎮@game", 1)
	if _, err := Configure(p, strings.NewReader(unicodeServer)); err != nil {
		t.Fatal(err)
	}
	add("configured-unicode-server-path", p, configurationStopped(), true, true, false, true)
	if err := os.Remove(p.Config); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(t.TempDir(), "not-read"), p.Config); err != nil {
		t.Fatal(err)
	}
	add("unsafe-path-unavailable", p, unknown, false, false, false, false)

	mutate := func(name string, valid bool, change func(map[string]any)) {
		t.Helper()
		var value map[string]any
		if err := json.Unmarshal(cases[2].Input, &value); err != nil {
			t.Fatal(err)
		}
		change(value)
		body, err := json.Marshal(value)
		if err != nil {
			t.Fatal(err)
		}
		entry := configurationContractCase{Name: name, Input: body, Valid: valid}
		if valid {
			entry.CanConfigure, entry.CanChangePassword = true, true
		}
		cases = append(cases, entry)
	}
	mutate("legacy-explicit-zero-dimensions", true, func(v map[string]any) {
		s := v["settings"].(map[string]any)
		s["width"], s["height"], s["capture_mode"] = 0, 0, ""
	})
	mutate("closed-after-failed-connection-test", true, func(v map[string]any) {
		// The adapter overlays the read-only test result after a fresh view.
		// Failed authentication does not negate a confirmed closed process.
		v["connection"].(map[string]any)["ok"] = false
	})
	mutate("integral-decimal-json-numbers", true, func(v map[string]any) {
		v["schema_version"] = json.Number("1.0")
		s := v["settings"].(map[string]any)
		for key, value := range map[string]string{"version": "1.0", "bitrate": "4500.0", "fps": "30.0", "width": "1920.0", "height": "1080.0"} {
			s[key] = json.Number(value)
		}
	})
	for _, field := range []string{"schema_version", "ok", "configured", "key_configured", "output_known", "can_configure", "can_close", "settings", "connection", "message"} {
		mutate("missing-top-"+field, false, func(v map[string]any) { delete(v, field) })
		mutate("wrong-top-type-"+field, false, func(v map[string]any) { v[field] = []any{} })
	}
	for _, field := range []string{"version", "server", "bitrate", "fps", "encoder", "microphone"} {
		mutate("missing-setting-"+field, false, func(v map[string]any) { delete(v["settings"].(map[string]any), field) })
		mutate("wrong-setting-type-"+field, false, func(v map[string]any) { v["settings"].(map[string]any)[field] = []any{} })
	}
	for _, field := range []string{"ok", "host", "port", "authentication_required", "credentials_available", "connected", "managed", "process", "output_known", "state", "message"} {
		mutate("missing-connection-"+field, false, func(v map[string]any) { delete(v["connection"].(map[string]any), field) })
		mutate("wrong-connection-type-"+field, false, func(v map[string]any) { v["connection"].(map[string]any)[field] = []any{} })
	}
	mutate("both-actions", false, func(v map[string]any) { v["can_close"] = true })
	mutate("unknown-authorizes-edit", false, func(v map[string]any) { v["output_known"] = false })
	mutate("failed-authorizes-edit", false, func(v map[string]any) { v["ok"] = false })
	mutate("running-authorizes-edit", false, func(v map[string]any) { v["connection"].(map[string]any)["process"] = "running" })
	mutate("absent-authorizes-close", false, func(v map[string]any) { v["can_configure"], v["can_close"] = false, true })
	mutate("configured-without-key", false, func(v map[string]any) { v["key_configured"] = false })
	mutate("configured-empty-server", false, func(v map[string]any) { v["settings"].(map[string]any)["server"] = "" })
	mutate("unpaired-dimensions", false, func(v map[string]any) { delete(v["settings"].(map[string]any), "height") })
	mutate("invalid-dimensions", false, func(v map[string]any) { v["settings"].(map[string]any)["width"] = 17 })
	mutate("wrong-schema-version", false, func(v map[string]any) { v["schema_version"] = 2 })
	mutate("wrong-settings-version", false, func(v map[string]any) { v["settings"].(map[string]any)["version"] = 2 })
	mutate("wrong-awaiting-verification-type", false, func(v map[string]any) { v["connection"].(map[string]any)["awaiting_verification"] = "false" })
	mutate("wrong-loopback-host", false, func(v map[string]any) { v["connection"].(map[string]any)["host"] = "remote.invalid" })
	mutate("wrong-control-port", false, func(v map[string]any) { v["connection"].(map[string]any)["port"] = "4455" })
	mutate("wrong-process-state", false, func(v map[string]any) { v["connection"].(map[string]any)["process"] = "closed" })
	mutate("wrong-output-state", false, func(v map[string]any) { v["connection"].(map[string]any)["state"] = "ready" })
	mutate("wrong-bitrate-range", false, func(v map[string]any) { v["settings"].(map[string]any)["bitrate"] = 0 })
	mutate("wrong-fps-value", false, func(v map[string]any) { v["settings"].(map[string]any)["fps"] = 25 })
	mutate("wrong-encoder-value", false, func(v map[string]any) { v["settings"].(map[string]any)["encoder"] = "automatic" })
	mutate("wrong-capture-mode-value", false, func(v map[string]any) { v["settings"].(map[string]any)["capture_mode"] = "fallback" })
	for _, test := range []struct{ name, server string }{
		{"server-c1-control", "rtmps://example.invalid/app\u0085"},
		{"empty-url-userinfo", "rtmps://@example.invalid/app"},
		{"empty-url-credentials", "rtmps://:@example.invalid/app"},
	} {
		mutate(test.name, false, func(v map[string]any) { v["settings"].(map[string]any)["server"] = test.server })
	}
	mutate("server-unpaired-surrogate", false, func(v map[string]any) {
		v["settings"].(map[string]any)["server"] = json.RawMessage(`"rtmps://example.invalid/app\ud800"`)
	})
	mutate("fractional-schema-version", false, func(v map[string]any) { v["schema_version"] = 1.5 })
	mutate("boolean-schema-version", false, func(v map[string]any) { v["schema_version"] = true })
	for _, field := range []string{"version", "bitrate", "fps", "width", "height"} {
		mutate("fractional-setting-"+field, false, func(v map[string]any) {
			v["settings"].(map[string]any)[field] = 1.5
		})
		mutate("boolean-setting-"+field, false, func(v map[string]any) {
			v["settings"].(map[string]any)[field] = true
		})
	}

	corpus := struct {
		SchemaVersion int                         `json:"schema_version"`
		Scope         string                      `json:"scope"`
		Cases         []configurationContractCase `json:"cases"`
	}{1, "Go-produced public views with synthetic observations and malformed mutations; no real Steam Deck/provider qualification", cases}
	want, err := json.MarshalIndent(corpus, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join("..", "..", "steamdeck", "tests", "fixtures", "configuration-contract.json")
	if *updateConfigurationCorpus {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, append(want, '\n'), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var expected, actual any
	if json.Unmarshal(want, &expected) != nil || json.Unmarshal(got, &actual) != nil || !reflect.DeepEqual(expected, actual) {
		t.Fatal("Go wire contract changed; review and refresh the shared configuration corpus")
	}
}
