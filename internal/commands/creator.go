package commands

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	api "github.com/szmyty/obsgod/pkg/api/v1"
	creator "github.com/szmyty/obsgod/pkg/creator/v1"
)

func creatorProfilePath(explicit string) (string, error) {
	if explicit != "" {
		return explicit, nil
	}
	if path := os.Getenv("OBSGOD_CREATOR_PROFILE"); path != "" {
		return path, nil
	}
	if base := os.Getenv("XDG_CONFIG_HOME"); base != "" {
		if !filepath.IsAbs(base) {
			return "", &api.Error{Code: api.InvalidInput, Operation: "creator.plan"}
		}
		return filepath.Join(base, "obsgod", "creator.json"), nil
	}
	base, e := os.UserConfigDir()
	if e != nil {
		return "", &api.Error{Code: api.InvalidInput, Operation: "creator.plan"}
	}
	return filepath.Join(base, "obsgod", "creator.json"), nil
}
func readCreatorProfile(explicit string) (creator.Profile, error) {
	path, e := creatorProfilePath(explicit)
	if e != nil {
		return creator.Profile{}, e
	}
	f, e := os.Open(path)
	if e != nil {
		return creator.Profile{}, &api.Error{Code: api.InvalidInput, Operation: "creator.plan"}
	}
	defer f.Close()
	return creator.DecodeProfile(f)
}
func newCreatorCommand(connection *config.Config, connect apiConnector) *coral.Command {
	if connect == nil {
		connect = connectAPI
	}
	root := &coral.Command{Use: "creator", Short: "Optional local creator orchestration through the public OBS API"}
	root.Example = "  obsgod creator plan --profile creator.json\n  obsgod creator start --profile creator.json --approve --allow-streaming\n  obsgod creator status"
	var profilePath string
	root.PersistentFlags().StringVar(&profilePath, "profile", "", "Creator profile file (env: OBSGOD_CREATOR_PROFILE; default: XDG obsgod/creator.json)")
	root.PersistentFlags().Bool("json", true, "Emit versioned JSON (always enabled for this command family)")
	root.AddCommand(&coral.Command{Use: "extensions", Short: "Discover local provider/event/content extension boundaries offline", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		return json.NewEncoder(cmd.OutOrStdout()).Encode(creator.Discover())
	}})
	root.AddCommand(&coral.Command{Use: "plan", Short: "Review resolved creator intent offline; no secrets are read", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		p, e := readCreatorProfile(profilePath)
		if e != nil {
			return writeAPI(cmd, "creator.plan", nil, e)
		}
		return writeAPI(cmd, "creator.plan", p.Review(), nil)
	}})
	root.AddCommand(&coral.Command{Use: "status", Short: "Observe current OBS state without provider account access", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		client, e := connect(cmd.Context(), *connection)
		if e != nil {
			return writeAPI(cmd, "creator.status", nil, e)
		}
		defer client.Close()
		r, e := creator.Status(cmd.Context(), client)
		if encode := json.NewEncoder(cmd.OutOrStdout()).Encode(r); encode != nil {
			return encode
		}
		return e
	}})
	for _, verb := range []string{"start", "stop"} {
		var approve, stream, record, replay bool
		command := &coral.Command{Use: verb, Short: verb + " the reviewed creator workflow; leaves OBS running", Args: coral.NoArgs}
		command.Flags().BoolVar(&approve, "approve", false, "Approve reviewed OBS settings for this invocation")
		command.Flags().BoolVar(&stream, "allow-streaming", false, "Approve streaming output for this invocation")
		command.Flags().BoolVar(&record, "allow-recording", false, "Approve local recording actions for this invocation")
		command.Flags().BoolVar(&replay, "allow-replay-buffer", false, "Approve local replay actions for this invocation")
		command.RunE = func(cmd *coral.Command, _ []string) error {
			op := "creator." + verb
			p, e := readCreatorProfile(profilePath)
			if e != nil {
				return writeAPI(cmd, op, nil, e)
			}
			needRecord := p.StopRecording
			needReplay := p.StopReplayBuffer
			needSettings := p.EndingScene != ""
			if verb == "start" {
				needRecord = p.Workflow.RecordingEnabled
				needReplay = p.Workflow.ReplayBufferEnabled
				needSettings = true
			}
			if !stream || (needSettings && !approve) || (needRecord && !record) || (needReplay && !replay) {
				return writeAPI(cmd, op, nil, &api.Error{Code: api.ApprovalRequired, Operation: op})
			}
			a := api.Approval{Settings: approve, Streaming: stream, Recording: record, ReplayBuffer: replay}
			var service api.RTMPService
			if verb == "start" {
				service, e = creator.ResolveService(p, creator.BuiltinProviders(), os.LookupEnv)
				if e != nil {
					return writeAPI(cmd, op, nil, e)
				}
			}
			client, e := connect(cmd.Context(), *connection)
			if e != nil {
				return writeAPI(cmd, op, nil, e)
			}
			defer client.Close()
			var r creator.Result
			if verb == "start" {
				r, e = creator.Start(cmd.Context(), client, p, service, a)
			} else {
				r, e = creator.Stop(cmd.Context(), client, p, a)
			}
			if encode := json.NewEncoder(cmd.OutOrStdout()).Encode(r); encode != nil {
				return encode
			}
			return e
		}
		root.AddCommand(command)
	}
	return root
}
