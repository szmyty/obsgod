//go:build !linux

package deck

import (
	"errors"
	"os"
)

func validateDeckyStorageMap(_ Paths, _ string) error {
	if os.Getenv("OBSGOD_DECKY_STORAGE_MAP") != "" {
		return errors.New("Decky storage context requires Linux")
	}
	return nil
}
