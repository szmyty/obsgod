package deck

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"time"
)

const resilienceAttempts = 3
const resilienceInterval = 2 * time.Second
const resilienceFreshness = 8 * time.Second

// ResilienceStatus reports the local observer, never provider/viewer reception.
// Device names, game identifiers, session addresses and raw errors stay private.
type ResilienceStatus struct {
	State       string    `json:"state"`
	Message     string    `json:"message"`
	Watching    bool      `json:"watching"`
	OutputKnown bool      `json:"output_known"`
	Failures    int       `json:"failures"`
	Recoveries  int       `json:"recoveries"`
	Updated     time.Time `json:"updated"`
}

type resilienceRecord struct {
	ResilienceStatus
	PID int `json:"pid"`
}

func resiliencePaths(p Paths) Paths {
	p.State = filepath.Join(p.State, "resilience-watch")
	return p
}

func resilienceMessage(state string) string {
	switch state {
	case "observing":
		return "Watching the selected audio route while managed output is active; mixer gain, mute and system volume are preserved"
	case "recovering":
		return "Audio, storage or control recovery is retrying within its three-attempt limit; verify sound in a clip or on your channel"
	case "exhausted":
		return "Automatic recovery reached its three-attempt limit. Check the selected SteamOS audio devices and managed OBS, then explicitly retry recovery. Output was not restarted"
	case "stopped":
		return "The audio observer is stopped; it never starts or restarts a broadcast, recording or OBS"
	case "unmanaged":
		return "Recovery stopped because the managed OBS profile or scene collection is no longer selected; no route was changed"
	default:
		return "Current audio recovery state is unconfirmed; inspect audio diagnostics and managed OBS before retrying"
	}
}

func validResilienceState(state string) bool {
	switch state {
	case "observing", "recovering", "exhausted", "stopped", "unmanaged", "unknown":
		return true
	}
	return false
}

func readResilienceRecord(p Paths) (resilienceRecord, bool) {
	var record resilienceRecord
	path := filepath.Join(resiliencePaths(p).State, "status.json")
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 4096 || readJSON(path, &record) != nil || !validResilienceState(record.State) || record.Failures < 0 || record.Failures > resilienceAttempts || record.Recoveries < 0 {
		return record, false
	}
	age := time.Since(record.Updated)
	if record.Updated.IsZero() || age > resilienceFreshness || age < -time.Second {
		return record, false
	}
	return record, true
}

func ReadResilienceStatus(p Paths) ResilienceStatus {
	record, fresh := readResilienceRecord(p)
	if !fresh {
		return ResilienceStatus{State: "unknown", Message: resilienceMessage("unknown")}
	}
	// Fixed messages are reconstructed: a modified state file cannot inject raw
	// device/server data into the public diagnostics console or support bundle.
	record.Message = resilienceMessage(record.State)
	return record.ResilienceStatus
}

func saveResilienceStatus(p Paths, state string, watching, known bool, failures, recoveries int) error {
	return writeJSON(filepath.Join(resiliencePaths(p).State, "status.json"), resilienceRecord{ResilienceStatus: ResilienceStatus{
		State: state, Message: resilienceMessage(state), Watching: watching, OutputKnown: known,
		Failures: failures, Recoveries: recoveries, Updated: time.Now().UTC(),
	}, PID: os.Getpid()})
}

type resilienceObservation struct {
	Managed bool
	Active  bool
}

// The observer's transport intentionally has no broadcast or scene methods.
// GuardMedia may finalize local outputs at their explicitly configured storage
// reserve. It cannot start output, delete clips or stop the broadcast.
// Unknown snapshots must be errors, never zero-value "stopped" observations.
type resilienceConnection interface {
	Observe(context.Context) (resilienceObservation, error)
	GuardMedia(context.Context, Paths) error
	Rebind(context.Context, Settings, AudioRouting) (bool, error)
	Close() error
}

type resilienceDeps struct {
	load     func(Paths) (Settings, Secrets, error)
	connect  func(context.Context, Secrets) (resilienceConnection, error)
	discover func(context.Context, bool) (AudioRouting, error)
	wait     func(context.Context, time.Duration) error
	interval time.Duration
}

// watchResilienceWith follows device changes only for already-active output.
// It observes before discovery and again under the same control lease used by
// explicit actions, preventing a delayed device query from racing Stop/config.
func watchResilienceWith(ctx context.Context, p Paths, deps resilienceDeps) error {
	leaseCtx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
	unlock, err := Lock(leaseCtx, resiliencePaths(p))
	cancel()
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if errors.Is(err, context.DeadlineExceeded) {
			return nil // The existing lifetime owner remains authoritative.
		}
		return errors.New("audio recovery could not establish its private lifetime lease")
	}
	defer unlock()
	if deps.wait == nil {
		deps.wait = wait
	}
	if deps.interval <= 0 {
		deps.interval = resilienceInterval
	}
	failures, recoveries := 0, 0
	for {
		if err := ctx.Err(); err != nil {
			_ = saveResilienceStatus(p, "stopped", false, false, failures, recoveries)
			return err
		}
		settings, secret, err := deps.load(p)
		if err != nil {
			_ = saveResilienceStatus(p, "unknown", false, false, failures, recoveries)
			return errors.New("audio recovery could not load verified local settings; no output was started")
		}
		cycle, done := context.WithTimeout(ctx, 5*time.Second)
		connection, cycleErr := deps.connect(cycle, secret)
		known, idle, unmanaged, changed, busy := false, false, false, false, false
		if cycleErr == nil {
			observed, observeErr := connection.Observe(cycle)
			cycleErr = observeErr
			if cycleErr == nil {
				known = true
				unmanaged, idle = !observed.Managed, !observed.Active
				if observed.Managed && observed.Active {
					// Early handshake lets a Start holding the control lease finish
					// without waiting for its observer to acquire that same lease.
					_ = saveResilienceStatus(p, "observing", true, true, failures, recoveries)
					// The storage guard owns its short control lease, so it runs
					// before the audio lease below and cannot deadlock explicit Stop.
					guardErr := connection.GuardMedia(cycle, p)
					if guardErr != nil {
						known = false // A local finalization may be unconfirmed.
					}
					route, routeErr := AudioRouting{}, guardErr
					if routeErr == nil {
						route, routeErr = deps.discover(cycle, settings.Microphone)
					}
					status := safeAudioStatus(route, routeErr)
					cycleErr = routeErr
					if cycleErr == nil {
						controlCtx, controlCancel := context.WithTimeout(cycle, 250*time.Millisecond)
						controlUnlock, lockErr := Lock(controlCtx, p)
						controlCancel()
						if lockErr != nil {
							if errors.Is(lockErr, context.DeadlineExceeded) || errors.Is(lockErr, context.Canceled) {
								busy = true // An explicit Start/Stop/configuration wins.
							} else {
								cycleErr = lockErr
								known = false
							}
						} else {
							observed, cycleErr = connection.Observe(cycle)
							known = cycleErr == nil
							if cycleErr == nil {
								unmanaged, idle = !observed.Managed, !observed.Active
								if observed.Managed && observed.Active {
									changed, cycleErr = connection.Rebind(cycle, settings, route)
								}
							}
							controlUnlock()
						}
						if cycleErr != nil {
							known = false
							status.State, status.Signal = "unknown", "unknown"
							status.Message = "OBS could not verify the selected audio route; automatic recovery is bounded and has not changed system volume or restarted output"
						}
					}
					if !busy && !unmanaged && !idle && guardErr == nil {
						saveAudioStatus(p, status)
					}
				}
			}
			_ = connection.Close()
		}
		done()
		if unmanaged {
			_ = saveResilienceStatus(p, "unmanaged", false, known, failures, recoveries)
			return errors.New(resilienceMessage("unmanaged"))
		}
		if idle {
			return saveResilienceStatus(p, "stopped", false, true, failures, recoveries)
		}
		if changed {
			recoveries++
		}
		delay, state := deps.interval, "observing"
		if cycleErr != nil {
			failures++
			state = "recovering"
			// Two waits at 2s and 4s, then stop after the third failed cycle.
			delay = deps.interval * time.Duration(1<<(failures-1))
			if failures >= resilienceAttempts {
				_ = saveResilienceStatus(p, "exhausted", false, known, failures, recoveries)
				return errors.New(resilienceMessage("exhausted"))
			}
		} else if !busy {
			failures = 0
		}
		if err := saveResilienceStatus(p, state, true, known, failures, recoveries); err != nil {
			return err
		}
		if err := deps.wait(ctx, delay); err != nil {
			_ = saveResilienceStatus(p, "stopped", false, false, failures, recoveries)
			return err
		}
	}
}
