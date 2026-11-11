// Package deckyinstall installs only the verified OBSGod plugin through the
// existing Decky service. It never edits root-owned plugin files directly.
package deckyinstall

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/gorilla/websocket"
)

type Input struct {
	ZIPPath string `json:"zip_path"`
	SHA256  string `json:"sha256"`
	Version string `json:"version"`
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

type message struct {
	Type   int               `json:"type"`
	ID     int64             `json:"id"`
	Event  string            `json:"event"`
	Args   []json.RawMessage `json:"args"`
	Result json.RawMessage   `json:"result"`
}

type client struct {
	conn   *websocket.Conn
	id     int64
	input  Input
	prompt string
}

// All connection errors deliberately discard the URL, which contains Decky's
// local authentication token. The token never enters argv, files or output.
func connect(ctx context.Context, endpoint string) (*client, error) {
	request, _ := http.NewRequestWithContext(ctx, "GET", endpoint+"/auth/token", nil)
	httpClient := &http.Client{Timeout: 3 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	response, err := httpClient.Do(request)
	if err != nil {
		return nil, errors.New("Decky Loader is not reachable. Keep it installed and run this updater in Desktop Mode")
	}
	defer response.Body.Close()
	token, err := io.ReadAll(io.LimitReader(response.Body, 1024))
	if err != nil || response.StatusCode != 200 || !tokenPattern.Match(token) {
		return nil, errors.New("could not authenticate with the local Decky service")
	}
	dialer := websocket.Dialer{HandshakeTimeout: 3 * time.Second, Proxy: http.ProxyFromEnvironment}
	conn, _, err := dialer.DialContext(ctx, "ws"+strings.TrimPrefix(endpoint, "http")+"/ws?"+url.Values{"auth": []string{string(token)}}.Encode(), nil)
	if err != nil {
		return nil, errors.New("could not connect to Decky's authenticated local installer")
	}
	conn.SetReadLimit(4 * 1024 * 1024)
	if deadline, ok := ctx.Deadline(); ok {
		_ = conn.SetReadDeadline(deadline)
	}
	var seed [8]byte
	if _, err = rand.Read(seed[:]); err != nil {
		_ = conn.Close()
		return nil, errors.New("could not initialize installer request IDs")
	}
	return &client{conn: conn, id: int64(binary.LittleEndian.Uint64(seed[:]) & ((1 << 52) - 1))}, nil
}

func (c *client) send(value any) error {
	_ = c.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
	if err := c.conn.WriteJSON(value); err != nil {
		return errors.New("Decky's connection changed. Close Steam's Big Picture window in Desktop Mode and rerun the updater")
	}
	return nil
}

func (c *client) call(route string, args ...any) (json.RawMessage, error) {
	c.id++
	id := c.id
	if args == nil {
		args = []any{}
	}
	if err := c.send(map[string]any{"type": 0, "id": id, "route": route, "args": args}); err != nil {
		return nil, err
	}
	for {
		var response message
		if err := c.conn.ReadJSON(&response); err != nil {
			return nil, errors.New("Decky's installer connection ended or timed out. Close Steam's Big Picture window in Desktop Mode, then rerun the updater")
		}
		if response.Type == 5 && response.Event == "loader/add_plugin_install_prompt" && len(response.Args) == 5 {
			var name, version, requestID, digest string
			var installType int
			if json.Unmarshal(response.Args[0], &name) == nil && json.Unmarshal(response.Args[1], &version) == nil && json.Unmarshal(response.Args[2], &requestID) == nil && json.Unmarshal(response.Args[3], &digest) == nil && json.Unmarshal(response.Args[4], &installType) == nil && name == "OBSGod" && version == c.input.Version && digest == c.input.SHA256 && installType == 4 && len(requestID) > 0 && len(requestID) < 128 {
				c.prompt = requestID
			}
		}
		if response.ID != id || response.Type == 5 {
			continue
		}
		if err := c.send(map[string]any{"type": 3, "id": id}); err != nil {
			return nil, err
		}
		if response.Type != 1 {
			return nil, fmt.Errorf("Decky rejected %s; update Decky Loader and rerun the updater", route)
		}
		return response.Result, nil
	}
}

type installedPlugin struct {
	Name     string `json:"name"`
	Version  string `json:"version"`
	Disabled bool   `json:"disabled"`
	LoadType int    `json:"load_type"`
}

func Install(ctx context.Context, input Input) error {
	return installAt(ctx, input, "http://127.0.0.1:1337")
}

func installAt(ctx context.Context, input Input, endpoint string) error {
	zipPath, err := validate(input)
	if err != nil {
		return err
	}
	c, err := connect(ctx, endpoint)
	if err != nil {
		return err
	}
	defer c.conn.Close()
	stopCancellation := context.AfterFunc(ctx, func() { _ = c.conn.Close() })
	defer stopCancellation()
	c.input = input
	previous, err := c.call("utilities/settings/get", "pluginOrder", []string{})
	if err != nil {
		return err
	}
	var oldOrder []string
	if json.Unmarshal(previous, &oldOrder) != nil {
		return errors.New("Decky returned an invalid plugin order")
	}
	// The explicit updater invocation authorizes this one verified OBSGod
	// package. Use the same request + confirmation routes as Decky's own UI.
	if _, err = c.call("utilities/install_plugin", "file://"+filepath.ToSlash(zipPath), "OBSGod", input.Version, input.SHA256, 4); err != nil {
		return err
	}
	if c.prompt == "" {
		return errors.New("Decky did not offer the expected verified OBSGod installation")
	}
	if _, err = c.call("utilities/confirm_plugin_install", c.prompt); err != nil {
		return err
	}
	result, err := c.call("loader/get_plugins")
	if err != nil {
		return err
	}
	var plugins []installedPlugin
	if json.Unmarshal(result, &plugins) != nil {
		return errors.New("could not verify Decky's installed plugin list")
	}
	found := false
	for _, plugin := range plugins {
		if plugin.Name == "OBSGod" && plugin.Version == input.Version && !plugin.Disabled && plugin.LoadType == 1 {
			found = true
		}
	}
	if !found {
		return errors.New("Decky did not confirm the expected enabled OBSGod version; keep the error visible and rerun after checking Decky")
	}
	// Decky's reinstall removes the old plugin-order entry. Restore just
	// OBSGod's position, preserving the relative order of every other plugin.
	current, err := c.call("utilities/settings/get", "pluginOrder", []string{})
	if err != nil {
		return err
	}
	var order []string
	if json.Unmarshal(current, &order) != nil {
		return errors.New("could not verify Decky's plugin order")
	}
	for _, name := range order {
		if name == "OBSGod" {
			return nil
		}
	}
	position := len(order)
	for index, name := range oldOrder {
		if name == "OBSGod" {
			position = min(index, len(order))
			break
		}
	}
	order = append(order, "")
	copy(order[position+1:], order[position:])
	order[position] = "OBSGod"
	if _, err = c.call("utilities/settings/set", "pluginOrder", order); err != nil {
		return err
	}
	return nil
}
