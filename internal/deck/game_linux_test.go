//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGameIdentityIsOwnedUnambiguousAndNeverSteam(t *testing.T) {
	root := t.TempDir()
	for _, p := range []struct{ pid, comm, env, state string }{
		{"1", "game", "SteamAppId=4242\x00", "S"},
		{"2", "steamwebhelper", "SteamAppId=769\x00", "S"},
		{"3", "obs", "SteamAppId=111\x00", "S"},
		{"4", "game", "SteamAppId=999\x00", "Z"},
		{"5", "helper", "SteamAppId=4242\x00", "S"},
	} {
		proc := filepath.Join(root, p.pid)
		if err := os.Mkdir(proc, 0700); err != nil {
			t.Fatal(err)
		}
		for name, data := range map[string]string{"comm": p.comm, "environ": p.env, "status": "State:\t" + p.state + "\n"} {
			if err := os.WriteFile(filepath.Join(proc, name), []byte(data), 0600); err != nil {
				t.Fatal(err)
			}
		}
	}
	ids := gameAppIDs(context.Background(), root, os.Getuid())
	if len(ids) != 1 || ids[0] != 4242 {
		t.Fatalf("wrong selected apps: %v", ids)
	}
	if got := chooseGame(ids, 0); got.State != "running" || got.AppID != 4242 {
		t.Fatal(got)
	}
	if got := chooseGame([]uint32{4242, 7777}, 0); got.State != "ambiguous" || got.AppID != 0 {
		t.Fatal(got)
	}
	if got := chooseGame([]uint32{4242, 7777}, 7777); got.AppID != 7777 {
		t.Fatal(got)
	}
	if got := chooseGame(nil, 7777); got.State != "idle" || got.AppID != 0 {
		t.Fatal(got)
	}
	data, _ := json.Marshal(chooseGame(ids, 0))
	if strings.Contains(string(data), "4242") {
		t.Fatal("app identity leaked in public status")
	}
	for _, raw := range []string{"SteamAppId=0\x00", "SteamAppId=769\x00", "SteamAppId=-1\x00", "SteamAppId=4294967296\x00", "SteamAppId=bad\x00"} {
		if steamAppID([]byte(raw)) != 0 {
			t.Fatal(raw)
		}
	}
	for _, raw := range []string{"GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 0", "GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 769", "GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 12, 34", "other = 12"} {
		if parseGraphicsApp([]byte(raw)) != 0 {
			t.Fatal(raw)
		}
	}
	if parseGraphicsApp([]byte("GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 4242\n")) != 4242 {
		t.Fatal("valid graphics focus not parsed")
	}
}

func TestCaptureModeChangePreservesCredentialsAndRejectsUnsafeOutput(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	_, before, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = SetCaptureMode(context.Background(), p, strings.NewReader(`{"capture_mode":"game"}`)); err != nil {
		t.Fatal(err)
	}
	settings, after, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if settings.CaptureMode != "game" || before.StreamKey != after.StreamKey || before.OBSPassword != after.OBSPassword || before.SettingsHash == after.SettingsHash {
		t.Fatal("mode failed to preserve bound credentials")
	}
	for _, bad := range []string{`{}`, `{"capture_mode":"desktop"}`, `{"capture_mode":"screen","stream_key":"no"}`, `{"capture_mode":"screen"}{}`} {
		if _, err = SetCaptureMode(context.Background(), p, strings.NewReader(bad)); err == nil {
			t.Fatal("bad mode accepted")
		}
	}
	requests := startManagedFixture(t, false, false, true)
	if _, err = SetCaptureMode(context.Background(), p, strings.NewReader(`{"capture_mode":"screen"}`)); err == nil {
		t.Fatal("changed capture mode during active output")
	}
	settings, _, err = Load(p)
	if err != nil || settings.CaptureMode != "game" {
		t.Fatal("unsafe change reached disk")
	}
	for len(requests) > 0 {
		q := <-requests
		if strings.HasPrefix(q.Type, "Set") || q.Type == "StartStream" || q.Type == "StopStream" {
			t.Fatal("mode change mutated live OBS", q.Type)
		}
	}
}
