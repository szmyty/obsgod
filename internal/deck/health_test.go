package deck

import (
	"context"
	"encoding/json"
	"math"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

func healthN(value float64) *float64 { return &value }
func healthB(value bool) *bool       { return &value }

func healthPair(now time.Time) (automation.HealthObservation, automation.HealthObservation) {
	a := automation.HealthObservation{ObservedAt: now.Add(-time.Second),
		Stats:  automation.HealthStats{CPUPercent: healthN(5), FPS: healthN(30), FrameRenderMS: healthN(2), MemoryMB: healthN(500), FreeDiskMB: healthN(5000), EncodeSkipped: healthN(4), EncodeTotal: healthN(900), RenderSkipped: healthN(2), RenderTotal: healthN(900)},
		Stream: automation.HealthStream{Active: healthB(true), Reconnecting: healthB(false), Bytes: healthN(1000000), DurationMS: healthN(30000), DroppedFrames: healthN(2), TotalFrames: healthN(900)}}
	b := a
	b.ObservedAt = now
	b.Stream.Bytes, b.Stream.DurationMS, b.Stream.TotalFrames = healthN(1562500), healthN(31000), healthN(930)
	b.Stats.EncodeTotal, b.Stats.RenderTotal = healthN(930), healthN(930)
	return a, b
}

func containsHealthAdvice(report HealthReport, code string) bool {
	for _, advice := range report.Advice {
		if advice.Code == code {
			return true
		}
	}
	return false
}

func TestHealthRatesUseFreshAdvancingCountersAndRetainUnknownGPU(t *testing.T) {
	now := time.Now()
	a, b := healthPair(now)
	r := buildHealth(a, b, now, 30, "signal", "visible")
	if !r.OK || r.State != "observed" || !r.OutputKnown || !r.Streaming || r.SampleMS != 1000 || r.Metrics.BitrateKbps == nil || *r.Metrics.BitrateKbps != 4500 {
		t.Fatalf("wrong fresh health: %+v", r)
	}
	if r.Metrics.StreamDroppedPercent == nil || *r.Metrics.StreamDroppedPercent != 0 || r.Metrics.GPUPercent != nil || r.ProviderReception != "unknown" || !containsHealthAdvice(r, "viewer-unconfirmed") {
		t.Fatalf("zero/unknown observations conflated: %+v", r)
	}
	if !r.ExpiresAt.Equal(b.ObservedAt.Add(healthFreshness)) {
		t.Fatal("health freshness missing")
	}
	encoded, err := json.Marshal(r)
	if err != nil || strings.Contains(string(encoded), "secret") {
		t.Fatal("health output unsafe", err)
	}
}

func TestHealthDegradationProducesAdviceWithoutChangingSettings(t *testing.T) {
	now := time.Now()
	a, b := healthPair(now)
	b.Stream.DroppedFrames = healthN(5)
	b.Stats.EncodeSkipped, b.Stats.RenderSkipped = healthN(7), healthN(5)
	b.Stats.CPUPercent, b.Stats.FPS, b.Stats.FreeDiskMB = healthN(95), healthN(20), healthN(500)
	r := buildHealth(a, b, now, 30, "muted", "unavailable")
	if r.State != "degraded" || !r.Streaming || !r.OutputKnown {
		t.Fatalf("degradation overwrote active output: %+v", r)
	}
	for _, code := range []string{"stream-drops", "encoder-lag", "render-lag", "high-cpu", "low-fps", "low-disk", "audio-unavailable", "capture-unconfirmed", "viewer-unconfirmed"} {
		if !containsHealthAdvice(r, code) {
			t.Error("missing measured advice", code)
		}
	}
	if r.Metrics.StreamDroppedPercent == nil || *r.Metrics.StreamDroppedPercent != 10 {
		t.Fatal("drop percentage used lifetime rather than interval")
	}
}

func TestHealthStaleMissingAndCounterResetNeverBecomeFalseZero(t *testing.T) {
	now := time.Now()
	for _, mode := range []string{"stale", "future", "short", "zero-time", "long", "bytes-reset", "duration-reset", "duration-stalled", "invalid-duration", "not-active-before", "missing-active", "missing-counter", "invalid-counter", "no-frame-progress"} {
		t.Run(mode, func(t *testing.T) {
			a, b := healthPair(now)
			unknown := false
			switch mode {
			case "stale":
				a.ObservedAt, b.ObservedAt, unknown = now.Add(-11*time.Second), now.Add(-10*time.Second), true
			case "future":
				a.ObservedAt, b.ObservedAt, unknown = now.Add(3*time.Second), now.Add(4*time.Second), true
			case "short":
				a.ObservedAt, unknown = now.Add(-time.Millisecond), true
			case "zero-time":
				a.ObservedAt, unknown = time.Time{}, true
			case "long":
				a.ObservedAt, unknown = now.Add(-4*time.Second), true
			case "bytes-reset":
				b.Stream.Bytes = healthN(12)
			case "duration-reset":
				b.Stream.DurationMS = healthN(100)
			case "duration-stalled":
				b.Stream.DurationMS = a.Stream.DurationMS
			case "invalid-duration":
				b.Stream.DurationMS = healthN(math.Inf(1))
			case "not-active-before":
				a.Stream.Active = healthB(false)
			case "missing-active":
				b.Stream.Active, unknown = nil, true
			case "missing-counter":
				b.Stream.Bytes = nil
			case "invalid-counter":
				b.Stream.Bytes = healthN(math.Inf(1))
			case "no-frame-progress":
				b.Stream.TotalFrames = a.Stream.TotalFrames
			}
			r := buildHealth(a, b, now, 30, "signal", "visible")
			if unknown {
				if r.State != "unknown" || r.OutputKnown {
					t.Fatalf("invalid sample claimed known output: %+v", r)
				}
			} else if mode == "no-frame-progress" {
				if r.Metrics.StreamDroppedPercent != nil {
					t.Fatal("no-frame observation became zero dropped rate")
				}
			} else if r.Metrics.BitrateKbps != nil || !containsHealthAdvice(r, "rate-unconfirmed") {
				t.Fatalf("reset/missing counter became measured bitrate: %+v", r)
			}
		})
	}
}

func TestHealthFiniteExtremeCountersRemainSerializable(t *testing.T) {
	now := time.Now()
	a, b := healthPair(now)
	a.Stream.Bytes, b.Stream.Bytes = healthN(0), healthN(1e308)
	a.Stream.DroppedFrames, b.Stream.DroppedFrames = healthN(0), healthN(1e307)
	a.Stream.TotalFrames, b.Stream.TotalFrames = healthN(0), healthN(1e308)
	r := buildHealth(a, b, now, 30, "signal", "visible")
	if _, err := json.Marshal(r); err != nil {
		t.Fatal("finite counters overflowed diagnostics", err)
	}
	if r.Metrics.StreamDroppedPercent == nil || math.Abs(*r.Metrics.StreamDroppedPercent-10) > 0.000001 {
		t.Fatal("large counter ratio overflowed")
	}
}

func TestHealthStoppedReconnectingAndSilentRemainDistinct(t *testing.T) {
	now := time.Now()
	a, b := healthPair(now)
	b.Stream.Active = healthB(false)
	r := buildHealth(a, b, now, 30, "unknown", "unknown")
	if r.State != "idle" || !r.OutputKnown || r.Streaming || r.Metrics.BitrateKbps != nil {
		t.Fatalf("stopped output wrongly reported: %+v", r)
	}
	b.Stream.Active, b.Stream.Reconnecting = healthB(true), healthB(true)
	r = buildHealth(a, b, now, 30, "silent", "placeholder")
	if r.State != "degraded" || !containsHealthAdvice(r, "reconnecting") || !containsHealthAdvice(r, "audio-silent") {
		t.Fatalf("reconnection/silence not visible: %+v", r)
	}
	b.Stream.Reconnecting, b.Stream.Bytes = healthB(false), a.Stream.Bytes
	r = buildHealth(a, b, now, 30, "signal", "visible")
	if r.State != "degraded" || !containsHealthAdvice(r, "no-output-progress") || r.Metrics.BitrateKbps == nil || *r.Metrics.BitrateKbps != 0 {
		t.Fatalf("stall became healthy or unknown: %+v", r)
	}
}

func TestHealthUntrustedEnumsAndImpossibleRatiosAreExcluded(t *testing.T) {
	now := time.Now()
	a, b := healthPair(now)
	b.Stream.DroppedFrames = healthN(1000)
	b.Stats.CPUPercent = healthN(200)
	r := buildHealth(a, b, now, 30, "secret-device-name", "private-game-name")
	encoded, err := json.Marshal(r)
	if err != nil || strings.Contains(string(encoded), "secret-device-name") || strings.Contains(string(encoded), "private-game-name") || r.Audio != "unknown" || r.Capture != "unknown" || r.Metrics.CPUPercent != nil || r.Metrics.StreamDroppedPercent != nil {
		t.Fatalf("untrusted metadata escaped: %+v %v", r, err)
	}
}

func TestHealthNoCredentialsReturnsUnknownWithoutStartingAnything(t *testing.T) {
	p := testPaths(t)
	r := ObserveStreamHealth(context.Background(), p)
	if r.OK || r.OutputKnown || r.State != "unknown" || r.ProviderReception != "unknown" {
		t.Fatalf("missing setup became stopped/healthy: %+v", r)
	}
}
