//go:build linux

package deck

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func TestLocalTestParentMaintainsCaptureWhileDetachedObserverYields(t *testing.T) {
	f := newVideoFixture(t)
	f.active, f.recording = false, true
	c, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	unlock, err := Lock(ctx, p)
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	load := func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }
	observerDone := make(chan error, 1)
	go func() {
		observerDone <- watchCaptureWith(ctx, p, captureWatchDeps{load: load, connect: dial,
			discover: func(context.Context) GameIdentity { return GameIdentity{AppID: 42, State: "running"} }, interval: time.Millisecond})
	}()
	executable, err := captureWatchExecutable()
	if err != nil {
		t.Fatal(err)
	}
	if err = waitCaptureWatchReady(p, executable, nil, time.Second); err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	requests := append([]fixtureRequest(nil), f.requests...)
	f.mu.Unlock()
	assertCaptureReadOnly(t, requests)
	calls, gameSeen, idleSeen := 0, false, false
	err = waitTestCaptureWith(ctx, p, c, s, Secrets{}, 300*time.Millisecond, captureWatchDeps{load: load,
		discover: func(context.Context) GameIdentity {
			calls++
			f.mu.Lock()
			defer f.mu.Unlock()
			if calls == 3 {
				gameSeen = f.scene == GameScene
			}
			if calls >= 4 && f.scene == IdleScene {
				idleSeen = true
			}
			if calls >= 3 {
				return GameIdentity{State: "idle"}
			}
			return GameIdentity{AppID: 42, State: "running"}
		}, interval: 10 * time.Millisecond})
	if err != nil || !gameSeen || !idleSeen {
		t.Fatalf("lease-owning test parent did not follow game/idle: game=%t idle=%t calls=%d err=%v", gameSeen, idleSeen, calls, err)
	}
	// The original transaction still owns the lease; a competing explicit
	// action cannot replace its clip while it waits and then be stopped by it.
	probe, done := context.WithTimeout(ctx, 20*time.Millisecond)
	_, lockErr := Lock(probe, p)
	done()
	if !errors.Is(lockErr, context.DeadlineExceeded) {
		t.Fatalf("local test lost its recording transaction lease: %v", lockErr)
	}
	cancel()
	<-observerDone
	f.mu.Lock()
	defer f.mu.Unlock()
	assertNoOutputCommands(t, f)
	if !f.recording || f.active {
		t.Fatal("capture maintenance changed recording or started broadcasting")
	}
}

func TestLocalTestCaptureDeadlineKeepsFinalizerConnectionAndDoesNotMaskErrors(t *testing.T) {
	for _, observationFailure := range []bool{false, true} {
		t.Run(map[bool]string{false: "duration", true: "observation-error"}[observationFailure], func(t *testing.T) {
			f := newVideoFixture(t)
			f.active, f.recording = false, true
			c, _ := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			failure := errors.New("fixture observation was unconfirmed")
			err := waitTestCaptureWith(context.Background(), p, c, s, Secrets{}, 20*time.Millisecond, captureWatchDeps{
				load:     func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil },
				discover: func(context.Context) GameIdentity { return GameIdentity{State: "idle"} },
				connect: func(ctx context.Context, _ Secrets) (*automation.Client, error) {
					<-ctx.Done()
					if observationFailure {
						return nil, failure
					}
					return nil, ctx.Err()
				}})
			if observationFailure && !errors.Is(err, failure) || !observationFailure && err != nil {
				t.Fatalf("clip deadline masked observation failure: %v", err)
			}
			if runtime, err := c.RuntimeStatus(context.Background()); err != nil || !runtime.Recording {
				t.Fatalf("clip deadline invalidated its finalizer connection: %+v %v", runtime, err)
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests)
		})
	}
}

func TestLocalTestCaptureRejectsLostOwnershipOrRecordingBeforeMutation(t *testing.T) {
	for _, change := range []string{"profile", "collection", "unknown", "stopped", "stream-only", "settings"} {
		t.Run(change, func(t *testing.T) {
			f := newVideoFixture(t)
			f.active, f.recording = false, true
			c, _ := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			fresh := s
			unlock, err := Lock(context.Background(), p)
			if err != nil {
				t.Fatal(err)
			}
			defer unlock()
			err = waitTestCaptureWith(context.Background(), p, c, s, Secrets{}, time.Second, captureWatchDeps{
				load: func(Paths) (Settings, Secrets, error) { return fresh, Secrets{}, nil },
				discover: func(context.Context) GameIdentity {
					f.mu.Lock()
					defer f.mu.Unlock()
					switch change {
					case "profile":
						f.profile = "Ordinary profile"
					case "collection":
						f.collection = "Ordinary collection"
					case "unknown":
						f.recordMalformed = true
					case "stopped":
						f.recording = false
					case "stream-only":
						f.recording, f.active = false, true
					case "settings":
						fresh.IdleText = "new idle configuration"
					}
					return GameIdentity{State: "idle"}
				}})
			if err == nil {
				t.Fatal("local test accepted changed recording ownership")
			}
			if change == "profile" || change == "collection" || change == "unknown" {
				if _, err := stopTestRecording(context.Background(), c); err == nil {
					t.Fatal("local test cleanup accepted unverified managed ownership")
				}
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests)
		})
	}
}

func TestLocalTestCaptureKeepsOriginalDeadlineAndCancellation(t *testing.T) {
	for _, cancelParent := range []bool{false, true} {
		t.Run(map[bool]string{false: "duration", true: "cancellation"}[cancelParent], func(t *testing.T) {
			f := newVideoFixture(t)
			c, _ := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			var once sync.Once
			start := time.Now()
			err := waitTestCaptureWith(ctx, p, c, s, Secrets{}, 30*time.Millisecond, captureWatchDeps{
				load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil },
				discover: func(ctx context.Context) GameIdentity {
					if cancelParent {
						once.Do(cancel)
					}
					<-ctx.Done()
					return GameIdentity{AppID: 42, State: "running"}
				}})
			if time.Since(start) > time.Second || cancelParent != errors.Is(err, context.Canceled) || !cancelParent && err != nil {
				t.Fatalf("local clip duration/cancellation changed: %v elapsed=%v", err, time.Since(start))
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests)
		})
	}
}
