//go:build linux

package deck

import (
	"context"
	"errors"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func assertCaptureReadOnly(t *testing.T, requests []fixtureRequest) {
	t.Helper()
	for _, request := range requests {
		if !strings.HasPrefix(request.Type, "Get") {
			t.Fatalf("capture observer mutated OBS through %s", request.Type)
		}
	}
}

func TestCaptureWatchRechecksOwnershipOutputAndSettingsAfterBlockedDiscovery(t *testing.T) {
	for _, change := range []string{"profile", "collection", "stop", "capture-mode", "output-unknown"} {
		t.Run(change, func(t *testing.T) {
			f := newVideoFixture(t)
			f.scene = GameScene
			_, dial := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			started, release := make(chan struct{}), make(chan struct{})
			var announce sync.Once
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			result := make(chan error, 1)
			go func() {
				result <- watchCaptureWith(ctx, p, captureWatchDeps{
					load: func(Paths) (Settings, Secrets, error) {
						f.mu.Lock()
						defer f.mu.Unlock()
						return s, Secrets{}, nil
					}, connect: dial, discover: func(ctx context.Context) GameIdentity {
						announce.Do(func() { close(started) })
						select {
						case <-release:
						case <-ctx.Done():
						}
						return GameIdentity{State: "idle"}
					}, interval: time.Millisecond,
				})
			}()
			select {
			case <-started:
			case <-ctx.Done():
				t.Fatal("discovery did not start")
			}
			// An explicit operation can acquire the shared lease while discovery
			// is blocked. Its new state must win when the callback returns.
			unlock, err := Lock(ctx, p)
			if err != nil {
				t.Fatal(err)
			}
			f.mu.Lock()
			changedAt := len(f.requests)
			switch change {
			case "profile":
				f.profile = "Ordinary profile"
			case "collection":
				f.collection = "Ordinary collection"
			case "stop":
				f.active = false
			case "capture-mode":
				s.CaptureMode = "screen"
			case "output-unknown":
				f.recordMalformed = true
			}
			f.mu.Unlock()
			unlock()
			close(release)
			select {
			case err = <-result:
			case <-ctx.Done():
				t.Fatal("observer did not finish after discovery returned")
			}
			if (change == "profile" || change == "collection" || change == "output-unknown") != (err != nil) {
				t.Fatalf("unexpected observer result for %s: %v", change, err)
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests[changedAt:])
			if f.scene != GameScene || len(f.inputs) != 1 {
				t.Fatal("stale discovery changed the scene or inputs")
			}
			if status := ReadCaptureVideoStatus(p); status.Watching || status.Frames != "unknown" {
				t.Fatalf("observer retained active frame claims: %+v", status)
			}
		})
	}
}

func TestCaptureWatchYieldsToSharedLeaseAndAttachesWithoutDeadlock(t *testing.T) {
	f := newVideoFixture(t)
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	unlock, err := Lock(ctx, p)
	if err != nil {
		t.Fatal(err)
	}
	var release sync.Once
	defer release.Do(unlock)
	discovered := make(chan struct{}, 4)
	result := make(chan error, 1)
	go func() {
		result <- watchCaptureWith(ctx, p, captureWatchDeps{
			load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }, connect: dial,
			discover: func(context.Context) GameIdentity {
				discovered <- struct{}{}
				return GameIdentity{AppID: 42, State: "running"}
			}, interval: time.Millisecond,
		})
	}()
	executable, err := captureWatchExecutable()
	if err != nil {
		t.Fatal(err)
	}
	// This is the same bounded readiness wait used by StartCaptureWatch.
	// It must return before the initiating Start releases the control lease.
	if err := waitCaptureWatchReady(p, executable, nil, time.Second); err != nil {
		t.Fatal(err)
	}
	record, fresh := readCaptureVideoRecord(p)
	if !fresh || !record.Watching || record.State != "unknown" || record.Frames != "unknown" || record.PID != os.Getpid() {
		t.Fatalf("read-only startup handshake made a frame-health claim: %+v", record)
	}
	// A second cycle proves the first lease attempt yielded instead of
	// waiting indefinitely or mutating under the initiating command's lease.
	for range 2 {
		select {
		case <-discovered:
		case <-ctx.Done():
			t.Fatal("observer did not yield and retry its shared lease")
		}
	}
	f.mu.Lock()
	assertCaptureReadOnly(t, f.requests)
	f.collection = "Ordinary collection"
	f.mu.Unlock()
	release.Do(unlock)
	select {
	case err := <-result:
		if err == nil || errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("observer did not recheck ownership after yielding: %v", err)
		}
	case <-ctx.Done():
		t.Fatal("observer did not finish after the control lease was released")
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	assertCaptureReadOnly(t, f.requests)
}

func TestCaptureWatchBoundsDiscoveryAndDiscardsTimedOutIdentity(t *testing.T) {
	f := newVideoFixture(t)
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	calls := 0
	err := watchCaptureWith(ctx, p, captureWatchDeps{
		load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }, connect: dial,
		discover: func(ctx context.Context) GameIdentity {
			calls++
			<-ctx.Done()
			return GameIdentity{AppID: 42, State: "running"}
		}, interval: time.Millisecond, discoveryTimeout: 25 * time.Millisecond,
	})
	if err == nil || errors.Is(err, context.DeadlineExceeded) || calls != 3 {
		t.Fatalf("discovery was not bounded to three failed cycles: calls=%d err=%v", calls, err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	assertCaptureReadOnly(t, f.requests)
	if status := ReadCaptureVideoStatus(p); status.State != "unknown" || status.Watching || status.Frames != "unknown" {
		t.Fatalf("timed-out discovery retained frame claims: %+v", status)
	}
}

func TestCaptureWatchReadinessTimeoutIsBounded(t *testing.T) {
	p := testPaths(t)
	executable, err := captureWatchExecutable()
	if err != nil {
		t.Fatal(err)
	}
	if err := waitCaptureWatchReady(p, executable, nil, 20*time.Millisecond); err == nil {
		t.Fatal("missing observer was reported ready")
	}
}

func TestCaptureWatchReadinessRequiresKnownManagedActiveOutput(t *testing.T) {
	for _, state := range []string{"profile", "collection", "idle", "unknown"} {
		t.Run(state, func(t *testing.T) {
			f := newVideoFixture(t)
			switch state {
			case "profile":
				f.profile = "Ordinary profile"
			case "collection":
				f.collection = "Ordinary collection"
			case "idle":
				f.active = false
			case "unknown":
				f.recordMalformed = true
			}
			_, dial := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			discoveries := 0
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			err := watchCaptureWith(ctx, p, captureWatchDeps{
				load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }, connect: dial,
				discover: func(context.Context) GameIdentity {
					discoveries++
					return GameIdentity{AppID: 42, State: "running"}
				}, interval: time.Millisecond,
			})
			if errors.Is(err, context.DeadlineExceeded) || discoveries != 0 {
				t.Fatalf("unconfirmed output reached discovery: calls=%d err=%v", discoveries, err)
			}
			executable, err := captureWatchExecutable()
			if err != nil {
				t.Fatal(err)
			}
			if err := waitCaptureWatchReady(p, executable, nil, 20*time.Millisecond); err == nil {
				t.Fatal("unconfirmed output announced observer readiness")
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests)
			if status := ReadCaptureVideoStatus(p); status.Watching || status.Frames != "unknown" {
				t.Fatalf("unconfirmed output announced frame health: %+v", status)
			}
		})
	}
}

func TestCaptureWatchInitialObservationFailureDoesNotAnnounceReadinessWhileRetrying(t *testing.T) {
	for _, failure := range []string{"connection", "output"} {
		t.Run(failure, func(t *testing.T) {
			f := newVideoFixture(t)
			f.recordMalformed = true
			_, dial := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			firstFailed, release := make(chan struct{}), make(chan struct{})
			result := make(chan error, 1)
			loads := 0
			go func() {
				deps := captureWatchDeps{
					load: func(Paths) (Settings, Secrets, error) {
						loads++
						if loads == 2 {
							close(firstFailed)
							select {
							case <-release:
							case <-ctx.Done():
							}
						}
						return s, Secrets{}, nil
					}, connect: dial,
					discover: func(context.Context) GameIdentity { return GameIdentity{State: "idle"} },
					interval: time.Millisecond,
				}
				if failure == "connection" {
					deps.connect = func(context.Context, Secrets) (*automation.Client, error) {
						return nil, errors.New("fixture connection unavailable")
					}
				}
				result <- watchCaptureWith(ctx, p, deps)
			}()
			select {
			case <-firstFailed:
			case <-ctx.Done():
				t.Fatal("initial observation did not remain available for a bounded retry")
			}
			executable, err := captureWatchExecutable()
			if err != nil {
				t.Fatal(err)
			}
			// Poll while the retry is deliberately blocked: checking only after
			// exhaustion would miss false readiness published by the first error.
			if err := waitCaptureWatchReady(p, executable, nil, 25*time.Millisecond); err == nil {
				t.Fatal("failed initial observation announced startup readiness")
			}
			if record, fresh := readCaptureVideoRecord(p); !fresh || record.Watching || record.Frames != "unknown" {
				t.Fatalf("initial failure published active observation: %+v", record)
			}
			close(release)
			select {
			case err := <-result:
				if err == nil || errors.Is(err, context.DeadlineExceeded) {
					t.Fatalf("initial observation failures did not exhaust their retry budget: %v", err)
				}
			case <-ctx.Done():
				t.Fatal("observer did not exhaust bounded initial retries")
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			assertCaptureReadOnly(t, f.requests)
		})
	}
}
