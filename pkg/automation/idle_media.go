package automation

import (
	"context"
	"errors"

	"github.com/andreykaipov/goobs/api/requests/inputs"
)

// EnsureMutedMediaInput creates a media source with its initial scene item
// disabled, then mutes it before a caller can enable it. Existing media is muted
// before its file/settings change. This avoids leaking an imported video's
// soundtrack into the user's separately selected system/microphone audio.
func (c *Client) EnsureMutedMediaInput(ctx context.Context, scene, name string, settings map[string]any) error {
	kinds, err := empty(ctx, "GetInputKindList", c.obs.Inputs.GetInputKindList)
	if err != nil {
		return err
	}
	found := false
	for _, kind := range kinds.InputKinds {
		if kind == "ffmpeg_source" {
			found = true
			break
		}
	}
	if !found {
		return errors.New("OBS local media playback is unavailable; black fallback is preserved")
	}
	list, err := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if err != nil {
		return err
	}
	exists := false
	for _, input := range list.Inputs {
		if input.InputName != name {
			continue
		}
		if input.InputKind != "ffmpeg_source" {
			return errors.New("owned idle media input has an unexpected type")
		}
		exists = true
		break
	}
	if exists {
		if err = c.SetInputMuted(ctx, name, true); err != nil {
			return err
		}
		_, err = request(ctx, "SetInputSettings", func() (*inputs.SetInputSettingsResponse, error) {
			return c.obs.Inputs.SetInputSettings(inputs.NewSetInputSettingsParams().WithInputName(name).WithInputSettings(settings).WithOverlay(false))
		})
	} else {
		_, err = request(ctx, "CreateInput", func() (*inputs.CreateInputResponse, error) {
			return c.obs.Inputs.CreateInput(inputs.NewCreateInputParams().WithSceneName(scene).WithInputName(name).WithInputKind("ffmpeg_source").WithInputSettings(settings).WithSceneItemEnabled(false))
		})
	}
	if err != nil {
		return err
	}
	return c.SetInputMuted(ctx, name, true)
}
