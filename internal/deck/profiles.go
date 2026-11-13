package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"time"
)

// StreamProfile is a portable set of managed output preferences. Destinations,
// credentials, local media paths and device identifiers deliberately have no
// representation here. Applying one retains the current destination/key pair.
type StreamProfile struct {
	Version     int    `json:"version"`
	Width       int    `json:"width"`
	Height      int    `json:"height"`
	Bitrate     int    `json:"bitrate"`
	FPS         int    `json:"fps"`
	Encoder     string `json:"encoder"`
	Microphone  bool   `json:"microphone"`
	CaptureMode string `json:"capture_mode"`
}

type StreamProfileOverrides struct {
	Width       *int    `json:"width,omitempty"`
	Height      *int    `json:"height,omitempty"`
	Bitrate     *int    `json:"bitrate,omitempty"`
	FPS         *int    `json:"fps,omitempty"`
	Encoder     *string `json:"encoder,omitempty"`
	Microphone  *bool   `json:"microphone,omitempty"`
	CaptureMode *string `json:"capture_mode,omitempty"`
}

type StreamPreset struct {
	Name              string        `json:"name"`
	Label             string        `json:"label"`
	Description       string        `json:"description"`
	HardwareQualified bool          `json:"hardware_qualified"`
	Profile           StreamProfile `json:"profile"`
}

type NamedStreamProfile struct {
	Name    string        `json:"name"`
	Profile StreamProfile `json:"profile"`
}

type StreamProfileDocument struct {
	Version int           `json:"version"`
	Profile StreamProfile `json:"profile"`
}

type streamProfileStore struct {
	Version      int                      `json:"version"`
	Profiles     map[string]StreamProfile `json:"profiles"`
	GameProfiles map[string]string        `json:"game_profiles,omitempty"`
}

type StreamProfileRequest struct {
	Action    string                  `json:"action"`
	Name      string                  `json:"name,omitempty"`
	Preset    string                  `json:"preset,omitempty"`
	Profile   *StreamProfile          `json:"profile,omitempty"`
	Overrides *StreamProfileOverrides `json:"overrides,omitempty"`
	GameID    string                  `json:"game_id,omitempty"`
	Document  *StreamProfileDocument  `json:"document,omitempty"`
}

type StreamProfileResult struct {
	OK              bool                   `json:"ok"`
	Version         int                    `json:"version"`
	Action          string                 `json:"action"`
	Message         string                 `json:"message"`
	Profile         *StreamProfile         `json:"profile,omitempty"`
	Profiles        []NamedStreamProfile   `json:"profiles,omitempty"`
	Presets         []StreamPreset         `json:"presets,omitempty"`
	GameProfiles    map[string]string      `json:"game_profiles,omitempty"`
	Current         *StreamProfile         `json:"current,omitempty"`
	Warnings        []string               `json:"warnings,omitempty"`
	Document        *StreamProfileDocument `json:"document,omitempty"`
	RequiresRestart bool                   `json:"requires_restart,omitempty"`
}

var streamProfileName = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`)
var steamGameID = regexp.MustCompile(`^[1-9][0-9]{0,9}$`)

func validSteamGameID(id string) bool {
	if !steamGameID.MatchString(id) {
		return false
	}
	value, err := strconv.ParseUint(id, 10, 32)
	return err == nil && value != 0 && value != 769
}

func validOutputDimensions(width, height int) bool {
	return (width == 960 && height == 540) || (width == 1280 && height == 720) || (width == 1920 && height == 1080)
}

func profileFromSettings(s Settings) StreamProfile {
	return StreamProfile{Version: 1, Width: s.OutputWidth(), Height: s.OutputHeight(), Bitrate: s.Bitrate, FPS: s.FPS, Encoder: s.Encoder, Microphone: s.Microphone, CaptureMode: s.CaptureModeName()}
}

func (p StreamProfile) Validate() error {
	if p.Version != 1 {
		return errors.New("unsupported stream profile version; use version 1")
	}
	if !validOutputDimensions(p.Width, p.Height) {
		return errors.New("portable profile requires explicit 960x540, 1280x720 or 1920x1080 dimensions")
	}
	if p.CaptureMode != "screen" && p.CaptureMode != "game" {
		return errors.New("portable profile requires an explicit screen or game capture mode")
	}
	// Delegate the tunable bounds to the same validator as Desktop configuration.
	s := p.settings(DefaultSettings())
	s.Server = "rtmps://profile-validation.invalid/app"
	return s.Validate()
}

func (p StreamProfile) settings(s Settings) Settings {
	s.Width, s.Height, s.Bitrate, s.FPS, s.Encoder, s.Microphone, s.CaptureMode = p.Width, p.Height, p.Bitrate, p.FPS, p.Encoder, p.Microphone, p.CaptureMode
	return s
}

func StreamPresets() []StreamPreset {
	base := profileFromSettings(DefaultSettings())
	small := base
	small.Width, small.Height, small.Bitrate = 960, 540, 2500
	smooth := base
	smooth.FPS, smooth.Bitrate = 60, 6000
	return []StreamPreset{
		{"small-540p30", "Smaller 540p / 30 FPS", "Lower output resolution and bandwidth; actual game, battery and encoder performance must be checked on your Deck.", false, small},
		{"balanced-720p30", "Balanced 720p / 30 FPS", "The existing 720p30 starting point; a preset is not proof of picture, sound or hardware performance.", false, base},
		{"smooth-720p60", "Smoother 720p / 60 FPS", "More frames and bandwidth may increase game load, power use and dropped frames. Test locally first.", false, smooth},
	}
}

func profileWarnings(p StreamProfile) []string {
	warnings := []string{"Presets are starting points, not hardware-qualified promises. Run a local recording and check game performance, picture and sound before broadcasting.", "A profile never starts streaming. Destination and stream key stay on this device; per-game bindings apply only before an explicit cold Start/local recording, never automatically during transitions."}
	if p.FPS == 60 || p.Width == 1920 {
		warnings = append(warnings, "60 FPS or 1080p can increase encoder/GPU load and power use; lower resolution or FPS if the game or output stutters.")
	}
	if p.Encoder == "x264" {
		warnings = append(warnings, "x264 uses the CPU and may reduce game performance or battery life. VAAPI requires a working supported hardware encoder.")
	}
	if p.CaptureMode == "game" {
		warnings = append(warnings, "Game-only selects video only; system audio is not isolated to one application. Unverified game capture uses the configured idle scene.")
	}
	return warnings
}

func profileStorePath(p Paths) string {
	return filepath.Join(filepath.Dir(p.Config), "stream-profiles.json")
}

func readStreamProfiles(p Paths) (streamProfileStore, error) {
	store := streamProfileStore{Version: 1, Profiles: map[string]StreamProfile{}, GameProfiles: map[string]string{}}
	info, err := os.Lstat(profileStorePath(p))
	if os.IsNotExist(err) {
		return store, nil
	}
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 1024*1024 {
		return store, errors.New("stream profiles must be a regular private file of at most 1 MiB")
	}
	f, err := os.Open(profileStorePath(p))
	if err != nil {
		return store, errors.New("could not read stream profiles")
	}
	defer f.Close()
	d := json.NewDecoder(io.LimitReader(f, 1024*1024+1))
	d.DisallowUnknownFields()
	if d.Decode(&store) != nil {
		return store, errors.New("invalid stream profile file")
	}
	var extra any
	if d.Decode(&extra) != io.EOF || store.Version != 1 || len(store.Profiles) > 64 || len(store.GameProfiles) > 256 {
		return store, errors.New("unsupported or oversized stream profile file")
	}
	if store.Profiles == nil {
		store.Profiles = map[string]StreamProfile{}
	}
	if store.GameProfiles == nil {
		store.GameProfiles = map[string]string{}
	}
	for name, profile := range store.Profiles {
		if !streamProfileName.MatchString(name) || profile.Validate() != nil {
			return store, errors.New("saved stream profile is invalid; restore a valid version 1 file")
		}
	}
	for game, name := range store.GameProfiles {
		if !validSteamGameID(game) {
			return store, errors.New("saved game profile binding is invalid")
		}
		if _, ok := store.Profiles[name]; !ok {
			return store, errors.New("a game binding refers to a missing saved profile")
		}
	}
	return store, nil
}

func writeStreamProfiles(p Paths, store streamProfileStore) error {
	if err := writeJSON(profileStorePath(p), store); err != nil {
		return errors.New("could not save stream profiles; check the private configuration directory and free space")
	}
	return nil
}

func profileCurrent(p Paths) *StreamProfile {
	settings := DefaultSettings()
	if readJSON(p.Config, &settings) != nil || settings.Validate() != nil {
		return nil
	}
	profile := profileFromSettings(settings)
	return &profile
}

func overlayStreamProfile(p StreamProfile, o StreamProfileOverrides) StreamProfile {
	if o.Width != nil {
		p.Width = *o.Width
	}
	if o.Height != nil {
		p.Height = *o.Height
	}
	if o.Bitrate != nil {
		p.Bitrate = *o.Bitrate
	}
	if o.FPS != nil {
		p.FPS = *o.FPS
	}
	if o.Encoder != nil {
		p.Encoder = *o.Encoder
	}
	if o.Microphone != nil {
		p.Microphone = *o.Microphone
	}
	if o.CaptureMode != nil {
		p.CaptureMode = *o.CaptureMode
	}
	return p
}

func environmentStreamProfile(explicit *StreamProfileOverrides) (StreamProfileOverrides, error) {
	if explicit == nil {
		explicit = &StreamProfileOverrides{}
	}
	var o StreamProfileOverrides
	for key, target := range map[string]**int{"WIDTH": &o.Width, "HEIGHT": &o.Height, "BITRATE": &o.Bitrate, "FPS": &o.FPS} {
		if (key == "WIDTH" && explicit.Width != nil) || (key == "HEIGHT" && explicit.Height != nil) || (key == "BITRATE" && explicit.Bitrate != nil) || (key == "FPS" && explicit.FPS != nil) {
			continue
		}
		if value := os.Getenv("OBSGOD_DECK_" + key); value != "" {
			n, err := strconv.Atoi(value)
			if err != nil {
				return o, errors.New("invalid managed stream-profile environment override")
			}
			*target = &n
		}
	}
	if value := os.Getenv("OBSGOD_DECK_ENCODER"); value != "" && explicit.Encoder == nil {
		o.Encoder = &value
	}
	if value := os.Getenv("OBSGOD_DECK_CAPTURE_MODE"); value != "" && explicit.CaptureMode == nil {
		o.CaptureMode = &value
	}
	if value, present := os.LookupEnv("OBSGOD_DECK_MICROPHONE"); present && explicit.Microphone == nil {
		v, err := strconv.ParseBool(value)
		if err != nil {
			return o, errors.New("OBSGOD_DECK_MICROPHONE must be true or false")
		}
		o.Microphone = &v
	}
	return o, nil
}

func resolveStreamProfile(p Paths, store streamProfileStore, input StreamProfileRequest) (StreamProfile, error) {
	candidate := profileFromSettings(DefaultSettings())
	if current := profileCurrent(p); current != nil {
		candidate = *current
	}
	name := input.Name
	if name == "" && input.Action != "save" {
		name = os.Getenv("OBSGOD_DECK_PROFILE")
	}
	if input.GameID != "" {
		if !validSteamGameID(input.GameID) {
			return candidate, errors.New("choose a numeric Steam game ID")
		}
		if input.Name == "" {
			var ok bool
			name, ok = store.GameProfiles[input.GameID]
			if !ok {
				return candidate, errors.New("no saved profile is bound to that game; choose a profile explicitly")
			}
		}
	}
	if name != "" && input.Preset == "" && input.Profile == nil && input.Action != "save" {
		var ok bool
		candidate, ok = store.Profiles[name]
		if !ok {
			return candidate, errors.New("saved stream profile was not found; list profiles or choose a preset")
		}
	}
	if input.Preset != "" {
		found := false
		for _, preset := range StreamPresets() {
			if preset.Name == input.Preset {
				candidate = preset.Profile
				found = true
				break
			}
		}
		if !found {
			return candidate, errors.New("unknown stream preset; list available presets")
		}
	}
	if input.Profile != nil {
		candidate = *input.Profile
	}
	// Explicit request/CLI overrides take precedence over environment, which
	// overrides the selected saved profile/current settings/defaults.
	environment, err := environmentStreamProfile(input.Overrides)
	if err != nil {
		return candidate, err
	}
	candidate = overlayStreamProfile(candidate, environment)
	if input.Overrides != nil {
		candidate = overlayStreamProfile(candidate, *input.Overrides)
	}
	return candidate, candidate.Validate()
}

// ManageStreamProfiles is called under the managed control lock for mutations.
// Inspect/export/preview remain offline. Applying preferences requires OBS to
// be positively absent, including unconfirmed listeners, so settings cannot be
// saved underneath a live output or silently fail to reach an existing encoder.
func ManageStreamProfiles(ctx context.Context, p Paths, reader io.Reader) (StreamProfileResult, error) {
	var input StreamProfileRequest
	result := StreamProfileResult{Version: 1}
	d := json.NewDecoder(io.LimitReader(reader, 1024*1024+1))
	d.DisallowUnknownFields()
	if d.Decode(&input) != nil {
		return result, errors.New("invalid stream-profile JSON")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return result, errors.New("provide exactly one stream-profile request")
	}
	result.Action = input.Action
	store, err := readStreamProfiles(p)
	if err != nil {
		return result, err
	}
	switch input.Action {
	case "list":
		result.Presets = StreamPresets()
		result.Current = profileCurrent(p)
		result.GameProfiles = store.GameProfiles
		names := make([]string, 0, len(store.Profiles))
		for name := range store.Profiles {
			names = append(names, name)
		}
		sort.Strings(names)
		result.Profiles = make([]NamedStreamProfile, 0, len(names))
		for _, name := range names {
			result.Profiles = append(result.Profiles, NamedStreamProfile{name, store.Profiles[name]})
		}
		result.Message = "Profiles inspected locally; no OBS connection or output was started"
	case "export":
		var profile StreamProfile
		if input.Name != "" {
			var ok bool
			profile, ok = store.Profiles[input.Name]
			if !ok {
				return result, errors.New("saved stream profile was not found")
			}
		} else if current := profileCurrent(p); current != nil {
			profile = *current
		} else {
			return result, errors.New("complete Desktop setup or choose a saved profile before exporting")
		}
		result.Document = &StreamProfileDocument{Version: 1, Profile: profile}
		result.Message = "Portable profile exported without destination, credentials, media paths or device identifiers"
	case "import":
		if !streamProfileName.MatchString(input.Name) || input.Document == nil || input.Document.Version != 1 || input.Document.Profile.Validate() != nil {
			return result, errors.New("import requires a safe profile name and a valid version 1 portable document")
		}
		if len(store.Profiles) >= 64 {
			if _, exists := store.Profiles[input.Name]; !exists {
				return result, errors.New("at most 64 saved stream profiles are supported")
			}
		}
		store.Profiles[input.Name] = input.Document.Profile
		if err = writeStreamProfiles(p, store); err != nil {
			return result, err
		}
		result.Profile = &input.Document.Profile
		result.Message = "Profile imported locally; it was not applied and no output was started"
	case "delete":
		if _, ok := store.Profiles[input.Name]; !ok {
			return result, errors.New("saved stream profile was not found")
		}
		delete(store.Profiles, input.Name)
		for game, name := range store.GameProfiles {
			if name == input.Name {
				delete(store.GameProfiles, game)
			}
		}
		if err = writeStreamProfiles(p, store); err != nil {
			return result, err
		}
		result.Message = "Saved profile and its game suggestions removed; current settings and media are unchanged"
	case "unbind-game":
		if !validSteamGameID(input.GameID) {
			return result, errors.New("choose a numeric Steam game ID")
		}
		delete(store.GameProfiles, input.GameID)
		if err = writeStreamProfiles(p, store); err != nil {
			return result, err
		}
		result.GameProfiles = store.GameProfiles
		result.Message = "Game profile binding removed; future explicit starts use current preferences"
	case "bind-game":
		if !validSteamGameID(input.GameID) {
			return result, errors.New("choose a numeric Steam game ID")
		}
		if _, ok := store.Profiles[input.Name]; !ok {
			return result, errors.New("choose an existing saved stream profile")
		}
		if len(store.GameProfiles) >= 256 {
			if _, exists := store.GameProfiles[input.GameID]; !exists {
				return result, errors.New("at most 256 game profile suggestions are supported")
			}
		}
		store.GameProfiles[input.GameID] = input.Name
		if err = writeStreamProfiles(p, store); err != nil {
			return result, err
		}
		result.GameProfiles = store.GameProfiles
		result.Message = "Game profile suggestion saved; it applies only on your next explicit cold Start or local recording, never during game transitions"
	case "preview", "validate", "save", "apply", "reset":
		var profile StreamProfile
		if input.Action == "reset" {
			profile = profileFromSettings(DefaultSettings())
		} else {
			profile, err = resolveStreamProfile(p, store, input)
			if err != nil {
				return result, err
			}
		}
		result.Profile = &profile
		result.Warnings = profileWarnings(profile)
		switch input.Action {
		case "save":
			if !streamProfileName.MatchString(input.Name) {
				return result, errors.New("profile name must use 1–64 ASCII letters, digits, periods, underscores or hyphens and start with a letter or digit")
			}
			if len(store.Profiles) >= 64 {
				if _, exists := store.Profiles[input.Name]; !exists {
					return result, errors.New("at most 64 saved stream profiles are supported")
				}
			}
			store.Profiles[input.Name] = profile
			if err = writeStreamProfiles(p, store); err != nil {
				return result, err
			}
			result.Message = "Profile saved locally; current settings and outputs are unchanged"
		case "apply", "reset":
			settings, _, loadErr := Load(p)
			if loadErr != nil {
				return result, loadErr
			}
			if err = profilesRequireClosedOBS(ctx, p); err != nil {
				return result, err
			}
			// A retiring observer owns its own lease; wait before changing capture
			// settings, then inspect presence again. Never kill OBS to force a change.
			leaseCtx, cancel := context.WithTimeout(ctx, 6*time.Second)
			unlock, lockErr := Lock(leaseCtx, captureWatchPaths(p))
			cancel()
			if lockErr != nil {
				return result, errors.New("the previous capture observer is finishing; wait and retry")
			}
			defer unlock()
			if err = profilesRequireClosedOBS(ctx, p); err != nil {
				return result, err
			}
			settings = profile.settings(settings)
			data, marshalErr := json.Marshal(settings)
			if marshalErr != nil {
				return result, errors.New("could not prepare profile settings")
			}
			if _, err = Configure(p, bytes.NewReader(data)); err != nil {
				return result, err
			}
			result.RequiresRestart = false
			result.Message = "Output preferences saved for the next explicit Start or local recording; no broadcast was started"
		default:
			result.Message = "Profile validated and previewed without connecting to OBS or changing settings"
		}
	default:
		return result, errors.New("choose list, preview, validate, save, apply, reset, export, import, delete, bind-game or unbind-game")
	}
	result.OK = true
	return result, nil
}

func profilesRequireClosedOBS(ctx context.Context, p Paths) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	process, listener := presence(p)
	if process != "absent" || listener {
		return errors.New("close idle managed OBS with Restart OBS before applying output preferences; active or unknown output blocks profile changes")
	}
	return nil
}

// ApplyBoundGameProfile is used exclusively by an explicit new Start/Test/local
// recording/replay action. Observers and status must never call this function.
// An ambiguous/idle game leaves current preferences unchanged.
func ApplyBoundGameProfile(ctx context.Context, p Paths) (bool, error) {
	return ApplyGameStreamProfile(ctx, p, DiscoverGame(ctx))
}

func ApplyGameStreamProfile(ctx context.Context, p Paths, game GameIdentity) (bool, error) {
	store, err := readStreamProfiles(p)
	if err != nil {
		return false, err
	}
	name := os.Getenv("OBSGOD_DECK_PROFILE")
	if name == "" && game.State == "running" && game.AppID != 0 {
		name = store.GameProfiles[strconv.FormatUint(uint64(game.AppID), 10)]
	}
	if name == "" {
		hasOverride := false
		for _, key := range []string{"WIDTH", "HEIGHT", "BITRATE", "FPS", "ENCODER", "CAPTURE_MODE"} {
			if os.Getenv("OBSGOD_DECK_"+key) != "" {
				hasOverride = true
			}
		}
		if _, present := os.LookupEnv("OBSGOD_DECK_MICROPHONE"); present {
			hasOverride = true
		}
		if !hasOverride {
			return false, nil
		}
	}
	request := StreamProfileRequest{Action: "apply", Name: name}
	profile, err := resolveStreamProfile(p, store, request)
	if err != nil {
		return false, err
	}
	settings, _, err := Load(p)
	if err != nil {
		return false, err
	}
	if profileFromSettings(settings) == profile {
		return false, nil
	}
	data, err := json.Marshal(request)
	if err != nil {
		return false, errors.New("could not prepare bound game profile")
	}
	_, err = ManageStreamProfiles(ctx, p, bytes.NewReader(data))
	return err == nil, err
}
