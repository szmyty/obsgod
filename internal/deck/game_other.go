//go:build !linux

package deck

import "context"

type GameIdentity struct {
	AppID uint32 `json:"-"`
	State string `json:"state"`
}

func DiscoverGame(context.Context) GameIdentity { return GameIdentity{State: "unknown"} }
