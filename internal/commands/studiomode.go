package commands

import (
	"fmt"
	"strconv"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newStudioModeCommand(service obs.Service) *coral.Command {
	studioModeCmd := &coral.Command{
		Use:   "studiomode",
		Short: "manage studio mode",
		Long:  `The studiomode command manages the studio mode`,
	}

	studioModeCmd.AddCommand(&coral.Command{
		Use:   "disable",
		Short: "Disables the studio mode",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.SetStudioModeEnabled(false)
		},
	})
	studioModeCmd.AddCommand(&coral.Command{
		Use:   "enable",
		Short: "Enables the studio mode",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.SetStudioModeEnabled(true)
		},
	})
	studioModeCmd.AddCommand(&coral.Command{
		Use:   "status",
		Short: "Reports studio mode status",
		RunE: func(cmd *coral.Command, args []string) error {
			enabled, err := service.IsStudioModeEnabled()
			if err != nil {
				return err
			}
			fmt.Printf("Studio Mode: %s\n", strconv.FormatBool(enabled))
			return nil
		},
	})
	studioModeCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Toggles the studio mode (enable/disable)",
		RunE: func(cmd *coral.Command, args []string) error {
			enabled, err := service.IsStudioModeEnabled()
			if err != nil {
				return err
			}
			return service.SetStudioModeEnabled(!enabled)
		},
	})
	studioModeCmd.AddCommand(&coral.Command{
		Use:   "transition",
		Short: "Transition to program",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.TriggerStudioModeTransition()
		},
	})

	return studioModeCmd
}
