//go:build !linux

package deck

import (
	"context"
	"errors"
)

func WatchCapture(context.Context, Paths) error {
	return errors.New("game capture observation requires Linux")
}
func StartCaptureWatch(Paths) error { return errors.New("game capture observation requires Linux") }
