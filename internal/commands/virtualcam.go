package commands

import (
	"fmt"
	"strconv"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newVirtualCamCommand(service obs.Service) *coral.Command {
	virtualCamCmd := &coral.Command{
		Use:   "virtualcam",
		Short: "manage virtual camera",
		Long:  `The virtualcam command manages the virtual camera`,
	}

	virtualCamCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Toggle virtual camera status",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.ToggleVirtualCam()
		},
	})
	virtualCamCmd.AddCommand(&coral.Command{
		Use:   "start",
		Short: "Starts virtual camera",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StartVirtualCam()
		},
	})
	virtualCamCmd.AddCommand(&coral.Command{
		Use:   "stop",
		Short: "Stops virtual camera",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StopVirtualCam()
		},
	})
	virtualCamCmd.AddCommand(&coral.Command{
		Use:   "status",
		Short: "Reports virtual camera status",
		RunE: func(cmd *coral.Command, args []string) error {
			active, err := service.GetVirtualCamActive()
			if err != nil {
				return err
			}
			fmt.Printf("Virtual camera: %s\n", strconv.FormatBool(active))
			return nil
		},
	})

	return virtualCamCmd
}
