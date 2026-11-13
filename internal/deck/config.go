// Package deck implements the optional Linux handheld runtime. Provider-neutral
// OBS operations live in pkg/automation; this package owns local installation state.
package deck

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"
)

const Port = "4457"

type Settings struct {
	Version    int    `json:"version"`
	Server     string `json:"server"`
	Bitrate    int    `json:"bitrate"`
	FPS        int    `json:"fps"`
	Microphone bool   `json:"microphone"`
	Encoder    string `json:"encoder"`
	// Empty values retain the pre-capture-mode JSON representation and settings
	// hash. Existing installations must load without resetting their stream key.
	CaptureMode     string `json:"capture_mode,omitempty"`
	IdleStyle       string `json:"idle_style,omitempty"`
	IdleText        string `json:"idle_text,omitempty"`
	Width           int    `json:"width,omitempty"`
	Height          int    `json:"height,omitempty"`
	IdleMedia       string `json:"idle_media,omitempty"`
	IdleMediaRights string `json:"idle_media_rights,omitempty"`
}

type Secrets struct {
	StreamKey    string `json:"stream_key"`
	OBSPassword  string `json:"obs_password"`
	SettingsHash string `json:"settings_hash"`
}

type Paths struct{ Config, Secrets, OBSConfig, State, Videos string }

func UserPaths() (Paths, error) {
	home, e := os.UserHomeDir()
	if e != nil {
		return Paths{}, e
	}
	if !filepath.IsAbs(home) || strings.ContainsAny(home, "\r\n\x00") {
		return Paths{}, errors.New("HOME must be an absolute directory without control characters")
	}
	root, e := os.UserConfigDir()
	if e != nil {
		return Paths{}, e
	}
	if !filepath.IsAbs(root) || strings.ContainsAny(root, "\r\n\x00") {
		return Paths{}, errors.New("the configuration directory must be absolute without control characters")
	}
	data := os.Getenv("XDG_STATE_HOME")
	if data == "" {
		data = filepath.Join(home, ".local/state")
	}
	if !filepath.IsAbs(data) || strings.ContainsAny(data, "\r\n\x00") {
		return Paths{}, errors.New("XDG_STATE_HOME must be an absolute directory without control characters")
	}
	videos, e := DefaultVideosDirectory(home, root)
	if e != nil {
		return Paths{}, e
	}
	return Paths{Config: filepath.Join(root, "obsgod/deck.json"), Secrets: filepath.Join(root, "obsgod/secrets.json"), OBSConfig: filepath.Join(home, ".var/app/com.obsproject.Studio/config/obsgod"), State: filepath.Join(data, "obsgod"), Videos: videos}, nil
}

func DefaultSettings() Settings {
	return Settings{Version: 1, Bitrate: 4500, FPS: 30, Encoder: "vaapi"}
}

func (s Settings) CaptureModeName() string {
	if s.CaptureMode == "game" {
		return "game"
	}
	return "screen"
}

func (s Settings) IdleStyleName() string {
	switch s.IdleStyle {
	case "placeholder", "image", "video":
		return s.IdleStyle
	}
	return "black"
}

// Zero dimensions preserve legacy settings hashes and retain 720p output.
// The canvas stays 1280x720; these values control encoded output scaling only.
func (s Settings) OutputWidth() int {
	if s.Width == 0 && s.Height == 0 {
		return 1280
	}
	return s.Width
}

func (s Settings) OutputHeight() int {
	if s.Width == 0 && s.Height == 0 {
		return 720
	}
	return s.Height
}

func (s Settings) IdleMessage() string {
	if strings.TrimSpace(s.IdleText) != "" {
		return s.IdleText
	}
	return "Game starting soon"
}

func (s Settings) Validate() error {
	u, e := url.Parse(s.Server)
	if e != nil || u.Hostname() == "" || (u.Scheme != "rtmp" && u.Scheme != "rtmps") || u.User != nil || u.RawQuery != "" || u.Fragment != "" || strings.ContainsAny(s.Server, "\r\n\x00") {
		return errors.New("enter only the RTMP(S) server URL from your dashboard, without a stream key, username or query")
	}
	if s.Version != 1 {
		return errors.New("unsupported settings version")
	}
	if s.Bitrate < 1000 || s.Bitrate > 8000 {
		return errors.New("video bitrate must be 1000–8000 kbps")
	}
	if s.FPS != 30 && s.FPS != 60 {
		return errors.New("frame rate must be 30 or 60")
	}
	if s.Encoder != "vaapi" && s.Encoder != "x264" {
		return errors.New("encoder must be vaapi or x264")
	}
	if !validOutputDimensions(s.OutputWidth(), s.OutputHeight()) {
		return errors.New("choose 960x540, 1280x720 or 1920x1080 output; width and height must be supplied together")
	}
	if s.CaptureMode != "" && s.CaptureMode != "screen" && s.CaptureMode != "game" {
		return errors.New("capture mode must be screen or game")
	}
	if s.IdleStyle != "" && s.IdleStyle != "black" && s.IdleStyle != "placeholder" && s.IdleStyle != "image" && s.IdleStyle != "video" {
		return errors.New("between-game screen must be black, placeholder, image or video")
	}
	if !utf8.ValidString(s.IdleText) || len([]rune(s.IdleText)) > 200 {
		return errors.New("between-game message must be at most 200 characters without control characters")
	}
	for _, r := range s.IdleText {
		if unicode.IsControl(r) && r != '\n' {
			return errors.New("between-game message contains an unsupported control character")
		}
	}
	return validateIdleMediaSettings(s)
}

func Load(p Paths) (Settings, Secrets, error) {
	s := DefaultSettings()
	var secret Secrets
	if e := readJSON(p.Config, &s); e != nil {
		return s, secret, errors.New("complete OBSGod Desktop setup first")
	}
	if e := s.Validate(); e != nil {
		return s, secret, e
	}
	if e := readPrivateJSON(p.Secrets, &secret); e != nil {
		return s, Secrets{}, e
	}
	if secret.StreamKey == "" || secret.OBSPassword == "" {
		return s, Secrets{}, errors.New("save your stream key in OBSGod Desktop setup")
	}
	if secret.SettingsHash != settingsHash(s) {
		return s, Secrets{}, errors.New("settings and credentials do not match; save Desktop setup again before starting")
	}
	return s, secret, nil
}

func settingsHash(s Settings) string {
	b, _ := json.Marshal(s)
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

func loadCredentials(p Paths) (Secrets, error) {
	var secret Secrets
	if e := readPrivateJSON(p.Secrets, &secret); e != nil {
		return secret, e
	}
	if secret.OBSPassword == "" {
		return secret, errors.New("OBS credentials are unavailable; inspect OBS in Desktop Mode")
	}
	return secret, nil
}

func Configure(p Paths, r io.Reader) (Settings, error) {
	input := struct {
		Settings
		StreamKey string `json:"stream_key"`
	}{Settings: DefaultSettings()}
	d := json.NewDecoder(io.LimitReader(r, 16385))
	d.DisallowUnknownFields()
	if e := d.Decode(&input); e != nil {
		return Settings{}, errors.New("invalid setup JSON")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return Settings{}, errors.New("setup must contain exactly one JSON object")
	}
	if e := input.Settings.Validate(); e != nil {
		return Settings{}, e
	}
	var secret Secrets
	if _, e := os.Lstat(p.Secrets); e == nil {
		if e = readPrivateJSON(p.Secrets, &secret); e != nil {
			return Settings{}, e
		}
	}
	if input.StreamKey != "" {
		secret.StreamKey = input.StreamKey
	} else if secret.StreamKey != "" {
		// A saved key belongs to its saved destination. Reusing it for another
		// server can disclose it to an unrelated provider. Same-server edits
		// retain the established blank-means-keep behavior.
		var previous Settings
		if readJSON(p.Config, &previous) != nil || previous.Server != input.Server || secret.SettingsHash != settingsHash(previous) {
			return Settings{}, errors.New("enter the key for this server; a saved key cannot be reused when its destination or settings binding changed")
		}
	}
	if secret.StreamKey == "" || len(secret.StreamKey) > 4096 || strings.ContainsAny(secret.StreamKey, "\r\n\x00") {
		return Settings{}, errors.New("enter a valid stream key in the password field")
	}
	if secret.OBSPassword == "" {
		b := make([]byte, 32)
		if _, e := rand.Read(b); e != nil {
			return Settings{}, e
		}
		secret.OBSPassword = hex.EncodeToString(b)
	}
	// Bind the pair so a failed second write cannot combine an old server URL
	// with a new secret. Recovery is simply saving setup again.
	secret.SettingsHash = settingsHash(input.Settings)
	if e := writeJSON(p.Secrets, secret); e != nil {
		return Settings{}, e
	}
	if e := writeJSON(p.Config, input.Settings); e != nil {
		return Settings{}, e
	}
	return input.Settings, nil
}

func readJSON(path string, v any) error {
	b, e := os.ReadFile(path)
	if e != nil {
		return e
	}
	return json.Unmarshal(b, v)
}
func readPrivateJSON(path string, v any) error {
	info, e := os.Lstat(path)
	if e != nil {
		return errors.New("OBSGod credentials are missing; run Desktop setup")
	}
	if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return errors.New("credential file must be a regular, private file (chmod 600); symlinks are refused")
	}
	if e = readJSON(path, v); e != nil {
		return errors.New("could not read OBSGod credentials; run Desktop setup")
	}
	return nil
}

func privateDir(path string) error {
	if e := os.MkdirAll(path, 0700); e != nil {
		return e
	}
	i, e := os.Lstat(path)
	if e != nil {
		return e
	}
	if !i.IsDir() || i.Mode()&os.ModeSymlink != 0 {
		return errors.New("unsafe OBSGod directory")
	}
	return os.Chmod(path, 0700)
}

func atomicWrite(path string, b []byte) error {
	if e := privateDir(filepath.Dir(path)); e != nil {
		return e
	}
	if i, e := os.Lstat(path); e == nil && (!i.Mode().IsRegular() || i.Mode()&os.ModeSymlink != 0) {
		return errors.New("refusing to replace a non-regular OBSGod file")
	}
	f, e := os.CreateTemp(filepath.Dir(path), ".obsgod-*")
	if e != nil {
		return e
	}
	name := f.Name()
	defer os.Remove(name)
	if e = f.Chmod(0600); e == nil {
		_, e = f.Write(b)
	}
	if e == nil {
		e = f.Sync()
	}
	closeErr := f.Close()
	if e != nil {
		return e
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(name, path)
}
func writeJSON(path string, v any) error {
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	return atomicWrite(path, append(b, '\n'))
}

// Prepare writes only inside OBSGod's isolated Flatpak config, while it is offline.
func Prepare(p Paths, s Settings, secret Secrets) error { return prepare(p, s, secret, false) }

func prepare(p Paths, s Settings, secret Secrets, visible bool) error {
	profile := filepath.Join(p.OBSConfig, "obs-studio/basic/profiles/OBSGod")
	mediaDir, replaySeconds, replayMemoryMB, err := MediaProfileValues(p)
	if err != nil {
		return err
	}
	if err = checkedMediaDirectory(mediaDir, true); err != nil {
		return err
	}
	for _, dir := range []string{p.OBSConfig, p.State, profile} {
		if e := privateDir(dir); e != nil {
			return e
		}
	}
	global := "[General]\nFirstRun=true\nConfigOnNewProfile=false\n\n[Basic]\nProfile=OBSGod\nProfileDir=OBSGod\nSceneCollection=OBSGod\nSceneCollectionFile=OBSGod\n\n[BasicWindow]\nPreviewEnabled=false\nSysTrayEnabled=true\nSysTrayWhenStarted=true\nWarnBeforeStartingStream=false\nWarnBeforeStoppingStream=false\n"
	if visible {
		global = strings.Replace(global, "SysTrayWhenStarted=true", "SysTrayWhenStarted=false", 1)
	}
	// OBS 30 uses global.ini; current OBS separates user preferences into
	// user.ini. FirstRun=true suppresses its interactive auto-config wizard.
	for _, name := range []string{"global.ini", "user.ini"} {
		if e := atomicWrite(filepath.Join(p.OBSConfig, "obs-studio", name), []byte(global)); e != nil {
			return e
		}
	}
	encoder := "ffmpeg_vaapi_tex"
	if s.Encoder == "x264" {
		encoder = "obs_x264"
	}
	ini := fmt.Sprintf("[General]\nName=OBSGod\n\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=%d\nOutputCY=%d\nFPSType=0\nFPSCommon=%d\nScaleType=bicubic\nColorFormat=NV12\nColorSpace=709\nColorRange=Partial\n\n[Output]\nMode=Advanced\n\n[AdvOut]\nTrackIndex=1\nEncoder=%s\nApplyServiceSettings=true\nUseRescale=false\nRecType=Standard\nRecFilePath=%s\nRecFormat2=mkv\nRecEncoder=none\nRecTracks=1\nRecRB=true\nRecRBTime=%d\nRecRBSize=%d\nFFOutputToFile=true\n\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n", s.OutputWidth(), s.OutputHeight(), s.FPS, encoder, filepath.ToSlash(mediaDir), replaySeconds, replayMemoryMB)
	if strings.ContainsAny(mediaDir, "\r\n") {
		return errors.New("unsupported newline in home directory")
	}
	if e := atomicWrite(filepath.Join(profile, "basic.ini"), []byte(ini)); e != nil {
		return e
	}
	enc := map[string]any{"bitrate": s.Bitrate, "rate_control": "CBR", "keyint_sec": 2, "profile": "high", "preset": "veryfast", "bf": 0, "vaapi_device": "/dev/dri/renderD128"}
	if s.Encoder == "vaapi" {
		enc["profile"] = 100
		enc["level"] = 41
		if s.OutputWidth() == 1920 && s.FPS == 60 {
			enc["level"] = 42
		}
	}
	if e := writeJSON(filepath.Join(profile, "streamEncoder.json"), enc); e != nil {
		return e
	}
	ws := map[string]any{"server_enabled": true, "server_port": 4457, "server_password": secret.OBSPassword, "auth_required": true, "alerts_enabled": false, "first_load": false}
	return writeJSON(filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json"), ws)
}
