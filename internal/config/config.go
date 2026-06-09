package config

import (
	"os"
	"strconv"
)

const (
	defaultHost = "localhost"
	defaultPort = uint32(4455)
)

type Config struct {
	Host     string
	Port     uint32
	Password string
}

func Default() Config {
	cfg := Config{
		Host:     envOrDefault("OBS_HOST", defaultHost),
		Port:     defaultPort,
		Password: os.Getenv("OBS_PASSWORD"),
	}

	if v := os.Getenv("OBS_PORT"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 32); err == nil {
			cfg.Port = uint32(n)
		}
	}

	return cfg
}

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
