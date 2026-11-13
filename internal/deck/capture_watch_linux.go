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
	load       func(Paths) (Settings, Secrets, error)
	connect    func(context.Context, Secrets) (*automation.Client, error)
	discover   func(context.Context) GameIdentity
	routeAudio func(context.Context, *automation.Client, Paths, Settings) error
	interval   time.Duration
}

// WatchCapture only maintains the selected game/idle scene while output already
// exists. It never starts, stops or implicitly authorizes a stream/recording.
func WatchCapture(ctx context.Context, p Paths) error {
	return watchCaptureWith(ctx, p, captureWatchDeps{load: Load, connect: func(ctx context.Context, secret Secrets) (*automation.Client, error) {
		return connect(ctx, secret, 600*time.Millisecond)
	}, discover: DiscoverGame, interval: time.Second})
}
func watchCaptureWith(ctx context.Context, p Paths, deps captureWatchDeps) error {
	lockCtx, done := context.WithTimeout(ctx, 100*time.Millisecond)
	unlock, err := Lock(lockCtx, captureWatchPaths(p))
	done()
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		// Another lifetime owner is authoritative; a second observer must exit.
		return nil
	}
	defer unlock()
	var target uint32
	var audioIdentity uint32
	audioReady := false
	failures := 0
	idleKey := ""
	var stability gameStability
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
		state, frames := "unknown", "unknown"
		outputIdle := false
		if connectErr == nil {
			runtime, runtimeErr := c.RuntimeStatus(cycle)
			stream, streamErr := c.StreamStatus(cycle)
			replay, replayErr := c.ReplayActive(cycle)
			if runtimeErr == nil && streamErr == nil && replayErr == nil && runtime.Profile == "OBSGod" && runtime.Collection == "OBSGod" {
				if !stream.Active && !runtime.Recording && !replay {
					outputIdle = true
					_ = c.SetScene(cycle, IdleScene)
					_ = pauseGameCapture(cycle, c)
					state = "stopped"
				} else {
					key := idleMediaKey(p, settings)
					if key != idleKey {
						connectErr = ensureIdleVideo(cycle, c, p, settings)
						if connectErr == nil {
							idleKey = key
						}
					}
					if connectErr == nil {
						discovered := deps.discover(cycle)
						game := stability.observe(discovered)
						identity := uint32(0)
						if discovered.State == "running" && discovered.AppID != 769 {
							identity = discovered.AppID
						}
						if deps.routeAudio != nil && (!audioReady || audioIdentity != identity) {
							// Audio recovery must leave time for the privacy-preserving video step.
							audioCtx, audioDone := context.WithTimeout(cycle, time.Second)
							audioErr := deps.routeAudio(audioCtx, c, p, settings)
							audioDone()
							if audioErr == nil {
								audioIdentity = identity
								audioReady = true
							} else {
								logEvent(p, "audio.unavailable")
							}
						}
						state, frames, connectErr = gameVideoStep(cycle, c, settings, game, runtime.Scene, &target)
					}
				}
			} else {
				if runtimeErr == nil && (runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod") {
					_ = c.Close()
					cancel()
					_ = writeCaptureVideoStatus(p, settings, "unknown", "unknown", false, os.Getpid())
					return errors.New("game capture observer stopped because the managed profile or collection is no longer selected")
				}
				connectErr = errors.New("managed OBS output state is unconfirmed")
			}
			_ = c.Close()
		}
		cancel()
		if outputIdle {
			return writeCaptureVideoStatus(p, settings, "stopped", "unknown", false, os.Getpid())
		}
		if connectErr != nil {
			target = 0
			audioReady = false
			idleKey = ""
			stability = gameStability{}
			failures++
			state, frames = "unknown", "unknown"
		} else {
			failures = 0
		}
		watching := failures < 3
		if err := writeCaptureVideoStatus(p, settings, state, frames, watching, os.Getpid()); err != nil {
			return err
		}
		if !watching {
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
// argv. A separate lifetime lock avoids duplicate observers and never takes the
// stream-control lock held by the initiating Start/Test operation.
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
	deadline := time.NewTimer(5 * time.Second)
	defer deadline.Stop()
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	for {
		record, fresh := readCaptureVideoRecord(p)
		if fresh && record.Watching && (record.State == "game" || record.State == "idle") && captureWatchOwner(record.PID, executable) {
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
