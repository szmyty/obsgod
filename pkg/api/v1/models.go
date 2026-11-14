// Package v1 is the versioned, provider-independent OBS control contract.
// It wraps the shared OBS adapter; it never launches OBS or contacts a provider.
// See docs/api-v1.md for compatibility, approval and observation semantics.
package v1

import (
	"fmt"
	"time"
)

const SchemaVersion = 1

// Connection holds private connection material. Do not persist Password in a
// profile. String and JSON formatting deliberately exclude credentials.
type Connection struct {
	Address          string        `json:"address"`
	Password         string        `json:"-"`
	ConnectTimeout   time.Duration `json:"-"`
	OperationTimeout time.Duration `json:"-"`
}

func (Connection) String() string     { return "OBS connection (credentials redacted)" }
func (c Connection) GoString() string { return c.String() }

// Approval is invocation-scoped; it must never be loaded from persisted config.
type Approval struct {
	Settings      bool `json:"-"`
	Streaming     bool `json:"-"`
	Recording     bool `json:"-"`
	ReplayBuffer  bool `json:"-"`
	VirtualCamera bool `json:"-"`
}

type StreamState struct {
	Active        bool    `json:"active"`
	Reconnecting  bool    `json:"reconnecting"`
	Bytes         float64 `json:"bytes"`
	DurationMS    float64 `json:"duration_ms"`
	SkippedFrames float64 `json:"skipped_frames"`
	TotalFrames   float64 `json:"total_frames"`
}
type RecordingState struct {
	Active     bool    `json:"active"`
	Paused     bool    `json:"paused"`
	Bytes      float64 `json:"bytes"`
	DurationMS float64 `json:"duration_ms"`
}

// ProfileInventory preserves OBS profile names and order without requiring
// unrelated output/configuration observations. It does not select a profile.
type ProfileInventory struct {
	Current  string   `json:"current"`
	Profiles []string `json:"profiles"`
}

// Snapshot is a sequential set of OBS observations, not an atomic transaction.
// An error returns no snapshot: unknown output state never becomes idle.
type Snapshot struct {
	SchemaVersion       int            `json:"schema_version"`
	Stream              StreamState    `json:"stream"`
	Recording           RecordingState `json:"recording"`
	ReplayBufferActive  bool           `json:"replay_buffer_active"`
	VirtualCameraActive bool           `json:"virtual_camera_active"`
	Profile             string         `json:"profile"`
	Collection          string         `json:"scene_collection"`
	Scene               string         `json:"scene"`
	Profiles            []string       `json:"profiles"`
	Collections         []string       `json:"scene_collections"`
	Scenes              []string       `json:"scenes"`
	ProviderReception   string         `json:"provider_reception"`
}
type SceneItem struct {
	ID      int    `json:"id"`
	Name    string `json:"name"`
	Enabled bool   `json:"enabled"`
}

// RTMPService never serializes or formats the endpoint or key. ConfigureService
// validates and confirms settings internally without exposing OBS credentials.
type RTMPService struct {
	Server string `json:"-"`
	Key    string `json:"-"`
}

func (RTMPService) String() string     { return "custom RTMP service (credentials redacted)" }
func (s RTMPService) GoString() string { return s.String() }

type WorkflowPlan struct {
	OBSProfile          string `json:"obs_profile,omitempty"`
	SceneCollection     string `json:"scene_collection,omitempty"`
	StartingScene       string `json:"starting_scene,omitempty"`
	LiveScene           string `json:"live_scene,omitempty"`
	RecordingEnabled    bool   `json:"recording_enabled"`
	ReplayBufferEnabled bool   `json:"replay_buffer_enabled"`
	ReadinessTimeout    string `json:"readiness_timeout,omitempty"`
	PostStartDelay      string `json:"post_start_delay,omitempty"`
}
type WorkflowResult struct {
	SchemaVersion int      `json:"schema_version"`
	OK            bool     `json:"ok"`
	Applied       []string `json:"applied"`
	Attempted     string   `json:"attempted,omitempty"`
	Message       string   `json:"message"`
}
type Capabilities struct {
	SchemaVersion     int      `json:"schema_version"`
	API               string   `json:"api"`
	Operations        []string `json:"operations"`
	ProviderReception string   `json:"provider_reception"`
}

func Discover() Capabilities {
	return Capabilities{SchemaVersion, "obsgod/v1", []string{"snapshot", "stream.start", "stream.stop", "recording.start", "recording.stop", "replay.start", "replay.stop", "replay.save", "virtual-camera.start", "virtual-camera.stop", "profile.list", "profile.select", "collection.select", "scene.select", "scene-items.list", "scene-item.enable", "service.configure-rtmp", "service.verify-rtmp", "workflow.apply"}, "unknown"}
}

// Response is the JSON process boundary used by the api command family.
// On error Result is omitted; partial orchestration uses its own typed result.
type Response struct {
	SchemaVersion int    `json:"schema_version"`
	OK            bool   `json:"ok"`
	Operation     string `json:"operation"`
	Result        any    `json:"result,omitempty"`
	Error         *Error `json:"error,omitempty"`
}

func NewResponse(operation string, result any, err error) Response {
	r := Response{SchemaVersion: SchemaVersion, OK: err == nil, Operation: operation, Result: result}
	if err != nil {
		r.Result = nil
		r.Error = Failure(operation, err)
	}
	return r
}

// Format prevents an accidental fmt representation from exposing secret fields.
func (c Connection) Format(s fmt.State, verb rune)  { _, _ = fmt.Fprint(s, c.String()) }
func (s RTMPService) Format(f fmt.State, verb rune) { _, _ = fmt.Fprint(f, s.String()) }
