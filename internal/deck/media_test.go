package deck

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/szmyty/obsgod/pkg/automation"
)

type fakeMediaClient struct {
	media                                                                         automation.MediaOutputStatus
	stream                                                                        automation.StreamStatus
	directory                                                                     string
	capture, configs, recordStarts, recordStops, replayStarts, replayStops, halts int
	startErr                                                                      error
	savedPath                                                                     string
	unmanaged                                                                     bool
}

func (f *fakeMediaClient) Close() error { return nil }
func (f *fakeMediaClient) RuntimeStatus(context.Context) (automation.RuntimeStatus, error) {
	if f.unmanaged {
		return automation.RuntimeStatus{Profile: "Ordinary OBS", Collection: "Ordinary"}, nil
	}
	return automation.RuntimeStatus{Profile: "OBSGod", Collection: "OBSGod"}, nil
}
func (f *fakeMediaClient) StreamStatus(context.Context) (automation.StreamStatus, error) {
	return f.stream, nil
}
func (f *fakeMediaClient) MediaStatus(context.Context) (automation.MediaOutputStatus, error) {
	return f.media, nil
}
func (f *fakeMediaClient) MediaDirectory(context.Context) (string, error) { return f.directory, nil }
func (f *fakeMediaClient) ConfigureMediaProfile(_ context.Context, directory string, _, _ int) error {
	f.configs++
	f.directory = directory
	return nil
}
func (f *fakeMediaClient) StartRecording(context.Context) error {
	f.recordStarts++
	f.media.Recording.Active = true
	return f.startErr
}
func (f *fakeMediaClient) StopRecording(context.Context) (string, error) {
	f.recordStops++
	f.media.Recording.Active = false
	return f.savedPath, nil
}
func (f *fakeMediaClient) StartReplay(context.Context) error {
	f.replayStarts++
	f.media.ReplayActive = true
	return f.startErr
}
func (f *fakeMediaClient) StopReplay(context.Context) error {
	f.replayStops++
	f.media.ReplayActive = false
	return nil
}
func (f *fakeMediaClient) SaveReplay(context.Context) (string, error) { return f.savedPath, nil }
func fakeMediaDeps(p Paths, f *fakeMediaClient, saved *[]string) mediaActionDeps {
	return mediaActionDeps{
		load:    func(p Paths) (Settings, Secrets, error) { return Settings{CaptureMode: "game"}, Secrets{}, nil },
		ready:   func(context.Context, Paths, Settings, Secrets) (mediaClient, error) { return f, nil },
		connect: func(context.Context, Secrets) (mediaClient, error) { return f, nil }, dependencies: func(context.Context) error { return nil },
		prepareCapture: func(context.Context, mediaClient, Paths, Settings) error { f.capture++; return nil }, watch: func(Paths) error { return nil },
		storage: func(Paths, RecordingPreferences, bool) (MediaStorage, error) {
			return MediaStorage{Permission: "ready"}, nil
		},
		saved: func(_ Paths, path, kind string) error { *saved = append(*saved, kind+":"+path); return nil }, halt: func(context.Context, mediaClient) { f.halts++ },
	}
}
func TestMediaStartCoexistsWithoutChangingLiveScene(t *testing.T) {
	p := testPaths(t)
	f := &fakeMediaClient{stream: automation.StreamStatus{Active: true}}
	saved := []string{}
	deps := fakeMediaDeps(p, f, &saved)
	result, e := mediaActionWith(context.Background(), p, "record-start", deps)
	if e != nil || !result.Recording {
		t.Fatal(result, e)
	}
	if f.capture != 0 || f.recordStarts != 1 || f.halts != 0 || !f.stream.Active {
		t.Fatal("starting recording disrupted live output", f)
	}
	if _, e = mediaActionWith(context.Background(), p, "record-start", deps); e != nil || f.recordStarts != 1 {
		t.Fatal("duplicate recording start was not coalesced", e, f)
	}
}
func TestReplayCoexistsWithRecordingAndDoesNotRewriteItsProfile(t *testing.T) {
	p := testPaths(t)
	f := &fakeMediaClient{directory: p.Videos, media: automation.MediaOutputStatus{Recording: automation.RecordingStatus{Active: true}}}
	saved := []string{}
	if _, e := mediaActionWith(context.Background(), p, "replay-start", fakeMediaDeps(p, f, &saved)); e != nil {
		t.Fatal(e)
	}
	if f.configs != 0 || f.capture != 0 || f.replayStarts != 1 || !f.media.Recording.Active {
		t.Fatal("replay changed existing local output", f)
	}
}
func TestLocalStartPreparesCaptureAndCleansFailedStartOnly(t *testing.T) {
	p := testPaths(t)
	f := &fakeMediaClient{startErr: errors.New("fixture encoder unavailable"), savedPath: "/fixture/partial.mkv"}
	saved := []string{}
	if _, e := mediaActionWith(context.Background(), p, "record-start", fakeMediaDeps(p, f, &saved)); e == nil {
		t.Fatal("claimed failed start succeeded")
	}
	if f.capture != 1 || f.recordStops != 1 || f.media.Recording.Active || len(saved) != 1 || f.halts != 1 {
		t.Fatal("new failed recording was not finalized/preserved", f, saved)
	}
}
func TestLocalStopKeepsReplayAndPreservesPartialClip(t *testing.T) {
	p := testPaths(t)
	if _, e := Configure(p, strings.NewReader(fixtureSettings)); e != nil {
		t.Fatal(e)
	}
	f := &fakeMediaClient{media: automation.MediaOutputStatus{Recording: automation.RecordingStatus{Active: true}, ReplayActive: true}, savedPath: "/fixture/partial.mkv"}
	saved := []string{}
	result, e := mediaActionWith(context.Background(), p, "record-cancel", fakeMediaDeps(p, f, &saved))
	if e != nil || result.RecordingPath != f.savedPath {
		t.Fatal(result, e)
	}
	if !f.media.ReplayActive || f.halts != 0 || len(saved) != 1 {
		t.Fatal("cancel destroyed media or stopped other output", f, saved)
	}
}
func TestMediaActionRefusesOrdinaryOBS(t *testing.T) {
	p := testPaths(t)
	f := &fakeMediaClient{unmanaged: true}
	saved := []string{}
	if _, e := mediaActionWith(context.Background(), p, "record-start", fakeMediaDeps(p, f, &saved)); e == nil {
		t.Fatal("mutated ordinary OBS")
	}
	if f.configs+f.recordStarts+f.capture != 0 {
		t.Fatal("unmanaged OBS was touched", f)
	}
}

func TestXDGVideoPreferenceIsParsedWithoutShell(t *testing.T) {
	home := t.TempDir()
	config := t.TempDir()
	t.Setenv("XDG_VIDEOS_DIR", "")
	if e := os.WriteFile(filepath.Join(config, "user-dirs.dirs"), []byte("XDG_VIDEOS_DIR=\"$HOME/My Videos\"\n"), 0600); e != nil {
		t.Fatal(e)
	}
	dir, e := DefaultVideosDirectory(home, config)
	if e != nil || dir != filepath.Join(home, "My Videos", "OBSGod") {
		t.Fatal(dir, e)
	}
	for _, bad := range []string{"$(touch /tmp/no)", "`touch /tmp/no`", "relative", "$OTHER/Videos"} {
		t.Setenv("XDG_VIDEOS_DIR", bad)
		if _, e = DefaultVideosDirectory(home, config); e == nil {
			t.Fatal("accepted shell/relative video preference", bad)
		}
	}
}
func TestRecordingStorageRejectsSymlinksAndInvalidLimits(t *testing.T) {
	p := testPaths(t)
	target := t.TempDir()
	if e := os.Symlink(target, p.Videos); e != nil {
		t.Fatal(e)
	}
	if _, e := MediaStorageStatus(p, true); e == nil {
		t.Fatal("recorded through a symlink")
	}
	pref := DefaultRecordingPreferences()
	pref.ReserveMiB = 0
	if pref.Validate() == nil {
		t.Fatal("accepted no disk reserve")
	}
	pref = DefaultRecordingPreferences()
	pref.ReplayMemoryMB = 1024
	if pref.Validate() == nil {
		t.Fatal("accepted excessive replay memory")
	}
}
func mediaFixtureFile(t *testing.T, p Paths, name string, age time.Duration) string {
	t.Helper()
	if e := os.MkdirAll(p.Videos, 0750); e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(p.Videos, name)
	if e := os.WriteFile(path, []byte("fixture-not-real-video"), 0600); e != nil {
		t.Fatal(e)
	}
	timestamp := time.Now().Add(-age)
	if e := os.Chtimes(path, timestamp, timestamp); e != nil {
		t.Fatal(e)
	}
	return path
}
func TestClipLibraryOwnsOnlyConfirmedUnchangedMedia(t *testing.T) {
	p := testPaths(t)
	confirmed := mediaFixtureFile(t, p, "DeckyStream-confirmed.mkv", 0)
	_ = mediaFixtureFile(t, p, "DeckyStream-interrupted.mkv", 0)
	_ = mediaFixtureFile(t, p, "Replay DeckyStream-unindexed.mkv", 0)
	_ = mediaFixtureFile(t, p, "unrelated.mkv", 0)
	if e := RegisterMediaFile(p, confirmed, "recording"); e != nil {
		t.Fatal(e)
	}
	library, e := MediaLibrary(p)
	if e != nil || len(library.Clips) != 1 || len(library.Recoverable) != 2 || library.Recoverable[0].Finalized || library.Recoverable[1].Finalized {
		t.Fatal(library, e)
	}
	if e = os.WriteFile(confirmed, []byte("changed-local-file"), 0600); e != nil {
		t.Fatal(e)
	}
	_, e = ExportClip(context.Background(), p, strings.NewReader(`{"name":"DeckyStream-confirmed.mkv","directory":"`+t.TempDir()+`"}`))
	if e == nil {
		t.Fatal("exported a replaced/changed clip without confirmation")
	}
}
func TestClipExportCopiesExclusivelyAndPreservesOriginal(t *testing.T) {
	p := testPaths(t)
	source := mediaFixtureFile(t, p, "DeckyStream-source.mkv", 0)
	if e := RegisterMediaFile(p, source, "replay"); e != nil {
		t.Fatal(e)
	}
	directory := t.TempDir()
	input, _ := json.Marshal(map[string]any{"name": filepath.Base(source), "directory": directory})
	result, e := ExportClip(context.Background(), p, strings.NewReader(string(input)))
	if e != nil || !result.OK {
		t.Fatal(result, e)
	}
	before, _ := os.ReadFile(source)
	copy, _ := os.ReadFile(result.Path)
	if string(before) != string(copy) {
		t.Fatal("export changed media")
	}
	if _, e = ExportClip(context.Background(), p, strings.NewReader(string(input))); e == nil {
		t.Fatal("overwrote existing export")
	}
	if _, e = os.Stat(source); e != nil {
		t.Fatal("export removed source", e)
	}
}
func TestClipCleanupPreviewsAndConfirmsOnlyExactIDs(t *testing.T) {
	p := testPaths(t)
	old := mediaFixtureFile(t, p, "DeckyStream-old.mkv", 72*time.Hour)
	newer := mediaFixtureFile(t, p, "DeckyStream-new.mkv", 0)
	other := mediaFixtureFile(t, p, "unrelated.mkv", 72*time.Hour)
	for _, path := range []string{old, newer} {
		if e := RegisterMediaFile(p, path, "recording"); e != nil {
			t.Fatal(e)
		}
	}
	preview, e := PruneClips(context.Background(), p, strings.NewReader(`{"older_than_days":1}`))
	if e != nil || !preview.Preview || len(preview.Clips) != 1 {
		t.Fatal(preview, e)
	}
	if _, e = os.Stat(old); e != nil {
		t.Fatal("preview removed clip")
	}
	if _, e = PruneClips(context.Background(), p, strings.NewReader(`{"older_than_days":1,"confirm":true}`)); e == nil {
		t.Fatal("cleanup lacked preview ID binding")
	}
	if _, e = PruneClips(context.Background(), p, strings.NewReader(`{"older_than_days":1,"confirm":true,"ids":["stale"]}`)); e == nil {
		t.Fatal("accepted stale preview")
	}
	input, _ := json.Marshal(map[string]any{"older_than_days": 1, "confirm": true, "ids": []string{preview.Clips[0].ID}})
	result, e := PruneClips(context.Background(), p, strings.NewReader(string(input)))
	if e != nil || len(result.Clips) != 1 {
		t.Fatal(result, e)
	}
	if _, e = os.Stat(old); !os.IsNotExist(e) {
		t.Fatal("selected old clip not removed", e)
	}
	for _, keep := range []string{newer, other} {
		if _, e = os.Stat(keep); e != nil {
			t.Fatal("unselected media was removed", keep, e)
		}
	}
}
