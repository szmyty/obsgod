package deck

import (
	"context"
	"net"
	"os"
	"path/filepath"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type audioReceipt struct {
	Status   AudioStatus `json:"status"`
	Observed time.Time   `json:"observed"`
}

func saveAudioStatus(p Paths, status AudioStatus) {
	_ = writeJSON(filepath.Join(p.State, "audio-status.json"), audioReceipt{Status: status, Observed: time.Now().UTC()})
}
func readAudioStatus(p Paths) *AudioStatus {
	var receipt audioReceipt
	path := filepath.Join(p.State, "audio-status.json")
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 4096 || readJSON(path, &receipt) != nil || receipt.Observed.IsZero() {
		return nil
	}
	age := time.Since(receipt.Observed)
	if age > 5*time.Second || age < -time.Second {
		receipt.Status.State = "unknown"
		receipt.Status.OutputAvailable = false
		receipt.Status.MicrophoneAvailable = false
		receipt.Status.Signal = "unmeasured"
		receipt.Status.Message = "Last configured audio route; current sound is unmeasured. Make a local test clip or run diagnostics to check audio"
	}
	return &receipt.Status
}

func ensureAudio(ctx context.Context, c *automation.Client, p Paths, s Settings) error {
	logEvent(p, "audio.discovering")
	pref, err := MixerSettings(p, s)
	if err != nil {
		return err
	}
	route, err := discoverMixerAudio(ctx, p, s)
	if err == nil && pref.MicrophoneEnabled && route.MicrophoneDevice != "" {
		if actual, actualErr := c.AudioInputDevice(ctx, MicAudio, "pulse_input_capture"); actualErr == nil && actual != route.MicrophoneDevice {
			if muteErr := c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture"); muteErr != nil {
				return muteErr
			}
			pref = latchMixerMute(p, pref, "microphone-changed")
			route.MicrophoneStreamMuted = true
		}
	}
	status := safeAudioStatus(route, err)
	saveAudioStatus(p, status)
	if err != nil {
		logEvent(p, "audio.unavailable")
		return err
	}
	sources := []struct{ name, kind, device string }{{GameAudio, "pulse_output_capture", route.OutputMonitor}}
	if pref.MicrophoneEnabled && route.MicrophoneDevice != "" {
		sources = append(sources, struct{ name, kind, device string }{MicAudio, "pulse_input_capture", route.MicrophoneDevice})
	}
	keep := map[string]bool{}
	for _, source := range sources {
		if source.name == MicAudio {
			err = c.EnsureMutedPulseInput(ctx, LiveScene, source.name, source.device)
		} else {
			err = c.EnsureInput(ctx, LiveScene, source.name, source.kind, map[string]any{"device_id": source.device})
		}
		if err == nil {
			for _, scene := range []string{LiveScene, GameScene, IdleScene} {
				if err = c.EnsureSceneItem(ctx, scene, source.name); err != nil {
					break
				}
				if err = c.SetSceneItemEnabledIfPresent(ctx, scene, source.name, true); err != nil {
					break
				}
			}
		}
		if err == nil {
			muted, gain := false, pref.GameGainPercent
			if source.name == MicAudio {
				muted, gain = pref.MicrophoneMuted || pref.PushToTalk, pref.MicrophoneGainPercent
			}
			_, err = c.ConfigureAudioInputPolicy(ctx, source.name, source.device, muted, gain)
		}
		if err != nil {
			status.State = "unavailable"
			status.Signal = "unknown"
			status.Message = "The selected audio route could not be verified inside OBS. Check audio diagnostics and the Steam/Flatpak audio connection"
			saveAudioStatus(p, status)
			logEvent(p, "audio.unavailable")
			return err
		}
		keep[source.name] = true
	}
	if !keep[MicAudio] {
		if err = c.MuteInputIfPresent(ctx, MicAudio, "pulse_input_capture"); err != nil {
			return err
		}
		if pref.MicrophoneEnabled {
			latchMixerMute(p, pref, "microphone-lost")
		}
	}
	if err = c.MuteOtherAudio(ctx, keep); err != nil {
		status.State = "unavailable"
		status.Signal = "unknown"
		status.Message = "The managed audio policy could not be confirmed; audio setup is incomplete"
		saveAudioStatus(p, status)
		logEvent(p, "audio.unavailable")
		return err
	}
	if status.OutputMuted {
		logEvent(p, "audio.system-muted")
	} else {
		logEvent(p, "audio.ready")
	}
	return nil
}

func measureAudio(ctx context.Context, p Paths, secret Secrets, duration time.Duration, record bool) *AudioStatus {
	status := readAudioStatus(p)
	if status == nil {
		status = &AudioStatus{State: "unknown", Message: "Audio route is unconfirmed", Signal: "unknown"}
	}
	cfg := automation.Config{Address: net.JoinHostPort("127.0.0.1", Port), Password: secret.OBSPassword, Timeout: 250 * time.Millisecond}
	signal, err := automation.ObserveAudioSignal(ctx, cfg, GameAudio, duration)
	status.Signal = signal.State
	if err != nil || signal.State == "unknown" {
		status.Signal = "unknown"
		status.Message = "OBS audio meters could not be observed; current sound is unconfirmed"
		if record {
			logEvent(p, "audio.meters-unavailable")
		}
	} else if signal.State == "signal" {
		status.Message = "OBS detected audio signal on the selected output monitor. Verify sound in the saved clip or on your channel"
		if record {
			logEvent(p, "audio.signal")
		}
	} else {
		status.Message = "No audio signal was detected during this short check. Play game sound and inspect the local clip; silence does not stop a stream"
		if record {
			logEvent(p, "audio.silent")
		}
	}
	if record {
		saveAudioStatus(p, *status)
	}
	return status
}
