package commands

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/deck"
)

func newDeckCommand() *coral.Command {
	root := &coral.Command{Use: "deck", Short: "Manage the optional Steam Deck streaming preview (JSON output)"}
	for _, name := range []string{"status", "doctor", "configure", "set-capture-mode", "start", "stop", "test-recording", "restart", "open-obs", "clear-logs"} {
		name := name
		cmd := &coral.Command{Use: name, Short: map[string]string{"status": "Read live output state without starting OBS", "doctor": "Diagnose installation, capture and OBS", "configure": "Save settings and key from JSON stdin, never argv", "start": "Capture Gaming Mode and wait for real stream output", "stop": "Stop streaming and confirm it stopped", "test-recording": "Save a ten-second local clip without broadcasting", "restart": "Close idle managed OBS to apply saved settings", "open-obs": "Open the isolated OBS window visibly for Desktop recovery without starting output"}[name], Args: coral.NoArgs}
		cmd.RunE = func(cmd *coral.Command, _ []string) error {
			ctx, cancel := context.WithTimeout(cmd.Context(), 75*time.Second)
			defer cancel()
			paths, e := deck.UserPaths()
			if e != nil {
				return e
			}
			var result deck.Result
			if name != "status" && name != "clear-logs" {
				deck.RecordOperation(paths, name)
			}
			if name == "clear-logs" {
				e = deck.ClearDiagnostics(ctx, paths)
				result = deck.Status(ctx, paths)
			} else if name == "status" {
				result = deck.Status(ctx, paths)
			} else if name == "doctor" {
				result = deck.Doctor(ctx, paths)
			} else {
				unlock, err := deck.Lock(ctx, paths)
				if err != nil {
					e = errors.New("another OBSGod operation is busy; wait and try again")
				} else {
					defer unlock()
					switch name {
					case "configure":
						state := deck.Status(ctx, paths)
						if state.Connected || state.State == "unknown" {
							e = errors.New("close managed OBS with Restart OBS before changing settings")
							break
						}
						var settings deck.Settings
						settings, e = deck.Configure(paths, cmd.InOrStdin())
						result = deck.Result{OK: e == nil, Configured: e == nil, State: "stopped", Message: "Settings saved on this device", Settings: &settings}
					case "start":
						result, e = deck.Start(ctx, paths)
					case "set-capture-mode":
						result, e = deck.SetCaptureMode(ctx, paths, cmd.InOrStdin())
					case "stop":
						result, e = deck.Stop(ctx, paths)
					case "test-recording":
						result, e = deck.TestRecording(ctx, paths)
					case "open-obs":
						result, e = deck.OpenOBS(ctx, paths)
					case "restart":
						result, e = deck.Restart(ctx, paths)
					}
				}
			}
			if name != "status" && name != "doctor" && name != "clear-logs" {
				// Action failure is separate from observed output. Even cancellation must
				// return a fresh conservative snapshot so the panel can offer recovery Stop.
				snapshotCtx, done := context.WithTimeout(context.Background(), 2*time.Second)
				snapshot := deck.Status(snapshotCtx, paths)
				done()
				snapshot.OK = result.OK && e == nil
				if result.Message != "" {
					snapshot.Message = result.Message
				}
				snapshot.RecordingPath = result.RecordingPath
				result = snapshot
			}
			if e != nil {
				result.OK = false
				result.Message = e.Error()
			}

			if name != "status" && name != "clear-logs" {
				deck.RecordOutcome(paths, e, result.OK)
			}
			result.Diagnostics = deck.ReadDiagnostics(paths)
			if err := json.NewEncoder(cmd.OutOrStdout()).Encode(result); err != nil {
				return err
			}
			if e != nil {
				return errors.New("Steam Deck operation failed (see JSON result)")
			}
			if !result.OK {
				return errors.New("Steam Deck diagnostic failed (see JSON result)")
			}
			return nil
		}
		root.AddCommand(cmd)
	}
	return root
}
