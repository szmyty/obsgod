//go:build linux

package deck

import (
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

const deckyStorageMapEnv = "OBSGOD_DECKY_STORAGE_MAP"

type deckyStorageMap struct {
	Schema  string `json:"schema"`
	Version int    `json:"version"`
	UID     int    `json:"uid"`
	Home    string `json:"home"`
	Shared  struct {
		Config  string `json:"config"`
		Secrets string `json:"secrets"`
		State   string `json:"state"`
	} `json:"shared"`
	Decky struct {
		Settings string `json:"settings"`
		Runtime  string `json:"runtime"`
		Logs     string `json:"logs"`
	} `json:"decky"`
	Compatibility struct {
		CLI       string `json:"cli"`
		Plugin    string `json:"plugin"`
		Namespace string `json:"storage_namespace"`
	} `json:"compatibility"`
}

var errDeckyStorageMap = errors.New("the Decky storage map is unsafe or differs from the current player paths; restore the original context or repair the plugin")

// deckyOwnedPath checks every existing component without following symlinks.
// Missing shared data is valid before first-run setup. Existing endpoints must
// belong to the player; only root-owned system ancestors are permitted.
func deckyOwnedPath(path string, directory, private, missing bool) error {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path || strings.IndexFunc(path, func(r rune) bool { return r < 32 || r == 127 }) >= 0 {
		return errDeckyStorageMap
	}
	current := string(filepath.Separator)
	parts := strings.Split(strings.TrimPrefix(path, current), current)
	for index, part := range parts {
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if os.IsNotExist(err) && missing {
			return nil
		}
		if err != nil || info.Mode()&os.ModeSymlink != 0 {
			return errDeckyStorageMap
		}
		owner, ok := info.Sys().(*syscall.Stat_t)
		if !ok || int(owner.Uid) != os.Getuid() && owner.Uid != 0 {
			return errDeckyStorageMap
		}
		if info.IsDir() && info.Mode().Perm()&0022 != 0 && info.Mode()&os.ModeSticky == 0 {
			// A private child beneath a renameable ancestor can be replaced with
			// a new controller lock inode. Trusted sticky /tmp remains valid.
			return errDeckyStorageMap
		}
		final := index == len(parts)-1
		if !final && !info.IsDir() {
			return errDeckyStorageMap
		}
		if final && (int(owner.Uid) != os.Getuid() || directory != info.IsDir() || private && info.Mode().Perm()&0077 != 0) {
			return errDeckyStorageMap
		}
		if final && !directory && (!info.Mode().IsRegular() || owner.Nlink != 1 || info.Size() > 65536) {
			return errDeckyStorageMap
		}
	}
	return nil
}

func validateDeckyStorageMap(paths Paths, home string) error {
	selected := os.Getenv(deckyStorageMapEnv)
	if selected == "" {
		return nil
	}
	if os.Getuid() != os.Geteuid() || os.Getuid() == 0 || deckyOwnedPath(selected, false, true, false) != nil {
		return errDeckyStorageMap
	}
	fd, err := syscall.Open(selected, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return errDeckyStorageMap
	}
	file := os.NewFile(uintptr(fd), "Decky storage map")
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 65536 {
		return errDeckyStorageMap
	}
	owner, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(owner.Uid) != os.Getuid() || owner.Nlink != 1 {
		return errDeckyStorageMap
	}
	var mapping deckyStorageMap
	decoder := json.NewDecoder(io.LimitReader(file, 65537))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&mapping) != nil || decoder.Decode(new(any)) != io.EOF {
		return errDeckyStorageMap
	}
	canonicalHome, err := filepath.EvalSymlinks(home)
	if err != nil || mapping.Schema != "obsgod.decky-storage-map/v1" || mapping.Version != 1 || mapping.UID != os.Getuid() || mapping.Home != canonicalHome ||
		mapping.Shared.Config != paths.Config || mapping.Shared.Secrets != paths.Secrets || mapping.Shared.State != paths.State ||
		mapping.Compatibility.CLI != "obsgod" || mapping.Compatibility.Plugin != "OBSGod" || mapping.Compatibility.Namespace != "obsgod" {
		return errDeckyStorageMap
	}
	if selected != filepath.Join(mapping.Decky.Settings, "storage-v1/map.json") || deckyOwnedPath(filepath.Dir(selected), true, true, false) != nil {
		return errDeckyStorageMap
	}
	for _, path := range []string{mapping.Decky.Settings, mapping.Decky.Runtime, mapping.Decky.Logs} {
		if deckyOwnedPath(path, true, false, false) != nil {
			return errDeckyStorageMap
		}
	}
	for _, path := range []string{filepath.Dir(paths.Config), paths.State} {
		if deckyOwnedPath(path, true, false, true) != nil {
			return errDeckyStorageMap
		}
	}
	if deckyOwnedPath(paths.Config, false, false, true) != nil || deckyOwnedPath(paths.Secrets, false, true, true) != nil {
		return errDeckyStorageMap
	}
	// The map is an assertion, not an arbitrary path override. Keeping this
	// exact state path also keeps old CLI/Desktop control.lock and watchers.
	return nil
}
