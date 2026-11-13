package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func profileRequest(t *testing.T, p Paths, request any) (StreamProfileResult, error) {
	t.Helper()
	data, err := json.Marshal(request)
	if err != nil {
		t.Fatal(err)
	}
	return ManageStreamProfiles(context.Background(), p, bytes.NewReader(data))
}

func TestStreamProfilesExportImportPreservesPrivateStateAndIsOffline(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	beforeSecret, _ := os.ReadFile(p.Secrets)
	beforeConfig, _ := os.ReadFile(p.Config)
	saved, err := profileRequest(t, p, map[string]any{"action": "save", "name": "portable", "preset": "smooth-720p60"})
	if err != nil || !saved.OK || saved.Profile.FPS != 60 {
		t.Fatal(saved, err)
	}
	exported, err := profileRequest(t, p, map[string]any{"action": "export", "name": "portable"})
	if err != nil || !exported.OK || exported.Document == nil {
		t.Fatal(exported, err)
	}
	raw, _ := json.Marshal(exported)
	for _, private := range []string{"fixture-never-real", "obs_password", "server", "example.invalid", p.OBSConfig, p.Config} {
		if bytes.Contains(raw, []byte(private)) {
			t.Fatal("portable export leaked private material", private)
		}
	}
	imported, err := profileRequest(t, p, map[string]any{"action": "import", "name": "copy", "document": exported.Document})
	if err != nil || !imported.OK {
		t.Fatal(imported, err)
	}
	listing, err := profileRequest(t, p, map[string]any{"action": "list"})
	if err != nil || len(listing.Profiles) != 2 || listing.Profiles[0].Name != "copy" || listing.Profiles[1].Name != "portable" {
		t.Fatal(listing, err)
	}
	afterSecret, _ := os.ReadFile(p.Secrets)
	afterConfig, _ := os.ReadFile(p.Config)
	if !bytes.Equal(beforeSecret, afterSecret) || !bytes.Equal(beforeConfig, afterConfig) {
		t.Fatal("saving or inspecting portable profiles modified current configuration")
	}
	info, err := os.Stat(profileStorePath(p))
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("profile store must remain private", err)
	}
}

func TestStreamProfileApplyAndResetPreserveDestinationCredentialsAndIdle(t *testing.T) {
	p := testPaths(t)
	configured, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	configured.IdleStyle = "placeholder"
	configured.IdleText = "Private local banner"
	body, _ := json.Marshal(configured)
	if _, err = Configure(p, bytes.NewReader(body)); err != nil {
		t.Fatal(err)
	}
	_, before, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	applied, err := profileRequest(t, p, map[string]any{"action": "apply", "preset": "small-540p30"})
	if err != nil || !applied.OK {
		t.Fatal(applied, err)
	}
	current, secret, err := Load(p)
	if err != nil || current.Width != 960 || current.Height != 540 || current.Bitrate != 2500 || current.Server != configured.Server || current.IdleText != configured.IdleText || secret.StreamKey != before.StreamKey || secret.OBSPassword != before.OBSPassword {
		t.Fatal("profile failed to preserve local destination/credential/idle binding", current, err)
	}
	if secret.SettingsHash == before.SettingsHash {
		t.Fatal("changed settings were not rebound")
	}
	if _, err = profileRequest(t, p, map[string]any{"action": "reset"}); err != nil {
		t.Fatal(err)
	}
	reset, resetSecret, err := Load(p)
	if err != nil || reset.OutputWidth() != 1280 || reset.FPS != 30 || reset.Server != configured.Server || reset.IdleText != configured.IdleText || resetSecret.StreamKey != before.StreamKey {
		t.Fatal("reset modified private/local fields", err)
	}
}

func TestStreamProfileChangesAreBlockedByUnknownListener(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	beforeConfig, _ := os.ReadFile(p.Config)
	beforeSecret, _ := os.ReadFile(p.Secrets)
	listener, err := net.Listen("tcp", "127.0.0.1:"+Port)
	if err != nil {
		t.Skip("test port already occupied")
	}
	defer listener.Close()
	// An occupied port with no owned process is unknown output, never idle.
	if _, err = profileRequest(t, p, map[string]any{"action": "apply", "preset": "small-540p30"}); err == nil {
		t.Fatal("applied preferences underneath unknown output")
	}
	afterConfig, _ := os.ReadFile(p.Config)
	afterSecret, _ := os.ReadFile(p.Secrets)
	if !bytes.Equal(beforeConfig, afterConfig) || !bytes.Equal(beforeSecret, afterSecret) {
		t.Fatal("failed idle guard modified settings")
	}
	if preview, err := profileRequest(t, p, map[string]any{"action": "preview", "preset": "small-540p30"}); err != nil || !preview.OK {
		t.Fatal("offline preview should not require OBS idle", preview, err)
	}
}

func TestStreamProfilePrecedenceExplicitOverridesEnvironmentAndSaved(t *testing.T) {
	p := testPaths(t)
	t.Setenv("OBSGOD_DECK_FPS", "bad-private-environment")
	t.Setenv("OBSGOD_DECK_BITRATE", "6500")
	t.Setenv("OBSGOD_DECK_MICROPHONE", "true")
	fps := 60
	result, err := profileRequest(t, p, StreamProfileRequest{Action: "preview", Preset: "small-540p30", Overrides: &StreamProfileOverrides{FPS: &fps}})
	if err != nil || !result.OK || result.Profile.FPS != 60 || result.Profile.Bitrate != 6500 || !result.Profile.Microphone || result.Profile.Width != 960 {
		t.Fatal(result, err)
	}
	if _, err = profileRequest(t, p, map[string]any{"action": "preview", "preset": "balanced-720p30"}); err == nil || strings.Contains(err.Error(), "bad-private-environment") {
		t.Fatal("invalid effective environment override was accepted or echoed", err)
	}
}

func TestStreamProfilesRejectUnsafeNamesVersionsDimensionsAndSecretFields(t *testing.T) {
	p := testPaths(t)
	invalid := []string{
		`null`,
		`{"action":"preview","preset":"not-real"}`,
		`{"action":"save","name":"../escape"}`,
		`{"action":"save","name":"bad name"}`,
		`{"action":"preview","profile":{"version":2,"width":1280,"height":720,"bitrate":4500,"fps":30,"encoder":"vaapi","capture_mode":"game"}}`,
		`{"action":"preview","profile":{"version":1,"width":0,"height":0,"bitrate":4500,"fps":30,"encoder":"vaapi","capture_mode":"game"}}`,
		`{"action":"preview","profile":{"version":1,"width":1920,"height":720,"bitrate":4500,"fps":30,"encoder":"vaapi","capture_mode":"game"}}`,
		`{"action":"preview","profile":{"version":1,"width":1280,"height":720,"bitrate":4500,"fps":30,"encoder":"vaapi","capture_mode":"game","stream_key":"private-value"}}`,
		`{"action":"import","name":"safe","document":{"version":1,"profile":{"version":1,"width":1280,"height":720,"bitrate":4500,"fps":30,"encoder":"vaapi","capture_mode":"game"},"server":"rtmps://private.invalid/app"}}`,
		`{"action":"list"}{}`,
	}
	for _, body := range invalid {
		result, err := ManageStreamProfiles(context.Background(), p, strings.NewReader(body))
		if err == nil || result.OK {
			t.Errorf("accepted invalid profile request: %s", body)
		}
		if err != nil && strings.Contains(err.Error(), "private-value") {
			t.Fatal("error leaked unknown field value")
		}
	}
	if _, err := os.Stat(profileStorePath(p)); !os.IsNotExist(err) {
		t.Fatal("invalid input created profile store")
	}
}

func TestStreamProfilesGameBindingIsExplicitAndAmbiguousGamesDoNothing(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	if _, err := profileRequest(t, p, map[string]any{"action": "save", "name": "game", "preset": "smooth-720p60"}); err != nil {
		t.Fatal(err)
	}
	if _, err := profileRequest(t, p, map[string]any{"action": "bind-game", "name": "game", "game_id": "4242"}); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(p.Config)
	for _, game := range []GameIdentity{{State: "idle"}, {State: "ambiguous"}, {State: "unknown"}, {State: "running", AppID: 999}} {
		if changed, err := ApplyGameStreamProfile(context.Background(), p, game); changed || err != nil {
			t.Fatal("unverified/unbound game changed profile", game, changed, err)
		}
	}
	unchanged, _ := os.ReadFile(p.Config)
	if !bytes.Equal(before, unchanged) {
		t.Fatal("binding metadata implicitly applied profile")
	}
	changed, err := ApplyGameStreamProfile(context.Background(), p, GameIdentity{State: "running", AppID: 4242})
	if err != nil || !changed {
		t.Fatal(changed, err)
	}
	current, _, err := Load(p)
	if err != nil || current.FPS != 60 {
		t.Fatal("explicit new output failed to select verified game's profile", err)
	}
	if changed, err = ApplyGameStreamProfile(context.Background(), p, GameIdentity{State: "running", AppID: 4242}); changed || err != nil {
		t.Fatal("unchanged profile should be idempotent", changed, err)
	}
	if _, err = profileRequest(t, p, map[string]any{"action": "unbind-game", "game_id": "4242"}); err != nil {
		t.Fatal(err)
	}
	if _, err = profileRequest(t, p, map[string]any{"action": "delete", "name": "game"}); err != nil {
		t.Fatal(err)
	}
	listing, err := profileRequest(t, p, map[string]any{"action": "list"})
	if err != nil || len(listing.GameProfiles) != 0 || len(listing.Profiles) != 0 {
		t.Fatal("deleted profile retained a dangling game binding", listing, err)
	}
}

func TestStreamProfilesRejectSymlinkAndOversizedStore(t *testing.T) {
	p := testPaths(t)
	if err := privateDir(filepath.Dir(p.Config)); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(t.TempDir(), "unrelated")
	original := []byte(`{"version":1,"profiles":{}}`)
	if err := os.WriteFile(target, original, 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, profileStorePath(p)); err != nil {
		t.Skip("symlinks unavailable")
	}
	if _, err := profileRequest(t, p, map[string]any{"action": "save", "name": "safe"}); err == nil {
		t.Fatal("followed profile store symlink")
	}
	after, _ := os.ReadFile(target)
	if !bytes.Equal(original, after) {
		t.Fatal("modified unrelated file")
	}
	if err := os.Remove(profileStorePath(p)); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(profileStorePath(p), bytes.Repeat([]byte(" "), 1024*1024+1), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := profileRequest(t, p, map[string]any{"action": "list"}); err == nil {
		t.Fatal("accepted oversized profile store")
	}
}

func TestOutputResolutionMigrationAndPrepareKeeps720pCanvas(t *testing.T) {
	p := testPaths(t)
	settings, err := Configure(p, strings.NewReader(fixtureSettings))
	if err != nil {
		t.Fatal(err)
	}
	legacyHash := settingsHash(settings)
	if settings.Width != 0 || settings.Height != 0 || settings.OutputWidth() != 1280 || settings.OutputHeight() != 720 {
		t.Fatal("legacy settings dimension migration changed")
	}
	raw, _ := json.Marshal(settings)
	if bytes.Contains(raw, []byte(`"width"`)) || bytes.Contains(raw, []byte(`"height"`)) {
		t.Fatal("legacy hash representation changed")
	}
	settings.Width, settings.Height, settings.FPS = 1920, 1080, 60
	data, _ := json.Marshal(settings)
	if _, err = Configure(p, bytes.NewReader(data)); err != nil {
		t.Fatal(err)
	}
	settings, secret, err := Load(p)
	if err != nil || secret.SettingsHash == legacyHash {
		t.Fatal("new dimensions failed to rebind", err)
	}
	if err = Prepare(p, settings, secret); err != nil {
		t.Fatal(err)
	}
	ini, err := os.ReadFile(filepath.Join(p.OBSConfig, "obs-studio/basic/profiles/OBSGod/basic.ini"))
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{"BaseCX=1280\nBaseCY=720", "OutputCX=1920\nOutputCY=1080", "FPSCommon=60"} {
		if !bytes.Contains(ini, []byte(expected)) {
			t.Fatal("prepare did not preserve canvas/scaled output", expected)
		}
	}
	enc, err := os.ReadFile(filepath.Join(p.OBSConfig, "obs-studio/basic/profiles/OBSGod/streamEncoder.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(enc, []byte(`"level": 42`)) {
		t.Fatal("1080p60 was constrained to H264 level4.1")
	}
	settings.Height = 720
	if settings.Validate() == nil {
		t.Fatal("incompatible dimension pair accepted")
	}
}

func TestStreamPresetsNeverClaimDeviceQualification(t *testing.T) {
	for _, preset := range StreamPresets() {
		if preset.HardwareQualified || preset.Profile.Validate() != nil || preset.Description == "" {
			t.Fatal("invalid or unsupported preset promise", preset)
		}
	}
}

func TestStreamProfileEnvironmentAppliesOnlyBeforeExplicitNewOutput(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	t.Setenv("OBSGOD_DECK_FPS", "60")
	before, _ := os.ReadFile(p.Config)
	// List/preview/validation never apply the environment to persistent settings.
	if _, err := profileRequest(t, p, map[string]any{"action": "list"}); err != nil {
		t.Fatal(err)
	}
	if _, err := profileRequest(t, p, map[string]any{"action": "preview"}); err != nil {
		t.Fatal(err)
	}
	unchanged, _ := os.ReadFile(p.Config)
	if !bytes.Equal(before, unchanged) {
		t.Fatal("read-only profile action applied environment")
	}
	changed, err := ApplyGameStreamProfile(context.Background(), p, GameIdentity{State: "idle"})
	if err != nil || !changed {
		t.Fatal("explicit output did not resolve environment over current preferences", changed, err)
	}
	current, _, err := Load(p)
	if err != nil || current.FPS != 60 {
		t.Fatal(current, err)
	}
}

func TestStreamProfileCancelledApplyDoesNotModifySettings(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(p.Config)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := ManageStreamProfiles(ctx, p, strings.NewReader(`{"action":"apply","preset":"smooth-720p60"}`)); err == nil {
		t.Fatal("applied profile after caller cancellation")
	}
	after, _ := os.ReadFile(p.Config)
	if !bytes.Equal(before, after) {
		t.Fatal("cancelled profile apply modified settings")
	}
}
