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
	for _, name := range []string{"status", "doctor", "configure", "start", "stop", "test-recording", "restart"} {
		name := name
		cmd := &coral.Command{Use: name, Short: map[string]string{"status": "Read live output state without starting OBS", "doctor": "Diagnose installation, capture and OBS", "configure": "Save settings and key from JSON stdin, never argv", "start": "Capture Gaming Mode and wait for real stream output", "stop": "Stop streaming and confirm it stopped", "test-recording": "Save a ten-second local clip without broadcasting", "restart": "Close idle managed OBS to apply saved settings"}[name], Args: coral.NoArgs}
		cmd.RunE = func(cmd *coral.Command, _ []string) error {
			ctx, cancel := context.WithTimeout(cmd.Context(), 75*time.Second)
			defer cancel()
			paths, e := deck.UserPaths()
			if e != nil {
				return e
			}
			var result deck.Result
			if name == "status" {
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
					case "stop":
						result, e = deck.Stop(ctx, paths)
					case "test-recording":
						result, e = deck.TestRecording(ctx, paths)
					case "restart":
						result, e = deck.Restart(ctx, paths)
					}
				}
			}
			if e != nil {
				result = deck.Result{OK: false, State: "error", Message: e.Error()}
			}
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
