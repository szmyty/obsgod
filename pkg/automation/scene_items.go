package automation

import (
	"context"

	"github.com/andreykaipov/goobs/api/requests/sceneitems"
)

// EnsureSceneItem attaches an already configured input to another managed scene.
// EnsureInput deliberately does not move or duplicate existing scene items.
func (c *Client) EnsureSceneItem(ctx context.Context, scene, source string) error {
	l, err := request(ctx, "GetSceneItemList", func() (*sceneitems.GetSceneItemListResponse, error) {
		return c.obs.SceneItems.GetSceneItemList(sceneitems.NewGetSceneItemListParams().WithSceneName(scene))
	})
	if err != nil {
		return err
	}
	for _, item := range l.SceneItems {
		if item.SourceName == source {
			return nil
		}
	}
	_, err = request(ctx, "CreateSceneItem", func() (*sceneitems.CreateSceneItemResponse, error) {
		return c.obs.SceneItems.CreateSceneItem(sceneitems.NewCreateSceneItemParams().WithSceneName(scene).WithSourceName(source).WithSceneItemEnabled(true))
	})
	return err
}

// SetSceneItemEnabledIfPresent never creates a missing source during cleanup.
func (c *Client) SetSceneItemEnabledIfPresent(ctx context.Context, scene, source string, enabled bool) error {
	l, err := request(ctx, "GetSceneItemList", func() (*sceneitems.GetSceneItemListResponse, error) {
		return c.obs.SceneItems.GetSceneItemList(sceneitems.NewGetSceneItemListParams().WithSceneName(scene))
	})
	if err != nil {
		return err
	}
	for _, item := range l.SceneItems {
		if item.SourceName == source {
			_, err = request(ctx, "SetSceneItemEnabled", func() (*sceneitems.SetSceneItemEnabledResponse, error) {
				return c.obs.SceneItems.SetSceneItemEnabled(sceneitems.NewSetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(item.SceneItemID).WithSceneItemEnabled(enabled))
			})
			return err
		}
	}
	return nil
}
