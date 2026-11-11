package deck

import (
	"bytes"
	"context"
	"encoding/base64"
	"errors"
	"image"
	_ "image/png"
	"net"
	"os"
	"strings"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

const LiveScene = "OBSGod Live"
const IdleScene = "OBSGod Idle"
const CaptureInput = "OBSGod Gamescope"
const GameAudio = "OBSGod Game Audio"
const MicAudio = "OBSGod Microphone"

var errUnmanaged = errors.New("the OBS instance is not using the managed OBSGod profile; refusing to change it")

// Do not request a fixed framerate from Gamescope: some versions crash their
// PipeWire node during negotiation. OBS controls output framerate separately.
const CapturePipeline = "pipewiresrc do-timestamp=true target-object=gamescope ! queue leaky=downstream max-size-buffers=2 ! videoconvert ! video."

type Result struct {
	OK            bool                      `json:"ok"`
	State         string                    `json:"state"`
	Message       string                    `json:"message"`
	Configured    bool                      `json:"configured"`
	Connected     bool                      `json:"connected"`
	Stream        automation.StreamStatus   `json:"stream"`
	Runtime       *automation.RuntimeStatus `json:"runtime,omitempty"`
	Settings      *Settings                 `json:"settings,omitempty"`
	RecordingPath string                    `json:"recording_path,omitempty"`
}

func connect(ctx context.Context, secret Secrets, timeout time.Duration) (*automation.Client, error) {
	return automation.Connect(ctx, automation.Config{Address: net.JoinHostPort("127.0.0.1", Port), Password: secret.OBSPassword, Timeout: timeout})
}

func Status(ctx context.Context, p Paths) Result {
	s, secret, e := Load(p)
	r := Result{OK: true, Configured: true, Settings: &s, State: "stopped", Message: "Not streaming"}
	if e != nil {
		r = Result{OK: true, State: "setup", Message: e.Error()}
		// Corrupted/missing non-secret preferences must not hide an active stream
		// or prevent the owner from stopping it.
		secret, e = loadCredentials(p)
		if e != nil {
			return r
		}
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	c, e := connect(ctx, secret, 600*time.Millisecond)
	if e != nil {
		conn, err := net.DialTimeout("tcp", "127.0.0.1:"+Port, 200*time.Millisecond)
		if err == nil || len(managedProcesses(p)) > 0 {
			if conn != nil {
				_ = conn.Close()
			}
			r.OK = false
			r.State = "unknown"
			r.Message = "OBS is present but its output state cannot be confirmed"
		}
		return r
	}
	defer c.Close()
	r.Connected = true
	r.Stream, e = c.StreamStatus(ctx)
	if e != nil {
		r.OK = false
		r.State = "unknown"
		r.Message = "OBS status unavailable; check the connection"
		return r
	}
	if r.Stream.Active {
		r.State = "starting"
		r.Message = "Connecting or reconnecting to the stream server"
		if !r.Stream.Reconnecting && r.Stream.Bytes > 0 {
			r.State = "streaming"
			r.Message = "OBS streaming"
		}
	}
	return r
}

func Doctor(ctx context.Context, p Paths) Result {
	r := Status(ctx, p)
	if e := checkDependencies(ctx); e != nil {
		r.OK = false
		r.Message = e.Error()
		return r
	}
	if !gamescopeReady(ctx) {
		r.Message = "Gamescope capture is unavailable here. Switch to Gaming Mode and launch a game before starting."
	}
	if r.Connected {
		_, secret, e := Load(p)
		if e != nil {
			return r
		}
		c, e := connect(ctx, secret, time.Second)
		if e == nil {
			defer c.Close()
			v, e := c.RuntimeStatus(ctx)
			if e == nil {
				r.Runtime = &v
			}
		}
	}
	return r
}

func ready(ctx context.Context, p Paths, s Settings, secret Secrets) (*automation.Client, error) {
	c, e := connect(ctx, secret, 5*time.Second)
	if e == nil {
		c, e = verifyManaged(ctx, c)
		if e == nil {
			return c, nil
		}
		if errors.Is(e, errUnmanaged) {
			return nil, e
		}
	} else {
		// An occupied port with different credentials must not cause a second OBS.
		conn, probeErr := net.DialTimeout("tcp", "127.0.0.1:"+Port, 300*time.Millisecond)
		if probeErr == nil {
			_ = conn.Close()
			return nil, errors.New("port 4457 is already in use or OBSGod credentials do not match; stop the conflicting instance in Desktop Mode")
		}
		if len(managedProcesses(p)) == 0 {
			if e := Prepare(p, s, secret); e != nil {
				return nil, e
			}
			if e := launchOBS(p); e != nil {
				return nil, e
			}
		}
	}
	for {
		if e := wait(ctx, 500*time.Millisecond); e != nil {
			return nil, errors.New("OBS did not become ready before the timeout; run Desktop setup diagnostics")
		}
		c, e = connect(ctx, secret, 5*time.Second)
		if e == nil {
			// OBS can accept authentication before its frontend accepts requests.
			c, e = verifyManaged(ctx, c)
			if e == nil {
				return c, nil
			}
			if errors.Is(e, errUnmanaged) {
				return nil, e
			}
		}
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
	}
}

func verifyManaged(ctx context.Context, c *automation.Client) (*automation.Client, error) {
	r, e := c.RuntimeStatus(ctx)
	if e != nil {
		_ = c.Close()
		return nil, e
	}
	if r.Profile != "OBSGod" {
		_ = c.Close()
		return nil, errUnmanaged
	}
	return c, nil
}

func ensureCapture(ctx context.Context, c *automation.Client, s Settings) error {
	if e := c.EnsureCollection(ctx, "OBSGod"); e != nil {
		return e
	}
	for _, scene := range []string{IdleScene, LiveScene} {
		if e := c.EnsureScene(ctx, scene); e != nil {
			return e
		}
	}
	settings := map[string]any{"pipeline": CapturePipeline, "use_timestamps_video": true, "sync_appsink_video": false, "disable_async_appsink_video": true, "disable_async_appsink_audio": true, "no_buffer": true, "drop_video": true, "stop_on_hide": true, "clear_on_end": true, "restart_on_error": true, "restart_on_eos": true, "restart_timeout": 2000}
	if e := c.EnsureInput(ctx, LiveScene, CaptureInput, "gstreamer-source", settings); e != nil {
		return e
	}
	if e := c.FitInput(ctx, LiveScene, CaptureInput); e != nil {
		return e
	}
	if e := c.EnsureInput(ctx, LiveScene, GameAudio, "pulse_output_capture", map[string]any{"device_id": "default"}); e != nil {
		return e
	}
	if e := c.SetInputMuted(ctx, GameAudio, false); e != nil {
		return e
	}
	keep := map[string]bool{GameAudio: true}
	if s.Microphone {
		if e := c.EnsureInput(ctx, LiveScene, MicAudio, "pulse_input_capture", map[string]any{"device_id": "default"}); e != nil {
			return e
		}
		if e := c.SetInputMuted(ctx, MicAudio, false); e != nil {
			return e
		}
		keep[MicAudio] = true
	}
	if e := c.MuteOtherAudio(ctx, keep); e != nil {
		return e
	}
	return c.SetScene(ctx, LiveScene)
}

// NonblankCapture checks actual screenshot pixels, not just source registration.
// A loading screen may legitimately be black; retry after opening a visible game.
func NonblankCapture(data string) bool {
	payload, ok := strings.CutPrefix(data, "data:image/png;base64,")
	if !ok || len(payload) > 2*1024*1024 {
		return false
	}
	b, e := base64.StdEncoding.DecodeString(payload)
	if e != nil {
		return false
	}
	cfg, _, e := image.DecodeConfig(bytes.NewReader(b))
	if e != nil || cfg.Width > 2048 || cfg.Height > 2048 {
		return false
	}
	im, _, e := image.Decode(bytes.NewReader(b))
	if e != nil || im.Bounds().Dx() < 16 || im.Bounds().Dy() < 16 {
		return false
	}
	var lo uint32 = 65535
	var hi uint32
	for y := im.Bounds().Min.Y; y < im.Bounds().Max.Y; y += 3 {
		for x := im.Bounds().Min.X; x < im.Bounds().Max.X; x += 3 {
			r, g, b, a := im.At(x, y).RGBA()
			if a == 0 {
				continue
			}
			v := (r + g + b) / 3
			if v < lo {
				lo = v
			}
			if v > hi {
				hi = v
			}
		}
	}
	return hi > 1024 && hi > lo+512
}

func waitCapture(ctx context.Context, c *automation.Client) error {
	for {
		// Check the rendered program scene, including transforms. A source can
		// have valid pixels while a mis-scaled/hidden scene still broadcasts black.
		data, e := c.Screenshot(ctx, LiveScene)
		if e == nil && NonblankCapture(data) {
			return nil
		}
		if e := wait(ctx, 600*time.Millisecond); e != nil {
			return errors.New("no visible game frames arrived. Open a game and try again; a black Gamescope feed cannot be streamed safely. No broadcast was started")
		}
	}
}

func Start(ctx context.Context, p Paths) (Result, error) {
	s, secret, e := Load(p)
	if e != nil {
		return Result{}, e
	}
	if e = checkDependencies(ctx); e != nil {
		return Result{}, e
	}
	c, e := ready(ctx, p, s, secret)
	if e != nil {
		return Result{}, e
	}
	defer c.Close()
	state, e := c.StreamStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	if !state.Active {
		if !gamescopeReady(ctx) {
			return Result{}, errors.New("switch to Gaming Mode and open a game first; the Gamescope capture feed is not available")
		}
		if e = ensureCapture(ctx, c, s); e != nil {
			return Result{}, e
		}
		captureCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
		e = waitCapture(captureCtx, c)
		cancel()
		if e != nil {
			_ = c.SetScene(ctx, IdleScene)
			return Result{}, e
		}
		if e = c.ConfigureRTMP(ctx, s.Server, secret.StreamKey); e != nil {
			return Result{}, e
		}
	}
	startCtx, cancel := context.WithTimeout(ctx, 25*time.Second)
	defer cancel()
	state, e = c.StartStream(startCtx)
	if e != nil {
		// A failed/cancelled start must not silently keep broadcasting later.
		cleanup, done := context.WithTimeout(context.Background(), 5*time.Second)
		defer done()
		_, stopErr := c.StopStream(cleanup)
		if stopErr == nil {
			_ = c.SetScene(cleanup, IdleScene)
			return Result{}, errors.New("stream did not reach a healthy output and was stopped; check the ingest URL, key, network and encoder in Desktop setup")
		}
		return Result{}, errors.New("stream start could not be confirmed and stop could not be confirmed. Use Stop streaming or inspect OBS immediately")
	}
	return Result{OK: true, Configured: true, Connected: true, State: "streaming", Message: "OBS streaming — verify picture and sound on your Kick channel", Stream: state}, nil
}

func Stop(ctx context.Context, p Paths) (Result, error) {
	secret, e := loadCredentials(p)
	if e != nil {
		return Result{}, e
	}
	c, e := connect(ctx, secret, time.Second)
	if e != nil {
		conn, err := net.DialTimeout("tcp", "127.0.0.1:"+Port, 300*time.Millisecond)
		if err != nil && len(managedProcesses(p)) == 0 {
			return Result{OK: true, Configured: true, State: "stopped", Message: "OBS is offline"}, nil
		}
		if conn != nil {
			_ = conn.Close()
		}
		return Result{}, errors.New("cannot confirm the stream has stopped: OBS is present but unreachable")
	}
	defer c.Close()
	if _, e = verifyManaged(ctx, c); e != nil {
		return Result{}, e
	}
	state, e := c.StopStream(ctx)
	if e != nil {
		return Result{}, e
	}
	r, e := c.RuntimeStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	if !r.Recording {
		_ = c.SetScene(ctx, IdleScene)
	}
	return Result{OK: true, Configured: true, Connected: true, State: "stopped", Message: "Streaming stopped", Stream: state}, nil
}

// TestRecording captures ten seconds locally and never configures/starts RTMP.
func TestRecording(ctx context.Context, p Paths) (Result, error) {
	s, secret, e := Load(p)
	if e != nil {
		return Result{}, e
	}
	if e = checkDependencies(ctx); e != nil {
		return Result{}, e
	}
	if !gamescopeReady(ctx) {
		return Result{}, errors.New("open a game in Gaming Mode before making the local test clip")
	}
	c, e := ready(ctx, p, s, secret)
	if e != nil {
		return Result{}, e
	}
	defer c.Close()
	r, e := c.RuntimeStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	st, e := c.StreamStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	if r.Recording || st.Active {
		return Result{}, errors.New("stop the existing stream or recording before making a test clip")
	}
	if e = ensureCapture(ctx, c, s); e != nil {
		return Result{}, e
	}
	defer func() {
		cleanup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_, _ = c.StopRecording(cleanup)
		_ = c.SetScene(cleanup, IdleScene)
	}()
	capCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
	e = waitCapture(capCtx, c)
	cancel()
	if e != nil {
		return Result{}, e
	}
	recordCtx, recordCancel := context.WithTimeout(ctx, 15*time.Second)
	e = c.StartRecording(recordCtx)
	recordCancel()
	if e != nil {
		return Result{}, e
	}
	if e = wait(ctx, 10*time.Second); e != nil {
		return Result{}, e
	}
	path, e := c.StopRecording(ctx)
	if e != nil {
		return Result{}, e
	}
	if info, err := os.Stat(path); path == "" || err != nil || !info.Mode().IsRegular() || info.Size() == 0 {
		return Result{}, errors.New("OBS did not produce a test recording; no successful clip can be confirmed")
	}
	return Result{OK: true, Configured: true, Connected: true, State: "stopped", Message: "Local test saved; watch it in Desktop Mode to check picture, game audio and microphone before broadcasting", RecordingPath: path}, nil
}

func Restart(ctx context.Context, p Paths) (Result, error) {
	secret, e := loadCredentials(p)
	if e != nil {
		return Result{}, e
	}
	c, e := connect(ctx, secret, time.Second)
	if e == nil {
		r, err := c.RuntimeStatus(ctx)
		if err != nil {
			_ = c.Close()
			return Result{}, err
		}
		s, err := c.StreamStatus(ctx)
		_ = c.Close()
		if err != nil {
			return Result{}, err
		}
		if r.Recording || s.Active {
			return Result{}, errors.New("stop streaming and recording before restarting OBSGod")
		}
	} else if len(managedProcesses(p)) > 0 {
		return Result{}, errors.New("cannot safely restart an unreachable OBS instance; inspect it in Desktop Mode first")
	}
	if e = stopManagedOBS(ctx, p); e != nil {
		return Result{}, e
	}
	return Result{OK: true, Configured: true, State: "stopped", Message: "Managed OBS closed; saved settings will apply on the next start"}, nil
}

func wait(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}
