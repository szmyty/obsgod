package automation

import (
	"context"
	"encoding/json"
	"errors"
	"math"

	"github.com/andreykaipov/goobs/api/requests/inputs"
)

// MixerInputState describes an observed input, never the system mixer. Device
// identifiers are kept out of this public projection and diagnostic errors.
type MixerInputState struct {
	Muted       bool    `json:"muted"`
	GainPercent float64 `json:"gain_percent"`
}

func (c *Client) MixerInput(ctx context.Context, name string) (MixerInputState, error) {
	var result MixerInputState
	mute, err := request(ctx, "GetInputMute", func() (*inputs.GetInputMuteResponse, error) {
		return c.obs.Inputs.GetInputMute(inputs.NewGetInputMuteParams().WithInputName(name))
	})
	if err != nil {
		return result, err
	}
	var raw map[string]json.RawMessage
	var muted *bool
	if json.Unmarshal(mute.GetRaw(), &raw) != nil || json.Unmarshal(raw["inputMuted"], &muted) != nil || muted == nil {
		return result, errors.New("OBS did not confirm the input mute state")
	}
	volume, err := request(ctx, "GetInputVolume", func() (*inputs.GetInputVolumeResponse, error) {
		return c.obs.Inputs.GetInputVolume(inputs.NewGetInputVolumeParams().WithInputName(name))
	})
	if err != nil {
		return result, err
	}
	var mul *float64
	if json.Unmarshal(volume.GetRaw(), &raw) != nil || json.Unmarshal(raw["inputVolumeMul"], &mul) != nil || mul == nil || math.IsNaN(*mul) || math.IsInf(*mul, 0) || *mul < 0 {
		return result, errors.New("OBS did not confirm the input gain")
	}
	return MixerInputState{Muted: *muted, GainPercent: *mul * 100}, nil
}

// SetMixerInput only changes the caller's named OBS source. Mute is applied
// before gain and unmute last. A request acknowledgement is not confirmation.
func (c *Client) SetMixerInput(ctx context.Context, name string, muted *bool, gain *float64) (MixerInputState, error) {
	if name == "" || (gain != nil && (math.IsNaN(*gain) || math.IsInf(*gain, 0) || *gain < 0 || *gain > 200)) {
		return MixerInputState{}, errors.New("input gain must be 0–200 percent")
	}
	if muted != nil && *muted {
		if err := c.SetInputMuted(ctx, name, true); err != nil {
			return MixerInputState{}, err
		}
	}
	if gain != nil {
		_, err := request(ctx, "SetInputVolume", func() (*inputs.SetInputVolumeResponse, error) {
			return c.obs.Inputs.SetInputVolume(inputs.NewSetInputVolumeParams().WithInputName(name).WithInputVolumeMul(*gain / 100))
		})
		if err != nil {
			return MixerInputState{}, err
		}
	}
	if muted != nil && !*muted {
		if err := c.SetInputMuted(ctx, name, false); err != nil {
			return MixerInputState{}, err
		}
	}
	result, err := c.MixerInput(ctx, name)
	if err != nil {
		return result, err
	}
	if (muted != nil && result.Muted != *muted) || (gain != nil && math.Abs(result.GainPercent-*gain) > .1) {
		return result, errors.New("OBS did not confirm the requested input mixer state")
	}
	return result, nil
}

// EnsureMutedPulseInput creates a microphone with its scene item disabled and
// mutes it before the caller makes it visible. Existing owned types must match.
func (c *Client) EnsureMutedPulseInput(ctx context.Context, scene, name, device string) error {
	list, err := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if err != nil {
		return err
	}
	for _, input := range list.Inputs {
		if input.InputName == name {
			if input.InputKind != "pulse_input_capture" {
				return errors.New("managed microphone has an unexpected input type")
			}
			muted := true
			if _, err = c.SetMixerInput(ctx, name, &muted, nil); err != nil {
				return err
			}
			_, err = request(ctx, "SetInputSettings", func() (*inputs.SetInputSettingsResponse, error) {
				return c.obs.Inputs.SetInputSettings(inputs.NewSetInputSettingsParams().WithInputName(name).WithInputSettings(map[string]any{"device_id": device}).WithOverlay(true))
			})
			return err
		}
	}
	_, err = request(ctx, "CreateInput", func() (*inputs.CreateInputResponse, error) {
		return c.obs.Inputs.CreateInput(inputs.NewCreateInputParams().WithSceneName(scene).WithInputName(name).WithInputKind("pulse_input_capture").WithInputSettings(map[string]any{"device_id": device}).WithSceneItemEnabled(false))
	})
	if err != nil {
		return err
	}
	muted := true
	_, err = c.SetMixerInput(ctx, name, &muted, nil)
	return err
}

func (c *Client) MuteInputIfPresent(ctx context.Context, name, kind string) error {
	list, err := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if err != nil {
		return err
	}
	for _, input := range list.Inputs {
		if input.InputName == name {
			if input.InputKind != kind {
				return errors.New("managed audio input has an unexpected type")
			}
			muted := true
			_, err := c.SetMixerInput(ctx, name, &muted, nil)
			return err
		}
	}
	return nil
}

// AudioInputDevice is for private application route comparisons, not diagnostics.
func (c *Client) AudioInputDevice(ctx context.Context, name, kind string) (string, error) {
	r, err := request(ctx, "GetInputSettings", func() (*inputs.GetInputSettingsResponse, error) {
		return c.obs.Inputs.GetInputSettings(inputs.NewGetInputSettingsParams().WithInputName(name))
	})
	if err != nil {
		return "", err
	}
	device, ok := r.InputSettings["device_id"].(string)
	if r.InputKind != kind || !ok || device == "" {
		return "", errors.New("OBS audio route is unconfirmed")
	}
	return device, nil
}
