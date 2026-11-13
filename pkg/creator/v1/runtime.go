package v1

import (
	"context"
	"time"

	api "github.com/szmyty/obsgod/pkg/api/v1"
)

// OBS is fulfilled by *api.Client. It deliberately contains no transport or
// external account methods, and can be implemented by an importing application.
type OBS interface {
	Snapshot(context.Context) (api.Snapshot, error)
	ApplyWorkflow(context.Context, api.WorkflowPlan, api.Approval) (api.WorkflowResult, error)
	ConfigureService(context.Context, api.RTMPService, api.Approval) error
	VerifyService(context.Context, api.RTMPService) error
	StartStream(context.Context, api.Approval) (api.StreamState, error)
	StopStream(context.Context, api.Approval) (api.StreamState, error)
	StartRecording(context.Context, api.Approval) error
	StopRecording(context.Context, api.Approval) (string, error)
	StartReplayBuffer(context.Context, api.Approval) error
	StopReplayBuffer(context.Context, api.Approval) error
	SelectScene(context.Context, string, api.Approval) error
}
type Event struct {
	Stage   string `json:"stage"`
	Outcome string `json:"outcome"`
}
type Result struct {
	SchemaVersion     int           `json:"schema_version"`
	OK                bool          `json:"ok"`
	Operation         string        `json:"operation"`
	Events            []Event       `json:"events"`
	Snapshot          *api.Snapshot `json:"snapshot,omitempty"`
	Error             *api.Error    `json:"error,omitempty"`
	ProviderReception string        `json:"provider_reception"`
}

func initial(op string) Result {
	return Result{SchemaVersion: 1, Operation: op, Events: []Event{}, ProviderReception: "unknown"}
}
func (r *Result) failed(stage string, e error) error {
	r.Events = append(r.Events, Event{stage, "failed"})
	r.Error = api.Failure(r.Operation, e)
	return r.Error
}
func (r *Result) failure(stage string, e error) (Result, error) {
	err := r.failed(stage, e)
	return *r, err
}
func (r *Result) applied(stage string) { r.Events = append(r.Events, Event{stage, "confirmed"}) }
func approvalError(op string) error    { return &api.Error{Code: api.ApprovalRequired, Operation: op} }
func conflict(op string) error         { return &api.Error{Code: api.Conflict, Operation: op} }

// Start leaves successfully started outputs running after a later failure. It
// reports the precise completed stages and never blindly retries or rolls back.
// Callers own connection lifecycle and must Close after cancellation.
func Start(ctx context.Context, obs OBS, p Profile, service api.RTMPService, a api.Approval) (Result, error) {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()
	r := initial("creator.start")
	if e := p.Validate(); e != nil {
		return r.failure("preflight", e)
	}
	if e := service.Validate(); e != nil {
		return r.failure("preflight", e)
	}
	if !a.Settings || !a.Streaming || (p.Workflow.RecordingEnabled && !a.Recording) || (p.Workflow.ReplayBufferEnabled && !a.ReplayBuffer) {
		return r.failure("preflight", approvalError(r.Operation))
	}
	if obs == nil {
		return r.failure("preflight", invalid(r.Operation))
	}
	before, e := obs.Snapshot(ctx)
	if e != nil {
		return r.failure("preflight", e)
	}
	r.applied("preflight")
	if before.Stream.Active || before.Stream.Reconnecting {
		// An active stream may belong to a different workflow. Reconcile private
		// service, selected settings and requested local outputs before reuse.
		if (p.Workflow.OBSProfile != "" && before.Profile != p.Workflow.OBSProfile) || (p.Workflow.SceneCollection != "" && before.Collection != p.Workflow.SceneCollection) || (p.Workflow.RecordingEnabled && !before.Recording.Active) || (p.Workflow.ReplayBufferEnabled && !before.ReplayBufferActive) {
			return r.failure("reconcile", conflict(r.Operation))
		}
		if e = obs.VerifyService(ctx, service); e != nil {
			return r.failure("provider_configured", e)
		}
		r.applied("provider_configured")
	} else {
		settings := p.Workflow
		settings.LiveScene = ""
		settings.PostStartDelay = ""
		settings.RecordingEnabled = false
		settings.ReplayBufferEnabled = false
		if _, e = obs.ApplyWorkflow(ctx, settings, a); e != nil {
			return r.failure("obs_settings", e)
		}
		r.applied("obs_settings")
		if e = obs.ConfigureService(ctx, service, a); e != nil {
			return r.failure("provider_configured", e)
		}
		r.applied("provider_configured")
		if p.Workflow.ReplayBufferEnabled {
			if e = obs.StartReplayBuffer(ctx, a); e != nil {
				return r.failure("replay_active", e)
			}
			r.applied("replay_active")
		}
		if p.Workflow.RecordingEnabled {
			if e = obs.StartRecording(ctx, a); e != nil {
				return r.failure("recording_active", e)
			}
			r.applied("recording_active")
		}
	}
	s, e := obs.StartStream(ctx, a)
	if e != nil {
		return r.failure("stream_progressing", e)
	}
	if !s.Active || s.Reconnecting {
		return r.failure("stream_progressing", conflict(r.Operation))
	}
	r.applied("stream_progressing")
	delay, _ := p.Delay()
	if delay > 0 {
		timer := time.NewTimer(delay)
		defer timer.Stop()
		select {
		case <-ctx.Done():
			return r.failure("readiness_delay", ctx.Err())
		case <-timer.C:
		}
		r.applied("readiness_delay")
	}
	if p.Workflow.LiveScene != "" {
		if e = obs.SelectScene(ctx, p.Workflow.LiveScene, a); e != nil {
			return r.failure("live_scene", e)
		}
		r.applied("live_scene")
	}
	after, e := obs.Snapshot(ctx)
	if e != nil {
		return r.failure("final_status", e)
	}
	if !after.Stream.Active || after.Stream.Reconnecting || (p.Workflow.RecordingEnabled && !after.Recording.Active) || (p.Workflow.ReplayBufferEnabled && !after.ReplayBufferActive) {
		return r.failure("final_status", conflict(r.Operation))
	}
	r.OK = true
	r.Snapshot = &after
	r.applied("final_status")
	return r, nil
}
func Status(ctx context.Context, obs OBS) (Result, error) {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	r := initial("creator.status")
	if obs == nil {
		return r.failure("status", invalid(r.Operation))
	}
	s, e := obs.Snapshot(ctx)
	if e != nil {
		return r.failure("status", e)
	}
	r.OK = true
	r.Snapshot = &s
	r.applied("status")
	return r, nil
}

// Stop preserves files and leaves OBS running. Local recording/replay are only
// stopped when both the reviewed policy and invocation approval request it.
func Stop(ctx context.Context, obs OBS, p Profile, a api.Approval) (Result, error) {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()
	r := initial("creator.stop")
	if e := p.Validate(); e != nil {
		return r.failure("preflight", e)
	}
	if !a.Streaming || (p.EndingScene != "" && !a.Settings) || (p.StopRecording && !a.Recording) || (p.StopReplayBuffer && !a.ReplayBuffer) {
		return r.failure("preflight", approvalError(r.Operation))
	}
	if obs == nil {
		return r.failure("preflight", invalid(r.Operation))
	}
	before, e := obs.Snapshot(ctx)
	if e != nil {
		return r.failure("preflight", e)
	}
	r.applied("preflight")
	if p.EndingScene != "" && (before.Stream.Active || before.Stream.Reconnecting) {
		if e = obs.SelectScene(ctx, p.EndingScene, a); e != nil {
			return r.failure("ending_scene", e)
		}
		r.applied("ending_scene")
	}
	s, e := obs.StopStream(ctx, a)
	if e != nil {
		return r.failure("stream_stopped", e)
	}
	if s.Active || s.Reconnecting {
		return r.failure("stream_stopped", conflict(r.Operation))
	}
	r.applied("stream_stopped")
	if p.StopRecording {
		if _, e = obs.StopRecording(ctx, a); e != nil {
			return r.failure("recording_stopped", e)
		}
		r.applied("recording_stopped")
	}
	if p.StopReplayBuffer {
		if e = obs.StopReplayBuffer(ctx, a); e != nil {
			return r.failure("replay_stopped", e)
		}
		r.applied("replay_stopped")
	}
	after, e := obs.Snapshot(ctx)
	if e != nil {
		return r.failure("final_status", e)
	}
	if after.Stream.Active || after.Stream.Reconnecting || (p.StopRecording && after.Recording.Active) || (p.StopReplayBuffer && after.ReplayBufferActive) {
		return r.failure("final_status", conflict(r.Operation))
	}
	r.OK = true
	r.Snapshot = &after
	r.applied("final_status")
	return r, nil
}

// Extensions describes supported local boundaries, not installed integrations.
type Extensions struct {
	SchemaVersion     int      `json:"schema_version"`
	Providers         []string `json:"rtmp_providers"`
	Events            []string `json:"lifecycle_events"`
	MultiOutputPolicy string   `json:"multi_output_policy"`
	ExternalHooks     string   `json:"external_hooks"`
	ContentPipeline   string   `json:"content_pipeline"`
}

func Discover() Extensions {
	return Extensions{1, []string{"kick", "twitch", "youtube", "custom"}, []string{"preflight", "obs_settings", "provider_configured", "replay_active", "recording_active", "stream_progressing", "readiness_delay", "live_scene", "ending_scene", "stream_stopped", "recording_stopped", "replay_stopped", "final_status"}, "one_obs_output_one_ingest_destination", "caller_consumes_results_no_automatic_subprocesses", "external_explicit_consumer_of_finalized_local_media"}
}
