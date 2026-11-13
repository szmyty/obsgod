// Package deckyinstall installs only the verified OBSGod plugin through the
// existing Decky service. It never edits root-owned plugin files directly.
package deckyinstall

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	_ "embed"
)

type Input struct {
	Operation         string `json:"operation,omitempty"`
	ZIPPath           string `json:"zip_path"`
	SHA256            string `json:"sha256"`
	Version           string `json:"version"`
	UninstallExisting bool   `json:"uninstall_existing,omitempty"`
}

var hashPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)
var versionPattern = regexp.MustCompile(`^[0-9][A-Za-z0-9.-]{0,79}$`)
var tokenPattern = regexp.MustCompile(`^[A-Za-z0-9-]{16,128}$`)

func validate(input Input) (string, error) {
	if !hashPattern.MatchString(input.SHA256) || !versionPattern.MatchString(input.Version) || !filepath.IsAbs(input.ZIPPath) || strings.ContainsAny(input.ZIPPath, "\x00\r\n") {
		return "", errors.New("invalid OBSGod installer request")
	}
	info, err := os.Lstat(input.ZIPPath)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 32*1024*1024 {
		return "", errors.New("the verified plugin ZIP must be a regular private file, at most 32 MiB")
	}
	file, err := os.Open(input.ZIPPath)
	if err != nil {
		return "", errors.New("could not open the verified plugin ZIP")
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, 32*1024*1024+1))
	if err != nil || len(data) > 32*1024*1024 {
		return "", errors.New("could not read the verified plugin ZIP")
	}
	digest := sha256.Sum256(data)
	if hex.EncodeToString(digest[:]) != input.SHA256 {
		return "", errors.New("plugin ZIP checksum mismatch; nothing was sent to Decky")
	}
	archive, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil || len(archive.File) > 1024 {
		return "", errors.New("invalid plugin ZIP")
	}
	var total uint64
	seen := map[string]bool{}
	for _, file := range archive.File {
		if file.Name != path.Clean(file.Name) || !strings.HasPrefix(file.Name, "obsgod/") || strings.Contains(file.Name, "\\") || !file.Mode().IsRegular() || seen[file.Name] {
			return "", errors.New("unsafe or duplicate plugin ZIP path; nothing was sent to Decky")
		}
		seen[file.Name] = true
		if file.UncompressedSize64 > 64*1024*1024-total {
			return "", errors.New("plugin ZIP contents exceed 64 MiB")
		}
		total += file.UncompressedSize64
	}
	readJSON := func(name string, value any) error {
		file, err := archive.Open(name)
		if err != nil {
			return err
		}
		defer file.Close()
		return json.NewDecoder(io.LimitReader(file, 16384)).Decode(value)
	}
	var plugin struct {
		Name       string   `json:"name"`
		Flags      []string `json:"flags"`
		APIVersion int      `json:"api_version"`
	}
	var metadata struct {
		Name         string            `json:"name"`
		Version      string            `json:"version"`
		Type         string            `json:"type"`
		RemoteBinary []json.RawMessage `json:"remote_binary"`
	}
	if readJSON("obsgod/plugin.json", &plugin) != nil || readJSON("obsgod/package.json", &metadata) != nil || plugin.Name != "OBSGod" || len(plugin.Flags) != 0 || plugin.APIVersion != 1 || metadata.Name != "obsgod" || metadata.Version != input.Version || metadata.Type != "module" || len(metadata.RemoteBinary) != 0 || !seen["obsgod/bin/obsgod"] || !seen["obsgod/main.py"] || !seen["obsgod/dist/index.js"] {
		return "", errors.New("ZIP is not the expected unprivileged OBSGod release")
	}
	resolved, err := filepath.EvalSymlinks(input.ZIPPath)
	if err != nil {
		return "", errors.New("could not resolve the verified ZIP path")
	}
	return resolved, nil
}

// Report contains only validated versions and fixed state, never Decky's token,
// frontend exceptions or process output.
type Report struct {
	Version           string `json:"version,omitempty"`
	DeckyVersion      string `json:"decky_version"`
	FrontendConnected bool   `json:"frontend_connected"`
	Removed           bool   `json:"removed,omitempty"`
}

//go:embed frontend-install.js
var frontendScript string

type frontendResult struct {
	OK                bool   `json:"ok"`
	Code              string `json:"code"`
	Version           string `json:"version"`
	DeckyVersion      string `json:"decky_version"`
	FrontendConnected bool   `json:"frontend_connected"`
	Removed           bool   `json:"removed"`
}

func httpClient() *http.Client {
	return &http.Client{Timeout: 85 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
}

func authToken(ctx context.Context, endpoint string) (string, error) {
	request, err := http.NewRequestWithContext(ctx, "GET", endpoint+"/auth/token", nil)
	if err != nil {
		return "", errors.New("invalid local Decky endpoint")
	}
	response, err := httpClient().Do(request)
	if err != nil {
		return "", errors.New("the Decky Loader is not reachable. Install/start Decky using its official instructions, keep Steam open in Desktop Mode, and retry")
	}
	defer response.Body.Close()
	token, err := io.ReadAll(io.LimitReader(response.Body, 1025))
	if err != nil || response.StatusCode != 200 || !tokenPattern.Match(token) {
		return "", errors.New("could not authenticate with the local Decky service; check Decky Loader and retry")
	}
	return string(token), nil
}

func evaluate(ctx context.Context, endpoint, token, tab, script string) (frontendResult, error) {
	var result frontendResult
	payload, _ := json.Marshal(map[string]any{"tab": tab, "run_async": true, "code": script})
	request, err := http.NewRequestWithContext(ctx, "POST", endpoint+"/methods/execute_in_tab", bytes.NewReader(payload))
	if err != nil {
		return result, errors.New("invalid local Decky endpoint")
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Decky-Auth", token)
	response, err := httpClient().Do(request)
	if err != nil {
		return result, errors.New("the Decky frontend request ended or timed out. Installation state is unconfirmed; keep Steam open, inspect Decky and rerun to verify")
	}
	defer response.Body.Close()
	var outer struct {
		Success bool `json:"success"`
		Result  struct {
			Success bool            `json:"success"`
			Result  json.RawMessage `json:"result"`
		} `json:"result"`
	}
	if response.StatusCode != 200 || json.NewDecoder(io.LimitReader(response.Body, 65537)).Decode(&outer) != nil || !outer.Success || !outer.Result.Success {
		// Raw responses can include traceback, user data or authentication tokens.
		// A missing named Steam context is not an assertion about Big Picture mode.
		return result, nil
	}
	var serialized string
	if json.Unmarshal(outer.Result.Result, &serialized) != nil || len(serialized) > 16384 || json.Unmarshal([]byte(serialized), &result) != nil {
		return frontendResult{}, nil
	}
	return result, nil
}

var deckyVersionPattern = regexp.MustCompile(`^v?3\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$`)

func runAt(ctx context.Context, input Input, endpoint string) (Report, error) {
	var report Report
	if input.Operation != "" && input.Operation != "install" && input.Operation != "probe" && input.Operation != "uninstall" {
		return report, errors.New("invalid OBSGod installer operation")
	}
	if input.UninstallExisting && input.Operation != "uninstall" {
		return report, errors.New("existing-folder removal is only valid for uninstall")
	}
	if input.Operation == "probe" || input.Operation == "uninstall" {
		if input.ZIPPath != "" || input.SHA256 != "" || input.Version != "" {
			return report, errors.New("probe/uninstall cannot include an installation request")
		}
	} else {
		resolved, err := validate(input)
		if err != nil {
			return report, err
		}
		input.ZIPPath = resolved
		input.Operation = "install"
	}
	token, err := authToken(ctx, endpoint)
	if err != nil {
		return report, err
	}
	value, _ := json.Marshal(input)
	script := strings.Replace(frontendScript, "__OBSGOD_REQUEST__", string(value), 1)
	for _, tab := range []string{"SP", "Steam Shared Context presented by Valve™", "SharedJSContext", "Steam"} {
		result, err := evaluate(ctx, endpoint, token, tab, script)
		if err != nil {
			return report, err
		}
		if !result.OK && (result.Code == "no-frontend" || result.Code == "") {
			continue
		}
		if !result.OK {
			messages := map[string]string{
				"unsupported":                    "Decky's frontend is incompatible with this installer. Update Decky Loader using its official instructions and retry",
				"busy":                           "Another OBSGod Decky installation is running. Let it finish, then retry",
				"install-unconfirmed":            "Decky did not confirm the requested OBSGod installation. Saved settings were preserved; inspect Decky and retry to verify or repair",
				"probe-failed":                   "Decky's version or plugin service could not be verified. Keep Steam open in Desktop Mode, check Decky and retry",
				"uninstall-unconfirmed":          "Decky did not confirm OBSGod removal. Existing app/settings were preserved; inspect Decky and retry",
				"uninstall-location-unconfirmed": "The loaded OBSGod plugin is outside the verified Decky location. Set DECKY_HOME to your actual Decky root, review the removal inventory and retry; existing files were preserved",
			}
			if message, ok := messages[result.Code]; ok {
				return report, errors.New(message)
			}
			return report, errors.New("the Decky installation state could not be verified. Keep Steam open, inspect Decky and retry")
		}
		if !result.FrontendConnected || !deckyVersionPattern.MatchString(result.DeckyVersion) || (input.Operation == "install" && result.Version != input.Version) || (input.Operation == "uninstall" && !result.Removed) {
			return report, errors.New("the Decky service returned an unexpected version or readiness result; installation is unconfirmed")
		}
		return Report{Version: result.Version, DeckyVersion: result.DeckyVersion, FrontendConnected: true, Removed: result.Removed}, nil
	}
	return report, errors.New("the Decky service is running, but its Steam frontend is unavailable. Keep the normal Steam client open in Desktop Mode, wait for Decky to load, and retry; do not uninstall your plugin")
}

func Run(ctx context.Context, input Input) (Report, error) {
	return runAt(ctx, input, "http://127.0.0.1:1337")
}

func Install(ctx context.Context, input Input) error { _, err := Run(ctx, input); return err }

func installAt(ctx context.Context, input Input, endpoint string) error {
	_, err := runAt(ctx, input, endpoint)
	return err
}
