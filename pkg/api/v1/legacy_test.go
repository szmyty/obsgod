package v1

import (
	"context"
	"errors"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type legacyBackend struct {
	backend
	calls   atomic.Int32
	closes  atomic.Int32
	request automation.LegacyRequest
	result  automation.LegacyResult
	err     error
	entered chan struct{}
	release chan struct{}
}

func (b *legacyBackend) Close() error { b.closes.Add(1); return nil }
func (b *legacyBackend) Legacy(ctx context.Context, r automation.LegacyRequest) (automation.LegacyResult, error) {
	b.calls.Add(1)
	b.request = r
	if b.entered != nil {
		close(b.entered)
		select {
		case <-ctx.Done():
			return automation.LegacyResult{}, ctx.Err()
		case <-b.release:
		}
	}
	return b.result, b.err
}

func TestLegacyCompatibilityRequiresItsExactInvocationApproval(t *testing.T) {
	groups := []struct {
		ops   []LegacyOperation
		right Approval
		wrong Approval
	}{
		{[]LegacyOperation{LegacyToggleStream, LegacyStartStream, LegacyStopStream}, Approval{Streaming: true}, Approval{Settings: true, Recording: true, ReplayBuffer: true, VirtualCamera: true}},
		{[]LegacyOperation{LegacyToggleRecording, LegacyStartRecording, LegacyStopRecording, LegacyPauseRecording, LegacyResumeRecording}, Approval{Recording: true}, Approval{Settings: true, Streaming: true, ReplayBuffer: true, VirtualCamera: true}},
		{[]LegacyOperation{LegacyStartReplayBuffer, LegacyStopReplayBuffer, LegacySaveReplayBuffer}, Approval{ReplayBuffer: true}, Approval{Settings: true, Streaming: true, Recording: true, VirtualCamera: true}},
		{[]LegacyOperation{LegacyToggleVirtualCam, LegacyStartVirtualCam, LegacyStopVirtualCam}, Approval{VirtualCamera: true}, Approval{Settings: true, Streaming: true, Recording: true, ReplayBuffer: true}},
		{[]LegacyOperation{LegacySetCurrentScene, LegacySetPreviewScene, LegacySetCurrentSceneCollection, LegacySetSceneItemVisible, LegacyToggleSceneItem, LegacyCenterSceneItem, LegacySetCurrentProfile, LegacySetLabelText, LegacyToggleMute, LegacySetStudioModeEnabled, LegacyTriggerStudioModeTransition}, Approval{Settings: true}, Approval{Streaming: true, Recording: true, ReplayBuffer: true, VirtualCamera: true}},
	}
	for _, group := range groups {
		for _, op := range group.ops {
			t.Run(string(op), func(t *testing.T) {
				b := &legacyBackend{}
				c := newClient(b, time.Second)
				defer c.Close()
				for _, approval := range []Approval{{}, group.wrong} {
					_, err := c.Legacy(context.Background(), LegacyRequest{Operation: op}, approval)
					var domain *Error
					if !errors.As(err, &domain) || domain.Code != ApprovalRequired || b.calls.Load() != 0 {
						t.Fatalf("missing/wrong approval reached OBS: err=%v calls=%d", err, b.calls.Load())
					}
				}
				if _, err := c.Legacy(context.Background(), LegacyRequest{Operation: op}, group.right); err != nil || b.calls.Load() != 1 {
					t.Fatalf("exact approval failed: err=%v calls=%d", err, b.calls.Load())
				}
				// Approval is not remembered for a subsequent invocation.
				if _, err := c.Legacy(context.Background(), LegacyRequest{Operation: op}, Approval{}); err == nil || b.calls.Load() != 1 {
					t.Fatal("approval leaked into the next invocation")
				}
			})
		}
	}
}

func TestLegacyCompatibilityIsClosedAndNarrow(t *testing.T) {
	b := &legacyBackend{}
	c := newClient(b, time.Second)
	defer c.Close()
	for _, op := range []LegacyOperation{"", "GetStreamServiceSettings", "private-operation-value"} {
		_, err := c.Legacy(context.Background(), LegacyRequest{Operation: op}, Approval{Settings: true, Streaming: true, Recording: true, ReplayBuffer: true, VirtualCamera: true})
		var domain *Error
		if !errors.As(err, &domain) || domain.Code != InvalidInput || b.calls.Load() != 0 || strings.Contains(err.Error(), "private-operation-value") {
			t.Fatalf("unknown protocol escape was accepted or echoed: %v", err)
		}
	}
	reads := []LegacyOperation{LegacyGetStreamStatus, LegacyGetRecordingStatus, LegacyListScenes, LegacyGetCurrentScene, LegacyListSceneCollections, LegacyGetCurrentSceneCollection, LegacyListSceneItems, LegacyGetSceneItemVisibility, LegacyListProfiles, LegacyGetCurrentProfile, LegacyGetReplayBufferActive, LegacyGetVirtualCamActive, LegacyGetSpecialSources, LegacyIsStudioModeEnabled}
	for _, op := range reads {
		if _, err := c.Legacy(context.Background(), LegacyRequest{Operation: op}, Approval{}); err != nil {
			t.Fatalf("read %s requires mutation approval: %v", op, err)
		}
	}
	if int(b.calls.Load()) != len(reads) {
		t.Fatal("read added backend operations")
	}
}

func TestLegacyCompatibilityDetachesRequestAndResultStorage(t *testing.T) {
	b := &legacyBackend{result: automation.LegacyResult{Names: []string{"First", "First", ""}, Visibility: []automation.LegacyItemVisibility{{Name: "Item", Visible: true}}, Output: automation.LegacyOutputStatus{Active: true, Paused: true, Timecode: "12:34:56.789"}}}
	c := newClient(b, time.Second)
	defer c.Close()
	names := []string{"Item"}
	got, err := c.Legacy(context.Background(), LegacyRequest{Operation: LegacyGetSceneItemVisibility, Scene: "Game Scene", Names: names}, Approval{})
	if err != nil {
		t.Fatal(err)
	}
	names[0] = "changed caller"
	got.Names[0] = "changed result"
	got.Visibility[0].Name = "changed result"
	if b.request.Names[0] != "Item" || b.result.Names[0] != "First" || b.result.Visibility[0].Name != "Item" || got.Output.Timecode != "12:34:56.789" {
		t.Fatal("request/result storage or exact timecode was not preserved")
	}
	b.err = errors.New("raw private key and password")
	_, err = c.Legacy(context.Background(), LegacyRequest{Operation: LegacyGetStreamStatus}, Approval{})
	if err == nil || strings.Contains(err.Error(), "private") || strings.Contains(err.Error(), "password") {
		t.Fatal("backend free-form text escaped")
	}
}

func TestLegacyCompatibilityCancellationOwnsOnlyAcquiredConnection(t *testing.T) {
	b := &legacyBackend{entered: make(chan struct{}), release: make(chan struct{})}
	c := newClient(b, time.Second)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { _, err := c.Legacy(ctx, LegacyRequest{Operation: LegacyListProfiles}, Approval{}); done <- err }()
	<-b.entered
	waitCtx, waitCancel := context.WithCancel(context.Background())
	waitCancel()
	if _, err := c.Legacy(waitCtx, LegacyRequest{Operation: LegacyStartStream}, Approval{Streaming: true}); !errors.Is(err, context.Canceled) || b.closes.Load() != 0 {
		t.Fatalf("unacquired cancellation interrupted another operation: %v closes=%d", err, b.closes.Load())
	}
	cancel()
	if err := <-done; !errors.Is(err, context.Canceled) || b.closes.Load() != 1 || !c.Closed() {
		t.Fatalf("acquired cancellation retained connection: %v closes=%d", err, b.closes.Load())
	}
	if _, err := c.Legacy(context.Background(), LegacyRequest{Operation: LegacyStartStream}, Approval{Streaming: true}); err == nil || b.calls.Load() != 1 {
		t.Fatal("cancelled connection was reused")
	}
	_ = c.Close()
	if b.closes.Load() != 1 {
		t.Fatal("connection closed more than once")
	}
}
