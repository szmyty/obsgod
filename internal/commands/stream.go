package commands

import (
	"encoding/json"
	"errors"
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
	var asJSON, quiet bool
	statusCmd := &coral.Command{
		Use:   "status",
		Short: "Reports streaming status",
		Args:  coral.NoArgs,
		RunE: func(cmd *coral.Command, args []string) error {
			if asJSON && quiet {
				return errors.New("choose --json or --quiet, not both")
			}
			status, err := service.GetStreamStatus()
			if err != nil {
				return err
			}
			if asJSON {
				return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
					SchemaVersion int    `json:"schema_version"`
					Kind          string `json:"kind"`
					Active        bool   `json:"active"`
					Timecode      string `json:"timecode,omitempty"`
				}{1, "stream", status.Active, status.Timecode})
			}
			if quiet {
				return nil
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Streaming: %s\n", strconv.FormatBool(status.Active))
			if !status.Active {
				return nil
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Timecode: %s\n", status.Timecode)
			return nil
		},
	}
	statusCmd.Flags().BoolVar(&asJSON, "json", false, "Print versioned stream status JSON")
	statusCmd.Flags().BoolVar(&quiet, "quiet", false, "Suppress successful status output; errors still fail")
	streamCmd.AddCommand(statusCmd)

	return streamCmd
}
