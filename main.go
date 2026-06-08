package main

import (
	"fmt"
	"net/http"
	"os"
	"strconv"

	"github.com/andreykaipov/goobs"
	"github.com/muesli/coral"
)

var (
	host     string
	password string
	port     uint32
	version  string

	rootCmd = &coral.Command{
		Use:   "obsgod",
		Short: "obsgod is a command-line remote control for OBS",
	}

	client *goobs.Client
)

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	if client != nil {
		_ = client.Disconnect()
	}
}

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func init() {
	coral.OnInitialize(connectOBS)

	defaultHost := envOrDefault("OBS_HOST", "localhost")
	defaultPassword := os.Getenv("OBS_PASSWORD")
	defaultPort := uint32(4455)
	if v := os.Getenv("OBS_PORT"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 32); err == nil {
			defaultPort = uint32(n)
		}
	}

	rootCmd.PersistentFlags().StringVar(&host, "host", defaultHost, "OBS host to connect to (env: OBS_HOST)")
	rootCmd.PersistentFlags().StringVar(&password, "password", defaultPassword, "OBS password (env: OBS_PASSWORD)")
	rootCmd.PersistentFlags().Uint32VarP(&port, "port", "p", defaultPort, "OBS port to connect to (env: OBS_PORT)")
}

func getUserAgent() string {
	userAgent := "obsgod"
	if version != "" {
		userAgent += "/" + version
	}
	return userAgent
}

func connectOBS() {
	var err error
	client, err = goobs.New(
		host+fmt.Sprintf(":%d", port),
		goobs.WithPassword(password),
		goobs.WithRequestHeader(http.Header{"User-Agent": []string{getUserAgent()}}),
	)
	if err != nil {
		fmt.Println("error:", err)
		os.Exit(1)
	}
}
