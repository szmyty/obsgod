//go:build linux

package deck

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/szmyty/obsgod/pkg/automation"
)

type videoItem struct {
	id      int
	enabled bool
}
type videoInput struct {
	kind     string
	settings map[string]any
}
type videoFixture struct {
	mu                sync.Mutex
	scene, collection string
	active, visible   bool
	scenes            map[string]map[string]*videoItem
	inputs            map[string]*videoInput
	requests          []fixtureRequest
	next              int
	image             string
}

func newVideoFixture(t *testing.T) *videoFixture {
	t.Helper()
	im := image.NewRGBA(image.Rect(0, 0, 160, 100))
	for y := 0; y < 100; y++ {
		for x := 0; x < 160; x++ {
			im.Set(x, y, color.RGBA{uint8(x), uint8(y), 100, 255})
		}
	}
	var encoded bytes.Buffer
	if err := png.Encode(&encoded, im); err != nil {
		t.Fatal(err)
	}
	f := &videoFixture{scene: IdleScene, collection: "OBSGod", active: true, visible: true, scenes: map[string]map[string]*videoItem{}, inputs: map[string]*videoInput{}, image: "data:image/png;base64," + base64.StdEncoding.EncodeToString(encoded.Bytes())}
	for _, scene := range []string{IdleScene, LiveScene, GameScene} {
		f.scenes[scene] = map[string]*videoItem{}
	}
	f.inputs["unexpected display"] = &videoInput{kind: "gstreamer-source", settings: map[string]any{"pipeline": CapturePipeline}}
	for _, scene := range []string{IdleScene, GameScene} {
		f.next++
		f.scenes[scene]["unexpected display"] = &videoItem{id: f.next, enabled: true}
	}
	return f
}
func (f *videoFixture) server(t *testing.T) *httptest.Server {
	t.Helper()
	up := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.WriteJSON(map[string]any{"op": 0, "d": map[string]any{"rpcVersion": 1}})
		var identify any
		if c.ReadJSON(&identify) != nil {
			return
		}
		_ = c.WriteJSON(map[string]any{"op": 2, "d": map[string]any{"negotiatedRpcVersion": 1}})
		for {
			var q struct {
				D fixtureRequest `json:"d"`
			}
			if c.ReadJSON(&q) != nil {
				return
			}
			f.mu.Lock()
			f.requests = append(f.requests, q.D)
			data := f.handle(q.D)
			f.mu.Unlock()
			if c.WriteJSON(map[string]any{"op": 7, "d": map[string]any{"requestType": q.D.Type, "requestId": q.D.ID, "requestStatus": map[string]any{"result": true, "code": 100}, "responseData": data}}) != nil {
				return
			}
		}
	}))
	t.Cleanup(server.Close)
	return server
}
func (f *videoFixture) handle(q fixtureRequest) map[string]any {
	data := map[string]any{}
	scene, _ := q.Data["sceneName"].(string)
	name, _ := q.Data["inputName"].(string)
	switch q.Type {
	case "GetVersion":
		data["obsVersion"] = "33.0.1"
		data["obsWebSocketVersion"] = "5.6.3"
	case "GetProfileList":
		data["currentProfileName"] = "OBSGod"
	case "GetSceneCollectionList":
		data["currentSceneCollectionName"] = f.collection
	case "GetCurrentProgramScene":
		data["sceneName"] = f.scene
	case "GetReplayBufferStatus":
		data["outputActive"] = false
	case "GetRecordStatus":
		data["outputActive"] = false
	case "GetStreamStatus":
		data["outputActive"] = f.active
		data["outputReconnecting"] = false
		data["outputBytes"] = 4096
	case "GetSceneList":
		list := []map[string]any{}
		for name := range f.scenes {
			list = append(list, map[string]any{"sceneName": name})
		}
		data["scenes"] = list
	case "CreateScene":
		f.scenes[scene] = map[string]*videoItem{}
	case "SetCurrentProgramScene":
		f.scene = scene
	case "GetInputKindList":
		data["inputKinds"] = []string{"gstreamer-source", "text_ft2_source_v2", "image_source", "ffmpeg_source", "pulse_output_capture", "pulse_input_capture"}
	case "GetInputList":
		list := []map[string]any{}
		for name, input := range f.inputs {
			list = append(list, map[string]any{"inputName": name, "inputKind": input.kind})
		}
		data["inputs"] = list
	case "CreateInput":
		kind, _ := q.Data["inputKind"].(string)
		settings := map[string]any{}
		for key, value := range q.Data["inputSettings"].(map[string]any) {
			settings[key] = value
		}
		f.inputs[name] = &videoInput{kind: kind, settings: settings}
		f.next++
		enabled, _ := q.Data["sceneItemEnabled"].(bool)
		f.scenes[scene][name] = &videoItem{id: f.next, enabled: enabled}
	case "SetInputSettings":
		if input := f.inputs[name]; input != nil {
			for key, value := range q.Data["inputSettings"].(map[string]any) {
				input.settings[key] = value
			}
		}
	case "GetSceneItemList":
		list := []map[string]any{}
		for source, item := range f.scenes[scene] {
			list = append(list, map[string]any{"sourceName": source, "sceneItemId": item.id, "sceneItemEnabled": item.enabled})
		}
		data["sceneItems"] = list
	case "CreateSceneItem":
		source, _ := q.Data["sourceName"].(string)
		f.next++
		f.scenes[scene][source] = &videoItem{id: f.next, enabled: true}
	case "GetSceneItemId":
		source, _ := q.Data["sourceName"].(string)
		if item := f.scenes[scene][source]; item != nil {
			data["sceneItemId"] = item.id
		}
	case "SetSceneItemEnabled":
		id, _ := q.Data["sceneItemId"].(float64)
		enabled, _ := q.Data["sceneItemEnabled"].(bool)
		for _, item := range f.scenes[scene] {
			if item.id == int(id) {
				item.enabled = enabled
			}
		}
	case "GetSourceScreenshot":
		source, _ := q.Data["sourceName"].(string)
		data["imageData"] = "blank"
		if source == GameCaptureInput && f.visible && f.inputs[GameCaptureInput] != nil {
			data["imageData"] = f.image
		}
	}
	return data
}
func videoClient(t *testing.T, f *videoFixture) (*automation.Client, func(context.Context, Secrets) (*automation.Client, error)) {
	t.Helper()
	server := f.server(t)
	dial := func(ctx context.Context, _ Secrets) (*automation.Client, error) {
		return automation.Connect(ctx, automation.Config{Address: strings.TrimPrefix(server.URL, "http://"), Timeout: time.Second})
	}
	c, err := dial(context.Background(), Secrets{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c, dial
}
func assertNoOutputCommands(t *testing.T, f *videoFixture) {
	t.Helper()
	for _, request := range f.requests {
		switch request.Type {
		case "StartStream", "StopStream", "StartRecord", "StopRecord":
			t.Fatalf("observer issued forbidden output command %s", request.Type)
		}
		if request.Type == "SetCurrentProgramScene" && request.Data["sceneName"] == LiveScene {
			t.Fatal("game controller selected the full display scene")
		}
	}
}
func TestGameVideoNeverFallsBackToDisplayAndExcludesUnknownSources(t *testing.T) {
	for _, test := range []struct {
		name    string
		game    GameIdentity
		visible bool
		want    string
	}{{"game", GameIdentity{AppID: 42, State: "running"}, true, GameScene}, {"no-game", GameIdentity{State: "idle"}, true, IdleScene}, {"ambiguous", GameIdentity{State: "ambiguous"}, true, IdleScene}, {"steam-ui", GameIdentity{AppID: 769, State: "running"}, true, IdleScene}, {"blank-game", GameIdentity{AppID: 42, State: "running"}, false, IdleScene}} {
		t.Run(test.name, func(t *testing.T) {
			f := newVideoFixture(t)
			f.visible = test.visible
			c, _ := videoClient(t, f)
			p := testPaths(t)
			s := DefaultSettings()
			s.CaptureMode = "game"
			if err := ensureVideoForGame(context.Background(), c, p, s, test.game); err != nil {
				t.Fatal(err)
			}
			f.mu.Lock()
			defer f.mu.Unlock()
			if f.scene != test.want {
				t.Fatalf("scene=%q want%q", f.scene, test.want)
			}
			for _, scene := range []string{GameScene, IdleScene} {
				if f.scenes[scene]["unexpected display"].enabled {
					t.Fatalf("unexpected source remained visible in %s", scene)
				}
			}
			if input := f.inputs[GameCaptureInput]; input != nil {
				pipeline := input.settings["pipeline"].(string)
				if !strings.Contains(pipeline, "obsgodgamescopesrc app-id=42") || strings.Contains(pipeline, "pipewiresrc") {
					t.Fatalf("unsafe game pipeline %q", pipeline)
				}
			}
			assertNoOutputCommands(t, f)
		})
	}
}
func TestIdlePlaceholderIsOpaquePlainTextAndCanReturnToBlack(t *testing.T) {
	f := newVideoFixture(t)
	f.inputs[IdlePlaceholderInput] = &videoInput{kind: "text_ft2_source_v2", settings: map[string]any{"from_file": true, "text_file": "private-file", "log_mode": true}}
	f.next++
	f.scenes[IdleScene][IdlePlaceholderInput] = &videoItem{id: f.next, enabled: true}
	c, _ := videoClient(t, f)
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	s.IdleStyle = "placeholder"
	s.IdleText = "private custom text"
	if err := ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	input := f.inputs[IdlePlaceholderInput]
	if input.settings["from_file"] != false || input.settings["text_file"] != "" || input.settings["log_mode"] != false || input.settings["color1"] != float64(0xFFFFFFFF) {
		t.Fatal("placeholder retained file-reading or transparent settings", input.settings)
	}
	f.mu.Unlock()
	s.IdleStyle = "black"
	if err := ensureVideoForGame(context.Background(), c, p, s, GameIdentity{State: "idle"}); err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	if f.scenes[IdleScene][IdlePlaceholderInput].enabled {
		t.Fatal("black fallback retained visible text")
	}
	f.mu.Unlock()
	data, err := json.Marshal(ReadCaptureVideoStatus(p))
	if err != nil || strings.Contains(string(data), s.IdleText) || strings.Contains(string(data), "app_id") || strings.Contains(string(data), "pid") {
		t.Fatal("private capture data entered status", string(data), err)
	}
}
func TestCaptureStatusRejectsStaleOrUntrustedFields(t *testing.T) {
	p := testPaths(t)
	s := DefaultSettings()
	s.CaptureMode = "game"
	if err := writeCaptureVideoStatus(p, s, "idle", "placeholder", true, os.Getpid()); err != nil {
		t.Fatal(err)
	}
	var record captureVideoRecord
	if err := readJSON(captureVideoPath(p), &record); err != nil {
		t.Fatal(err)
	}
	record.Updated = time.Now().Add(-6 * time.Second)
	if err := writeJSON(captureVideoPath(p), record); err != nil {
		t.Fatal(err)
	}
	if status := ReadCaptureVideoStatus(p); status.State != "unknown" || status.Watching {
		t.Fatalf("stale observer accepted %+v", status)
	}
}
