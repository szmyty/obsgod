package deck

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type MediaClip struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Kind        string `json:"kind"`
	Bytes       int64  `json:"bytes"`
	ModifiedUTC string `json:"modified_utc"`
	Directory   string `json:"directory"`
	Finalized   bool   `json:"finalized"`
}
type MediaLibraryResult struct {
	OK          bool        `json:"ok"`
	Clips       []MediaClip `json:"clips"`
	Recoverable []MediaClip `json:"recoverable"`
	Message     string      `json:"message"`
}
type mediaEntry struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	Kind       string `json:"kind"`
	Directory  string `json:"directory"`
	Size       int64  `json:"size"`
	ModifiedNS int64  `json:"modified_ns"`
}
type mediaIndex struct {
	Version int          `json:"version"`
	Entries []mediaEntry `json:"entries"`
}

func mediaIndexPath(p Paths) string { return filepath.Join(p.State, "media-index.json") }
func mediaID(directory, name string) string {
	sum := sha256.Sum256([]byte(directory + "\x00" + name))
	return hex.EncodeToString(sum[:12])
}
func safeMediaName(name string) bool {
	return name != "" && name == filepath.Base(name) && name != "." && name != ".." && !strings.ContainsAny(name, "/\\") && strings.IndexFunc(name, func(r rune) bool { return r < 32 || r == 127 }) < 0 && strings.EqualFold(filepath.Ext(name), ".mkv")
}
func readMediaIndex(p Paths) (mediaIndex, error) {
	index := mediaIndex{Version: 1, Entries: []mediaEntry{}}
	info, e := os.Lstat(mediaIndexPath(p))
	if os.IsNotExist(e) {
		return index, nil
	}
	if e != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 4*1024*1024 {
		return index, errors.New("clip index is unsafe or unavailable; existing media was preserved")
	}
	if e = readJSON(mediaIndexPath(p), &index); e != nil || index.Version != 1 || len(index.Entries) > 5000 {
		return index, errors.New("invalid clip index; existing media was preserved")
	}
	seen := map[string]bool{}
	for _, entry := range index.Entries {
		if !safeMediaName(entry.Name) || validateMediaDirectory(entry.Directory) != nil || entry.ID != mediaID(entry.Directory, entry.Name) || seen[entry.ID] || entry.Size <= 0 || entry.ModifiedNS <= 0 || (entry.Kind != "recording" && entry.Kind != "replay") {
			return index, errors.New("invalid clip ownership record; existing media was preserved")
		}
		seen[entry.ID] = true
	}
	return index, nil
}
func finalizedMediaInfo(path string) (os.FileInfo, error) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path || !safeMediaName(filepath.Base(path)) {
		return nil, errors.New("OBS returned an unexpected recording path; inspect its recording folder. No media was deleted")
	}
	if e := checkedMediaDirectory(filepath.Dir(path), false); e != nil {
		return nil, e
	}
	info, e := os.Lstat(path)
	if e != nil || !info.Mode().IsRegular() || info.Size() <= 0 {
		return nil, errors.New("OBS has not produced a nonempty regular recording file; inspect its recording folder")
	}
	return info, nil
}

// RegisterMediaFile indexes only a finalized path returned by verified managed OBS.
// The caller must hold the control lease and have confirmed muxer completion.
func RegisterMediaFile(p Paths, path, kind string) error { return registerMediaFile(p, path, kind) }

func registerMediaFile(p Paths, path, kind string) error {
	pref, e := RecordingSettings(p)
	if e != nil {
		return e
	}
	if filepath.Dir(path) != mediaDirectory(p, pref) {
		return errors.New("OBS saved outside the selected recording directory; the file was preserved but cannot be managed automatically")
	}
	info, e := finalizedMediaInfo(path)
	if e != nil {
		return e
	}
	if kind != "recording" && kind != "replay" {
		return errors.New("invalid local clip kind")
	}
	index, e := readMediaIndex(p)
	if e != nil {
		return e
	}
	id := mediaID(filepath.Dir(path), filepath.Base(path))
	entry := mediaEntry{ID: id, Name: filepath.Base(path), Kind: kind, Directory: filepath.Dir(path), Size: info.Size(), ModifiedNS: info.ModTime().UnixNano()}
	found := false
	for n, item := range index.Entries {
		if item.ID == id {
			index.Entries[n] = entry
			found = true
			break
		}
	}
	if !found {
		if len(index.Entries) >= 5000 {
			return errors.New("clip index is full; the saved file was preserved, export existing clips before recording more")
		}
		index.Entries = append(index.Entries, entry)
	}
	return writeJSON(mediaIndexPath(p), index)
}
func mediaEntryInfo(entry mediaEntry) (os.FileInfo, error) {
	info, e := finalizedMediaInfo(filepath.Join(entry.Directory, entry.Name))
	if e != nil {
		return nil, e
	}
	if info.Size() != entry.Size || info.ModTime().UnixNano() != entry.ModifiedNS {
		return nil, errors.New("the saved clip changed after finalization; automatic export/cleanup was refused to preserve it")
	}
	return info, nil
}
func clipFromEntry(entry mediaEntry) MediaClip {
	return MediaClip{ID: entry.ID, Name: entry.Name, Kind: entry.Kind, Bytes: entry.Size, ModifiedUTC: time.Unix(0, entry.ModifiedNS).UTC().Format(time.RFC3339Nano), Directory: entry.Directory, Finalized: true}
}
func MediaLibrary(p Paths) (MediaLibraryResult, error) {
	result := MediaLibraryResult{OK: true, Clips: []MediaClip{}, Recoverable: []MediaClip{}, Message: "Only OBS-confirmed finalized clips are eligible for export or explicit cleanup; no media is deleted automatically"}
	index, e := readMediaIndex(p)
	if e != nil {
		return result, e
	}
	known := map[string]bool{}
	for _, entry := range index.Entries {
		known[entry.ID] = true
		if _, e = mediaEntryInfo(entry); e == nil {
			result.Clips = append(result.Clips, clipFromEntry(entry))
		}
	}
	sort.Slice(result.Clips, func(i, j int) bool { return result.Clips[i].ModifiedUTC > result.Clips[j].ModifiedUTC })
	pref, e := RecordingSettings(p)
	if e != nil {
		return result, e
	}
	directory := mediaDirectory(p, pref)
	if checkedMediaDirectory(directory, false) == nil {
		files, readErr := os.ReadDir(directory)
		if readErr == nil {
			for _, file := range files {
				if len(result.Recoverable) >= 1000 {
					break
				}
				if !strings.HasPrefix(file.Name(), "DeckyStream-") || !safeMediaName(file.Name()) || known[mediaID(directory, file.Name())] {
					continue
				}
				info, infoErr := file.Info()
				if infoErr == nil && info.Mode().IsRegular() && info.Size() > 0 {
					result.Recoverable = append(result.Recoverable, MediaClip{ID: mediaID(directory, file.Name()), Name: file.Name(), Kind: "unverified", Bytes: info.Size(), ModifiedUTC: info.ModTime().UTC().Format(time.RFC3339Nano), Directory: directory, Finalized: false})
				}
			}
		}
	}
	if len(result.Recoverable) > 0 {
		result.Message = "Unindexed MKV files may be active or interrupted recordings. They are preserved and never cleaned up automatically; confirm output is idle, then inspect/remux them with OBS in Desktop Mode"
	}
	return result, nil
}

type MediaExportResult struct {
	OK      bool   `json:"ok"`
	Path    string `json:"path"`
	Message string `json:"message"`
}

func findMediaEntry(index mediaIndex, id, name string) (mediaEntry, error) {
	var match mediaEntry
	count := 0
	for _, entry := range index.Entries {
		if (id != "" && entry.ID == id) || (id == "" && name != "" && entry.Name == name) {
			match = entry
			count++
		}
	}
	if count != 1 {
		return mediaEntry{}, errors.New("choose one finalized clip from the local library by its ID")
	}
	return match, nil
}
func decodeMediaJSON(reader io.Reader, v any) error {
	d := json.NewDecoder(io.LimitReader(reader, 8193))
	d.DisallowUnknownFields()
	if d.Decode(v) != nil {
		return errors.New("invalid local media JSON")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return errors.New("local media action must contain one JSON object")
	}
	return nil
}

// ExportClip copies a confirmed finalized clip to a user-selected real directory.
// It never overwrites an existing destination or follows a source-file symlink.
func ExportClip(ctx context.Context, p Paths, reader io.Reader) (MediaExportResult, error) {
	var input struct {
		ID        string `json:"id"`
		Name      string `json:"name"`
		Directory string `json:"directory"`
	}
	if e := decodeMediaJSON(reader, &input); e != nil {
		return MediaExportResult{}, e
	}
	index, e := readMediaIndex(p)
	if e != nil {
		return MediaExportResult{}, e
	}
	entry, e := findMediaEntry(index, input.ID, input.Name)
	if e != nil {
		return MediaExportResult{}, e
	}
	info, e := mediaEntryInfo(entry)
	if e != nil {
		return MediaExportResult{}, e
	}
	if e = checkedMediaDirectory(input.Directory, true); e != nil {
		return MediaExportResult{}, e
	}
	free, e := mediaFreeBytes(input.Directory)
	if e != nil || free < uint64(info.Size())+256*1024*1024 {
		return MediaExportResult{}, errors.New("export destination needs the clip size plus 256 MiB free")
	}
	source, e := openMediaRead(filepath.Join(entry.Directory, entry.Name))
	if e != nil {
		return MediaExportResult{}, errors.New("cannot safely open the finalized clip")
	}
	defer source.Close()
	actual, e := source.Stat()
	if e != nil || !os.SameFile(info, actual) || actual.Size() != entry.Size || actual.ModTime().UnixNano() != entry.ModifiedNS {
		return MediaExportResult{}, errors.New("clip changed while preparing export; no destination was overwritten")
	}
	destination := filepath.Join(input.Directory, entry.Name)
	target, e := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if e != nil {
		return MediaExportResult{}, errors.New("cannot create export file; an existing file will never be overwritten")
	}
	complete := false
	defer func() {
		_ = target.Close()
		if !complete {
			_ = os.Remove(destination)
		}
	}()
	buffer := make([]byte, 256*1024)
	var written int64
	for {
		if e = ctx.Err(); e != nil {
			return MediaExportResult{}, e
		}
		count, readErr := source.Read(buffer)
		if count > 0 {
			n, writeErr := target.Write(buffer[:count])
			written += int64(n)
			if writeErr != nil || n != count {
				return MediaExportResult{}, errors.New("clip export was interrupted; original media was preserved")
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return MediaExportResult{}, errors.New("clip export could not read the source; original media was preserved")
		}
		if written > entry.Size {
			return MediaExportResult{}, errors.New("clip changed while exporting; original media was preserved")
		}
	}
	if written != entry.Size {
		return MediaExportResult{}, errors.New("clip changed while exporting; original media was preserved")
	}
	if e = target.Sync(); e != nil {
		return MediaExportResult{}, errors.New("clip export did not finish writing; original media was preserved")
	}
	if e = target.Close(); e != nil {
		return MediaExportResult{}, e
	}
	complete = true
	return MediaExportResult{OK: true, Path: destination, Message: "Finalized clip copied; original media was preserved"}, nil
}

type MediaPruneResult struct {
	OK      bool        `json:"ok"`
	Preview bool        `json:"preview"`
	Clips   []MediaClip `json:"clips"`
	Bytes   int64       `json:"bytes"`
	Message string      `json:"message"`
}

// PruneClips is preview-only unless confirm is explicitly true. Only unchanged,
// index-owned finalized files can be removed, and only with every output idle.
func PruneClips(ctx context.Context, p Paths, reader io.Reader) (MediaPruneResult, error) {
	var input struct {
		Confirm       bool     `json:"confirm"`
		OlderThanDays int      `json:"older_than_days"`
		IDs           []string `json:"ids,omitempty"`
	}
	if e := decodeMediaJSON(reader, &input); e != nil {
		return MediaPruneResult{}, e
	}
	if input.OlderThanDays < 1 || input.OlderThanDays > 3650 {
		return MediaPruneResult{}, errors.New("choose an explicit cleanup age of 1–3650 days; cleanup is disabled by default")
	}
	index, e := readMediaIndex(p)
	if e != nil {
		return MediaPruneResult{}, e
	}
	result := MediaPruneResult{OK: true, Preview: !input.Confirm, Clips: []MediaClip{}, Message: "Cleanup preview only; no files were deleted"}
	cutoff := time.Now().Add(-time.Duration(input.OlderThanDays) * 24 * time.Hour)
	selected := map[string]bool{}
	for _, entry := range index.Entries {
		if time.Unix(0, entry.ModifiedNS).Before(cutoff) {
			if _, e = mediaEntryInfo(entry); e == nil {
				selected[entry.ID] = true
				result.Clips = append(result.Clips, clipFromEntry(entry))
				result.Bytes += entry.Size
			}
		}
	}
	if !input.Confirm {
		return result, nil
	}
	if len(input.IDs) == 0 || len(input.IDs) > 1000 {
		return MediaPruneResult{}, errors.New("confirm cleanup with the exact clip IDs from a fresh preview")
	}
	requested := map[string]bool{}
	for _, id := range input.IDs {
		if requested[id] || !selected[id] {
			return MediaPruneResult{}, errors.New("cleanup preview is stale; preview again before deleting any clip")
		}
		requested[id] = true
	}
	selected = requested
	state := Status(ctx, p)
	media := MediaStatus(ctx, p)
	if !state.OutputKnown || state.Stream.Active || state.Recording || !media.Known || media.ReplayActive {
		return MediaPruneResult{}, errors.New("stop every output and confirm idle status before deleting selected clips")
	}
	// All selected files were previewed by policy. Revalidate each immediately
	// before unlinking; modified/symlink/recovery files are never touched.
	retained := make([]mediaEntry, 0, len(index.Entries))
	result.Clips = []MediaClip{}
	result.Bytes = 0
	for _, entry := range index.Entries {
		if !selected[entry.ID] {
			retained = append(retained, entry)
			continue
		}
		if _, e = mediaEntryInfo(entry); e != nil {
			retained = append(retained, entry)
			continue
		}
		if e = os.Remove(filepath.Join(entry.Directory, entry.Name)); e != nil {
			retained = append(retained, entry)
			continue
		}
		result.Clips = append(result.Clips, clipFromEntry(entry))
		result.Bytes += entry.Size
	}
	index.Entries = retained
	if e = writeJSON(mediaIndexPath(p), index); e != nil {
		return result, errors.New("selected clips were removed but their index could not be updated; remaining media was preserved")
	}
	result.Message = "Explicit cleanup completed for unchanged finalized clips only; other media was preserved"
	return result, nil
}
