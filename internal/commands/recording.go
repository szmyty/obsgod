package commands

import (
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
	recordingCmd.AddCommand(&coral.Command{
		Use:   "status",
		Short: "Reports recording status",
		RunE: func(cmd *coral.Command, args []string) error {
			status, err := service.GetRecordingStatus()
			if err != nil {
				return err
			}
			fmt.Printf("Recording: %s\n", strconv.FormatBool(status.Active))
			if !status.Active {
				return nil
			}
			fmt.Printf("Paused: %s\n", strconv.FormatBool(status.Paused))
			fmt.Printf("Timecode: %s\n", status.Timecode)
			return nil
		},
	})

	return recordingCmd
}
