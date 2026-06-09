package commands

import (
	"errors"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newLabelCommand(service obs.Service) *coral.Command {
	labelCmd := &coral.Command{
		Use:   "label",
		Short: "manage text labels",
		Long:  `The label command manages text labels`,
	}

	labelCmd.AddCommand(&coral.Command{
		Use:   "text",
		Short: "Changes a text label",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("text requires a source and the new text")
			}
			return service.SetLabelText(args[0], args[1])
		},
	})
	labelCmd.AddCommand(&coral.Command{
		Use:   "countdown",
		Short: "Triggers a countdown and continuously updates a label with the remaining time",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("countdown requires a label and the countdown in seconds")
			}
			duration, err := parseCountdownDuration(args[1])
			if err != nil {
				return err
			}
			return countdown(service, args[0], duration)
		},
	})

	return labelCmd
}
