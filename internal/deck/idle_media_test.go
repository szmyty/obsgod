package deck

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeIdlePNG(t *testing.T, path string) []byte {
	t.Helper()
	im := image.NewRGBA(image.Rect(0, 0, 40, 30))
	im.Set(4, 4, color.RGBA{200, 20, 30, 255})
	var out bytes.Buffer
	if err := png.Encode(&out, im); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, out.Bytes(), 0600); err != nil {
		t.Fatal(err)
	}
	return out.Bytes()
}
func TestIdleImportCopiesOwnedBytesAndNeverStoresOriginalPath(t *testing.T) {
	p := testPaths(t)
	source := filepath.Join(t.TempDir(), "owner file.not-png")
	original := writeIdlePNG(t, source)
	name, err := importIdleMedia(p, source, "image")
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(original)
	if name != hex.EncodeToString(sum[:])+".png" {
		t.Fatal("import did not identify actual bytes", name)
	}
	target := filepath.Join(idleMediaDirectory(p), name)
	info, err := os.Stat(target)
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("owned media not private", err)
	}
	if err = os.WriteFile(source, []byte("changed original"), 0600); err != nil {
		t.Fatal(err)
	}
	copied, _ := os.ReadFile(target)
	if !bytes.Equal(copied, original) {
		t.Fatal("original edit changed owned copy")
	}
	s := DefaultSettings()
	s.IdleStyle = "image"
	s.IdleMedia = name
	preview, _ := json.Marshal(PreviewIdle(p, s))
	if bytes.Contains(preview, []byte(source)) || !bytes.Contains(preview, []byte(`"media":"ready"`)) {
		t.Fatal("unsafe preview", string(preview))
	}
	if err = os.Remove(target); err != nil {
		t.Fatal(err)
	}
	if got := PreviewIdle(p, s); got.Media != "unavailable" {
		t.Fatal("missing import claimed ready", got)
	}
}
func TestIdleMediaRefusesUnsupportedUnsafeAndOversizedInputs(t *testing.T) {
	p := testPaths(t)
	dir := t.TempDir()
	valid := filepath.Join(dir, "valid.png")
	writeIdlePNG(t, valid)
	link := filepath.Join(dir, "link.png")
	if err := os.Symlink(valid, link); err != nil {
		t.Fatal(err)
	}
	playlist := filepath.Join(dir, "pretend.mp4")
	_ = os.WriteFile(playlist, []byte("#EXTM3U\nhttps://example.invalid/stream"), 0600)
	huge := filepath.Join(dir, "huge.mp4")
	file, err := os.Create(huge)
	if err != nil {
		t.Fatal(err)
	}
	_ = file.Truncate(idleVideoLimit + 1)
	_ = file.Close()
	for _, test := range []struct{ path, style string }{{link, "image"}, {dir, "image"}, {"https://example.invalid/logo.png", "image"}, {playlist, "video"}, {huge, "video"}, {valid, "video"}, {filepath.Join(dir, "missing.png"), "image"}} {
		if _, err = importIdleMedia(p, test.path, test.style); err == nil {
			t.Errorf("accepted unsafe input %q %s", test.path, test.style)
		}
	}
	for _, name := range []string{"../private.png", "/etc/passwd", strings.Repeat("a", 64) + ".svg", strings.Repeat("a", 64) + ".m3u8"} {
		s := DefaultSettings()
		s.IdleStyle = "image"
		s.IdleMedia = name
		if validateIdleMediaSettings(s) == nil {
			t.Errorf("accepted media reference %q", name)
		}
	}
}
func TestConfigureIdleRequiresRightsAndPreservesCredentials(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	_, secret, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	source := filepath.Join(t.TempDir(), "original private name.png")
	writeIdlePNG(t, source)
	input := map[string]any{"idle_style": "image", "source": source, "attribution": "Owner original"}
	data, _ := json.Marshal(input)
	before, _ := os.ReadFile(p.Config)
	if _, err = ConfigureIdle(context.Background(), p, bytes.NewReader(data)); err == nil {
		t.Fatal("unacknowledged rights accepted")
	}
	after, _ := os.ReadFile(p.Config)
	if !bytes.Equal(before, after) {
		t.Fatal("failed import changed settings")
	}
	input["rights_acknowledged"] = true
	data, _ = json.Marshal(input)
	result, err := ConfigureIdle(context.Background(), p, bytes.NewReader(data))
	if err != nil {
		t.Fatal(err)
	}
	saved, later, err := Load(p)
	if err != nil || saved.IdleStyle != "image" || saved.IdleMediaRights != "Owner original" || later.StreamKey != secret.StreamKey || later.OBSPassword != secret.OBSPassword {
		t.Fatal("idle save did not preserve binding/credentials", err)
	}
	encoded, _ := json.Marshal(result)
	if bytes.Contains(encoded, []byte(source)) || bytes.Contains(encoded, []byte(secret.StreamKey)) {
		t.Fatal("idle result exposed source/secret")
	}
	if _, err = ConfigureIdle(context.Background(), p, strings.NewReader(`{"idle_style":"black"}`)); err != nil {
		t.Fatal(err)
	}
	if _, err = ConfigureIdle(context.Background(), p, strings.NewReader(`{"idle_style":"image"}`)); err != nil {
		t.Fatal("could not reuse imported asset", err)
	}
}
func TestIdleImportDetectsAlteredOwnedFile(t *testing.T) {
	p := testPaths(t)
	source := filepath.Join(t.TempDir(), "image.png")
	writeIdlePNG(t, source)
	name, err := importIdleMedia(p, source, "image")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(idleMediaDirectory(p), name)
	if err = os.WriteFile(path, []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = importIdleMedia(p, source, "image"); err == nil {
		t.Fatal("silently overwrote altered owned bytes")
	}
}
func TestGameStabilityFailsClosedWithoutDelayingIdle(t *testing.T) {
	var stable gameStability
	sequence := []GameIdentity{{State: "running", AppID: 42}, {State: "running", AppID: 42}, {State: "ambiguous"}, {State: "running", AppID: 43}, {State: "idle"}, {State: "running", AppID: 43}, {State: "running", AppID: 43}, {State: "running", AppID: 769}}
	want := []string{"idle", "running", "ambiguous", "idle", "idle", "idle", "running", "running"}
	for i, input := range sequence {
		got := stable.observe(input)
		if got.State != want[i] {
			t.Fatalf("step%d=%+v want%s", i, got, want[i])
		}
		if input.AppID == 769 && stable.app != 0 {
			t.Fatal("Steam UI accepted as game")
		}
	}
}
func TestIdleImportRefusesSymlinkDestinationAncestorAndTruncatedImage(t *testing.T) {
	source := filepath.Join(t.TempDir(), "source.png")
	original := writeIdlePNG(t, source)
	p := testPaths(t)
	outside := t.TempDir()
	if err := os.Symlink(outside, p.OBSConfig); err != nil {
		t.Fatal(err)
	}
	if _, err := importIdleMedia(p, source, "image"); err == nil {
		t.Fatal("followed symlink destination")
	}
	entries, err := os.ReadDir(outside)
	if err != nil || len(entries) != 0 {
		t.Fatal("unsafe import wrote outside owned tree", err)
	}
	corrupt := filepath.Join(t.TempDir(), "corrupt.png")
	if err = os.WriteFile(corrupt, original[:33], 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = importIdleMedia(testPaths(t), corrupt, "image"); err == nil {
		t.Fatal("accepted truncated PNG header without pixels")
	}
}
func TestIdleMediaImportCancellationAndOversizedJSONPreserveSettings(t *testing.T) {
	p := testPaths(t)
	source := filepath.Join(t.TempDir(), "image.png")
	writeIdlePNG(t, source)
	cancelled, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := importIdleMediaWithin(cancelled, p, source, "image"); err == nil {
		t.Fatal("cancelled copy completed")
	}
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(p.Config)
	input := `{"idle_style":"black"}` + strings.Repeat(" ", 8200) + `{}`
	if _, err := ConfigureIdle(context.Background(), p, strings.NewReader(input)); err == nil {
		t.Fatal("oversized/trailing JSON accepted")
	}
	after, _ := os.ReadFile(p.Config)
	if !bytes.Equal(before, after) {
		t.Fatal("refused oversized input modified configuration")
	}
}
