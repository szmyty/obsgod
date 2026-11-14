//go:build !linux

package deck

func nativeConfigurationPathsSafe(p Paths) bool {
	// Managed mutation still requires positive Linux runtime observations. Keep
	// the portable CLI build independent of Unix UID/Stat_t implementation.
	return controlParentsSafe(p.Config) && controlParentsSafe(p.Secrets)
}
