package deck

import (
	"context"
	"runtime"
	"time"
)

// SupportBundle intentionally projects an allowlisted subset of Status. Never
// marshal Result here: it also contains the server, user text and local paths.
type SupportBundle struct {
	SchemaVersion int               `json:"schema_version"`
	ObservedAt    time.Time         `json:"observed_at"`
	Platform      string            `json:"platform"`
	Status        SupportStatus     `json:"status"`
	Diagnostics   []DiagnosticEntry `json:"diagnostics"`
	Health        *HealthReport     `json:"health,omitempty"`
	Resilience    *ResilienceStatus `json:"resilience,omitempty"`
}

type SupportStatus struct {
	Configured  bool   `json:"configured"`
	OutputKnown bool   `json:"output_known"`
	Connected   bool   `json:"connected"`
	Streaming   bool   `json:"streaming"`
	Recording   bool   `json:"recording"`
	Replay      bool   `json:"replay"`
	MediaKnown  bool   `json:"media_known"`
	State       string `json:"state"`
	Connection  string `json:"connection"`
	Process     string `json:"process"`
	Capture     string `json:"capture"`
	Game        string `json:"game"`
	Frames      string `json:"frames"`
}

func supportEnum(value string, allowed ...string) string {
	for _, item := range allowed {
		if value == item {
			return item
		}
	}
	return "unknown"
}

func supportStatus(r Result) SupportStatus {
	s := SupportStatus{
		Configured: r.Configured, OutputKnown: r.OutputKnown, Connected: r.Connected,
		Streaming: r.Stream.Active, Recording: r.Recording,
		State:      supportEnum(r.State, "stopped", "streaming", "starting", "stopping", "setup", "error", "recording"),
		Connection: supportEnum(r.Connection, "connected", "disconnected", "unavailable", "authenticated", "ready"),
		Process:    supportEnum(r.Process, "absent", "owned", "running"),
		Capture:    supportEnum(r.Capture, "available", "unavailable", "ready", "blank"),
		Game:       supportEnum(r.Game, "running", "active", "idle", "ambiguous", "unavailable"),
		Frames:     supportEnum(r.Frames, "visible", "ready", "usable", "blank", "placeholder", "unavailable"),
	}
	if r.Media != nil {
		s.Replay, s.MediaKnown = r.Media.ReplayActive, r.Media.Known
	}
	return s
}

// ExportSupportBundle reads local state without launching OBS, changing output,
// writing files, or contacting a destination. Unknown remains explicit.
func ExportSupportBundle(ctx context.Context, p Paths) SupportBundle {
	r := Status(ctx, p)
	health := ObserveStreamHealth(ctx, p)
	resilience := ReadResilienceStatus(p)
	return SupportBundle{SchemaVersion: 1, ObservedAt: time.Now().UTC(),
		Platform: runtime.GOOS + "/" + runtime.GOARCH, Status: supportStatus(r),
		Diagnostics: ReadDiagnostics(p), Health: &health, Resilience: &resilience}
}
