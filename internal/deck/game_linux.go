//go:build linux

package deck

import (
	"context"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type GameIdentity struct {
	AppID uint32 `json:"-"`
	State string `json:"state"`
}

func steamAppID(env []byte) uint32 {
	for _, pair := range strings.Split(string(env), "\x00") {
		key, value, ok := strings.Cut(pair, "=")
		if ok && key == "SteamAppId" {
			n, err := strconv.ParseUint(value, 10, 32)
			if err == nil && n != 0 && n != 769 {
				return uint32(n)
			}
		}
	}
	return 0
}

func gameAppIDs(ctx context.Context, root string, uid int) []uint32 {
	processes, _ := filepath.Glob(filepath.Join(root, "[0-9]*"))
	seen := map[uint32]bool{}
	for _, proc := range processes {
		if ctx.Err() != nil {
			break
		}
		info, err := os.Stat(proc)
		if err != nil {
			continue
		}
		stat, ok := info.Sys().(*syscall.Stat_t)
		if !ok || int(stat.Uid) != uid || processExited(proc) {
			continue
		}
		name, _ := os.ReadFile(filepath.Join(proc, "comm"))
		switch strings.TrimSpace(string(name)) {
		case "steam", "steamwebhelper", "obs", "obsgod":
			continue
		}
		env, err := os.ReadFile(filepath.Join(proc, "environ"))
		if err == nil && len(env) <= 1024*1024 {
			if id := steamAppID(env); id != 0 {
				seen[id] = true
			}
		}
	}
	result := make([]uint32, 0, len(seen))
	for id := range seen {
		result = append(result, id)
	}
	sort.Slice(result, func(i, j int) bool { return result[i] < result[j] })
	return result
}

func chooseGame(ids []uint32, focused uint32) GameIdentity {
	if len(ids) == 0 {
		return GameIdentity{State: "idle"}
	}
	if focused != 0 {
		for _, id := range ids {
			if id == focused {
				return GameIdentity{AppID: id, State: "running"}
			}
		}
	}
	if len(ids) == 1 {
		return GameIdentity{AppID: ids[0], State: "running"}
	}
	return GameIdentity{State: "ambiguous"}
}

func parseGraphicsApp(data []byte) uint32 {
	line := strings.TrimSpace(string(data))
	const prefix = "GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = "
	if !strings.HasPrefix(line, prefix) {
		return 0
	}
	n, err := strconv.ParseUint(strings.TrimPrefix(line, prefix), 10, 32)
	if err != nil || n == 0 || n == 769 {
		return 0
	}
	return uint32(n)
}

func DiscoverGame(ctx context.Context) GameIdentity {
	ids := gameAppIDs(ctx, "/proc", os.Getuid())
	if len(ids) <= 1 {
		return chooseGame(ids, 0)
	}
	// xprop is optional. Without unambiguous graphics focus, overlapping games
	// show fallback rather than selecting an arbitrary application or Steam UI.
	probe, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
	defer cancel()
	data, err := commandOutput(probe, "xprop", "-root", "GAMESCOPE_FOCUSED_APP_GFX")
	if err != nil || len(data) > 1024 {
		return chooseGame(ids, 0)
	}
	return chooseGame(ids, parseGraphicsApp(data))
}
