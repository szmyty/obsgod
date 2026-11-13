package commands

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
	appversion "github.com/szmyty/obsgod/internal/version"
	api "github.com/szmyty/obsgod/pkg/api/v1"
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
	base := *cfg
	var configPath, connectionProfile, passwordFile string
	var resolved config.Resolved
	var display presentation
	rootCmd.PersistentPreRunE = func(cmd *coral.Command, _ []string) error {
		// Deck's isolated credentials/configuration are independent of the generic
		// remote-OBS CLI. Recovery and offline help must not depend on this file.
		branch := cmd
		for branch.Parent() != nil && branch.Parent() != rootCmd {
			branch = branch.Parent()
		}
		dryRun, _ := cmd.Flags().GetBool("dry-run")
		if branch.Name() == "deck" || branch.Name() == "doctor" || branch.Name() == "completion" || branch.Name() == "reference" || branch.Name() == "version" || branch.Name() == coral.ShellCompRequestCmd || branch.Name() == coral.ShellCompNoDescRequestCmd || (branch.Name() == "api" && cmd.Name() == "capabilities") || (branch.Name() == "creator" && (cmd.Name() == "plan" || cmd.Name() == "extensions")) || (branch.Name() == "config" && (cmd.Name() == "path" || cmd.Name() == "profiles")) || (branch.Name() == "workflow" && (cmd.Name() != "apply" || dryRun)) {
			diagnosticMetadata(cmd, display, "independent_configuration")
			return nil
		}
		diagnosticMetadata(cmd, display, "checking_configuration")
		if rootCmd.PersistentFlags().Changed("password") && rootCmd.PersistentFlags().Changed("password-file") {
			return errors.New("choose --password-file or --password, not both")
		}
		options := config.Options{Path: configPath, Profile: connectionProfile, PasswordFile: passwordFile}
		if rootCmd.PersistentFlags().Changed("host") {
			value := cfg.Host
			options.Host = &value
		}
		if rootCmd.PersistentFlags().Changed("port") {
			value := cfg.Port
			options.Port = &value
		}
		if rootCmd.PersistentFlags().Changed("password") {
			value := cfg.Password
			options.Password = &value
		}
		var err error
		resolved, err = config.Resolve(base, options)
		if err != nil {
			if branch.Name() == "api" || branch.Name() == "creator" {
				return writeAPI(cmd, "connect", nil, &api.Error{Code: api.InvalidInput, Operation: "connect"})
			}
			return err
		}
		*cfg = resolved.Config
		return nil
	}

	rootCmd.PersistentFlags().StringVar(&configPath, "config", "", "OBS connection config file (env: OBSGOD_CONFIG; default: XDG obsgod/config.json)")
	rootCmd.PersistentFlags().BoolVar(&display.verbose, "verbose", false, "Write credential-free command/stage diagnostics to stderr")
	rootCmd.PersistentFlags().BoolVar(&display.noColor, "no-color", false, "Disable optional terminal color in verbose diagnostics (also respects NO_COLOR/TERM)")
	rootCmd.PersistentFlags().StringVar(&connectionProfile, "connection-profile", "", "Named connection profile (env: OBSGOD_CONNECTION_PROFILE)")
	rootCmd.PersistentFlags().StringVar(&passwordFile, "password-file", "", "Private single-line OBS password file; avoids secret command arguments")
	rootCmd.PersistentFlags().StringVar(&cfg.Host, "host", cfg.Host, "OBS host (env: OBSGOD_HOST or legacy OBS_HOST)")
	rootCmd.PersistentFlags().StringVar(&cfg.Password, "password", cfg.Password, "OBS password; prefer --password-file or OBS_PASSWORD to avoid shell history")
	// pflag prints a string flag's default in help; environment-backed passwords
	// are configuration values, never help text.
	rootCmd.PersistentFlags().Lookup("password").DefValue = ""
	rootCmd.PersistentFlags().Uint32VarP(&cfg.Port, "port", "p", cfg.Port, "OBS port (env: OBSGOD_PORT or legacy OBS_PORT)")
	// Generated help/reference/completions must be independent of the invoking
	// user's environment. Actual effective values remain available in config show.
	rootCmd.PersistentFlags().Lookup("host").DefValue = "localhost"
	rootCmd.PersistentFlags().Lookup("port").DefValue = "4455"
	rootCmd.AddCommand(newConfigCommand(func() config.Resolved { return resolved }, &configPath))
	rootCmd.AddCommand(newVersionCommand(buildVersion))
	rootCmd.AddCommand(newCompletionCommand())
	rootCmd.AddCommand(newReferenceCommand())
	rootCmd.AddCommand(newWorkflowCommand(cfg, &configPath, nil))
	rootCmd.AddCommand(newAPICommand(cfg, &configPath, nil))
	rootCmd.AddCommand(newCreatorCommand(cfg, nil))

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
	rootCmd.AddCommand(newDeckCommand())
	// Construct a separate command instance so both entrypoints retain the same
	// managed implementation, context, timeout and JSON contract.
	for _, managed := range newDeckCommand().Commands() {
		if managed.Name() == "doctor" {
			managed.Short = "Diagnose managed Steam Deck installation, OBS and capture (JSON)"
			rootCmd.AddCommand(managed)
			break
		}
	}
	auditCommandUsage(rootCmd)

	return rootCmd
}

func newConfigCommand(current func() config.Resolved, explicit *string) *coral.Command {
	command := &coral.Command{Use: "config", Short: "Inspect and validate connection configuration without starting OBS"}
	command.AddCommand(&coral.Command{Use: "path", Short: "Print the configured file location, even if its contents are invalid", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		path, _, err := config.ConfigPath(*explicit)
		if err != nil {
			return err
		}
		_, err = fmt.Fprintln(cmd.OutOrStdout(), path)
		return err
	}})
	var asJSON bool
	show := &coral.Command{Use: "show", Short: "Show resolved configuration with credentials redacted (no OBS connection)", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		value := current().Public()
		if asJSON {
			return json.NewEncoder(cmd.OutOrStdout()).Encode(value)
		}
		_, err := fmt.Fprintf(cmd.OutOrStdout(), "Config: %s (loaded: %t)\nConnection profile: %s\nOBS: %s:%d\nPassword configured: %t (source: %s)\nOBS connection: not checked\n", value.ConfigFile, value.FileLoaded, value.ConnectionProfile, value.Host, value.Port, value.PasswordConfigured, value.PasswordSource)
		return err
	}}
	show.Flags().BoolVar(&asJSON, "json", false, "Print versioned redacted JSON")
	command.AddCommand(show)
	var checkJSON bool
	check := &coral.Command{Use: "validate", Aliases: []string{"check"}, Short: "Check the selected configuration and credential reference without connecting", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		if checkJSON {
			return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
				SchemaVersion int           `json:"schema_version"`
				OK            bool          `json:"ok"`
				Configuration config.Public `json:"configuration"`
			}{1, true, current().Public()})
		}
		_, err := fmt.Fprintln(cmd.OutOrStdout(), "Configuration and credential references are valid. OBS connectivity was not checked. Use deck doctor for managed Steam Deck diagnostics.")
		return err
	}}
	check.Flags().BoolVar(&checkJSON, "json", false, "Print versioned redacted JSON")
	command.AddCommand(check)
	var profilesJSON bool
	profiles := &coral.Command{Use: "profiles", Short: "List available connection profiles; this does not change OBS profiles", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		names, err := config.ProfileNames(*explicit)
		if err != nil {
			return err
		}
		if profilesJSON {
			return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
				SchemaVersion int      `json:"schema_version"`
				Profiles      []string `json:"profiles"`
			}{1, names})
		}
		_, err = fmt.Fprintln(cmd.OutOrStdout(), strings.Join(names, "\n"))
		return err
	}}
	profiles.Flags().BoolVar(&profilesJSON, "json", false, "Print versioned profile names")
	command.AddCommand(profiles)
	return command
}

func newVersionCommand(buildVersion string) *coral.Command {
	var asJSON bool
	command := &coral.Command{Use: "version", Short: "Print build version without connecting to OBS", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		if asJSON {
			return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
				SchemaVersion int    `json:"schema_version"`
				Name          string `json:"name"`
				Version       string `json:"version"`
			}{1, appversion.Name, appversion.Display(buildVersion)})
		}
		_, err := fmt.Fprintln(cmd.OutOrStdout(), appversion.Name+" "+appversion.Display(buildVersion))
		return err
	}}
	command.Flags().BoolVar(&asJSON, "json", false, "Print versioned build JSON")
	return command
}

func newCompletionCommand() *coral.Command {
	return &coral.Command{Use: "completion [bash|zsh|fish]", Short: "Generate offline shell completions to stdout", Args: coral.ExactArgs(1), ValidArgs: []string{"bash", "zsh", "fish"}, RunE: func(cmd *coral.Command, args []string) error {
		switch args[0] {
		case "bash":
			return cmd.Root().GenBashCompletionV2(cmd.OutOrStdout(), true)
		case "zsh":
			return cmd.Root().GenZshCompletion(cmd.OutOrStdout())
		case "fish":
			return cmd.Root().GenFishCompletion(cmd.OutOrStdout(), true)
		default:
			return errors.New("unsupported completion shell; choose bash, zsh or fish")
		}
	}}
}
