package deck

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"
)

const idleImageLimit int64 = 16 << 20
const idleVideoLimit int64 = 256 << 20

var idleMediaName = regexp.MustCompile(`^[0-9a-f]{64}\.(png|jpg|mp4|webm)$`)

func idleMediaDirectory(p Paths) string {
	return filepath.Join(p.OBSConfig, "obs-studio", "obsgod-media")
}

// validateIdleMediaSettings validates the portable metadata, never a caller's
// arbitrary path. Managed media names identify immutable imported bytes.
func validateIdleMediaSettings(s Settings) error {
	if s.IdleMedia != "" && !idleMediaName.MatchString(s.IdleMedia) {
		return errors.New("idle media must be imported through Desktop setup; arbitrary file paths are refused")
	}
	if !utf8.ValidString(s.IdleMediaRights) || len([]rune(s.IdleMediaRights)) > 500 {
		return errors.New("media attribution must contain at most 500 characters")
	}
	for _, r := range s.IdleMediaRights {
		if unicode.IsControl(r) && r != '\n' {
			return errors.New("media attribution contains an unsupported control character")
		}
	}
	style := s.IdleStyleName()
	if style == "image" || style == "video" {
		if s.IdleMedia == "" {
			return errors.New("import a local image or video before selecting its idle screen")
		}
		ext := filepath.Ext(s.IdleMedia)
		if style == "image" && ext != ".png" && ext != ".jpg" {
			return errors.New("image idle screens require a PNG or JPEG import")
		}
		if style == "video" && ext != ".mp4" && ext != ".webm" {
			return errors.New("video idle screens require an MP4 or WebM import")
		}
	}
	return nil
}

// openLocalMedia refuses symlinks in every component and validates the same open
// file that is copied. The original filename is never retained in diagnostics.
func openLocalMedia(path string) (*os.File, error) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path || strings.ContainsAny(path, "\r\n\x00") {
		return nil, errors.New("choose an absolute local file path without control characters")
	}
	current := filepath.VolumeName(path) + string(filepath.Separator)
	for _, part := range strings.Split(strings.TrimPrefix(strings.TrimPrefix(path, filepath.VolumeName(path)), string(filepath.Separator)), string(filepath.Separator)) {
		if part == "" {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err != nil || info.Mode()&os.ModeSymlink != 0 {
			return nil, errors.New("local media must exist without symlink path components")
		}
	}
	before, err := os.Lstat(path)
	if err != nil || !before.Mode().IsRegular() {
		return nil, errors.New("local media must be a regular file")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, errors.New("local media could not be opened; check file permissions")
	}
	after, err := file.Stat()
	if err != nil || !after.Mode().IsRegular() || !os.SameFile(before, after) {
		_ = file.Close()
		return nil, errors.New("local media changed while opening it; retry")
	}
	return file, nil
}

func mediaExtension(file *os.File, style string) (string, int64, error) {
	info, err := file.Stat()
	if err != nil || info.Size() <= 0 {
		return "", 0, errors.New("choose a nonempty local media file")
	}
	if style == "image" {
		if info.Size() > idleImageLimit {
			return "", 0, errors.New("idle images must be no larger than 16 MiB")
		}
		config, format, err := image.DecodeConfig(io.LimitReader(file, idleImageLimit+1))
		if err != nil || (format != "png" && format != "jpeg") || config.Width < 1 || config.Height < 1 || config.Width > 8192 || config.Height > 8192 || int64(config.Width)*int64(config.Height) > 32*1024*1024 {
			return "", 0, errors.New("choose a valid PNG or JPEG image within 8192 pixels per side and 32 megapixels")
		}
		if _, err = file.Seek(0, io.SeekStart); err != nil {
			return "", 0, err
		}
		if format == "jpeg" {
			format = "jpg"
		}
		return "." + format, idleImageLimit, nil
	}
	if style != "video" || info.Size() > idleVideoLimit {
		return "", 0, errors.New("idle videos must be local MP4 or WebM files no larger than 256 MiB")
	}
	var head [64]byte
	count, _ := file.ReadAt(head[:], 0)
	ext := ""
	if count >= 12 && bytes.Equal(head[4:8], []byte("ftyp")) {
		ext = ".mp4"
	}
	// Require a WebM EBML document type, not arbitrary Matroska or a playlist.
	if count >= 12 && bytes.Equal(head[:4], []byte{0x1a, 0x45, 0xdf, 0xa3}) && bytes.Contains(head[:count], []byte("webm")) {
		ext = ".webm"
	}
	if ext == "" {
		return "", 0, errors.New("choose an MP4 or WebM video, not a playlist, URL or unsupported container")
	}
	return ext, idleVideoLimit, nil
}

func importIdleMedia(p Paths, source, style string) (string, error) {
	return importIdleMediaWithin(context.Background(), p, source, style)
}
func importIdleMediaWithin(ctx context.Context, p Paths, source, style string) (string, error) {
	file, err := openLocalMedia(source)
	if err != nil {
		return "", err
	}
	defer file.Close()
	ext, limit, err := mediaExtension(file, style)
	if err != nil {
		return "", err
	}
	directory := idleMediaDirectory(p)
	// Never follow an existing symlink ancestor while creating the owned copy.
	if err = checkIdleMediaAncestry(directory); err != nil {
		return "", err
	}
	// Validate the full destination ancestry before creating the private leaf.
	if err = privateDir(p.OBSConfig); err != nil {
		return "", err
	}
	if err = privateDir(filepath.Join(p.OBSConfig, "obs-studio")); err != nil {
		return "", err
	}
	if err = privateDir(directory); err != nil {
		return "", err
	}
	temp, err := os.CreateTemp(directory, ".import-*")
	if err != nil {
		return "", errors.New("could not create the owned media copy; check free space and permissions")
	}
	defer os.Remove(temp.Name())
	defer temp.Close()
	hash := sha256.New()
	copied, err := io.Copy(io.MultiWriter(temp, hash), io.LimitReader(idleMediaReader{ctx, file}, limit+1))
	if err != nil || copied > limit {
		return "", errors.New("media copy failed or exceeded its size limit; existing settings were preserved")
	}
	// Verify format after the copy too, because an in-place edit could have raced.
	if _, err = temp.Seek(0, io.SeekStart); err != nil {
		return "", err
	}
	copiedExt, _, err := mediaExtension(temp, style)
	if err != nil || copiedExt != ext {
		return "", errors.New("local media changed while copying; retry")
	}
	if style == "image" {
		if _, err = temp.Seek(0, io.SeekStart); err != nil {
			return "", err
		}
		if _, _, err = image.Decode(io.LimitReader(temp, idleImageLimit+1)); err != nil {
			return "", errors.New("image pixels could not be decoded; choose an intact PNG or JPEG")
		}
	}
	if err = temp.Sync(); err != nil {
		return "", errors.New("could not save the owned media copy; check free space")
	}
	name := hex.EncodeToString(hash.Sum(nil)) + ext
	destination := filepath.Join(directory, name)
	if info, err := os.Lstat(destination); err == nil {
		if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
			return "", errors.New("the owned media destination is unsafe; inspect Desktop setup")
		}
		// Identical bytes are reusable; do not overwrite altered imported content.
		existing, err := openLocalMedia(destination)
		if err != nil {
			return "", errors.New("the owned media copy could not be verified")
		}
		defer existing.Close()
		verifiedHash := sha256.New()
		count, err := io.Copy(verifiedHash, io.LimitReader(existing, limit+1))
		if err != nil || count > limit {
			return "", errors.New("the owned media copy could not be verified")
		}
		if hex.EncodeToString(verifiedHash.Sum(nil))+ext != name {
			return "", errors.New("the owned media copy changed; remove it explicitly in Desktop Mode before reimporting")
		}
		return name, nil
	}
	if err = temp.Close(); err != nil {
		return "", err
	}
	if err = os.Rename(temp.Name(), destination); err != nil {
		return "", errors.New("could not finalize the owned media copy")
	}
	return name, nil
}

// idleMediaFile returns only a validated imported regular file, never an
// arbitrary config-supplied filesystem location. A missing asset falls back to
// black at runtime; it never selects a display source or interrupts output.
func idleMediaFile(p Paths, s Settings) (string, error) {
	if err := validateIdleMediaSettings(s); err != nil {
		return "", err
	}
	if s.IdleStyleName() != "image" && s.IdleStyleName() != "video" {
		return "", nil
	}
	path := filepath.Join(idleMediaDirectory(p), s.IdleMedia)
	file, err := openLocalMedia(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || info.Mode().Perm()&0077 != 0 {
		return "", errors.New("owned idle media must remain private")
	}
	ext, _, err := mediaExtension(file, s.IdleStyleName())
	if err != nil || ext != filepath.Ext(path) {
		return "", errors.New("owned idle media has an unsupported format")
	}
	if _, err = file.Seek(0, io.SeekStart); err != nil {
		return "", err
	}
	limit := idleImageLimit
	if s.IdleStyleName() == "video" {
		limit = idleVideoLimit
	}
	hash := sha256.New()
	count, err := io.Copy(hash, io.LimitReader(file, limit+1))
	if err != nil || count > limit || hex.EncodeToString(hash.Sum(nil))+ext != s.IdleMedia {
		return "", errors.New("owned idle media changed; use a fresh acknowledged import")
	}
	return path, nil
}

// IdlePreview is a local configuration observation, not proof of rendered media
// or viewer reception. Original source paths and attribution are not exposed.
type IdlePreview struct {
	Style   string `json:"style"`
	Media   string `json:"media"`
	Muted   bool   `json:"muted"`
	Message string `json:"message"`
}

func PreviewIdle(p Paths, s Settings) IdlePreview {
	result := IdlePreview{Style: s.IdleStyleName(), Media: "none", Muted: true, Message: "Black or plain-text fallback; output authorization is unchanged"}
	if result.Style == "image" || result.Style == "video" {
		result.Media = "ready"
		result.Message = "Local imported media is available; idle video is always muted"
		if _, err := idleMediaFile(p, s); err != nil {
			result.Media = "unavailable"
			result.Message = "Imported media is unavailable; black is used until it is repaired"
		}
	}
	return result
}

// ConfigureIdle changes only the next owned idle scene preferences. It never
// launches OBS, configures a service, or starts/stops any output.
func ConfigureIdle(ctx context.Context, p Paths, reader io.Reader) (Result, error) {
	var input struct {
		Style              string  `json:"idle_style"`
		Text               *string `json:"idle_text,omitempty"`
		Source             string  `json:"source,omitempty"`
		RightsAcknowledged bool    `json:"rights_acknowledged,omitempty"`
		Attribution        *string `json:"attribution,omitempty"`
	}
	body, err := io.ReadAll(io.LimitReader(reader, 8193))
	if err != nil || len(body) > 8192 {
		return Result{}, errors.New("idle-screen settings exceed the 8192-byte limit")
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&input) != nil {
		return Result{}, errors.New("invalid idle-screen JSON")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return Result{}, errors.New("idle-screen settings must be exactly one JSON object")
	}
	if input.Style != "black" && input.Style != "placeholder" && input.Style != "image" && input.Style != "video" {
		return Result{}, errors.New("choose black, placeholder, image or video")
	}
	if input.Source != "" && (input.Style != "image" && input.Style != "video") {
		return Result{}, errors.New("media imports require image or video mode")
	}
	if input.Source != "" && !input.RightsAcknowledged {
		return Result{}, errors.New("confirm that you own or have permission to use this media before importing it")
	}
	settings, _, err := Load(p)
	if err != nil {
		return Result{}, err
	}
	state := Status(ctx, p)
	if !state.OutputKnown || state.Stream.Active || state.Recording || state.Media == nil || !state.Media.Known || state.Media.ReplayActive {
		return Result{}, errors.New("stop streaming and recording and confirm idle status, including replay, before editing the idle screen")
	}
	leaseCtx, cancel := context.WithTimeout(ctx, 6*time.Second)
	unlock, err := Lock(leaseCtx, captureWatchPaths(p))
	cancel()
	if err != nil {
		return Result{}, errors.New("the previous capture observer is finishing; wait for idle status and retry")
	}
	defer unlock()
	state = Status(ctx, p)
	if !state.OutputKnown || state.Stream.Active || state.Recording || state.Media == nil || !state.Media.Known || state.Media.ReplayActive {
		return Result{}, errors.New("output changed while waiting; idle preferences were not changed")
	}
	settings.IdleStyle = input.Style
	if input.Text != nil {
		settings.IdleText = *input.Text
	}
	if input.Attribution != nil {
		settings.IdleMediaRights = *input.Attribution
	}
	if input.Source != "" {
		// Validate the non-file fields before allocating an owned media copy.
		candidate := settings
		candidate.IdleStyle = "black"
		candidate.IdleMedia = ""
		if err = candidate.Validate(); err != nil {
			return Result{}, err
		}
		settings.IdleMedia, err = importIdleMediaWithin(ctx, p, input.Source, input.Style)
		if err != nil {
			return Result{}, err
		}
	}
	if err = settings.Validate(); err != nil {
		return Result{}, err
	}
	if settings.IdleStyleName() == "image" || settings.IdleStyleName() == "video" {
		if _, err = idleMediaFile(p, settings); err != nil {
			return Result{}, errors.New("the selected imported media is unavailable; choose its local file and import it again")
		}
	}
	data, err := json.Marshal(settings)
	if err != nil {
		return Result{}, err
	}
	if _, err = Configure(p, bytes.NewReader(data)); err != nil {
		return Result{}, err
	}
	return Result{OK: true, Configured: true, State: "stopped", Settings: &settings, Message: "Idle screen saved for the next explicit stream or recording; no output was started"}, nil
}

// Include file metadata so removing/restoring an imported asset is observed
// without hashing hundreds of megabytes during every one-second status cycle.
func idleMediaKey(p Paths, s Settings) string {
	key := s.IdleStyleName() + "\x00" + s.IdleMessage() + "\x00" + s.IdleMedia
	if s.IdleMedia != "" {
		if info, err := os.Lstat(filepath.Join(idleMediaDirectory(p), s.IdleMedia)); err == nil {
			key += fmt.Sprintf("\x00%d:%d:%d", info.Size(), info.ModTime().UnixNano(), info.Mode())
		} else {
			key += "\x00missing"
		}
	}
	return key
}

// Returning to idle is immediate for privacy. A new game needs two consistent
// observations before becoming visible, avoiding a one-cycle launch/exit flap.
type gameStability struct {
	app     uint32
	samples int
}

func (s *gameStability) observe(game GameIdentity) GameIdentity {
	if game.State != "running" || game.AppID == 0 || game.AppID == 769 {
		s.app = 0
		s.samples = 0
		return game
	}
	if game.AppID != s.app {
		s.app = game.AppID
		s.samples = 1
	} else if s.samples < 2 {
		s.samples++
	}
	if s.samples < 2 {
		return GameIdentity{State: "idle"}
	}
	return game
}

func checkIdleMediaAncestry(path string) error {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path || strings.ContainsAny(path, "\r\n\x00") {
		return errors.New("owned media directory must be an absolute safe path")
	}
	current := filepath.VolumeName(path) + string(filepath.Separator)
	for _, part := range strings.Split(strings.TrimPrefix(strings.TrimPrefix(path, filepath.VolumeName(path)), string(filepath.Separator)), string(filepath.Separator)) {
		if part == "" {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return errors.New("owned media directory contains an unsafe path component")
		}
	}
	return nil
}

// Honor cancellation between bounded disk reads without exposing the filename.
type idleMediaReader struct {
	ctx    context.Context
	reader io.Reader
}

func (r idleMediaReader) Read(data []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	return r.reader.Read(data)
}
