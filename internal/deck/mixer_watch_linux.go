//go:build linux

package deck

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"syscall"
	"time"
)

func WatchMixer(ctx context.Context, p Paths) error {
	return watchMixerWith(ctx, p, muteTalkInput, os.Getpid(), mixerTalkInterval)
}
func StartMixerWatch(p Paths) error {
	executable, err := captureWatchExecutable()
	if err != nil {
		return errors.New("could not locate the microphone privacy observer")
	}
	if r, fresh := readMixerWatchRecord(p); fresh && captureWatchOwner(r.PID, executable) {
		return nil
	}
	output, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		return errors.New("could not prepare the microphone privacy observer")
	}
	defer output.Close()
	command := exec.Command(executable, "deck", "mixer-watch")
	command.Env = sessionEnvironment()
	command.Stdin = nil
	command.Stdout, command.Stderr = output, output
	command.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err = command.Start(); err != nil {
		return errors.New("could not launch the microphone privacy observer")
	}
	exited := make(chan struct{}, 1)
	go func() { _ = command.Wait(); exited <- struct{}{} }()
	deadline := time.NewTimer(650 * time.Millisecond)
	defer deadline.Stop()
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		if r, fresh := readMixerWatchRecord(p); fresh && captureWatchOwner(r.PID, executable) {
			return nil
		}
		select {
		case <-exited:
			return errors.New("microphone privacy observer exited; microphone stayed muted")
		case <-deadline.C:
			return errors.New("microphone privacy observer did not become ready; microphone stayed muted")
		case <-ticker.C:
		}
	}
}

func mixerGuardianAlive(p Paths) bool {
	executable, err := captureWatchExecutable()
	if err != nil {
		return false
	}
	record, fresh := readMixerWatchRecord(p)
	return fresh && captureWatchOwner(record.PID, executable)
}
