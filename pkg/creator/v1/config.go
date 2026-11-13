// Package v1 composes the public OBS API into optional creator workflows. It
// lives in this repository until an owner decides the separate-product boundary.
// Provider credentials and policy never enter the reusable OBS API package.
package v1

import (
	"encoding/json"
	"io"
	"regexp"
	"strings"
	"time"

	api "github.com/szmyty/obsgod/pkg/api/v1"
)

type ProviderConfig struct {
	ID     string `json:"id"`
	Server string `json:"server"`
	KeyEnv string `json:"key_env,omitempty"`
}

func (ProviderConfig) String() string     { return "provider configuration (credentials redacted)" }
func (p ProviderConfig) GoString() string { return p.String() }

type Profile struct {
	SchemaVersion    int              `json:"schema_version"`
	Provider         ProviderConfig   `json:"provider"`
	Workflow         api.WorkflowPlan `json:"workflow"`
	EndingScene      string           `json:"ending_scene,omitempty"`
	ReadinessDelay   string           `json:"readiness_delay,omitempty"`
	StopRecording    bool             `json:"stop_recording"`
	StopReplayBuffer bool             `json:"stop_replay_buffer"`
}

func (p Profile) Validate() error {
	if p.SchemaVersion != 1 || p.Workflow.Validate() != nil || (p.EndingScene != "" && !api.ValidName(p.EndingScene)) {
		return invalid("creator.plan")
	}
	if _, e := p.Delay(); e != nil {
		return e
	}
	if p.Provider.ID == "" || !providerID.MatchString(p.Provider.ID) || (p.Provider.KeyEnv != "" && !environmentName.MatchString(p.Provider.KeyEnv)) {
		return invalid("creator.plan")
	}
	// A dummy key validates endpoint structure without resolving or exposing a secret.
	if (api.RTMPService{Server: p.Provider.Server, Key: "validation-placeholder"}).Validate() != nil {
		return invalid("creator.plan")
	}
	return nil
}
func (p Profile) Delay() (time.Duration, error) {
	value := p.ReadinessDelay
	if value == "" {
		value = p.Workflow.PostStartDelay
	}
	if value == "" {
		return 0, nil
	}
	d, e := time.ParseDuration(value)
	if e != nil || d < 0 || d > 30*time.Second {
		return 0, invalid("creator.plan")
	}
	return d, nil
}

var environmentName = regexp.MustCompile(`^[A-Z_][A-Z0-9_]{0,127}$`)
var providerID = regexp.MustCompile(`^[a-z][a-z0-9_-]{0,31}$`)

func invalid(op string) error { return &api.Error{Code: api.InvalidInput, Operation: op} }
func DecodeProfile(r io.Reader) (Profile, error) {
	var p Profile
	// The entire document must fit the limit, and trailing JSON is rejected.
	b, e := io.ReadAll(io.LimitReader(r, 65537))
	if e != nil || len(b) > 65536 {
		return p, invalid("creator.plan")
	}
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.DisallowUnknownFields()
	if d.Decode(&p) != nil {
		return Profile{}, invalid("creator.plan")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return Profile{}, invalid("creator.plan")
	}
	if e = p.Validate(); e != nil {
		return Profile{}, e
	}
	return p, nil
}

// Provider implementations resolve private transport settings only. Account
// APIs, metadata and audience reception require separate opt-in integrations.
type Provider interface {
	ID() string
	Resolve(ProviderConfig, func(string) (string, bool)) (api.RTMPService, error)
}
type RTMPProvider struct {
	Name          string
	DefaultKeyEnv string
}

func (p RTMPProvider) ID() string { return p.Name }
func (p RTMPProvider) Resolve(c ProviderConfig, lookup func(string) (string, bool)) (api.RTMPService, error) {
	if c.ID != p.Name {
		return api.RTMPService{}, invalid("creator.start")
	}
	name := c.KeyEnv
	if name == "" {
		name = p.DefaultKeyEnv
	}
	if !environmentName.MatchString(name) || lookup == nil {
		return api.RTMPService{}, invalid("creator.start")
	}
	key, ok := lookup(name)
	if !ok {
		return api.RTMPService{}, invalid("creator.start")
	}
	s := api.RTMPService{Server: c.Server, Key: key}
	if e := s.Validate(); e != nil {
		return api.RTMPService{}, invalid("creator.start")
	}
	return s, nil
}
func BuiltinProviders() []Provider {
	return []Provider{RTMPProvider{"kick", "KICK_STREAM_KEY"}, RTMPProvider{"twitch", "TWITCH_STREAM_KEY"}, RTMPProvider{"youtube", "YOUTUBE_STREAM_KEY"}, RTMPProvider{"custom", "OBSGOD_STREAM_KEY"}}
}
func ResolveService(p Profile, providers []Provider, lookup func(string) (string, bool)) (api.RTMPService, error) {
	if e := p.Validate(); e != nil {
		return api.RTMPService{}, e
	}
	for _, provider := range providers {
		if provider != nil && provider.ID() == p.Provider.ID {
			service, err := provider.Resolve(p.Provider, lookup)
			if err != nil {
				return api.RTMPService{}, api.Failure("creator.start", err)
			}
			if err = service.Validate(); err != nil {
				return api.RTMPService{}, api.Failure("creator.start", err)
			}
			return service, nil
		}
	}
	return api.RTMPService{}, invalid("creator.start")
}

type Plan struct {
	SchemaVersion     int              `json:"schema_version"`
	Provider          string           `json:"provider"`
	CredentialSource  string           `json:"credential_source"`
	Workflow          api.WorkflowPlan `json:"workflow"`
	EndingScene       string           `json:"ending_scene,omitempty"`
	ReadinessDelay    string           `json:"readiness_delay,omitempty"`
	StopRecording     bool             `json:"stop_recording"`
	StopReplayBuffer  bool             `json:"stop_replay_buffer"`
	OBSLifecycle      string           `json:"obs_lifecycle"`
	ProviderReception string           `json:"provider_reception"`
}

// Review omits the endpoint and values of all secrets, even in dry-run output.
func (p Profile) Review() Plan {
	return Plan{1, p.Provider.ID, "environment", p.Workflow, p.EndingScene, p.ReadinessDelay, p.StopRecording, p.StopReplayBuffer, "connect_existing_leave_running", "unknown"}
}
