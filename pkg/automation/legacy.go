package automation

import (
	"context"
	"errors"
	"github.com/andreykaipov/goobs"
	configrequests "github.com/andreykaipov/goobs/api/requests/config"
	"github.com/andreykaipov/goobs/api/requests/inputs"
	sceneitems "github.com/andreykaipov/goobs/api/requests/sceneitems"
	"github.com/andreykaipov/goobs/api/requests/scenes"
	"github.com/andreykaipov/goobs/api/requests/ui"
)

type LegacyOperation string

const (
	LegacyToggleStream                LegacyOperation = "stream.toggle"
	LegacyStartStream                 LegacyOperation = "stream.start"
	LegacyStopStream                  LegacyOperation = "stream.stop"
	LegacyGetStreamStatus             LegacyOperation = "stream.status"
	LegacyToggleRecording             LegacyOperation = "recording.toggle"
	LegacyStartRecording              LegacyOperation = "recording.start"
	LegacyStopRecording               LegacyOperation = "recording.stop"
	LegacyPauseRecording              LegacyOperation = "recording.pause"
	LegacyResumeRecording             LegacyOperation = "recording.resume"
	LegacyGetRecordingStatus          LegacyOperation = "recording.status"
	LegacyListScenes                  LegacyOperation = "scene.list"
	LegacyGetCurrentScene             LegacyOperation = "scene.get"
	LegacySetCurrentScene             LegacyOperation = "scene.set"
	LegacySetPreviewScene             LegacyOperation = "scene.preview"
	LegacyListSceneCollections        LegacyOperation = "collection.list"
	LegacyGetCurrentSceneCollection   LegacyOperation = "collection.get"
	LegacySetCurrentSceneCollection   LegacyOperation = "collection.set"
	LegacyListSceneItems              LegacyOperation = "scene-item.list"
	LegacySetSceneItemVisible         LegacyOperation = "scene-item.visible.set"
	LegacyToggleSceneItem             LegacyOperation = "scene-item.toggle"
	LegacyGetSceneItemVisibility      LegacyOperation = "scene-item.visible.get"
	LegacyCenterSceneItem             LegacyOperation = "scene-item.center"
	LegacyListProfiles                LegacyOperation = "profile.list"
	LegacyGetCurrentProfile           LegacyOperation = "profile.get"
	LegacySetCurrentProfile           LegacyOperation = "profile.set"
	LegacySetLabelText                LegacyOperation = "label.text"
	LegacyStartReplayBuffer           LegacyOperation = "replay.start"
	LegacyStopReplayBuffer            LegacyOperation = "replay.stop"
	LegacySaveReplayBuffer            LegacyOperation = "replay.save"
	LegacyGetReplayBufferActive       LegacyOperation = "replay.status"
	LegacyToggleVirtualCam            LegacyOperation = "virtual-camera.toggle"
	LegacyStartVirtualCam             LegacyOperation = "virtual-camera.start"
	LegacyStopVirtualCam              LegacyOperation = "virtual-camera.stop"
	LegacyGetVirtualCamActive         LegacyOperation = "virtual-camera.status"
	LegacyGetSpecialSources           LegacyOperation = "source.special"
	LegacyToggleMute                  LegacyOperation = "source.toggle-mute"
	LegacySetStudioModeEnabled        LegacyOperation = "studio.set"
	LegacyIsStudioModeEnabled         LegacyOperation = "studio.status"
	LegacyTriggerStudioModeTransition LegacyOperation = "studio.transition"
)

// Legacy compatibility types describe only documented v0 operations. They do
// not expose raw OBS requests, arbitrary JSON payloads or protocol clients.
type LegacyRequest struct {
	Operation LegacyOperation
	Name      string
	Scene     string
	Names     []string
	Text      string
	Enabled   bool
}
type LegacyOutputStatus struct {
	Active   bool
	Paused   bool
	Timecode string
}
type LegacySpecialSources struct {
	Desktop1 string
	Desktop2 string
	Mic1     string
	Mic2     string
	Mic3     string
}
type LegacyItemVisibility struct {
	Name    string
	Visible bool
}
type LegacyResult struct {
	Names      []string
	Current    string
	Output     LegacyOutputStatus
	Active     bool
	Sources    LegacySpecialSources
	Visibility []LegacyItemVisibility
}

// Legacy preserves acknowledged-request semantics for the explicit compatibility
// facade. Confirmed-state public methods remain separate and unchanged.
func (c *Client) Legacy(ctx context.Context, r LegacyRequest) (LegacyResult, error) {
	s := compatibilitySession{client: c, ctx: ctx}
	switch r.Operation {
	case LegacyToggleStream:
		return LegacyResult{}, s.ToggleStream()
	case LegacyStartStream:
		return LegacyResult{}, s.StartStream()
	case LegacyStopStream:
		return LegacyResult{}, s.StopStream()
	case LegacyGetStreamStatus:
		v, err := s.GetStreamStatus()
		return LegacyResult{Output: v}, err
	case LegacyToggleRecording:
		return LegacyResult{}, s.ToggleRecording()
	case LegacyStartRecording:
		return LegacyResult{}, s.StartRecording()
	case LegacyStopRecording:
		return LegacyResult{}, s.StopRecording()
	case LegacyPauseRecording:
		return LegacyResult{}, s.PauseRecording()
	case LegacyResumeRecording:
		return LegacyResult{}, s.ResumeRecording()
	case LegacyGetRecordingStatus:
		v, err := s.GetRecordingStatus()
		return LegacyResult{Output: v}, err
	case LegacyListScenes:
		v, err := s.ListScenes()
		return LegacyResult{Names: v}, err
	case LegacyGetCurrentScene:
		v, err := s.GetCurrentScene()
		return LegacyResult{Current: v}, err
	case LegacySetCurrentScene:
		return LegacyResult{}, s.SetCurrentScene(r.Name)
	case LegacySetPreviewScene:
		return LegacyResult{}, s.SetPreviewScene(r.Name)
	case LegacyListSceneCollections:
		v, err := s.ListSceneCollections()
		return LegacyResult{Names: v}, err
	case LegacyGetCurrentSceneCollection:
		v, err := s.GetCurrentSceneCollection()
		return LegacyResult{Current: v}, err
	case LegacySetCurrentSceneCollection:
		return LegacyResult{}, s.SetCurrentSceneCollection(r.Name)
	case LegacyListSceneItems:
		v, err := s.ListSceneItems(r.Scene)
		return LegacyResult{Names: v}, err
	case LegacySetSceneItemVisible:
		return LegacyResult{}, s.SetSceneItemVisible(r.Enabled, r.Scene, r.Names...)
	case LegacyToggleSceneItem:
		return LegacyResult{}, s.ToggleSceneItem(r.Scene, r.Names...)
	case LegacyGetSceneItemVisibility:
		v, err := s.GetSceneItemVisibility(r.Scene, r.Names...)
		return LegacyResult{Visibility: v}, err
	case LegacyCenterSceneItem:
		return LegacyResult{}, s.CenterSceneItem(r.Scene, r.Names...)
	case LegacyListProfiles:
		v, err := s.ListProfiles()
		return LegacyResult{Names: v}, err
	case LegacyGetCurrentProfile:
		v, err := s.GetCurrentProfile()
		return LegacyResult{Current: v}, err
	case LegacySetCurrentProfile:
		return LegacyResult{}, s.SetCurrentProfile(r.Name)
	case LegacySetLabelText:
		return LegacyResult{}, s.SetLabelText(r.Name, r.Text)
	case LegacyStartReplayBuffer:
		return LegacyResult{}, s.StartReplayBuffer()
	case LegacyStopReplayBuffer:
		return LegacyResult{}, s.StopReplayBuffer()
	case LegacySaveReplayBuffer:
		return LegacyResult{}, s.SaveReplayBuffer()
	case LegacyGetReplayBufferActive:
		v, err := s.GetReplayBufferActive()
		return LegacyResult{Active: v}, err
	case LegacyToggleVirtualCam:
		return LegacyResult{}, s.ToggleVirtualCam()
	case LegacyStartVirtualCam:
		return LegacyResult{}, s.StartVirtualCam()
	case LegacyStopVirtualCam:
		return LegacyResult{}, s.StopVirtualCam()
	case LegacyGetVirtualCamActive:
		v, err := s.GetVirtualCamActive()
		return LegacyResult{Active: v}, err
	case LegacyGetSpecialSources:
		v, err := s.GetSpecialSources()
		return LegacyResult{Sources: v}, err
	case LegacyToggleMute:
		return LegacyResult{}, s.ToggleMute(r.Name)
	case LegacySetStudioModeEnabled:
		return LegacyResult{}, s.SetStudioModeEnabled(r.Enabled)
	case LegacyIsStudioModeEnabled:
		v, err := s.IsStudioModeEnabled()
		return LegacyResult{Active: v}, err
	case LegacyTriggerStudioModeTransition:
		return LegacyResult{}, s.TriggerStudioModeTransition()
	default:
		return LegacyResult{}, errors.New("unsupported legacy operation")
	}
}

type compatibilitySession struct {
	client *Client
	ctx    context.Context
}

func (s compatibilitySession) clientOrConnect() (*goobs.Client, error) {
	if err := s.ctx.Err(); err != nil {
		return nil, err
	}
	return s.client.obs, nil
}
func legacyRequest[P, T any](ctx context.Context, name string, f func(...P) (T, error), args ...P) (T, error) {
	return request(ctx, name, func() (T, error) { return f(args...) })
}

func (s compatibilitySession) ToggleStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "ToggleStream", c.Stream.ToggleStream)
	return err
}

func (s compatibilitySession) StartStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StartStream", c.Stream.StartStream)
	return err
}

func (s compatibilitySession) StopStream() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StopStream", c.Stream.StopStream)
	return err
}

func (s compatibilitySession) GetStreamStatus() (LegacyOutputStatus, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return LegacyOutputStatus{}, err
	}
	r, err := legacyRequest(s.ctx, "GetStreamStatus", c.Stream.GetStreamStatus)
	if err != nil {
		return LegacyOutputStatus{}, err
	}
	return LegacyOutputStatus{Active: r.OutputActive, Timecode: r.OutputTimecode}, nil
}

func (s compatibilitySession) ToggleRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "ToggleRecord", c.Record.ToggleRecord)
	return err
}

func (s compatibilitySession) StartRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StartRecord", c.Record.StartRecord)
	return err
}

func (s compatibilitySession) StopRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StopRecord", c.Record.StopRecord)
	return err
}

func (s compatibilitySession) PauseRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "PauseRecord", c.Record.PauseRecord)
	return err
}

func (s compatibilitySession) ResumeRecording() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "ResumeRecord", c.Record.ResumeRecord)
	return err
}

func (s compatibilitySession) GetRecordingStatus() (LegacyOutputStatus, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return LegacyOutputStatus{}, err
	}
	r, err := legacyRequest(s.ctx, "GetRecordStatus", c.Record.GetRecordStatus)
	if err != nil {
		return LegacyOutputStatus{}, err
	}
	return LegacyOutputStatus{Active: r.OutputActive, Paused: r.OutputPaused, Timecode: r.OutputTimecode}, nil
}

func (s compatibilitySession) ListScenes() ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	r, err := legacyRequest(s.ctx, "GetSceneList", c.Scenes.GetSceneList)
	if err != nil {
		return nil, err
	}

	scenes := make([]string, 0, len(r.Scenes))
	for _, scene := range r.Scenes {
		scenes = append(scenes, scene.SceneName)
	}
	return scenes, nil
}

func (s compatibilitySession) GetCurrentScene() (string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return "", err
	}
	r, err := legacyRequest(s.ctx, "GetCurrentProgramScene", c.Scenes.GetCurrentProgramScene)
	if err != nil {
		return "", err
	}
	return r.SceneName, nil
}

func (s compatibilitySession) SetCurrentScene(scene string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := scenes.NewSetCurrentProgramSceneParams().WithSceneName(scene)
	_, err = legacyRequest(s.ctx, "SetCurrentProgramScene", c.Scenes.SetCurrentProgramScene, params)
	return err
}

func (s compatibilitySession) SetPreviewScene(scene string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := scenes.NewSetCurrentPreviewSceneParams().WithSceneName(scene)
	_, err = legacyRequest(s.ctx, "SetCurrentPreviewScene", c.Scenes.SetCurrentPreviewScene, params)
	return err
}

func (s compatibilitySession) ListSceneCollections() ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	r, err := legacyRequest(s.ctx, "GetSceneCollectionList", c.Config.GetSceneCollectionList)
	if err != nil {
		return nil, err
	}
	collections := make([]string, 0, len(r.SceneCollections))
	collections = append(collections, r.SceneCollections...)
	return collections, nil
}

func (s compatibilitySession) GetCurrentSceneCollection() (string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return "", err
	}
	r, err := legacyRequest(s.ctx, "GetSceneCollectionList", c.Config.GetSceneCollectionList)
	if err != nil {
		return "", err
	}
	return r.CurrentSceneCollectionName, nil
}

func (s compatibilitySession) SetCurrentSceneCollection(collection string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := configrequests.NewSetCurrentSceneCollectionParams().WithSceneCollectionName(collection)
	_, err = legacyParameter(s.ctx, "SetCurrentSceneCollection", c.Config.SetCurrentSceneCollection, params)
	return err
}

func (s compatibilitySession) ListSceneItems(scene string) ([]string, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	params := sceneitems.NewGetSceneItemListParams().WithSceneName(scene)
	resp, err := legacyRequest(s.ctx, "GetSceneItemList", c.SceneItems.GetSceneItemList, params)
	if err != nil {
		return nil, err
	}

	items := make([]string, 0, len(resp.SceneItems))
	for _, item := range resp.SceneItems {
		items = append(items, item.SourceName)
	}
	return items, nil
}

func (s compatibilitySession) getSceneItemID(c *goobs.Client, scene, item string) (int, error) {
	params := sceneitems.NewGetSceneItemIdParams().WithSceneName(scene).WithSourceName(item)
	resp, err := legacyParameter(s.ctx, "GetSceneItemId", c.SceneItems.GetSceneItemId, params)
	if err != nil {
		return 0, err
	}
	return resp.SceneItemId, nil
}

func (s compatibilitySession) SetSceneItemVisible(visible bool, scene string, items ...string) error {
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
		_, err = legacyParameter(s.ctx, "SetSceneItemEnabled", c.SceneItems.SetSceneItemEnabled, params)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s compatibilitySession) ToggleSceneItem(scene string, items ...string) error {
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
		resp, err := legacyParameter(s.ctx, "GetSceneItemEnabled", c.SceneItems.GetSceneItemEnabled, params)
		if err != nil {
			return err
		}
		if err := s.SetSceneItemVisible(!resp.SceneItemEnabled, scene, item); err != nil {
			return err
		}
	}
	return nil
}

func (s compatibilitySession) GetSceneItemVisibility(scene string, items ...string) ([]LegacyItemVisibility, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return nil, err
	}
	visibility := make([]LegacyItemVisibility, 0, len(items))
	for _, item := range items {
		id, err := s.getSceneItemID(c, scene, item)
		if err != nil {
			return nil, err
		}
		params := sceneitems.NewGetSceneItemEnabledParams().WithSceneName(scene).WithSceneItemId(id)
		resp, err := legacyParameter(s.ctx, "GetSceneItemEnabled", c.SceneItems.GetSceneItemEnabled, params)
		if err != nil {
			return nil, err
		}
		visibility = append(visibility, LegacyItemVisibility{Name: item, Visible: resp.SceneItemEnabled})
	}
	return visibility, nil
}

func (s compatibilitySession) CenterSceneItem(scene string, items ...string) error {
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
		transformResp, err := legacyParameter(s.ctx, "GetSceneItemTransform", c.SceneItems.GetSceneItemTransform, transformParams)
		if err != nil {
			return err
		}
		videoResp, err := legacyRequest(s.ctx, "GetVideoSettings", c.Config.GetVideoSettings)
		if err != nil {
			return err
		}

		transform := transformResp.SceneItemTransform
		transform.PositionX = videoResp.BaseWidth / 2

		setParams := sceneitems.NewSetSceneItemTransformParams().
			WithSceneName(scene).
			WithSceneItemId(id).
			WithSceneItemTransform(transform)
		_, err = legacyParameter(s.ctx, "SetSceneItemTransform", c.SceneItems.SetSceneItemTransform, setParams)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s compatibilitySession) ListProfiles() ([]string, error) {
	v, err := s.client.ProfileInventory(s.ctx)
	if err != nil {
		return nil, err
	}
	return append([]string{}, v.Profiles...), nil
}

func (s compatibilitySession) GetCurrentProfile() (string, error) {
	v, err := s.client.ProfileInventory(s.ctx)
	if err != nil {
		return "", err
	}
	return v.Current, nil
}

func (s compatibilitySession) SetCurrentProfile(profile string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := configrequests.NewSetCurrentProfileParams().WithProfileName(profile)
	_, err = legacyParameter(s.ctx, "SetCurrentProfile", c.Config.SetCurrentProfile, params)
	return err
}

func (s compatibilitySession) SetLabelText(source, text string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := inputs.NewSetInputSettingsParams().
		WithInputName(source).
		WithInputSettings(map[string]any{"text": text}).
		WithOverlay(true)
	_, err = legacyParameter(s.ctx, "SetInputSettings", c.Inputs.SetInputSettings, params)
	return err
}

func (s compatibilitySession) StartReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StartReplayBuffer", c.Outputs.StartReplayBuffer)
	return err
}

func (s compatibilitySession) StopReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StopReplayBuffer", c.Outputs.StopReplayBuffer)
	return err
}

func (s compatibilitySession) SaveReplayBuffer() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "SaveReplayBuffer", c.Outputs.SaveReplayBuffer)
	return err
}

func (s compatibilitySession) GetReplayBufferActive() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := legacyRequest(s.ctx, "GetReplayBufferStatus", c.Outputs.GetReplayBufferStatus)
	if err != nil {
		return false, err
	}
	return r.OutputActive, nil
}

func (s compatibilitySession) ToggleVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "ToggleVirtualCam", c.Outputs.ToggleVirtualCam)
	return err
}

func (s compatibilitySession) StartVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StartVirtualCam", c.Outputs.StartVirtualCam)
	return err
}

func (s compatibilitySession) StopVirtualCam() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "StopVirtualCam", c.Outputs.StopVirtualCam)
	return err
}

func (s compatibilitySession) GetVirtualCamActive() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := legacyRequest(s.ctx, "GetVirtualCamStatus", c.Outputs.GetVirtualCamStatus)
	if err != nil {
		return false, err
	}
	return r.OutputActive, nil
}

func (s compatibilitySession) GetSpecialSources() (LegacySpecialSources, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return LegacySpecialSources{}, err
	}
	resp, err := legacyRequest(s.ctx, "GetSpecialInputs", c.Inputs.GetSpecialInputs)
	if err != nil {
		return LegacySpecialSources{}, err
	}
	return LegacySpecialSources{
		Desktop1: resp.Desktop1,
		Desktop2: resp.Desktop2,
		Mic1:     resp.Mic1,
		Mic2:     resp.Mic2,
		Mic3:     resp.Mic3,
	}, nil
}

func (s compatibilitySession) ToggleMute(source string) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	params := inputs.NewToggleInputMuteParams().WithInputName(source)
	_, err = legacyRequest(s.ctx, "ToggleInputMute", c.Inputs.ToggleInputMute, params)
	return err
}

func (s compatibilitySession) SetStudioModeEnabled(enabled bool) error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyParameter(s.ctx, "SetStudioModeEnabled", c.Ui.SetStudioModeEnabled, ui.NewSetStudioModeEnabledParams().WithStudioModeEnabled(enabled))
	return err
}

func (s compatibilitySession) IsStudioModeEnabled() (bool, error) {
	c, err := s.clientOrConnect()
	if err != nil {
		return false, err
	}
	r, err := legacyRequest(s.ctx, "GetStudioModeEnabled", c.Ui.GetStudioModeEnabled)
	if err != nil {
		return false, err
	}
	return r.StudioModeEnabled, nil
}

func (s compatibilitySession) TriggerStudioModeTransition() error {
	c, err := s.clientOrConnect()
	if err != nil {
		return err
	}
	_, err = legacyRequest(s.ctx, "TriggerStudioModeTransition", c.Transitions.TriggerStudioModeTransition)
	return err
}

func legacyParameter[P, T any](ctx context.Context, name string, f func(P) (T, error), arg P) (T, error) {
	return request(ctx, name, func() (T, error) { return f(arg) })
}
