package deck

import (
	"context"
	"errors"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type MediaSnapshot struct {
	Known        bool                       `json:"known"`
	Recording    automation.RecordingStatus `json:"recording"`
	ReplayActive bool                       `json:"replay_active"`
	Preferences  RecordingPreferences       `json:"preferences"`
	Storage      MediaStorage               `json:"storage"`
	Message      string                     `json:"message"`
}

// MediaStatus never launches OBS and does not turn connection failure into idle.
func MediaStatus(ctx context.Context, p Paths) MediaSnapshot {
	pref, e := RecordingSettings(p)
	result := MediaSnapshot{Preferences: pref, Message: "Local recording/replay state is unknown; inspect managed OBS before starting output"}
	if e == nil {
		result.Storage, _ = inspectMediaStorage(p, pref, false)
	} else {
		result.Message = e.Error()
	}
	process, listener := presence(p)
	if process == "absent" && !listener {
		result.Known = true
		result.Message = "No managed OBS output is running"
		return result
	}
	secret, e := loadCredentials(p)
	if e != nil {
		return result
	}
	ctx, cancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	defer cancel()
	c, e := connect(ctx, secret, 500*time.Millisecond)
	if e != nil {
		return result
	}
	defer c.Close()
	return mediaSnapshotFrom(ctx, p, c, result)
}

// ObserveMedia uses an existing authenticated connection to avoid an extra
// handshake when attaching recording/replay observations to the main snapshot.
func ObserveMedia(ctx context.Context, p Paths, c *automation.Client) MediaSnapshot {
	pref, e := RecordingSettings(p)
	r := MediaSnapshot{Preferences: pref, Message: "Local recording/replay state is unknown"}
	if e != nil {
		r.Message = e.Error()
		return r
	}
	r.Storage, _ = inspectMediaStorage(p, pref, false)
	return mediaSnapshotFrom(ctx, p, c, r)
}
func mediaSnapshotFrom(ctx context.Context, p Paths, c *automation.Client, result MediaSnapshot) MediaSnapshot {
	runtime, e := c.RuntimeStatus(ctx)
	if e != nil || runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return result
	}
	media, e := c.MediaStatus(ctx)
	if e != nil {
		return result
	}
	result.Known = true
	result.Recording = media.Recording
	result.ReplayActive = media.ReplayActive
	result.Message = "Local recording and replay are stopped"
	if media.Recording.Active {
		result.Message = "OBS confirms local recording is active"
	}
	if media.ReplayActive {
		result.Message = "OBS confirms replay buffer is active; use Save replay to keep a local clip"
	}
	if media.Recording.Active && media.ReplayActive {
		result.Message = "OBS confirms local recording and replay buffer are active"
	}
	return result
}

type mediaClient interface {
	Close() error
	RuntimeStatus(context.Context) (automation.RuntimeStatus, error)
	StreamStatus(context.Context) (automation.StreamStatus, error)
	MediaStatus(context.Context) (automation.MediaOutputStatus, error)
	MediaDirectory(context.Context) (string, error)
	ConfigureMediaProfile(context.Context, string, int, int) error
	StartRecording(context.Context) error
	StopRecording(context.Context) (string, error)
	StartReplay(context.Context) error
	StopReplay(context.Context) error
	SaveReplay(context.Context) (string, error)
}
type mediaActionDeps struct {
	load           func(Paths) (Settings, Secrets, error)
	ready          func(context.Context, Paths, Settings, Secrets) (mediaClient, error)
	connect        func(context.Context, Secrets) (mediaClient, error)
	dependencies   func(context.Context) error
	prepareCapture func(context.Context, mediaClient, Paths, Settings) error
	watch          func(Paths) error
	storage        func(Paths, RecordingPreferences, bool) (MediaStorage, error)
	saved          func(Paths, string, string) error
	halt           func(context.Context, mediaClient)
}

func defaultMediaDeps() mediaActionDeps {
	return mediaActionDeps{
		load: Load, ready: func(ctx context.Context, p Paths, s Settings, secret Secrets) (mediaClient, error) {
			return ready(ctx, p, s, secret)
		}, connect: func(ctx context.Context, secret Secrets) (mediaClient, error) {
			return connect(ctx, secret, time.Second)
		}, dependencies: checkDependencies,
		prepareCapture: func(ctx context.Context, c mediaClient, p Paths, s Settings) error {
			client := c.(*automation.Client)
			if s.CaptureModeName() == "screen" && !waitGamescope(ctx) {
				return errors.New("Gamescope capture is unavailable; use game-only with its idle screen or return to Gaming Mode before recording")
			}
			if e := ensureCapture(ctx, client, p, s); e != nil {
				return e
			}
			if s.CaptureModeName() == "screen" {
				capCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
				defer cancel()
				return waitCapture(capCtx, client, p)
			}
			return nil
		}, watch: StartCaptureWatch, storage: inspectMediaStorage, saved: registerMediaFile,
		halt: func(ctx context.Context, c mediaClient) { haltCapture(ctx, c.(*automation.Client)) },
	}
}

// MediaAction requires the caller's normal control lease. Start actions can
// launch the managed OBS profile, but never configure/start a broadcast. Stop
// and save actions never launch OBS. Existing outputs retain their scene/audio.
func MediaAction(ctx context.Context, p Paths, action string) (Result, error) {
	return mediaActionWith(ctx, p, action, defaultMediaDeps())
}
func mediaActionWith(ctx context.Context, p Paths, action string, deps mediaActionDeps) (Result, error) {
	switch action {
	case "record-start", "record-stop", "record-cancel", "replay-start", "replay-stop", "replay-save":
	default:
		return Result{}, errors.New("choose record-start, record-stop, record-cancel, replay-start, replay-stop or replay-save")
	}
	start := action == "record-start" || action == "replay-start"
	var s Settings
	var secret Secrets
	var e error
	if start {
		s, secret, e = deps.load(p)
	} else {
		secret, e = loadCredentials(p)
	}
	if e != nil {
		return Result{}, e
	}
	pref, e := RecordingSettings(p)
	if e != nil {
		return Result{}, e
	}
	var c mediaClient
	if start {
		if e = deps.dependencies(ctx); e != nil {
			return Result{}, e
		}
		if _, e = deps.storage(p, pref, true); e != nil {
			return Result{}, e
		}
		c, e = deps.ready(ctx, p, s, secret)
	} else {
		c, e = deps.connect(ctx, secret)
		if e != nil {
			process, listener := presence(p)
			if process == "absent" && !listener && (action == "record-stop" || action == "record-cancel" || action == "replay-stop") {
				return Result{OK: true, OutputKnown: true, Message: "Managed OBS is offline; no local output is running"}, nil
			}
		}
	}
	if e != nil {
		return Result{}, e
	}
	defer c.Close()
	runtime, e := c.RuntimeStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	if runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return Result{}, errUnmanaged
	}
	media, e := c.MediaStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	stream, e := c.StreamStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	completed := false
	if start {
		defer func() {
			if !completed {
				cleanup, cancel := context.WithTimeout(context.Background(), 2*time.Second)
				defer cancel()
				after, err := c.MediaStatus(cleanup)
				if err == nil && !after.Recording.Active && !after.ReplayActive {
					current, streamErr := c.StreamStatus(cleanup)
					if streamErr == nil && !current.Active {
						deps.halt(cleanup, c)
					}
				}
			}
		}()
	}
	if action == "record-start" && media.Recording.Active {
		return Result{OK: true, Recording: true, Message: "OBS confirms recording is already active"}, nil
	}
	if action == "replay-start" && media.ReplayActive {
		return Result{OK: true, Message: "OBS confirms replay buffer is already active"}, nil
	}
	if start {
		if !media.Recording.Active && !media.ReplayActive {
			if e = c.ConfigureMediaProfile(ctx, mediaDirectory(p, pref), pref.ReplaySeconds, pref.ReplayMemoryMB); e != nil {
				return Result{}, e
			}
		} else {
			directory, dirErr := c.MediaDirectory(ctx)
			if dirErr != nil || directory != mediaDirectory(p, pref) {
				return Result{}, errors.New("local output is using different storage; stop recording/replay before applying recording preferences")
			}
		}
		if !stream.Active && !media.Recording.Active && !media.ReplayActive {
			if e = deps.prepareCapture(ctx, c, p, s); e != nil {
				return Result{}, e
			}
		}
	}
	result := Result{OK: true, Configured: true, Connected: true, OutputKnown: true}
	switch action {
	case "record-start":
		e = c.StartRecording(ctx)
		if e != nil {
			cleanup, cancel := context.WithTimeout(context.Background(), 12*time.Second)
			defer cancel()
			path, stopErr := c.StopRecording(cleanup)
			if stopErr == nil && path != "" {
				_ = deps.saved(p, path, "recording")
			}
			if stopErr != nil {
				return Result{}, errors.New("recording start failed and stop could not be confirmed; inspect managed OBS immediately. Existing media was preserved")
			}
			return Result{}, e
		}
		result.Recording = true
		result.Message = "OBS confirms local recording started; streaming state was not changed"
	case "record-stop", "record-cancel":
		path, stopErr := c.StopRecording(ctx)
		if stopErr != nil {
			return Result{}, stopErr
		}
		if path != "" {
			if e = deps.saved(p, path, "recording"); e != nil {
				return Result{}, e
			}
			result.RecordingPath = path
			result.Message = "Recording finalized and saved locally; streaming and replay were not changed"
		} else {
			result.Message = "OBS confirms recording is already stopped"
		}
		if action == "record-cancel" && path != "" {
			result.Message = "Recording cancelled and its partial clip finalized; no media was deleted"
		}
	case "replay-start":
		e = c.StartReplay(ctx)
		if e != nil {
			cleanup, cancel := context.WithTimeout(context.Background(), 12*time.Second)
			defer cancel()
			if stopErr := c.StopReplay(cleanup); stopErr != nil {
				return Result{}, errors.New("replay start failed and stop could not be confirmed; inspect managed OBS immediately")
			}
			return Result{}, e
		}
		result.Message = "OBS confirms replay buffer started locally; streaming state was not changed"
	case "replay-stop":
		if e = c.StopReplay(ctx); e != nil {
			return Result{}, e
		}
		result.Message = "OBS confirms replay buffer stopped; saved clips were preserved and unsaved buffered frames were discarded"
	case "replay-save":
		if _, e = deps.storage(p, pref, true); e != nil {
			return Result{}, e
		}
		path, saveErr := c.SaveReplay(ctx)
		if saveErr != nil {
			return Result{}, saveErr
		}
		if e = deps.saved(p, path, "replay"); e != nil {
			return Result{}, e
		}
		result.RecordingPath = path
		result.Message = "New replay clip finalized and saved locally; recording and streaming were not changed"
	}
	after, e := c.MediaStatus(ctx)
	if e != nil {
		return Result{}, e
	}
	result.Recording = after.Recording.Active
	if start && s.CaptureModeName() == "game" {
		_ = deps.watch(p)
	}
	if !after.Recording.Active && !after.ReplayActive {
		current, streamErr := c.StreamStatus(ctx)
		if streamErr == nil && !current.Active {
			deps.halt(ctx, c)
		}
	}
	completed = true
	return result, nil
}

// MediaStorageGuard is an opt-in-by-preference local safety limit (default
// 1 GiB reserve), not a recovery/broadcast loop. Call only from the owned active
// output observer. It never starts output, changes a scene with remaining output,
// deletes media or stops the stream. An unmeasurable disk remains unknown.
func MediaStorageGuard(ctx context.Context, p Paths, c *automation.Client) error {
	pref, e := RecordingSettings(p)
	if e != nil {
		return e
	}
	runtime, e := c.RuntimeStatus(ctx)
	if e != nil {
		return e
	}
	if runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return errUnmanaged
	}
	media, e := c.MediaStatus(ctx)
	if e != nil {
		return e
	}
	if !media.Recording.Active && !media.ReplayActive {
		return nil
	}
	dir := mediaDirectory(p, pref)
	if e = checkedMediaDirectory(dir, false); e != nil {
		return e
	}
	free, e := mediaFreeBytes(dir)
	if e != nil {
		return e
	}
	if free >= uint64(pref.ReserveMiB)*1024*1024 {
		return nil
	}
	lockCtx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
	unlock, e := Lock(lockCtx, p)
	cancel()
	if e != nil {
		return nil
	}
	defer unlock()
	// Re-read ownership under the lease as well: external OBS interaction may
	// switch the profile/collection while the disk query or lease is pending.
	runtime, e = c.RuntimeStatus(ctx)
	if e != nil {
		return e
	}
	if runtime.Profile != "OBSGod" || runtime.Collection != "OBSGod" {
		return errUnmanaged
	}
	media, e = c.MediaStatus(ctx)
	if e != nil {
		return e
	}
	if media.Recording.Active {
		path, err := c.StopRecording(ctx)
		if err != nil {
			return err
		}
		if path != "" {
			if err = registerMediaFile(p, path, "recording"); err != nil {
				return err
			}
		}
	}
	if media.ReplayActive {
		if e = c.StopReplay(ctx); e != nil {
			return e
		}
	}
	haltCaptureIfIdle(ctx, c)
	logEvent(p, "media.disk-limit")
	return errors.New(mediaShortfallMessage(free))
}
