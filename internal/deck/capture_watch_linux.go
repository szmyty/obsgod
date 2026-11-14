//go:build linux

package deck

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type captureWatchDeps struct {
	load             func(Paths) (Settings, Secrets, error)
	connect          func(context.Context, Secrets) (*automation.Client, error)
	discover         func(context.Context) GameIdentity
	routeAudio       func(context.Context, *automation.Client, Paths, Settings) error
	interval         time.Duration
	discoveryTimeout time.Duration
}

const captureDiscoveryTimeout = time.Second

func observeCaptureOutput(ctx context.Context, c *automation.Client) (automation.RuntimeStatus, bool, error) {
	runtime, err := c.RuntimeStatus(ctx)
	if err != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return runtime, false, err
	}
	stream, err := c.StreamStatus(ctx)
	if err != nil {
		return runtime, false, err
	}
	replay, err := c.ReplayActive(ctx)
	return runtime, stream.Active || stream.Reconnecting || runtime.Recording || replay, err
}

// WatchCapture only maintains the selected game/idle scene while output already
// exists. It never starts, stops or implicitly authorizes a stream/recording.
func WatchCapture(ctx context.Context, p Paths) error {
	return watchCaptureWith(ctx, p, captureWatchDeps{load: Load, connect: func(ctx context.Context, secret Secrets) (*automation.Client, error) {
		return connect(ctx, secret, 600*time.Millisecond)
	}, discover: DiscoverGame, interval: time.Second})
}

type captureWatchCache struct {
	target            uint32
	audioIdentity     uint32
	audioReady        bool
	videoPolicySet    bool
	microphoneEnabled bool
	idleKey           string
	stability         gameStability
}

type captureWatchResult struct {
	settings                 Settings
	state, frames            string
	stopped, unmanaged, busy bool
	err                      error
}

// mutateCapture takes the shared control lease only after discovery. Every
// setting and output fact that authorizes a mutation is checked again here.
func mutateCapture(ctx context.Context, p Paths, deps captureWatchDeps, c *automation.Client, settings Settings, secret Secrets, discovered GameIdentity, cache *captureWatchCache) captureWatchResult {
	result := captureWatchResult{settings: settings, state: "unknown", frames: "unknown"}
	control, controlDone := context.WithTimeout(ctx, 250*time.Millisecond)
	unlock, err := Lock(control, p)
	controlDone()
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
			result.busy = true // Explicit Start/Stop/configuration wins.
		} else {
			result.err = err
		}
		return result
	}
	defer unlock()
	return mutateCaptureUnderLease(ctx, p, deps, c, settings, secret, discovered, cache, false)
}

// The caller owns the shared control lease. The local test parent uses this
// same guarded mutation phase while its recording transaction retains ownership.
func mutateCaptureUnderLease(ctx context.Context, p Paths, deps captureWatchDeps, c *automation.Client, settings Settings, secret Secrets, discovered GameIdentity, cache *captureWatchCache, requireRecording bool) captureWatchResult {
	result := captureWatchResult{settings: settings, state: "unknown", frames: "unknown"}
	fresh, freshSecret, err := deps.load(p)
	if err != nil {
		result.err = err
		return result
	}
	result.settings = fresh
	result.stopped = fresh.CaptureModeName() != "game"
	result.busy = fresh != settings || freshSecret != secret
	if result.stopped || result.busy {
		return result
	}
	runtime, active, err := observeCaptureOutput(ctx, c)
	result.err = err
	if err != nil {
		return result
	}
	result.unmanaged = runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod"
	result.stopped = !result.unmanaged && (!active || requireRecording && !runtime.Recording)
	if result.unmanaged || result.stopped {
		return result
	}
	videoSettings, err := effectiveVideoSettings(p, fresh)
	if err != nil {
		result.err = err
		return result
	}
	if cache.videoPolicySet && cache.microphoneEnabled != videoSettings.Microphone {
		cache.target, cache.idleKey = 0, ""
	}
	cache.videoPolicySet, cache.microphoneEnabled = true, videoSettings.Microphone
	key := idleMediaKey(p, fresh)
	if key != cache.idleKey {
		if result.err = ensureIdleVideo(ctx, c, p, videoSettings); result.err != nil {
			return result
		}
		cache.idleKey = key
	}
	result.state, result.frames, result.err = gameVideoStep(ctx, c, videoSettings, cache.stability.observe(discovered), runtime.Scene, &cache.target)
	if result.err != nil {
		return result
	}
	identity := uint32(0)
	if discovered.State == "running" && discovered.AppID != 769 {
		identity = discovered.AppID
	}
	if deps.routeAudio != nil && (!cache.audioReady || cache.audioIdentity != identity) {
		// Video reaches its privacy-preserving state before optional audio
		// recovery spends the remaining budget. No video mutation follows it.
		audioCtx, audioDone := context.WithTimeout(ctx, time.Second)
		audioErr := deps.routeAudio(audioCtx, c, p, fresh)
		audioDone()
		if audioErr == nil {
			cache.audioIdentity, cache.audioReady = identity, true
		} else {
			logEvent(p, "audio.unavailable")
		}
	}
	return result
}

// waitTestCapture retains the initiating command's control lease. Servicing
// game capture here lets the detached observer yield without freezing a local
// clip on its initial idle frame or showing an exited game for ten seconds.
func waitTestCapture(ctx context.Context, p Paths, c *automation.Client, settings Settings, secret Secrets, duration time.Duration) error {
	return waitTestCaptureWith(ctx, p, c, settings, secret, duration, captureWatchDeps{load: Load, discover: DiscoverGame,
		connect: func(ctx context.Context, secret Secrets) (*automation.Client, error) {
			return connect(ctx, secret, 600*time.Millisecond)
		}, interval: time.Second, discoveryTimeout: captureDiscoveryTimeout})
}

func waitTestCaptureWith(ctx context.Context, p Paths, c *automation.Client, settings Settings, secret Secrets, duration time.Duration, deps captureWatchDeps) error {
	if settings.CaptureModeName() != "game" {
		return wait(ctx, duration)
	}
	if deps.interval <= 0 {
		deps.interval = time.Second
	}
	if deps.discoveryTimeout <= 0 {
		deps.discoveryTimeout = captureDiscoveryTimeout
	}
	period, done := context.WithTimeout(ctx, duration)
	defer done()
	cache := captureWatchCache{}
	for {
		cycle, cycleDone := context.WithTimeout(period, 4*time.Second)
		discovery, discoveryDone := context.WithTimeout(cycle, deps.discoveryTimeout)
		game := deps.discover(discovery)
		err := discovery.Err()
		discoveryDone()
		if err == nil {
			// A tick ending at the clip deadline may invalidate its transport.
			// Keep the transaction's original connection available for cleanup.
			tickClient := c
			if deps.connect != nil {
				tickClient, err = deps.connect(cycle, secret)
			}
			if err == nil {
				result := mutateCaptureUnderLease(cycle, p, deps, tickClient, settings, secret, game, &cache, true)
				err = result.err
				if result.unmanaged || result.stopped || result.busy {
					err = errors.New("local test capture ownership or recording state changed; inspect managed OBS before retrying")
				}
				if deps.connect != nil {
					_ = tickClient.Close()
				}
			}
		}
		cycleDone()
		if period.Err() != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			if err != nil && !errors.Is(err, context.DeadlineExceeded) && !errors.Is(err, context.Canceled) {
				return err
			}
			return nil // The original clip duration bounds all capture ticks.
		}
		if err != nil {
			return err
		}
		if err = wait(period, deps.interval); err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			return nil
		}
	}
}

func watchCaptureWith(ctx context.Context, p Paths, deps captureWatchDeps) error {
	lockCtx, done := context.WithTimeout(ctx, 100*time.Millisecond)
	unlock, err := Lock(lockCtx, captureWatchPaths(p))
	done()
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if errors.Is(err, context.DeadlineExceeded) {
			return nil // Another lifetime owner remains authoritative.
		}
		return errors.New("game capture observer could not establish its private lifetime lease")
	}
	defer unlock()
	if deps.interval <= 0 {
		deps.interval = time.Second
	}
	if deps.discoveryTimeout <= 0 {
		deps.discoveryTimeout = captureDiscoveryTimeout
	}
	cache := captureWatchCache{}
	ready, failures := false, 0
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		settings, secret, err := deps.load(p)
		if err != nil {
			return err
		}
		if settings.CaptureModeName() != "game" {
			return writeCaptureVideoStatus(p, settings, "stopped", "unknown", false, os.Getpid())
		}
		cycle, cancel := context.WithTimeout(ctx, 4*time.Second)
		c, connectErr := deps.connect(cycle, secret)
		result := captureWatchResult{settings: settings, state: "unknown", frames: "unknown", err: connectErr}
		if connectErr == nil {
			runtime, active, observeErr := observeCaptureOutput(cycle, c)
			result.err = observeErr
			if observeErr == nil {
				result.unmanaged = runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod"
				result.stopped = !result.unmanaged && !active
				if !result.unmanaged && active {
					// Read-only readiness lets Start finish while it still holds
					// the shared control lease. Frame health remains unknown.
					if !ready {
						result.err = writeCaptureVideoStatus(p, settings, "unknown", "unknown", true, os.Getpid())
						ready = result.err == nil
					}
					if result.err == nil {
						discovery, discoveryDone := context.WithTimeout(cycle, deps.discoveryTimeout)
						discovered := deps.discover(discovery)
						result.err = discovery.Err()
						discoveryDone()
						if result.err == nil {
							result = mutateCapture(cycle, p, deps, c, settings, secret, discovered, &cache)
						}
					}
				}
			}
			_ = c.Close()
		}
		cancel()
		if result.unmanaged {
			_ = writeCaptureVideoStatus(p, result.settings, "unknown", "unknown", false, os.Getpid())
			return errors.New("game capture observer stopped because the managed profile or collection is no longer selected")
		}
		if result.stopped {
			// Explicit Stop owns cleanup. An idle observer performs no OBS writes.
			return writeCaptureVideoStatus(p, result.settings, "stopped", "unknown", false, os.Getpid())
		}
		if result.err != nil || result.busy {
			cache = captureWatchCache{}
		}
		if result.err != nil {
			failures++
			result.state, result.frames = "unknown", "unknown"
		} else if !result.busy {
			failures = 0
		}
		watching := ready && failures < 3
		if err := writeCaptureVideoStatus(p, result.settings, result.state, result.frames, watching, os.Getpid()); err != nil {
			return err
		}
		if failures >= 3 {
			return errors.New("game capture observer could not confirm its control connection; no full display fallback was selected")
		}
		if err := wait(ctx, deps.interval); err != nil {
			return err
		}
	}
}
func captureWatchExecutable() (string, error) {
	executable, err := os.Executable()
	if err != nil {
		return "", err
	}
	return filepath.EvalSymlinks(executable)
}
func captureWatchOwner(pid int, executable string) bool {
	if pid <= 0 {
		return false
	}
	proc := filepath.Join("/proc", strconv.Itoa(pid))
	info, err := os.Stat(proc)
	if err != nil || processExited(proc) {
		return false
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(stat.Uid) != os.Getuid() {
		return false
	}
	actual, err := os.Readlink(filepath.Join(proc, "exe"))
	return err == nil && actual == executable
}

// StartCaptureWatch launches the same canonical CLI, with no credentials in
// argv. Its separate lifetime lock and read-only readiness handshake let the
// initiating Start/Test operation finish while still holding the control lease.
func StartCaptureWatch(p Paths) error {
	settings, _, err := Load(p)
	if err != nil {
		return err
	}
	if settings.CaptureModeName() != "game" {
		return nil
	}
	executable, err := captureWatchExecutable()
	if err != nil {
		return errors.New("could not locate the capture observer executable")
	}
	probe, done := context.WithTimeout(context.Background(), 100*time.Millisecond)
	unlock, lockErr := Lock(probe, captureWatchPaths(p))
	done()
	if lockErr != nil {
		record, fresh := readCaptureVideoRecord(p)
		if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
			return nil
		}
		return errors.New("the existing game capture observer has not confirmed fresh state")
	}
	unlock()
	output, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		return errors.New("could not prepare the capture observer")
	}
	defer output.Close()
	command := exec.Command(executable, "deck", "capture-watch")
	command.Env = sessionEnvironment()
	command.Stdin = nil
	command.Stdout, command.Stderr = output, output
	command.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := command.Start(); err != nil {
		return errors.New("could not launch the game capture observer")
	}
	exited := make(chan int, 1)
	go func() { _ = command.Wait(); exited <- command.ProcessState.ExitCode() }()
	return waitCaptureWatchReady(p, executable, exited, 5*time.Second)
}

func waitCaptureWatchReady(p Paths, executable string, exited <-chan int, timeout time.Duration) error {
	deadline := time.NewTimer(timeout)
	defer deadline.Stop()
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	for {
		record, fresh := readCaptureVideoRecord(p)
		if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
			return nil
		}
		select {
		case <-exited:
			// A simultaneous launcher may have won the lifetime lock.
			record, fresh := readCaptureVideoRecord(p)
			if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
				return nil
			}
			return errors.New("game capture observer exited before confirming its state")
		case <-deadline.C:
			return errors.New("game capture observer has not confirmed fresh state; output was not stopped or restarted")
		case <-ticker.C:
		}
	}
}
