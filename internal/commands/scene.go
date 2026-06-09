package commands

import (
	"errors"
	"fmt"
	"strings"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newSceneCommand(service obs.Service) *coral.Command {
	sceneCmd := &coral.Command{
		Use:   "scene",
		Short: "manage scenes",
		Long:  `The scene command manages scenes`,
	}

	sceneCmd.AddCommand(&coral.Command{
		Use:   "current",
		Short: "Switch program to a different scene",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("current requires a scene name as argument")
			}
			return service.SetCurrentScene(strings.Join(args, " "))
		},
	})
	sceneCmd.AddCommand(&coral.Command{
		Use:   "list",
		Short: "List all scene names",
		RunE: func(cmd *coral.Command, args []string) error {
			scenes, err := service.ListScenes()
			if err != nil {
				return err
			}
			for _, scene := range scenes {
				fmt.Println(scene)
			}
			return nil
		},
	})
	sceneCmd.AddCommand(&coral.Command{
		Use:   "get",
		Short: "Get the current scene",
		RunE: func(cmd *coral.Command, args []string) error {
			scene, err := service.GetCurrentScene()
			if err != nil {
				return err
			}
			fmt.Println(scene)
			return nil
		},
	})
	sceneCmd.AddCommand(&coral.Command{
		Use:   "preview",
		Short: "Switch preview to a different scene (studio mode must be enabled)",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("preview requires a scene name as argument")
			}
			return service.SetPreviewScene(strings.Join(args, " "))
		},
	})
	sceneCmd.AddCommand(&coral.Command{
		Use:   "switch",
		Short: "Switch program or preview in studio mode to a different scene",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("switch requires a scene name as argument")
			}

			scene := strings.Join(args, " ")
			enabled, err := service.IsStudioModeEnabled()
			if err != nil {
				return err
			}
			if enabled {
				return service.SetPreviewScene(scene)
			}
			return service.SetCurrentScene(scene)
		},
	})

	return sceneCmd
}
