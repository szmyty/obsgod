package automation

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

type workflowFixture struct {
	state         WorkflowSnapshot
	changes       []string
	reads         int
	failAfter     string
	activateAfter string
	unknown       bool
	ignoreScene   bool
}

func newWorkflowFixture() *workflowFixture {
	return &workflowFixture{state: WorkflowSnapshot{Profile: "Original", Collection: "Original", Scene: "Original", Profiles: []string{"Original", "Studio"}, Collections: []string{"Original", "Studio"}, Scenes: []string{"Original", "Starting", "Live"}}}
}
func (f *workflowFixture) WorkflowSnapshot(ctx context.Context) (WorkflowSnapshot, error) {
	f.reads++
	if err := ctx.Err(); err != nil {
		return WorkflowSnapshot{}, err
	}
	if f.unknown || (f.failAfter != "" && len(f.changes) > 0 && f.changes[len(f.changes)-1] == f.failAfter) {
		return WorkflowSnapshot{}, errors.New("private-server-text")
	}
	if f.activateAfter != "" && len(f.changes) > 0 && f.changes[len(f.changes)-1] == f.activateAfter {
		f.state.StreamActive = true
	}
	return f.state, nil
}
func (f *workflowFixture) SetWorkflowProfile(_ context.Context, name string) error {
	f.changes = append(f.changes, "profile")
	f.state.Profile = name
	return nil
}
func (f *workflowFixture) SetWorkflowCollection(_ context.Context, name string) error {
	f.changes = append(f.changes, "scene_collection")
	f.state.Collection = name
	return nil
}
func (f *workflowFixture) SetScene(_ context.Context, name string) error {
	f.changes = append(f.changes, name)
	if !f.ignoreScene {
		f.state.Scene = name
	}
	return nil
}
func (f *workflowFixture) StartRecording(context.Context) error {
	f.changes = append(f.changes, "recording")
	f.state.RecordingActive = true
	return nil
}
func (f *workflowFixture) StartWorkflowReplayBuffer(context.Context) error {
	f.changes = append(f.changes, "replay_buffer")
	f.state.ReplayBufferActive = true
	return nil
}
func (f *workflowFixture) Close() error { return nil }

func TestWorkflowRequiresSeparateApprovalsBeforeAnyOBSRead(t *testing.T) {
	for _, approvals := range []WorkflowApprovals{{}, {Settings: true}, {Settings: true, Recording: true}} {
		fixture := newWorkflowFixture()
		_, err := ApplyWorkflow(context.Background(), fixture, WorkflowPlan{RecordingEnabled: true, ReplayBufferEnabled: true}, approvals)
		if err == nil || fixture.reads != 0 || len(fixture.changes) != 0 {
			t.Fatalf("missing approval contacted OBS: reads=%d changes=%v err=%v", fixture.reads, fixture.changes, err)
		}
	}
}

func TestWorkflowAppliesReviewedStagesAndConfirmsRequestedLocalOutputs(t *testing.T) {
	fixture := newWorkflowFixture()
	plan := WorkflowPlan{OBSProfile: "Studio", SceneCollection: "Studio", StartingScene: "Starting", LiveScene: "Live", RecordingEnabled: true, ReplayBufferEnabled: true, PostStartDelay: "1ms"}
	result, err := ApplyWorkflow(context.Background(), fixture, plan, WorkflowApprovals{true, true, true})
	if err != nil || !result.OK || result.Attempted != "" {
		t.Fatalf("workflow failed: %+v %v", result, err)
	}
	if !reflect.DeepEqual(fixture.changes, []string{"profile", "scene_collection", "Starting", "Live", "replay_buffer", "recording"}) {
		t.Fatalf("unexpected stages: %v", fixture.changes)
	}
	if fixture.state.StreamActive || !fixture.state.RecordingActive || !fixture.state.ReplayBufferActive {
		t.Fatal("wrong final outputs")
	}
}

func TestWorkflowRejectsEveryActiveOrUnknownOutputWithoutChanges(t *testing.T) {
	for _, kind := range []string{"stream", "recording", "replay", "camera", "unknown"} {
		t.Run(kind, func(t *testing.T) {
			f := newWorkflowFixture()
			switch kind {
			case "stream":
				f.state.StreamActive = true
			case "recording":
				f.state.RecordingActive = true
			case "replay":
				f.state.ReplayBufferActive = true
			case "camera":
				f.state.VirtualCameraActive = true
			case "unknown":
				f.unknown = true
			}
			result, err := ApplyWorkflow(context.Background(), f, WorkflowPlan{OBSProfile: "Studio"}, WorkflowApprovals{Settings: true})
			if err == nil || result.OK || len(f.changes) != 0 || strings.Contains(err.Error(), "private-server-text") {
				t.Fatalf("unsafe active/unknown behavior: %+v %v %v", result, f.changes, err)
			}
		})
	}
}

func TestWorkflowStopsAfterConcurrentOutputOrLostReadiness(t *testing.T) {
	for _, kind := range []string{"active", "unknown"} {
		t.Run(kind, func(t *testing.T) {
			f := newWorkflowFixture()
			if kind == "active" {
				f.activateAfter = "profile"
			} else {
				f.failAfter = "profile"
			}
			result, err := ApplyWorkflow(context.Background(), f, WorkflowPlan{OBSProfile: "Studio", SceneCollection: "Studio", RecordingEnabled: true}, WorkflowApprovals{Settings: true, Recording: true})
			if err == nil || result.OK || !reflect.DeepEqual(f.changes, []string{"profile"}) || !reflect.DeepEqual(result.Applied, []string{"profile"}) || result.Attempted != "profile" {
				t.Fatalf("should preserve explicit partial state without further action: %+v %v %v", result, f.changes, err)
			}
		})
	}
}

func TestWorkflowDoesNotCreateMissingContentAndBoundsReadiness(t *testing.T) {
	f := newWorkflowFixture()
	if _, err := ApplyWorkflow(context.Background(), f, WorkflowPlan{OBSProfile: "Missing"}, WorkflowApprovals{Settings: true}); err == nil || len(f.changes) != 0 {
		t.Fatal("missing profile accepted or created")
	}
	f = newWorkflowFixture()
	f.ignoreScene = true
	start := time.Now()
	result, err := ApplyWorkflow(context.Background(), f, WorkflowPlan{StartingScene: "Starting", ReadinessTimeout: "100ms"}, WorkflowApprovals{Settings: true})
	if err == nil || result.OK || time.Since(start) > time.Second || !reflect.DeepEqual(f.changes, []string{"Starting"}) {
		t.Fatalf("readiness was unbounded or repeated mutation: %+v %v", result, err)
	}
}

func TestWorkflowCancellationDuringDelayPreventsLaterSceneAndOutput(t *testing.T) {
	f := newWorkflowFixture()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	result, err := ApplyWorkflow(ctx, f, WorkflowPlan{StartingScene: "Starting", LiveScene: "Live", PostStartDelay: "5s", RecordingEnabled: true}, WorkflowApprovals{Settings: true, Recording: true})
	if err == nil || result.OK || !reflect.DeepEqual(f.changes, []string{"Starting"}) {
		t.Fatalf("cancellation dispatched later stages: %+v %v %v", result, f.changes, err)
	}
}

func TestWorkflowTransportUsesV5InventoryAndExistingOnlySetters(t *testing.T) {
	type testCase struct {
		name, malformedOperation, malformedField string
		optionalCode                             int
		nullField                                bool
	}
	cases := []testCase{{name: "available", optionalCode: 100}, {name: "unavailable_optional_outputs", optionalCode: 604}, {name: "unknown_optional_outputs", optionalCode: 600}}
	for _, operation := range []string{"GetStreamStatus", "GetRecordStatus", "GetReplayBufferStatus", "GetVirtualCamStatus"} {
		fields := []string{"outputActive"}
		if operation == "GetStreamStatus" {
			fields = append(fields, "outputReconnecting")
		}
		for _, field := range fields {
			for _, null := range []bool{false, true} {
				cases = append(cases, testCase{name: operation + "/" + field + "/null=" + strconv.FormatBool(null), optionalCode: 100, malformedOperation: operation, malformedField: field, nullField: null})
			}
		}
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			optionalCode := test.optionalCode
			var lock sync.Mutex
			profile, collection, scene := "Original", "Original", "Original"
			replay, recording := false, false
			requests := []string{}
			up := websocket.Upgrader{}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				conn, err := up.Upgrade(w, r, nil)
				if err != nil {
					return
				}
				defer conn.Close()
				_ = conn.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
				var identify any
				if conn.ReadJSON(&identify) != nil {
					return
				}
				_ = conn.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
				for {
					var q struct {
						D struct {
							Type string         `json:"requestType"`
							ID   string         `json:"requestId"`
							Data map[string]any `json:"requestData"`
						} `json:"d"`
					}
					if conn.ReadJSON(&q) != nil {
						return
					}
					lock.Lock()
					requests = append(requests, q.D.Type)
					data := map[string]any{}
					code := 100
					switch q.D.Type {
					case "GetStreamStatus":
						data = map[string]any{"outputActive": false, "outputReconnecting": false}
					case "GetRecordStatus":
						data = map[string]any{"outputActive": recording, "outputBytes": 4096}
					case "GetReplayBufferStatus":
						code = optionalCode
						data = map[string]any{"outputActive": replay}
					case "GetVirtualCamStatus":
						code = optionalCode
						data = map[string]any{"outputActive": false}
					case "GetProfileList":
						data = map[string]any{"currentProfileName": profile, "profiles": []string{"Original", "Studio"}}
					case "GetSceneCollectionList":
						data = map[string]any{"currentSceneCollectionName": collection, "sceneCollections": []string{"Original", "Studio"}}
					case "GetSceneList":
						data = map[string]any{"currentProgramSceneName": scene, "scenes": []map[string]any{{"sceneName": "Original"}, {"sceneName": "Live"}}}
					case "SetCurrentProfile":
						profile = q.D.Data["profileName"].(string)
					case "SetCurrentSceneCollection":
						collection = q.D.Data["sceneCollectionName"].(string)
					case "SetCurrentProgramScene":
						scene = q.D.Data["sceneName"].(string)
					case "StartReplayBuffer":
						replay = true
					case "StartRecord":
						recording = true
					default:
						code = 204
					}
					if q.D.Type == test.malformedOperation {
						if test.nullField {
							data[test.malformedField] = nil
						} else {
							delete(data, test.malformedField)
						}
					}
					lock.Unlock()
					if conn.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": code == 100, "code": code}, "responseData": data}}) != nil {
						return
					}
				}
			}))
			defer server.Close()
			client, err := ConnectWorkflow(context.Background(), Config{Address: strings.TrimPrefix(server.URL, "http://")}, time.Second)
			if err != nil {
				t.Fatal(err)
			}
			defer client.Close()
			result, err := ApplyWorkflow(context.Background(), client, WorkflowPlan{OBSProfile: "Studio", SceneCollection: "Studio", LiveScene: "Live", RecordingEnabled: true, ReplayBufferEnabled: optionalCode == 100}, WorkflowApprovals{true, true, true})
			if optionalCode == 600 || test.malformedOperation != "" {
				if err == nil || result.OK {
					t.Fatal("unknown optionaloutput state did not block workflow")
				}
			} else if err != nil || !result.OK {
				t.Fatalf("protocol-backed workflow failed: %+v %v", result, err)
			}
			lock.Lock()
			defer lock.Unlock()
			for _, request := range requests {
				if (optionalCode == 600 || test.malformedOperation != "") && (strings.HasPrefix(request, "Set") || strings.HasPrefix(request, "Start")) {
					t.Fatal("unknown output allowed changes")
				}
				if request == "StartStream" || request == "StopStream" || strings.HasPrefix(request, "Create") {
					t.Fatalf("unexpected workflow request %s", request)
				}
			}

		})
	}
}
