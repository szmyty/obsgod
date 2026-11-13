package deck

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

const GameScene = "OBSGod Game"
const GameCaptureInput = "OBSGod Game Window"
const IdlePlaceholderInput = "OBSGod Idle Message"
const IdleImageInput = "OBSGod Idle Image"
const IdleVideoInput = "OBSGod Idle Video"

// CaptureVideoStatus contains fixed safe facts, never game IDs or custom text.
type CaptureVideoStatus struct {
	Mode      string    `json:"mode"`
	State     string    `json:"state"`
	IdleStyle string    `json:"idle_style"`
	Frames    string    `json:"frames"`
	Watching  bool      `json:"watching"`
	Updated   time.Time `json:"updated"`
	Message   string    `json:"message"`
}
type captureVideoRecord struct {
	Mode      string    `json:"mode"`
	State     string    `json:"state"`
	IdleStyle string    `json:"idle_style"`
	Frames    string    `json:"frames"`
	Watching  bool      `json:"watching"`
	Updated   time.Time `json:"updated"`
	PID       int       `json:"pid,omitempty"`
}

func captureWatchPaths(p Paths) Paths { p.State = filepath.Join(p.State, "capture-watch"); return p }
func captureVideoPath(p Paths) string {
	return filepath.Join(captureWatchPaths(p).State, "status.json")
}
func videoStatus(record captureVideoRecord) CaptureVideoStatus {
	status := CaptureVideoStatus{Mode: record.Mode, State: record.State, IdleStyle: record.IdleStyle, Frames: record.Frames, Watching: record.Watching, Updated: record.Updated}
	switch record.State {
	case "screen":
		status.Message = "Full display capture is selected"
	case "game":
		status.Message = "App-filtered game video is selected"
	case "idle":
		status.Message = "No usable unambiguous game capture is available; showing the selected idle fallback"
	case "stopped":
		status.Message = "The capture observer is stopped; it never starts output"
	default:
		status.State = "unknown"
		status.Frames = "unknown"
		status.Message = "Game capture status is unconfirmed; no full display fallback is used"
	}
	return status
}
func readCaptureVideoRecord(p Paths) (captureVideoRecord, bool) {
	var record captureVideoRecord
	path := captureVideoPath(p)
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 4096 || readJSON(path, &record) != nil {
		return record, false
	}
	if record.Mode != "screen" && record.Mode != "game" {
		return record, false
	}
	if record.IdleStyle != "black" && record.IdleStyle != "placeholder" && record.IdleStyle != "image" && record.IdleStyle != "video" {
		return record, false
	}
	switch record.State {
	case "screen", "game", "idle", "stopped", "unknown":
	default:
		return record, false
	}
	switch record.Frames {
	case "visible", "placeholder", "unknown":
	default:
		return record, false
	}
	age := time.Since(record.Updated)
	if record.Updated.IsZero() || age > 5*time.Second || age < -time.Second {
		return record, false
	}
	return record, true
}
func ReadCaptureVideoStatus(p Paths) CaptureVideoStatus {
	record, ok := readCaptureVideoRecord(p)
	if !ok {
		return videoStatus(captureVideoRecord{Mode: "unknown", State: "unknown", Frames: "unknown"})
	}
	return videoStatus(record)
}
func writeCaptureVideoStatus(p Paths, s Settings, state, frames string, watching bool, pid int) error {
	return writeJSON(captureVideoPath(p), captureVideoRecord{Mode: s.CaptureModeName(), State: state, IdleStyle: s.IdleStyleName(), Frames: frames, Watching: watching, Updated: time.Now().UTC(), PID: pid})
}
func captureSourceSettings(pipeline string) map[string]any {
	return map[string]any{"pipeline": pipeline, "use_timestamps_video": true, "sync_appsink_video": false, "disable_async_appsink_video": true, "disable_async_appsink_audio": true, "no_buffer": true, "drop_video": true, "stop_on_hide": false, "clear_on_end": true, "restart_on_error": true, "restart_on_eos": true, "restart_timeout": 2000}
}
func sceneVideoWhitelist(s Settings, source string) map[string]bool {
	keep := map[string]bool{GameAudio: true}
	if s.Microphone {
		keep[MicAudio] = true
	}
	if source != "" {
		keep[source] = true
	}
	return keep
}
func ensureIdleVideo(ctx context.Context, c *automation.Client, p Paths, s Settings) error {
	for _, scene := range []string{IdleScene, LiveScene, GameScene} {
		if err := c.EnsureScene(ctx, scene); err != nil {
			return err
		}
	}
	keep := sceneVideoWhitelist(s, "")
	if s.IdleStyleName() == "placeholder" {
		settings := map[string]any{"text": s.IdleMessage(), "font": map[string]any{"face": "Sans Serif", "size": 64, "style": "Regular", "flags": 0}, "color1": uint32(0xFFFFFFFF), "color2": uint32(0xFFFFFFFF), "from_file": false, "text_file": "", "log_mode": false, "outline": false, "drop_shadow": false, "word_wrap": true, "custom_width": 1100}
		if err := c.EnsureInput(ctx, IdleScene, IdlePlaceholderInput, "text_ft2_source_v2", settings); err != nil {
			return err
		}
		if err := c.EnsureSceneItem(ctx, IdleScene, IdlePlaceholderInput); err != nil {
			return err
		}
		if err := c.FitInput(ctx, IdleScene, IdlePlaceholderInput); err != nil {
			return err
		}
		keep[IdlePlaceholderInput] = true
	}
	if s.IdleStyleName() == "image" || s.IdleStyleName() == "video" {
		// Disable stale video before checking/reloading the asset. Missing, changed
		// or unsupported media yields opaque black, never a display capture.
		if err := c.EnableOnlySceneItems(ctx, IdleScene, keep); err != nil {
			return err
		}
		path, err := idleMediaFile(p, s)
		if err == nil {
			name := IdleImageInput
			if s.IdleStyleName() == "image" {
				err = c.EnsureInput(ctx, IdleScene, name, "image_source", map[string]any{"file": path, "unload": true, "linear_alpha": true})
			} else {
				name = IdleVideoInput
				err = c.EnsureMutedMediaInput(ctx, IdleScene, name, map[string]any{"local_file": path, "is_local_file": true, "looping": true, "restart_on_activate": true, "close_when_inactive": true, "clear_on_media_end": true, "hw_decode": false, "buffering_mb": 8, "input_format": ""})
			}
			if err == nil {
				err = c.EnsureSceneItem(ctx, IdleScene, name)
			}
			if err == nil {
				err = c.FitInput(ctx, IdleScene, name)
			}
			if err == nil {
				keep[name] = true
			}
		}
		if err != nil {
			logEvent(p, "idle.media-unavailable")
		} else {
			logEvent(p, "idle.media-ready")
		}
		// Errors loading custom media must not interrupt an already authorized
		// stream. Black remains visible and the next observer cycle may repair it.
	}
	// Disable unexpected video items too: a black fallback must not accidentally
	// reveal a prior manually added display source. Sources are preserved.
	return c.EnableOnlySceneItems(ctx, IdleScene, keep)
}
func gameCapturePipeline(appID uint32) (string, error) {
	if appID == 0 || appID == 769 {
		return "", errors.New("game capture requires an unambiguous non-Steam-UI application")
	}
	return fmt.Sprintf("obsgodgamescopesrc app-id=%d ! queue leaky=downstream max-size-buffers=2 ! videoconvert ! video.", appID), nil
}
func pauseGameCapture(ctx context.Context, c *automation.Client) error {
	if err := c.SetSceneItemEnabledIfPresent(ctx, GameScene, GameCaptureInput, false); err != nil {
		return err
	}
	return c.UpdateInputIfPresent(ctx, GameCaptureInput, map[string]any{"stop_on_hide": true})
}
func switchVideoScene(ctx context.Context, c *automation.Client, current, target string) error {
	if current == target {
		return nil
	}
	return c.SetScene(ctx, target)
}

// gameVideoStep only selects the owned Game/Idle scenes. Failure, ambiguity or
// absent frames never selects the full display source.
func gameVideoStep(ctx context.Context, c *automation.Client, s Settings, game GameIdentity, current string, target *uint32) (string, string, error) {
	if game.State != "running" || game.AppID == 0 || game.AppID == 769 {
		if err := switchVideoScene(ctx, c, current, IdleScene); err != nil {
			return "unknown", "unknown", err
		}
		if *target != 0 {
			if err := pauseGameCapture(ctx, c); err != nil {
				return "unknown", "unknown", err
			}
		}
		*target = 0
		return "idle", "placeholder", nil
	}
	if *target != game.AppID {
		if err := switchVideoScene(ctx, c, current, IdleScene); err != nil {
			return "unknown", "unknown", err
		}
		current = IdleScene
		pipeline, err := gameCapturePipeline(game.AppID)
		if err != nil {
			return "unknown", "unknown", err
		}
		if err := c.EnsureInput(ctx, GameScene, GameCaptureInput, "gstreamer-source", captureSourceSettings(pipeline)); err != nil {
			return "unknown", "unknown", err
		}
		if err := c.EnsureSceneItem(ctx, GameScene, GameCaptureInput); err != nil {
			return "unknown", "unknown", err
		}
		if err := c.FitInput(ctx, GameScene, GameCaptureInput); err != nil {
			return "unknown", "unknown", err
		}
		if err := c.EnableOnlySceneItems(ctx, GameScene, sceneVideoWhitelist(s, GameCaptureInput)); err != nil {
			return "unknown", "unknown", err
		}
		*target = game.AppID
	}
	data, err := c.Screenshot(ctx, GameCaptureInput)
	if err != nil {
		*target = 0
	}
	if err != nil || !NonblankCapture(data) {
		if err := switchVideoScene(ctx, c, current, IdleScene); err != nil {
			return "unknown", "unknown", err
		}
		return "idle", "placeholder", nil
	}
	if err := switchVideoScene(ctx, c, current, GameScene); err != nil {
		return "unknown", "unknown", err
	}
	return "game", "visible", nil
}
func ensureVideo(ctx context.Context, c *automation.Client, p Paths, s Settings) error {
	game := GameIdentity{State: "unknown"}
	if s.CaptureModeName() == "game" {
		game = DiscoverGame(ctx)
	}
	return ensureVideoForGame(ctx, c, p, s, game)
}
func ensureVideoForGame(ctx context.Context, c *automation.Client, p Paths, s Settings, game GameIdentity) error {
	if err := ensureIdleVideo(ctx, c, p, s); err != nil {
		return err
	}
	if s.CaptureModeName() == "screen" {
		if err := pauseGameCapture(ctx, c); err != nil {
			return err
		}
		if err := c.EnsureInput(ctx, LiveScene, CaptureInput, "gstreamer-source", captureSourceSettings(CapturePipeline)); err != nil {
			return err
		}
		if err := c.EnsureSceneItem(ctx, LiveScene, CaptureInput); err != nil {
			return err
		}
		if err := c.FitInput(ctx, LiveScene, CaptureInput); err != nil {
			return err
		}
		if err := c.EnableOnlySceneItems(ctx, LiveScene, sceneVideoWhitelist(s, CaptureInput)); err != nil {
			return err
		}
		if err := c.SetScene(ctx, LiveScene); err != nil {
			return err
		}
		return writeCaptureVideoStatus(p, s, "screen", "unknown", false, 0)
	}
	// Pause any previously configured display capture before selecting game mode.
	if err := c.SetScene(ctx, IdleScene); err != nil {
		return err
	}
	if err := c.SetSceneItemEnabledIfPresent(ctx, LiveScene, CaptureInput, false); err != nil {
		return err
	}
	if err := c.UpdateInputIfPresent(ctx, CaptureInput, map[string]any{"stop_on_hide": true}); err != nil {
		return err
	}
	// Clear the prior game scene's visibility before accepting fresh filtered data.
	if err := c.EnableOnlySceneItems(ctx, GameScene, sceneVideoWhitelist(s, "")); err != nil {
		return err
	}
	if err := pauseGameCapture(ctx, c); err != nil {
		return err
	}
	var target uint32
	state, frames, err := gameVideoStep(ctx, c, s, game, IdleScene, &target)
	if err != nil {
		return err
	}
	return writeCaptureVideoStatus(p, s, state, frames, false, 0)
}
