package deck

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func testPaths(t *testing.T) Paths {
	t.Helper()
	d := t.TempDir()
	return Paths{Config: filepath.Join(d, "config/deck.json"), Secrets: filepath.Join(d, "config/secrets.json"), OBSConfig: filepath.Join(d, "obs"), State: filepath.Join(d, "state"), Videos: filepath.Join(d, "videos")}
}

const fixtureSettings = `{"version":1,"server":"rtmps://example.invalid/app","bitrate":4500,"fps":30,"encoder":"vaapi","microphone":false,"stream_key":"fixture-never-real"}`

func TestChangingDestinationRequiresItsOwnExplicitKey(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	beforeSettings, _ := os.ReadFile(p.Config)
	beforeSecrets, _ := os.ReadFile(p.Secrets)
	changed := strings.Replace(fixtureSettings, "example.invalid", "other.invalid", 1)
	if _, err := Configure(p, strings.NewReader(strings.Replace(changed, "fixture-never-real", "", 1))); err == nil {
		t.Fatal("silently sent the saved key to another destination")
	}
	afterSettings, _ := os.ReadFile(p.Config)
	afterSecrets, _ := os.ReadFile(p.Secrets)
	if !bytes.Equal(beforeSettings, afterSettings) || !bytes.Equal(beforeSecrets, afterSecrets) {
		t.Fatal("refused destination change modified saved configuration")
	}
	if _, err := Configure(p, strings.NewReader(strings.Replace(changed, "fixture-never-real", "second-fixture-not-real", 1))); err != nil {
		t.Fatal(err)
	}
	settings, secret, err := Load(p)
	if err != nil || settings.Server != "rtmps://other.invalid/app" || secret.StreamKey != "second-fixture-not-real" {
		t.Fatal("explicit new destination/key did not bind together", err)
	}
}

func TestBlankKeyCannotRepairAMismatchedPairIntoAnotherDestination(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	originalSettings, _ := os.ReadFile(p.Config)
	other := strings.Replace(strings.Replace(fixtureSettings, "example.invalid", "other.invalid", 1), "fixture-never-real", "other-destination-fixture-key", 1)
	if _, err := Configure(p, strings.NewReader(other)); err != nil {
		t.Fatal(err)
	}
	// Model the documented second-write failure: new server B credentials were
	// committed but server A's old settings remained on disk.
	if err := atomicWrite(p.Config, originalSettings); err != nil {
		t.Fatal(err)
	}
	beforeSecret, _ := os.ReadFile(p.Secrets)
	blank := strings.Replace(fixtureSettings, "fixture-never-real", "", 1)
	if _, err := Configure(p, strings.NewReader(blank)); err == nil {
		t.Fatal("rebound destination B's secret to old destination A")
	}
	afterSettings, _ := os.ReadFile(p.Config)
	afterSecret, _ := os.ReadFile(p.Secrets)
	if !bytes.Equal(originalSettings, afterSettings) || !bytes.Equal(beforeSecret, afterSecret) {
		t.Fatal("mismatched binding refusal changed the saved pair")
	}
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal("explicit owner-entered key could not repair the mismatched pair", err)
	}
	_, secret, err := Load(p)
	if err != nil || secret.StreamKey != "fixture-never-real" {
		t.Fatal("repair did not bind the intended destination/key", err)
	}
}

func TestPrivateConfigAndSecretPreservation(t *testing.T) {
	p := testPaths(t)
	s, e := Configure(p, strings.NewReader(fixtureSettings))
	if e != nil {
		t.Fatal(e)
	}
	_, secret, e := Load(p)
	if e != nil {
		t.Fatal(e)
	}
	if secret.StreamKey != "fixture-never-real" || len(secret.OBSPassword) != 64 {
		t.Fatal("credentials did not roundtrip")
	}
	settingsJSON, _ := json.Marshal(s)
	if bytes.Contains(settingsJSON, []byte(secret.StreamKey)) {
		t.Fatal("settings contain stream key")
	}
	if _, e = Configure(p, strings.NewReader(strings.Replace(fixtureSettings, "fixture-never-real", "", 1))); e != nil {
		t.Fatal(e)
	}
	_, saved, e := Load(p)
	if e != nil || saved != secret {
		t.Fatal("blank key did not preserve credentials")
	}
	if e = Prepare(p, s, secret); e != nil {
		t.Fatal(e)
	}
	for _, path := range []string{p.Config, p.Secrets, filepath.Join(p.OBSConfig, "obs-studio/plugin_config/obs-websocket/config.json")} {
		i, e := os.Stat(path)
		if e != nil || i.Mode().Perm() != 0600 {
			t.Errorf("non-private file %s", path)
		}
	}
	i, e := os.Stat(filepath.Dir(p.Secrets))
	if e != nil || i.Mode().Perm() != 0700 {
		t.Fatal("credential directory not private")
	}
}

func TestRejectInvalidSettingsAndSecretPaths(t *testing.T) {
	for _, body := range []string{`{}`, `null`, fixtureSettings + `{}`, strings.Replace(fixtureSettings, "rtmps://example.invalid/app", "https://example.invalid/app", 1), strings.Replace(fixtureSettings, "4500", "99", 1), strings.Replace(fixtureSettings, `"stream_key":"fixture-never-real"`, `"stream_key":""`, 1), strings.Replace(fixtureSettings, "rtmps://example.invalid/app", "rtmps://user:secret@example.invalid/app", 1)} {
		if _, e := Configure(testPaths(t), strings.NewReader(body)); e == nil {
			t.Errorf("accepted invalid settings: %s", body)
		}
	}
	p := testPaths(t)
	if _, e := Configure(p, strings.NewReader(fixtureSettings)); e != nil {
		t.Fatal(e)
	}
	if e := os.Chmod(p.Secrets, 0644); e != nil {
		t.Fatal(e)
	}
	if _, _, e := Load(p); e == nil {
		t.Fatal("accepted public credentials")
	}
	if e := os.Remove(p.Secrets); e != nil {
		t.Fatal(e)
	}
	target := filepath.Join(t.TempDir(), "unrelated")
	if e := os.WriteFile(target, []byte("untouched"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.Symlink(target, p.Secrets); e != nil {
		t.Skip("symlinks unavailable")
	}
	if _, e := Configure(p, strings.NewReader(fixtureSettings)); e == nil {
		t.Fatal("followed credential symlink")
	}
	b, _ := os.ReadFile(target)
	if string(b) != "untouched" {
		t.Fatal("modified unrelated file")
	}
}

func TestCaptureRejectsBlankButAcceptsRealPixels(t *testing.T) {
	im := image.NewRGBA(image.Rect(0, 0, 160, 100))
	var buffer bytes.Buffer
	encode := func() string {
		buffer.Reset()
		if e := png.Encode(&buffer, im); e != nil {
			t.Fatal(e)
		}
		return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buffer.Bytes())
	}
	if NonblankCapture(encode()) {
		t.Fatal("transparent image accepted")
	}
	for y := 0; y < 100; y++ {
		for x := 0; x < 160; x++ {
			im.Set(x, y, color.RGBA{0, 0, 0, 255})
		}
	}
	if NonblankCapture(encode()) {
		t.Fatal("black image accepted")
	}
	for y := 30; y < 60; y++ {
		for x := 30; x < 80; x++ {
			im.Set(x, y, color.RGBA{180, 120, 60, 255})
		}
	}
	if !NonblankCapture(encode()) {
		t.Fatal("visible image rejected")
	}
	if NonblankCapture("not an image") {
		t.Fatal("invalid image accepted")
	}
}

func TestPreparePreservesOtherOBSConfig(t *testing.T) {
	p := testPaths(t)
	other := filepath.Join(filepath.Dir(p.OBSConfig), "obs-studio", "global.ini")
	if e := os.MkdirAll(filepath.Dir(other), 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(other, []byte("my existing scenes"), 0600); e != nil {
		t.Fatal(e)
	}
	s, e := Configure(p, strings.NewReader(fixtureSettings))
	if e != nil {
		t.Fatal(e)
	}
	_, secrets, e := Load(p)
	if e != nil {
		t.Fatal(e)
	}
	if e = Prepare(p, s, secrets); e != nil {
		t.Fatal(e)
	}
	b, _ := os.ReadFile(other)
	if string(b) != "my existing scenes" {
		t.Fatal("changed other OBS settings")
	}
}

func TestMissingCredentialsCannotHideAnOccupiedOBSPort(t *testing.T) {
	listener, e := net.Listen("tcp", "127.0.0.1:"+Port)
	if e != nil {
		t.Skip("test OBS port is already occupied")
	}
	defer listener.Close()
	r := Status(context.Background(), testPaths(t))
	if r.OK || r.State != "unknown" {
		t.Fatalf("unconfirmed OBS must remain unknown, got %+v", r)
	}
}
