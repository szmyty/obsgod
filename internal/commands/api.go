package commands

import (
	"context"
	"encoding/json"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	api "github.com/szmyty/obsgod/pkg/api/v1"
	"github.com/szmyty/obsgod/pkg/automation"
)

type apiConnector func(context.Context, config.Config) (*api.Client, error)

func connectAPI(ctx context.Context, c config.Config) (*api.Client, error) {
	return api.Connect(ctx, api.Connection{Address: net.JoinHostPort(strings.Trim(c.Host, "[]"), strconv.FormatUint(uint64(c.Port), 10)), Password: c.Password, ConnectTimeout: 3 * time.Second, OperationTimeout: 45 * time.Second})
}
func writeAPI(cmd *coral.Command, op string, value any, err error) error {
	if e := json.NewEncoder(cmd.OutOrStdout()).Encode(api.NewResponse(op, value, err)); e != nil {
		return e
	}
	if err != nil {
		return api.Failure(op, err)
	}
	return nil
}
func apiPlan(p automation.WorkflowPlan) api.WorkflowPlan {
	return api.WorkflowPlan{OBSProfile: p.OBSProfile, SceneCollection: p.SceneCollection, StartingScene: p.StartingScene, LiveScene: p.LiveScene, RecordingEnabled: p.RecordingEnabled, ReplayBufferEnabled: p.ReplayBufferEnabled, ReadinessTimeout: p.ReadinessTimeout, PostStartDelay: p.PostStartDelay}
}

func newAPICommand(connection *config.Config, path *string, connect apiConnector) *coral.Command {
	if connect == nil {
		connect = connectAPI
	}
	root := &coral.Command{Use: "api", Short: "Versioned public OBS API adapter; emits one JSON result, preserves legacy commands"}
	root.Example = "  obsgod api capabilities\n  obsgod api snapshot\n  obsgod api stream start --approve"
	root.PersistentFlags().Bool("json", true, "Emit versioned JSON (always enabled for this command family)")
	root.AddCommand(&coral.Command{Use: "capabilities", Short: "Discover the public contract offline", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error { return writeAPI(cmd, "capabilities", api.Discover(), nil) }})
	withClient := func(op string, action func(context.Context, *api.Client) (any, error)) func(*coral.Command, []string) error {
		return func(cmd *coral.Command, _ []string) error {
			client, e := connect(cmd.Context(), *connection)
			if e != nil {
				return writeAPI(cmd, op, nil, e)
			}
			defer client.Close()
			value, e := action(cmd.Context(), client)
			return writeAPI(cmd, op, value, e)
		}
	}
	root.AddCommand(&coral.Command{Use: "snapshot", Aliases: []string{"status"}, Short: "Observe outputs, profiles, collections and scenes", Args: coral.NoArgs, RunE: withClient("snapshot", func(ctx context.Context, c *api.Client) (any, error) { return c.Snapshot(ctx) })})
	stream := &coral.Command{Use: "stream", Short: "Query or explicitly change OBS streaming"}
	stream.AddCommand(&coral.Command{Use: "status", Short: "Observe OBS stream output; provider reception stays unknown", Args: coral.NoArgs, RunE: withClient("snapshot", func(ctx context.Context, c *api.Client) (any, error) { return c.StreamStatus(ctx) })})
	for _, verb := range []string{"start", "stop"} {
		var approve bool
		command := &coral.Command{Use: verb, Short: "Explicitly " + verb + " streaming and confirm observed state", Args: coral.NoArgs}
		command.Flags().BoolVar(&approve, "approve", false, "Approve this output action for this invocation")
		command.RunE = func(cmd *coral.Command, _ []string) error {
			op := "stream." + verb
			if !approve {
				return writeAPI(cmd, op, nil, &api.Error{Code: api.ApprovalRequired, Operation: op})
			}
			return withClient(op, func(ctx context.Context, c *api.Client) (any, error) {
				a := api.Approval{Streaming: true}
				if verb == "start" {
					return c.StartStream(ctx, a)
				}
				return c.StopStream(ctx, a)
			})(cmd, nil)
		}
		stream.AddCommand(command)
	}
	root.AddCommand(stream)
	for _, kind := range []string{"recording", "replay", "virtual-camera"} {
		group := &coral.Command{Use: kind, Short: "Explicitly control local " + kind + " output"}
		verbs := []string{"start", "stop"}
		if kind == "replay" {
			verbs = append(verbs, "save")
		}
		for _, verb := range verbs {
			var approve bool
			command := &coral.Command{Use: verb, Short: verb + " " + kind + " with confirmation", Args: coral.NoArgs}
			command.Flags().BoolVar(&approve, "approve", false, "Approve this local output action for this invocation")
			command.RunE = func(cmd *coral.Command, _ []string) error {
				op := kind + "." + verb
				if !approve {
					return writeAPI(cmd, op, nil, &api.Error{Code: api.ApprovalRequired, Operation: op})
				}
				return withClient(op, func(ctx context.Context, c *api.Client) (any, error) {
					a := api.Approval{Recording: kind == "recording", ReplayBuffer: kind == "replay", VirtualCamera: kind == "virtual-camera"}
					switch kind {
					case "recording":
						if verb == "start" {
							return struct{}{}, c.StartRecording(ctx, a)
						}
						return c.StopRecording(ctx, a)
					case "replay":
						switch verb {
						case "start":
							return struct{}{}, c.StartReplayBuffer(ctx, a)
						case "stop":
							return struct{}{}, c.StopReplayBuffer(ctx, a)
						default:
							return c.SaveReplay(ctx, a)
						}
					default:
						return struct{}{}, c.SetVirtualCamera(ctx, verb == "start", a)
					}
				})(cmd, nil)
			}
			group.AddCommand(command)
		}
		root.AddCommand(group)
	}
	for _, kind := range []string{"profile", "collection", "scene"} {
		group := &coral.Command{Use: kind, Short: "List or select existing OBS " + kind + " settings"}
		group.AddCommand(&coral.Command{Use: "list", Short: "List existing " + kind + " names", Args: coral.NoArgs, RunE: withClient("snapshot", func(ctx context.Context, c *api.Client) (any, error) {
			// Keep this command's existing response envelope and list shape while
			// avoiding unrelated output queries for a profile-only observation.
			if kind == "profile" {
				profiles, err := c.Profiles(ctx)
				if err != nil {
					return nil, err
				}
				return profiles.Profiles, nil
			}
			s, e := c.Snapshot(ctx)
			if e != nil {
				return nil, e
			}
			switch kind {
			case "collection":
				return s.Collections, nil
			default:
				return s.Scenes, nil
			}
		})})
		var approve bool
		selectCmd := &coral.Command{Use: "select NAME", Short: "Select an existing " + kind + " (structural changes require idle outputs)", Args: coral.ExactArgs(1)}
		selectCmd.Flags().BoolVar(&approve, "approve", false, "Approve this settings change for this invocation")
		selectCmd.RunE = func(cmd *coral.Command, args []string) error {
			op := kind + ".select"
			if !approve {
				return writeAPI(cmd, op, nil, &api.Error{Code: api.ApprovalRequired, Operation: op})
			}
			if !api.ValidName(args[0]) {
				return writeAPI(cmd, op, nil, &api.Error{Code: api.InvalidInput, Operation: op})
			}
			return withClient(op, func(ctx context.Context, c *api.Client) (any, error) {
				a := api.Approval{Settings: true}
				switch kind {
				case "profile":
					return struct{}{}, c.SelectProfile(ctx, args[0], a)
				case "collection":
					return struct{}{}, c.SelectCollection(ctx, args[0], a)
				default:
					return struct{}{}, c.SelectScene(ctx, args[0], a)
				}
			})(cmd, nil)
		}
		group.AddCommand(selectCmd)
		root.AddCommand(group)
	}
	items := &coral.Command{Use: "scene-items", Short: "Read or explicitly change a scene item's visibility"}
	items.AddCommand(&coral.Command{Use: "list SCENE", Short: "List scene items with stable IDs", Args: coral.ExactArgs(1), RunE: func(cmd *coral.Command, args []string) error {
		return withClient("scene-items.list", func(ctx context.Context, c *api.Client) (any, error) { return c.SceneItems(ctx, args[0]) })(cmd, nil)
	}})
	for _, verb := range []string{"show", "hide"} {
		var approve bool
		command := &coral.Command{Use: verb + " SCENE ID", Short: verb + " a scene item by numeric ID", Args: coral.ExactArgs(2)}
		command.Flags().BoolVar(&approve, "approve", false, "Approve this visibility change for this invocation")
		command.RunE = func(cmd *coral.Command, args []string) error {
			id, e := strconv.Atoi(args[1])
			if e != nil || id < 0 {
				return writeAPI(cmd, "scene-item.enable", nil, &api.Error{Code: api.InvalidInput, Operation: "scene-item.enable"})
			}
			if !approve {
				return writeAPI(cmd, "scene-item.enable", nil, &api.Error{Code: api.ApprovalRequired, Operation: "scene-item.enable"})
			}
			return withClient("scene-item.enable", func(ctx context.Context, c *api.Client) (any, error) {
				return struct{}{}, c.SetSceneItemEnabled(ctx, args[0], id, verb == "show", api.Approval{Settings: true})
			})(cmd, nil)
		}
		items.AddCommand(command)
	}
	root.AddCommand(items)
	var approve, record, replay bool
	workflow := &coral.Command{Use: "workflow NAME", Short: "Apply an existing declarative workflow; never starts streaming", Args: coral.ExactArgs(1)}
	workflow.Flags().BoolVar(&approve, "approve", false, "Approve settings for this invocation")
	workflow.Flags().BoolVar(&record, "allow-recording", false, "Approve requested local recording")
	workflow.Flags().BoolVar(&replay, "allow-replay-buffer", false, "Approve requested replay capture")
	workflow.RunE = func(cmd *coral.Command, args []string) error {
		plan, _, e := config.ResolveWorkflow(*path, args[0])
		if e != nil {
			return writeAPI(cmd, "workflow.apply", nil, &api.Error{Code: api.InvalidInput, Operation: "workflow.apply"})
		}
		if !approve || (plan.RecordingEnabled && !record) || (plan.ReplayBufferEnabled && !replay) {
			return writeAPI(cmd, "workflow.apply", nil, &api.Error{Code: api.ApprovalRequired, Operation: "workflow.apply"})
		}
		client, e := connect(cmd.Context(), *connection)
		if e != nil {
			return writeAPI(cmd, "workflow.apply", nil, e)
		}
		defer client.Close()
		r, e := client.ApplyWorkflow(cmd.Context(), apiPlan(plan), api.Approval{Settings: approve, Recording: record, ReplayBuffer: replay})
		// Preserve partial stage evidence inside the result, including on failure.
		response := api.NewResponse("workflow.apply", r, e)
		response.Result = r
		if encode := json.NewEncoder(cmd.OutOrStdout()).Encode(response); encode != nil {
			return encode
		}
		return e
	}
	root.AddCommand(workflow)
	return root
}
