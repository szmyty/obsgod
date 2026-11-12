//go:build linux

package deck

import (
	"context"
	"errors"
	"reflect"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func TestCaptureWatchTransitionsRerouteAudioWithoutStartingOrStoppingOutput(t *testing.T) {
	f := newVideoFixture(t)
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	identities := []uint32{42, 42, 0, 43, 43}
	loads, index := 0, 0
	var current uint32
	var routes []uint32
	deps := captureWatchDeps{load: func(Paths) (Settings, Secrets, error) {
		loads++
		if loads > len(identities) {
			f.mu.Lock()
			f.active = false
			f.mu.Unlock()
		}
		return s, Secrets{}, nil
	}, connect: dial, discover: func(context.Context) GameIdentity {
		current = identities[index]
		index++
		if current == 0 {
			return GameIdentity{State: "idle"}
		}
		return GameIdentity{AppID: current, State: "running"}
	}, routeAudio: func(context.Context, *automation.Client, Paths, Settings) error {
		routes = append(routes, current)
		return nil
	}, interval: time.Millisecond}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := watchCaptureWith(ctx, p, deps); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(routes, []uint32{42, 0, 43}) {
		t.Fatalf("audio was not rerouted once per identity: %v", routes)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	assertNoOutputCommands(t, f)
	if f.scene != IdleScene {
		t.Fatal("observer did not leave idle after confirmed output stop")
	}
	var pipelines []string
	for _, request := range f.requests {
		if request.Type == "CreateInput" || request.Type == "SetInputSettings" {
			if request.Data["inputName"] == GameCaptureInput {
				settings := request.Data["inputSettings"].(map[string]any)
				if pipeline, ok := settings["pipeline"].(string); ok {
					pipelines = append(pipelines, pipeline)
				}
			}
		}
	}
	if len(pipelines) != 2 {
		t.Fatalf("game capture was not cached across stable identity: %v", pipelines)
	}
	if status := ReadCaptureVideoStatus(p); status.State != "stopped" || status.Watching {
		t.Fatalf("stopped observer status %+v", status)
	}
}
func TestCaptureWatchRefusesDifferentCollectionWithoutMutation(t *testing.T) {
	f := newVideoFixture(t)
	f.collection = "Ordinary collection"
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	err := watchCaptureWith(context.Background(), p, captureWatchDeps{load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }, connect: dial, discover: func(context.Context) GameIdentity { return GameIdentity{AppID: 42, State: "running"} }, interval: time.Millisecond})
	if err == nil {
		t.Fatal("observer accepted an ordinary collection")
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, request := range f.requests {
		if len(request.Type) < 3 || request.Type[:3] != "Get" {
			t.Fatalf("modified ordinary collection through %s", request.Type)
		}
	}
}
func TestCaptureWatchRetriesAudioAndResetsTargetAfterConnectionFailure(t *testing.T) {
	f := newVideoFixture(t)
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	loads, connections, routes := 0, 0, 0
	deps := captureWatchDeps{load: func(Paths) (Settings, Secrets, error) {
		loads++
		if loads > 4 {
			f.mu.Lock()
			f.active = false
			f.mu.Unlock()
		}
		return s, Secrets{}, nil
	}, connect: func(ctx context.Context, secret Secrets) (*automation.Client, error) {
		connections++
		if connections == 2 {
			return nil, errors.New("fixture disconnect")
		}
		return dial(ctx, secret)
	}, discover: func(context.Context) GameIdentity { return GameIdentity{AppID: 42, State: "running"} }, routeAudio: func(context.Context, *automation.Client, Paths, Settings) error {
		routes++
		if routes == 1 {
			return errors.New("fixture audio unavailable")
		}
		return nil
	}, interval: time.Millisecond}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := watchCaptureWith(ctx, p, deps); err != nil {
		t.Fatal(err)
	}
	if routes != 2 {
		t.Fatalf("audio failure or reconnect was not retried: %d", routes)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	assertNoOutputCommands(t, f)
	configured := 0
	for _, request := range f.requests {
		if request.Data["inputName"] == GameCaptureInput && (request.Type == "CreateInput" || request.Type == "SetInputSettings") {
			settings := request.Data["inputSettings"].(map[string]any)
			if _, ok := settings["pipeline"]; ok {
				configured++
			}
		}
	}
	if configured != 2 {
		t.Fatalf("reconnect did not reset game target: %d", configured)
	}
}

func TestCaptureWatchUsesSeparateLifetimeLockFromOutputControl(t *testing.T) {
	f := newVideoFixture(t)
	f.active = false
	_, dial := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	unlock, err := Lock(context.Background(), p)
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	err = watchCaptureWith(ctx, p, captureWatchDeps{load: func(Paths) (Settings, Secrets, error) { return s, Secrets{}, nil }, connect: dial, discover: func(context.Context) GameIdentity { return GameIdentity{State: "idle"} }, interval: time.Millisecond})
	if err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.requests) == 0 {
		t.Fatal("observer was blocked by the initiating output operation")
	}
	assertNoOutputCommands(t, f)
	if status := ReadCaptureVideoStatus(p); status.State != "stopped" {
		t.Fatalf("observer did not run while output lock was held: %+v", status)
	}
}
