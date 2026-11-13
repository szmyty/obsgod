package deck

import (
	"context"
	"math"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

const healthFreshness = 8 * time.Second

type HealthMetrics struct {
	BitrateKbps          *float64 `json:"bitrate_kbps,omitempty"`
	StreamDroppedPercent *float64 `json:"stream_dropped_percent,omitempty"`
	EncodeSkippedPercent *float64 `json:"encode_skipped_percent,omitempty"`
	RenderMissedPercent  *float64 `json:"render_missed_percent,omitempty"`
	CPUPercent           *float64 `json:"cpu_percent,omitempty"`
	FPS                  *float64 `json:"fps,omitempty"`
	FrameRenderMS        *float64 `json:"frame_render_ms,omitempty"`
	MemoryMB             *float64 `json:"memory_mb,omitempty"`
	FreeDiskMB           *float64 `json:"free_disk_mb,omitempty"`
	GPUPercent           *float64 `json:"gpu_percent,omitempty"`
}

type HealthAdvice struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// HealthReport is a redaction-safe numeric projection. Values missing from
// Metrics are unknown, including GPU utilization (not provided by OBS). It
// contains no endpoint, device name, stream key, game title, text or media path.
type HealthReport struct {
	SchemaVersion     int            `json:"schema_version"`
	OK                bool           `json:"ok"`
	State             string         `json:"state"`
	Message           string         `json:"message"`
	ObservedAt        time.Time      `json:"observed_at"`
	ExpiresAt         time.Time      `json:"expires_at"`
	SampleMS          int64          `json:"sample_ms"`
	OutputKnown       bool           `json:"output_known"`
	Streaming         bool           `json:"streaming"`
	Reconnecting      *bool          `json:"reconnecting"`
	Metrics           HealthMetrics  `json:"metrics"`
	Audio             string         `json:"audio"`
	Capture           string         `json:"capture"`
	ProviderReception string         `json:"provider_reception"`
	Advice            []HealthAdvice `json:"advice"`
	Limitations       []string       `json:"limitations"`
}

func unknownHealth(now time.Time) HealthReport {
	return HealthReport{SchemaVersion: 1, State: "unknown", Message: "Current OBS health could not be confirmed; inspect the connection and use Stop if needed",
		ObservedAt: now.UTC(), ExpiresAt: now.UTC().Add(healthFreshness), Audio: "unknown", Capture: "unknown", ProviderReception: "unknown",
		Advice:      []HealthAdvice{{Code: "output-unconfirmed", Message: "Check the managed OBS connection; a failed health check does not mean a stream stopped"}},
		Limitations: []string{"Measurements describe OBS on this device, not provider or viewer reception", "GPU utilization and total reconnect count are not supplied by this OBS interface", "Short samples can miss brief audio, network or encoder problems; no quality settings are changed automatically"}}
}

func finiteHealthValue(value *float64) *float64 {
	if value == nil || *value < 0 || math.IsNaN(*value) || math.IsInf(*value, 0) {
		return nil
	}
	v := *value
	return &v
}

func healthDelta(before, after *float64) *float64 {
	a, b := finiteHealthValue(before), finiteHealthValue(after)
	if a == nil || b == nil || *b < *a {
		return nil
	}
	delta := *b - *a
	return &delta
}

func frameRatio(beforeDropped, afterDropped, beforeTotal, afterTotal *float64) *float64 {
	dropped, total := healthDelta(beforeDropped, afterDropped), healthDelta(beforeTotal, afterTotal)
	if dropped == nil || total == nil || *total < 1 || *dropped > *total {
		return nil
	}
	// Divide first so finite but unusually large counters cannot overflow and
	// break the JSON diagnostic response.
	percent := (*dropped / *total) * 100
	return &percent
}

func healthAudio(status *AudioStatus) string {
	if status == nil {
		return "unknown"
	}
	if status.State == "muted" || (status.OutputAvailable && status.OutputMuted) {
		return "muted"
	}
	if status.State == "unavailable" {
		return "unavailable"
	}
	return supportEnum(status.Signal, "signal", "silent")
}

// buildHealth compares samples from the same short read-only observation. A
// counter reset, stopped/restarted output, stale sample or unknown field cannot
// turn into a rate, a false zero or a healthy verdict.
func buildHealth(before, after automation.HealthObservation, now time.Time, fps int, audio, capture string) HealthReport {
	r := unknownHealth(now)
	age := now.Sub(after.ObservedAt)
	window := after.ObservedAt.Sub(before.ObservedAt)
	if before.ObservedAt.IsZero() || after.ObservedAt.IsZero() || age < -time.Second || age > healthFreshness || window < 100*time.Millisecond || window > 3*time.Second {
		return r
	}
	r.ObservedAt, r.ExpiresAt, r.SampleMS = after.ObservedAt.UTC(), after.ObservedAt.UTC().Add(healthFreshness), window.Milliseconds()
	r.Audio = supportEnum(audio, "signal", "silent", "muted", "unavailable")
	r.Capture = supportEnum(capture, "visible", "placeholder", "unavailable")
	r.Metrics = HealthMetrics{CPUPercent: finiteHealthValue(after.Stats.CPUPercent), FPS: finiteHealthValue(after.Stats.FPS),
		FrameRenderMS: finiteHealthValue(after.Stats.FrameRenderMS), MemoryMB: finiteHealthValue(after.Stats.MemoryMB), FreeDiskMB: finiteHealthValue(after.Stats.FreeDiskMB)}
	if r.Metrics.CPUPercent != nil && *r.Metrics.CPUPercent > 100 {
		r.Metrics.CPUPercent = nil
	}
	if after.Stream.Active == nil {
		return r
	}
	r.OK, r.OutputKnown, r.Streaming = true, true, *after.Stream.Active
	r.Reconnecting = after.Stream.Reconnecting
	r.Advice = []HealthAdvice{}
	add := func(code, message string) { r.Advice = append(r.Advice, HealthAdvice{Code: code, Message: message}) }
	if !r.Streaming {
		r.State, r.Message = "idle", "OBS confirms streaming is stopped; recording and preview can still use device resources"
		add("not-streaming", "Start streaming explicitly when you are ready; health checks never start a broadcast")
	} else {
		r.State, r.Message = "observed", "Recent OBS measurements are available; provider and viewer reception remain unconfirmed"
		beforeDuration, afterDuration := finiteHealthValue(before.Stream.DurationMS), finiteHealthValue(after.Stream.DurationMS)
		stable := before.Stream.Active != nil && *before.Stream.Active && beforeDuration != nil && afterDuration != nil && *afterDuration > *beforeDuration
		if stable {
			if delta := healthDelta(before.Stream.Bytes, after.Stream.Bytes); delta != nil {
				// Kbps here uses decimal kilobits and local elapsed observation
				// time, not a configured bitrate or lifetime average.
				rate := *delta / (window.Seconds() * 125)
				r.Metrics.BitrateKbps = &rate
			}
			r.Metrics.StreamDroppedPercent = frameRatio(before.Stream.DroppedFrames, after.Stream.DroppedFrames, before.Stream.TotalFrames, after.Stream.TotalFrames)
			r.Metrics.EncodeSkippedPercent = frameRatio(before.Stats.EncodeSkipped, after.Stats.EncodeSkipped, before.Stats.EncodeTotal, after.Stats.EncodeTotal)
			r.Metrics.RenderMissedPercent = frameRatio(before.Stats.RenderSkipped, after.Stats.RenderSkipped, before.Stats.RenderTotal, after.Stats.RenderTotal)
		}
		if r.Reconnecting != nil && *r.Reconnecting {
			r.State = "degraded"
			add("reconnecting", "OBS is reconnecting; check the connection and destination dashboard. A viewer may not currently receive output")
		} else if r.Metrics.BitrateKbps == nil {
			r.State = "starting"
			add("rate-unconfirmed", "Output counters changed or were incomplete; wait for another sample before judging bitrate")
		} else if *r.Metrics.BitrateKbps == 0 {
			r.State = "degraded"
			add("no-output-progress", "OBS output bytes did not advance during this sample; refresh and inspect connectivity if the stall continues")
		}
		for _, entry := range []struct {
			value *float64
			code  string
			text  string
		}{
			{r.Metrics.StreamDroppedPercent, "stream-drops", "OBS dropped stream frames during this sample. Check upload stability and consider a lower bitrate after stopping output"},
			{r.Metrics.EncodeSkippedPercent, "encoder-lag", "OBS skipped encoding frames during this sample. Consider a lower resolution/FPS or another supported encoder after stopping output"},
			{r.Metrics.RenderMissedPercent, "render-lag", "OBS missed rendering frames during this sample. Reduce game/scene GPU load or output FPS after stopping output"},
		} {
			if entry.value != nil && *entry.value >= 1 {
				r.State = "degraded"
				add(entry.code, entry.text)
			}
		}
		if r.Metrics.FPS != nil && fps > 0 && *r.Metrics.FPS < float64(fps)*0.9 {
			r.State = "degraded"
			add("low-fps", "OBS is rendering below the selected frame rate; inspect capture and game/encoder load before changing quality")
		}
		if r.Metrics.CPUPercent != nil && *r.Metrics.CPUPercent >= 85 {
			r.State = "degraded"
			add("high-cpu", "OBS CPU usage is high in this sample; lower game/encoding load if picture or sound is affected")
		}
		if r.Capture == "unknown" || r.Capture == "unavailable" {
			r.State = "degraded"
			add("capture-unconfirmed", "Captured picture is unconfirmed; inspect the local preview or clip. Game-only capture never falls back to the full display")
		}
		if r.Audio == "silent" {
			add("audio-silent", "No output audio was measured in the short meter sample; play sound and verify a local clip before assuming an audio fault")
		} else if r.Audio == "muted" || r.Audio == "unavailable" {
			r.State = "degraded"
			add("audio-unavailable", "The selected output is muted or unavailable. Check SteamOS audio and routing; no system volume was changed")
		} else if r.Audio == "unknown" {
			add("audio-unmeasured", "Current audio signal is unmeasured; use a local test clip to confirm sound")
		}
	}
	if r.Metrics.FreeDiskMB != nil && *r.Metrics.FreeDiskMB < 1024 {
		add("low-disk", "OBS reports less than 1 GiB available at its recording location; free space or choose another location before recording")
	}
	add("viewer-unconfirmed", "OBS statistics do not prove your provider or viewers receive picture and sound; check a viewer independently")
	return r
}

// ObserveStreamHealth never launches OBS, starts/stops output, changes quality
// or contacts a provider. Its two-sample window is bounded even if OBS fails.
func ObserveStreamHealth(ctx context.Context, p Paths) HealthReport {
	now := time.Now()
	unknown := unknownHealth(now)
	s, secret, err := Load(p)
	if err != nil {
		// Keep health and Stop useful even if a settings file needs repair.
		secret, err = loadCredentials(p)
		if err != nil {
			return unknown
		}
		s = DefaultSettings()
		s.FPS = 0 // An unreadable preference is not evidence of a selected frame rate.
	}
	ctx, cancel := context.WithTimeout(ctx, 2500*time.Millisecond)
	defer cancel()
	c, err := connect(ctx, secret, 400*time.Millisecond)
	if err != nil {
		return unknown
	}
	defer c.Close()
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return unknown
	}
	before, err := c.HealthObservation(ctx)
	if err != nil || wait(ctx, 350*time.Millisecond) != nil {
		return unknown
	}
	after, err := c.HealthObservation(ctx)
	if err != nil {
		return unknown
	}
	capture := "unknown"
	if s.CaptureModeName() == "game" && runtime.Scene == IdleScene {
		capture = "placeholder"
	} else {
		data, err := c.Screenshot(ctx, runtime.Scene)
		if err == nil && NonblankCapture(data) {
			capture = "visible"
		}
	}
	// Recovery refreshes route metadata without asserting a signal. Observe the
	// meter independently here so a prior status poll is not needed to obtain
	// current audio health. This separate bounded subscription is read-only and
	// does not write the cached receipt or change the selected route/mixer.
	audio := readAudioStatus(p)
	if after.Stream.Active != nil && *after.Stream.Active {
		audioCtx, audioCancel := context.WithTimeout(ctx, 450*time.Millisecond)
		audio = measureAudio(audioCtx, p, secret, 180*time.Millisecond, false)
		audioCancel()
	}
	return buildHealth(before, after, time.Now(), s.FPS, healthAudio(audio), capture)
}
