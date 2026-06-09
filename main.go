package main

import (
	"fmt"
	"os"

	"github.com/szmyty/obsgod/internal/commands"
	"github.com/szmyty/obsgod/internal/config"
	"github.com/szmyty/obsgod/internal/obs"
)

var version string

func main() {
	cfg := config.Default()
	service := obs.NewService(&cfg, version)
	defer func() {
		if err := service.Close(); err != nil {
			fmt.Fprintf(os.Stderr, "warning: disconnect from OBS: %v\n", err)
		}
	}()

	cmd := commands.NewRoot(&cfg, service, version)
	if err := cmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}
