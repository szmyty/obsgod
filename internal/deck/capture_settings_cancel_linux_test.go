//go:build linux

package deck

import (
	"context"
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
	"time"
)

type captureInputCancellation struct {
	io.Reader
	cancel context.CancelFunc
}

func (r captureInputCancellation) Read(data []byte) (int, error) {
	n, err := r.Reader.Read(data)
	if err == io.EOF {
		r.cancel()
	}
	return n, err
}

func TestCaptureModeCancellationBeforeOrDuringInputPreservesSavedPair(t *testing.T) {
	for _, duringInput := range []bool{false, true} {
		t.Run(map[bool]string{false: "already cancelled", true: "cancelled at stdin EOF"}[duringInput], func(t *testing.T) {
			p := testPaths(t)
			if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
				t.Fatal(err)
			}
			before := configurationPair(t, p)
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			var input io.Reader = strings.NewReader(`{"capture_mode":"game"}`)
			if duringInput {
				input = captureInputCancellation{Reader: input, cancel: cancel}
			} else {
				cancel()
			}
			if _, err := SetCaptureMode(ctx, p, input); !errors.Is(err, context.Canceled) || !reflect.DeepEqual(before, configurationPair(t, p)) {
				t.Fatal("cancelled capture edit changed settings or credentials", err)
			}
		})
	}
}

func TestCaptureModeWatcherDeadlineCannotWriteAfterLeaseRelease(t *testing.T) {
	p := testPaths(t)
	if _, err := Configure(p, strings.NewReader(fixtureSettings)); err != nil {
		t.Fatal(err)
	}
	before := configurationPair(t, p)
	_, beforeSecret, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	unlock, err := Lock(context.Background(), captureWatchPaths(p))
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 80*time.Millisecond)
	defer cancel()
	_, err = SetCaptureMode(ctx, p, strings.NewReader(`{"capture_mode":"game"}`))
	unlock()
	if !errors.Is(err, context.DeadlineExceeded) || !reflect.DeepEqual(before, configurationPair(t, p)) {
		t.Fatal("expired watcher wait changed the saved pair", err)
	}
	// A fresh explicit edit after the old operation has returned must still work.
	if _, err := SetCaptureMode(context.Background(), p, strings.NewReader(`{"capture_mode":"game"}`)); err != nil {
		t.Fatal(err)
	}
	settings, secret, err := Load(p)
	if err != nil || settings.CaptureMode != "game" || secret.StreamKey != beforeSecret.StreamKey || secret.OBSPassword != beforeSecret.OBSPassword {
		t.Fatal("fresh capture edit lost its credential binding", err)
	}
}
