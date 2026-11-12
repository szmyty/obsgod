//go:build linux

package deck

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestUserPathsRespectXDGAndRejectRelativeRoots(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "configuration"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(home, "state"))
	p, err := UserPaths()
	if err != nil || p.Config != filepath.Join(home, "configuration/obsgod/deck.json") || p.State != filepath.Join(home, "state/obsgod") {
		t.Fatal("XDG context was not retained", err)
	}
	if p.Videos != filepath.Join(home, "Videos/OBSGod") {
		t.Fatal("existing recordings location changed without migration")
	}
	for _, key := range []string{"HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME"} {
		t.Run(key, func(t *testing.T) {
			t.Setenv(key, "relative-private-fixture")
			if _, err := UserPaths(); err == nil || strings.Contains(err.Error(), "private-fixture") {
				t.Fatal("unsafe path accepted or echoed")
			}
		})
	}
}
