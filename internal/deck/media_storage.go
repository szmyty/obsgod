package deck

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"
)

// RecordingPreferences are local-only preferences, separate from destination
// credentials. Retention is a suggested manual cleanup age; it never authorizes
// deletion. ReserveMiB authorizes finalizing local output before disk exhaustion.
type RecordingPreferences struct {
	Version        int    `json:"version"`
	Directory      string `json:"directory"`
	ReplaySeconds  int    `json:"replay_seconds"`
	ReplayMemoryMB int    `json:"replay_memory_mb"`
	ReserveMiB     int    `json:"reserve_mib"`
	RetentionDays  int    `json:"retention_days"`
}

type MediaStorage struct {
	Directory      string  `json:"directory"`
	AvailableBytes *uint64 `json:"available_bytes,omitempty"`
	ReserveBytes   uint64  `json:"reserve_bytes"`
	Permission     string  `json:"permission"`
	Message        string  `json:"message"`
}

func DefaultRecordingPreferences() RecordingPreferences {
	return RecordingPreferences{Version: 1, ReplaySeconds: 60, ReplayMemoryMB: 256, ReserveMiB: 1024}
}
func recordingPreferencesPath(p Paths) string {
	return filepath.Join(filepath.Dir(p.Config), "recording.json")
}
func (r RecordingPreferences) Validate() error {
	if r.Version != 1 {
		return errors.New("unsupported recording preferences version")
	}
	if r.Directory != "" {
		if err := validateMediaDirectory(r.Directory); err != nil {
			return err
		}
	}
	if r.ReplaySeconds < 15 || r.ReplaySeconds > 120 {
		return errors.New("replay duration must be 15–120 seconds")
	}
	if r.ReplayMemoryMB < 64 || r.ReplayMemoryMB > 512 {
		return errors.New("replay memory limit must be 64–512 MiB")
	}
	if r.ReserveMiB < 256 || r.ReserveMiB > 65536 {
		return errors.New("free-space reserve must be 256–65536 MiB")
	}
	if r.RetentionDays < 0 || r.RetentionDays > 3650 {
		return errors.New("manual cleanup age must be 0–3650 days; zero keeps every clip")
	}
	return nil
}
func RecordingSettings(p Paths) (RecordingPreferences, error) {
	pref := DefaultRecordingPreferences()
	info, e := os.Lstat(recordingPreferencesPath(p))
	if os.IsNotExist(e) {
		return pref, nil
	}
	if e != nil || !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 || info.Size() > 8192 {
		return pref, errors.New("recording preferences must be a regular local file")
	}
	b, e := os.ReadFile(recordingPreferencesPath(p))
	if os.IsNotExist(e) {
		return pref, nil
	}
	if e != nil {
		return pref, errors.New("cannot read recording preferences")
	}
	if len(b) > 8192 {
		return pref, errors.New("recording preferences are too large")
	}
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.DisallowUnknownFields()
	if d.Decode(&pref) != nil {
		return pref, errors.New("invalid recording preferences")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return pref, errors.New("recording preferences must contain one object")
	}
	return pref, pref.Validate()
}
func mediaDirectory(p Paths, r RecordingPreferences) string {
	if r.Directory != "" {
		return r.Directory
	}
	return p.Videos
}

// MediaProfileValues supplies the isolated OBS profile's disk/replay values.
// It does not start output, create media, or change the ordinary OBS profile.
func MediaProfileValues(p Paths) (string, int, int, error) {
	r, e := RecordingSettings(p)
	if e != nil {
		return "", 0, 0, e
	}
	dir := mediaDirectory(p, r)
	if e = validateMediaDirectory(dir); e != nil {
		return "", 0, 0, e
	}
	return dir, r.ReplaySeconds, r.ReplayMemoryMB, nil
}
func validateMediaDirectory(dir string) error {
	if !filepath.IsAbs(dir) || filepath.Clean(dir) != dir || dir == string(filepath.Separator) || strings.IndexFunc(dir, func(r rune) bool { return unicode.IsControl(r) }) >= 0 {
		return errors.New("choose an absolute recording directory without control characters, dot segments or trailing separators")
	}
	return nil
}

// checkedMediaDirectory refuses symbolic-link traversal. Existing user-selected
// directories keep their permissions; only newly created directories use 0750.
func checkedMediaDirectory(dir string, create bool) error {
	if e := validateMediaDirectory(dir); e != nil {
		return e
	}
	current := string(filepath.Separator)
	for _, part := range strings.Split(strings.TrimPrefix(dir, string(filepath.Separator)), string(filepath.Separator)) {
		current = filepath.Join(current, part)
		st, e := os.Lstat(current)
		if os.IsNotExist(e) {
			if !create {
				return os.ErrNotExist
			}
			if e = os.Mkdir(current, 0750); e != nil {
				return errors.New("cannot create the recording directory; check its permissions")
			}
			st, e = os.Lstat(current)
		}
		if e != nil || !st.IsDir() || st.Mode()&os.ModeSymlink != 0 {
			return errors.New("recording directories must be real directories; symbolic links are refused")
		}
	}
	return nil
}
func inspectMediaStorage(p Paths, pref RecordingPreferences, probe bool) (MediaStorage, error) {
	dir := mediaDirectory(p, pref)
	s := MediaStorage{Directory: dir, ReserveBytes: uint64(pref.ReserveMiB) * 1024 * 1024, Permission: "unavailable", Message: "Recording storage could not be confirmed"}
	if e := checkedMediaDirectory(dir, probe); e != nil {
		s.Message = "Recording directory is missing or unsafe; choose a writable directory in Desktop setup"
		return s, e
	}
	if probe {
		f, e := os.CreateTemp(dir, ".deckystream-write-check-*")
		if e != nil {
			s.Message = "Recording directory is not writable"
			return s, errors.New(s.Message)
		}
		name := f.Name()
		closeErr := f.Close()
		removeErr := os.Remove(name)
		if closeErr != nil || removeErr != nil {
			return s, errors.New("recording storage write check did not complete")
		}
	}
	free, e := mediaFreeBytes(dir)
	if e != nil {
		s.Message = "Available recording storage could not be measured"
		return s, e
	}
	s.AvailableBytes = &free
	if free < s.ReserveBytes {
		s.Message = "Recording storage is below the configured free-space reserve; free space or select another directory"
		return s, errors.New(s.Message)
	}
	s.Permission = "ready"
	s.Message = "Local recording storage has space above the configured reserve; write access is rechecked before output starts"
	return s, nil
}

// ConfigureRecording saves only preferences while every output is confirmed idle.
// An idle OBS process is closed by the user explicitly if applying new encoder
// or profile settings requires a restart. No configuration operation broadcasts.
func ConfigureRecording(ctx context.Context, p Paths, reader io.Reader) (RecordingPreferences, error) {
	pref := DefaultRecordingPreferences()
	d := json.NewDecoder(io.LimitReader(reader, 8193))
	d.DisallowUnknownFields()
	if d.Decode(&pref) != nil {
		return pref, errors.New("invalid recording preferences JSON")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return pref, errors.New("recording preferences must contain one JSON object")
	}
	if e := pref.Validate(); e != nil {
		return pref, e
	}
	state := Status(ctx, p)
	if !state.OutputKnown || state.Stream.Active || state.Recording {
		return pref, errors.New("stop all output and confirm idle status before changing recording preferences")
	}
	media := MediaStatus(ctx, p)
	if !media.Known || media.ReplayActive {
		return pref, errors.New("stop replay and confirm idle status before changing recording preferences")
	}
	if _, e := inspectMediaStorage(p, pref, true); e != nil {
		return pref, e
	}
	if e := writeJSON(recordingPreferencesPath(p), pref); e != nil {
		return pref, e
	}
	return pref, nil
}

// DefaultVideosDirectory reads the XDG user-dirs preference without executing a
// shell. Only a quoted absolute path or a leading $HOME is expanded.
func DefaultVideosDirectory(home, configRoot string) (string, error) {
	fallback := filepath.Join(home, "Videos", "OBSGod")
	if value := os.Getenv("XDG_VIDEOS_DIR"); value != "" {
		return parseVideosDirectory(value, home)
	}
	filename := filepath.Join(configRoot, "user-dirs.dirs")
	info, e := os.Lstat(filename)
	if os.IsNotExist(e) {
		return fallback, nil
	}
	if e != nil || !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return "", errors.New("XDG user directory preferences must be a regular file")
	}
	f, e := os.Open(filename)
	if e != nil {
		return "", e
	}
	defer f.Close()
	scan := bufio.NewScanner(io.LimitReader(f, 65537))
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if strings.HasPrefix(line, "XDG_VIDEOS_DIR=") {
			value := strings.TrimSpace(strings.TrimPrefix(line, "XDG_VIDEOS_DIR="))
			if len(value) < 2 || value[0] != '"' || value[len(value)-1] != '"' {
				return "", errors.New("XDG_VIDEOS_DIR must be a quoted directory")
			}
			value = value[1 : len(value)-1]
			value = strings.ReplaceAll(strings.ReplaceAll(value, `\"`, `"`), `\\`, `\`)
			return parseVideosDirectory(value, home)
		}
	}
	if scan.Err() != nil {
		return "", errors.New("cannot read XDG Videos preference")
	}
	return fallback, nil
}
func parseVideosDirectory(value, home string) (string, error) {
	if value == "$HOME" {
		value = home
	} else if strings.HasPrefix(value, "$HOME/") {
		value = filepath.Join(home, strings.TrimPrefix(value, "$HOME/"))
	}
	if strings.ContainsAny(value, "$`\x00") || !filepath.IsAbs(value) {
		return "", errors.New("XDG_VIDEOS_DIR must be an absolute local directory; shell expansion is not supported")
	}
	value = filepath.Clean(value)
	if e := validateMediaDirectory(value); e != nil {
		return "", e
	}
	return filepath.Join(value, "OBSGod"), nil
}

func mediaShortfallMessage(bytes uint64) string {
	return "Recording storage has " + strconv.FormatUint(bytes/(1024*1024), 10) + " MiB free; local recording/replay were stopped at the configured reserve. Existing media was preserved; streaming was not changed"
}

// MediaStorage reads or explicitly probes the configured local recording directory.
func MediaStorageStatus(p Paths, probe bool) (MediaStorage, error) {
	pref, e := RecordingSettings(p)
	if e != nil {
		return MediaStorage{}, e
	}
	return inspectMediaStorage(p, pref, probe)
}
