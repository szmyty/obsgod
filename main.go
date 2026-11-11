package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/szmyty/obsgod/internal/commands"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
)

var version string
var commitSHA string

func main() {
	buildVersion := version
	if commitSHA != "" {
		buildVersion += " (" + commitSHA + ")"
	}
	cfg := config.Default()
	service := obs.NewService(&cfg, buildVersion)
	defer func() {
		if err := service.Close(); err != nil {
			fmt.Fprintf(os.Stderr, "warning: disconnect from OBS: %v\n", err)
		}
	}()

	cmd := commands.NewRoot(&cfg, service, buildVersion)
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	if err := cmd.ExecuteContext(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}
