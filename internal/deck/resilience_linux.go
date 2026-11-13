//go:build linux

package deck

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"syscall"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type resilienceOBS struct{ client *automation.Client }

func (c resilienceOBS) Close() error { return c.client.Close() }
func (c resilienceOBS) GuardMedia(ctx context.Context, p Paths) error {
	return MediaStorageGuard(ctx, p, c.client)
}
func (c resilienceOBS) Observe(ctx context.Context) (resilienceObservation, error) {
	runtime, err := c.client.RuntimeStatus(ctx)
	if err != nil {
		return resilienceObservation{}, err
	}
	stream, err := c.client.StreamStatus(ctx)
	if err != nil {
		return resilienceObservation{}, err
	}
	replay, err := c.client.ReplayActive(ctx)
	if err != nil {
		return resilienceObservation{}, err
	}
	return resilienceObservation{Managed: runtime.Profile == "OBSGod" && runtime.Collection == "OBSGod", Active: stream.Active || stream.Reconnecting || runtime.Recording || replay}, nil
}
func (c resilienceOBS) Rebind(ctx context.Context, settings Settings, route AudioRouting) (bool, error) {
	changed, err := c.client.RebindAudioInput(ctx, GameAudio, "pulse_output_capture", route.OutputMonitor)
	if err != nil {
		return changed, err
	}
	if settings.Microphone {
		microphoneChanged, err := c.client.RebindAudioInput(ctx, MicAudio, "pulse_input_capture", route.MicrophoneDevice)
		return changed || microphoneChanged, err
	}
	return changed, nil
}

// WatchResilience maintains selected audio routes only; it never launches OBS,
// changes video mode, alters gain/mute, or starts/restarts any output. The media
// guard may finalize recording/replay at their configured disk reserve, while
// preserving a live broadcast and every existing clip.
// A lost control connection is retried at most three times with bounded delays.
func WatchResilience(ctx context.Context, p Paths) error {
	return watchResilienceWith(ctx, p, resilienceDeps{load: Load,
		connect: func(ctx context.Context, secret Secrets) (resilienceConnection, error) {
			client, err := connect(ctx, secret, 600*time.Millisecond)
			if err != nil {
				return nil, err
			}
			return resilienceOBS{client: client}, nil
		}, discover: DiscoverAudio, interval: resilienceInterval,
	})
}

// StartResilienceWatch is called after an explicit output action or an explicit
// recovery retry. The detached child verifies current managed output before any
// route mutation. Its separate lifetime lease coalesces duplicate launchers.
func StartResilienceWatch(p Paths) error {
	if _, _, err := Load(p); err != nil {
		return err
	}
	executable, err := captureWatchExecutable()
	if err != nil {
		return errors.New("could not locate the audio recovery executable")
	}
	probe, done := context.WithTimeout(context.Background(), 100*time.Millisecond)
	unlock, lockErr := Lock(probe, resiliencePaths(p))
	done()
	if lockErr != nil {
		record, fresh := readResilienceRecord(p)
		if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
			return nil
		}
		return errors.New("the existing audio observer has not confirmed fresh state; inspect audio diagnostics before retrying")
	}
	unlock()
	output, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		return errors.New("could not prepare the audio recovery observer")
	}
	defer output.Close()
	command := exec.Command(executable, "deck", "resilience-watch")
	command.Env = sessionEnvironment()
	command.Stdin = nil
	command.Stdout, command.Stderr = output, output
	command.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := command.Start(); err != nil {
		return errors.New("could not launch the audio recovery observer")
	}
	exited := make(chan struct{}, 1)
	go func() { _ = command.Wait(); exited <- struct{}{} }()
	deadline := time.NewTimer(5 * time.Second)
	defer deadline.Stop()
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	for {
		record, fresh := readResilienceRecord(p)
		if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
			return nil
		}
		select {
		case <-exited:
			record, fresh := readResilienceRecord(p)
			if fresh && record.Watching && captureWatchOwner(record.PID, executable) {
				return nil
			}
			return errors.New("the audio observer exited before confirming active managed output; it did not restart output")
		case <-deadline.C:
			return errors.New("the audio observer has not confirmed fresh state; output was not stopped or restarted")
		case <-ticker.C:
		}
	}
}
