package automation

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"time"

	"github.com/andreykaipov/goobs/api/requests/config"
)

// RecordingStatus is an observation of OBS's local muxer. It does not imply a
// broadcast or confirm that a provider/viewer has received anything.
type RecordingStatus struct {
	Active   bool    `json:"active"`
	Paused   bool    `json:"paused"`
	Bytes    float64 `json:"bytes"`
	Duration float64 `json:"duration_ms"`
}

type MediaOutputStatus struct {
	Recording    RecordingStatus `json:"recording"`
	ReplayActive bool            `json:"replay_active"`
}

func (c *Client) RecordingStatus(ctx context.Context) (RecordingStatus, error) {
	r, e := empty(ctx, "GetRecordStatus", c.obs.Record.GetRecordStatus)
	if e != nil {
		return RecordingStatus{}, e
	}
	if e = workflowKnownOutput(r.GetRaw(), "outputActive"); e != nil {
		return RecordingStatus{}, e
	}
	return RecordingStatus{Active: r.OutputActive, Paused: r.OutputPaused, Bytes: r.OutputBytes, Duration: r.OutputDuration}, nil
}
func (c *Client) ReplayActive(ctx context.Context) (bool, error) {
	r, e := empty(ctx, "GetReplayBufferStatus", c.obs.Outputs.GetReplayBufferStatus)
	if workflowOutputUnavailable(e, "GetReplayBufferStatus") {
		return false, nil
	}
	if e != nil {
		return false, e
	}
	if e = workflowKnownOutput(r.GetRaw(), "outputActive"); e != nil {
		return false, e
	}
	return r.OutputActive, nil
}
func (c *Client) MediaStatus(ctx context.Context) (MediaOutputStatus, error) {
	r, e := c.RecordingStatus(ctx)
	if e != nil {
		return MediaOutputStatus{}, e
	}
	replay, e := c.ReplayActive(ctx)
	if e != nil {
		return MediaOutputStatus{}, e
	}
	return MediaOutputStatus{Recording: r, ReplayActive: replay}, nil
}

// StartReplay only enables a local replay buffer. It never configures or starts
// streaming. A request acknowledgement is followed by a confirmed state read.
func (c *Client) StartReplay(ctx context.Context) error {
	active, e := c.ReplayActive(ctx)
	if e != nil || active {
		return e
	}
	if _, e = empty(ctx, "StartReplayBuffer", c.obs.Outputs.StartReplayBuffer); e != nil {
		return e
	}
	return c.waitReplay(ctx, true)
}
func (c *Client) StopReplay(ctx context.Context) error {
	active, e := c.ReplayActive(ctx)
	if e != nil || !active {
		return e
	}
	if _, e = empty(ctx, "StopReplayBuffer", c.obs.Outputs.StopReplayBuffer); e != nil {
		return e
	}
	return c.waitReplay(ctx, false)
}
func (c *Client) waitReplay(ctx context.Context, want bool) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	for {
		active, e := c.ReplayActive(ctx)
		if e != nil {
			return e
		}
		if active == want {
			return nil
		}
		if e = pause(ctx, 100*time.Millisecond); e != nil {
			return e
		}
	}
}
func (c *Client) lastReplay(ctx context.Context) (string, error) {
	r, e := empty(ctx, "GetLastReplayBufferReplay", c.obs.Outputs.GetLastReplayBufferReplay)
	if e != nil {
		return "", e
	}
	return r.SavedReplayPath, nil
}

// SaveReplay waits for a *new* finalized replay path. Returning a previous save
// would incorrectly announce success while OBS is still asynchronously muxing.
func (c *Client) SaveReplay(ctx context.Context) (string, error) {
	active, e := c.ReplayActive(ctx)
	if e != nil {
		return "", e
	}
	if !active {
		return "", errors.New("start the local replay buffer before saving a clip")
	}
	previous, e := c.lastReplay(ctx)
	if e != nil {
		var requestErr *RequestError
		if !errors.As(e, &requestErr) || (requestErr.Code != 600 && requestErr.Code != 601) {
			return "", e
		}
	}
	if _, e = empty(ctx, "SaveReplayBuffer", c.obs.Outputs.SaveReplayBuffer); e != nil {
		return "", e
	}
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	for {
		path, err := c.lastReplay(ctx)
		if err == nil && path != "" && path != previous {
			return path, nil
		}
		if err != nil {
			var re *RequestError
			if !errors.As(err, &re) || (re.Code != 600 && re.Code != 601) {
				return "", err
			}
		}
		if err = pause(ctx, 100*time.Millisecond); err != nil {
			return "", errors.New("OBS has not confirmed a new replay file; existing clips were preserved, inspect the recording folder before retrying")
		}
	}
}

func (c *Client) MediaDirectory(ctx context.Context) (string, error) {
	r, e := empty(ctx, "GetRecordDirectory", c.obs.Config.GetRecordDirectory)
	if e != nil {
		return "", e
	}
	return r.RecordDirectory, nil
}

// ConfigureMediaProfile changes only recording/replay preferences while their
// outputs are idle. In particular it does not touch streaming service settings,
// encoder settings, gains, mute state or the selected scene.
func (c *Client) ConfigureMediaProfile(ctx context.Context, directory string, seconds, memoryMB int) error {
	if directory == "" || strings.ContainsAny(directory, "\r\n\x00") || seconds < 15 || seconds > 120 || memoryMB < 64 || memoryMB > 512 {
		return errors.New("invalid local recording/replay preferences")
	}
	state, e := c.MediaStatus(ctx)
	if e != nil {
		return e
	}
	if state.Recording.Active || state.ReplayActive {
		return errors.New("stop local recording and replay before changing their storage or buffer settings")
	}
	if _, e = request(ctx, "SetRecordDirectory", func() (*config.SetRecordDirectoryResponse, error) {
		return c.obs.Config.SetRecordDirectory(config.NewSetRecordDirectoryParams().WithRecordDirectory(directory))
	}); e != nil {
		return e
	}
	for _, item := range []struct{ category, name, value string }{{"AdvOut", "RecRB", "true"}, {"AdvOut", "RecRBTime", strconv.Itoa(seconds)}, {"AdvOut", "RecRBSize", strconv.Itoa(memoryMB)}, {"Output", "FilenameFormatting", "DeckyStream-%CCYY-%MM-%DD_%hh-%mm-%ss"}} {
		_, e = request(ctx, "SetProfileParameter", func() (*config.SetProfileParameterResponse, error) {
			return c.obs.Config.SetProfileParameter(config.NewSetProfileParameterParams().WithParameterCategory(item.category).WithParameterName(item.name).WithParameterValue(item.value))
		})
		if e != nil {
			return e
		}
	}
	return nil
}
