package obs

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/andreykaipov/goobs"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obstransport"
	appversion "github.com/szmyty/obsgod/internal/version"
	api "github.com/szmyty/obsgod/pkg/api/v1"
)

type OutputStatus struct {
	Active   bool
	Paused   bool
	Timecode string
}

type SpecialSources struct {
	Desktop1 string
	Desktop2 string
	Mic1     string
	Mic2     string
	Mic3     string
}

type ItemVisibility struct {
	Name    string
	Visible bool
}

type Service interface {
	Close() error
	ToggleStream() error
	StartStream() error
	StopStream() error
	GetStreamStatus() (OutputStatus, error)
	ToggleRecording() error
	StartRecording() error
	StopRecording() error
	PauseRecording() error
	ResumeRecording() error
	GetRecordingStatus() (OutputStatus, error)
	ListScenes() ([]string, error)
	GetCurrentScene() (string, error)
	SetCurrentScene(string) error
	SetPreviewScene(string) error
	ListSceneCollections() ([]string, error)
	GetCurrentSceneCollection() (string, error)
	SetCurrentSceneCollection(string) error
	ListSceneItems(scene string) ([]string, error)
	SetSceneItemVisible(bool, string, ...string) error
	ToggleSceneItem(string, ...string) error
	GetSceneItemVisibility(string, ...string) ([]ItemVisibility, error)
	CenterSceneItem(string, ...string) error
	ListProfiles() ([]string, error)
	GetCurrentProfile() (string, error)
	SetCurrentProfile(string) error
	SetLabelText(string, string) error
	StartReplayBuffer() error
	StopReplayBuffer() error
	SaveReplayBuffer() error
	GetReplayBufferActive() (bool, error)
	ToggleVirtualCam() error
	StartVirtualCam() error
	StopVirtualCam() error
	GetVirtualCamActive() (bool, error)
	GetSpecialSources() (SpecialSources, error)
	ToggleMute(string) error
	SetStudioModeEnabled(bool) error
	IsStudioModeEnabled() (bool, error)
	TriggerStudioModeTransition() error
}

type Dialer = obstransport.Dialer

type service struct {
	cfg           *config.Config
	buildVersion  string
	dialer        Dialer
	mu            sync.Mutex
	client        *api.Client
	ctx           context.Context
	acquisition   chan struct{}
	generation    uint64
	connectCancel context.CancelFunc
}

func NewService(cfg *config.Config, buildVersion string) Service {
	return NewServiceWithDialer(cfg, buildVersion, goobs.New)
}
func NewServiceWithDialer(cfg *config.Config, buildVersion string, dialer Dialer) Service {
	if dialer == nil {
		dialer = goobs.New
	}
	s := &service{cfg: cfg, buildVersion: buildVersion, dialer: dialer, ctx: context.Background(), acquisition: make(chan struct{}, 1)}
	s.acquisition <- struct{}{}
	return s
}

// SetContext binds one CLI invocation's cancellation without authorizing any
// output change. The service captures it before each call; queued cancellation
// is handled by the facade and cannot close an operation's acquired connection.
func (s *service) SetContext(ctx context.Context) {
	if ctx == nil {
		ctx = context.Background()
	}
	s.mu.Lock()
	s.ctx = ctx
	s.mu.Unlock()
}
func (s *service) invocationContext() context.Context { s.mu.Lock(); defer s.mu.Unlock(); return s.ctx }
func (s *service) Close() error {
	s.mu.Lock()
	s.generation++
	cancel := s.connectCancel
	client := s.client
	s.client = nil
	s.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	if client != nil {
		return legacyError(client.Close())
	}
	return nil
}
func (s *service) clientOrConnect(ctx context.Context) (*api.Client, error) {
	if err := ctx.Err(); err != nil {
		return nil, api.Failure("connect", err)
	}
	select {
	case <-ctx.Done():
		return nil, api.Failure("connect", ctx.Err())
	case <-s.acquisition:
	}
	defer func() { s.acquisition <- struct{}{} }()
	if err := ctx.Err(); err != nil {
		return nil, api.Failure("connect", err)
	}
	s.mu.Lock()
	if s.client != nil && !s.client.Closed() {
		client := s.client
		s.mu.Unlock()
		return client, nil
	}
	if s.cfg == nil {
		s.mu.Unlock()
		return nil, fmt.Errorf("OBS configuration is not initialized")
	}
	cfg := *s.cfg
	generation := s.generation
	attempt, cancel := context.WithCancel(ctx)
	s.connectCancel = cancel
	s.mu.Unlock()
	defer cancel()
	address := net.JoinHostPort(strings.Trim(cfg.Host, "[]"), strconv.FormatUint(uint64(cfg.Port), 10))
	private := obstransport.WithDialer(attempt, s.dialer, appversion.UserAgent(s.buildVersion))
	client, err := api.Connect(private, api.Connection{Address: address, Password: cfg.Password, ConnectTimeout: 10 * time.Second, OperationTimeout: 10 * time.Second})
	s.mu.Lock()
	s.connectCancel = nil
	if generation != s.generation && err == nil {
		err = context.Canceled
	}
	if err == nil {
		s.client = client
	}
	s.mu.Unlock()
	if err != nil {
		if client != nil {
			_ = client.Close()
		}
		if ctx.Err() != nil {
			return nil, api.Failure("connect", ctx.Err())
		}
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return nil, api.Failure("connect", err)
		}
		if strings.ContainsAny(address, "@/\\\r\n\x00") {
			address = "configured endpoint"
		}
		return nil, fmt.Errorf("connect to OBS at %s: %w", address, &api.Error{Code: api.Unavailable, Operation: "connect", Retryable: true})
	}
	return client, nil
}
func legacyError(err error) error {
	if err == nil {
		return nil
	}
	var safe *api.Error
	if errors.As(err, &safe) {
		return err
	}
	return api.Failure("request", err)
}
func (s *service) invoke(r api.LegacyRequest, a api.Approval) (api.LegacyResult, error) {
	ctx := s.invocationContext()
	client, err := s.clientOrConnect(ctx)
	if err != nil {
		return api.LegacyResult{}, legacyError(err)
	}
	value, err := client.Legacy(ctx, r, a)
	return value, legacyError(err)
}

func (s *service) ToggleStream() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyToggleStream}, api.Approval{Streaming: true})
	return err
}

func (s *service) StartStream() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStartStream}, api.Approval{Streaming: true})
	return err
}

func (s *service) StopStream() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStopStream}, api.Approval{Streaming: true})
	return err
}

func (s *service) GetStreamStatus() (OutputStatus, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetStreamStatus}, api.Approval{})
	return OutputStatus{Active: v.Output.Active, Paused: v.Output.Paused, Timecode: v.Output.Timecode}, err
}

func (s *service) ToggleRecording() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyToggleRecording}, api.Approval{Recording: true})
	return err
}

func (s *service) StartRecording() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStartRecording}, api.Approval{Recording: true})
	return err
}

func (s *service) StopRecording() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStopRecording}, api.Approval{Recording: true})
	return err
}

func (s *service) PauseRecording() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyPauseRecording}, api.Approval{Recording: true})
	return err
}

func (s *service) ResumeRecording() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyResumeRecording}, api.Approval{Recording: true})
	return err
}

func (s *service) GetRecordingStatus() (OutputStatus, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetRecordingStatus}, api.Approval{})
	return OutputStatus{Active: v.Output.Active, Paused: v.Output.Paused, Timecode: v.Output.Timecode}, err
}

func (s *service) ListScenes() ([]string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyListScenes}, api.Approval{})
	return v.Names, err
}

func (s *service) GetCurrentScene() (string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetCurrentScene}, api.Approval{})
	return v.Current, err
}

func (s *service) SetCurrentScene(scene string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetCurrentScene, Name: scene}, api.Approval{Settings: true})
	return err
}

func (s *service) SetPreviewScene(scene string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetPreviewScene, Name: scene}, api.Approval{Settings: true})
	return err
}

func (s *service) ListSceneCollections() ([]string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyListSceneCollections}, api.Approval{})
	return v.Names, err
}

func (s *service) GetCurrentSceneCollection() (string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetCurrentSceneCollection}, api.Approval{})
	return v.Current, err
}

func (s *service) SetCurrentSceneCollection(collection string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetCurrentSceneCollection, Name: collection}, api.Approval{Settings: true})
	return err
}

func (s *service) ListSceneItems(scene string) ([]string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyListSceneItems, Scene: scene}, api.Approval{})
	return v.Names, err
}

func (s *service) SetSceneItemVisible(visible bool, scene string, items ...string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetSceneItemVisible, Enabled: visible, Scene: scene, Names: items}, api.Approval{Settings: true})
	return err
}

func (s *service) ToggleSceneItem(scene string, items ...string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyToggleSceneItem, Scene: scene, Names: items}, api.Approval{Settings: true})
	return err
}

func (s *service) GetSceneItemVisibility(scene string, items ...string) ([]ItemVisibility, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetSceneItemVisibility, Scene: scene, Names: items}, api.Approval{})
	if err != nil {
		return nil, err
	}
	result := make([]ItemVisibility, 0, len(v.Visibility))
	for _, item := range v.Visibility {
		result = append(result, ItemVisibility{Name: item.Name, Visible: item.Visible})
	}
	return result, err
}

func (s *service) CenterSceneItem(scene string, items ...string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyCenterSceneItem, Scene: scene, Names: items}, api.Approval{Settings: true})
	return err
}

func (s *service) ListProfiles() ([]string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyListProfiles}, api.Approval{})
	return v.Names, err
}

func (s *service) GetCurrentProfile() (string, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetCurrentProfile}, api.Approval{})
	return v.Current, err
}

func (s *service) SetCurrentProfile(profile string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetCurrentProfile, Name: profile}, api.Approval{Settings: true})
	return err
}

func (s *service) SetLabelText(source, text string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetLabelText, Name: source, Text: text}, api.Approval{Settings: true})
	return err
}

func (s *service) StartReplayBuffer() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStartReplayBuffer}, api.Approval{ReplayBuffer: true})
	return err
}

func (s *service) StopReplayBuffer() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStopReplayBuffer}, api.Approval{ReplayBuffer: true})
	return err
}

func (s *service) SaveReplayBuffer() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySaveReplayBuffer}, api.Approval{ReplayBuffer: true})
	return err
}

func (s *service) GetReplayBufferActive() (bool, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetReplayBufferActive}, api.Approval{})
	return v.Active, err
}

func (s *service) ToggleVirtualCam() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyToggleVirtualCam}, api.Approval{VirtualCamera: true})
	return err
}

func (s *service) StartVirtualCam() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStartVirtualCam}, api.Approval{VirtualCamera: true})
	return err
}

func (s *service) StopVirtualCam() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyStopVirtualCam}, api.Approval{VirtualCamera: true})
	return err
}

func (s *service) GetVirtualCamActive() (bool, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetVirtualCamActive}, api.Approval{})
	return v.Active, err
}

func (s *service) GetSpecialSources() (SpecialSources, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyGetSpecialSources}, api.Approval{})
	return SpecialSources{Desktop1: v.Sources.Desktop1, Desktop2: v.Sources.Desktop2, Mic1: v.Sources.Mic1, Mic2: v.Sources.Mic2, Mic3: v.Sources.Mic3}, err
}

func (s *service) ToggleMute(source string) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyToggleMute, Name: source}, api.Approval{Settings: true})
	return err
}

func (s *service) SetStudioModeEnabled(enabled bool) error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacySetStudioModeEnabled, Enabled: enabled}, api.Approval{Settings: true})
	return err
}

func (s *service) IsStudioModeEnabled() (bool, error) {
	v, err := s.invoke(api.LegacyRequest{Operation: api.LegacyIsStudioModeEnabled}, api.Approval{})
	return v.Active, err
}

func (s *service) TriggerStudioModeTransition() error {
	_, err := s.invoke(api.LegacyRequest{Operation: api.LegacyTriggerStudioModeTransition}, api.Approval{Settings: true})
	return err
}
