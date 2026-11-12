package deck

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
)

// SetCaptureMode changes only local capture preferences. It never starts or
// stops output and does not rewrite the running OBS profile. The next explicit
// Start/Test configures the selected capture path after checking output again.
func SetCaptureMode(ctx context.Context, p Paths, reader io.Reader) (Result, error) {
	var input struct {
		Mode string `json:"capture_mode"`
	}
	d := json.NewDecoder(io.LimitReader(reader, 1025))
	d.DisallowUnknownFields()
	if d.Decode(&input) != nil || (input.Mode != "screen" && input.Mode != "game") {
		return Result{}, errors.New("choose screen or game capture")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return Result{}, errors.New("capture mode must be one JSON object")
	}
	s, _, err := Load(p)
	if err != nil {
		return Result{}, err
	}
	state := Status(ctx, p)
	if !state.OutputKnown || state.Stream.Active || state.Recording {
		return Result{}, errors.New("stop streaming and recording and confirm idle status before changing capture mode")
	}
	s.CaptureMode = input.Mode
	data, err := json.Marshal(s)
	if err != nil {
		return Result{}, err
	}
	// Configure preserves the saved key/password and atomically binds the new
	// settings pair. Only app preferences change; no OBS scene or output call.
	if _, err = Configure(p, bytes.NewReader(data)); err != nil {
		return Result{}, err
	}
	return Result{OK: true, Configured: true, State: "stopped", Settings: &s, Message: "Capture mode saved; it applies to the next explicit stream or local test"}, nil
}
