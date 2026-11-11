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
	"start.requested":          "Start streaming requested. Open a game in Gaming Mode first.",
	"stop.requested":           "Stop streaming / cancel requested.",
	"test-recording.requested": "Local test requested. Open a game first; this does not broadcast and the streaming dot stays red.",
	"restart.requested":        "Close idle managed OBS requested.",
	"configure.requested":      "Saving local settings.",
	"doctor.requested":         "Checking dependencies, capture and OBS.",
	"operation.succeeded":      "Operation completed.",
	"operation.failed":         "Operation failed. The full result is displayed above this console.",
	"operation.cancelled":      "Operation cancelled; checking or cleaning up output.",
	"operation.timeout":        "Operation exceeded its time limit; output must be checked before retrying.",
	"obs.request-failed":       "OBS request failed with status code",
	"obs.conflict":             "Port 4457 is already in use or OBSGod credentials do not match; stop the conflicting instance in Desktop Mode.",
	"obs.unmanaged":            "The OBS instance is not using the managed OBSGod profile; refusing to change it.",
	"settings.missing":         "Complete OBSGod Desktop setup first.",
	"dependencies.checking":    "Checking user-installed OBS and GStreamer Flatpaks.",
	"dependencies.missing":     "OBS or GStreamer is unavailable. Run Install / check OBS in Desktop setup.",
	"obs.connecting":           "Connecting to the managed OBS instance on localhost.",
	"obs.launching":            "Launching OBS with the isolated OBSGod profile.",
	"obs.waiting":              "Waiting for OBS and its authenticated control connection.",
	"obs.ready":                "Managed OBS is ready.",
	"obs.exited":               "OBS exited before becoming ready. Exit code",
	"obs.timeout":              "OBS startup timed out before its control connection became ready. Check OBS in Desktop Mode.",
	"session.no-display":       "No graphical display was found for the current Steam session. Restart Gaming Mode before retrying.",
	"capture.checking":         "Checking for the Gamescope capture feed. A game must be running in Gaming Mode.",
	"capture.unavailable":      "Gamescope capture is unavailable. Open a game in Gaming Mode before retrying.",
	"capture.configuring":      "Preparing game video and the selected audio sources.",
	"capture.waiting":          "Waiting for visible game frames.",
	"capture.ready":            "Visible game frames confirmed.",
	"capture.blank":            "No visible game frames arrived. Open a game with a visible picture and retry. No new broadcast was started.",
	"stream.connecting":        "Connecting OBS to the configured streaming server.",
	"stream.ready":             "OBS is sending streaming output. Check picture and sound on your channel.",
	"stream.failed-stopped":    "Streaming failed to become healthy; OBS confirmed it stopped.",
	"stream.unconfirmed":       "Streaming and stop could not be confirmed. Use Stop streaming or inspect OBS immediately.",
	"stream.stopped":           "OBS confirmed streaming is stopped.",
	"recording.starting":       "Starting the local recording and waiting for encoded output.",
	"recording.running":        "Recording ten seconds locally. Nothing is being broadcast.",
	"recording.saved":          "Local test clip saved to Videos/OBSGod. Watch it before broadcasting.",
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
		case "obs.exited", "obs.timeout", "obs.request-failed", "obs.conflict", "obs.unmanaged", "settings.missing", "operation.failed", "operation.timeout", "capture.blank", "capture.unavailable", "stream.unconfirmed", "stream.failed-stopped", "dependencies.missing", "session.no-display":
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
