package commands

import (
	"encoding/json"
	"errors"
	"fmt"
	"strconv"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newRecordingCommand(service obs.Service) *coral.Command {
	recordingCmd := &coral.Command{
		Use:   "recording",
		Short: "manage recordings",
		Long:  `The recording command manages recordings`,
	}

	pauseRecordingCmd := &coral.Command{
		Use:   "pause",
		Short: "manage paused state",
	}

	pauseRecordingCmd.AddCommand(&coral.Command{
		Use:   "enable",
		Short: "Pause recording",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.PauseRecording()
		},
	})
	pauseRecordingCmd.AddCommand(&coral.Command{
		Use:   "resume",
		Short: "Resume recording",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.ResumeRecording()
		},
	})
	pauseRecordingCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Pause/resume recording",
		RunE: func(cmd *coral.Command, args []string) error {
			status, err := service.GetRecordingStatus()
			if err != nil {
				return err
			}
			if !status.Active {
				return fmt.Errorf("recording is not running")
			}
			if status.Paused {
				return service.ResumeRecording()
			}
			return service.PauseRecording()
		},
	})

	recordingCmd.AddCommand(&coral.Command{
		Use:   "toggle",
		Short: "Toggle recording",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.ToggleRecording()
		},
	})
	recordingCmd.AddCommand(&coral.Command{
		Use:   "start",
		Short: "Starts recording",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StartRecording()
		},
	})
	recordingCmd.AddCommand(&coral.Command{
		Use:   "stop",
		Short: "Stops recording",
		RunE: func(cmd *coral.Command, args []string) error {
			return service.StopRecording()
		},
	})
	recordingCmd.AddCommand(pauseRecordingCmd)
	var asJSON, quiet bool
	statusCmd := &coral.Command{
		Use:   "status",
		Short: "Reports recording status",
		Args:  coral.NoArgs,
		RunE: func(cmd *coral.Command, args []string) error {
			if asJSON && quiet {
				return errors.New("choose --json or --quiet, not both")
			}
			status, err := service.GetRecordingStatus()
			if err != nil {
				return err
			}
			if asJSON {
				return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
					SchemaVersion int    `json:"schema_version"`
					Kind          string `json:"kind"`
					Active        bool   `json:"active"`
					Paused        bool   `json:"paused"`
					Timecode      string `json:"timecode,omitempty"`
				}{1, "recording", status.Active, status.Paused, status.Timecode})
			}
			if quiet {
				return nil
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Recording: %s\n", strconv.FormatBool(status.Active))
			if !status.Active {
				return nil
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Paused: %s\n", strconv.FormatBool(status.Paused))
			fmt.Fprintf(cmd.OutOrStdout(), "Timecode: %s\n", status.Timecode)
			return nil
		},
	}
	statusCmd.Flags().BoolVar(&asJSON, "json", false, "Print versioned recording status JSON")
	statusCmd.Flags().BoolVar(&quiet, "quiet", false, "Suppress successful status output; errors still fail")
	recordingCmd.AddCommand(statusCmd)

	return recordingCmd
}
