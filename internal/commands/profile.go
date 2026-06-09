package commands

import (
	"errors"
	"fmt"
	"strings"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/obs"
)

func newProfileCommand(service obs.Service) *coral.Command {
	profileCmd := &coral.Command{
		Use:   "profile",
		Short: "manage profiles",
		Long:  `The profile command manages profiles`,
	}

	profileCmd.AddCommand(&coral.Command{
		Use:   "list",
		Short: "List all profiles",
		RunE: func(cmd *coral.Command, args []string) error {
			profiles, err := service.ListProfiles()
			if err != nil {
				return err
			}
			for _, profile := range profiles {
				fmt.Println(profile)
			}
			return nil
		},
	})
	profileCmd.AddCommand(&coral.Command{
		Use:   "get",
		Short: "Get the current profile",
		RunE: func(cmd *coral.Command, args []string) error {
			profile, err := service.GetCurrentProfile()
			if err != nil {
				return err
			}
			fmt.Println(profile)
			return nil
		},
	})
	profileCmd.AddCommand(&coral.Command{
		Use:   "set",
		Short: "Set the current profile",
		RunE: func(cmd *coral.Command, args []string) error {
			if len(args) < 1 {
				return errors.New("set requires a profile name as argument")
			}
			return service.SetCurrentProfile(strings.Join(args, " "))
		},
	})

	return profileCmd
}
