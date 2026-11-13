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
	Diagnostics   []DiagnosticEntry         `json:"diagnostics"`
	Process       string                    `json:"process"`
	Connection    string                    `json:"connection"`
	OutputKnown   bool                      `json:"output_known"`
	Recording     bool                      `json:"recording"`
	Capture       string                    `json:"capture"`
	Game          string                    `json:"game"`
	Frames        string                    `json:"frames"`
	Audio         *AudioStatus              `json:"audio,omitempty"`
	Video         *CaptureVideoStatus       `json:"video,omitempty"`
	Media         *MediaSnapshot            `json:"media"`
	Resilience    *ResilienceStatus         `json:"resilience,omitempty"`
}

func connect(ctx context.Context, secret Secrets, timeout time.Duration) (*automation.Client, error) {
	return automation.Connect(ctx, automation.Config{Address: net.JoinHostPort("127.0.0.1", Port), Password: secret.OBSPassword, Timeout: timeout})
}

// presence is conservative: an occupied control port without a matching managed
// process is still possibly active output, never proof that OBS is stopped.
func presence(p Paths) (string, bool) {
	process := obsProcessState(p)
	conn, err := net.DialTimeout("tcp", "127.0.0.1:"+Port, 150*time.Millisecond)
	if conn != nil {
		_ = conn.Close()
	}
	if err == nil && process == "absent" {
		process = "unknown"
	}
	return process, err == nil
}

func Status(ctx context.Context, p Paths) Result {
	s, secret, loadErr := Load(p)
	process, listener := presence(p)
	r := Result{OK: true, Configured: loadErr == nil, State: "stopped", Message: "Not streaming", Process: process, Connection: "disconnected", Capture: "unknown", Game: "unknown", Frames: "unknown"}
	pref, _ := RecordingSettings(p)
	r.Media = &MediaSnapshot{Preferences: pref, Message: "Local output state is unconfirmed"}
	resilience := ReadResilienceStatus(p)
	r.Resilience = &resilience
	if loadErr == nil {
		r.Settings = &s
	} else {
		r.State, r.Message = "setup", loadErr.Error()
		secret, loadErr = loadCredentials(p)
	}
	if process == "absent" && !listener {
		r.OutputKnown = true
		r.Connection = "unavailable"
		r.Media.Known = true
		r.Media.Message = "No managed OBS output is running"
	}
	if loadErr != nil {
		if !r.OutputKnown {
			r.OK = false
			r.State = "unknown"
			r.Message = "OBS may still be running but its credentials are unavailable. Inspect the managed OBS window before changing settings"
		}
		return r
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	c, err := connect(ctx, secret, 600*time.Millisecond)
	if err != nil {
		if !r.OutputKnown {
			r.OK = false
			r.State = "unknown"
			r.Message = "OBS is present but its output state cannot be confirmed"
		}
		return r
	}
	defer c.Close()
	r.Connected, r.Connection = true, "ready"
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		r.OK, r.State, r.OutputKnown = false, "unknown", false
		r.Message = "The managed OBS profile and output state could not be verified"
		return r
	}
	r.Process, r.Runtime, r.Recording = "running", &runtime, runtime.Recording
	r.Stream, err = c.StreamStatus(ctx)
	if err != nil {
		r.OK, r.State, r.OutputKnown = false, "unknown", false
		r.Message = "OBS status unavailable; check the connection"
		return r
	}
	media := ObserveMedia(ctx, p, c)
	r.Media = &media
	if !media.Known {
		r.OK, r.State, r.OutputKnown = false, "unknown", false
		r.Message = "OBS is connected but recording/replay state could not be confirmed; inspect local output before changing settings"
		return r
	}
	r.Recording = media.Recording.Active
	r.OutputKnown = true
	r.Audio = readAudioStatus(p)
	video := ReadCaptureVideoStatus(p)
	r.Video = &video
	captureCtx, captureCancel := context.WithTimeout(ctx, 400*time.Millisecond)
	r.Capture = captureAvailability(captureCtx)
	captureCancel()
	if r.Stream.Active || r.Recording || media.ReplayActive {
		data, frameErr := c.Screenshot(ctx, runtime.Scene)
		if frameErr == nil {
			r.Frames = "blank"
			if NonblankCapture(data) {
				r.Frames = "visible"
			}
		}
	}
	if (r.Stream.Active || r.Recording || media.ReplayActive) && ctx.Err() == nil {
		audioCtx, audioCancel := context.WithTimeout(ctx, 450*time.Millisecond)
		r.Audio = measureAudio(audioCtx, p, secret, 180*time.Millisecond, false)
		audioCancel()
	}
	if s.CaptureModeName() == "game" && runtime.Scene == IdleScene {
		r.Frames = "placeholder"
		r.Game = "idle"
	}
	if s.CaptureModeName() == "game" && runtime.Scene == GameScene {
		r.Game = "running"
	}
	if r.Stream.Active {
		r.State, r.Message = "starting", "Connecting or reconnecting to the stream server"
		if !r.Stream.Reconnecting && r.Stream.Bytes > 0 {
			r.State, r.Message = "streaming", "OBS streaming"
			if s.CaptureModeName() == "game" && runtime.Scene == IdleScene {
				r.Message = "OBS streaming — between-game screen; waiting for verified game capture"
			} else if r.Frames != "visible" || (s.CaptureModeName() == "screen" && r.Capture == "unavailable") {
				r.Message = "OBS output is active; captured picture cannot be confirmed. Check capture or use Stop"
			}
		}
	} else if r.Configured {
		r.State, r.Message = "stopped", "Not streaming"
		if r.Recording {
			r.Message = "Recording locally; not streaming"
		} else if media.ReplayActive {
			r.Message = "Replay buffer is active locally; not streaming"
		}
	}
	return r
}

func Doctor(ctx context.Context, p Paths) Result {
	r := Status(ctx, p)
	if settings, _, err := Load(p); err == nil {
		route, audioErr := DiscoverAudio(ctx, settings.Microphone)
		status := safeAudioStatus(route, audioErr)
		r.Audio = &status
	}
	if err := checkDependencies(ctx); err != nil {
		r.OK = false
		r.Message = err.Error()
		return r
	}
	captureCtx, cancel := context.WithTimeout(ctx, time.Second)
	defer cancel()
	r.Capture = captureAvailability(captureCtx)
	// Capture availability is independent of process, connection and output state.
	// A missing feed must never overwrite a live-stream status.
	if r.Capture == "unavailable" && r.State != "streaming" && r.State != "starting" && r.State != "unknown" {
		r.Message = "Gamescope capture feed is unavailable in this session. OBS control does not require a game; a local clip or broadcast still requires usable captured frames"
	}
	return r
}

const connectAttemptTimeout = time.Second
const startupTimeout = 20 * time.Second

func connectionKind(err error) string {
	var e *automation.ConnectionError
	if errors.As(err, &e) {
		return e.Kind
	}
	return "transport"
}

func ready(ctx context.Context, p Paths, s Settings, secret Secrets) (*automation.Client, error) {
	return readyWithin(ctx, p, s, secret, startupTimeout)
}

func readyWithin(ctx context.Context, p Paths, s Settings, secret Secrets, budget time.Duration) (*automation.Client, error) {
	ctx, cancel := context.WithTimeout(ctx, budget)
	defer cancel()
	logEvent(p, "obs.connecting")
	var launched <-chan int
	lastStage := "obs.listener-unavailable"
	recovery := recoveryMarkerPresent(p)
	for {
		c, err := connect(ctx, secret, connectAttemptTimeout)
		if err == nil {
			// Authentication can finish while the OBS frontend is still loading.
			attempt, done := context.WithTimeout(ctx, connectAttemptTimeout)
			c, err = verifyManaged(attempt, c)
			done()
			if err == nil {
				logEvent(p, "obs.ready")
				return c, nil
			}
			if errors.Is(err, errUnmanaged) {
				return nil, err
			}
			lastStage = "obs.frontend-waiting"
		} else {
			if connectionKind(err) == "authentication" {
				logEvent(p, "obs.authentication-failed")
				return nil, errors.New("OBS WebSocket authentication failed; open the managed OBS window and verify its local server settings. No second OBS instance was launched")
			}
			process, listening := presence(p)
			if process == "unknown" && !listening {
				logEvent(p, "obs.ownership-unknown")
				return nil, errors.New("an owned OBS process could not be identified safely. Inspect its window before launching another instance")
			}
			if listening {
				lastStage = "obs.authentication-waiting"
				if launched == nil && len(managedProcesses(p)) == 0 {
					return nil, errors.New("port 4457 is already in use or OBSGod credentials do not match; stop the conflicting instance in Desktop Mode")
				}
			} else {
				lastStage = "obs.listener-unavailable"
			}
			if launched == nil && !listening && process == "absent" {
				if err := ctx.Err(); err != nil {
					return nil, err
				}
				if err := Prepare(p, s, secret); err != nil {
					return nil, err
				}
				if recovery {
					logEvent(p, "obs.recovery-marker")
				}
				logEvent(p, "obs.launching")
				launched, err = launchOBS(p)
				if err != nil {
					return nil, err
				}
				logEvent(p, "obs.waiting")
			}
		}
		select {
		case code := <-launched:
			logEvent(p, "obs.exited", code)
			return nil, errors.New("OBS exited before becoming ready; check installed Flatpaks and open the managed OBS window in Desktop Mode")
		default:
		}
		if err := wait(ctx, 200*time.Millisecond); err != nil {
			if errors.Is(err, context.Canceled) {
				return nil, err
			}
			logEvent(p, lastStage)
			logEvent(p, "obs.timeout")
			if recovery {
				return nil, errors.New("OBS startup reached its time limit and a previous unclean-shutdown marker was found. Open the managed OBS window to resolve its recovery dialog; do not choose Safe Mode because it disables control and capture plugins")
			}
			switch lastStage {
			case "obs.frontend-waiting":
				return nil, errors.New("OBS authenticated but its frontend did not become ready within the startup limit. Open the managed OBS window and check for a setup or plugin dialog")
			case "obs.authentication-waiting":
				return nil, errors.New("OBS control port opened but authentication did not complete within the startup limit. Check the managed WebSocket server and password in Desktop Mode")
			default:
				return nil, errors.New("OBS did not open its control listener within the startup limit. Open the managed OBS window to check launch, display/session, recovery dialogs and the built-in WebSocket server")
			}
		}
	}
}

func verifyManaged(ctx context.Context, c *automation.Client) (*automation.Client, error) {
	r, e := c.RuntimeStatus(ctx)
	if e != nil {
		_ = c.Close()
		return nil, e
	}
	if r.Profile != "OBSGod" || r.Collection != "OBSGod" {
		_ = c.Close()
		return nil, errUnmanaged
	}
	return c, nil
}

func ensureCapture(ctx context.Context, c *automation.Client, p Paths, s Settings) error {
	if err := ensureVideo(ctx, c, p, s); err != nil {
		return err
	}
	return ensureAudio(ctx, c, p, s)
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

func waitCapture(ctx context.Context, c *automation.Client, p Paths) error {
	logEvent(p, "capture.waiting")
	for {
		// Check the rendered program scene, including transforms. A source can
		// have valid pixels while a mis-scaled/hidden scene still broadcasts black.
		data, e := c.Screenshot(ctx, LiveScene)
		if e == nil && NonblankCapture(data) {
			logEvent(p, "capture.ready")
			return nil
		}
		if e := wait(ctx, 600*time.Millisecond); e != nil {
			logEvent(p, "capture.blank")
			return errors.New("no usable captured frames arrived. Check the current Gamescope feed and visible content; a blank feed cannot be broadcast safely. No new broadcast was started")
		}
	}
}

func waitGamescope(ctx context.Context) bool {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	for {
		if gamescopeReady(ctx) {
			return true
		}
		if wait(ctx, 150*time.Millisecond) != nil {
			return false
		}
	}
}

func haltCapture(ctx context.Context, c *automation.Client) {
	_ = c.SetScene(ctx, IdleScene)
	_ = c.UpdateInputIfPresent(ctx, CaptureInput, map[string]any{"stop_on_hide": true})
	_ = c.UpdateInputIfPresent(ctx, GameCaptureInput, map[string]any{"stop_on_hide": true})
}

// haltCaptureIfIdle must not disrupt an independently started recording or an
// output whose shutdown could not be verified. Keep capture running on unknown.
func haltCaptureIfIdle(ctx context.Context, c *automation.Client) {
	stream, err := c.StreamStatus(ctx)
	if err != nil || stream.Active {
		return
	}
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Recording {
		return
	}
	replay, err := c.ReplayActive(ctx)
	if err != nil || replay {
		return
	}
	haltCapture(ctx, c)
}

func Start(ctx context.Context, p Paths) (Result, error) {
	if process, listener := presence(p); process == "absent" && !listener {
		if _, err := ApplyBoundGameProfile(ctx, p); err != nil {
			return Result{}, err
		}
	}
	s, secret, e := Load(p)
	if e != nil {
		return Result{}, e
	}
	logEvent(p, "dependencies.checking")
	if e = checkDependencies(ctx); e != nil {
		logEvent(p, "dependencies.missing")
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
	wasActive := state.Active
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil {
		return Result{}, err
	}
	if !wasActive && runtime.Recording {
		return Result{}, errors.New("a local recording is already active; stop it before changing capture or starting a new stream")
	}
	replay, err := c.ReplayActive(ctx)
	if err != nil {
		return Result{}, err
	}
	if !wasActive && replay {
		return Result{}, errors.New("a replay buffer is already active; stop it before changing capture or starting a new stream")
	}

	succeeded := false
	defer func() {
		if !succeeded && !wasActive {
			cleanup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			haltCaptureIfIdle(cleanup, c)
		}
	}()
	if !wasActive {
		logEvent(p, "capture.checking")
		if s.CaptureModeName() == "screen" && !waitGamescope(ctx) {
			logEvent(p, "capture.unavailable")
			return Result{}, errors.New("the Gamescope capture feed is unavailable in this session; OBS is ready, but a broadcast requires usable captured frames")
		}
		logEvent(p, "capture.configuring")
		if e = ensureCapture(ctx, c, p, s); e != nil {
			return Result{}, e
		}
		captureCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
		if s.CaptureModeName() == "screen" {
			e = waitCapture(captureCtx, c, p)
		}
		cancel()
		if e != nil {
			return Result{}, e
		}
		if e = c.ConfigureRTMP(ctx, s.Server, secret.StreamKey); e != nil {
			return Result{}, e
		}
	}
	startCtx, cancel := context.WithTimeout(ctx, 25*time.Second)
	defer cancel()
	logEvent(p, "stream.connecting")
	state, e = c.StartStream(startCtx)
	if e != nil {
		if wasActive {
			logEvent(p, "stream.existing-unconfirmed")
			return Result{}, errors.New("the existing stream did not confirm advancing output. It was not stopped automatically; inspect it or use Stop streaming")
		}
		// A failed/cancelled new start must not silently keep broadcasting later.
		cleanup, done := context.WithTimeout(context.Background(), 5*time.Second)
		defer done()
		_, stopErr := c.StopStream(cleanup)
		if stopErr == nil {
			haltCaptureIfIdle(cleanup, c)
			logEvent(p, "stream.failed-stopped")
			return Result{}, errors.New("stream did not reach a healthy output and was stopped; check the ingest URL, key, network and encoder in Desktop setup")
		}
		logEvent(p, "stream.unconfirmed")
		return Result{}, errors.New("stream start could not be confirmed and stop could not be confirmed. Use Stop streaming or inspect OBS immediately")
	}
	succeeded = true
	_ = StartResilienceWatch(p)
	if s.CaptureModeName() == "game" {
		if err := StartCaptureWatch(p); err != nil {
			logEvent(p, "game.watch-unavailable")
		}
	}
	audioCtx, audioCancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	_ = measureAudio(audioCtx, p, secret, time.Second, true)
	audioCancel()
	logEvent(p, "stream.ready")
	return Result{OK: true, Configured: true, Connected: true, State: "streaming", Message: "OBS streaming — verify picture and sound on your Kick channel", Stream: state}, nil
}

func Stop(ctx context.Context, p Paths) (Result, error) {
	secret, e := loadCredentials(p)
	if e != nil {
		return Result{}, e
	}
	c, e := connect(ctx, secret, time.Second)
	if e != nil {
		process, listener := presence(p)
		if process == "absent" && !listener {
			return Result{OK: true, Configured: true, State: "stopped", Message: "OBS is offline"}, nil
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
	_ = r // Capture cleanup independently confirms recording and replay again.
	haltCaptureIfIdle(ctx, c)
	logEvent(p, "stream.stopped")
	return Result{OK: true, Configured: true, Connected: true, State: "stopped", Message: "Streaming stopped", Stream: state}, nil
}

// TestRecording captures ten seconds locally and never configures/starts RTMP.
func TestRecording(ctx context.Context, p Paths) (Result, error) {
	if process, listener := presence(p); process == "absent" && !listener {
		if _, err := ApplyBoundGameProfile(ctx, p); err != nil {
			return Result{}, err
		}
	}
	s, secret, e := Load(p)
	if e != nil {
		return Result{}, e
	}
	logEvent(p, "dependencies.checking")
	if e = checkDependencies(ctx); e != nil {
		logEvent(p, "dependencies.missing")
		return Result{}, e
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
	replay, replayErr := c.ReplayActive(ctx)
	if replayErr != nil {
		return Result{}, replayErr
	}
	if r.Recording || st.Active || replay {
		return Result{}, errors.New("stop the existing stream, recording or replay before making a test clip")
	}
	if _, e = MediaStorageStatus(p, true); e != nil {
		return Result{}, e
	}
	directory, seconds, memoryMB, mediaErr := MediaProfileValues(p)
	if mediaErr != nil {
		return Result{}, mediaErr
	}
	if e = c.ConfigureMediaProfile(ctx, directory, seconds, memoryMB); e != nil {
		return Result{}, e
	}
	logEvent(p, "capture.checking")
	if s.CaptureModeName() == "screen" && !waitGamescope(ctx) {
		logEvent(p, "capture.unavailable")
		return Result{}, errors.New("the Gamescope capture feed is unavailable in this session; OBS is ready, but a local clip requires usable captured frames")
	}
	logEvent(p, "capture.configuring")
	if e = ensureCapture(ctx, c, p, s); e != nil {
		return Result{}, e
	}
	defer func() {
		cleanup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_, _ = c.StopRecording(cleanup)
		haltCaptureIfIdle(cleanup, c)
	}()
	capCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
	if s.CaptureModeName() == "screen" {
		e = waitCapture(capCtx, c, p)
	}
	cancel()
	if e != nil {
		return Result{}, e
	}
	recordCtx, recordCancel := context.WithTimeout(ctx, 15*time.Second)
	logEvent(p, "recording.starting")
	e = c.StartRecording(recordCtx)
	recordCancel()
	if e != nil {
		return Result{}, e
	}
	_ = StartResilienceWatch(p)
	if s.CaptureModeName() == "game" {
		if err := StartCaptureWatch(p); err != nil {
			logEvent(p, "game.watch-unavailable")
		}
	}
	audioCtx, audioCancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	_ = measureAudio(audioCtx, p, secret, time.Second, true)
	audioCancel()
	logEvent(p, "recording.running")
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
	if e = RegisterMediaFile(p, path, "recording"); e != nil {
		return Result{}, e
	}
	logEvent(p, "recording.saved")
	return Result{OK: true, Configured: true, Connected: true, State: "stopped", Message: "Local test saved; watch it in Desktop Mode to check picture, game audio and microphone before broadcasting", RecordingPath: path}, nil
}

// OpenOBS is an explicit Desktop recovery action. It launches the isolated
// profile visibly without starting a stream or recording and never duplicates
// an instance whose output state might be unknown.
func OpenOBS(ctx context.Context, p Paths) (Result, error) {
	s, secret, err := Load(p)
	if err != nil {
		return Result{}, err
	}
	if err := checkDependencies(ctx); err != nil {
		return Result{}, err
	}
	process, listener := presence(p)
	if process != "absent" || listener {
		return Result{}, errors.New("managed OBS or its control port is already present; inspect the existing OBS window instead of launching a second instance")
	}
	if err := prepare(p, s, secret, true); err != nil {
		return Result{}, err
	}
	logEvent(p, "obs.open-visible")
	exited, err := launchVisibleOBS(p)
	if err != nil {
		return Result{}, err
	}
	select {
	case code := <-exited:
		logEvent(p, "obs.exited", code)
		return Result{}, errors.New("managed OBS exited before its recovery window could be confirmed; check the installed Flatpaks and graphical session")
	case <-ctx.Done():
		return Result{}, ctx.Err()
	case <-time.After(200 * time.Millisecond):
	}
	return Result{OK: true, Message: "Managed OBS launch requested in a visible window. Resolve any setup or recovery dialog; this action does not start a stream or recording"}, nil
}

func Restart(ctx context.Context, p Paths) (Result, error) {
	secret, e := loadCredentials(p)
	if e != nil {
		return Result{}, e
	}
	c, e := connect(ctx, secret, time.Second)
	if e == nil {
		if _, err := verifyManaged(ctx, c); err != nil {
			return Result{}, err
		}
		r, err := c.RuntimeStatus(ctx)
		if err != nil {
			_ = c.Close()
			return Result{}, err
		}
		s, err := c.StreamStatus(ctx)
		if err != nil {
			_ = c.Close()
			return Result{}, err
		}
		replay, replayErr := c.ReplayActive(ctx)
		_ = c.Close()
		if replayErr != nil {
			return Result{}, replayErr
		}
		if r.Recording || s.Active || replay {
			return Result{}, errors.New("stop streaming, recording and replay before restarting OBSGod")
		}
	} else if process, listener := presence(p); process != "absent" || listener {
		return Result{}, errors.New("cannot safely restart an unreachable OBS instance; inspect it in Desktop Mode first")
	}
	if e = stopManagedOBS(ctx, p); e != nil {
		return Result{}, e
	}
	process, listener := presence(p)
	if process != "absent" || listener {
		return Result{}, errors.New("managed OBS shutdown could not be confirmed; inspect its window before changing settings")
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
