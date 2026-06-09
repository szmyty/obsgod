package commands

import (
	"errors"
	"fmt"
	"strings"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newSceneCollectionCommand(service obs.Service) *coral.Command {
	sceneCollectionCmd := &coral.Command{
		Use:   "scenecollection",
		Short: "manage scene collections",
		Long:  `The scenecollection command manages scene collections`,
	}

	sceneCollectionCmd.AddCommand(&coral.Command{
		Use:   "list",
		Short: "List all scene collections",
		RunE: func(cmd *coral.Command, args []string) error {
			collections, err := service.ListSceneCollections()
			if err != nil {
				return err
			}
			for _, collection := range collections {
				fmt.Println(collection)
			}
			return nil
		},
	})
	sceneCollectionCmd.AddCommand(&coral.Command{
		Use:   "get",
		Short: "Get the current scene collection",
		RunE: func(cmd *coral.Command, args []string) error {
			collection, err := service.GetCurrentSceneCollection()
			if err != nil {
				return err
			}
			fmt.Println(collection)
			return nil
		},
	})
	sceneCollectionCmd.AddCommand(&coral.Command{
		Use:   "set",
		Short: "Set the current scene collection",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("set requires a scene collection name as argument")
			}
			return service.SetCurrentSceneCollection(strings.Join(args, " "))
		},
	})

	return sceneCollectionCmd
}
