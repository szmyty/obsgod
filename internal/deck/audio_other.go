//go:build !linux

package deck

import "context"

func DiscoverAudio(context.Context, bool) (AudioRouting, error) {
	return AudioRouting{}, &audioDiscoveryError{code: "platform"}
}
