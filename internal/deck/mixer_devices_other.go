//go:build !linux

package deck

import (
	"context"
	"os"
)

func MixerDevices(context.Context) ([]MixerDevice, map[string]bool, error) {
	return nil, nil, &audioDiscoveryError{code: "platform"}
}
func MixerHardwareInfo() MixerHardware {
	return MixerHardware{Model: "unknown", Guidance: "Steam Deck audio device discovery requires Linux"}
}

func openMixerFile(path string) (*os.File, error) { return os.Open(path) }
