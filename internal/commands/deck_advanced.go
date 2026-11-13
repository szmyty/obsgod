package commands

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"time"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/deck"
)

func addDeckAdvancedCommands(root *coral.Command) {
	root.AddCommand(&coral.Command{Use: "resilience-watch", Hidden: true, Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		p, err := deck.UserPaths()
		if err != nil {
			return err
		}
		return deck.WatchResilience(cmd.Context(), p)
	}})
	for _, name := range []string{"stream-profiles", "set-idle-media", "media", "stream-health", "retry-recovery"} {
		name := name
		command := &coral.Command{Use: name, Args: coral.NoArgs, Short: map[string]string{
			"stream-profiles": "Preview, validate, save, apply or export stream profiles using JSON stdin",
			"set-idle-media":  "Import local between-game media with rights acknowledgement using JSON stdin",
			"media":           "Manage local recording, replay, clips and storage using JSON stdin; never broadcasts",
			"stream-health":   "Read a bounded local OBS health sample; provider reception remains unknown",
			"retry-recovery":  "Retry bounded audio recovery for already-active managed output; never starts output",
		}[name]}
		if name == "stream-profiles" {
			for _, field := range []string{"width", "height", "bitrate", "fps"} {
				command.Flags().Int(field, 0, "Override JSON/environment profile "+field+" for this action")
			}
			for _, field := range []string{"encoder", "capture-mode"} {
				command.Flags().String(field, "", "Override JSON/environment profile "+field+" for this action")
			}
			command.Flags().Bool("microphone", false, "Override profile microphone preference; use --microphone=false to disable")
		}
		command.RunE = func(cmd *coral.Command, _ []string) error {
			ctx, cancel := context.WithTimeout(cmd.Context(), 75*time.Second)
			defer cancel()
			p, err := deck.UserPaths()
			if err != nil {
				return err
			}
			var result any
			if name == "stream-health" {
				result = deck.ObserveStreamHealth(ctx, p)
			} else if name == "retry-recovery" {
				err = deck.StartResilienceWatch(p)
				result = map[string]any{"ok": err == nil, "message": "Bounded recovery requested for existing output; inspect fresh recovery status", "resilience": deck.ReadResilienceStatus(p)}
			} else {
				unlock, lockErr := deck.Lock(ctx, p)
				if lockErr != nil {
					err = errors.New("another managed OBS operation is busy; wait or cancel it")
				} else {
					defer unlock()
					switch name {
					case "stream-profiles":
						var reader io.Reader
						reader, err = streamProfileFlagInput(cmd)
						if err == nil {
							result, err = deck.ManageStreamProfiles(ctx, p, reader)
						}
					case "set-idle-media":
						result, err = deck.ConfigureIdle(ctx, p, cmd.InOrStdin())
					case "media":
						result, err = runDeckMedia(ctx, p, cmd.InOrStdin())
					}
				}
			}
			// Normalize only the command result, never a cached output snapshot.
			data, marshalErr := json.Marshal(result)
			if marshalErr != nil {
				return marshalErr
			}
			out := map[string]any{}
			if string(data) != "null" {
				if marshalErr = json.Unmarshal(data, &out); marshalErr != nil {
					return marshalErr
				}
			}
			if err != nil {
				out["ok"], out["message"] = false, err.Error()
			}
			if encodeErr := json.NewEncoder(cmd.OutOrStdout()).Encode(out); encodeErr != nil {
				return encodeErr
			}
			if err != nil || out["ok"] != true {
				return errors.New("local operation was not confirmed (see JSON result)")
			}
			return nil
		}
		root.AddCommand(command)
	}
}

func streamProfileFlagInput(cmd *coral.Command) (io.Reader, error) {
	changed := false
	for _, field := range []string{"width", "height", "bitrate", "fps", "encoder", "capture-mode", "microphone"} {
		changed = changed || cmd.Flags().Changed(field)
	}
	if !changed {
		return cmd.InOrStdin(), nil
	}
	var input deck.StreamProfileRequest
	decoder := json.NewDecoder(io.LimitReader(cmd.InOrStdin(), 16385))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&input) != nil {
		return nil, errors.New("provide one profile request as JSON stdin before applying flags")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return nil, errors.New("profile request must be exactly one JSON object")
	}
	if input.Overrides == nil {
		input.Overrides = &deck.StreamProfileOverrides{}
	}
	for _, item := range []struct {
		name  string
		value **int
	}{{"width", &input.Overrides.Width}, {"height", &input.Overrides.Height}, {"bitrate", &input.Overrides.Bitrate}, {"fps", &input.Overrides.FPS}} {
		if cmd.Flags().Changed(item.name) {
			value, _ := cmd.Flags().GetInt(item.name)
			*item.value = &value
		}
	}
	if cmd.Flags().Changed("encoder") {
		value, _ := cmd.Flags().GetString("encoder")
		input.Overrides.Encoder = &value
	}
	if cmd.Flags().Changed("capture-mode") {
		value, _ := cmd.Flags().GetString("capture-mode")
		input.Overrides.CaptureMode = &value
	}
	if cmd.Flags().Changed("microphone") {
		value, _ := cmd.Flags().GetBool("microphone")
		input.Overrides.Microphone = &value
	}
	data, err := json.Marshal(input)
	return bytes.NewReader(data), err
}

func runDeckMedia(ctx context.Context, p deck.Paths, reader io.Reader) (any, error) {
	decoder := json.NewDecoder(io.LimitReader(reader, 16385))
	var request map[string]json.RawMessage
	if decoder.Decode(&request) != nil || request == nil {
		return nil, errors.New("media requires one JSON object")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return nil, errors.New("media requires exactly one JSON object")
	}
	var action string
	if json.Unmarshal(request["action"], &action) != nil {
		return nil, errors.New("choose a local media action")
	}
	delete(request, "action")
	payload, _ := json.Marshal(request)
	remaining := bytes.NewReader(payload)
	switch action {
	case "status":
		if len(request) != 0 {
			return nil, errors.New("media status does not accept extra settings")
		}
		snapshot := deck.MediaStatus(ctx, p)
		return map[string]any{"ok": snapshot.Known, "message": snapshot.Message, "media": snapshot, "preferences": snapshot.Preferences}, nil
	case "list":
		if len(request) != 0 {
			return nil, errors.New("clip list does not accept extra settings")
		}
		return deck.MediaLibrary(p)
	case "configure":
		var preferences json.RawMessage
		if value, ok := request["preferences"]; ok && len(request) == 1 {
			preferences = value
		} else {
			return nil, errors.New("send recording preferences in the preferences object")
		}
		settings, err := deck.ConfigureRecording(ctx, p, bytes.NewReader(preferences))
		return map[string]any{"ok": err == nil, "preferences": settings, "message": "Local recording preferences saved; no output was started"}, err
	case "export":
		return deck.ExportClip(ctx, p, remaining)
	case "prune":
		return deck.PruneClips(ctx, p, remaining)
	case "record-start", "record-stop", "record-cancel", "replay-start", "replay-stop", "replay-save":
		if len(request) != 0 {
			return nil, errors.New("output actions do not accept extra settings")
		}
		if action == "record-start" || action == "replay-start" {
			state := deck.Status(ctx, p)
			if state.Process == "absent" && state.OutputKnown {
				if _, err := deck.ApplyBoundGameProfile(ctx, p); err != nil {
					return nil, err
				}
			}
		}
		result, err := deck.MediaAction(ctx, p, action)
		if err == nil && (action == "record-start" || action == "replay-start") {
			_ = deck.StartResilienceWatch(p)
		}
		return result, err
	default:
		return nil, errors.New("choose status, list, configure, export, prune, record-start, record-stop, record-cancel, replay-start, replay-stop or replay-save")
	}
}
