//go:build !linux

package deck

import (
	"context"
	"errors"
)

func Lock(context.Context, Paths) (func(), error) {
	return nil, errors.New("the Steam Deck runtime requires Linux")
}
