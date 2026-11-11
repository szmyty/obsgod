//go:build !linux

package deck

import (
	"context"
	"errors"
)

func checkDependencies(context.Context) error {
	return errors.New("Steam Deck integration requires Linux")
}
func captureAvailability(context.Context) string { return "unavailable" }
func gamescopeReady(context.Context) bool        { return false }
func recoveryMarkerPresent(Paths) bool           { return false }
func obsProcessState(Paths) string               { return "absent" }
func managedProcesses(Paths) []int               { return nil }
func launchVisibleOBS(Paths) (<-chan int, error) {
	return nil, errors.New("Steam Deck integration requires Linux")
}
func launchOBS(Paths) (<-chan int, error) {
	return nil, errors.New("Steam Deck integration requires Linux")
}
func stopManagedOBS(context.Context, Paths) error {
	return errors.New("Steam Deck integration requires Linux")
}
func privateUmask() {}
