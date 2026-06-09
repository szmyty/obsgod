package obs

import (
	"fmt"
	"net/http"
	"sync"

	"github.com/andreykaipov/goobs"
	configrequests "github.com/andreykaipov/goobs/api/requests/config"
	"github.com/andreykaipov/goobs/api/requests/inputs"
	sceneitems "github.com/andreykaipov/goobs/api/requests/sceneitems"
	"github.com/andreykaipov/goobs/api/requests/scenes"
	"github.com/andreykaipov/goobs/api/requests/ui"
	"github.com/szmyty/obsgod/internal/config"
	appversion "github.com/szmyty/obsgod/internal/version"
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

type Dialer func(address string, options ...goobs.Option) (*goobs.Client, error)

type service struct {
	cfg          *config.Config
	buildVersion string
	dialer       Dialer

	mu     sync.Mutex
	client *goobs.Client
}

func NewService(cfg *config.Config, buildVersion string) Service {
	return NewServiceWithDialer(cfg, buildVersion, goobs.New)
}

func NewServiceWithDialer(cfg *config.Config, buildVersion string, dialer Dialer) Service {
	if dialer == nil {
		dialer = goobs.New
	}
	return &service{cfg: cfg, buildVersion: buildVersion, dialer: dialer}
}

func (s *service) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.client == nil {
		return nil
	}

	err := s.client.Disconnect()
	s.client = nil
	return err
}

func (s *service) clientOrConnect() (*goobs.Client, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.client != nil {
		return s.client, nil
	}

	if s.cfg == nil {
		return nil, fmt.Errorf("OBS configuration is not initialized")
	}

	address := fmt.Sprintf("%s:%d", s.cfg.Host, s.cfg.Port)
	client, err := s.dialer(
		address,
		goobs.WithPassword(s.cfg.Password),
		goobs.WithRequestHeader(http.Header{"User-Agent": []string{appversion.UserAgent(s.buildVersion)}}),
	)
	if err != nil {
		return nil, fmt.Errorf("connect to OBS at %s: %w", address, err)
	}

	s.client = client
	return s.client, nil
}

func (s *service) ToggleStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Stream.ToggleStream()
	return err
}

func (s *service) StartStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Stream.StartStream()
	return err
}

func (s *service) StopStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Stream.StopStream()
	return err
}

func (s *service) GetStreamStatus() (OutputStatus, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return OutputStatus{}, err
	}
	r, err := c.Stream.GetStreamStatus()
	if err != nil {
		return OutputStatus{}, err
	}
	return OutputStatus{Active: r.OutputActive, Timecode: r.OutputTimecode}, nil
}

func (s *service) ToggleRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Record.ToggleRecord()
	return err
}

func (s *service) StartRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Record.StartRecord()
	return err
}

func (s *service) StopRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Record.StopRecord()
	return err
}

func (s *service) PauseRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Record.PauseRecord()
	return err
}

func (s *service) ResumeRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Record.ResumeRecord()
	return err
}

func (s *service) GetRecordingStatus() (OutputStatus, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return OutputStatus{}, err
	}
	r, err := c.Record.GetRecordStatus()
	if err != nil {
		return OutputStatus{}, err
	}
	return OutputStatus{Active: r.OutputActive, Paused: r.OutputPaused, Timecode: r.OutputTimecode}, nil
}

func (s *service) ListScenes() ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	r, err := c.Scenes.GetSceneList()
	if err != nil {
		return nil, err
	}

	scenes := make([]string, 0, len(r.Scenes))
	for _, scene := range r.Scenes {
		scenes = append(scenes, scene.SceneName)
	}
	return scenes, nil
}

func (s *service) GetCurrentScene() (string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return "", err
	}
	r, err := c.Scenes.GetCurrentProgramScene()
	if err != nil {
		return "", err
	}
	return r.SceneName, nil
}

func (s *service) SetCurrentScene(scene string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := scenes.NewSetCurrentProgramSceneParams().WithSceneName(scene)
	_, err = c.Scenes.SetCurrentProgramScene(params)
	return err
}

func (s *service) SetPreviewScene(scene string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := scenes.NewSetCurrentPreviewSceneParams().WithSceneName(scene)
	_, err = c.Scenes.SetCurrentPreviewScene(params)
	return err
}

func (s *service) ListSceneCollections() ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	r, err := c.Config.GetSceneCollectionList()
	if err != nil {
		return nil, err
	}
	collections := make([]string, 0, len(r.SceneCollections))
	for _, collection := range r.SceneCollections {
		collections = append(collections, collection)
	}
	return collections, nil
}

func (s *service) GetCurrentSceneCollection() (string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return "", err
	}
	r, err := c.Config.GetSceneCollectionList()
	if err != nil {
		return "", err
	}
	return r.CurrentSceneCollectionName, nil
}

func (s *service) SetCurrentSceneCollection(collection string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := configrequests.NewSetCurrentSceneCollectionParams().WithSceneCollectionName(collection)
	_, err = c.Config.SetCurrentSceneCollection(params)
	return err
}

func (s *service) ListSceneItems(scene string) ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	params := sceneitems.NewGetSceneItemListParams().WithSceneName(scene)
	resp, err := c.SceneItems.GetSceneItemList(params)
	if err != nil {
		return nil, err
	}

	items := make([]string, 0, len(resp.SceneItems))
	for _, item := range resp.SceneItems {
		items = append(items, item.SourceName)
	}
	return items, nil
}

func (s *service) getSceneItemID(c *goobs.Client, scene, item string) (int, error) {
	params := sceneitems.NewGetSceneItemIdParams().WithSceneName(scene).WithSourceName(item)
	resp, err := c.SceneItems.GetSceneItemId(params)
	if err != nil {
		return 0, err
	}
	return resp.SceneItemId, nil
}

func (s *service) SetSceneItemVisible(visible bool, scene string, items ...string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	for _, item := range items {
		id, err := s.getSceneItemID(c, scene, item)
		if err != nil {
			return err
		}

		params := sceneitems.NewSetSceneItemEnabledParams().
			WithSceneName(scene).
			WithSceneItemId(id).
			WithSceneItemEnabled(visible)
		_, err = c.SceneItems.SetSceneItemEnabled(params)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *service) ToggleSceneItem(scene string, items ...string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	for _, item := range items {
		id, err := s.getSceneItemID(c, scene, item)
		if err != nil {
			return err
		}
		params := sceneitems.NewGetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id)
		resp, err := c.SceneItems.GetSceneItemEnabled(params)
		if err != nil {
			return err
		}
		if err := s.SetSceneItemVisible(!resp.SceneItemEnabled, scene, item); err != nil {
			return err
		}
	}
	return nil
}

func (s *service) GetSceneItemVisibility(scene string, items ...string) ([]ItemVisibility, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	visibility := make([]ItemVisibility, 0, len(items))
	for _, item := range items {
		id, err := s.getSceneItemID(c, scene, item)
		if err != nil {
			return nil, err
		}
		params := sceneitems.NewGetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id)
		resp, err := c.SceneItems.GetSceneItemEnabled(params)
		if err != nil {
			return nil, err
		}
		visibility = append(visibility, ItemVisibility{Name: item, Visible: resp.SceneItemEnabled})
	}
	return visibility, nil
}

func (s *service) CenterSceneItem(scene string, items ...string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	for _, item := range items {
		id, err := s.getSceneItemID(c, scene, item)
		if err != nil {
			return err
		}
		transformParams := sceneitems.NewGetSceneItemTransformParams().WithSceneName(scene).WithSceneItemId(id)
		transformResp, err := c.SceneItems.GetSceneItemTransform(transformParams)
		if err != nil {
			return err
		}
		videoResp, err := c.Config.GetVideoSettings()
		if err != nil {
			return err
		}

		transform := transformResp.SceneItemTransform
		transform.PositionX = videoResp.BaseWidth / 2

		setParams := sceneitems.NewSetSceneItemTransformParams().
			WithSceneName(scene).
			WithSceneItemId(id).
			WithSceneItemTransform(transform)
		_, err = c.SceneItems.SetSceneItemTransform(setParams)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *service) ListProfiles() ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	r, err := c.Config.GetProfileList()
	if err != nil {
		return nil, err
	}
	profiles := make([]string, 0, len(r.Profiles))
	for _, profile := range r.Profiles {
		profiles = append(profiles, profile)
	}
	return profiles, nil
}

func (s *service) GetCurrentProfile() (string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return "", err
	}
	r, err := c.Config.GetProfileList()
	if err != nil {
		return "", err
	}
	return r.CurrentProfileName, nil
}

func (s *service) SetCurrentProfile(profile string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := configrequests.NewSetCurrentProfileParams().WithProfileName(profile)
	_, err = c.Config.SetCurrentProfile(params)
	return err
}

func (s *service) SetLabelText(source, text string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := inputs.NewSetInputSettingsParams().
		WithInputName(source).
		WithInputSettings(map[string]any{"text": text}).
		WithOverlay(true)
	_, err = c.Inputs.SetInputSettings(params)
	return err
}

func (s *service) StartReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.StartReplayBuffer()
	return err
}

func (s *service) StopReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.StopReplayBuffer()
	return err
}

func (s *service) SaveReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.SaveReplayBuffer()
	return err
}

func (s *service) GetReplayBufferActive() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := c.Outputs.GetReplayBufferStatus()
	if err != nil {
		return false, err
	}
	return r.OutputActive, nil
}

func (s *service) ToggleVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.ToggleVirtualCam()
	return err
}

func (s *service) StartVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.StartVirtualCam()
	return err
}

func (s *service) StopVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Outputs.StopVirtualCam()
	return err
}

func (s *service) GetVirtualCamActive() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := c.Outputs.GetVirtualCamStatus()
	if err != nil {
		return false, err
	}
	return r.OutputActive, nil
}

func (s *service) GetSpecialSources() (SpecialSources, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return SpecialSources{}, err
	}
	resp, err := c.Inputs.GetSpecialInputs()
	if err != nil {
		return SpecialSources{}, err
	}
	return SpecialSources{
		Desktop1: resp.Desktop1,
		Desktop2: resp.Desktop2,
		Mic1:     resp.Mic1,
		Mic2:     resp.Mic2,
		Mic3:     resp.Mic3,
	}, nil
}

func (s *service) ToggleMute(source string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := inputs.NewToggleInputMuteParams().WithInputName(source)
	_, err = c.Inputs.ToggleInputMute(params)
	return err
}

func (s *service) SetStudioModeEnabled(enabled bool) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Ui.SetStudioModeEnabled(ui.NewSetStudioModeEnabledParams().WithStudioModeEnabled(enabled))
	return err
}

func (s *service) IsStudioModeEnabled() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := c.Ui.GetStudioModeEnabled()
	if err != nil {
		return false, err
	}
	return r.StudioModeEnabled, nil
}

func (s *service) TriggerStudioModeTransition() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = c.Transitions.TriggerStudioModeTransition()
	return err
}
