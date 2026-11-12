package commands

import (
	"errors"
	"fmt"
	"strings"

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
			fmt.Fprintln(cmd.OutOrStdout(), "Special Sources")
			fmt.Fprintln(cmd.OutOrStdout(), "===============")
			fmt.Fprintf(cmd.OutOrStdout(), "Desktop1: %s\n", sources.Desktop1)
			fmt.Fprintf(cmd.OutOrStdout(), "Desktop2: %s\n", sources.Desktop2)
			fmt.Fprintf(cmd.OutOrStdout(), "Mic1: %s\n", sources.Mic1)
			fmt.Fprintf(cmd.OutOrStdout(), "Mic2: %s\n", sources.Mic2)
			fmt.Fprintf(cmd.OutOrStdout(), "Mic3: %s\n", sources.Mic3)
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
			return service.ToggleMute(strings.Join(args, " "))
		},
	})

	return sourceCmd
}
