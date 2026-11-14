//go:build linux

package deck

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"time"
)

var errUnsafeControlPath = errors.New("managed OBS storage is unsafe; check directory ownership, permissions and symlinks before retrying")

func Lock(ctx context.Context, p Paths) (func(), error) {
	privateUmask()
	// Older CLI clients need the same protected namespace even when they do
	// not carry a Decky storage map. A private leaf below a renameable parent
	// could otherwise become a second control.lock while the first is held.
	if e := deckyOwnedPath(p.State, true, false, true); e != nil {
		return nil, errUnsafeControlPath
	}
	if e := privateDir(p.State); e != nil {
		return nil, e
	}
	if e := deckyOwnedPath(p.State, true, true, false); e != nil {
		return nil, errUnsafeControlPath
	}
	f, e := os.OpenFile(filepath.Join(p.State, "control.lock"), os.O_CREATE|os.O_RDWR|syscall.O_NOFOLLOW, 0600)
	if e != nil {
		return nil, e
	}
	for {
		e = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if e == nil {
			return func() { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN); _ = f.Close() }, nil
		}
		if e != syscall.EAGAIN && e != syscall.EWOULDBLOCK {
			_ = f.Close()
			return nil, e
		}
		select {
		case <-ctx.Done():
			_ = f.Close()
			return nil, ctx.Err()
		case <-time.After(100 * time.Millisecond):
		}
	}
}
