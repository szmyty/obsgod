package v1

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	api "github.com/szmyty/obsgod/pkg/api/v1"
)

type fakeOBS struct {
	OBS
	state api.Snapshot
	calls []string
	fail  string
}

func (f *fakeOBS) call(name string) error {
	f.calls = append(f.calls, name)
	if f.fail == name {
		return errors.New("provider-echo-private-key")
	}
	return nil
}
func (f *fakeOBS) Snapshot(context.Context) (api.Snapshot, error) {
	e := f.call("snapshot")
	return f.state, e
}
func (f *fakeOBS) ApplyWorkflow(_ context.Context, p api.WorkflowPlan, _ api.Approval) (api.WorkflowResult, error) {
	e := f.call("settings")
	if e == nil {
		f.state.Profile = p.OBSProfile
		f.state.Collection = p.SceneCollection
		f.state.Scene = p.StartingScene
	}
	return api.WorkflowResult{OK: e == nil}, e
}
func (f *fakeOBS) ConfigureService(context.Context, api.RTMPService, api.Approval) error {
	return f.call("configure")
}
func (f *fakeOBS) VerifyService(context.Context, api.RTMPService) error { return f.call("verify") }
func (f *fakeOBS) StartStream(context.Context, api.Approval) (api.StreamState, error) {
	e := f.call("start")
	if e == nil {
		f.state.Stream = api.StreamState{Active: true, Bytes: 4096}
	}
	return f.state.Stream, e
}
func (f *fakeOBS) StopStream(context.Context, api.Approval) (api.StreamState, error) {
	e := f.call("stop")
	if e == nil {
		f.state.Stream = api.StreamState{}
	}
	return f.state.Stream, e
}
func (f *fakeOBS) StartRecording(context.Context, api.Approval) error {
	e := f.call("record.start")
	if e == nil {
		f.state.Recording.Active = true
	}
	return e
}
func (f *fakeOBS) StopRecording(context.Context, api.Approval) (string, error) {
	e := f.call("record.stop")
	if e == nil {
		f.state.Recording.Active = false
	}
	return "/fixture/finalized.mkv", e
}
func (f *fakeOBS) StartReplayBuffer(context.Context, api.Approval) error {
	e := f.call("replay.start")
	if e == nil {
		f.state.ReplayBufferActive = true
	}
	return e
}
func (f *fakeOBS) StopReplayBuffer(context.Context, api.Approval) error {
	e := f.call("replay.stop")
	if e == nil {
		f.state.ReplayBufferActive = false
	}
	return e
}
func (f *fakeOBS) SelectScene(_ context.Context, name string, _ api.Approval) error {
	e := f.call("scene")
	if e == nil {
		f.state.Scene = name
	}
	return e
}
func profile() Profile {
	return Profile{SchemaVersion: 1, Provider: ProviderConfig{ID: "kick", Server: "rtmps://example.invalid/app"}, Workflow: api.WorkflowPlan{OBSProfile: "Gaming", SceneCollection: "Games", StartingScene: "Starting", LiveScene: "Live", RecordingEnabled: true, ReplayBufferEnabled: true}, EndingScene: "Ending", StopRecording: true, StopReplayBuffer: true}
}
func approved() api.Approval {
	return api.Approval{Settings: true, Streaming: true, Recording: true, ReplayBuffer: true}
}
func service() api.RTMPService {
	return api.RTMPService{Server: "rtmps://example.invalid/app", Key: "private-key"}
}
func TestStartStopAndReconcileUsePublicBoundary(t *testing.T) {
	f := &fakeOBS{}
	p := profile()
	r, e := Start(context.Background(), f, p, service(), approved())
	if e != nil || !r.OK || r.Snapshot == nil || r.ProviderReception != "unknown" {
		t.Fatalf("start: %+v %v", r, e)
	}
	want := "snapshot,settings,configure,replay.start,record.start,start,scene,snapshot"
	if strings.Join(f.calls, ",") != want {
		t.Fatalf("start order: %v", f.calls)
	}
	f.calls = nil
	r, e = Start(context.Background(), f, p, service(), approved())
	if e != nil || !r.OK {
		t.Fatalf("repeat: %+v %v", r, e)
	}
	if strings.Join(f.calls, ",") != "snapshot,verify,start,scene,snapshot" {
		t.Fatalf("repeat changed configuration: %v", f.calls)
	}
	f.calls = nil
	r, e = Stop(context.Background(), f, p, approved())
	if e != nil || !r.OK || r.Snapshot.Stream.Active || r.Snapshot.Recording.Active || r.Snapshot.ReplayBufferActive {
		t.Fatalf("stop: %+v %v", r, e)
	}
	if strings.Join(f.calls, ",") != "snapshot,scene,stop,record.stop,replay.stop,snapshot" {
		t.Fatalf("stop order: %v", f.calls)
	}
}
func TestApprovalsAndValidationPrecedeNetwork(t *testing.T) {
	for _, a := range []api.Approval{{}, {Settings: true, Streaming: true}, {Settings: true, Streaming: true, Recording: true}} {
		f := &fakeOBS{}
		r, e := Start(context.Background(), f, profile(), service(), a)
		if e == nil || len(f.calls) != 0 || r.Error == nil || len(r.Events) != 1 {
			t.Fatalf("unapproved mutation: %+v %v %v", r, e, f.calls)
		}
	}
	f := &fakeOBS{}
	p := profile()
	p.SchemaVersion = 2
	r, e := Start(context.Background(), f, p, service(), approved())
	if e == nil || len(f.calls) != 0 || r.Error == nil {
		t.Fatal("invalid profile connected")
	}
}
func TestPartialFailureKeepsOutputsAndSanitizesEvidence(t *testing.T) {
	f := &fakeOBS{fail: "scene"}
	r, e := Start(context.Background(), f, profile(), service(), approved())
	if e == nil || r.OK || r.Error == nil || !f.state.Stream.Active || !f.state.Recording.Active || !f.state.ReplayBufferActive {
		t.Fatalf("partial result: %+v %v", r, e)
	}
	for _, call := range f.calls {
		if call == "stop" || call == "record.stop" || call == "replay.stop" {
			t.Fatal("blind rollback stopped outputs")
		}
	}
	b, _ := json.Marshal(r)
	if strings.Contains(string(b), "private-key") || strings.Contains(e.Error(), "private-key") {
		t.Fatal("free-form failure leaked")
	}
	if got := r.Events[len(r.Events)-1]; got.Stage != "live_scene" || got.Outcome != "failed" {
		t.Fatalf("partial stage missing: %+v", r)
	}
}
func TestStopPolicyPreservesUnselectedLocalOutputs(t *testing.T) {
	p := profile()
	p.StopRecording = false
	p.StopReplayBuffer = false
	p.EndingScene = ""
	f := &fakeOBS{state: api.Snapshot{Stream: api.StreamState{Active: true}, Recording: api.RecordingState{Active: true}, ReplayBufferActive: true}}
	r, e := Stop(context.Background(), f, p, api.Approval{Streaming: true})
	if e != nil || !r.OK || !r.Snapshot.Recording.Active || !r.Snapshot.ReplayBufferActive {
		t.Fatalf("local policy: %+v %v", r, e)
	}
	if strings.Join(f.calls, ",") != "snapshot,stop,snapshot" {
		t.Fatalf("unrequested local actions: %v", f.calls)
	}
}
func TestDifferentActiveWorkflowIsNotReconfigured(t *testing.T) {
	f := &fakeOBS{state: api.Snapshot{Stream: api.StreamState{Active: true}, Profile: "Other"}}
	r, e := Start(context.Background(), f, profile(), service(), approved())
	if e == nil || r.Error == nil || r.Error.Code != api.Conflict || strings.Join(f.calls, ",") != "snapshot" {
		t.Fatalf("active conflict: %+v %v", r, e)
	}
}
func TestProfileStrictnessAndPluggableProviders(t *testing.T) {
	p := profile()
	b, _ := json.Marshal(p)
	if _, e := DecodeProfile(strings.NewReader(string(b))); e != nil {
		t.Fatal(e)
	}
	for _, body := range []string{string(b) + "{}", `null`, strings.Replace(string(b), `"provider":{`, `"provider":{"key":"private",`, 1), strings.Replace(string(b), `"schema_version":1`, `"schema_version":2`, 1)} {
		if _, e := DecodeProfile(strings.NewReader(body)); e == nil {
			t.Fatalf("invalid profile accepted: %s", body)
		}
	}
	lookups := []string{}
	lookup := func(name string) (string, bool) { lookups = append(lookups, name); return "private-key", true }
	s, e := ResolveService(p, BuiltinProviders(), lookup)
	if e != nil || s.Key != "private-key" || strings.Join(lookups, ",") != "KICK_STREAM_KEY" {
		t.Fatal("Kick env resolution")
	}
	p.Provider.ID = "independent"
	p.Provider.KeyEnv = "INDEPENDENT_KEY"
	s, e = ResolveService(p, []Provider{RTMPProvider{Name: "independent", DefaultKeyEnv: "INDEPENDENT_KEY"}}, lookup)
	if e != nil || s.Key == "" {
		t.Fatal("provider required OBS core change")
	}
	plan, _ := json.Marshal(p.Review())
	if strings.Contains(string(plan), "example.invalid") || strings.Contains(string(plan), "private-key") {
		t.Fatal("review exposed endpoint/secret")
	}
}
