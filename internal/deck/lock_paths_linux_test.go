//go:build linux

package deck

import (
	"context"
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func TestLegacyLockRefusesRecreatedNamespaceWhileOriginalInodeIsHeld(t *testing.T) {
	t.Setenv(deckyStorageMapEnv, "")
	for _, mode := range []os.FileMode{0777, 0770} {
		t.Run(mode.String(), func(t *testing.T) {
			ancestor := filepath.Join(t.TempDir(), "shared")
			private := filepath.Join(ancestor, "private-grandchild")
			paths := Paths{State: filepath.Join(private, "obsgod")}
			if err := os.MkdirAll(paths.State, 0700); err != nil {
				t.Fatal(err)
			}
			release, err := Lock(context.Background(), paths)
			if err != nil {
				t.Fatal(err)
			}
			defer release()
			original, err := os.Stat(filepath.Join(paths.State, "control.lock"))
			if err != nil {
				t.Fatal(err)
			}
			if err = os.Chmod(ancestor, mode); err != nil {
				t.Fatal(err)
			}
			moved := filepath.Join(private, "previous-obsgod")
			if err = os.Rename(paths.State, moved); err != nil {
				t.Fatal(err)
			}
			if err = os.Mkdir(paths.State, 0700); err != nil {
				t.Fatal(err)
			}
			if unlock, err := Lock(context.Background(), paths); err == nil {
				unlock()
				t.Fatal("legacy client opened a second controller namespace under a writable ancestor")
			}
			if _, err = os.Stat(filepath.Join(paths.State, "control.lock")); !os.IsNotExist(err) {
				t.Fatal("second control.lock was created", err)
			}
			retained, err := os.Stat(filepath.Join(moved, "control.lock"))
			if err != nil || !os.SameFile(original, retained) {
				t.Fatal("original controller inode changed", err)
			}
			fd, err := syscall.Open(filepath.Join(moved, "control.lock"), syscall.O_RDWR|syscall.O_NOFOLLOW, 0)
			if err != nil {
				t.Fatal(err)
			}
			defer syscall.Close(fd)
			if err = syscall.Flock(fd, syscall.LOCK_EX|syscall.LOCK_NB); err != syscall.EWOULDBLOCK && err != syscall.EAGAIN {
				t.Fatal("original lease was not held through the rename", err)
			}
		})
	}
}
