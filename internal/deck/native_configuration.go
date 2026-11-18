package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"strings"
	"unicode"
)

// ConfigurationView is deliberately separate from Secrets and setup tokens.
// It is suitable for the player's private configuration UI, not support logs.
type ConfigurationView struct {
	SchemaVersion int               `json:"schema_version"`
	OK            bool              `json:"ok"`
	Configured    bool              `json:"configured"`
	KeyConfigured bool              `json:"key_configured"`
	Settings      Settings          `json:"settings"`
	Connection    ConnectionDetails `json:"connection"`
	OutputKnown   bool              `json:"output_known"`
	CanConfigure  bool              `json:"can_configure"`
	CanClose      bool              `json:"can_close"`
	Message       string            `json:"message"`
}

type configurationFields struct {
	Server      *string `json:"server"`
	StreamKey   *string `json:"stream_key"`
	ReplaceKey  bool    `json:"replace_key"`
	Bitrate     *int    `json:"bitrate"`
	FPS         *int    `json:"fps"`
	Encoder     *string `json:"encoder"`
	Microphone  *bool   `json:"microphone"`
	CaptureMode *string `json:"capture_mode"`
	Width       *int    `json:"width"`
	Height      *int    `json:"height"`
}

var errNativeConfiguration = errors.New("saved stream settings are unsafe or invalid; repair the local configuration before editing")

func savedConfigurationSettings(p Paths) (Settings, error) {
	s := DefaultSettings()
	if !nativeConfigurationPathsSafe(p) {
		return s, errNativeConfiguration
	}
	info, err := os.Lstat(p.Config)
	if os.IsNotExist(err) {
		return s, nil
	}
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0022 != 0 || info.Size() > 65536 {
		return s, errNativeConfiguration
	}
	file, err := os.Open(p.Config)
	if err != nil {
		return s, errNativeConfiguration
	}
	defer file.Close()
	decoder := json.NewDecoder(io.LimitReader(file, 65537))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&s) != nil || decoder.Decode(new(any)) != io.EOF || s.Validate() != nil {
		return DefaultSettings(), errNativeConfiguration
	}
	return s, nil
}

func configurationIdle(state Result) bool {
	return state.OK && state.OutputKnown && (state.Runtime == nil || !state.Runtime.Recording) && !state.Stream.Active && !state.Stream.Reconnecting && !state.Recording &&
		state.Media != nil && state.Media.Known && !state.Media.Recording.Active && !state.Media.Recording.Paused && !state.Media.ReplayActive
}

func configurationClosed(state Result) bool {
	return configurationIdle(state) && !state.Connected && state.Process == "absent" && (state.State == "stopped" || state.State == "setup")
}

func configurationCanClose(state Result) bool {
	return configurationIdle(state) && state.Connected && state.Process == "running" && state.Runtime != nil &&
		state.Runtime.Profile == "OBSGod" && state.Runtime.Collection == "OBSGod"
}

// ReadConfiguration never launches/closes OBS, writes settings or starts output.
// Missing first-run settings return editable defaults, with no invented key.
func ReadConfiguration(ctx context.Context, p Paths) ConfigurationView {
	return readConfiguration(ctx, p, Status, ControlConnectionInfo)
}

func readConfiguration(ctx context.Context, p Paths, observe func(context.Context, Paths) Result, connection func(Paths) ConnectionDetails) ConfigurationView {
	if !nativeConfigurationPathsSafe(p) {
		return ConfigurationView{SchemaVersion: 1, Settings: DefaultSettings(), Message: errNativeConfiguration.Error(),
			Connection: ConnectionDetails{Host: "127.0.0.1", Port: Port, Authentication: true, Process: "unknown", State: "unknown"}}
	}
	settings, err := savedConfigurationSettings(p)
	state := observe(ctx, p)
	local := connection(p)
	view := ConfigurationView{SchemaVersion: 1, OK: err == nil, Settings: settings, Connection: local,
		OutputKnown:  state.OutputKnown && state.Process == local.Process,
		CanConfigure: err == nil && configurationClosed(state) && local.OutputKnown && local.Process == "absent" && !local.Connected,
		CanClose:     err == nil && configurationCanClose(state) && local.Process == "running",
		Message:      "Enter a stream key privately on this device. Saving does not start broadcasting"}
	if err == nil {
		_, _, loadErr := Load(p)
		view.Configured, view.KeyConfigured = loadErr == nil, loadErr == nil
		switch {
		case view.CanConfigure:
			view.Message = "Settings can be changed while managed OBS is closed; saving does not broadcast"
		case view.CanClose:
			view.Message = "Managed OBS is idle; close it explicitly before editing settings"
		default:
			view.Message = "Stop every output and close managed OBS before editing settings; unknown state cannot authorize changes"
		}
	} else {
		view.Message = errNativeConfiguration.Error()
	}
	return view
}

func decodeConfigurationFields(reader io.Reader) (configurationFields, error) {
	var request configurationFields
	body, err := io.ReadAll(io.LimitReader(reader, 16385))
	if err != nil || len(body) == 0 || len(body) > 16384 {
		return request, errors.New("send one stream settings object no larger than 16384 bytes")
	}
	allowed := map[string]bool{"server": true, "stream_key": true, "replace_key": true, "bitrate": true, "fps": true,
		"encoder": true, "microphone": true, "capture_mode": true, "width": true, "height": true}
	decoder := json.NewDecoder(bytes.NewReader(body))
	start, err := decoder.Token()
	if err != nil || start != json.Delim('{') {
		return request, errors.New("send one stream settings object with known scalar fields")
	}
	seen := map[string]bool{}
	for decoder.More() {
		token, err := decoder.Token()
		name, ok := token.(string)
		if err != nil || !ok || !allowed[name] || seen[name] {
			return request, errors.New("send each supported stream settings field once")
		}
		seen[name] = true
		var value any
		if decoder.Decode(&value) != nil || value == nil {
			return request, errors.New("stream settings must contain non-null scalar values")
		}
		switch value.(type) {
		case string, bool, float64:
		default:
			return request, errors.New("stream settings must contain only scalar values")
		}
	}
	if len(seen) == 0 {
		return request, errors.New("choose at least one stream setting to save")
	}
	if _, err = decoder.Token(); err != nil || decoder.Decode(new(any)) != io.EOF || json.Unmarshal(body, &request) != nil {
		return request, errors.New("stream settings have an invalid field type or trailing data")
	}
	if (request.Width == nil) != (request.Height == nil) {
		return request, errors.New("provide both output width and height together")
	}
	if request.Server != nil && (len(*request.Server) > 4096 || strings.IndexFunc(*request.Server, unicode.IsControl) >= 0) {
		return request, errors.New("enter a bounded RTMP(S) server URL without control characters")
	}
	if request.StreamKey != nil && (len(*request.StreamKey) > 4096 || strings.IndexFunc(*request.StreamKey, unicode.IsControl) >= 0) {
		return request, errors.New("enter a stream key of at most 4096 bytes without control characters")
	}
	if request.StreamKey != nil && *request.StreamKey != "" && strings.TrimSpace(*request.StreamKey) == "" {
		return request, errors.New("enter a nonblank stream key, or leave it empty to retain the current destination key")
	}
	if request.ReplaceKey && (request.StreamKey == nil || strings.TrimSpace(*request.StreamKey) == "") {
		return request, errors.New("enter the new stream key when changing the stream account or replacing its key")
	}
	return request, nil
}

// ConfigureFields merges a bounded native form while the caller holds Lock.
// Existing Configure remains the sole secret/password/settings-hash writer.
func ConfigureFields(ctx context.Context, p Paths, reader io.Reader) (Settings, error) {
	return configureFields(ctx, p, reader, Status)
}

func configureFields(ctx context.Context, p Paths, reader io.Reader, observe func(context.Context, Paths) Result) (Settings, error) {
	request, err := decodeConfigurationFields(reader)
	if err != nil {
		return Settings{}, err
	}
	saved, err := savedConfigurationSettings(p)
	if err != nil {
		return Settings{}, err
	}
	if request.Server != nil {
		saved.Server = *request.Server
	}
	if request.Bitrate != nil {
		saved.Bitrate = *request.Bitrate
	}
	if request.FPS != nil {
		saved.FPS = *request.FPS
	}
	if request.Encoder != nil {
		saved.Encoder = *request.Encoder
	}
	if request.Microphone != nil {
		saved.Microphone = *request.Microphone
	}
	if request.CaptureMode != nil {
		saved.CaptureMode = *request.CaptureMode
	}
	if request.Width != nil {
		saved.Width, saved.Height = *request.Width, *request.Height
	}
	if err = saved.Validate(); err != nil {
		return Settings{}, err
	}
	if !configurationClosed(observe(ctx, p)) {
		return Settings{}, errors.New("stop all output and explicitly close managed OBS before saving stream settings")
	}
	key := ""
	if request.StreamKey != nil {
		key = *request.StreamKey
	}
	data, err := json.Marshal(struct {
		Settings
		StreamKey string `json:"stream_key"`
	}{saved, key})
	if err != nil {
		return Settings{}, errors.New("could not prepare stream settings")
	}
	if err := ctx.Err(); err != nil {
		return Settings{}, err
	}
	state := observe(ctx, p)
	if err := ctx.Err(); err != nil {
		return Settings{}, err
	}
	if !configurationClosed(state) {
		return Settings{}, errors.New("managed OBS state changed before saving; close it and retry")
	}
	return Configure(p, bytes.NewReader(data))
}
