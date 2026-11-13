//go:build !linux

package deck

import "errors"

func mediaFreeBytes(string) (uint64, error) {
	return 0, errors.New("recording storage measurement requires Linux")
}
