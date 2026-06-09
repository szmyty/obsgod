package commands

import (
	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
	appversion "github.com/szmyty/obsgod/internal/version"
)

func NewRoot(cfg *config.Config, service obs.Service, buildVersion string) *coral.Command {
	if cfg == nil {
		defaultConfig := config.Default()
		cfg = &defaultConfig
	}

	rootCmd := &coral.Command{
		Use:           appversion.Name,
		Short:         "obsgod is a command-line remote control for OBS",
		Version:       appversion.Display(buildVersion),
		SilenceErrors: true,
		SilenceUsage:  true,
	}

	rootCmd.PersistentFlags().StringVar(&cfg.Host, "host", cfg.Host, "OBS host to connect to (env: OBS_HOST)")
	rootCmd.PersistentFlags().StringVar(&cfg.Password, "password", cfg.Password, "OBS password (env: OBS_PASSWORD)")
	rootCmd.PersistentFlags().Uint32VarP(&cfg.Port, "port", "p", cfg.Port, "OBS port to connect to (env: OBS_PORT)")

	rootCmd.AddCommand(newLabelCommand(service))
	rootCmd.AddCommand(newProfileCommand(service))
	rootCmd.AddCommand(newRecordingCommand(service))
	rootCmd.AddCommand(newReplayBufferCommand(service))
	rootCmd.AddCommand(newSceneCollectionCommand(service))
	rootCmd.AddCommand(newSceneCommand(service))
	rootCmd.AddCommand(newSceneItemCommand(service))
	rootCmd.AddCommand(newSourceCommand(service))
	rootCmd.AddCommand(newStreamCommand(service))
	rootCmd.AddCommand(newStudioModeCommand(service))
	rootCmd.AddCommand(newVirtualCamCommand(service))

	return rootCmd
}
