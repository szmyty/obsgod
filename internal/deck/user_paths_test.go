//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLegacyControlLockRequiresProtectedAncestorsWithoutStorageMap(t *testing.T) {
	t.Setenv("OBSGOD_DECKY_STORAGE_MAP", "")
	for _, sticky := range []bool{false, true} {
		t.Run(map[bool]string{false: "unsafe", true: "sticky"}[sticky], func(t *testing.T) {
			parent := filepath.Join(t.TempDir(), "public-parent")
			if err := os.Mkdir(parent, 0700); err != nil {
				t.Fatal(err)
			}
			mode := os.FileMode(0777)
			if sticky {
				mode |= os.ModeSticky
			}
			if err := os.Chmod(parent, mode); err != nil {
				t.Fatal(err)
			}
			paths := testPaths(t)
			paths.State = filepath.Join(parent, "managed")
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			release, err := Lock(ctx, paths)
			if !sticky {
				if err == nil {
					release()
					t.Fatal("legacy command acquired a control namespace under an unsafe parent")
				}
				if _, err := os.Lstat(paths.State); !os.IsNotExist(err) {
					t.Fatal("unsafe legacy state directory was created")
				}
				return
			}
			if err != nil {
				t.Fatal("trusted sticky parent was refused", err)
			}
			release()
		})
	}
}

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

func deckyPathsFixture(t *testing.T) (Paths, string, deckyStorageMap) {
	t.Helper()
	if os.Getuid() == 0 {
		t.Skip("native Decky map requires an actual unprivileged player; root rejection is tested separately")
	}
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "configuration"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(home, "state"))
	t.Setenv(deckyStorageMapEnv, "")
	paths, err := UserPaths()
	if err != nil {
		t.Fatal(err)
	}
	var mapping deckyStorageMap
	mapping.Schema, mapping.Version, mapping.UID, mapping.Home = "obsgod.decky-storage-map/v1", 1, os.Getuid(), home
	mapping.Shared.Config, mapping.Shared.Secrets, mapping.Shared.State = paths.Config, paths.Secrets, paths.State
	mapping.Decky.Settings, mapping.Decky.Runtime, mapping.Decky.Logs = filepath.Join(home, "decky-settings"), filepath.Join(home, "decky-data"), filepath.Join(home, "decky-logs")
	mapping.Compatibility.CLI, mapping.Compatibility.Plugin, mapping.Compatibility.Namespace = "obsgod", "OBSGod", "obsgod"
	for _, directory := range []string{filepath.Join(mapping.Decky.Settings, "storage-v1"), mapping.Decky.Runtime, mapping.Decky.Logs} {
		if err = os.MkdirAll(directory, 0700); err != nil {
			t.Fatal(err)
		}
	}
	path := filepath.Join(mapping.Decky.Settings, "storage-v1/map.json")
	writeDeckyMap(t, path, mapping)
	return paths, path, mapping
}

func writeDeckyMap(t *testing.T, path string, mapping deckyStorageMap) {
	t.Helper()
	data, err := json.Marshal(mapping)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
}

func TestDeckyStorageMapRetainsOneCredentialBindingAndController(t *testing.T) {
	legacy, path, _ := deckyPathsFixture(t)
	settings := DefaultSettings()
	settings.Server = "rtmps://fixture.invalid/live"
	secrets := Secrets{StreamKey: "synthetic-private-stream-key", OBSPassword: "synthetic-private-control", SettingsHash: settingsHash(settings)}
	if err := writeJSON(legacy.Config, settings); err != nil {
		t.Fatal(err)
	}
	if err := writeJSON(legacy.Secrets, secrets); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(legacy.Secrets)
	t.Setenv(deckyStorageMapEnv, path)
	native, err := UserPaths()
	if err != nil || native != legacy {
		t.Fatal("native context forked shared store or native OBS/Videos paths", err)
	}
	_, loaded, err := Load(native)
	if err != nil || loaded != secrets {
		t.Fatal("credential binding did not survive metadata transition", err)
	}
	current, _ := os.ReadFile(legacy.Secrets)
	if string(current) != string(data) {
		t.Fatal("credentials were rewritten")
	}
	release, err := Lock(context.Background(), legacy)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	defer cancel()
	if unlock, err := Lock(ctx, native); !errors.Is(err, context.DeadlineExceeded) {
		if unlock != nil {
			unlock()
		}
		t.Fatal("native and legacy contexts did not share the same controller lock", err)
	}
	t.Setenv(deckyStorageMapEnv, "")
	rollback, err := UserPaths()
	if err != nil || rollback != legacy {
		t.Fatal("legacy rollback changed settings, credentials, OBS, state or Videos", err)
	}
}

func TestDeckyStorageMapRejectsChangedIdentityRootsAndSchema(t *testing.T) {
	_, path, original := deckyPathsFixture(t)
	t.Setenv(deckyStorageMapEnv, path)
	for _, mutate := range []func(*deckyStorageMap){
		func(m *deckyStorageMap) { m.UID++ },
		func(m *deckyStorageMap) { m.Version = 2 },
		func(m *deckyStorageMap) { m.Shared.State = m.Decky.Runtime },
		func(m *deckyStorageMap) { m.Shared.Secrets = filepath.Join(m.Home, "another-private-fixture") },
		func(m *deckyStorageMap) { m.Compatibility.Namespace = "deckystream" },
	} {
		changed := original
		mutate(&changed)
		writeDeckyMap(t, path, changed)
		if _, err := UserPaths(); err == nil || strings.Contains(err.Error(), "private-fixture") {
			t.Fatal("unsafe map accepted or path echoed", err)
		}
	}
	writeDeckyMap(t, path, original)
	t.Setenv("XDG_STATE_HOME", filepath.Join(original.Home, "changed-state"))
	if _, err := UserPaths(); err == nil {
		t.Fatal("changed XDG context silently selected a second control store")
	}
}

func TestDeckyStorageMapRejectsSymlinksPublicFilesAndHardlinks(t *testing.T) {
	_, path, _ := deckyPathsFixture(t)
	t.Setenv(deckyStorageMapEnv, path)
	if err := os.Chmod(path, 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := UserPaths(); err == nil {
		t.Fatal("public metadata map accepted")
	}
	_ = os.Chmod(path, 0600)
	link := filepath.Join(filepath.Dir(path), "unrelated-hardlink")
	if err := os.Link(path, link); err != nil {
		t.Fatal(err)
	}
	if _, err := UserPaths(); err == nil {
		t.Fatal("hardlinked map accepted")
	}
	_ = os.Remove(link)
	data, _ := os.ReadFile(path)
	other := filepath.Join(filepath.Dir(path), "original")
	if err := os.Rename(path, other); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(other, path); err != nil {
		t.Fatal(err)
	}
	if _, err := UserPaths(); err == nil {
		t.Fatal("symlink map accepted")
	}
	_ = os.Remove(path)
	if current, _ := os.ReadFile(other); string(current) != string(data) {
		t.Fatal("symlink target was changed")
	}
}

func TestDeckyStorageMapDoesNotPermitRootBackend(t *testing.T) {
	if os.Getuid() != 0 {
		t.Skip("root-only negative identity case")
	}
	t.Setenv("HOME", t.TempDir())
	t.Setenv(deckyStorageMapEnv, filepath.Join(os.Getenv("HOME"), "map.json"))
	if _, err := UserPaths(); err == nil {
		t.Fatal("root backend accepted a native Decky storage map")
	}
}

func TestDeckyStorageRejectsRenameableAncestorBeforeSecondController(t *testing.T) {
	legacy, path, mapping := deckyPathsFixture(t)
	ancestor := filepath.Join(mapping.Home, "shared-ancestor")
	private := filepath.Join(ancestor, "private-grandchild")
	legacy.State = filepath.Join(private, "obsgod")
	if err := os.MkdirAll(legacy.State, 0700); err != nil {
		t.Fatal(err)
	}
	mapping.Shared.State = legacy.State
	writeDeckyMap(t, path, mapping)
	t.Setenv("XDG_STATE_HOME", private)
	t.Setenv(deckyStorageMapEnv, path)
	if _, err := UserPaths(); err != nil {
		t.Fatal("private baseline rejected", err)
	}
	release, err := Lock(context.Background(), legacy)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	original, err := os.Stat(filepath.Join(legacy.State, "control.lock"))
	if err != nil {
		t.Fatal(err)
	}
	if err = os.Chmod(ancestor, 0777); err != nil {
		t.Fatal(err)
	}
	if _, err = UserPaths(); err == nil {
		t.Fatal("private grandchild concealed a non-sticky writable ancestor")
	}
	moved := filepath.Join(private, "previous-obsgod")
	if err = os.Rename(legacy.State, moved); err != nil {
		t.Fatal(err)
	}
	if err = os.Mkdir(legacy.State, 0700); err != nil {
		t.Fatal(err)
	}
	if _, err = UserPaths(); err == nil {
		t.Fatal("replacement namespace accepted while old controller lease remains held")
	}
	if _, err = os.Stat(filepath.Join(legacy.State, "control.lock")); !os.IsNotExist(err) {
		t.Fatal("second controller lock was created", err)
	}
	retained, err := os.Stat(filepath.Join(moved, "control.lock"))
	if err != nil || !os.SameFile(original, retained) {
		t.Fatal("original controller inode changed", err)
	}
}

func TestDeckyStorageSupportsTrustedStickyAncestor(t *testing.T) {
	legacy, path, mapping := deckyPathsFixture(t)
	ancestor := filepath.Join(mapping.Home, "sticky-shared")
	private := filepath.Join(ancestor, "private-grandchild")
	legacy.State = filepath.Join(private, "obsgod")
	if err := os.MkdirAll(legacy.State, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(ancestor, os.ModeSticky|0777); err != nil {
		t.Fatal(err)
	}
	mapping.Shared.State = legacy.State
	writeDeckyMap(t, path, mapping)
	t.Setenv("XDG_STATE_HOME", private)
	t.Setenv(deckyStorageMapEnv, path)
	native, err := UserPaths()
	if err != nil || native.State != legacy.State {
		t.Fatal("legitimate sticky-root XDG override rejected", err)
	}
	release, err := Lock(context.Background(), legacy)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	defer cancel()
	if unlock, err := Lock(ctx, native); !errors.Is(err, context.DeadlineExceeded) {
		if unlock != nil {
			unlock()
		}
		t.Fatal("sticky-root contexts did not retain one controller inode", err)
	}
}
