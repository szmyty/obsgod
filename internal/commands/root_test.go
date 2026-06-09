package commands

import (
	"bytes"
	"errors"
	"strings"
	"testing"

	"github.com/andreykaipov/goobs"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
)

func TestHelpDoesNotConnectToOBS(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("unexpected connection")
	})

	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "")
	cmd.SetArgs([]string{"--help"})
	cmd.SetOut(&bytes.Buffer{})
	cmd.SetErr(&bytes.Buffer{})

	if err := cmd.Execute(); err != nil {
		t.Fatalf("expected help to succeed without OBS, got %v", err)
	}
	if dialCount != 0 {
		t.Fatalf("expected help to avoid OBS connection, got %d dial attempts", dialCount)
	}
}

func TestVersionDoesNotConnectToOBS(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "1.2.3", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("unexpected connection")
	})

	stdout := &bytes.Buffer{}
	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "1.2.3")
	cmd.SetArgs([]string{"--version"})
	cmd.SetOut(stdout)
	cmd.SetErr(&bytes.Buffer{})

	if err := cmd.Execute(); err != nil {
		t.Fatalf("expected version to succeed without OBS, got %v", err)
	}
	if dialCount != 0 {
		t.Fatalf("expected version to avoid OBS connection, got %d dial attempts", dialCount)
	}
	if !strings.Contains(stdout.String(), "1.2.3") {
		t.Fatalf("expected version output to include build version, got %q", stdout.String())
	}
}

func TestOperationalCommandConnectsLazily(t *testing.T) {
	var dialCount int
	service := obs.NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 1}, "", func(address string, options ...goobs.Option) (*goobs.Client, error) {
		dialCount++
		return nil, errors.New("boom")
	})

	cmd := NewRoot(&config.Config{Host: "127.0.0.1", Port: 1}, service, "")
	cmd.SetArgs([]string{"stream", "start"})
	cmd.SetOut(&bytes.Buffer{})
	cmd.SetErr(&bytes.Buffer{})

	err := cmd.Execute()
	if err == nil {
		t.Fatal("expected stream start to attempt OBS connection")
	}
	if dialCount != 1 {
		t.Fatalf("expected one OBS connection attempt, got %d", dialCount)
	}
	if !strings.Contains(err.Error(), "connect to OBS at 127.0.0.1:1") {
		t.Fatalf("expected contextual connection error, got %v", err)
	}
}
