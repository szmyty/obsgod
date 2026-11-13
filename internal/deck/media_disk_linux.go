//go:build linux

package deck

import "syscall"

func mediaFreeBytes(directory string) (uint64, error) {
	var s syscall.Statfs_t
	if e := syscall.Statfs(directory, &s); e != nil {
		return 0, e
	}
	return s.Bavail * uint64(s.Bsize), nil
}
