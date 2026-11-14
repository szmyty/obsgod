package v1

import (
	"context"
	"github.com/szmyty/obsgod/pkg/automation"
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

// Legacy is an explicit v0 compatibility surface. Successful mutations mean
// request acknowledgement, not confirmed completion. It cannot accept arbitrary
// protocol requests. Normal v1 operations retain their stronger observations.
// Approval must be supplied for this invocation; context carries no authority.
func (c *Client) Legacy(ctx context.Context, r LegacyRequest, a Approval) (LegacyResult, error) {
	switch r.Operation {
	case LegacyToggleStream:
		if !a.Streaming {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStartStream:
		if !a.Streaming {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStopStream:
		if !a.Streaming {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyGetStreamStatus:
	case LegacyToggleRecording:
		if !a.Recording {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStartRecording:
		if !a.Recording {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStopRecording:
		if !a.Recording {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyPauseRecording:
		if !a.Recording {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyResumeRecording:
		if !a.Recording {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyGetRecordingStatus:
	case LegacyListScenes:
	case LegacyGetCurrentScene:
	case LegacySetCurrentScene:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacySetPreviewScene:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyListSceneCollections:
	case LegacyGetCurrentSceneCollection:
	case LegacySetCurrentSceneCollection:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyListSceneItems:
	case LegacySetSceneItemVisible:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyToggleSceneItem:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyGetSceneItemVisibility:
	case LegacyCenterSceneItem:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyListProfiles:
	case LegacyGetCurrentProfile:
	case LegacySetCurrentProfile:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacySetLabelText:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStartReplayBuffer:
		if !a.ReplayBuffer {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStopReplayBuffer:
		if !a.ReplayBuffer {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacySaveReplayBuffer:
		if !a.ReplayBuffer {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyGetReplayBufferActive:
	case LegacyToggleVirtualCam:
		if !a.VirtualCamera {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStartVirtualCam:
		if !a.VirtualCamera {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyStopVirtualCam:
		if !a.VirtualCamera {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyGetVirtualCamActive:
	case LegacyGetSpecialSources:
	case LegacyToggleMute:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacySetStudioModeEnabled:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	case LegacyIsStudioModeEnabled:
	case LegacyTriggerStudioModeTransition:
		if !a.Settings {
			return LegacyResult{}, fail("request", ApprovalRequired)
		}
	default:
		return LegacyResult{}, fail("request", InvalidInput)
	}
	r.Names = append([]string{}, r.Names...)
	return run(ctx, c, "request", func(ctx context.Context) (LegacyResult, error) {
		value, err := c.backend.Legacy(ctx, automation.LegacyRequest{Operation: automation.LegacyOperation(r.Operation), Name: r.Name, Scene: r.Scene, Names: r.Names, Text: r.Text, Enabled: r.Enabled})
		if err != nil {
			return LegacyResult{}, err
		}
		result := LegacyResult{Names: append([]string{}, value.Names...), Current: value.Current,
			Output: LegacyOutputStatus{Active: value.Output.Active, Paused: value.Output.Paused, Timecode: value.Output.Timecode}, Active: value.Active,
			Sources:    LegacySpecialSources{Desktop1: value.Sources.Desktop1, Desktop2: value.Sources.Desktop2, Mic1: value.Sources.Mic1, Mic2: value.Sources.Mic2, Mic3: value.Sources.Mic3},
			Visibility: make([]LegacyItemVisibility, 0, len(value.Visibility))}
		for _, v := range value.Visibility {
			result.Visibility = append(result.Visibility, LegacyItemVisibility{Name: v.Name, Visible: v.Visible})
		}
		return result, nil
	})
}
