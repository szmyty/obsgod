package automation

import (
	"context"
	"errors"
	"math"
	"time"

	"github.com/andreykaipov/goobs/api/events"
	"github.com/andreykaipov/goobs/api/events/subscriptions"
	"github.com/andreykaipov/goobs/api/requests/inputs"
	"github.com/andreykaipov/goobs/api/typedefs"
)

// InputAudioStatus contains routing facts only; no device names or signal data.
type InputAudioStatus struct {
	DeviceAvailable bool    `json:"device_available"`
	Muted           bool    `json:"muted"`
	Volume          float64 `json:"volume"`
	Track1          bool    `json:"track1"`
	Monitoring      string  `json:"monitoring"`
}

// ConfigureAudioInput repairs the intended mixer settings of a caller-owned
// input. The selected device must exist in OBS's own audio-server view. It does
// not change system volume or enable local monitoring (which can cause feedback).
func (c *Client) ConfigureAudioInput(ctx context.Context, name, device string) (InputAudioStatus, error) {
	var status InputAudioStatus
	properties, err := request(ctx, "GetInputPropertiesListPropertyItems", func() (*inputs.GetInputPropertiesListPropertyItemsResponse, error) {
		return c.obs.Inputs.GetInputPropertiesListPropertyItems(inputs.NewGetInputPropertiesListPropertyItemsParams().WithInputName(name).WithPropertyName("device_id"))
	})
	if err != nil {
		return status, err
	}
	for _, item := range properties.PropertyItems {
		if item != nil && item.ItemEnabled && item.ItemValue == device {
			status.DeviceAvailable = true
			break
		}
	}
	if !status.DeviceAvailable {
		return status, errors.New("the selected audio device is not visible inside OBS. Check the Steam/Flatpak audio connection and retry; no alternate device was guessed")
	}
	settings, err := request(ctx, "GetInputSettings", func() (*inputs.GetInputSettingsResponse, error) {
		return c.obs.Inputs.GetInputSettings(inputs.NewGetInputSettingsParams().WithInputName(name))
	})
	if err != nil {
		return status, err
	}
	if settings.InputSettings["device_id"] != device {
		return status, errors.New("OBS did not retain the selected audio device; audio routing is unconfirmed")
	}
	if err := c.SetInputMuted(ctx, name, false); err != nil {
		return status, err
	}
	_, err = request(ctx, "SetInputVolume", func() (*inputs.SetInputVolumeResponse, error) {
		return c.obs.Inputs.SetInputVolume(inputs.NewSetInputVolumeParams().WithInputName(name).WithInputVolumeMul(1))
	})
	if err != nil {
		return status, err
	}
	tracks := typedefs.InputAudioTracks{"1": true, "2": false, "3": false, "4": false, "5": false, "6": false}
	_, err = request(ctx, "SetInputAudioTracks", func() (*inputs.SetInputAudioTracksResponse, error) {
		return c.obs.Inputs.SetInputAudioTracks(inputs.NewSetInputAudioTracksParams().WithInputName(name).WithInputAudioTracks(&tracks))
	})
	if err != nil {
		return status, err
	}
	_, err = request(ctx, "SetInputAudioMonitorType", func() (*inputs.SetInputAudioMonitorTypeResponse, error) {
		return c.obs.Inputs.SetInputAudioMonitorType(inputs.NewSetInputAudioMonitorTypeParams().WithInputName(name).WithMonitorType("OBS_MONITORING_TYPE_NONE"))
	})
	if err != nil {
		return status, err
	}
	muted, err := request(ctx, "GetInputMute", func() (*inputs.GetInputMuteResponse, error) {
		return c.obs.Inputs.GetInputMute(inputs.NewGetInputMuteParams().WithInputName(name))
	})
	if err != nil {
		return status, err
	}
	status.Muted = muted.InputMuted
	volume, err := request(ctx, "GetInputVolume", func() (*inputs.GetInputVolumeResponse, error) {
		return c.obs.Inputs.GetInputVolume(inputs.NewGetInputVolumeParams().WithInputName(name))
	})
	if err != nil {
		return status, err
	}
	status.Volume = volume.InputVolumeMul
	observedTracks, err := request(ctx, "GetInputAudioTracks", func() (*inputs.GetInputAudioTracksResponse, error) {
		return c.obs.Inputs.GetInputAudioTracks(inputs.NewGetInputAudioTracksParams().WithInputName(name))
	})
	if err != nil {
		return status, err
	}
	if observedTracks.InputAudioTracks != nil {
		status.Track1 = (*observedTracks.InputAudioTracks)["1"]
	}
	monitoring, err := request(ctx, "GetInputAudioMonitorType", func() (*inputs.GetInputAudioMonitorTypeResponse, error) {
		return c.obs.Inputs.GetInputAudioMonitorType(inputs.NewGetInputAudioMonitorTypeParams().WithInputName(name))
	})
	if err != nil {
		return status, err
	}
	status.Monitoring = monitoring.MonitorType
	if status.Muted || math.Abs(status.Volume-1) > 0.001 || !status.Track1 || status.Monitoring != "OBS_MONITORING_TYPE_NONE" {
		return status, errors.New("OBS audio mixer routing did not match the requested unmuted track 1 output; audio is unconfirmed")
	}
	return status, nil
}

// AudioSignal is a short observation, not proof of viewer-side audio reception.
type AudioSignal struct {
	State   string  `json:"state"`
	Samples int     `json:"samples"`
	Peak    float64 `json:"peak"`
}

// ObserveAudioSignal uses its own short-lived high-volume event connection so
// ordinary status/control clients remain unsubscribed. Silence does not fail a
// stream: the current game may simply be quiet during this short observation.
func ObserveAudioSignal(ctx context.Context, cfg Config, inputName string, duration time.Duration) (AudioSignal, error) {
	result := AudioSignal{State: "unknown"}
	if duration <= 0 || duration > time.Second {
		duration = time.Second
	}
	cfg.EventSubscriptions = subscriptions.InputVolumeMeters
	c, err := Connect(ctx, cfg)
	if err != nil {
		return result, err
	}
	defer c.Close()
	timer := time.NewTimer(duration)
	defer timer.Stop()
	for {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		case <-timer.C:
			if result.Samples > 0 {
				result.State = "silent"
				if result.Peak > 0.0001 {
					result.State = "signal"
				}
			}
			return result, nil
		case raw, ok := <-c.obs.IncomingEvents:
			if !ok {
				return result, errors.New("OBS audio level observation disconnected; signal is unknown")
			}
			event, ok := raw.(*events.InputVolumeMeters)
			if !ok {
				continue
			}
			for _, input := range event.Inputs {
				if input == nil || input.Name != inputName {
					continue
				}
				result.Samples++
				for _, channel := range input.Levels {
					peak := channel[1]
					if !math.IsNaN(peak) && !math.IsInf(peak, 0) && peak > result.Peak {
						result.Peak = peak
					}
				}
			}
		}
	}
}
