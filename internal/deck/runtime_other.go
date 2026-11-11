//go:build !linux

package deck

import (
	"context"
	"errors"
)

func checkDependencies(context.Context) error {
	return errors.New("Steam Deck integration requires Linux")
}
func gamescopeReady(context.Context) bool { return false }
func managedProcesses(Paths) []int        { return nil }
func launchOBS(Paths) error               { return errors.New("Steam Deck integration requires Linux") }
func stopManagedOBS(context.Context, Paths) error {
	return errors.New("Steam Deck integration requires Linux")
}
func privateUmask() {}
