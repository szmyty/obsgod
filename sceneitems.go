package main

import (
	"errors"
	"fmt"

	sceneitems "github.com/andreykaipov/goobs/api/requests/sceneitems"
	"github.com/muesli/coral"
)

var (
	sceneItemCmd = &coral.Command{
		Use:   "sceneitem",
		Short: "manage scene items",
		Long:  `The sceneitem command manages a scene's items`,
		RunE:  nil,
	}

	listSceneItemsCmd = &coral.Command{
		Use:   "list",
		Short: "Lists all items of a scene",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("list requires a scene")
			}
			return listSceneItems(args[0])
		},
	}

	toggleSceneItemCmd = &coral.Command{
		Use:   "toggle",
		Short: "Toggles visibility of a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("toggle requires a scene and scene-item")
			}
			return toggleSceneItem(args[0], args[1:]...)
		},
	}

	showSceneItemCmd = &coral.Command{
		Use:   "show",
		Short: "Makes a scene-item visible",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("show requires a scene and scene-item(s)")
			}
			return setSceneItemVisible(true, args[0], args[1:]...)
		},
	}

	hideSceneItemCmd = &coral.Command{
		Use:   "hide",
		Short: "Hides a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("hide requires a scene and scene-item(s)")
			}
			return setSceneItemVisible(false, args[0], args[1:]...)
		},
	}

	getSceneItemVisibilityCmd = &coral.Command{
		Use:   "visible",
		Short: "Show visibility status of a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("visible requires a scene and scene-item")
			}
			return getSceneItemVisibility(args[0], args[1:]...)
		},
	}

	centerSceneItemCmd = &coral.Command{
		Use:   "center",
		Short: "Horizontally centers a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("center requires a scene and scene-item")
			}
			return centerSceneItem(args[0], args[1:]...)
		},
	}
)

func getSceneItemID(scene, item string) (int, error) {
	p := sceneitems.NewGetSceneItemIdParams().WithSceneName(scene).WithSourceName(item)
	resp, err := client.SceneItems.GetSceneItemId(p)
	if err != nil {
		return 0, err
	}
	return resp.SceneItemId, nil
}

func listSceneItems(scene string) error {
	p := sceneitems.NewGetSceneItemListParams().WithSceneName(scene)
	resp, err := client.SceneItems.GetSceneItemList(p)
	if err != nil {
		return err
	}

	for _, s := range resp.SceneItems {
		fmt.Println(s.SourceName)
	}
	return nil
}

func setSceneItemVisible(visible bool, scene string, items ...string) error {
	for _, item := range items {
		id, err := getSceneItemID(scene, item)
		if err != nil {
			return err
		}

		p := sceneitems.NewSetSceneItemEnabledParams().
			WithSceneName(scene).
			WithSceneItemId(id).
			WithSceneItemEnabled(visible)

		_, err = client.SceneItems.SetSceneItemEnabled(p)
		if err != nil {
			return err
		}
	}
	return nil
}

func toggleSceneItem(scene string, items ...string) error {
	for _, item := range items {
		id, err := getSceneItemID(scene, item)
		if err != nil {
			return err
		}

		p := sceneitems.NewGetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id)
		resp, err := client.SceneItems.GetSceneItemEnabled(p)
		if err != nil {
			return err
		}

		err = setSceneItemVisible(!resp.SceneItemEnabled, scene, item)
		if err != nil {
			return err
		}
	}
	return nil
}

func getSceneItemVisibility(scene string, items ...string) error {
	for _, item := range items {
		id, err := getSceneItemID(scene, item)
		if err != nil {
			return err
		}

		p := sceneitems.NewGetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id)
		resp, err := client.SceneItems.GetSceneItemEnabled(p)
		if err != nil {
			return err
		}

		fmt.Printf("%s: %t\n", item, resp.SceneItemEnabled)
	}
	return nil
}

func centerSceneItem(scene string, items ...string) error {
	for _, item := range items {
		id, err := getSceneItemID(scene, item)
		if err != nil {
			return err
		}

		tp := sceneitems.NewGetSceneItemTransformParams().WithSceneName(scene).WithSceneItemId(id)
		tresp, err := client.SceneItems.GetSceneItemTransform(tp)
		if err != nil {
			return err
		}

		vresp, err := client.Config.GetVideoSettings()
		if err != nil {
			return err
		}

		transform := tresp.SceneItemTransform
		transform.PositionX = vresp.BaseWidth / 2

		sp := sceneitems.NewSetSceneItemTransformParams().
			WithSceneName(scene).
			WithSceneItemId(id).
			WithSceneItemTransform(transform)

		_, err = client.SceneItems.SetSceneItemTransform(sp)
		if err != nil {
			return err
		}
	}
	return nil
}

func init() {
	sceneItemCmd.AddCommand(centerSceneItemCmd)
	sceneItemCmd.AddCommand(toggleSceneItemCmd)
	sceneItemCmd.AddCommand(showSceneItemCmd)
	sceneItemCmd.AddCommand(hideSceneItemCmd)
	sceneItemCmd.AddCommand(getSceneItemVisibilityCmd)
	sceneItemCmd.AddCommand(listSceneItemsCmd)
	rootCmd.AddCommand(sceneItemCmd)
}
