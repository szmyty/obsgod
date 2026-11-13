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
	"sync"
	"time"

	"github.com/andreykaipov/goobs"
	"github.com/gorilla/websocket"
)

// Config describes an OBS connection. Password must come from a secret source.
type Config struct {
	Address  string
	Password string
	Timeout  time.Duration
	// Zero preserves request-only connections. Meter observations use their own
	// bounded connection so high-volume events cannot delay control operations.
	EventSubscriptions int
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

// ConnectionError reports a fixed, credential-free connection stage. The
// underlying server text, endpoint and password are never included.
type ConnectionError struct{ Kind string }

func (e *ConnectionError) Error() string {
	switch e.Kind {
	case "authentication":
		return "OBS WebSocket authentication failed; the managed password does not match"
	case "timeout":
		return "OBS control connection did not authenticate within its connection limit"
	case "refused":
		return "OBS WebSocket listener is not available"
	default:
		return "OBS control connection failed before authenticated readiness"
	}
}

func connectionFailureKind(err error, contextErr error, deadline, completedAt time.Time) string {
	// goobs owns an authentication timer as well as our attempt context. Its
	// untyped timeout can win the scheduling race before Context.Err is set.
	// Classify against the monotonic attempt deadline, never server/error text.
	if contextErr != nil || !completedAt.Before(deadline) || errors.Is(err, context.DeadlineExceeded) {
		return "timeout"
	}
	var closeErr *websocket.CloseError
	if errors.As(err, &closeErr) && closeErr.Code == 4009 {
		return "authentication"
	}
	var timeout net.Error
	if errors.As(err, &timeout) && timeout.Timeout() {
		return "timeout"
	}
	var opErr *net.OpError
	if errors.As(err, &opErr) {
		return "refused"
	}
	return "transport"
}

// Connect establishes an authenticated connection with bounded readiness.
func Connect(ctx context.Context, cfg Config) (*Client, error) {
	if _, _, err := net.SplitHostPort(cfg.Address); err != nil {
		return nil, errors.New("invalid OBS address: use host:port")
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 3 * time.Second
	}
	attempt, cancel := context.WithTimeout(ctx, cfg.Timeout)
	defer cancel()
	deadline, _ := attempt.Deadline()
	// goobs does not expose a half-open connection if authentication fails.
	// Own the transport so cancellation and unsuccessful handshakes release it.
	var mu sync.Mutex
	var transport net.Conn
	closeTransport := func() {
		mu.Lock()
		defer mu.Unlock()
		if transport != nil {
			_ = transport.Close()
		}
	}
	stopCancellation := context.AfterFunc(attempt, closeTransport)
	defer stopCancellation()
	dialer := &websocket.Dialer{HandshakeTimeout: cfg.Timeout, NetDialContext: func(_ context.Context, network, address string) (net.Conn, error) {
		conn, err := (&net.Dialer{Timeout: cfg.Timeout}).DialContext(attempt, network, address)
		if err != nil {
			return nil, err
		}
		mu.Lock()
		transport = conn
		if attempt.Err() != nil {
			_ = conn.Close()
		}
		mu.Unlock()
		return conn, nil
	}}
	type result struct {
		client *goobs.Client
		err    error
	}
	ch := make(chan result)
	go func() {
		c, err := goobs.New(cfg.Address, goobs.WithPassword(cfg.Password), goobs.WithDialer(dialer),
			goobs.WithResponseTimeoutDuration(cfg.Timeout), goobs.WithEventSubscriptions(cfg.EventSubscriptions), goobs.WithLogger(log.New(io.Discard, "", 0)))
		select {
		case ch <- result{c, err}:
		case <-attempt.Done():
			if c != nil {
				_ = c.Disconnect()
			}
		}
	}()
	select {
	case <-attempt.Done():
		closeTransport()
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, &ConnectionError{Kind: "timeout"}
	case r := <-ch:
		completedAt := time.Now()
		if r.err != nil || attempt.Err() != nil || !completedAt.Before(deadline) {
			if r.client != nil {
				_ = r.client.Disconnect()
			}
			closeTransport()
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			kind := connectionFailureKind(r.err, attempt.Err(), deadline, completedAt)
			return nil, &ConnectionError{Kind: kind}
		}
		// Stop the cancellation hook before canceling the attempt context. The
		// authenticated client's own requests retain their individual time limits.
		if !stopCancellation() {
			closeTransport()
			_ = r.client.Disconnect()
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			return nil, &ConnectionError{Kind: "timeout"}
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
	// The generated response uses zero-valued booleans for missing/null fields
	// and can coerce other JSON types. Neither establishes an idle stream.
	// Validate the raw flags before status can authorize Start/Stop or settings.
	if e = workflowKnownOutput(r.GetRaw(), "outputActive", "outputReconnecting"); e != nil {
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
