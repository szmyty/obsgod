package automation

// These typed primitives share the existing context-aware request adapter.
// Approval and application policy live in pkg/api/v1, not in protocol calls.
import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/andreykaipov/goobs/api/requests/sceneitems"
)

type SceneItemState struct {
	ID      int
	Name    string
	Enabled bool
}

// APIRecordingStatus distinguishes an unknown paused state from false.
func (c *Client) APIRecordingStatus(ctx context.Context) (RecordingStatus, error) {
	r, err := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if err != nil {
		return RecordingStatus{}, err
	}
	if err = workflowKnownOutput(r.GetRaw(), "outputActive", "outputPaused"); err != nil {
		return RecordingStatus{}, err
	}
	return RecordingStatus{Active: r.OutputActive, Paused: r.OutputPaused, Bytes: r.OutputBytes, Duration: r.OutputDuration}, nil
}
func (c *Client) SceneItems(ctx context.Context, scene string) ([]SceneItemState, error) {
	r, err := request(ctx, "GetSceneItemList", func() (*sceneitems.GetSceneItemListResponse, error) {
		return c.obs.SceneItems.GetSceneItemList(sceneitems.NewGetSceneItemListParams().WithSceneName(scene))
	})
	if err != nil {
		return nil, err
	}
	var raw struct {
		Items []map[string]json.RawMessage `json:"sceneItems"`
	}
	if json.Unmarshal(r.GetRaw(), &raw) != nil || raw.Items == nil || len(raw.Items) != len(r.SceneItems) {
		return nil, errors.New("OBS scene item state is incomplete")
	}
	for _, item := range raw.Items {
		var enabled *bool
		var id *int
		if json.Unmarshal(item["sceneItemEnabled"], &enabled) != nil || enabled == nil || json.Unmarshal(item["sceneItemId"], &id) != nil || id == nil || *id < 0 {
			return nil, errors.New("OBS scene item state is incomplete")
		}
	}
	result := make([]SceneItemState, 0, len(r.SceneItems))
	for _, item := range r.SceneItems {
		result = append(result, SceneItemState{item.SceneItemID, item.SourceName, item.SceneItemEnabled})
	}
	return result, nil
}
func (c *Client) SetItemEnabled(ctx context.Context, scene string, id int, enabled bool) error {
	_, err := request(ctx, "SetSceneItemEnabled", func() (*sceneitems.SetSceneItemEnabledResponse, error) {
		return c.obs.SceneItems.SetSceneItemEnabled(sceneitems.NewSetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id).WithSceneItemEnabled(enabled))
	})
	return err
}
func (c *Client) VirtualCameraActive(ctx context.Context) (bool, error) {
	r, err := empty(ctx, "GetVirtualCamStatus", c.obs.Outputs.GetVirtualCamStatus)
	if err != nil {
		return false, err
	}
	if err = workflowKnownOutput(r.GetRaw(), "outputActive"); err != nil {
		return false, err
	}
	return r.OutputActive, nil
}
func (c *Client) SetVirtualCamera(ctx context.Context, active bool) error {
	current, err := c.VirtualCameraActive(ctx)
	if err != nil || current == active {
		return err
	}
	if active {
		_, err = empty(ctx, "StartVirtualCam", c.obs.Outputs.StartVirtualCam)
	} else {
		_, err = empty(ctx, "StopVirtualCam", c.obs.Outputs.StopVirtualCam)
	}
	if err != nil {
		return err
	}
	for {
		current, err = c.VirtualCameraActive(ctx)
		if err != nil || current == active {
			return err
		}
		if err = pause(ctx, 100*time.Millisecond); err != nil {
			return err
		}
	}
}

// ConfirmRTMP compares private settings in memory. The read response, including
// its key, is never returned or logged by this method.
var ErrServiceMismatch = errors.New("OBS has not confirmed the requested custom stream service")

func (c *Client) ConfirmRTMP(ctx context.Context, server, key string) error {
	r, err := empty(ctx, "GetStreamServiceSettings", c.obs.Config.GetStreamServiceSettings)
	if err != nil {
		return err
	}
	if r.StreamServiceType != "rtmp_custom" || r.StreamServiceSettings == nil || r.StreamServiceSettings.Server != server || r.StreamServiceSettings.Key != key {
		return ErrServiceMismatch
	}
	return nil
}
