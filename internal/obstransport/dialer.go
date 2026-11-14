// Package obstransport carries private construction dependencies between the
// legacy adapter and the shared OBS connection. It is not a public API option.
package obstransport

import (
	"context"

	"github.com/andreykaipov/goobs"
)

type Dialer func(string, ...goobs.Option) (*goobs.Client, error)

type key struct{}
type options struct {
	dialer    Dialer
	userAgent string
}

// WithDialer preserves the legacy injected construction seam without exposing
// protocol clients in a public facade constructor or model.
func WithDialer(ctx context.Context, dialer Dialer, userAgent string) context.Context {
	return context.WithValue(ctx, key{}, options{dialer, userAgent})
}

func FromContext(ctx context.Context) (Dialer, string) {
	value, _ := ctx.Value(key{}).(options)
	return value.dialer, value.userAgent
}
