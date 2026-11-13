//go:build linux

package deck

import (
	"os"
	"syscall"
)

func openMediaRead(path string) (*os.File, error) {
	return os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
}
