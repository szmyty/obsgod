//go:build linux

package deck

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

type resilienceFixture struct {
	active       bool
	managed      bool
	observations int
	observe      func(int) (resilienceObservation, error)
	routes       []AudioRouting
	rebindErr    error
	previous     AudioRouting
	changes      int
	guards       int
	guardErr     error
}

func (f *resilienceFixture) Observe(context.Context) (resilienceObservation, error) {
	f.observations++
	if f.observe != nil {
		return f.observe(f.observations)
	}
	return resilienceObservation{Managed: f.managed, Active: f.active}, nil
}
func (f *resilienceFixture) Close() error { return nil }
func (f *resilienceFixture) GuardMedia(context.Context, Paths) error {
	f.guards++
	return f.guardErr
}
func (f *resilienceFixture) Rebind(_ context.Context, _ Settings, route AudioRouting) (bool, error) {
	f.routes = append(f.routes, route)
	if f.rebindErr != nil {
		return false, f.rebindErr
	}
	changed := route.OutputMonitor != f.previous.OutputMonitor || route.MicrophoneDevice != f.previous.MicrophoneDevice
	if changed {
		f.changes++
		f.previous = route
	}
	return changed, nil
}

func recoveryTestDeps(f *resilienceFixture) resilienceDeps {
	return resilienceDeps{
		load: func(Paths) (Settings, Secrets, error) { return DefaultSettings(), Secrets{}, nil },
		connect: func(context.Context, Secrets) (resilienceConnection, error) {
			return f, nil
		},
		discover: func(context.Context, bool) (AudioRouting, error) {
			return AudioRouting{OutputMonitor: "private-output-device", RouteReason: "default_output"}, nil
		},
		interval: time.Millisecond,
	}
}

func TestResilienceFollowsHeadphoneMicrophoneChangesAcrossCaptureModes(t *testing.T) {
	for _, mode := range []string{"screen", "game"} {
		t.Run(mode, func(t *testing.T) {
			f := &resilienceFixture{managed: true, active: true}
			deps := recoveryTestDeps(f)
			deps.load = func(Paths) (Settings, Secrets, error) {
				s := DefaultSettings()
				s.CaptureMode, s.Microphone = mode, true
				return s, Secrets{}, nil
			}
			routes := []AudioRouting{
				{OutputMonitor: "speakers.monitor", MicrophoneDevice: "deck-microphone", MicrophoneRequested: true},
				{OutputMonitor: "headset.monitor", MicrophoneDevice: "headset-microphone", MicrophoneRequested: true},
				{OutputMonitor: "headset.monitor", MicrophoneDevice: "headset-microphone", MicrophoneRequested: true},
			}
			index := 0
			deps.discover = func(_ context.Context, microphone bool) (AudioRouting, error) {
				if !microphone {
					t.Fatal("recovery discarded the selected microphone policy")
				}
				return routes[index], nil
			}
			deps.wait = func(context.Context, time.Duration) error {
				index++
				if index == len(routes) {
					f.active = false
				}
				return nil
			}
			p := testPaths(t)
			if err := watchResilienceWith(context.Background(), p, deps); err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(f.routes, routes) || f.changes != 2 || f.guards != 3 {
				t.Fatalf("incorrect hotplug routing: %+v changes=%d", f.routes, f.changes)
			}
			status := ReadResilienceStatus(p)
			if status.State != "stopped" || status.Watching || !status.OutputKnown || status.Recoveries != 2 {
				t.Fatalf("incorrect stopped state: %+v", status)
			}
		})
	}
}

func TestResilienceStopsAtThreeFailuresWithBoundedBackoffAndPrivateErrors(t *testing.T) {
	for _, failure := range []string{"connection", "snapshot", "storage", "device", "rebind"} {
		t.Run(failure, func(t *testing.T) {
			p := testPaths(t)
			f := &resilienceFixture{managed: true, active: true}
			deps := recoveryTestDeps(f)
			privateErr := errors.New("private-device-password-session-server")
			connects, discoveries := 0, 0
			deps.connect = func(context.Context, Secrets) (resilienceConnection, error) {
				connects++
				if failure == "connection" {
					return nil, privateErr
				}
				return f, nil
			}
			if failure == "snapshot" {
				f.observe = func(int) (resilienceObservation, error) { return resilienceObservation{}, privateErr }
			}
			if failure == "storage" {
				f.guardErr = privateErr
			}
			deps.discover = func(context.Context, bool) (AudioRouting, error) {
				discoveries++
				if failure == "device" {
					return AudioRouting{}, privateErr
				}
				return AudioRouting{OutputMonitor: "private-device"}, nil
			}
			if failure == "rebind" {
				f.rebindErr = privateErr
			}
			var delays []time.Duration
			deps.wait = func(_ context.Context, delay time.Duration) error { delays = append(delays, delay); return nil }
			err := watchResilienceWith(context.Background(), p, deps)
			if err == nil || strings.Contains(err.Error(), "private-") || connects != 3 || !reflect.DeepEqual(delays, []time.Duration{time.Millisecond, 2 * time.Millisecond}) {
				t.Fatalf("recovery was not bounded/redacted: %v connects=%d delays=%v", err, connects, delays)
			}
			status := ReadResilienceStatus(p)
			if status.State != "exhausted" || status.Watching || status.Failures != 3 || status.OutputKnown != (failure == "device") {
				t.Fatalf("incorrect exhausted status: %+v", status)
			}
			encoded, _ := json.Marshal(status)
			if strings.Contains(string(encoded), "private-") {
				t.Fatal("private error was persisted")
			}
			if (failure == "connection" || failure == "snapshot") && (discoveries != 0 || len(f.routes) != 0) {
				t.Fatal("unknown output caused device discovery or mutation")
			}
			if (failure == "device" || failure == "storage") && len(f.routes) != 0 {
				t.Fatal("an unverified device was applied")
			}
		})
	}
}

func TestResilienceDoesNotRecoverStoppedOrUnmanagedOutput(t *testing.T) {
	for _, mode := range []string{"stopped", "stopped-after-discovery", "unmanaged", "unmanaged-after-discovery"} {
		t.Run(mode, func(t *testing.T) {
			f := &resilienceFixture{managed: true, active: true}
			f.observe = func(observation int) (resilienceObservation, error) {
				managed, active := true, true
				if observation >= 2 || !strings.HasSuffix(mode, "after-discovery") {
					if strings.HasPrefix(mode, "unmanaged") {
						managed = false
					} else {
						active = false
					}
				}
				return resilienceObservation{Managed: managed, Active: active}, nil
			}
			p := testPaths(t)
			deps := recoveryTestDeps(f)
			deps.wait = func(context.Context, time.Duration) error { t.Fatal("idle/unmanaged observer retried"); return nil }
			err := watchResilienceWith(context.Background(), p, deps)
			if (err != nil) != strings.HasPrefix(mode, "unmanaged") || len(f.routes) != 0 {
				t.Fatalf("stopped/unmanaged output was mutated: %v routes=%v", err, f.routes)
			}
			if status := ReadResilienceStatus(p); status.Watching || !status.OutputKnown {
				t.Fatalf("false recovery state: %+v", status)
			}
		})
	}
}

func TestResilienceReconnectDoesNotRestartStoppedOutputAndResetsFailureBudget(t *testing.T) {
	p := testPaths(t)
	f := &resilienceFixture{managed: true, active: true}
	deps := recoveryTestDeps(f)
	connects := 0
	deps.connect = func(context.Context, Secrets) (resilienceConnection, error) {
		connects++
		if connects == 1 || connects == 3 {
			return nil, errors.New("temporary control disconnect")
		}
		if connects == 4 {
			f.active = false
		}
		return f, nil
	}
	deps.wait = func(context.Context, time.Duration) error { return nil }
	if err := watchResilienceWith(context.Background(), p, deps); err != nil {
		t.Fatal(err)
	}
	if connects != 4 || len(f.routes) != 1 || f.changes != 1 {
		t.Fatalf("restored connection changed stopped output: connections=%d routes=%v", connects, f.routes)
	}
	if status := ReadResilienceStatus(p); status.State != "stopped" || status.Failures != 1 {
		t.Fatalf("successful cycle did not reset failure budget: %+v", status)
	}
}

func TestResilienceExplicitControlLeaseWinsAndCancellationMakesNoDeviceChanges(t *testing.T) {
	p := testPaths(t)
	unlock, err := Lock(context.Background(), p)
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	f := &resilienceFixture{managed: true, active: true}
	deps := recoveryTestDeps(f)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	deps.wait = func(context.Context, time.Duration) error { cancel(); return ctx.Err() }
	err = watchResilienceWith(ctx, p, deps)
	if !errors.Is(err, context.Canceled) || len(f.routes) != 0 {
		t.Fatalf("recovery did not yield to explicit control: %v routes=%v", err, f.routes)
	}
	if status := ReadResilienceStatus(p); status.Watching || status.OutputKnown {
		t.Fatalf("cancelled observer claimed current output knowledge: %+v", status)
	}
}

func TestResilienceUnsafeControlLeaseFailsBoundedlyInsteadOfClaimingBusy(t *testing.T) {
	for _, lifetime := range []bool{false, true} {
		p := testPaths(t)
		leasePaths := p
		if lifetime {
			leasePaths = resiliencePaths(p)
		}
		if err := privateDir(leasePaths.State); err != nil {
			t.Fatal(err)
		}
		target := filepath.Join(t.TempDir(), "private-unrelated-file")
		if err := os.WriteFile(target, []byte("preserve"), 0600); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(target, filepath.Join(leasePaths.State, "control.lock")); err != nil {
			t.Fatal(err)
		}
		f := &resilienceFixture{managed: true, active: true}
		deps := recoveryTestDeps(f)
		waits := 0
		deps.wait = func(context.Context, time.Duration) error { waits++; return nil }
		err := watchResilienceWith(context.Background(), p, deps)
		if err == nil || strings.Contains(err.Error(), "private-") || len(f.routes) != 0 || waits > 2 {
			t.Fatalf("unsafe control lease was trusted or retried without bound: err=%v routes=%v waits=%d", err, f.routes, waits)
		}
		original, err := os.ReadFile(target)
		if err != nil || string(original) != "preserve" {
			t.Fatal("recovery changed an unrelated file")
		}
		if !lifetime && ReadResilienceStatus(p).State != "exhausted" {
			t.Fatal("unsafe normal lease did not produce explicit exhausted state")
		}
	}
}

func TestResilienceReceiptRejectsStaleFutureUnsafeAndPrivateMessages(t *testing.T) {
	p := testPaths(t)
	path := filepath.Join(resiliencePaths(p).State, "status.json")
	for _, test := range []struct {
		name string
		when time.Time
		mode os.FileMode
	}{
		{"stale", time.Now().Add(-9 * time.Second), 0600},
		{"future", time.Now().Add(5 * time.Second), 0600},
		{"public", time.Now(), 0644},
	} {
		t.Run(test.name, func(t *testing.T) {
			if err := writeJSON(path, resilienceRecord{ResilienceStatus: ResilienceStatus{State: "observing", Watching: true, OutputKnown: true, Updated: test.when}}); err != nil {
				t.Fatal(err)
			}
			if err := os.Chmod(path, test.mode); err != nil {
				t.Fatal(err)
			}
			if status := ReadResilienceStatus(p); status.State != "unknown" || status.Watching || status.OutputKnown {
				t.Fatalf("unsafe receipt trusted: %+v", status)
			}
		})
	}
	if err := writeJSON(path, resilienceRecord{ResilienceStatus: ResilienceStatus{State: "observing", Message: "private-device-id", Watching: true, OutputKnown: true, Updated: time.Now()}}); err != nil {
		t.Fatal(err)
	}
	if status := ReadResilienceStatus(p); strings.Contains(status.Message, "private-") {
		t.Fatal("status file injected private data")
	}
	if err := writeJSON(filepath.Join(p.State, "audio-status.json"), audioReceipt{Observed: time.Now().Add(-6 * time.Second), Status: AudioStatus{State: "ready", OutputAvailable: true, MicrophoneAvailable: true, Signal: "signal"}}); err != nil {
		t.Fatal(err)
	}
	if status := readAudioStatus(p); status == nil || status.State != "unknown" || status.OutputAvailable || status.MicrophoneAvailable || status.Signal != "unmeasured" {
		t.Fatalf("old audio route was presented as current: %+v", status)
	}
}
