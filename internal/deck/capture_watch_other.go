//go:build !linux

package deck

import (
	"context"
	"errors"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func WatchCapture(context.Context, Paths) error {
	return errors.New("game capture observation requires Linux")
}
func StartCaptureWatch(Paths) error { return errors.New("game capture observation requires Linux") }

func waitTestCapture(ctx context.Context, _ Paths, _ *automation.Client, _ Settings, _ Secrets, duration time.Duration) error {
	return wait(ctx, duration)
}
