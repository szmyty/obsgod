package automation

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"time"
)

// HealthStats contains only documented numeric OBS observations. Optional
// pointers distinguish a missing value from a measured zero. In particular,
// obs-websocket does not expose GPU utilization or provider/viewer reception.
type HealthStats struct {
	CPUPercent    *float64 `json:"cpu_percent,omitempty"`
	FPS           *float64 `json:"fps,omitempty"`
	FrameRenderMS *float64 `json:"frame_render_ms,omitempty"`
	MemoryMB      *float64 `json:"memory_mb,omitempty"`
	FreeDiskMB    *float64 `json:"free_disk_mb,omitempty"`
	EncodeSkipped *float64 `json:"encode_skipped,omitempty"`
	EncodeTotal   *float64 `json:"encode_total,omitempty"`
	RenderSkipped *float64 `json:"render_skipped,omitempty"`
	RenderTotal   *float64 `json:"render_total,omitempty"`
}

type HealthStream struct {
	Active        *bool    `json:"active,omitempty"`
	Reconnecting  *bool    `json:"reconnecting,omitempty"`
	Bytes         *float64 `json:"bytes,omitempty"`
	DurationMS    *float64 `json:"duration_ms,omitempty"`
	DroppedFrames *float64 `json:"dropped_frames,omitempty"`
	TotalFrames   *float64 `json:"total_frames,omitempty"`
}

// HealthObservation is a read-only snapshot, never a claim about audience
// reception. ObservedAt is generated locally after both bounded OBS requests.
type HealthObservation struct {
	ObservedAt time.Time    `json:"observed_at"`
	Stats      HealthStats  `json:"stats"`
	Stream     HealthStream `json:"stream"`
}

func healthNumber(value *float64) *float64 {
	if value == nil || math.IsNaN(*value) || math.IsInf(*value, 0) || *value < 0 {
		return nil
	}
	return value
}

// Decode the allowlisted fields from the raw response rather than relying on
// goobs's zero-valued numeric members: absent data must remain unknown. Neither
// raw response bodies nor server text are returned to callers or logs.
func decodeHealthStats(data []byte) (HealthStats, error) {
	var raw struct {
		CPUPercent    *float64 `json:"cpuUsage"`
		FPS           *float64 `json:"activeFps"`
		FrameRenderMS *float64 `json:"averageFrameRenderTime"`
		MemoryMB      *float64 `json:"memoryUsage"`
		FreeDiskMB    *float64 `json:"availableDiskSpace"`
		EncodeSkipped *float64 `json:"outputSkippedFrames"`
		EncodeTotal   *float64 `json:"outputTotalFrames"`
		RenderSkipped *float64 `json:"renderSkippedFrames"`
		RenderTotal   *float64 `json:"renderTotalFrames"`
	}
	if len(data) > 65536 || json.Unmarshal(data, &raw) != nil {
		return HealthStats{}, errors.New("OBS health statistics could not be decoded")
	}
	return HealthStats{
		CPUPercent: healthNumber(raw.CPUPercent), FPS: healthNumber(raw.FPS),
		FrameRenderMS: healthNumber(raw.FrameRenderMS), MemoryMB: healthNumber(raw.MemoryMB),
		FreeDiskMB: healthNumber(raw.FreeDiskMB), EncodeSkipped: healthNumber(raw.EncodeSkipped),
		EncodeTotal: healthNumber(raw.EncodeTotal), RenderSkipped: healthNumber(raw.RenderSkipped),
		RenderTotal: healthNumber(raw.RenderTotal),
	}, nil
}

func decodeHealthStream(data []byte) (HealthStream, error) {
	var raw struct {
		Active        *bool    `json:"outputActive"`
		Reconnecting  *bool    `json:"outputReconnecting"`
		Bytes         *float64 `json:"outputBytes"`
		DurationMS    *float64 `json:"outputDuration"`
		DroppedFrames *float64 `json:"outputSkippedFrames"`
		TotalFrames   *float64 `json:"outputTotalFrames"`
	}
	if len(data) > 65536 || json.Unmarshal(data, &raw) != nil {
		return HealthStream{}, errors.New("OBS stream counters could not be decoded")
	}
	return HealthStream{
		Active: raw.Active, Reconnecting: raw.Reconnecting, Bytes: healthNumber(raw.Bytes),
		DurationMS: healthNumber(raw.DurationMS), DroppedFrames: healthNumber(raw.DroppedFrames),
		TotalFrames: healthNumber(raw.TotalFrames),
	}, nil
}

// HealthObservation reads numeric GetStats and stream counters without
// changing settings or output. Calls must remain sequential on this Client.
func (c *Client) HealthObservation(ctx context.Context) (HealthObservation, error) {
	var observation HealthObservation
	stats, err := empty(ctx, "GetStats", c.obs.General.GetStats)
	if err != nil {
		return observation, err
	}
	observation.Stats, err = decodeHealthStats(stats.GetRaw())
	if err != nil {
		return observation, err
	}
	stream, err := empty(ctx, "GetStreamStatus", c.obs.Stream.GetStreamStatus)
	if err != nil {
		return HealthObservation{}, err
	}
	observation.Stream, err = decodeHealthStream(stream.GetRaw())
	if err != nil {
		return HealthObservation{}, err
	}
	observation.ObservedAt = time.Now().UTC()
	return observation, nil
}
