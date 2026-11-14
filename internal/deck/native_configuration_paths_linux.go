//go:build linux

package deck

import "path/filepath"

func nativeConfigurationPathsSafe(p Paths) bool {
	return deckyOwnedPath(filepath.Dir(p.Config), true, false, true) == nil &&
		deckyOwnedPath(filepath.Dir(p.Secrets), true, false, true) == nil &&
		deckyOwnedPath(p.Config, false, false, true) == nil && deckyOwnedPath(p.Secrets, false, true, true) == nil
}
