// Package automation provides context-aware, provider-independent OBS operations.
// The transport is OBS WebSocket v5 through goobs. It never logs credentials or
// returns server-supplied error comments, which can contain sensitive settings.
package automation

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"regexp"
	"strconv"
	"time"

	"github.com/andreykaipov/goobs"
	"github.com/gorilla/websocket"
)

// Config describes an OBS connection. Password must come from a secret source.
type Config struct {
	Address  string
	Password string
	Timeout  time.Duration
}

// Client owns one connection. Operations on a Client must be sequential.
type Client struct{ obs *goobs.Client }

// RequestError exposes a protocol status code without the server's free-form
// comment or response body. Those fields are deliberately excluded.
type RequestError struct {
	Operation string
	Code      int
}

func (e *RequestError) Error() string {
	return fmt.Sprintf("OBS %s failed (code %d); check OBSGod diagnostics on the device", e.Operation, e.Code)
}

var statusCode = regexp.MustCompile(`\(([0-9]{3})\)`)

// Connect establishes an authenticated connection with bounded readiness.
func Connect(ctx context.Context, cfg Config) (*Client, error) {
	if _, _, err := net.SplitHostPort(cfg.Address); err != nil {
		return nil, errors.New("invalid OBS address: use host:port")
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 3 * time.Second
	}
	dialer := &websocket.Dialer{HandshakeTimeout: cfg.Timeout, NetDialContext: func(_ context.Context, network, address string) (net.Conn, error) {
		return (&net.Dialer{Timeout: cfg.Timeout}).DialContext(ctx, network, address)
	}}
	type result struct {
		client *goobs.Client
		err    error
	}
	ch := make(chan result)
	go func() {
		c, err := goobs.New(cfg.Address, goobs.WithPassword(cfg.Password), goobs.WithDialer(dialer),
			goobs.WithResponseTimeoutDuration(cfg.Timeout), goobs.WithEventSubscriptions(0), goobs.WithLogger(log.New(io.Discard, "", 0)))
		select {
		case ch <- result{c, err}:
		case <-ctx.Done():
			if c != nil {
				_ = c.Disconnect()
			}
		}
	}()
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case r := <-ch:
		if r.err != nil {
			return nil, errors.New("OBS connection failed: check that OBS and WebSocket authentication are ready")
		}
		return &Client{obs: r.client}, nil
	}
}

// Close releases the connection. Pending operations have a bounded timeout.
func (c *Client) Close() error { return c.obs.Disconnect() }

func request[T any](ctx context.Context, name string, f func() (T, error)) (T, error) {
	var zero T
	if err := ctx.Err(); err != nil {
		return zero, err
	}
	type result struct {
		value T
		err   error
	}
	ch := make(chan result, 1)
	go func() { v, e := f(); ch <- result{v, e} }()
	select {
	case <-ctx.Done():
		return zero, ctx.Err()
	case r := <-ch:
		if r.err != nil {
			code := 0
			if match := statusCode.FindStringSubmatch(r.err.Error()); len(match) == 2 {
				code, _ = strconv.Atoi(match[1])
			}
			return zero, &RequestError{Operation: name, Code: code}
		}
		return r.value, nil
	}
}

func empty[P, T any](ctx context.Context, name string, f func(...P) (T, error)) (T, error) {
	return request(ctx, name, func() (T, error) { return f() })
}

// StreamStatus is OBS's output state, not a provider-side audience confirmation.
type StreamStatus struct {
	Active        bool    `json:"active"`
	Reconnecting  bool    `json:"reconnecting"`
	Bytes         float64 `json:"bytes"`
	Duration      float64 `json:"duration_ms"`
	SkippedFrames float64 `json:"skipped_frames"`
	TotalFrames   float64 `json:"total_frames"`
}

func (c *Client) StreamStatus(ctx context.Context) (StreamStatus, error) {
	r, err := request(ctx, "GetStreamStatus", func() (*streamResponse, error) { return c.streamStatus() })
	if err != nil {
		return StreamStatus{}, err
	}
	return *r, nil
}

type streamResponse = StreamStatus

func (c *Client) streamStatus() (*streamResponse, error) {
	r, e := c.obs.Stream.GetStreamStatus()
	if e != nil {
		return nil, e
	}
	return &StreamStatus{Active: r.OutputActive, Reconnecting: r.OutputReconnecting, Bytes: r.OutputBytes, Duration: r.OutputDuration, SkippedFrames: r.OutputSkippedFrames, TotalFrames: r.OutputTotalFrames}, nil
}

// StartStream is idempotent and waits for advancing output bytes.
func (c *Client) StartStream(ctx context.Context) (StreamStatus, error) {
	s, err := c.StreamStatus(ctx)
	if err != nil {
		return s, err
	}
	if !s.Active {
		if _, err := empty(ctx, "StartStream", c.obs.Stream.StartStream); err != nil {
			return s, err
		}
	}
	baseline := s.Bytes
	for {
		s, err = c.StreamStatus(ctx)
		if err != nil {
			return s, err
		}
		if s.Active && !s.Reconnecting && s.Bytes > baseline {
			return s, nil
		}
		if err := pause(ctx, 400*time.Millisecond); err != nil {
			return s, err
		}
	}
}

// StopStream is safe to repeat and waits until the output has stopped.
func (c *Client) StopStream(ctx context.Context) (StreamStatus, error) {
	s, err := c.StreamStatus(ctx)
	if err != nil {
		return s, err
	}
	if s.Active {
		if _, err := empty(ctx, "StopStream", c.obs.Stream.StopStream); err != nil {
			return s, err
		}
	}
	for s.Active {
		if err := pause(ctx, 250*time.Millisecond); err != nil {
			return s, err
		}
		s, err = c.StreamStatus(ctx)
		if err != nil {
			return s, err
		}
	}
	return s, nil
}

func pause(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}
