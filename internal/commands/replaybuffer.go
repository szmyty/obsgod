package commands

import (
	"fmt"
	"strconv"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newReplayBufferCommand(service obs.Service) *coral.Command {
	replayBufferCmd := &coral.Command{
		Use:   "replaybuffer",
		Short: "manage replay buffer",
		Long:  `The replaybuffer command manages the replay buffer`,
	}

	replayBufferCmd.AddCommand(&coral.Command{
		Use:   "start",
		Short: "Starts replay buffer",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StartReplayBuffer()
		},
	})
	replayBufferCmd.AddCommand(&coral.Command{
		Use:   "stop",
		Short: "Stops replay buffer",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StopReplayBuffer()
		},
	})
	replayBufferCmd.AddCommand(&coral.Command{
		Use:   "save",
		Short: "Saves replay buffer",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.SaveReplayBuffer()
		},
	})
	replayBufferCmd.AddCommand(&coral.Command{
		Use:   "status",
		Short: "Reports replay buffer status",
		RunE: func(cmd *coral.Command, args []string) error {
			active, err := service.GetReplayBufferActive()
			if err != nil {
				return err
			}
			fmt.Printf("Replay Buffer active: %s\n", strconv.FormatBool(active))
			return nil
		},
	})

	return replayBufferCmd
}
