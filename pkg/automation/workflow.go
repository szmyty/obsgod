package automation

import (
	"context"
	"encoding/json"
	"errors"
	"time"
	"unicode"
	"unicode/utf8"

	obsconfig "github.com/andreykaipov/goobs/api/requests/config"
)

// WorkflowPlan is provider-neutral intent. It never contains credentials or a
// streaming action. Applying it requires approvals supplied outside the plan.
type WorkflowPlan struct {
	OBSProfile          string `json:"obs_profile,omitempty"`
	SceneCollection     string `json:"scene_collection,omitempty"`
	StartingScene       string `json:"starting_scene,omitempty"`
	LiveScene           string `json:"live_scene,omitempty"`
	RecordingEnabled    bool   `json:"recording_enabled"`
	ReplayBufferEnabled bool   `json:"replay_buffer_enabled"`
	ReadinessTimeout    string `json:"readiness_timeout"`
	PostStartDelay      string `json:"post_start_delay"`
}

func (p WorkflowPlan) Durations() (time.Duration, time.Duration, error) {
	ready, delay := 3*time.Second, time.Duration(0)
	var err error
	if p.ReadinessTimeout != "" {
		ready, err = time.ParseDuration(p.ReadinessTimeout)
		if err != nil {
			return 0, 0, errors.New("workflow readiness_timeout must be a duration from 100ms to 30s")
		}
	}
	if ready < 100*time.Millisecond || ready > 30*time.Second {
		return 0, 0, errors.New("workflow readiness_timeout must be from 100ms to 30s")
	}
	if p.PostStartDelay != "" {
		delay, err = time.ParseDuration(p.PostStartDelay)
		if err != nil {
			return 0, 0, errors.New("workflow post_start_delay must be a duration from 0s to 10s")
		}
	}
	if delay < 0 || delay > 10*time.Second {
		return 0, 0, errors.New("workflow post_start_delay must be from 0s to 10s")
	}
	return ready, delay, nil
}

func (p WorkflowPlan) Validate() error {
	for _, name := range []string{p.OBSProfile, p.SceneCollection, p.StartingScene, p.LiveScene} {
		if !utf8.ValidString(name) || len([]rune(name)) > 256 {
			return errors.New("workflow OBS names must be valid text of at most 256 characters")
		}
		for _, character := range name {
			if unicode.IsControl(character) {
				return errors.New("workflow OBS names must not contain control characters")
			}
		}
	}
	_, _, err := p.Durations()
	return err
}

type WorkflowApprovals struct {
	Settings     bool
	Recording    bool
	ReplayBuffer bool
}

func (a WorkflowApprovals) Validate(p WorkflowPlan) error {
	if !a.Settings {
		return errors.New("workflow apply requires --approve; inspect workflow plan or --dry-run first")
	}
	if p.RecordingEnabled && !a.Recording {
		return errors.New("workflow requests local recording; explicitly add --allow-recording or disable it in the plan")
	}
	if p.ReplayBufferEnabled && !a.ReplayBuffer {
		return errors.New("workflow requests the local replay buffer; explicitly add --allow-replay-buffer or disable it in the plan")
	}
	return nil
}

type WorkflowSnapshot struct {
	StreamActive        bool
	RecordingActive     bool
	ReplayBufferActive  bool
	VirtualCameraActive bool
	Profile             string
	Collection          string
	Scene               string
	Profiles            []string
	Collections         []string
	Scenes              []string
}

// WorkflowBackend intentionally excludes StartStream and StopStream. Unknown
// output state must return an error, never a zero snapshot reported as known.
type WorkflowBackend interface {
	WorkflowSnapshot(context.Context) (WorkflowSnapshot, error)
	SetWorkflowProfile(context.Context, string) error
	SetWorkflowCollection(context.Context, string) error
	SetScene(context.Context, string) error
	StartRecording(context.Context) error
	StartWorkflowReplayBuffer(context.Context) error
	Close() error
}

type WorkflowResult struct {
	SchemaVersion int      `json:"schema_version"`
	OK            bool     `json:"ok"`
	Applied       []string `json:"applied"`
	Attempted     string   `json:"attempted,omitempty"`
	Message       string   `json:"message"`
}

// ApplyWorkflow never broadcasts, stops an output, creates OBS content or rolls
// back automatically. On failure the applied stages remain explicit: rollback
// could overwrite a concurrent user's work or stop their recording.
func ApplyWorkflow(ctx context.Context, backend WorkflowBackend, plan WorkflowPlan, approvals WorkflowApprovals) (WorkflowResult, error) {
	result := WorkflowResult{SchemaVersion: 1, Applied: []string{}}
	if err := plan.Validate(); err != nil {
		return result, err
	}
	if err := approvals.Validate(plan); err != nil {
		return result, err
	}
	ready, delay, _ := plan.Durations()
	ctx, cancel := context.WithTimeout(ctx, ready+delay)
	defer cancel()
	recordingStarted, replayStarted := false, false
	read := func() (WorkflowSnapshot, error) {
		state, err := backend.WorkflowSnapshot(ctx)
		if err != nil {
			return state, errors.New("workflow output state is unconfirmed; no further changes were made; inspect OBS and retry")
		}
		if state.StreamActive || state.VirtualCameraActive || (state.RecordingActive && !recordingStarted) || (state.ReplayBufferActive && !replayStarted) {
			return state, errors.New("workflow requires confirmed idle OBS output; stop stream, recording, replay buffer and virtual camera explicitly before retrying")
		}
		return state, nil
	}
	fail := func(err error) (WorkflowResult, error) {
		result.Message = "Workflow stopped; inspect OBS and the applied stages before retrying. Outputs were not stopped automatically."
		if ctx.Err() != nil {
			err = ctx.Err()
		}
		return result, err
	}
	state, err := read()
	if err != nil {
		return fail(err)
	}
	if (plan.OBSProfile != "" && !hasName(state.Profiles, plan.OBSProfile)) || (plan.SceneCollection != "" && !hasName(state.Collections, plan.SceneCollection)) {
		return fail(errors.New("requested OBS profile or scene collection does not exist; create it in OBS before applying this workflow"))
	}
	// Confirm every structural change before dispatching the next one. A lost
	// connection or newly active output ends the workflow rather than guessing.
	stages := []struct {
		name  string
		value string
		apply func(context.Context, string) error
		match func(WorkflowSnapshot) bool
	}{
		{"profile", plan.OBSProfile, backend.SetWorkflowProfile, func(s WorkflowSnapshot) bool { return s.Profile == plan.OBSProfile }},
		{"scene_collection", plan.SceneCollection, backend.SetWorkflowCollection, func(s WorkflowSnapshot) bool { return s.Collection == plan.SceneCollection }},
		{"starting_scene", plan.StartingScene, backend.SetScene, func(s WorkflowSnapshot) bool { return s.Scene == plan.StartingScene }},
	}
	apply := func(name, value string, change func(context.Context, string) error, match func(WorkflowSnapshot) bool) error {
		var err error
		state, err = read()
		if err != nil {
			return err
		}
		if (name == "starting_scene" || name == "live_scene") && !hasName(state.Scenes, value) {
			return errors.New("requested scene is absent in the selected collection; inspect the applied stages and correct the workflow")
		}
		if match(state) {
			return nil
		}
		result.Attempted = name
		if err := change(ctx, value); err != nil {
			return errors.New("workflow OBS change failed; its outcome may be unconfirmed; inspect OBS before retrying")
		}
		result.Applied = append(result.Applied, name)
		for {
			state, err = read()
			if err != nil || match(state) {
				if err == nil {
					result.Attempted = ""
				}
				return err
			}
			if err := pause(ctx, 50*time.Millisecond); err != nil {
				return errors.New("workflow readiness deadline reached; inspect OBS before retrying")
			}
		}
	}
	for _, stage := range stages {
		if stage.value != "" {
			if err := apply(stage.name, stage.value, stage.apply, stage.match); err != nil {
				return fail(err)
			}
		}
	}
	if delay > 0 {
		if err := pause(ctx, delay); err != nil {
			return fail(errors.New("workflow cancelled during its delay; inspect applied stages before retrying"))
		}
		result.Applied = append(result.Applied, "post_start_delay")
	}
	if plan.LiveScene != "" {
		if err := apply("live_scene", plan.LiveScene, backend.SetScene, func(s WorkflowSnapshot) bool { return s.Scene == plan.LiveScene }); err != nil {
			return fail(err)
		}
	}
	if _, err := read(); err != nil {
		return fail(err)
	}
	if plan.ReplayBufferEnabled {
		result.Attempted = "replay_buffer"
		if err := backend.StartWorkflowReplayBuffer(ctx); err != nil {
			return fail(errors.New("replay-buffer start is unconfirmed; inspect OBS; it was not stopped automatically"))
		}
		replayStarted = true
		result.Attempted = ""
		result.Applied = append(result.Applied, "replay_buffer")
	}
	if _, err := read(); err != nil {
		return fail(err)
	}
	if plan.RecordingEnabled {
		result.Attempted = "recording"
		if err := backend.StartRecording(ctx); err != nil {
			return fail(errors.New("recording start is unconfirmed; inspect OBS; it was not stopped automatically"))
		}
		recordingStarted = true
		result.Attempted = ""
		result.Applied = append(result.Applied, "recording")
	}
	state, err = read()
	if err != nil || (plan.RecordingEnabled && !state.RecordingActive) || (plan.ReplayBufferEnabled && !state.ReplayBufferActive) {
		return fail(errors.New("workflow final output state is unconfirmed; inspect OBS before retrying"))
	}
	finalScene := plan.LiveScene
	if finalScene == "" {
		finalScene = plan.StartingScene
	}
	if (plan.OBSProfile != "" && state.Profile != plan.OBSProfile) || (plan.SceneCollection != "" && state.Collection != plan.SceneCollection) || (finalScene != "" && state.Scene != finalScene) {
		return fail(errors.New("workflow settings changed or could not be confirmed; inspect OBS before retrying"))
	}
	result.OK = true
	result.Message = "Workflow applied. Streaming was not started; local output was enabled only when explicitly approved."
	return result, nil
}

func hasName(names []string, wanted string) bool {
	for _, name := range names {
		if name == wanted {
			return true
		}
	}
	return false
}

func (c *Client) WorkflowSnapshot(ctx context.Context) (WorkflowSnapshot, error) {
	var state WorkflowSnapshot
	stream, err := empty(ctx, "GetStreamStatus", c.obs.Stream.GetStreamStatus)
	if err != nil {
		return state, err
	}
	if err := workflowKnownOutput(stream.GetRaw(), "outputActive", "outputReconnecting"); err != nil {
		return state, err
	}
	state.StreamActive = stream.OutputActive || stream.OutputReconnecting
	record, err := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if err != nil {
		return state, err
	}
	if err := workflowKnownOutput(record.GetRaw(), "outputActive"); err != nil {
		return state, err
	}
	state.RecordingActive = record.OutputActive
	replay, err := empty(ctx, "GetReplayBufferStatus", c.obs.Outputs.GetReplayBufferStatus)
	if err != nil && !workflowOutputUnavailable(err, "GetReplayBufferStatus") {
		return state, err
	}
	if err == nil {
		if err := workflowKnownOutput(replay.GetRaw(), "outputActive"); err != nil {
			return state, err
		}
		state.ReplayBufferActive = replay.OutputActive
	}
	camera, err := empty(ctx, "GetVirtualCamStatus", c.obs.Outputs.GetVirtualCamStatus)
	if err != nil && !workflowOutputUnavailable(err, "GetVirtualCamStatus") {
		return state, err
	}
	if err == nil {
		if err := workflowKnownOutput(camera.GetRaw(), "outputActive"); err != nil {
			return state, err
		}
		state.VirtualCameraActive = camera.OutputActive
	}
	profiles, err := empty(ctx, "GetProfileList", c.obs.Config.GetProfileList)
	if err != nil {
		return state, err
	}
	state.Profile, state.Profiles = profiles.CurrentProfileName, profiles.Profiles
	collections, err := empty(ctx, "GetSceneCollectionList", c.obs.Config.GetSceneCollectionList)
	if err != nil {
		return state, err
	}
	state.Collection, state.Collections = collections.CurrentSceneCollectionName, collections.SceneCollections
	scenes, err := empty(ctx, "GetSceneList", c.obs.Scenes.GetSceneList)
	if err != nil {
		return state, err
	}
	state.Scene = scenes.CurrentProgramSceneName
	for _, scene := range scenes.Scenes {
		state.Scenes = append(state.Scenes, scene.SceneName)
	}
	return state, nil
}

func workflowKnownOutput(raw json.RawMessage, fields ...string) error {
	// goobs uses plain bool response fields, whose zero value also represents a
	// missing/null field. Inspect the raw successful response before authorizing
	// a mutation: malformed output data must remain unknown, not confirmed idle.
	var values map[string]json.RawMessage
	if json.Unmarshal(raw, &values) != nil || values == nil {
		return errors.New("workflow OBS output status is malformed; inspect OBS before retrying")
	}
	for _, name := range fields {
		var value *bool
		if json.Unmarshal(values[name], &value) != nil || value == nil {
			return errors.New("workflow OBS output status is incomplete; inspect OBS before retrying")
		}
	}
	return nil
}

func workflowOutputUnavailable(err error, operation string) bool {
	// OBS WebSocket returns InvalidResourceState only when these optional
	// outputs are unavailable; an absent output cannot currently be active.
	// Other operations/codes remain unknown and block workflow mutations.
	var failure *RequestError
	return errors.As(err, &failure) && failure.Operation == operation && failure.Code == 604
}

func (c *Client) SetWorkflowProfile(ctx context.Context, name string) error {
	_, err := request(ctx, "SetCurrentProfile", func() (*obsconfig.SetCurrentProfileResponse, error) {
		return c.obs.Config.SetCurrentProfile(obsconfig.NewSetCurrentProfileParams().WithProfileName(name))
	})
	return err
}

func (c *Client) SetWorkflowCollection(ctx context.Context, name string) error {
	_, err := request(ctx, "SetCurrentSceneCollection", func() (*obsconfig.SetCurrentSceneCollectionResponse, error) {
		return c.obs.Config.SetCurrentSceneCollection(obsconfig.NewSetCurrentSceneCollectionParams().WithSceneCollectionName(name))
	})
	return err
}

func (c *Client) StartWorkflowReplayBuffer(ctx context.Context) error {
	_, err := empty(ctx, "StartReplayBuffer", c.obs.Outputs.StartReplayBuffer)
	if err != nil {
		return err
	}
	for {
		status, err := empty(ctx, "GetReplayBufferStatus", c.obs.Outputs.GetReplayBufferStatus)
		if err != nil || status.OutputActive {
			return err
		}
		if err := pause(ctx, 50*time.Millisecond); err != nil {
			return err
		}
	}
}

// ConnectWorkflow retries only refused listeners under one bounded readiness
// deadline. Authentication/transport errors are not hidden in retry loops.
func ConnectWorkflow(ctx context.Context, cfg Config, readiness time.Duration) (*Client, error) {
	if readiness < 100*time.Millisecond || readiness > 30*time.Second {
		return nil, errors.New("workflow connection readiness must be from 100ms to 30s")
	}
	ctx, cancel := context.WithTimeout(ctx, readiness)
	defer cancel()
	cfg.Timeout = time.Second
	for {
		client, err := Connect(ctx, cfg)
		if err == nil {
			return client, nil
		}
		var connection *ConnectionError
		if !errors.As(err, &connection) || connection.Kind != "refused" {
			return nil, err
		}
		if err := pause(ctx, 100*time.Millisecond); err != nil {
			return nil, errors.New("workflow OBS readiness deadline reached; start OBS and enable its built-in WebSocket server")
		}
	}
}
