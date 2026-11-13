//go:build !linux

package deck

import (
	"context"
	"errors"
)

func WatchResilience(context.Context, Paths) error {
	return errors.New("Steam Deck audio recovery requires Linux")
}
func StartResilienceWatch(Paths) error {
	return errors.New("Steam Deck audio recovery requires Linux")
}
