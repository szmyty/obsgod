package automation

import (
	"context"
	"errors"
	"strings"

	"github.com/andreykaipov/goobs/api/requests/inputs"
)

// RebindAudioInput moves an existing, caller-owned PulseAudio input to a proven
// device. Recovery changes only device_id: OBS mute, gain, tracks and monitoring
// are the user's current mixer policy and must survive a headphone reconnect.
// It never creates a missing input or chooses an alternate device. The caller
// must verify managed ownership and active output before invoking it.
func (c *Client) RebindAudioInput(ctx context.Context, name, kind, device string) (bool, error) {
	if name == "" || device == "" || (kind != "pulse_input_capture" && kind != "pulse_output_capture") {
		return false, errors.New("audio recovery requires an existing PulseAudio source and selected device")
	}
	if kind == "pulse_input_capture" && strings.HasSuffix(device, ".monitor") {
		return false, errors.New("an output monitor cannot be selected as a microphone")
	}
	settings, err := request(ctx, "GetInputSettings", func() (*inputs.GetInputSettingsResponse, error) {
		return c.obs.Inputs.GetInputSettings(inputs.NewGetInputSettingsParams().WithInputName(name))
	})
	if err != nil {
		return false, err
	}
	if settings.InputKind != kind {
		return false, errors.New("audio recovery refused an unexpected or unconfirmed input type")
	}
	properties, err := request(ctx, "GetInputPropertiesListPropertyItems", func() (*inputs.GetInputPropertiesListPropertyItemsResponse, error) {
		return c.obs.Inputs.GetInputPropertiesListPropertyItems(inputs.NewGetInputPropertiesListPropertyItemsParams().WithInputName(name).WithPropertyName("device_id"))
	})
	if err != nil {
		return false, err
	}
	available := false
	for _, item := range properties.PropertyItems {
		if item != nil && item.ItemEnabled && item.ItemValue == device {
			available = true
			break
		}
	}
	if !available {
		return false, errors.New("the selected audio device is not visible inside OBS; no alternate route was guessed")
	}
	if settings.InputSettings["device_id"] == device {
		return false, nil
	}
	_, err = request(ctx, "SetInputSettings", func() (*inputs.SetInputSettingsResponse, error) {
		return c.obs.Inputs.SetInputSettings(inputs.NewSetInputSettingsParams().WithInputName(name).WithInputSettings(map[string]any{"device_id": device}).WithOverlay(true))
	})
	if err != nil {
		return false, err
	}
	observed, err := request(ctx, "GetInputSettings", func() (*inputs.GetInputSettingsResponse, error) {
		return c.obs.Inputs.GetInputSettings(inputs.NewGetInputSettingsParams().WithInputName(name))
	})
	if err != nil {
		return false, err
	}
	if observed.InputKind != kind || observed.InputSettings["device_id"] != device {
		return false, errors.New("OBS did not confirm the changed audio route; inspect the managed audio settings")
	}
	return true, nil
}
