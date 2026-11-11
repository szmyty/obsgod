package automation

import (
	"context"
	"errors"
	"time"

	"github.com/andreykaipov/goobs/api/requests/config"
	"github.com/andreykaipov/goobs/api/requests/inputs"
	"github.com/andreykaipov/goobs/api/requests/sceneitems"
	"github.com/andreykaipov/goobs/api/requests/scenes"
	"github.com/andreykaipov/goobs/api/requests/sources"
	"github.com/andreykaipov/goobs/api/typedefs"
)

func (c *Client) EnsureCollection(ctx context.Context, name string) error {
	l, e := empty(ctx, "GetSceneCollectionList", c.obs.Config.GetSceneCollectionList)
	if e != nil {
		return e
	}
	if l.CurrentSceneCollectionName == name {
		return nil
	}
	found := false
	for _, s := range l.SceneCollections {
		if s == name {
			found = true
		}
	}
	if !found {
		_, e = request(ctx, "CreateSceneCollection", func() (*config.CreateSceneCollectionResponse, error) {
			return c.obs.Config.CreateSceneCollection(config.NewCreateSceneCollectionParams().WithSceneCollectionName(name))
		})
		return e
	}
	_, e = request(ctx, "SetCurrentSceneCollection", func() (*config.SetCurrentSceneCollectionResponse, error) {
		return c.obs.Config.SetCurrentSceneCollection(config.NewSetCurrentSceneCollectionParams().WithSceneCollectionName(name))
	})
	return e
}

// MuteOtherAudio prevents OBS's first-run global microphone defaults from being
// mixed into a managed stream. Names in keep are explicitly configured inputs.
func (c *Client) MuteOtherAudio(ctx context.Context, keep map[string]bool) error {
	r, e := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if e != nil {
		return e
	}
	for _, v := range r.Inputs {
		if (v.InputKind == "pulse_input_capture" || v.InputKind == "pulse_output_capture") && !keep[v.InputName] {
			if e = c.SetInputMuted(ctx, v.InputName, true); e != nil {
				return e
			}
		}
	}
	return nil
}

func (c *Client) FitInput(ctx context.Context, scene, name string) error {
	r, e := request(ctx, "GetSceneItemId", func() (*sceneitems.GetSceneItemIdResponse, error) {
		return c.obs.SceneItems.GetSceneItemId(sceneitems.NewGetSceneItemIdParams().WithSceneName(scene).WithSourceName(name))
	})
	if e != nil {
		return e
	}
	_, e = request(ctx, "SetSceneItemTransform", func() (*sceneitems.SetSceneItemTransformResponse, error) {
		return c.obs.SceneItems.SetSceneItemTransform(sceneitems.NewSetSceneItemTransformParams().WithSceneName(scene).WithSceneItemId(r.SceneItemId).WithSceneItemTransform(&typedefs.SceneItemTransform{PositionX: 640, PositionY: 360, ScaleX: 1, ScaleY: 1, Alignment: 0, BoundsType: "OBS_BOUNDS_SCALE_INNER", BoundsWidth: 1280, BoundsHeight: 720}))
	})
	return e
}

// RuntimeStatus contains safe diagnostic fields, never stream-service settings.
type RuntimeStatus struct {
	Version    string `json:"obs_version"`
	Profile    string `json:"profile"`
	Collection string `json:"collection"`
	Scene      string `json:"scene"`
	Recording  bool   `json:"recording"`
}

func (c *Client) RuntimeStatus(ctx context.Context) (RuntimeStatus, error) {
	var s RuntimeStatus
	v, e := empty(ctx, "GetVersion", c.obs.General.GetVersion)
	if e != nil {
		return s, e
	}
	s.Version = v.ObsVersion
	p, e := empty(ctx, "GetProfileList", c.obs.Config.GetProfileList)
	if e != nil {
		return s, e
	}
	s.Profile = p.CurrentProfileName
	l, e := empty(ctx, "GetSceneCollectionList", c.obs.Config.GetSceneCollectionList)
	if e != nil {
		return s, e
	}
	s.Collection = l.CurrentSceneCollectionName
	r, e := empty(ctx, "GetCurrentProgramScene", c.obs.Scenes.GetCurrentProgramScene)
	if e != nil {
		return s, e
	}
	s.Scene = r.SceneName
	t, e := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if e != nil {
		return s, e
	}
	s.Recording = t.OutputActive
	return s, nil
}

// ConfigureRTMP sets a generic custom service. Callers own provider semantics.
func (c *Client) ConfigureRTMP(ctx context.Context, server, key string) error {
	_, err := request(ctx, "SetStreamServiceSettings", func() (*config.SetStreamServiceSettingsResponse, error) {
		return c.obs.Config.SetStreamServiceSettings(config.NewSetStreamServiceSettingsParams().WithStreamServiceType("rtmp_custom").WithStreamServiceSettings(&typedefs.StreamServiceSettings{Server: server, Key: key}))
	})
	return err
}

// EnsureScene creates a scene when it does not already exist.
func (c *Client) EnsureScene(ctx context.Context, name string) error {
	l, e := empty(ctx, "GetSceneList", c.obs.Scenes.GetSceneList)
	if e != nil {
		return e
	}
	for _, s := range l.Scenes {
		if s.SceneName == name {
			return nil
		}
	}
	_, e = request(ctx, "CreateScene", func() (*scenes.CreateSceneResponse, error) {
		return c.obs.Scenes.CreateScene(scenes.NewCreateSceneParams().WithSceneName(name))
	})
	return e
}

func (c *Client) SetScene(ctx context.Context, name string) error {
	_, e := request(ctx, "SetCurrentProgramScene", func() (*scenes.SetCurrentProgramSceneResponse, error) {
		return c.obs.Scenes.SetCurrentProgramScene(scenes.NewSetCurrentProgramSceneParams().WithSceneName(name))
	})
	return e
}

// EnsureInput configures a named input in a managed scene. Existing input types
// must match. It does not remove unrelated inputs or sources.
func (c *Client) EnsureInput(ctx context.Context, scene, name, kind string, settings map[string]any) error {
	k, e := empty(ctx, "GetInputKindList", c.obs.Inputs.GetInputKindList)
	if e != nil {
		return e
	}
	found := false
	for _, v := range k.InputKinds {
		if v == kind {
			found = true
		}
	}
	if !found {
		return errors.New("required OBS input is unavailable: install the OBSGod capture dependencies and restart its OBS instance")
	}
	l, e := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if e != nil {
		return e
	}
	for _, v := range l.Inputs {
		if v.InputName != name {
			continue
		}
		if v.InputKind != kind {
			return errors.New("managed OBS input has an unexpected type")
		}
		_, e = request(ctx, "SetInputSettings", func() (*inputs.SetInputSettingsResponse, error) {
			return c.obs.Inputs.SetInputSettings(inputs.NewSetInputSettingsParams().WithInputName(name).WithInputSettings(settings).WithOverlay(true))
		})
		return e
	}
	_, e = request(ctx, "CreateInput", func() (*inputs.CreateInputResponse, error) {
		return c.obs.Inputs.CreateInput(inputs.NewCreateInputParams().WithSceneName(scene).WithInputName(name).WithInputKind(kind).WithInputSettings(settings).WithSceneItemEnabled(true))
	})
	return e
}

func (c *Client) SetInputMuted(ctx context.Context, name string, muted bool) error {
	_, e := request(ctx, "SetInputMute", func() (*inputs.SetInputMuteResponse, error) {
		return c.obs.Inputs.SetInputMute(inputs.NewSetInputMuteParams().WithInputName(name).WithInputMuted(muted))
	})
	return e
}

// UpdateInputIfPresent overlays source-specific settings without creating an
// input. This is useful for idempotent cleanup after partial setup failures.
func (c *Client) UpdateInputIfPresent(ctx context.Context, name string, settings map[string]any) error {
	l, e := empty(ctx, "GetInputList", c.obs.Inputs.GetInputList)
	if e != nil {
		return e
	}
	for _, input := range l.Inputs {
		if input.InputName == name {
			_, e = request(ctx, "SetInputSettings", func() (*inputs.SetInputSettingsResponse, error) {
				return c.obs.Inputs.SetInputSettings(inputs.NewSetInputSettingsParams().WithInputName(name).WithInputSettings(settings).WithOverlay(true))
			})
			return e
		}
	}
	return nil
}

// Screenshot returns image data to the caller; callers must not log it.
func (c *Client) Screenshot(ctx context.Context, name string) (string, error) {
	r, e := request(ctx, "GetSourceScreenshot", func() (*sources.GetSourceScreenshotResponse, error) {
		return c.obs.Sources.GetSourceScreenshot(sources.NewGetSourceScreenshotParams().WithSourceName(name).WithImageFormat("png").WithImageWidth(160).WithImageHeight(100))
	})
	if e != nil {
		return "", e
	}
	return r.ImageData, nil
}

func (c *Client) StartRecording(ctx context.Context) error {
	r, e := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if e != nil || r.OutputActive {
		return e
	}
	_, e = empty(ctx, "StartRecord", c.obs.Record.StartRecord)
	if e != nil {
		return e
	}
	for {
		r, e = empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
		if e != nil {
			return e
		}
		if r.OutputActive && r.OutputBytes > 0 {
			return nil
		}
		if e = pause(ctx, 250*time.Millisecond); e != nil {
			return errors.New("OBS did not begin recording; inspect the managed OBS window and encoder settings in Desktop Mode")
		}
	}
}
func (c *Client) StopRecording(ctx context.Context) (string, error) {
	r, e := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if e != nil {
		return "", e
	}
	if !r.OutputActive {
		return "", nil
	}
	s, e := empty(ctx, "StopRecord", c.obs.Record.StopRecord)
	if e != nil {
		return "", e
	}
	return s.OutputPath, nil
}
