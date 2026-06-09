package commands

import (
	"errors"
	"fmt"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newSceneItemCommand(service obs.Service) *coral.Command {
	sceneItemCmd := &coral.Command{
		Use:   "sceneitem",
		Short: "manage scene items",
		Long:  `The sceneitem command manages a scene's items`,
	}

	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "list",
		Short: "Lists all items of a scene",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("list requires a scene")
			}
			items, err := service.ListSceneItems(args[0])
			if err != nil {
				return err
			}
			for _, item := range items {
				fmt.Println(item)
			}
			return nil
		},
	})
	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Toggles visibility of a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("toggle requires a scene and scene-item")
			}
			return service.ToggleSceneItem(args[0], args[1:]...)
		},
	})
	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "show",
		Short: "Makes a scene-item visible",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("show requires a scene and scene-item(s)")
			}
			return service.SetSceneItemVisible(true, args[0], args[1:]...)
		},
	})
	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "hide",
		Short: "Hides a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("hide requires a scene and scene-item(s)")
			}
			return service.SetSceneItemVisible(false, args[0], args[1:]...)
		},
	})
	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "visible",
		Short: "Show visibility status of a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("visible requires a scene and scene-item")
			}
			visibility, err := service.GetSceneItemVisibility(args[0], args[1:]...)
			if err != nil {
				return err
			}
			for _, item := range visibility {
				fmt.Printf("%s: %t\n", item.Name, item.Visible)
			}
			return nil
		},
	})
	sceneItemCmd.AddCommand(&coral.Command{
		Use:   "center",
		Short: "Horizontally centers a scene-item",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("center requires a scene and scene-item")
			}
			return service.CenterSceneItem(args[0], args[1:]...)
		},
	})

	return sceneItemCmd
}
