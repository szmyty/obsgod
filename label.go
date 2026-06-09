package main

import (
	"errors"

	"github.com/andreykaipov/goobs/api/requests/inputs"
	"github.com/muesli/coral"
)

var (
	labelCmd = &coral.Command{
		Use:   "label",
		Short: "manage text labels",
		Long:  `The label command manages text labels`,
		RunE:  nil,
	}

	textCmd = &coral.Command{
		Use:   "text",
		Short: "Changes a text label",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 2 {
				return errors.New("text requires a source and the new text")
			}
			return changeLabel(args[0], args[1])
		},
	}
)

func changeLabel(source string, text string) error {
	p := inputs.NewSetInputSettingsParams().
		WithInputName(source).
		WithInputSettings(map[string]any{"text": text}).
		WithOverlay(true)

	_, err := client.Inputs.SetInputSettings(p)
	return err
}

func init() {
	labelCmd.AddCommand(textCmd)
	rootCmd.AddCommand(labelCmd)
}
