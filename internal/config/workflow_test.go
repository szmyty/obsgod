package config

import (
	"strings"
	"testing"
)

func TestWorkflowSelectionDefaultsAndKnownEnvironmentOverrides(t *testing.T) {
	root := isolateEnvironment(t)
	path := writeConfig(t, root, `{"version":1,"default_workflow":"studio","workflow_profiles":{"studio":{"obs_profile":"Studio","recording_enabled":false},"local":{"starting_scene":"Local"}}}`)
	for _, key := range []string{"OBSGOD_WORKFLOW", "OBSGOD_WORKFLOW_RECORDING_ENABLED", "OBSGOD_WORKFLOW_REPLAY_BUFFER_ENABLED", "OBSGOD_WORKFLOW_OBS_PROFILE", "OBSGOD_WORKFLOW_READINESS_TIMEOUT", "OBSGOD_WORKFLOW_POST_START_DELAY"} {
		t.Setenv(key, "")
	}
	plan, name, err := ResolveWorkflow(path, "")
	if err != nil || name != "studio" || plan.OBSProfile != "Studio" || plan.ReadinessTimeout != "3s" || plan.PostStartDelay != "0s" {
		t.Fatalf("default workflow: %+v %q %v", plan, name, err)
	}
	t.Setenv("OBSGOD_WORKFLOW", "local")
	t.Setenv("OBSGOD_WORKFLOW_RECORDING_ENABLED", "true")
	t.Setenv("OBSGOD_WORKFLOW_READINESS_TIMEOUT", "2s")
	plan, name, err = ResolveWorkflow(path, "")
	if err != nil || name != "local" || plan.StartingScene != "Local" || !plan.RecordingEnabled || plan.ReadinessTimeout != "2s" {
		t.Fatalf("environment override: %+v %q %v", plan, name, err)
	}
	_, name, err = ResolveWorkflow(path, "studio")
	if err != nil || name != "studio" {
		t.Fatal("explicit workflow must override environment selection")
	}
	t.Setenv("OBSGOD_WORKFLOW_RECORDING_ENABLED", "private-credential-marker")
	if _, _, err := ResolveWorkflow(path, "studio"); err == nil || strings.Contains(err.Error(), "private-credential-marker") {
		t.Fatalf("invalid environment must fail without echo: %v", err)
	}
}

func TestWorkflowKnownSchemaDurationAndApprovalBoundaries(t *testing.T) {
	for _, body := range []string{
		`{"version":1,"workflow_profiles":{"studio":{"approve":true}}}`,
		`{"version":1,"workflow_profiles":{"studio":{"start_stream":true}}}`,
		`{"version":1,"workflow_profiles":{"studio":{"readiness_timeout":"31s"}}}`,
		`{"version":1,"workflow_profiles":{"studio":{"post_start_delay":"-1s"}}}`,
		`{"version":1,"workflow_profiles":{"studio":{"obs_profile":"bad\nname"}}}`,
	} {
		t.Run(body, func(t *testing.T) {
			root := isolateEnvironment(t)
			path := writeConfig(t, root, body)
			if _, _, err := ResolveWorkflow(path, "studio"); err == nil {
				t.Fatal("unsafe/unsupported workflow accepted")
			}
		})
	}
}
