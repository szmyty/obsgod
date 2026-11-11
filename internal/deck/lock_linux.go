//go:build linux

package deck

import (
	"context"
	"os"
	"path/filepath"
	"syscall"
	"time"
)

func Lock(ctx context.Context, p Paths) (func(), error) {
	if e := privateDir(p.State); e != nil {
		return nil, e
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
