package commands

import (
	"fmt"
	"strconv"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newStreamCommand(service obs.Service) *coral.Command {
	streamCmd := &coral.Command{
		Use:   "stream",
		Short: "manage streams",
		Long:  `The stream command manages streams`,
	}

	streamCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Toggle streaming",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.ToggleStream()
		},
	})
	streamCmd.AddCommand(&coral.Command{
		Use:   "start",
		Short: "Starts streaming",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StartStream()
		},
	})
	streamCmd.AddCommand(&coral.Command{
		Use:   "stop",
		Short: "Stops streaming",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StopStream()
		},
	})
	streamCmd.AddCommand(&coral.Command{
		Use:   "status",
		Short: "Reports streaming status",
		RunE: func(cmd *coral.Command, args []string) error {
			status, err := service.GetStreamStatus()
			if err != nil {
				return err
			}
			fmt.Printf("Streaming: %s\n", strconv.FormatBool(status.Active))
			if !status.Active {
				return nil
			}
			fmt.Printf("Timecode: %s\n", status.Timecode)
			return nil
		},
	})

	return streamCmd
}
