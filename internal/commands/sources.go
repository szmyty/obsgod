package commands

import (
	"errors"
	"fmt"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newSourceCommand(service obs.Service) *coral.Command {
	sourceCmd := &coral.Command{
		Use:   "source",
		Short: "manage sources",
		Long:  `The source command manages sources`,
	}

	sourceCmd.AddCommand(&coral.Command{
		Use:   "list",
		Short: "Lists all sources",
		RunE: func(cmd *coral.Command, args []string) error {
			sources, err := service.GetSpecialSources()
			if err != nil {
				return err
			}
			fmt.Println("Special Sources")
			fmt.Println("===============")
			fmt.Printf("Desktop1: %s\n", sources.Desktop1)
			fmt.Printf("Desktop2: %s\n", sources.Desktop2)
			fmt.Printf("Mic1: %s\n", sources.Mic1)
			fmt.Printf("Mic2: %s\n", sources.Mic2)
			fmt.Printf("Mic3: %s\n", sources.Mic3)
			return nil
		},
	})
	sourceCmd.AddCommand(&coral.Command{
		Use:   "toggle-mute",
		Short: "Toggles mute",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("toggle-mute requires a source name as argument")
			}
			return service.ToggleMute(args[0])
		},
	})

	return sourceCmd
}
