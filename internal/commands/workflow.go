package commands

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"strconv"
	"strings"

	"github.com/muesli/coral"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/pkg/automation"
)

type workflowConnector func(context.Context, config.Config, automation.WorkflowPlan) (automation.WorkflowBackend, error)

func connectWorkflow(ctx context.Context, connection config.Config, plan automation.WorkflowPlan) (automation.WorkflowBackend, error) {
	ready, _, err := plan.Durations()
	if err != nil {
		return nil, err
	}
	return automation.ConnectWorkflow(ctx, automation.Config{Address: net.JoinHostPort(strings.Trim(connection.Host, "[]"), strconv.FormatUint(uint64(connection.Port), 10)), Password: connection.Password}, ready)
}

func newWorkflowCommand(connection *config.Config, path *string, connect workflowConnector) *coral.Command {
	if connect == nil {
		connect = connectWorkflow
	}
	command := &coral.Command{Use: "workflow", Short: "Plan or explicitly apply provider-neutral OBS settings; never starts streaming"}
	command.AddCommand(&coral.Command{Use: "list", Short: "List declarative workflow profiles without connecting to OBS", Args: coral.NoArgs, RunE: func(cmd *coral.Command, _ []string) error {
		names, err := config.WorkflowNames(*path)
		if err != nil {
			return err
		}
		return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
			SchemaVersion int      `json:"schema_version"`
			Workflows     []string `json:"workflows"`
		}{1, names})
	}})
	var approve, allowRecording, allowReplay, dryRun bool
	encodePlan := func(cmd *coral.Command, args []string) error {
		selected := ""
		if len(args) != 0 {
			selected = args[0]
		}
		plan, name, err := config.ResolveWorkflow(*path, selected)
		if err != nil {
			return err
		}
		return json.NewEncoder(cmd.OutOrStdout()).Encode(struct {
			SchemaVersion int                     `json:"schema_version"`
			Workflow      string                  `json:"workflow"`
			DryRun        bool                    `json:"dry_run"`
			Plan          automation.WorkflowPlan `json:"plan"`
		}{1, name, true, plan})
	}
	command.AddCommand(&coral.Command{Use: "plan [NAME]", Short: "Show resolved workflow intent offline; applies no changes", Args: coral.MaximumNArgs(1), RunE: encodePlan})
	apply := &coral.Command{Use: "apply [NAME]", Short: "Apply reviewed settings to confirmed idle OBS; explicit approvals required", Args: coral.MaximumNArgs(1), RunE: func(cmd *coral.Command, args []string) error {
		if dryRun {
			return encodePlan(cmd, args)
		}
		selected := ""
		if len(args) != 0 {
			selected = args[0]
		}
		plan, _, err := config.ResolveWorkflow(*path, selected)
		if err != nil {
			return err
		}
		approvals := automation.WorkflowApprovals{Settings: approve, Recording: allowRecording, ReplayBuffer: allowReplay}
		if err := approvals.Validate(plan); err != nil {
			return err
		}
		backend, err := connect(cmd.Context(), *connection, plan)
		if err != nil {
			return err
		}
		defer backend.Close()
		result, err := automation.ApplyWorkflow(cmd.Context(), backend, plan, approvals)
		if encodeErr := json.NewEncoder(cmd.OutOrStdout()).Encode(result); encodeErr != nil {
			return encodeErr
		}
		if err != nil {
			return fmt.Errorf("workflow failed: %w", err)
		}
		return nil
	}}
	apply.Flags().BoolVar(&dryRun, "dry-run", false, "Show the plan offline without connecting or applying")
	apply.Flags().BoolVar(&approve, "approve", false, "Approve the reviewed settings changes for this invocation")
	apply.Flags().BoolVar(&allowRecording, "allow-recording", false, "Also approve local recording when requested by this workflow")
	apply.Flags().BoolVar(&allowReplay, "allow-replay-buffer", false, "Also approve local replay-buffer capture when requested")
	command.AddCommand(apply)
	return command
}
