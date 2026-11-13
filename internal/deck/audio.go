package deck

import "errors"

// AudioRouting contains identifiers only for local OBS configuration. Do not
// serialize device names: Bluetooth/USB names can contain private identifiers.
type AudioRouting struct {
	OutputMonitor         string `json:"-"`
	MicrophoneDevice      string `json:"-"`
	OutputMuted           bool   `json:"-"`
	MicrophoneMuted       bool   `json:"-"`
	MicrophoneRequested   bool   `json:"-"`
	MicrophoneStreamMuted bool   `json:"-"`
	RouteReason           string `json:"-"`
}

// AudioStatus reports routing facts, not proof that a game or viewer heard sound.
type AudioStatus struct {
	State               string `json:"state"`
	Message             string `json:"message"`
	RouteReason         string `json:"route_reason,omitempty"`
	OutputAvailable     bool   `json:"output_available"`
	OutputMuted         bool   `json:"output_muted"`
	MicrophoneRequested bool   `json:"microphone_requested"`
	MicrophoneAvailable bool   `json:"microphone_available"`
	MicrophoneMuted     bool   `json:"microphone_muted"`
	Signal              string `json:"signal"`
}

type audioDiscoveryError struct{ code string }

func (e *audioDiscoveryError) Error() string {
	switch e.code {
	case "missing-tool":
		return "Audio device discovery needs pactl. Check SteamOS PulseAudio/PipeWire utilities in Desktop Mode"
	case "query":
		return "The current Steam audio server could not be queried. Check the selected output device in SteamOS audio settings"
	case "limit":
		return "Audio device metadata exceeded its safe size limit; no route was changed"
	case "metadata":
		return "The audio server returned incomplete device metadata; no route was changed"
	case "output":
		return "The selected system output or its monitor is unavailable. Choose an output device in SteamOS audio settings and retry"
	case "microphone":
		return "The selected microphone is unavailable or is an output monitor. Choose a real microphone in SteamOS audio settings or turn microphone capture off"
	case "platform":
		return "Steam Deck audio routing requires Linux"
	default:
		return "Audio routing could not be confirmed; check SteamOS audio settings"
	}
}

func safeAudioStatus(route AudioRouting, err error) AudioStatus {
	status := AudioStatus{State: "ready", Message: "Selected system output monitor is available. Other apps on that output may also be captured; signal has not been measured", RouteReason: route.RouteReason, OutputAvailable: route.OutputMonitor != "", OutputMuted: route.OutputMuted, MicrophoneRequested: route.MicrophoneRequested, MicrophoneAvailable: route.MicrophoneDevice != "", MicrophoneMuted: route.MicrophoneMuted, Signal: "unmeasured"}
	if err != nil {
		status.State = "unavailable"
		status.Message = "Audio routing could not be confirmed. Check the current SteamOS output and microphone settings"
		var discovery *audioDiscoveryError
		if errors.As(err, &discovery) {
			status.Message = discovery.Error()
		}
	} else if route.OutputMonitor == "" {
		status.State = "unknown"
		status.Message = "Audio routing has not been observed in this session"
	} else if route.OutputMuted {
		status.State = "muted"
		status.Message = "The selected system output or its monitor is muted or has zero volume. OBSGod does not change system volume"
	} else if route.MicrophoneRequested && route.MicrophoneDevice == "" {
		status.State = "microphone-unavailable"
		status.MicrophoneMuted = true
		status.Message = "The selected microphone is unavailable; stream microphone capture stays muted without selecting another input"
	} else if route.MicrophoneRequested && route.MicrophoneStreamMuted {
		status.State = "microphone-muted"
		status.MicrophoneMuted = true
		status.Message = "Stream microphone is muted by saved mixer preferences; game audio and system microphone settings are unchanged"
	} else if route.MicrophoneRequested && route.MicrophoneMuted {
		status.State = "microphone-muted"
		status.Message = "System output is selected, but the requested microphone is muted or has zero volume in SteamOS"
	}
	return status
}
