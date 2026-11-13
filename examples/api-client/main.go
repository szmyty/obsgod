// Example: go run ./examples/api-client --action status
// Connection credentials come from OBS_PASSWORD, never command arguments.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	api "github.com/szmyty/obsgod/pkg/api/v1"
)

func run() error {
	action := flag.String("action", "status", "status, start or stop")
	approve := flag.Bool("approve", false, "Approve streaming for this invocation")
	flag.Parse()
	if *action != "status" && *action != "start" && *action != "stop" {
		return fmt.Errorf("choose status, start or stop")
	}
	if *action != "status" && !*approve {
		return fmt.Errorf("explicit --approve is required")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	address := os.Getenv("OBSGOD_EXAMPLE_ADDRESS")
	if address == "" {
		address = "localhost:4455"
	}
	c, e := api.Connect(ctx, api.Connection{Address: address, Password: os.Getenv("OBS_PASSWORD")})
	if e != nil {
		return e
	}
	defer c.Close()
	var state api.StreamState
	switch *action {
	case "start":
		state, e = c.StartStream(ctx, api.Approval{Streaming: *approve})
	case "stop":
		state, e = c.StopStream(ctx, api.Approval{Streaming: *approve})
	default:
		state, e = c.StreamStatus(ctx)
	}
	if encode := json.NewEncoder(os.Stdout).Encode(api.NewResponse("example", state, e)); encode != nil {
		return encode
	}
	return e
}
func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
