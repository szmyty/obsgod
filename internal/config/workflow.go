package config

import (
	"errors"
	"os"
	"sort"
	"strconv"

	"github.com/szmyty/obsgod/pkg/automation"
)

func WorkflowNames(explicit string) ([]string, error) {
	path, required, err := ConfigPath(explicit)
	if err != nil {
		return nil, err
	}
	document, _, err := loadFile(path, required)
	if err != nil {
		return nil, err
	}
	names := []string{}
	for name := range document.WorkflowProfiles {
		names = append(names, name)
	}
	sort.Strings(names)
	return names, nil
}

// ResolveWorkflow reads declarative non-secret intent only. Approval is never
// loaded from files or the environment, and selection never applies anything.
func ResolveWorkflow(explicit, name string) (automation.WorkflowPlan, string, error) {
	path, required, err := ConfigPath(explicit)
	if err != nil {
		return automation.WorkflowPlan{}, "", err
	}
	document, _, err := loadFile(path, required)
	if err != nil {
		return automation.WorkflowPlan{}, "", err
	}
	if name == "" {
		name = os.Getenv("OBSGOD_WORKFLOW")
	}
	if name == "" {
		name = document.DefaultWorkflow
	}
	plan, exists := document.WorkflowProfiles[name]
	if !exists || !profileName.MatchString(name) {
		return automation.WorkflowPlan{}, "", errors.New("workflow profile is unavailable; use workflow list and select a configured name")
	}
	fields := map[string]*string{
		"OBSGOD_WORKFLOW_OBS_PROFILE":       &plan.OBSProfile,
		"OBSGOD_WORKFLOW_SCENE_COLLECTION":  &plan.SceneCollection,
		"OBSGOD_WORKFLOW_STARTING_SCENE":    &plan.StartingScene,
		"OBSGOD_WORKFLOW_LIVE_SCENE":        &plan.LiveScene,
		"OBSGOD_WORKFLOW_READINESS_TIMEOUT": &plan.ReadinessTimeout,
		"OBSGOD_WORKFLOW_POST_START_DELAY":  &plan.PostStartDelay,
	}
	// Fixed order keeps validation deterministic; environment values are never
	// interpolated into errors, shell expressions or paths.
	keys := make([]string, 0, len(fields))
	for key := range fields {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		if value := os.Getenv(key); value != "" {
			*fields[key] = value
		}
	}
	for _, option := range []struct {
		key         string
		destination *bool
	}{
		{"OBSGOD_WORKFLOW_RECORDING_ENABLED", &plan.RecordingEnabled},
		{"OBSGOD_WORKFLOW_REPLAY_BUFFER_ENABLED", &plan.ReplayBufferEnabled},
	} {
		if value := os.Getenv(option.key); value != "" {
			parsed, err := strconv.ParseBool(value)
			if err != nil {
				return automation.WorkflowPlan{}, "", errors.New("workflow output environment options must be true or false")
			}
			*option.destination = parsed
		}
	}
	ready, delay, err := plan.Durations()
	if err != nil {
		return automation.WorkflowPlan{}, "", err
	}
	plan.ReadinessTimeout, plan.PostStartDelay = ready.String(), delay.String()
	return plan, name, plan.Validate()
}
