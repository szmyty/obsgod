//go:build linux

package deck

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestIdleImageAndMissingMediaRemainPrivateFallbacks(t *testing.T) {
	f := newVideoFixture(t)
	c, _ := videoClient(t, f)
	p := testPaths(t)
	source := filepath.Join(t.TempDir(), "image.png")
	writeIdlePNG(t, source)
	name, err := importIdleMedia(p, source, "image")
	if err != nil {
		t.Fatal(err)
	}
	s := DefaultSettings()
	s.CaptureMode = "game"
	s.IdleStyle = "image"
	s.IdleMedia = name
	if err = ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	if !f.scenes[IdleScene][IdleImageInput].enabled || f.scenes[IdleScene]["unexpected display"].enabled {
		t.Fatal("image did not exclude other video")
	}
	if f.inputs[IdleImageInput].kind != "image_source" || f.inputs[IdleImageInput].settings["file"] != filepath.Join(idleMediaDirectory(p), name) {
		t.Fatal("image did not use owned local copy")
	}
	f.mu.Unlock()
	if err = os.Remove(filepath.Join(idleMediaDirectory(p), name)); err != nil {
		t.Fatal(err)
	}
	if err = ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err != nil {
		t.Fatal("missing media interrupted output", err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.scenes[IdleScene][IdleImageInput].enabled {
		t.Fatal("missing media kept stale image visible")
	}
	assertNoOutputCommands(t, f)
}
func TestIdleVideoIsDisabledThenMutedBeforeBecomingVisible(t *testing.T) {
	f := newVideoFixture(t)
	c, _ := videoClient(t, f)
	p := testPaths(t)
	source := filepath.Join(t.TempDir(), "video.mp4")
	// Header-only fixture exercises wire safety, not decoding/playback proof.
	if err := os.WriteFile(source, []byte{0, 0, 0, 24, 'f', 't', 'y', 'p', 'i', 's', 'o', 'm', 0, 0, 0, 0, 'i', 's', 'o', 'm', 'm', 'p', '4', '2'}, 0600); err != nil {
		t.Fatal(err)
	}
	name, err := importIdleMedia(p, source, "video")
	if err != nil {
		t.Fatal(err)
	}
	s := DefaultSettings()
	s.CaptureMode = "game"
	s.IdleStyle = "video"
	s.IdleMedia = name
	s.Microphone = true
	if err = ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	created, muted, enabled := -1, -1, -1
	for i, r := range f.requests {
		if r.Type == "CreateInput" && r.Data["inputName"] == IdleVideoInput {
			created = i
			if r.Data["sceneItemEnabled"] != false {
				t.Fatal("media created with live audio enabled")
			}
		}
		if r.Type == "SetInputMute" && r.Data["inputName"] == IdleVideoInput {
			if r.Data["inputMuted"] != true {
				t.Fatal("video was unmuted")
			}
			muted = i
		}
		if r.Type == "SetSceneItemEnabled" && r.Data["sceneItemEnabled"] == true {
			if id, ok := r.Data["sceneItemId"].(float64); ok && int(id) == f.scenes[IdleScene][IdleVideoInput].id {
				enabled = i
			}
		}
	}
	if created < 0 || muted <= created || enabled <= muted {
		t.Fatalf("wrong muted creation order create%d mute%d enable%d", created, muted, enabled)
	}
	input := f.inputs[IdleVideoInput]
	if input.kind != "ffmpeg_source" || input.settings["is_local_file"] != true || input.settings["looping"] != true {
		t.Fatal("video settings not bounded local looping", input)
	}
	assertNoOutputCommands(t, f)
}
