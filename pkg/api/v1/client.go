package v1

import (
	"context"
	"errors"
	"math"
	"net"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/szmyty/obsgod/pkg/automation"
)

type backend interface {
	automation.WorkflowBackend
	StreamStatus(context.Context) (automation.StreamStatus, error)
	StartStream(context.Context) (automation.StreamStatus, error)
	StopStream(context.Context) (automation.StreamStatus, error)
	APIRecordingStatus(context.Context) (automation.RecordingStatus, error)
	StopRecording(context.Context) (string, error)
	StartReplay(context.Context) error
	StopReplay(context.Context) error
	SaveReplay(context.Context) (string, error)
	SceneItems(context.Context, string) ([]automation.SceneItemState, error)
	SetItemEnabled(context.Context, string, int, bool) error
	SetVirtualCamera(context.Context, bool) error
	ConfigureRTMP(context.Context, string, string) error
	ConfirmRTMP(context.Context, string, string) error
}

// Client owns one authenticated connection. Public operations are serialized.
// Close is idempotent and interrupts a running request. Cancellation of an
// acquired operation closes the connection, preventing a still-running transport
// request from racing a later mutation. Reconnect and inspect before retrying.
type Client struct {
	backend   backend
	lease     chan struct{}
	timeout   time.Duration
	closed    atomic.Bool
	closeOnce sync.Once
	closeErr  error
}

func Connect(ctx context.Context, cfg Connection) (*Client, error) {
	if !validConnection(cfg) {
		return nil, fail("connect", InvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return nil, Failure("connect", err)
	}
	connectTimeout := cfg.ConnectTimeout
	if connectTimeout == 0 {
		connectTimeout = 3 * time.Second
	}
	operationTimeout := cfg.OperationTimeout
	if operationTimeout == 0 {
		operationTimeout = 15 * time.Second
	}
	b, err := automation.Connect(ctx, automation.Config{Address: cfg.Address, Password: cfg.Password, Timeout: connectTimeout})
	if err != nil {
		return nil, Failure("connect", err)
	}
	return newClient(b, operationTimeout), nil
}
func validConnection(c Connection) bool {
	host, port, err := net.SplitHostPort(c.Address)
	number, parseErr := strconv.Atoi(port)
	return err == nil && parseErr == nil && host != "" && !strings.ContainsAny(host, "@/\\\r\n\x00") && number > 0 && number <= 65535 && c.ConnectTimeout >= 0 && c.ConnectTimeout <= 30*time.Second && c.OperationTimeout >= 0 && c.OperationTimeout <= 2*time.Minute
}
func newClient(b backend, timeout time.Duration) *Client {
	c := &Client{backend: b, lease: make(chan struct{}, 1), timeout: timeout}
	c.lease <- struct{}{}
	return c
}
func (c *Client) Close() error {
	c.closeOnce.Do(func() {
		c.closed.Store(true)
		if err := c.backend.Close(); err != nil {
			c.closeErr = Failure("close", err)
		}
	})
	return c.closeErr
}
func run[T any](ctx context.Context, c *Client, operation string, action func(context.Context) (T, error)) (T, error) {
	var zero T
	if err := ctx.Err(); err != nil {
		return zero, Failure(operation, err)
	}
	if c == nil || c.closed.Load() {
		return zero, fail(operation, Unavailable)
	}
	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()
	select {
	case <-ctx.Done():
		return zero, Failure(operation, ctx.Err())
	case <-c.lease:
	}
	defer func() { c.lease <- struct{}{} }()
	if c.closed.Load() {
		return zero, fail(operation, Unavailable)
	}
	// A cancelled adapter request may still be unwinding its transport goroutine.
	// Closing is the safe lifecycle boundary; no later command reuses it.
	stop := context.AfterFunc(ctx, func() { _ = c.Close() })
	value, err := action(ctx)
	if !stop() || ctx.Err() != nil {
		_ = c.Close()
		return zero, Failure(operation, ctx.Err())
	}
	if err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			_ = c.Close()
		}
		return zero, Failure(operation, err)
	}
	return value, nil
}
func mutate(ctx context.Context, c *Client, operation string, approved bool, action func(context.Context) error) error {
	if !approved {
		return fail(operation, ApprovalRequired)
	}
	_, err := run(ctx, c, operation, func(ctx context.Context) (struct{}, error) { return struct{}{}, action(ctx) })
	return err
}

func streamState(s automation.StreamStatus) StreamState {
	return StreamState{s.Active, s.Reconnecting, s.Bytes, s.Duration, s.SkippedFrames, s.TotalFrames}
}
func recordingState(s automation.RecordingStatus) RecordingState {
	return RecordingState{s.Active, s.Paused, s.Bytes, s.Duration}
}
func validMetrics(values ...float64) bool {
	for _, value := range values {
		if value < 0 || math.IsNaN(value) || math.IsInf(value, 0) {
			return false
		}
	}
	return true
}
func checkedStream(s automation.StreamStatus, err error) (StreamState, error) {
	if err != nil {
		return StreamState{}, err
	}
	if !validMetrics(s.Bytes, s.Duration, s.SkippedFrames, s.TotalFrames) {
		return StreamState{}, fail("snapshot", OBSRequest)
	}
	return streamState(s), nil
}
func (c *Client) Snapshot(ctx context.Context) (Snapshot, error) {
	return run(ctx, c, "snapshot", func(ctx context.Context) (Snapshot, error) {
		w, err := c.backend.WorkflowSnapshot(ctx)
		if err != nil {
			return Snapshot{}, err
		}
		s, err := c.backend.StreamStatus(ctx)
		if err != nil {
			return Snapshot{}, err
		}
		r, err := c.backend.APIRecordingStatus(ctx)
		if err != nil {
			return Snapshot{}, err
		}
		stream, err := checkedStream(s, nil)
		if err != nil {
			return Snapshot{}, err
		}
		if !validMetrics(r.Bytes, r.Duration) {
			return Snapshot{}, fail("snapshot", OBSRequest)
		}
		return Snapshot{SchemaVersion: SchemaVersion, Stream: stream, Recording: recordingState(r), ReplayBufferActive: w.ReplayBufferActive, VirtualCameraActive: w.VirtualCameraActive, Profile: w.Profile, Collection: w.Collection, Scene: w.Scene, Profiles: nonNil(w.Profiles), Collections: nonNil(w.Collections), Scenes: nonNil(w.Scenes), ProviderReception: "unknown"}, nil
	})
}
func nonNil(v []string) []string {
	if v == nil {
		return []string{}
	}
	return append([]string{}, v...)
}
func (c *Client) StreamStatus(ctx context.Context) (StreamState, error) {
	return run(ctx, c, "snapshot", func(ctx context.Context) (StreamState, error) {
		s, e := c.backend.StreamStatus(ctx)
		return checkedStream(s, e)
	})
}
func (c *Client) StartStream(ctx context.Context, approval Approval) (StreamState, error) {
	if !approval.Streaming {
		return StreamState{}, fail("stream.start", ApprovalRequired)
	}
	return run(ctx, c, "stream.start", func(ctx context.Context) (StreamState, error) {
		s, e := c.backend.StartStream(ctx)
		return checkedStream(s, e)
	})
}
func (c *Client) StopStream(ctx context.Context, approval Approval) (StreamState, error) {
	if !approval.Streaming {
		return StreamState{}, fail("stream.stop", ApprovalRequired)
	}
	return run(ctx, c, "stream.stop", func(ctx context.Context) (StreamState, error) {
		s, e := c.backend.StopStream(ctx)
		return checkedStream(s, e)
	})
}
func (c *Client) StartRecording(ctx context.Context, a Approval) error {
	return mutate(ctx, c, "recording.start", a.Recording, func(ctx context.Context) error {
		s, e := c.backend.APIRecordingStatus(ctx)
		if e != nil || s.Active {
			return e
		}
		return c.backend.StartRecording(ctx)
	})
}
func (c *Client) StopRecording(ctx context.Context, a Approval) (string, error) {
	if !a.Recording {
		return "", fail("recording.stop", ApprovalRequired)
	}
	return run(ctx, c, "recording.stop", func(ctx context.Context) (string, error) {
		s, e := c.backend.APIRecordingStatus(ctx)
		if e != nil || !s.Active {
			return "", e
		}
		return c.backend.StopRecording(ctx)
	})
}
func (c *Client) StartReplayBuffer(ctx context.Context, a Approval) error {
	return mutate(ctx, c, "replay.start", a.ReplayBuffer, c.backend.StartReplay)
}
func (c *Client) StopReplayBuffer(ctx context.Context, a Approval) error {
	return mutate(ctx, c, "replay.stop", a.ReplayBuffer, c.backend.StopReplay)
}
func (c *Client) SaveReplay(ctx context.Context, a Approval) (string, error) {
	if !a.ReplayBuffer {
		return "", fail("replay.save", ApprovalRequired)
	}
	return run(ctx, c, "replay.save", c.backend.SaveReplay)
}
func (c *Client) SetVirtualCamera(ctx context.Context, active bool, a Approval) error {
	op := "virtual-camera.stop"
	if active {
		op = "virtual-camera.start"
	}
	return mutate(ctx, c, op, a.VirtualCamera, func(ctx context.Context) error { return c.backend.SetVirtualCamera(ctx, active) })
}
func validName(value string) bool {
	if value == "" || len(value) > 256 || !utf8.ValidString(value) {
		return false
	}
	for _, r := range value {
		if unicode.IsControl(r) {
			return false
		}
	}
	return true
}
func ValidName(value string) bool { return validName(value) }
func (c *Client) SelectScene(ctx context.Context, name string, a Approval) error {
	if !validName(name) {
		return fail("scene.select", InvalidInput)
	}
	return mutate(ctx, c, "scene.select", a.Settings, func(ctx context.Context) error {
		w, e := c.backend.WorkflowSnapshot(ctx)
		if e != nil {
			return e
		}
		found := false
		for _, scene := range w.Scenes {
			if scene == name {
				found = true
			}
		}
		if !found {
			return fail("scene.select", InvalidInput)
		}
		if e = c.backend.SetScene(ctx, name); e != nil {
			return e
		}
		after, e := c.backend.WorkflowSnapshot(ctx)
		if e == nil && after.Scene != name {
			return fail("scene.select", Conflict)
		}
		return e
	})
}
func (c *Client) SceneItems(ctx context.Context, scene string) ([]SceneItem, error) {
	if !validName(scene) {
		return nil, fail("scene-items.list", InvalidInput)
	}
	return run(ctx, c, "scene-items.list", func(ctx context.Context) ([]SceneItem, error) {
		items, e := c.backend.SceneItems(ctx, scene)
		if e != nil {
			return nil, e
		}
		r := make([]SceneItem, 0, len(items))
		for _, i := range items {
			r = append(r, SceneItem{i.ID, i.Name, i.Enabled})
		}
		return r, nil
	})
}
func (c *Client) SetSceneItemEnabled(ctx context.Context, scene string, id int, enabled bool, a Approval) error {
	if !validName(scene) || id < 0 {
		return fail("scene-item.enable", InvalidInput)
	}
	return mutate(ctx, c, "scene-item.enable", a.Settings, func(ctx context.Context) error {
		if e := c.backend.SetItemEnabled(ctx, scene, id, enabled); e != nil {
			return e
		}
		items, e := c.backend.SceneItems(ctx, scene)
		if e != nil {
			return e
		}
		for _, item := range items {
			if item.ID == id && item.Enabled == enabled {
				return nil
			}
		}
		return fail("scene-item.enable", Conflict)
	})
}
func (p WorkflowPlan) adapter() automation.WorkflowPlan {
	return automation.WorkflowPlan{OBSProfile: p.OBSProfile, SceneCollection: p.SceneCollection, StartingScene: p.StartingScene, LiveScene: p.LiveScene, RecordingEnabled: p.RecordingEnabled, ReplayBufferEnabled: p.ReplayBufferEnabled, ReadinessTimeout: p.ReadinessTimeout, PostStartDelay: p.PostStartDelay}
}
func (p WorkflowPlan) Validate() error {
	for _, name := range []string{p.OBSProfile, p.SceneCollection, p.StartingScene, p.LiveScene} {
		if name != "" && !validName(name) {
			return fail("workflow.validate", InvalidInput)
		}
	}
	if err := p.adapter().Validate(); err != nil {
		return fail("workflow.validate", InvalidInput)
	}
	return nil
}
func (c *Client) ApplyWorkflow(ctx context.Context, p WorkflowPlan, a Approval) (WorkflowResult, error) {
	if e := p.Validate(); e != nil {
		return WorkflowResult{}, e
	}
	if !a.Settings || (p.RecordingEnabled && !a.Recording) || (p.ReplayBufferEnabled && !a.ReplayBuffer) {
		return WorkflowResult{}, fail("workflow.apply", ApprovalRequired)
	}
	// Keep the partial-stage result on failure; raw adapter messages are excluded.
	var result WorkflowResult
	_, err := run(ctx, c, "workflow.apply", func(ctx context.Context) (struct{}, error) {
		r, e := automation.ApplyWorkflow(ctx, c.backend, p.adapter(), automation.WorkflowApprovals{Settings: a.Settings, Recording: a.Recording, ReplayBuffer: a.ReplayBuffer})
		message := "workflow applied; no stream was started"
		if e != nil {
			message = "workflow incomplete; inspect OBS before retrying"
		}
		result = WorkflowResult{SchemaVersion, r.OK, nonNil(r.Applied), r.Attempted, message}
		return struct{}{}, e
	})
	return result, err
}
func (c *Client) SelectProfile(ctx context.Context, name string, a Approval) error {
	if !validName(name) {
		return fail("profile.select", InvalidInput)
	}
	_, e := c.ApplyWorkflow(ctx, WorkflowPlan{OBSProfile: name}, a)
	if e != nil {
		return Failure("profile.select", e)
	}
	return nil
}
func (c *Client) SelectCollection(ctx context.Context, name string, a Approval) error {
	if !validName(name) {
		return fail("collection.select", InvalidInput)
	}
	_, e := c.ApplyWorkflow(ctx, WorkflowPlan{SceneCollection: name}, a)
	if e != nil {
		return Failure("collection.select", e)
	}
	return nil
}
func (s RTMPService) Validate() error {
	u, e := url.Parse(s.Server)
	if e != nil || len(s.Server) > 4096 || u.Hostname() == "" || (u.Scheme != "rtmp" && u.Scheme != "rtmps") || u.User != nil || u.RawQuery != "" || u.Fragment != "" || strings.ContainsAny(s.Server, "\r\n\x00") || s.Key == "" || len(s.Key) > 4096 || strings.TrimSpace(s.Key) != s.Key || strings.ContainsAny(s.Key, "\r\n\x00") {
		return fail("service.configure-rtmp", InvalidInput)
	}
	for _, value := range []string{s.Server, u.Path, s.Key} {
		for _, r := range value {
			if unicode.IsControl(r) {
				return fail("service.configure-rtmp", InvalidInput)
			}
		}
	}
	return nil
}
func (c *Client) ConfigureService(ctx context.Context, s RTMPService, a Approval) error {
	if e := s.Validate(); e != nil {
		return e
	}
	return mutate(ctx, c, "service.configure-rtmp", a.Settings, func(ctx context.Context) error {
		w, e := c.backend.WorkflowSnapshot(ctx)
		if e != nil {
			return e
		}
		if w.StreamActive || w.RecordingActive || w.ReplayBufferActive || w.VirtualCameraActive {
			return fail("service.configure-rtmp", Conflict)
		}
		if e = c.backend.ConfigureRTMP(ctx, s.Server, s.Key); e != nil {
			return e
		}
		return c.backend.ConfirmRTMP(ctx, s.Server, s.Key)
	})
}

// VerifyService compares a private desired service without changing settings or
// returning the configured key. It can reconcile an already-running workflow.
func (c *Client) VerifyService(ctx context.Context, s RTMPService) error {
	if e := s.Validate(); e != nil {
		return e
	}
	_, e := run(ctx, c, "service.verify-rtmp", func(ctx context.Context) (struct{}, error) {
		return struct{}{}, c.backend.ConfirmRTMP(ctx, s.Server, s.Key)
	})
	return e
}
