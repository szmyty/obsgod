package automation

import (
	"context"
	"errors"
	"net"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

type closeCountingConnection struct {
	net.Conn
	closes atomic.Int32
}

func (c *closeCountingConnection) Close() error { c.closes.Add(1); return c.Conn.Close() }

func TestOwnedConnectionClosesPhysicalSocketOnce(t *testing.T) {
	a, b := net.Pipe()
	defer b.Close()
	physical := &closeCountingConnection{Conn: a}
	owned := &ownedConnection{Conn: physical}
	for i := 0; i < 3; i++ {
		if err := owned.Close(); err != nil {
			t.Fatal(err)
		}
	}
	if physical.closes.Load() != 1 {
		t.Fatalf("physical transport close count=%d", physical.closes.Load())
	}
}

func TestCloseReportsUnconfirmedShutdownWithoutRawDetails(t *testing.T) {
	var closes atomic.Int32
	c := &Client{closeTransport: func() error { closes.Add(1); return errors.New("private endpoint/password close error") }}
	err := c.Close()
	if err == nil || strings.Contains(err.Error(), "private") || strings.Contains(err.Error(), "password") {
		t.Fatalf("raw shutdown failure was hidden or exposed: %v", err)
	}
	if next := c.Close(); next != err || closes.Load() != 1 {
		t.Fatal("close failure or ownership changed on repeat")
	}
	select {
	case <-c.cleanupDone:
	default:
		t.Fatal("empty protocol cleanup did not finish")
	}
}

func TestCancelledRealRequestClosesPromptlyAndProtocolCleanupFinishes(t *testing.T) {
	c := dialFixture(t, &fakeOBS{hangStatus: true})
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	if _, err := c.StreamStatus(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("request cancellation: %v", err)
	}
	start := time.Now()
	if err := c.Close(); err != nil {
		t.Fatal(err)
	}
	if time.Since(start) > 100*time.Millisecond {
		t.Fatal("shutdown waited for goobs request mutex")
	}
	select {
	case <-c.cleanupDone:
	case <-time.After(time.Second):
		t.Fatal("bounded protocol cleanup retained a goroutine")
	}
	if err := c.Close(); err != nil {
		t.Fatal(err)
	}
}
