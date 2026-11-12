package main

import (
	"context"
	"encoding/json"
	"io"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/szmyty/obsgod/internal/deckyinstall"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	ctx, timeout := context.WithTimeout(ctx, 90*time.Second)
	defer timeout()
	var input deckyinstall.Input
	decoder := json.NewDecoder(io.LimitReader(os.Stdin, 16385))
	decoder.DisallowUnknownFields()
	err := decoder.Decode(&input)
	var extra any
	if err == nil && decoder.Decode(&extra) != io.EOF {
		err = io.ErrUnexpectedEOF
	}
	message := "Invalid installer request"
	var report deckyinstall.Report
	if err == nil {
		report, err = deckyinstall.Run(ctx, input)
		message = "Decky confirmed the requested OBSGod version is installed and enabled"
		if input.Operation == "probe" {
			message = "Decky service and its connected Steam frontend are ready"
		}
		if input.Operation == "uninstall" {
			message = "Decky confirms OBSGod is absent from its loaded plugins"
		}
		if err != nil {
			message = err.Error()
		}
	}
	result := map[string]any{"ok": err == nil, "message": message}
	if err == nil {
		result["decky_version"] = report.DeckyVersion
		result["frontend_connected"] = report.FrontendConnected
		if report.Removed {
			result["removed"] = true
		}
		if report.Version != "" {
			result["version"] = report.Version
		}
	}
	_ = json.NewEncoder(os.Stdout).Encode(result)
	if err != nil {
		os.Exit(1)
	}
}
