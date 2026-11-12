package deck

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"
)

func TestLegacySettingsHashSurvivesNewOptionalPreferences(t *testing.T) {
	s := DefaultSettings()
	s.Server = "rtmps://example.invalid/app"
	// Exact pre-upgrade representation: no new defaults can be serialized into it.
	legacy := `{"version":1,"server":"rtmps://example.invalid/app","bitrate":4500,"fps":30,"microphone":false,"encoder":"vaapi"}`
	data, err := json.Marshal(s)
	if err != nil || string(data) != legacy {
		t.Fatalf("legacy representation changed: %s %v", data, err)
	}
	hash := sha256.Sum256([]byte(legacy))
	if settingsHash(s) != hex.EncodeToString(hash[:]) {
		t.Fatal("old secret binding invalidated")
	}
	if s.CaptureModeName() != "screen" || s.IdleStyleName() != "black" {
		t.Fatal("legacy behavior changed")
	}
	for _, mode := range []string{"screen", "game"} {
		s.CaptureMode = mode
		if err = s.Validate(); err != nil {
			t.Fatal(err)
		}
	}
	s.IdleStyle = "placeholder"
	s.IdleText = "Back soon 🎮"
	if err = s.Validate(); err != nil {
		t.Fatal(err)
	}
	s.IdleText = strings.Repeat("x", 201)
	if s.Validate() == nil {
		t.Fatal("unbounded placeholder accepted")
	}
}
