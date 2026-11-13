//go:build !linux

package deck

import "os"

func openMediaRead(path string) (*os.File, error) { return os.Open(path) }
