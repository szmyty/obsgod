//go:build !linux

package deck

import (
	"context"
	"errors"
)

func WatchMixer(context.Context, Paths) error {
	return errors.New("microphone privacy observation requires Linux")
}
func StartMixerWatch(Paths) error { return errors.New("microphone privacy observation requires Linux") }

func mixerGuardianAlive(Paths) bool { return false }
