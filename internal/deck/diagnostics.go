package deck

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

// Only event identifiers and numeric OBS/exit codes reach disk. Never store
// arbitrary errors, settings, subprocess output, URLs or authentication data.
var diagnosticMessages = map[string]string{
	"start.requested":             "Start streaming requested. OBS control does not require a running game.",
	"stop.requested":              "Stop streaming / cancel requested.",
	"test-recording.requested":    "Local test requested. This does not broadcast; the streaming dot stays red. Usable capture is checked after OBS readiness.",
	"open-obs.requested":          "Open the managed OBS recovery window requested. No stream or recording is started.",
	"obs.ownership-unknown":       "An owned OBS process could not be identified safely. Inspect its existing window before launching another instance.",
	"obs.open-visible":            "Launching the isolated OBSGod profile visibly for Desktop recovery.",
	"restart.requested":           "Close idle managed OBS requested.",
	"configure.requested":         "Saving local settings.",
	"set-capture-mode.requested":  "Changing the next capture mode after confirming output is idle.",
	"doctor.requested":            "Checking dependencies, capture and OBS.",
	"operation.succeeded":         "Operation completed.",
	"operation.failed":            "Operation failed. Read the preceding events for the last completed step; the current result appears above the console.",
	"operation.cancelled":         "Operation cancelled; checking or cleaning up output.",
	"operation.timeout":           "Operation exceeded its time limit; output must be checked before retrying.",
	"obs.request-failed":          "OBS request failed with status code",
	"obs.conflict":                "Port 4457 is already in use or OBSGod credentials do not match; stop the conflicting instance in Desktop Mode.",
	"obs.unmanaged":               "The OBS instance is not using the managed OBSGod profile; refusing to change it.",
	"settings.missing":            "Complete OBSGod Desktop setup first.",
	"dependencies.checking":       "Checking user-installed OBS and GStreamer Flatpaks.",
	"dependencies.missing":        "OBS or GStreamer is unavailable. Run Install / check OBS in Desktop setup.",
	"obs.connecting":              "Connecting to the managed OBS instance on localhost.",
	"obs.launching":               "Launching OBS with the isolated OBSGod profile.",
	"obs.waiting":                 "Waiting for OBS and its authenticated control connection.",
	"obs.listener-unavailable":    "OBS did not expose its local control listener. Check launch/display failures, recovery dialogs and the enabled built-in WebSocket server.",
	"obs.authentication-waiting":  "The control port is open but authenticated readiness was not confirmed. Check the managed instance and local credentials.",
	"obs.authentication-failed":   "OBS rejected the managed WebSocket password. No additional OBS instance was launched.",
	"obs.frontend-waiting":        "OBS authenticated but its frontend is not accepting requests. Check setup, recovery or plugin dialogs.",
	"obs.recovery-marker":         "A previous unclean OBS shutdown was detected. A recovery dialog may need attention in the managed OBS window; Safe Mode disables WebSockets and capture plugins.",
	"obs.ready":                   "Managed OBS is ready.",
	"obs.exited":                  "OBS exited before becoming ready. Exit code",
	"obs.timeout":                 "OBS startup reached its bounded time limit. Read the connection-stage event and open the managed OBS window in Desktop Mode.",
	"session.no-display":          "No X11 or Wayland display was found for the current Steam session. Restart Gaming Mode before retrying.",
	"capture.checking":            "Checking the current Gamescope capture feed independently of game presence.",
	"capture.unavailable":         "Gamescope capture is unavailable in this session. OBS control can work without a game; a clip or broadcast still needs usable frames.",
	"capture.configuring":         "Preparing captured video and the selected audio sources.",
	"capture.waiting":             "Waiting for usable rendered capture frames.",
	"capture.ready":               "Usable rendered capture frames confirmed.",
	"capture.blank":               "No usable rendered capture frames arrived. Check the current feed and visible content. No new broadcast was started.",
	"audio.discovering":           "Finding the current game or default system output monitor and selected microphone.",
	"audio.ready":                 "OBS verified the selected audio device, volume, track 1 and monitoring-off settings.",
	"audio.unavailable":           "Audio routing could not be verified. Check the SteamOS output and the device visible inside OBS.",
	"audio.system-muted":          "The selected system output is muted or has zero volume. OBSGod does not change system volume.",
	"audio.signal":                "OBS detected audio signal on the selected output. Verify sound in the saved clip or on your channel.",
	"audio.silent":                "No sound was detected during the short audio check. Play game audio and inspect the local clip; silence does not stop output.",
	"audio.meters-unavailable":    "OBS audio meters could not be observed. Current sound is unconfirmed.",
	"game.watch-unavailable":      "Automatic game transitions could not be started. Output remains active; inspect capture or use Stop.",
	"game.waiting":                "Showing the selected between-game screen while waiting for a verified game.",
	"game.ready":                  "App-filtered game capture is visible. Whole-screen fallback is disabled in game-only mode.",
	"game.capture-unavailable":    "App-filtered game capture is unavailable or unconfirmed. Showing the selected between-game screen.",
	"stream.connecting":           "Connecting OBS to the configured streaming server.",
	"stream.ready":                "OBS is sending streaming output. Check picture and sound on your channel.",
	"stream.existing-unconfirmed": "An existing stream did not confirm advancing output. It was preserved; inspect it or use Stop streaming.",
	"stream.failed-stopped":       "Streaming failed to become healthy; OBS confirmed it stopped.",
	"stream.unconfirmed":          "Streaming and stop could not be confirmed. Use Stop streaming or inspect OBS immediately.",
	"stream.stopped":              "OBS confirmed streaming is stopped.",
	"recording.starting":          "Starting the local recording and waiting for encoded output.",
	"recording.running":           "Recording ten seconds locally. Nothing is being broadcast.",
	"recording.saved":             "Local test clip saved to Videos/OBSGod. Watch it before broadcasting.",
}

type diagnosticEvent struct {
	Time   time.Time `json:"time"`
	Code   string    `json:"code"`
	Number int       `json:"number,omitempty"`
}

type DiagnosticEntry struct {
	Time    time.Time `json:"time"`
	Level   string    `json:"level"`
	Message string    `json:"message"`
}

const diagnosticLimit = 100

func diagnosticPaths(p Paths) Paths {
	p.State = filepath.Join(p.State, "diagnostics")
	return p
}

func readEvents(p Paths) []diagnosticEvent {
	var events []diagnosticEvent
	path := filepath.Join(diagnosticPaths(p).State, "events.json")
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 64*1024 {
		return events
	}
	if readJSON(path, &events) != nil {
		return nil
	}
	if len(events) > diagnosticLimit {
		events = events[len(events)-diagnosticLimit:]
	}
	return events
}

func ReadDiagnostics(p Paths) []DiagnosticEntry {
	entries := []DiagnosticEntry{}
	for _, event := range readEvents(p) {
		message, ok := diagnosticMessages[event.Code]
		if !ok || event.Time.IsZero() {
			continue
		}
		level := "info"
		switch event.Code {
		case "audio.unavailable", "audio.meters-unavailable", "game.watch-unavailable", "obs.listener-unavailable", "obs.authentication-waiting", "obs.authentication-failed", "obs.frontend-waiting", "obs.recovery-marker", "obs.exited", "obs.timeout", "obs.request-failed", "obs.conflict", "obs.unmanaged", "settings.missing", "operation.failed", "operation.timeout", "capture.blank", "capture.unavailable", "stream.unconfirmed", "stream.failed-stopped", "dependencies.missing", "session.no-display":
			level = "error"
		}
		if event.Code == "obs.exited" || event.Code == "obs.request-failed" {
			message = fmt.Sprintf("%s %d.", message, event.Number)
		}
		entries = append(entries, DiagnosticEntry{Time: event.Time, Level: level, Message: message})
	}
	return entries
}

func logEvent(p Paths, code string, number ...int) {
	if _, ok := diagnosticMessages[code]; !ok {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	unlock, err := Lock(ctx, diagnosticPaths(p))
	if err != nil {
		return // Diagnostics must never prevent Stop or change output behavior.
	}
	defer unlock()
	events := readEvents(p)
	event := diagnosticEvent{Time: time.Now().UTC(), Code: code}
	if len(number) > 0 {
		event.Number = number[0]
	}
	events = append(events, event)
	if len(events) > diagnosticLimit {
		events = events[len(events)-diagnosticLimit:]
	}
	_ = writeJSON(filepath.Join(diagnosticPaths(p).State, "events.json"), events)
}

func RecordOperation(p Paths, action string) { logEvent(p, action+".requested") }

func RecordOutcome(p Paths, err error, ok bool) {
	if errors.Is(err, context.Canceled) {
		logEvent(p, "operation.cancelled")
	} else if errors.Is(err, context.DeadlineExceeded) {
		logEvent(p, "operation.timeout")
	} else if err != nil || !ok {
		if err != nil {
			switch err.Error() {
			case "port 4457 is already in use or OBSGod credentials do not match; stop the conflicting instance in Desktop Mode":
				logEvent(p, "obs.conflict")
			case errUnmanaged.Error():
				logEvent(p, "obs.unmanaged")
			case "complete OBSGod Desktop setup first":
				logEvent(p, "settings.missing")
			}
		}
		var requestError *automation.RequestError
		if errors.As(err, &requestError) {
			logEvent(p, "obs.request-failed", requestError.Code)
		}
		logEvent(p, "operation.failed")
	} else {
		logEvent(p, "operation.succeeded")
	}
}

func ClearDiagnostics(ctx context.Context, p Paths) error {
	unlock, err := Lock(ctx, diagnosticPaths(p))
	if err != nil {
		return errors.New("could not clear the diagnostic console; try again")
	}
	defer unlock()
	return writeJSON(filepath.Join(diagnosticPaths(p).State, "events.json"), []diagnosticEvent{})
}
