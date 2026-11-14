package automation

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"testing"
)

type workflowResponseFailure struct {
	WorkflowBackend
	state      WorkflowSnapshot
	reads      int
	failRead   int
	failChange string
	err        error
}

func (f *workflowResponseFailure) WorkflowSnapshot(context.Context) (WorkflowSnapshot, error) {
	f.reads++
	if f.reads == f.failRead {
		return WorkflowSnapshot{}, f.err
	}
	return f.state, nil
}
func (f *workflowResponseFailure) SetWorkflowProfile(_ context.Context, name string) error {
	if f.failChange == "profile" {
		return f.err
	}
	f.state.Profile = name
	return nil
}
func (f *workflowResponseFailure) StartWorkflowReplayBuffer(context.Context) error {
	return f.err
}
func (f *workflowResponseFailure) StartRecording(context.Context) error { return f.err }

func TestWorkflowPreservesResponseFailureAtEverySanitizationBoundary(t *testing.T) {
	for _, timeout := range []bool{false, true} {
		for _, tc := range []struct {
			name       string
			plan       WorkflowPlan
			failRead   int
			failChange string
		}{
			{name: "initial observation", failRead: 1},
			{name: "stage preflight", plan: WorkflowPlan{OBSProfile: "Target"}, failRead: 2},
			{name: "stage mutation", plan: WorkflowPlan{OBSProfile: "Target"}, failChange: "profile"},
			{name: "stage readback", plan: WorkflowPlan{OBSProfile: "Target"}, failRead: 3},
			{name: "replay start", plan: WorkflowPlan{ReplayBufferEnabled: true}},
			{name: "recording start", plan: WorkflowPlan{RecordingEnabled: true}},
			{name: "final observation", failRead: 4},
		} {
			t.Run(fmt.Sprintf("%s/timeout=%v", tc.name, timeout), func(t *testing.T) {
				fixture := &workflowResponseFailure{
					state:    WorkflowSnapshot{Profile: "Original", Profiles: []string{"Original", "Target"}},
					failRead: tc.failRead, failChange: tc.failChange,
					err: fmt.Errorf("private backend endpoint/key: %w", &ResponseError{Timeout: timeout}),
				}
				result, err := ApplyWorkflow(context.Background(), fixture, tc.plan, WorkflowApprovals{Settings: true, Recording: true, ReplayBuffer: true})
				var response *ResponseError
				if result.OK || !errors.As(err, &response) || response.Timeout != timeout || errors.Is(err, context.DeadlineExceeded) != timeout {
					t.Fatalf("workflow erased response boundary failure: result=%+v err=%v", result, err)
				}
				if strings.Contains(fmt.Sprintf("%v %+v %#v", err, err, err), "private") {
					t.Fatal("workflow retained arbitrary backend error details")
				}
			})
		}
	}
}
